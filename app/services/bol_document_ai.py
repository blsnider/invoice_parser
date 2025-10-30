from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions
import logging
from typing import Dict, Any, List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from datetime import datetime, date
import re

from app.core.config import settings
from app.models.bol import BOLData, ShipmentItem, Address
from app.utils.exceptions import DocumentAIError

logger = logging.getLogger(__name__)


class BOLDocumentAIService:
    def __init__(self):
        self.project_id = settings.PROJECT_ID
        self.location = settings.PROCESSOR_LOCATION
        self.processor_id = settings.BOL_PROCESSOR_ID
        self.client: Optional[documentai.DocumentProcessorServiceClient] = None
        self.executor = ThreadPoolExecutor(max_workers=3)

    def initialize(self):
        try:
            opts = ClientOptions(
                api_endpoint=f"{self.location}-documentai.googleapis.com"
            )
            self.client = documentai.DocumentProcessorServiceClient(client_options=opts)
            logger.info("BOL Document AI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize BOL Document AI client: {e}")
            raise DocumentAIError(f"BOL Document AI initialization failed: {str(e)}")

    async def process_document(
        self,
        content: bytes,
        mime_type: str = "application/pdf"
    ) -> documentai.Document:
        try:
            if not self.client:
                self.initialize()

            loop = asyncio.get_event_loop()
            document = await loop.run_in_executor(
                self.executor,
                self._process_document_sync,
                content,
                mime_type
            )

            return document

        except Exception as e:
            logger.error(f"BOL document processing failed: {e}")
            raise DocumentAIError(f"Failed to process BOL document: {str(e)}")

    def _process_document_sync(
        self,
        content: bytes,
        mime_type: str
    ) -> documentai.Document:
        if not self.processor_id:
            raise DocumentAIError("BOL_PROCESSOR_ID not configured")

        name = self.client.processor_path(
            self.project_id,
            self.location,
            self.processor_id
        )

        raw_document = documentai.RawDocument(
            content=content,
            mime_type=mime_type
        )

        request = documentai.ProcessRequest(
            name=name,
            raw_document=raw_document
        )

        result = self.client.process_document(request=request)
        return result.document

    async def extract_multiple_bols(
        self,
        document: documentai.Document,
        document_id: str
    ) -> List[BOLData]:
        """Extract multiple BOLs from a single document (one per page)"""
        try:
            # Check if we have pages to process
            if not document.pages:
                # No pages, fall back to single BOL extraction
                bol_data = await self.extract_bol_data(document, document_id)
                return [bol_data]

            # Process each page as a separate BOL
            bol_data_list = []
            for page_num, page in enumerate(document.pages):
                # Generate unique ID for each BOL
                bol_id = f"{document_id}-{page_num+1:03d}"

                # Extract text from this specific page
                page_text = self._get_page_text(document, page)

                # Extract entities from this page's text
                entities = self._extract_from_text(page_text)

                # Extract form fields from this page if available
                if hasattr(page, 'form_fields') and page.form_fields:
                    page_entities = self._extract_entities_from_page(page, document.text)
                    # Merge with text-extracted entities
                    entities.update(page_entities)

                # Extract shipment items from this page
                shipment_items = self._extract_items_from_page(page, page_text)

                # Create BOLData for this page
                bol_data = BOLData(
                    bol_id=bol_id,
                    bol_number=entities.get('bol_number'),
                    pro_number=entities.get('pro_number'),
                    ship_date=self._parse_date(entities.get('ship_date')),
                    shipper=self._extract_address_from_entities(entities, 'shipper'),
                    consignee=self._extract_address_from_entities(entities, 'consignee'),
                    carrier_name=entities.get('carrier_name'),
                    freight_charge_terms=entities.get('freight_charge_terms'),
                    total_weight=self._parse_float(entities.get('total_weight')),
                    weight_unit='LBS',
                    total_pallets=self._parse_int(entities.get('total_pallets')),
                    shipment_items=shipment_items,
                    raw_text=page_text,
                    metadata={
                        'page_number': page_num + 1,
                        'total_pages': len(document.pages),
                        'processing_time': datetime.utcnow().isoformat()
                    }
                )

                # Only add BOLs that have at least a BOL number or meaningful data
                if bol_data.bol_number or bol_data.shipper or bol_data.consignee:
                    bol_data_list.append(bol_data)
                else:
                    logger.warning(f"Page {page_num + 1} has no BOL data, skipping")

            # If no valid BOLs found, return at least one with available data
            if not bol_data_list:
                bol_data = await self.extract_bol_data(document, document_id)
                return [bol_data]

            return bol_data_list

        except Exception as e:
            logger.error(f"Failed to extract multiple BOLs: {e}")
            raise DocumentAIError(f"Multiple BOL extraction failed: {str(e)}")

    async def extract_bol_data(
        self,
        document: documentai.Document,
        bol_id: str
    ) -> BOLData:
        try:
            entities = self._extract_entities(document)
            shipment_items = self._extract_shipment_items(document)
            confidence_scores = self._calculate_confidence_scores(document)

            bol_data = BOLData(
                bol_id=bol_id,
                bol_number=entities.get("bol_number") or entities.get("bill_of_lading_number"),
                pro_number=entities.get("pro_number") or entities.get("tracking_number"),
                scac_code=entities.get("scac_code") or entities.get("carrier_code"),

                ship_date=self._parse_date(entities.get("ship_date") or entities.get("pickup_date")),
                delivery_date=self._parse_date(entities.get("delivery_date") or entities.get("expected_delivery")),

                shipper=self._extract_address_from_entities(entities, "shipper"),
                consignee=self._extract_address_from_entities(entities, "consignee"),
                bill_to=self._extract_address_from_entities(entities, "bill_to"),

                carrier_name=entities.get("carrier_name") or entities.get("carrier"),
                driver_name=entities.get("driver_name") or entities.get("driver"),
                truck_number=entities.get("truck_number") or entities.get("tractor_number"),
                trailer_number=entities.get("trailer_number"),
                seal_number=entities.get("seal_number") or entities.get("seal"),

                origin_terminal=entities.get("origin_terminal") or entities.get("origin"),
                destination_terminal=entities.get("destination_terminal") or entities.get("destination"),

                freight_charge_terms=entities.get("freight_charge_terms") or entities.get("payment_terms"),
                payment_terms=entities.get("payment_terms"),

                total_weight=self._parse_float(entities.get("total_weight") or entities.get("weight")),
                weight_unit=entities.get("weight_unit", "LBS"),
                total_pieces=self._parse_int(entities.get("total_pieces") or entities.get("pieces")),
                total_pallets=self._parse_int(entities.get("total_pallets") or entities.get("pallets")),

                shipment_items=shipment_items,

                special_instructions=entities.get("special_instructions") or entities.get("notes"),
                delivery_instructions=entities.get("delivery_instructions"),

                freight_charges=self._parse_amount(entities.get("freight_charges")),
                accessorial_charges=self._parse_amount(entities.get("accessorial_charges")),
                total_charges=self._parse_amount(entities.get("total_charges") or entities.get("total_amount")),

                shipment_type=entities.get("shipment_type") or entities.get("service_type"),
                service_type=entities.get("service_type") or entities.get("service_level"),

                confidence_scores=confidence_scores,
                raw_text=document.text,
                metadata={
                    "page_count": len(document.pages),
                    "processing_time": datetime.utcnow().isoformat()
                }
            )

            return bol_data

        except Exception as e:
            logger.error(f"Failed to extract BOL data: {e}")
            raise DocumentAIError(f"BOL data extraction failed: {str(e)}")

    def _extract_entities(self, document: documentai.Document) -> Dict[str, Any]:
        entities = {}

        # First try to extract from form fields (Form Parser output)
        for page in document.pages:
            if hasattr(page, 'form_fields') and page.form_fields:
                for field in page.form_fields:
                    # Get field name and value
                    field_name = ""
                    field_value = ""

                    if field.field_name and field.field_name.text_anchor:
                        field_name = self._get_text_from_anchor(document.text, field.field_name.text_anchor)

                    if field.field_value and field.field_value.text_anchor:
                        field_value = self._get_text_from_anchor(document.text, field.field_value.text_anchor)

                    if field_name:
                        # Map common BOL field names to our entity keys
                        mapped_name = self._map_form_field_to_entity(field_name)
                        if mapped_name:
                            entities[mapped_name] = field_value.strip()

        # If no form fields found, try entities (for other processor types)
        if not entities and document.entities:
            for entity in document.entities:
                entity_type = entity.type_.lower().replace(" ", "_")

                if entity.mention_text:
                    entities[entity_type] = entity.mention_text
                else:
                    entities[entity_type] = entity.text_anchor.content if entity.text_anchor else None

                if entity.properties:
                    for prop in entity.properties:
                        prop_type = f"{entity_type}_{prop.type_.lower().replace(' ', '_')}"
                        if prop.mention_text:
                            entities[prop_type] = prop.mention_text
                        elif prop.text_anchor:
                            entities[prop_type] = prop.text_anchor.content

        # If still no entities, extract from raw text
        if not entities and document.text:
            entities = self._extract_from_text(document.text)

        return entities

    def _get_text_from_anchor(self, full_text: str, text_anchor) -> str:
        """Extract text using text anchor offsets"""
        if not text_anchor.text_segments:
            return ""

        text = ""
        for segment in text_anchor.text_segments:
            start = segment.start_index if segment.start_index else 0
            end = segment.end_index if segment.end_index else len(full_text)
            text += full_text[start:end]

        return text.strip()

    def _map_form_field_to_entity(self, field_name: str) -> Optional[str]:
        """Map form field names to entity keys"""
        field_lower = field_name.lower().strip()

        # BOL number mappings
        if 'bol #' in field_lower or 'bol#' in field_lower or 'bill of lading' in field_lower:
            return 'bol_number'
        elif 'pro #' in field_lower or 'pro#' in field_lower or 'pro number' in field_lower:
            return 'pro_number'
        elif 'carrier' in field_lower and 'name' in field_lower:
            return 'carrier_name'
        elif 'shipper' in field_lower:
            if 'name' in field_lower:
                return 'shipper_name'
            elif 'address' in field_lower:
                return 'shipper_address'
            else:
                return 'shipper'
        elif 'consignee' in field_lower:
            if 'name' in field_lower:
                return 'consignee_name'
            elif 'address' in field_lower:
                return 'consignee_address'
            else:
                return 'consignee'
        elif 'date' in field_lower:
            if 'ship' in field_lower or 'pickup' in field_lower:
                return 'ship_date'
            elif 'delivery' in field_lower:
                return 'delivery_date'
            else:
                return 'date'
        elif 'weight' in field_lower:
            if 'total' in field_lower:
                return 'total_weight'
            else:
                return 'weight'
        elif 'freight charge' in field_lower:
            return 'freight_charge_terms'

        return None

    def _extract_from_text(self, text: str) -> Dict[str, Any]:
        """Extract BOL data from raw text using patterns"""
        import re
        entities = {}

        # Extract BOL number - handle both "BOL #" and "BOL #\n" patterns
        bol_patterns = [
            r'BOL\s*#\s*\n\s*([\d]+)',  # BOL # on separate line
            r'BOL\s*#\s*([\d]+)',  # BOL # on same line
        ]
        for pattern in bol_patterns:
            bol_match = re.search(pattern, text)
            if bol_match:
                entities['bol_number'] = bol_match.group(1)
                break

        # Extract PRO number - look for PRO # followed by number (may have DATE in between)
        pro_patterns = [
            r'PRO\s*#[\s\n]*DATE[\s\n]+([\d]+)',  # PRO # DATE <number>
            r'PRO\s*#[\s\n]+([\d]+)',  # PRO # <number>
        ]
        for pattern in pro_patterns:
            pro_match = re.search(pattern, text)
            if pro_match and len(pro_match.group(1)) > 3:  # Ensure it's a real PRO number
                entities['pro_number'] = pro_match.group(1)
                break

        # Extract carrier name - handle multi-line carrier names
        carrier_patterns = [
            r'NAME OF CARRIER[\s\n]+PRO\s*#[\s\n]+DATE[\s\n]+BOL\s*#[\s\n]+([^\n]+(?:\n[^\d\n][^\n]+)?)',
            r'NAME OF CARRIER[\s\n]+([^\n]+(?:\s*-\s*[^\n]+)?)',  # Handle names with dashes
        ]
        for pattern in carrier_patterns:
            carrier_match = re.search(pattern, text)
            if carrier_match:
                carrier_text = carrier_match.group(1).strip()
                # Clean up - remove date patterns and numbers
                carrier_text = re.sub(r'\d{1,2}/\d{1,2}/\d{4}.*$', '', carrier_text).strip()
                if carrier_text and 'PRO' not in carrier_text and 'DATE' not in carrier_text:
                    entities['carrier_name'] = carrier_text
                    break

        # Extract date - look for actual date pattern, not just "DATE" header
        date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
            r'(\d{1,2}/\d{1,2}/\d{2})(?!\d)',  # MM/DD/YY
            r'(\d{1,2}-\d{1,2}-\d{4})',  # MM-DD-YYYY
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, text)
            if date_match:
                entities['ship_date'] = date_match.group(1)
                break

        # Extract shipper info - look for ORIGIN: section
        # The format is: ORIGIN:\n<Company Name>\n<Street Address>\n<City, State ZIP>
        origin_section = re.search(
            r'ORIGIN:[\s\n]+([^\n]+)[\s\n]+(\d+[^\n]+)[\s\n]+([^,\n]+,\s*[A-Z]{2}\s+\d{5})',
            text
        )

        if origin_section:
            # Extract shipper name (first line after ORIGIN:)
            shipper_name = origin_section.group(1).strip()
            entities['shipper_name'] = shipper_name

            # Extract street address
            entities['shipper_street'] = origin_section.group(2).strip()

            # Extract city, state, zip
            city_state_zip = origin_section.group(3).strip()
            city_state_match = re.match(r'([^,]+),\s*([A-Z]{2})\s+(\d{5})', city_state_zip)
            if city_state_match:
                entities['shipper_city'] = city_state_match.group(1)
                entities['shipper_state'] = city_state_match.group(2)
                entities['shipper_zip'] = city_state_match.group(3)
        else:
            # Fallback: Try to extract from SHIPPER INFORMATION section
            shipper_section = re.search(
                r'SHIPPER INFORMATION[\s\n]+(?:CONSIGNEE INFORMATION[\s\n]+)?([^\n]+)',
                text
            )
            if shipper_section:
                shipper_name = shipper_section.group(1).strip()
                # Clean up - remove "CONSIGNEE INFORMATION" if captured
                shipper_name = re.sub(r'CONSIGNEE INFORMATION.*$', '', shipper_name).strip()
                # Clean up C/O
                shipper_name = re.sub(r'/\s*C\/O.*$', '', shipper_name).strip()
                if shipper_name and 'ORIGIN:' not in shipper_name:
                    entities['shipper_name'] = shipper_name

        # Extract shipper contact info
        shipper_contact = re.search(r'(Donna Merlin|[A-Z][a-z]+\s+[A-Z][a-z]+)[\s\n]+(\d{3}[-.]?\d{3}[-.]?\d{4})', text)
        if shipper_contact:
            entities['shipper_contact_name'] = shipper_contact.group(1)
            entities['shipper_contact_phone'] = shipper_contact.group(2).replace('.', '-')

        # Extract consignee info with better pattern
        consignee_patterns = [
            r'(\d+)\s*[-–]\s*([^\n]*Scheels)',  # Format: "58 - Omaha Scheels"
            r'CONSIGNEE:[\s\n]+(\d+\s*[-–]\s*[^\n]+)',  # General numbered format
            r'CONSIGNEE:[\s\n]+([^\n]+)',  # Fallback
        ]
        for pattern in consignee_patterns:
            consignee_match = re.search(pattern, text)
            if consignee_match:
                if len(consignee_match.groups()) > 1 and 'Scheels' in pattern:
                    # Handle "58 - Omaha Scheels" format
                    entities['consignee_name'] = consignee_match.group(2).strip()
                else:
                    consignee_text = consignee_match.group(1).strip()
                    # Clean up the name
                    consignee_text = re.sub(r'^\d+\s*[-–]\s*', '', consignee_text)
                    if consignee_text and 'DOCK TYPE' not in consignee_text:
                        entities['consignee_name'] = consignee_text
                break

        # Extract complete consignee section - everything from CONSIGNEE: to the next section
        # This ensures we get the right address, not the bill-to address
        consignee_block = re.search(
            r'CONSIGNEE:[\s\n]+([\s\S]*?)(?:DOCK TYPE|ACCESS\.|DELIVERY #|PICK UP #|NOTES|FREIGHT READY TIME|FREIGHT CHARGES)',
            text
        )

        if consignee_block:
            consignee_text = consignee_block.group(1)

            # Extract address - look for street address pattern
            # May have suite/apt on next line
            addr_match = re.search(
                r'(\d+[^\n]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Circle|Way)[^\n]*)(?:[\s\n]+(?:Ste|Suite|Apt|Unit)\s+[^\n]+)?[\s\n]+([^,\n]+,\s*[A-Z]{2}\s+\d{5})',
                consignee_text
            )

            if addr_match:
                street = addr_match.group(1).strip()
                # Check if there's a suite/apt on the next line
                suite_match = re.search(
                    r'(\d+[^\n]+)[\s\n]+((?:Ste|Suite|Apt|Unit)\s+[^\n]+)',
                    consignee_text
                )
                if suite_match and suite_match.group(1) in street:
                    # Add suite to street address
                    street = f"{street}, {suite_match.group(2).strip()}"

                entities['consignee_street'] = street
                city_state_zip = addr_match.group(2).strip()
                city_state_match = re.match(r'([^,]+),\s*([A-Z]{2})\s+(\d{5})', city_state_zip)
                if city_state_match:
                    entities['consignee_city'] = city_state_match.group(1)
                    entities['consignee_state'] = city_state_match.group(2)
                    entities['consignee_zip'] = city_state_match.group(3)

        # Extract consignee contact
        consignee_contact = re.search(r'Shipping\s*&?\s*Receiving[\s\n]+(\d{3}[-.]?\d{3}[-.]?\d{4})', text)
        if consignee_contact:
            entities['consignee_contact_name'] = 'Shipping & Receiving'
            entities['consignee_contact_phone'] = consignee_contact.group(1).replace('.', '-')

        # Extract freight charges terms - just the term, not the whole line
        freight_match = re.search(r'FREIGHT CHARGES:\s*(Collect|Prepaid|Third Party)', text, re.IGNORECASE)
        if freight_match:
            entities['freight_charge_terms'] = freight_match.group(1).capitalize()

        # Extract Bill To information
        bill_to_match = re.search(
            r'SEND FREIGHT BILL TO:[\s\n]+([^\n]+)[\s\n]+(\d+[^\n]+)[\s\n]+([^,\n]+,\s*[A-Z]{2}\s+\d{5})',
            text
        )
        if bill_to_match:
            entities['bill_to_name'] = bill_to_match.group(1).strip()
            entities['bill_to_street'] = bill_to_match.group(2).strip()
            city_state_zip = bill_to_match.group(3).strip()
            city_state_match = re.match(r'([^,]+),\s*([A-Z]{2})\s+(\d{5})', city_state_zip)
            if city_state_match:
                entities['bill_to_city'] = city_state_match.group(1)
                entities['bill_to_state'] = city_state_match.group(2)
                entities['bill_to_zip'] = city_state_match.group(3)

        # Extract total weight - look for pattern with "lbs"
        weight_patterns = [
            r'TOTAL[\s\n]+\d+\s+Pallets[\s\n]+(\d+)\s*lbs',  # TOTAL section
            r'SHIPPING WEIGHT[\s\n]+[^\n]*?(\d+)\s*lbs',  # Shipping weight line
            r'(\d{3,})\s*lbs',  # 3+ digit weight fallback
        ]
        for pattern in weight_patterns:
            weight_match = re.search(pattern, text, re.IGNORECASE)
            if weight_match:
                entities['total_weight'] = weight_match.group(1)
                break

        # Extract pallets
        pallet_patterns = [
            r'(\d+)\s+Pallets[\s\n]+\d+\s*lbs',  # In TOTAL section
            r'(\d+)\s*Pallets?',  # General pattern
        ]
        for pattern in pallet_patterns:
            pallet_match = re.search(pattern, text, re.IGNORECASE)
            if pallet_match:
                entities['total_pallets'] = pallet_match.group(1)
                break

        # Extract special instructions
        special_match = re.search(r'\*+Special Instructions\*+[\s\n]+([^\n]+)', text)
        if special_match:
            entities['special_instructions'] = special_match.group(1).strip()

        # Extract additional identifiers
        billing_id_match = re.search(r'BILLING ID[\s\n]+(\d+)', text)
        if billing_id_match:
            entities['billing_id'] = billing_id_match.group(1)

        customer_po_match = re.search(r'CUSTOMER PO[\s\n]+(\d+)', text)
        if customer_po_match:
            entities['customer_po'] = customer_po_match.group(1)

        custom_id_match = re.search(r'CUSTOM ID[\s\n]+(\d+)', text)
        if custom_id_match:
            entities['custom_id'] = custom_id_match.group(1)

        return entities

    def _get_page_text(self, document: documentai.Document, page: documentai.Document.Page) -> str:
        """Extract text from a specific page"""
        if not page.layout or not page.layout.text_anchor:
            return ""

        text = ""
        for segment in page.layout.text_anchor.text_segments:
            start = segment.start_index if segment.start_index else 0
            end = segment.end_index if segment.end_index else len(document.text)
            text += document.text[start:end]

        return text

    def _extract_entities_from_page(self, page: documentai.Document.Page, full_text: str) -> Dict[str, Any]:
        """Extract entities from form fields on a specific page"""
        entities = {}

        if not hasattr(page, 'form_fields') or not page.form_fields:
            return entities

        for field in page.form_fields:
            field_name = ""
            field_value = ""

            if field.field_name and field.field_name.text_anchor:
                field_name = self._get_text_from_anchor(full_text, field.field_name.text_anchor)

            if field.field_value and field.field_value.text_anchor:
                field_value = self._get_text_from_anchor(full_text, field.field_value.text_anchor)

            if field_name:
                mapped_name = self._map_form_field_to_entity(field_name)
                if mapped_name:
                    entities[mapped_name] = field_value.strip()

        return entities

    def _extract_items_from_page(self, page: documentai.Document.Page, page_text: str) -> List[ShipmentItem]:
        """Extract shipment items from a specific page"""
        items = []

        # Try to extract from tables on this page
        if hasattr(page, 'tables') and page.tables:
            for table in page.tables:
                table_items = self._extract_items_from_table(table)
                items.extend(table_items)

        # If no table items found, try text extraction
        if not items:
            import re

            # Look for item section with description, quantity, class, and weight
            item_section = re.search(
                r'#\s*PACKAGES[\s\S]*?(?=FREIGHT CHARGES:|TOTAL|RECEIVED|$)',
                page_text,
                re.IGNORECASE
            )

            if item_section:
                item_text = item_section.group(0)

                # Extract item details into a dictionary first
                item_data = {}

                # Description with NMFC
                nmfc_match = re.search(r'NMFC\s*#([\d-]+)[,\s]+([^,\n]+)', item_text)
                if nmfc_match:
                    item_data['nmfc_code'] = nmfc_match.group(1)
                    description = nmfc_match.group(2).strip()
                    # Clean up description
                    item_data['description'] = re.sub(r'PCF.*$', '', description).strip()

                # Quantity and type (e.g., "1 Pallets")
                qty_match = re.search(r'(\d+)\s+(Pallets?|Cartons?|Boxes?|Pieces?)', item_text, re.IGNORECASE)
                if qty_match:
                    item_data['quantity'] = int(qty_match.group(1))
                    item_data['packaging_type'] = qty_match.group(2).rstrip('s')  # Remove plural 's'

                # Weight
                weight_match = re.search(r'(\d+)\s*lbs', item_text, re.IGNORECASE)
                if weight_match:
                    item_data['weight'] = float(weight_match.group(1))
                    item_data['weight_unit'] = "LBS"

                # Class
                class_match = re.search(r'CLASS\s*\n?\s*(\d+)', item_text)
                if class_match:
                    item_data['freight_class'] = class_match.group(1)

                # Dimensions
                dim_match = re.search(r'(\d+)\s*x\s*(\d+)\s*x\s*(\d+)', item_text)
                if dim_match:
                    item_data['dimensions'] = f"{dim_match.group(1)}x{dim_match.group(2)}x{dim_match.group(3)}"

                # Only create ShipmentItem if we have a description (required field)
                if item_data.get('description'):
                    item = ShipmentItem(**item_data)
                    items.append(item)
                elif item_data.get('nmfc_code'):
                    # If we only have NMFC code but no description, use a generic description
                    item_data['description'] = f"Item with NMFC #{item_data['nmfc_code']}"
                    item = ShipmentItem(**item_data)
                    items.append(item)

            # Fallback: Pattern to find items like "NMFC #61700-03, Electrical appliances"
            if not items:
                item_pattern = r'NMFC\s*#([\d-]+)[,\s]+([^,\n]+)'
                item_matches = re.findall(item_pattern, page_text)

                for nmfc, desc in item_matches:
                    item = ShipmentItem(
                        nmfc_code=nmfc.strip(),
                        description=desc.strip()
                    )
                    items.append(item)

        return items

    def _detect_multiple_bols(self, text: str) -> List[Dict[str, Any]]:
        """Detect and split multiple BOLs in a single document"""
        import re

        # Find all BOL numbers and their positions
        bol_pattern = r'BOL\s*#\s*([\d]+)'
        bol_matches = [(m.group(1), m.start()) for m in re.finditer(bol_pattern, text)]

        if len(bol_matches) <= 1:
            # Single BOL or no BOL found
            return [{'text': text, 'bol_number': bol_matches[0][0] if bol_matches else None}]

        # Split document into sections for each BOL
        bol_sections = []
        for i, (bol_num, start_pos) in enumerate(bol_matches):
            # Find the end position (start of next BOL or end of document)
            if i < len(bol_matches) - 1:
                end_pos = bol_matches[i + 1][1]
            else:
                end_pos = len(text)

            # Extract section text
            section_text = text[start_pos:end_pos]
            bol_sections.append({
                'text': section_text,
                'bol_number': bol_num,
                'position': start_pos
            })

        return bol_sections

    def _extract_from_text_section(self, text: str, bol_number: str) -> Dict[str, Any]:
        """Extract BOL data from a text section for a specific BOL"""
        import re
        entities = {}

        # Set the known BOL number
        entities['bol_number'] = bol_number

        # Extract PRO number
        pro_match = re.search(r'PRO\s*#\s*([\d\w-]+)', text)
        if pro_match:
            entities['pro_number'] = pro_match.group(1)

        # Extract carrier name
        carrier_match = re.search(r'NAME OF CARRIER[\s\n]+([^\n]+)', text)
        if carrier_match:
            entities['carrier_name'] = carrier_match.group(1).strip()

        # Extract date
        date_match = re.search(r'DATE[\s\n]+(\d{1,2}/\d{1,2}/\d{2,4})', text)
        if date_match:
            entities['ship_date'] = date_match.group(1)

        # Extract shipper info
        shipper_match = re.search(r'SHIPPER INFORMATION[\s\n]+([^\n]+)', text)
        if shipper_match:
            shipper_text = shipper_match.group(1).strip()
            if 'CONSIGNEE' not in shipper_text and 'ORIGIN:' not in shipper_text:
                entities['shipper_name'] = shipper_text

        # Extract consignee info
        consignee_match = re.search(r'CONSIGNEE:[\s\n]+(?:[-\s]+)?([^\n]+)', text)
        if consignee_match:
            consignee_text = consignee_match.group(1).strip()
            consignee_text = re.sub(r'^[-\s]+', '', consignee_text)
            entities['consignee_name'] = consignee_text

        # Extract freight charges terms
        freight_match = re.search(r'FREIGHT CHARGES:\s*(\w+)', text)
        if freight_match:
            entities['freight_charge_terms'] = freight_match.group(1)

        # Extract total weight for this BOL section
        weight_match = re.search(r'(\d+)\s*lbs', text, re.IGNORECASE)
        if weight_match:
            entities['total_weight'] = weight_match.group(1)

        # Extract pallets for this BOL section
        pallet_match = re.search(r'(\d+)\s*Pallets?', text, re.IGNORECASE)
        if pallet_match:
            entities['total_pallets'] = pallet_match.group(1)

        return entities

    def _extract_shipment_items_from_section(
        self,
        document: documentai.Document,
        section_start: int,
        section_text: str
    ) -> List[ShipmentItem]:
        """Extract shipment items for a specific BOL section"""
        # For now, use basic text extraction from the section
        # Could be enhanced to use table detection based on position
        items = []

        # Look for shipment items in the section text
        import re

        # Pattern to find items like "NMFC #15520-05, Athletic or Sporting Goods"
        item_pattern = r'NMFC\s*#[\d-]+,\s*([^,\n]+)'
        item_matches = re.findall(item_pattern, section_text)

        for desc in item_matches:
            items.append(ShipmentItem(description=desc.strip()))

        return items if items else []

    def _extract_shipment_items(self, document: documentai.Document) -> List[ShipmentItem]:
        items = []

        for entity in document.entities:
            if entity.type_.lower() in ["line_item", "shipment_item", "cargo_item"]:
                item_data = {}

                for prop in entity.properties:
                    prop_type = prop.type_.lower().replace(" ", "_")
                    value = prop.mention_text or (prop.text_anchor.content if prop.text_anchor else None)

                    if prop_type in ["weight", "quantity", "pieces"]:
                        item_data[prop_type] = self._parse_float(value)
                    else:
                        item_data[prop_type] = value

                if item_data.get("description") or item_data.get("commodity"):
                    shipment_item = ShipmentItem(
                        description=item_data.get("description") or item_data.get("commodity", ""),
                        quantity=item_data.get("quantity"),
                        weight=item_data.get("weight"),
                        weight_unit=item_data.get("weight_unit"),
                        dimensions=item_data.get("dimensions"),
                        packaging_type=item_data.get("packaging_type") or item_data.get("package_type"),
                        hazmat_class=item_data.get("hazmat_class") or item_data.get("hazmat"),
                        nmfc_code=item_data.get("nmfc_code") or item_data.get("nmfc"),
                        freight_class=item_data.get("freight_class") or item_data.get("class")
                    )
                    items.append(shipment_item)

        if not items and document.pages:
            for page in document.pages:
                if page.tables:
                    for table in page.tables:
                        table_items = self._extract_items_from_table(table)
                        items.extend(table_items)

        return items

    def _extract_items_from_table(self, table) -> List[ShipmentItem]:
        items = []

        if not table.header_rows or not table.body_rows:
            return items

        headers = []
        for cell in table.header_rows[0].cells:
            header_text = cell.layout.text_anchor.content if cell.layout and cell.layout.text_anchor else ""
            headers.append(header_text.lower().strip())

        for row in table.body_rows:
            row_data = {}
            for idx, cell in enumerate(row.cells):
                if idx < len(headers):
                    cell_text = cell.layout.text_anchor.content if cell.layout and cell.layout.text_anchor else ""
                    row_data[headers[idx]] = cell_text.strip()

            if row_data:
                item = self._parse_table_row_to_shipment_item(row_data)
                if item:
                    items.append(item)

        return items

    def _parse_table_row_to_shipment_item(self, row_data: Dict[str, str]) -> Optional[ShipmentItem]:
        description = (
            row_data.get("description") or
            row_data.get("commodity") or
            row_data.get("product") or
            row_data.get("item")
        )

        if not description:
            return None

        return ShipmentItem(
            description=description,
            quantity=self._parse_float(row_data.get("quantity") or row_data.get("qty") or row_data.get("pieces")),
            weight=self._parse_float(row_data.get("weight") or row_data.get("wt")),
            weight_unit=row_data.get("unit") or "LBS",
            dimensions=row_data.get("dimensions") or row_data.get("dims"),
            packaging_type=row_data.get("package type") or row_data.get("pkg type"),
            hazmat_class=row_data.get("hazmat") or row_data.get("hm"),
            nmfc_code=row_data.get("nmfc"),
            freight_class=row_data.get("class") or row_data.get("freight class")
        )

    def _extract_address_from_entities(self, entities: Dict[str, Any], prefix: str) -> Optional[Address]:
        # Try to extract structured address fields
        # Direct field mapping
        field_mappings = {
            'name': [f'{prefix}_name', f'{prefix}'],
            'street': [f'{prefix}_street', f'{prefix}_address', f'{prefix}_addr'],
            'city': [f'{prefix}_city'],
            'state': [f'{prefix}_state'],
            'postal_code': [f'{prefix}_zip', f'{prefix}_postal_code', f'{prefix}_postal'],
            'contact_name': [f'{prefix}_contact_name', f'{prefix}_contact'],
            'contact_phone': [f'{prefix}_contact_phone', f'{prefix}_phone']
        }

        address_fields = {}
        for field, possible_keys in field_mappings.items():
            for key in possible_keys:
                if key in entities and entities[key]:
                    address_fields[field] = entities[key]
                    break

        # Default country to USA if not specified
        if 'country' not in address_fields:
            address_fields['country'] = entities.get(f"{prefix}_country") or "USA"

        # Also check for complete address blocks
        if entities.get(f"{prefix}_address_block"):
            address_parts = self._parse_address_block(entities.get(f"{prefix}_address_block"))
            address_fields.update(address_parts)

        # Special handling for bill_to addresses
        if prefix == "bill_to" and not address_fields.get("name"):
            # Extract from entities with bill_to prefix
            if entities.get("bill_to_name"):
                address_fields["name"] = entities.get("bill_to_name")
            if entities.get("bill_to_street"):
                address_fields["street"] = entities.get("bill_to_street")
            if entities.get("bill_to_city"):
                address_fields["city"] = entities.get("bill_to_city")
            if entities.get("bill_to_state"):
                address_fields["state"] = entities.get("bill_to_state")
            if entities.get("bill_to_zip"):
                address_fields["postal_code"] = entities.get("bill_to_zip")

        # Special handling for consignee names from text extraction
        if prefix == "consignee" and not address_fields.get("name") and entities.get("consignee_name"):
            # Parse consignee format like "30-1 CONSIGNEE: - Meridian Scheels"
            consignee_text = entities.get("consignee_name")
            if ' - ' in consignee_text:
                parts = consignee_text.split(' - ', 1)
                if len(parts) > 1:
                    address_fields["name"] = parts[1].strip()
            else:
                address_fields["name"] = consignee_text.strip()

        if any(address_fields.values()):
            return Address(**{k: v for k, v in address_fields.items() if v})

        return None

    def _parse_address_block(self, address_text: str) -> Dict[str, str]:
        """Parse a multi-line address block into components"""
        lines = address_text.strip().split('\n')
        result = {}

        if lines:
            result["name"] = lines[0].strip()

        if len(lines) > 1:
            result["street"] = lines[1].strip()

        if len(lines) > 2:
            # Try to parse city, state, zip from last line
            last_line = lines[-1].strip()
            # Pattern for "City, ST 12345" or "City ST 12345"
            match = re.match(r'^(.+?),?\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', last_line)
            if match:
                result["city"] = match.group(1).strip()
                result["state"] = match.group(2)
                result["postal_code"] = match.group(3)
            else:
                # If pattern doesn't match, use as is
                result["city"] = last_line

        return result

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        if not date_str:
            return None

        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%m/%d/%y",
            "%d/%m/%y"
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue

        return None

    def _parse_amount(self, amount_str: Optional[str]) -> Optional[Decimal]:
        if not amount_str:
            return None

        cleaned = re.sub(r'[^\d.,\-]', '', amount_str)
        cleaned = cleaned.replace(',', '')

        try:
            return Decimal(cleaned)
        except:
            return None

    def _parse_float(self, value_str: Optional[str]) -> Optional[float]:
        if not value_str:
            return None

        cleaned = re.sub(r'[^\d.,\-]', '', value_str)
        cleaned = cleaned.replace(',', '')

        try:
            return float(cleaned)
        except:
            return None

    def _parse_int(self, value_str: Optional[str]) -> Optional[int]:
        if not value_str:
            return None

        cleaned = re.sub(r'[^\d\-]', '', value_str)

        try:
            return int(cleaned)
        except:
            return None

    def _calculate_confidence_scores(self, document: documentai.Document) -> Dict[str, float]:
        scores = {}

        for entity in document.entities:
            entity_type = entity.type_.lower().replace(" ", "_")
            if entity.confidence:
                scores[entity_type] = entity.confidence

        if scores:
            scores["overall"] = sum(scores.values()) / len(scores)
        else:
            scores["overall"] = 0.0

        return scores


bol_document_ai_service = BOLDocumentAIService()
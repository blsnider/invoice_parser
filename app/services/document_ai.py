from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions
import logging
from typing import Dict, Any, List, Optional, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from datetime import datetime, date
import re

from app.core.config import settings
from app.models.invoice import InvoiceData, InvoiceLineItem, Address
from app.utils.exceptions import DocumentAIError

logger = logging.getLogger(__name__)


class DocumentAIService:
    def __init__(self):
        self.project_id = settings.PROJECT_ID
        self.location = settings.PROCESSOR_LOCATION
        self.processor_id = settings.PROCESSOR_ID
        self.client: Optional[documentai.DocumentProcessorServiceClient] = None
        self.executor = ThreadPoolExecutor(max_workers=3)
        
    def initialize(self):
        try:
            opts = ClientOptions(
                api_endpoint=f"{self.location}-documentai.googleapis.com"
            )
            self.client = documentai.DocumentProcessorServiceClient(client_options=opts)
            logger.info("Document AI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Document AI client: {e}")
            raise DocumentAIError(f"Document AI initialization failed: {str(e)}")
    
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
            logger.error(f"Document processing failed: {e}")
            raise DocumentAIError(f"Failed to process document: {str(e)}")
    
    def _process_document_sync(
        self, 
        content: bytes,
        mime_type: str
    ) -> documentai.Document:
        if not self.processor_id:
            processor_name = f"projects/{self.project_id}/locations/{self.location}/processors"
            
            processors = self.client.list_processors(parent=processor_name)
            invoice_processor = None
            
            for processor in processors:
                if "invoice" in processor.display_name.lower():
                    invoice_processor = processor
                    self.processor_id = processor.name.split("/")[-1]
                    logger.info(f"Found invoice processor: {self.processor_id}")
                    break
            
            if not invoice_processor:
                logger.info("No invoice processor found, creating one...")
                processor = self.client.create_processor(
                    parent=processor_name,
                    processor=documentai.Processor(
                        display_name="Invoice Parser",
                        type_="INVOICE_PROCESSOR"
                    )
                )
                self.processor_id = processor.name.split("/")[-1]
                logger.info(f"Created processor: {self.processor_id}")
        
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
    
    async def extract_invoice_data(
        self, 
        document: documentai.Document,
        invoice_id: str
    ) -> InvoiceData:
        try:
            entities = self._extract_entities(document)
            line_items = self._extract_line_items(document)
            confidence_scores = self._calculate_confidence_scores(document)
            
            invoice_data = InvoiceData(
                invoice_id=invoice_id,
                invoice_number=entities.get("invoice_id") or entities.get("invoice_number"),
                invoice_date=self._parse_date(entities.get("invoice_date")),
                due_date=self._parse_date(entities.get("due_date")),
                
                supplier_name=entities.get("supplier_name") or entities.get("vendor_name"),
                supplier_address=self._extract_address(entities, "supplier"),
                supplier_tax_id=entities.get("supplier_tax_id"),
                supplier_email=entities.get("supplier_email"),
                supplier_phone=entities.get("supplier_phone"),
                
                customer_name=entities.get("receiver_name") or entities.get("bill_to_name"),
                customer_address=self._extract_address(entities, "receiver"),
                customer_tax_id=entities.get("receiver_tax_id"),
                customer_email=entities.get("receiver_email"),
                customer_phone=entities.get("receiver_phone"),
                
                currency=entities.get("currency_code", "USD"),
                subtotal=self._parse_amount(entities.get("net_amount")),
                tax_amount=self._parse_amount(entities.get("total_tax_amount")),
                total_amount=self._parse_amount(entities.get("total_amount")) or Decimal("0"),
                amount_due=self._parse_amount(entities.get("amount_due")),
                
                line_items=line_items,
                
                payment_terms=entities.get("payment_terms"),
                payment_method=entities.get("payment_method"),
                
                confidence_scores=confidence_scores,
                raw_text=document.text,
                metadata={
                    "page_count": len(document.pages),
                    "processing_time": datetime.utcnow().isoformat()
                }
            )
            
            return invoice_data
            
        except Exception as e:
            logger.error(f"Failed to extract invoice data: {e}")
            raise DocumentAIError(f"Data extraction failed: {str(e)}")
    
    def _extract_entities(self, document: documentai.Document) -> Dict[str, Any]:
        entities = {}
        
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
        
        return entities
    
    def _extract_line_items(self, document: documentai.Document) -> List[InvoiceLineItem]:
        line_items = []
        
        for entity in document.entities:
            if entity.type_.lower() == "line_item":
                item_data = {}
                
                for prop in entity.properties:
                    prop_type = prop.type_.lower().replace(" ", "_")
                    value = prop.mention_text or (prop.text_anchor.content if prop.text_anchor else None)
                    
                    if prop_type in ["amount", "unit_price", "tax_amount"]:
                        item_data[prop_type] = self._parse_amount(value)
                    elif prop_type == "quantity":
                        item_data[prop_type] = self._parse_quantity(value)
                    elif prop_type == "tax_rate":
                        item_data[prop_type] = self._parse_percentage(value)
                    else:
                        item_data[prop_type] = value
                
                if item_data.get("description") or item_data.get("item_description"):
                    line_item = InvoiceLineItem(
                        description=item_data.get("description") or item_data.get("item_description", ""),
                        quantity=item_data.get("quantity"),
                        unit_price=item_data.get("unit_price"),
                        amount=item_data.get("amount", Decimal("0")),
                        tax_rate=item_data.get("tax_rate"),
                        tax_amount=item_data.get("tax_amount")
                    )
                    line_items.append(line_item)
        
        if not line_items and document.pages:
            for page in document.pages:
                if page.tables:
                    for table in page.tables:
                        table_items = self._extract_items_from_table(table)
                        line_items.extend(table_items)
        
        return line_items
    
    def _extract_items_from_table(self, table) -> List[InvoiceLineItem]:
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
                item = self._parse_table_row_to_line_item(row_data)
                if item:
                    items.append(item)
        
        return items
    
    def _parse_table_row_to_line_item(self, row_data: Dict[str, str]) -> Optional[InvoiceLineItem]:
        description = (
            row_data.get("description") or 
            row_data.get("item") or 
            row_data.get("product") or 
            row_data.get("service")
        )
        
        if not description:
            return None
        
        return InvoiceLineItem(
            description=description,
            quantity=self._parse_quantity(row_data.get("quantity") or row_data.get("qty")),
            unit_price=self._parse_amount(row_data.get("unit price") or row_data.get("price")),
            amount=self._parse_amount(row_data.get("amount") or row_data.get("total")) or Decimal("0"),
            tax_rate=self._parse_percentage(row_data.get("tax rate") or row_data.get("tax %")),
            tax_amount=self._parse_amount(row_data.get("tax") or row_data.get("tax amount"))
        )
    
    def _extract_address(self, entities: Dict[str, Any], prefix: str) -> Optional[Address]:
        address_fields = {
            "street": entities.get(f"{prefix}_address") or entities.get(f"{prefix}_address_line_1"),
            "city": entities.get(f"{prefix}_city"),
            "state": entities.get(f"{prefix}_state") or entities.get(f"{prefix}_province"),
            "postal_code": entities.get(f"{prefix}_postal_code") or entities.get(f"{prefix}_zip"),
            "country": entities.get(f"{prefix}_country")
        }
        
        if any(address_fields.values()):
            return Address(**{k: v for k, v in address_fields.items() if v})
        
        return None
    
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
            "%m-%d-%Y"
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
    
    def _parse_quantity(self, qty_str: Optional[str]) -> Optional[float]:
        if not qty_str:
            return None
        
        cleaned = re.sub(r'[^\d.,\-]', '', qty_str)
        cleaned = cleaned.replace(',', '')
        
        try:
            return float(cleaned)
        except:
            return None
    
    def _parse_percentage(self, pct_str: Optional[str]) -> Optional[float]:
        if not pct_str:
            return None
        
        cleaned = re.sub(r'[^\d.,\-]', '', pct_str)
        cleaned = cleaned.replace(',', '')
        
        try:
            value = float(cleaned)
            return value if value <= 1 else value / 100
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


document_ai_service = DocumentAIService()
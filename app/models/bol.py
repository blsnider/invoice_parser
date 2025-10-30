from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal


class ShipmentItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    weight: Optional[float] = None
    weight_unit: Optional[str] = None
    dimensions: Optional[str] = None
    packaging_type: Optional[str] = None
    hazmat_class: Optional[str] = None
    nmfc_code: Optional[str] = None
    freight_class: Optional[str] = None


class Address(BaseModel):
    name: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class BOLData(BaseModel):
    bol_id: str = Field(..., description="Unique BOL identifier")
    bol_number: Optional[str] = Field(None, description="BOL number from document")
    pro_number: Optional[str] = Field(None, description="PRO/tracking number")
    scac_code: Optional[str] = Field(None, description="Carrier SCAC code")

    ship_date: Optional[date] = Field(None, description="Shipment date")
    delivery_date: Optional[date] = Field(None, description="Expected delivery date")

    shipper: Optional[Address] = None
    consignee: Optional[Address] = None
    bill_to: Optional[Address] = None

    carrier_name: Optional[str] = Field(None, description="Carrier company name")
    driver_name: Optional[str] = None
    truck_number: Optional[str] = None
    trailer_number: Optional[str] = None
    seal_number: Optional[str] = None

    origin_terminal: Optional[str] = None
    destination_terminal: Optional[str] = None

    freight_charge_terms: Optional[str] = Field(None, description="Prepaid, Collect, Third Party")
    payment_terms: Optional[str] = None

    total_weight: Optional[float] = None
    weight_unit: Optional[str] = Field(default="LBS")
    total_pieces: Optional[int] = None
    total_pallets: Optional[int] = None

    shipment_items: List[ShipmentItem] = Field(default_factory=list)

    special_instructions: Optional[str] = None
    delivery_instructions: Optional[str] = None

    freight_charges: Optional[Decimal] = None
    accessorial_charges: Optional[Decimal] = None
    total_charges: Optional[Decimal] = None

    shipment_type: Optional[str] = Field(None, description="LTL, FTL, Parcel, etc.")
    service_type: Optional[str] = Field(None, description="Standard, Expedited, etc.")

    confidence_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for extracted fields"
    )

    raw_text: Optional[str] = Field(None, description="Full extracted text from document")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            Decimal: str,
            date: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat() if v else None
        }


class BOLParseRequest(BaseModel):
    file_name: str
    content_type: str = "application/pdf"
    extract_tables: bool = True
    extract_items: bool = True
    language_hints: List[str] = Field(default_factory=lambda: ["en"])


class BatchBOLParseRequest(BaseModel):
    files: List[BOLParseRequest]
    parallel_processing: bool = True
    max_workers: int = Field(default=5, ge=1, le=10)
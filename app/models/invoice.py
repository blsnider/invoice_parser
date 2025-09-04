from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal


class InvoiceLineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[Decimal] = None
    amount: Decimal
    tax_rate: Optional[float] = None
    tax_amount: Optional[Decimal] = None


class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class InvoiceData(BaseModel):
    invoice_id: str = Field(..., description="Unique invoice identifier")
    invoice_number: Optional[str] = Field(None, description="Invoice number from document")
    invoice_date: Optional[date] = Field(None, description="Date when invoice was issued")
    due_date: Optional[date] = Field(None, description="Payment due date")
    
    supplier_name: Optional[str] = Field(None, description="Supplier/vendor name")
    supplier_address: Optional[Address] = None
    supplier_tax_id: Optional[str] = None
    supplier_email: Optional[str] = None
    supplier_phone: Optional[str] = None
    
    customer_name: Optional[str] = Field(None, description="Customer/buyer name")
    customer_address: Optional[Address] = None
    customer_tax_id: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    
    currency: str = Field(default="USD", description="Invoice currency code")
    subtotal: Optional[Decimal] = Field(None, description="Total before tax")
    tax_amount: Optional[Decimal] = Field(None, description="Total tax amount")
    total_amount: Decimal = Field(..., description="Total invoice amount")
    amount_due: Optional[Decimal] = Field(None, description="Outstanding amount")
    
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    
    payment_terms: Optional[str] = None
    payment_method: Optional[str] = None
    bank_details: Optional[Dict[str, str]] = None
    
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


class InvoiceParseRequest(BaseModel):
    file_name: str
    content_type: str = "application/pdf"
    extract_tables: bool = True
    extract_line_items: bool = True
    language_hints: List[str] = Field(default_factory=lambda: ["en"])


class BatchParseRequest(BaseModel):
    files: List[InvoiceParseRequest]
    parallel_processing: bool = True
    max_workers: int = Field(default=5, ge=1, le=10)
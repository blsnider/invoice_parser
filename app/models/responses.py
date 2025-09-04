from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.invoice import InvoiceData


class ParseResponse(BaseModel):
    success: bool
    invoice_id: str
    message: str = "Invoice parsed successfully"
    data: Optional[InvoiceData] = None
    preview_url: Optional[str] = None
    storage_path: Optional[str] = None
    processing_time: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BatchParseResponse(BaseModel):
    success: bool
    total_files: int
    processed: int
    failed: int
    results: List[ParseResponse]
    processing_time: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    error: bool = True
    message: str
    code: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    dependencies: Optional[Dict[str, str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PreviewResponse(BaseModel):
    invoice_id: str
    signed_url: str
    expires_in: int = Field(default=900, description="URL expiration in seconds")
    content_type: str = "application/pdf"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
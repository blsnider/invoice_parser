from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from app.models.invoice import InvoiceData
from app.models.bol import BOLData


class ParseResponse(BaseModel):
    success: bool
    document_id: str = Field(alias="invoice_id")  # Backward compatibility
    message: str = "Document parsed successfully"
    data: Optional[Union[InvoiceData, BOLData]] = None
    preview_url: Optional[str] = None
    storage_path: Optional[str] = None
    processing_time: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        allow_population_by_field_name = True


class BatchParseResponse(BaseModel):
    success: bool
    total_files: int
    successful: int = Field(alias="processed")  # Backward compatibility
    failed: int
    results: List[ParseResponse]
    processing_time: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True


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
    document_id: str = Field(alias="invoice_id")  # Backward compatibility
    signed_url: str
    expires_in: int = Field(default=900, description="URL expiration in seconds")
    content_type: str = "application/pdf"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True
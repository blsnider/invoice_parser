from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.bol import BOLData


class BOLParseResponse(BaseModel):
    success: bool
    bol_id: str
    message: str = "BOL parsed successfully"
    data: Optional[BOLData] = None
    preview_url: Optional[str] = None
    storage_path: Optional[str] = None
    processing_time: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MultiBOLParseResponse(BaseModel):
    success: bool
    document_id: str
    message: str = "Multiple BOLs parsed successfully"
    bol_count: int
    bols: List[BOLData]
    preview_url: Optional[str] = None
    processing_time: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BOLBatchParseResponse(BaseModel):
    success: bool
    total_files: int
    successful: int
    failed: int
    results: List[BOLParseResponse]
    processing_time: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BOLPreviewResponse(BaseModel):
    bol_id: str
    signed_url: str
    expires_in: int = Field(default=900, description="URL expiration in seconds")
    content_type: str = "application/pdf"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
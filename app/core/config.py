from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from functools import lru_cache
import os


class Settings(BaseSettings):
    PROJECT_ID: str = Field(..., description="Google Cloud Project ID")
    BUCKET_NAME: str = Field(..., description="GCS bucket for storage")
    
    PROCESSOR_ID: Optional[str] = Field(None, description="Document AI processor ID")
    PROCESSOR_LOCATION: str = Field(default="us", description="Document AI processor location")
    PROCESSOR_VERSION: Optional[str] = Field(None, description="Document AI processor version")
    
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = Field(
        default=None,
        description="Path to service account JSON file"
    )
    
    SERVICE_ACCOUNT_EMAIL: Optional[str] = Field(
        default=None,
        description="Service account email for signed URL generation"
    )
    
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allowed origins"
    )
    
    MAX_FILE_SIZE: int = Field(default=10_485_760, description="Max file size in bytes (10MB)")
    ALLOWED_EXTENSIONS: List[str] = Field(
        default_factory=lambda: [".pdf"],
        description="Allowed file extensions"
    )
    
    SIGNED_URL_EXPIRATION: int = Field(default=900, description="Signed URL expiration in seconds")
    
    BATCH_MAX_WORKERS: int = Field(default=5, description="Max workers for batch processing")
    REQUEST_TIMEOUT: int = Field(default=300, description="Request timeout in seconds")
    
    REDIS_URL: Optional[str] = Field(None, description="Redis URL for caching")
    CACHE_TTL: int = Field(default=3600, description="Cache TTL in seconds")
    
    ENVIRONMENT: str = Field(default="development", description="Environment name")
    DEBUG: bool = Field(default=False, description="Debug mode")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
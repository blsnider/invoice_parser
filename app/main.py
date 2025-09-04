from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import google.cloud.storage as _gcs
import google.auth

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import parsing

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting Invoice Parsing Service")
    
    # Check for credentials and project ID here
    credentials, project_id = google.auth.default()
    logger.info(f"[adc] credentials class={type(credentials)} project={project_id}")
    
    logger.info(f"[versions] google-cloud-storage={_gcs.__version__}, google-auth={google.auth.__version__}")
    logger.info(f"Project ID: {settings.PROJECT_ID}")
    logger.info(f"Bucket Name: {settings.BUCKET_NAME}")
    logger.info(f"Service Account Email: {settings.SERVICE_ACCOUNT_EMAIL}")
    logger.info(f"Processor ID: {settings.PROCESSOR_ID}")
    
    yield
    
    logger.info("Shutting down Invoice Parsing Service")

# Rest of the code remains the same
app = FastAPI(
    title="Invoice Parsing Service",
    description="FastAPI service for parsing PDF invoices using Google Cloud Document AI",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parsing.router, prefix="/api/v1", tags=["parsing"])


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "invoice-parser",
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    return {
        "service": "Invoice Parsing Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "parse_invoice": "/api/v1/parse-invoice",
            "parse_batch": "/api/v1/parse-batch",
            "invoice_preview": "/api/v1/invoice/{invoice_id}/preview",
            "invoice_data": "/api/v1/invoice/{invoice_id}/data",
            "list_invoices": "/api/v1/invoices"
        }
    }
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import google.cloud.storage as _gcs
import google.auth

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import parsing, bol_parsing

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting Document Parsing Service")

    # Check for credentials and project ID here
    credentials, project_id = google.auth.default()
    logger.info(f"[adc] credentials class={type(credentials)} project={project_id}")

    logger.info(f"[versions] google-cloud-storage={_gcs.__version__}, google-auth={google.auth.__version__}")
    logger.info(f"Project ID: {settings.PROJECT_ID}")
    logger.info(f"Bucket Name: {settings.BUCKET_NAME}")
    logger.info(f"Service Account Email: {settings.SERVICE_ACCOUNT_EMAIL}")
    logger.info(f"Invoice Processor ID: {settings.INVOICE_PROCESSOR_ID or settings.PROCESSOR_ID}")
    logger.info(f"BOL Processor ID: {settings.BOL_PROCESSOR_ID}")

    yield

    logger.info("Shutting down Document Parsing Service")

# Rest of the code remains the same
app = FastAPI(
    title="Document Parsing Service",
    description="FastAPI service for parsing PDF invoices and BOLs using Google Cloud Document AI",
    version="1.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parsing.router, prefix="/api/v1", tags=["invoice-parsing"])
app.include_router(bol_parsing.router, prefix="/api/v1", tags=["bol-parsing"])


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "document-parser",
        "version": "1.1.0",
        "processors": {
            "invoice": settings.INVOICE_PROCESSOR_ID or settings.PROCESSOR_ID,
            "bol": settings.BOL_PROCESSOR_ID
        }
    }


@app.get("/")
async def root():
    return {
        "service": "Document Parsing Service",
        "version": "1.1.0",
        "endpoints": {
            "health": "/health",
            "invoice": {
                "parse_invoice": "/api/v1/parse-invoice",
                "parse_batch": "/api/v1/parse-batch",
                "invoice_preview": "/api/v1/invoice/{invoice_id}/preview",
                "invoice_data": "/api/v1/invoice/{invoice_id}/data",
                "list_invoices": "/api/v1/invoices"
            },
            "bol": {
                "parse_bol": "/api/v1/parse-bol",
                "parse_bol_multi": "/api/v1/parse-bol-multi",
                "parse_batch_bol": "/api/v1/parse-batch-bol",
                "bol_preview": "/api/v1/bol/{bol_id}/preview",
                "bol_data": "/api/v1/bol/{bol_id}/data",
                "list_bols": "/api/v1/bols"
            }
        }
    }
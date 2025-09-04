from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging
import json

from app.models.responses import ParseResponse, BatchParseResponse, ErrorResponse, PreviewResponse
from app.models.invoice import InvoiceData, InvoiceParseRequest
from app.services.parser import invoice_parser
from app.utils.validation import validate_file, sanitize_filename
from app.utils.exceptions import InvoiceParserException
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/parse-invoice", response_model=ParseResponse)
async def parse_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    extract_tables: bool = Form(default=True),
    extract_line_items: bool = Form(default=True),
    language_hints: Optional[str] = Form(default="en")
):
    try:
        file_content = await file.read()
        
        validate_file(file_content, file.filename)
        
        sanitized_filename = sanitize_filename(file.filename)
        
        metadata = {
            "original_filename": file.filename,
            "content_type": file.content_type,
            "extract_tables": extract_tables,
            "extract_line_items": extract_line_items,
            "language_hints": language_hints
        }
        
        result = await invoice_parser.parse_invoice(
            file_content,
            sanitized_filename,
            file.content_type or "application/pdf",
            metadata
        )
        
        if result.success and result.data:
            try:
                await invoice_parser.validate_invoice_data(result.data)
            except Exception as e:
                logger.warning(f"Validation warning: {e}")
        
        return result
        
    except InvoiceParserException as e:
        logger.error(f"Invoice parsing error: {e.message}")
        raise HTTPException(status_code=400, detail={
            "error": True,
            "message": e.message,
            "code": e.code
        })
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Internal server error",
            "code": "INTERNAL_ERROR"
        })


@router.post("/parse-batch", response_model=BatchParseResponse)
async def parse_batch(
    files: List[UploadFile] = File(...),
    max_workers: int = Form(default=5, ge=1, le=10),
    extract_tables: bool = Form(default=True),
    extract_line_items: bool = Form(default=True)
):
    try:
        if len(files) > 50:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": True,
                    "message": "Maximum 50 files allowed per batch",
                    "code": "BATCH_SIZE_EXCEEDED"
                }
            )
        
        file_data_list = []
        for file in files:
            file_content = await file.read()
            
            try:
                validate_file(file_content, file.filename)
            except Exception as e:
                logger.warning(f"Skipping invalid file {file.filename}: {e}")
                continue
            
            file_data_list.append({
                "content": file_content,
                "name": sanitize_filename(file.filename),
                "content_type": file.content_type or "application/pdf",
                "metadata": {
                    "original_filename": file.filename,
                    "extract_tables": extract_tables,
                    "extract_line_items": extract_line_items
                }
            })
        
        if not file_data_list:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": True,
                    "message": "No valid files to process",
                    "code": "NO_VALID_FILES"
                }
            )
        
        result = await invoice_parser.parse_batch(
            file_data_list,
            max_workers=min(max_workers, settings.BATCH_MAX_WORKERS)
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch parsing error: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Batch processing failed",
            "code": "BATCH_ERROR"
        })


@router.get("/invoice/{invoice_id}/preview", response_model=PreviewResponse)
async def get_invoice_preview(
    invoice_id: str,
    expires_in: int = 900
):
    try:
        invoices = await invoice_parser.storage.list_invoices(f"invoices/{invoice_id}/")
        
        if not invoices:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": True,
                    "message": f"Invoice {invoice_id} not found",
                    "code": "INVOICE_NOT_FOUND"
                }
            )
        
        file_name = invoices[0].split("/")[-1]
        
        signed_url = await invoice_parser.get_invoice_preview(
            invoice_id,
            file_name
        )
        
        return PreviewResponse(
            invoice_id=invoice_id,
            signed_url=signed_url,
            expires_in=expires_in,
            content_type="application/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preview: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to generate preview URL",
            "code": "PREVIEW_ERROR"
        })


@router.get("/invoice/{invoice_id}/data", response_model=InvoiceData)
async def get_invoice_data(invoice_id: str):
    try:
        invoice_data = await invoice_parser.get_invoice_data(invoice_id)
        
        return invoice_data
        
    except InvoiceParserException as e:
        if "not found" in e.message.lower():
            raise HTTPException(
                status_code=404,
                detail={
                    "error": True,
                    "message": f"Invoice data for {invoice_id} not found",
                    "code": "DATA_NOT_FOUND"
                }
            )
        raise HTTPException(status_code=400, detail={
            "error": True,
            "message": e.message,
            "code": e.code
        })
    except Exception as e:
        logger.error(f"Failed to get invoice data: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to retrieve invoice data",
            "code": "DATA_ERROR"
        })


@router.delete("/invoice/{invoice_id}")
async def delete_invoice(invoice_id: str):
    try:
        await invoice_parser.storage.delete_invoice(invoice_id)
        
        return {
            "success": True,
            "message": f"Invoice {invoice_id} deleted successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to delete invoice: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to delete invoice",
            "code": "DELETE_ERROR"
        })


@router.get("/invoices")
async def list_invoices(
    limit: int = 100,
    offset: int = 0
):
    try:
        all_invoices = await invoice_parser.storage.list_invoices("parsed/")
        
        invoice_ids = list(set(
            path.split("/")[1] 
            for path in all_invoices 
            if path.endswith("data.json")
        ))
        
        paginated = invoice_ids[offset:offset + limit]
        
        invoices = []
        for invoice_id in paginated:
            try:
                data = await invoice_parser.get_invoice_data(invoice_id)
                invoices.append({
                    "invoice_id": invoice_id,
                    "invoice_number": data.invoice_number,
                    "supplier_name": data.supplier_name,
                    "total_amount": str(data.total_amount),
                    "currency": data.currency,
                    "invoice_date": data.invoice_date.isoformat() if data.invoice_date else None
                })
            except Exception as e:
                logger.warning(f"Failed to load invoice {invoice_id}: {e}")
        
        return {
            "total": len(invoice_ids),
            "limit": limit,
            "offset": offset,
            "invoices": invoices
        }
        
    except Exception as e:
        logger.error(f"Failed to list invoices: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to list invoices",
            "code": "LIST_ERROR"
        })


@router.post("/invoice/{invoice_id}/reprocess")
async def reprocess_invoice(invoice_id: str):
    try:
        invoices = await invoice_parser.storage.list_invoices(f"invoices/{invoice_id}/")
        
        if not invoices:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": True,
                    "message": f"Invoice {invoice_id} not found",
                    "code": "INVOICE_NOT_FOUND"
                }
            )
        
        file_name = invoices[0].split("/")[-1]
        file_content = await invoice_parser.storage.download_file(invoice_id, file_name)
        
        document = await invoice_parser.document_ai.process_document(
            file_content,
            "application/pdf"
        )
        
        invoice_data = await invoice_parser.document_ai.extract_invoice_data(
            document,
            invoice_id
        )
        
        await invoice_parser.storage.save_parsed_data(
            invoice_id,
            invoice_data.dict()
        )
        
        return ParseResponse(
            success=True,
            invoice_id=invoice_id,
            message="Invoice reprocessed successfully",
            data=invoice_data,
            preview_url=await invoice_parser.get_invoice_preview(invoice_id, file_name),
            storage_path=f"parsed/{invoice_id}/data.json",
            processing_time=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reprocess invoice: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to reprocess invoice",
            "code": "REPROCESS_ERROR"
        })
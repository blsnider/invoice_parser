from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging
import json

from app.models.responses import ErrorResponse
from app.models.bol_responses import BOLParseResponse, BOLBatchParseResponse, BOLPreviewResponse, MultiBOLParseResponse
from app.models.bol import BOLData, BOLParseRequest
from app.services.bol_parser import bol_parser
from app.utils.validation import validate_file, sanitize_filename
from app.utils.exceptions import DocumentParserException
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/parse-bol", response_model=BOLParseResponse)
async def parse_bol(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    extract_tables: bool = Form(default=True),
    extract_items: bool = Form(default=True),
    language_hints: Optional[str] = Form(default="en")
):
    """Parse single BOL (backward compatible - returns first BOL if multiple found)"""
    try:
        file_content = await file.read()

        validate_file(file_content, file.filename)

        sanitized_filename = sanitize_filename(file.filename)

        metadata = {
            "original_filename": file.filename,
            "content_type": file.content_type,
            "extract_tables": extract_tables,
            "extract_items": extract_items,
            "language_hints": language_hints
        }

        result = await bol_parser.parse_bol(
            file_content,
            sanitized_filename,
            file.content_type or "application/pdf",
            metadata
        )

        if result.success and result.data:
            try:
                await bol_parser.validate_bol_data(result.data)
            except Exception as e:
                logger.warning(f"Validation warning: {e}")

        return result

    except DocumentParserException as e:
        logger.error(f"BOL parsing error: {e.message}")
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


@router.post("/parse-bol-multi", response_model=MultiBOLParseResponse)
async def parse_bol(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    extract_tables: bool = Form(default=True),
    extract_items: bool = Form(default=True),
    language_hints: Optional[str] = Form(default="en")
):
    """Parse multiple BOLs from a single PDF document"""
    try:
        file_content = await file.read()

        validate_file(file_content, file.filename)

        sanitized_filename = sanitize_filename(file.filename)

        metadata = {
            "original_filename": file.filename,
            "content_type": file.content_type,
            "extract_tables": extract_tables,
            "extract_items": extract_items,
            "language_hints": language_hints
        }

        result = await bol_parser.parse_bol_multi(
            file_content,
            sanitized_filename,
            file.content_type or "application/pdf",
            metadata
        )

        if result.success and result.bols:
            for bol in result.bols:
                try:
                    await bol_parser.validate_bol_data(bol)
                except Exception as e:
                    logger.warning(f"Validation warning for BOL {bol.bol_id}: {e}")

        return result

    except DocumentParserException as e:
        logger.error(f"BOL parsing error: {e.message}")
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


@router.post("/parse-batch-bol", response_model=BOLBatchParseResponse)
async def parse_batch_bol(
    files: List[UploadFile] = File(...),
    max_workers: int = Form(default=5, ge=1, le=10),
    extract_tables: bool = Form(default=True),
    extract_items: bool = Form(default=True)
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
                    "extract_items": extract_items
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

        result = await bol_parser.parse_batch(
            file_data_list,
            max_workers=min(max_workers, settings.BATCH_MAX_WORKERS)
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch BOL parsing error: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Batch processing failed",
            "code": "BATCH_ERROR"
        })


@router.get("/bol/{bol_id}/preview", response_model=BOLPreviewResponse)
async def get_bol_preview(
    bol_id: str,
    expires_in: int = 900
):
    try:
        bols = await bol_parser.storage.list_bols(f"bols/{bol_id}/")

        if not bols:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": True,
                    "message": f"BOL {bol_id} not found",
                    "code": "BOL_NOT_FOUND"
                }
            )

        file_name = bols[0].split("/")[-1]

        signed_url = await bol_parser.get_bol_preview(
            bol_id,
            file_name
        )

        return BOLPreviewResponse(
            bol_id=bol_id,
            signed_url=signed_url,
            expires_in=expires_in,
            content_type="application/pdf"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get BOL preview: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to generate preview URL",
            "code": "PREVIEW_ERROR"
        })


@router.get("/bol/{bol_id}/data", response_model=BOLData)
async def get_bol_data(bol_id: str):
    try:
        bol_data = await bol_parser.get_bol_data(bol_id)

        return bol_data

    except DocumentParserException as e:
        if "not found" in e.message.lower():
            raise HTTPException(
                status_code=404,
                detail={
                    "error": True,
                    "message": f"BOL data for {bol_id} not found",
                    "code": "DATA_NOT_FOUND"
                }
            )
        raise HTTPException(status_code=400, detail={
            "error": True,
            "message": e.message,
            "code": e.code
        })
    except Exception as e:
        logger.error(f"Failed to get BOL data: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to retrieve BOL data",
            "code": "DATA_ERROR"
        })


@router.delete("/bol/{bol_id}")
async def delete_bol(bol_id: str):
    try:
        await bol_parser.storage.delete_bol(bol_id)

        return {
            "success": True,
            "message": f"BOL {bol_id} deleted successfully"
        }

    except Exception as e:
        logger.error(f"Failed to delete BOL: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to delete BOL",
            "code": "DELETE_ERROR"
        })


@router.get("/bols")
async def list_bols(
    limit: int = 100,
    offset: int = 0
):
    try:
        all_bols = await bol_parser.storage.list_bols("parsed_bol/")

        bol_ids = list(set(
            path.split("/")[1]
            for path in all_bols
            if path.endswith("data.json")
        ))

        paginated = bol_ids[offset:offset + limit]

        bols = []
        for bol_id in paginated:
            try:
                data = await bol_parser.get_bol_data(bol_id)
                bols.append({
                    "bol_id": bol_id,
                    "bol_number": data.bol_number,
                    "shipper_name": data.shipper.name if data.shipper else None,
                    "consignee_name": data.consignee.name if data.consignee else None,
                    "carrier_name": data.carrier_name,
                    "ship_date": data.ship_date.isoformat() if data.ship_date else None
                })
            except Exception as e:
                logger.warning(f"Failed to load BOL {bol_id}: {e}")

        return {
            "total": len(bol_ids),
            "limit": limit,
            "offset": offset,
            "bols": bols
        }

    except Exception as e:
        logger.error(f"Failed to list BOLs: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to list BOLs",
            "code": "LIST_ERROR"
        })


@router.post("/bol/{bol_id}/reprocess")
async def reprocess_bol(bol_id: str):
    try:
        bols = await bol_parser.storage.list_bols(f"bols/{bol_id}/")

        if not bols:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": True,
                    "message": f"BOL {bol_id} not found",
                    "code": "BOL_NOT_FOUND"
                }
            )

        file_name = bols[0].split("/")[-1]
        file_content = await bol_parser.storage.download_file(bol_id, file_name, "bols")

        document = await bol_parser.document_ai.process_document(
            file_content,
            "application/pdf"
        )

        bol_data = await bol_parser.document_ai.extract_bol_data(
            document,
            bol_id
        )

        await bol_parser.storage.save_parsed_bol_data(
            bol_id,
            bol_data.dict()
        )

        return BOLParseResponse(
            success=True,
            bol_id=bol_id,
            message="BOL reprocessed successfully",
            data=bol_data,
            preview_url=await bol_parser.get_bol_preview(bol_id, file_name),
            storage_path=f"parsed_bol/{bol_id}/data.json",
            processing_time=0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reprocess BOL: {e}")
        raise HTTPException(status_code=500, detail={
            "error": True,
            "message": "Failed to reprocess BOL",
            "code": "REPROCESS_ERROR"
        })
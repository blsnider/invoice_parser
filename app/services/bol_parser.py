import logging
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.services.bol_document_ai import bol_document_ai_service
from app.services.storage import storage_service
from app.models.bol import BOLData
from app.models.bol_responses import BOLParseResponse, BOLBatchParseResponse, MultiBOLParseResponse
from app.utils.exceptions import DocumentParserException

logger = logging.getLogger(__name__)


class BOLParser:
    def __init__(self):
        self.document_ai = bol_document_ai_service
        self.storage = storage_service
        self.executor = ThreadPoolExecutor(max_workers=settings.BATCH_MAX_WORKERS)

    async def parse_bol(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str,
        metadata: Dict[str, Any]
    ) -> BOLParseResponse:
        """Parse single BOL - backward compatible method"""
        result = await self.parse_bol_multi(
            file_content,
            file_name,
            content_type,
            metadata
        )

        # If multiple BOLs detected, return first one for backward compatibility
        if isinstance(result, MultiBOLParseResponse) and result.bols:
            first_bol = result.bols[0]
            return BOLParseResponse(
                success=result.success,
                bol_id=first_bol.bol_id,
                message="First BOL extracted from multi-BOL document" if result.bol_count > 1 else "BOL parsed successfully",
                data=first_bol,
                preview_url=result.preview_url,
                storage_path=f"parsed_bol/{first_bol.bol_id}/data.json",
                processing_time=result.processing_time
            )

        # Single BOL response
        return result

    async def parse_bol_multi(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str,
        metadata: Dict[str, Any]
    ) -> MultiBOLParseResponse:
        """Parse potentially multiple BOLs from a single PDF"""
        start_time = datetime.utcnow()
        document_id = str(uuid.uuid4())

        try:
            # Initialize storage if needed
            if not self.storage.client:
                self.storage.initialize()

            # Save original PDF to storage
            await self.storage.upload_file(
                file_content,
                document_id,
                file_name,
                folder="bols"
            )
            logger.info(f"Uploaded BOL file to storage: bols/{document_id}/{file_name}")

            # Process with Document AI
            document = await self.document_ai.process_document(
                file_content,
                content_type
            )
            logger.info(f"Document AI processing complete for document {document_id}")

            # Extract multiple BOLs
            bol_data_list = await self.document_ai.extract_multiple_bols(
                document,
                document_id
            )

            # Add metadata to each BOL
            for bol_data in bol_data_list:
                bol_data.metadata.update(metadata)
                # Save each BOL's data
                await self.save_bol_data(bol_data.bol_id, bol_data)

            # Generate preview URL for the original document
            preview_url = await self.get_bol_preview(document_id, file_name)

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            return MultiBOLParseResponse(
                success=True,
                document_id=document_id,
                message=f"{len(bol_data_list)} BOL(s) parsed successfully",
                bol_count=len(bol_data_list),
                bols=bol_data_list,
                preview_url=preview_url,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"BOL parsing failed for {document_id}: {e}")
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            # Try to clean up on failure
            try:
                await self.storage.delete_bol(document_id)
            except:
                pass

            return MultiBOLParseResponse(
                success=False,
                document_id=document_id,
                message=f"BOL parsing failed: {str(e)}",
                bol_count=0,
                bols=[],
                preview_url=None,
                processing_time=processing_time
            )

    async def parse_batch(
        self,
        files: List[Dict[str, Any]],
        max_workers: int = 5
    ) -> BOLBatchParseResponse:
        start_time = datetime.utcnow()

        # Create tasks for parallel processing
        tasks = []
        for file_data in files:
            task = self.parse_bol(
                file_data["content"],
                file_data["name"],
                file_data["content_type"],
                file_data["metadata"]
            )
            tasks.append(task)

        # Execute tasks with limited concurrency
        results = []
        for i in range(0, len(tasks), max_workers):
            batch_tasks = tasks[i:i + max_workers]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing error: {result}")
                    results.append(ParseResponse(
                        success=False,
                        document_id="",
                        message=str(result),
                        data=None,
                        preview_url=None,
                        storage_path=None,
                        processing_time=0
                    ))
                else:
                    results.append(result)

        # Calculate summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        return BOLBatchParseResponse(
            success=successful > 0,
            total_files=len(files),
            successful=successful,
            failed=failed,
            results=results,
            processing_time=processing_time
        )

    async def save_bol_data(self, bol_id: str, bol_data: BOLData):
        """Save parsed BOL data to storage"""
        try:
            data_dict = bol_data.dict()
            await self.storage.save_parsed_data(
                bol_id,
                data_dict,
                folder="parsed_bol"
            )
            logger.info(f"Saved parsed BOL data for {bol_id}")
        except Exception as e:
            logger.error(f"Failed to save BOL data: {e}")
            raise DocumentParserException(
                message=f"Failed to save BOL data: {str(e)}",
                code="STORAGE_ERROR"
            )

    async def get_bol_data(self, bol_id: str) -> BOLData:
        """Retrieve parsed BOL data from storage"""
        try:
            data_dict = await self.storage.get_parsed_data(bol_id, folder="parsed_bol")
            return BOLData(**data_dict)
        except FileNotFoundError:
            raise DocumentParserException(
                message=f"BOL data for {bol_id} not found",
                code="DATA_NOT_FOUND"
            )
        except Exception as e:
            logger.error(f"Failed to retrieve BOL data: {e}")
            raise DocumentParserException(
                message=f"Failed to retrieve BOL data: {str(e)}",
                code="RETRIEVAL_ERROR"
            )

    async def get_bol_preview(self, bol_id: str, file_name: str) -> str:
        """Generate signed URL for BOL preview"""
        try:
            return await self.storage.generate_signed_url(
                bol_id,
                file_name,
                folder="bols"
            )
        except Exception as e:
            logger.error(f"Failed to generate preview URL: {e}")
            raise DocumentParserException(
                message=f"Failed to generate preview URL: {str(e)}",
                code="PREVIEW_ERROR"
            )

    async def validate_bol_data(self, bol_data: BOLData):
        """Validate BOL data for completeness and accuracy"""
        warnings = []

        # Check required fields
        if not bol_data.bol_number:
            warnings.append("BOL number not found")

        if not bol_data.shipper:
            warnings.append("Shipper information missing")

        if not bol_data.consignee:
            warnings.append("Consignee information missing")

        if not bol_data.shipment_items:
            warnings.append("No shipment items found")

        # Check confidence scores
        if bol_data.confidence_scores.get("overall", 0) < 0.6:
            warnings.append("Low overall confidence score")

        if warnings:
            logger.warning(f"BOL validation warnings: {', '.join(warnings)}")

        return warnings


# Singleton instance
bol_parser = BOLParser()
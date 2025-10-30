import logging
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime
import time

from app.models.invoice import InvoiceData
from app.models.responses import ParseResponse, BatchParseResponse
from app.services.storage import storage_service
from app.services.document_ai import document_ai_service
from app.utils.exceptions import ParseError, ValidationError

logger = logging.getLogger(__name__)


class InvoiceParser:
    def __init__(self):
        self.storage = storage_service
        self.document_ai = document_ai_service
    
    async def parse_invoice(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ParseResponse:
        start_time = time.time()
        
        try:
            if not self.storage.bucket:
                self.storage.initialize()
            if not self.document_ai.client:
                self.document_ai.initialize()
            
            logger.info(f"Starting invoice parsing for file: {file_name}")

            # Generate invoice ID
            import uuid
            invoice_id = str(uuid.uuid4())

            await self.storage.upload_file(
                file_content,
                invoice_id,
                file_name,
                content_type,
                metadata,
                folder="invoices"
            )
            logger.info(f"File uploaded with invoice ID: {invoice_id}")
            
            document = await self.document_ai.process_document(
                file_content,
                content_type
            )
            logger.info(f"Document processed successfully")
            
            invoice_data = await self.document_ai.extract_invoice_data(
                document,
                invoice_id
            )
            logger.info(f"Data extracted successfully")
            
            storage_path = await self.storage.save_parsed_data(
                invoice_id,
                invoice_data.dict()
            )
            logger.info(f"Parsed data saved to: {storage_path}")
            
            preview_url = await self.storage.generate_signed_url(
                invoice_id,
                file_name
            )
            
            processing_time = time.time() - start_time
            
            return ParseResponse(
                success=True,
                invoice_id=invoice_id,
                message="Invoice parsed successfully",
                data=invoice_data,
                preview_url=preview_url,
                storage_path=storage_path,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Invoice parsing failed: {e}")
            processing_time = time.time() - start_time
            
            return ParseResponse(
                success=False,
                invoice_id="",
                message=f"Parsing failed: {str(e)}",
                data=None,
                preview_url=None,
                storage_path=None,
                processing_time=processing_time
            )
    
    async def parse_batch(
        self,
        files: List[Dict[str, Any]],
        max_workers: int = 5
    ) -> BatchParseResponse:
        start_time = time.time()
        results = []
        
        try:
            if not self.storage.bucket:
                self.storage.initialize()
            if not self.document_ai.client:
                self.document_ai.initialize()
            
            logger.info(f"Starting batch parsing for {len(files)} files")
            
            semaphore = asyncio.Semaphore(max_workers)
            
            async def parse_with_semaphore(file_data):
                async with semaphore:
                    return await self.parse_invoice(
                        file_data["content"],
                        file_data["name"],
                        file_data.get("content_type", "application/pdf"),
                        file_data.get("metadata")
                    )
            
            tasks = [parse_with_semaphore(file_data) for file_data in files]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            parse_results = []
            for result in results:
                if isinstance(result, Exception):
                    parse_results.append(
                        ParseResponse(
                            success=False,
                            invoice_id="",
                            message=f"Error: {str(result)}",
                            data=None,
                            preview_url=None,
                            storage_path=None,
                            processing_time=0
                        )
                    )
                else:
                    parse_results.append(result)
            
            successful = sum(1 for r in parse_results if r.success)
            failed = len(parse_results) - successful
            
            processing_time = time.time() - start_time
            
            return BatchParseResponse(
                success=failed == 0,
                total_files=len(files),
                processed=successful,
                failed=failed,
                results=parse_results,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Batch parsing failed: {e}")
            processing_time = time.time() - start_time
            
            return BatchParseResponse(
                success=False,
                total_files=len(files),
                processed=0,
                failed=len(files),
                results=[],
                processing_time=processing_time
            )
    
    async def get_invoice_data(self, invoice_id: str) -> InvoiceData:
        try:
            data_dict = await self.storage.get_parsed_data(invoice_id)
            
            return InvoiceData(**data_dict)
            
        except Exception as e:
            logger.error(f"Failed to get invoice data: {e}")
            raise ParseError(f"Failed to retrieve invoice data: {str(e)}")
    
    async def get_invoice_preview(
        self,
        invoice_id: str,
        file_name: str = "invoice.pdf"
    ) -> str:
        try:
            signed_url = await self.storage.generate_signed_url(
                invoice_id,
                file_name
            )
            
            return signed_url
            
        except Exception as e:
            logger.error(f"Failed to generate preview URL: {e}")
            raise ParseError(f"Failed to generate preview URL: {str(e)}")
    
    async def check_duplicate(
        self,
        invoice_data: InvoiceData
    ) -> Optional[str]:
        try:
            existing_invoices = await self.storage.list_invoices("parsed/")
            
            for invoice_path in existing_invoices:
                if not invoice_path.endswith("data.json"):
                    continue
                
                invoice_id = invoice_path.split("/")[1]
                existing_data = await self.storage.get_parsed_data(invoice_id)
                
                if (existing_data.get("invoice_number") == invoice_data.invoice_number and
                    existing_data.get("supplier_name") == invoice_data.supplier_name and
                    str(existing_data.get("total_amount")) == str(invoice_data.total_amount)):
                    return invoice_id
            
            return None
            
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return None
    
    async def validate_invoice_data(self, invoice_data: InvoiceData) -> bool:
        errors = []
        
        if not invoice_data.total_amount or invoice_data.total_amount <= 0:
            errors.append("Invalid total amount")
        
        if invoice_data.subtotal and invoice_data.tax_amount:
            calculated_total = invoice_data.subtotal + invoice_data.tax_amount
            if abs(calculated_total - invoice_data.total_amount) > 0.01:
                errors.append("Total amount doesn't match subtotal + tax")
        
        if invoice_data.invoice_date and invoice_data.due_date:
            if invoice_data.due_date < invoice_data.invoice_date:
                errors.append("Due date is before invoice date")
        
        if invoice_data.line_items:
            line_total = sum(item.amount for item in invoice_data.line_items)
            if invoice_data.subtotal and abs(line_total - invoice_data.subtotal) > 0.01:
                errors.append("Line items total doesn't match subtotal")
        
        confidence_score = invoice_data.confidence_scores.get("overall", 0)
        if confidence_score < 0.5:
            errors.append(f"Low confidence score: {confidence_score:.2f}")
        
        if errors:
            raise ValidationError(f"Validation failed: {', '.join(errors)}")
        
        return True


invoice_parser = InvoiceParser()
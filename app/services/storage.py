from google.cloud import storage
from google.cloud.exceptions import NotFound
from google.auth.transport.requests import Request
from google.auth import iam
import google.auth
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import timedelta
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.utils.exceptions import StorageError
from app.utils.json_encoder import dumps_invoice_data

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

class StorageService:
    def __init__(self):
        self.client: Optional[storage.Client] = None
        self.bucket: Optional[storage.Bucket] = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.bucket_name = settings.BUCKET_NAME
        self.project_id = settings.PROJECT_ID
        self._credentials = None
        self._request: Optional[Request] = None

    def initialize(self):
        try:
            # Application Default Credentials (token-only on Cloud Run)
            self._credentials, detected_project = google.auth.default(scopes=SCOPES)
            if not self.project_id:
                self.project_id = detected_project

            # Create a Request() for refresh + IAM signer
            self._request = Request()

            self.client = storage.Client(
                project=self.project_id, credentials=self._credentials
            )
            self.bucket = self.client.bucket(self.bucket_name)

            if not self.bucket.exists():
                logger.warning(f"Bucket {self.bucket_name} does not exist. Creating...")
                self.bucket = self.client.create_bucket(
                    self.bucket_name,
                    location="US",
                )
                logger.info(f"Bucket {self.bucket_name} created successfully")
            else:
                logger.info(f"Connected to bucket: {self.bucket_name}")

        except Exception as e:
            logger.error(f"Failed to initialize storage service: {e}")
            raise StorageError(f"Storage initialization failed: {str(e)}")

    def _fresh_access_token(self) -> str:
        # Ensure we have a fresh OAuth access token; required for IAM-backed signing
        if self._credentials is None:
            self._credentials, _ = google.auth.default(scopes=SCOPES)
        if self._request is None:
            self._request = Request()

        self._credentials.refresh(self._request)
        return self._credentials.token

    async def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
            invoice_id = str(uuid.uuid4())
            blob_name = f"invoices/{invoice_id}/{file_name}"

            loop = asyncio.get_event_loop()
            blob_path = await loop.run_in_executor(
                self.executor,
                self._upload_to_gcs,
                file_content,
                blob_name,
                content_type,
                metadata,
            )

            logger.info(f"File uploaded successfully: {blob_path}")
            return invoice_id

        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise StorageError(f"File upload failed: {str(e)}")

    def _upload_to_gcs(
        self,
        content: bytes,
        blob_name: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        blob = self.bucket.blob(blob_name)
        if metadata:
            blob.metadata = metadata
        blob.upload_from_string(content, content_type=content_type)
        return blob.name

    async def download_file(self, invoice_id: str, file_name: str) -> bytes:
        try:
            blob_name = f"invoices/{invoice_id}/{file_name}"

            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                self.executor,
                self._download_from_gcs,
                blob_name,
            )
            return content

        except NotFound:
            logger.error(f"File not found: {blob_name}")
            raise StorageError(f"File not found: {invoice_id}/{file_name}")
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            raise StorageError(f"File download failed: {str(e)}")

    def _download_from_gcs(self, blob_name: str) -> bytes:
        blob = self.bucket.blob(blob_name)
        return blob.download_as_bytes()

    async def save_parsed_data(self, invoice_id: str, data: Dict[str, Any]) -> str:
        try:
            blob_name = f"parsed/{invoice_id}/data.json"
            json_content = dumps_invoice_data(data).encode("utf-8")

            loop = asyncio.get_event_loop()
            blob_path = await loop.run_in_executor(
                self.executor,
                self._upload_to_gcs,
                json_content,
                blob_name,
                "application/json",
                {"invoice_id": invoice_id, "type": "parsed_data"},
            )

            logger.info(f"Parsed data saved: {blob_path}")
            return blob_path

        except Exception as e:
            logger.error(f"Failed to save parsed data: {e}")
            raise StorageError(f"Failed to save parsed data: {str(e)}")

    async def get_parsed_data(self, invoice_id: str) -> Dict[str, Any]:
        try:
            blob_name = f"parsed/{invoice_id}/data.json"

            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                self.executor,
                self._download_from_gcs,
                blob_name,
            )
            return json.loads(content)

        except NotFound:
            logger.error(f"Parsed data not found for invoice: {invoice_id}")
            raise StorageError(f"Parsed data not found: {invoice_id}")
        except Exception as e:
            logger.error(f"Failed to get parsed data: {e}")
            raise StorageError(f"Failed to retrieve parsed data: {str(e)}")

    async def generate_signed_url(
        self,
        invoice_id: str,
        file_name: str,
        expiration: int = None,
    ) -> str:
        try:
            blob_name = f"invoices/{invoice_id}/{file_name}"
            expiration = expiration or settings.SIGNED_URL_EXPIRATION

            loop = asyncio.get_event_loop()
            signed_url = await loop.run_in_executor(
                self.executor,
                self._generate_signed_url,
                blob_name,
                expiration,
            )
            return signed_url

        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            raise StorageError(f"Failed to generate signed URL: {str(e)}")

    def _generate_signed_url(self, blob_name: str, expiration: int) -> str:
        if self.bucket is None:
            raise StorageError("Storage service not initialized")

        blob = self.bucket.blob(blob_name)
        logger.info(f"[sign] generating V4 URL for: {blob_name}")
        logger.info(f"[sign] SERVICE_ACCOUNT_EMAIL={settings.SERVICE_ACCOUNT_EMAIL!r}")

        if not settings.SERVICE_ACCOUNT_EMAIL:
            raise StorageError("SERVICE_ACCOUNT_EMAIL environment variable not set!")

    # Ensure request + creds exist and are fresh
        if self._request is None:
         self._request = Request()
        self._credentials.refresh(self._request)

        exp = timedelta(seconds=expiration)

    # ---- Path A: token + email (preferred) ----
        try:
            logger.info("[sign] PATH A: token+email")
            url = blob.generate_signed_url(
             version="v4",
             expiration=exp,
                method="GET",  # use "PUT" for uploads and add content_type
             service_account_email=settings.SERVICE_ACCOUNT_EMAIL,
             access_token=self._credentials.token,
        )
            logger.info("[sign] PATH A succeeded")
            return url
        except Exception as e:
            logger.warning(f"[sign] PATH A failed: {e!r}")

    # ---- Path B: explicit IAM Signer (fallback) ----
        try:
            from google.auth import iam
            logger.info("[sign] PATH B: iam.Signer fallback")
            signer = iam.Signer(
                request=self._request,
             credentials=self._credentials,
             service_account_email=settings.SERVICE_ACCOUNT_EMAIL,
            )
            url = blob.generate_signed_url(
             version="v4",
             expiration=exp,
             method="GET",
             credentials=signer,     # forces IAM-backed signing
        )
            logger.info("[sign] PATH B succeeded")
            return url
        except Exception as e:
            logger.error(f"[sign] PATH B failed: {e!r}")
            raise StorageError(f"Failed to generate signed URL: {e}")


    async def list_invoices(self, prefix: Optional[str] = None) -> list:
        try:
            prefix = prefix or "invoices/"

            loop = asyncio.get_event_loop()
            blobs = await loop.run_in_executor(
                self.executor,
                self._list_blobs,
                prefix,
            )
            return blobs

        except Exception as e:
            logger.error(f"Failed to list invoices: {e}")
            raise StorageError(f"Failed to list invoices: {str(e)}")

    def _list_blobs(self, prefix: str) -> list:
        blobs = self.bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]

    async def delete_invoice(self, invoice_id: str):
        try:
            prefix = f"invoices/{invoice_id}/"

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self._delete_blobs,
                prefix,
            )

            parsed_prefix = f"parsed/{invoice_id}/"
            await loop.run_in_executor(
                self.executor,
                self._delete_blobs,
                parsed_prefix,
            )

            logger.info(f"Invoice {invoice_id} deleted successfully")

        except Exception as e:
            logger.error(f"Failed to delete invoice: {e}")
            raise StorageError(f"Failed to delete invoice: {str(e)}")

    def _delete_blobs(self, prefix: str):
        blobs = self.bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            blob.delete()
            logger.debug(f"Deleted blob: {blob.name}")


storage_service = StorageService()

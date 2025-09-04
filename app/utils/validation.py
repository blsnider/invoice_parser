import os
from typing import BinaryIO, Optional
import hashlib
from app.core.config import settings
from app.utils.exceptions import FileTypeError, FileSizeError, ValidationError

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


def validate_file(
    file_content: bytes,
    file_name: str,
    max_size: Optional[int] = None
) -> bool:
    max_size = max_size or settings.MAX_FILE_SIZE
    
    if len(file_content) > max_size:
        raise FileSizeError(
            f"File size ({len(file_content)} bytes) exceeds maximum allowed size ({max_size} bytes)"
        )
    
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise FileTypeError(
            f"File type '{file_ext}' not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    if HAS_MAGIC:
        try:
            mime = magic.from_buffer(file_content[:2048], mime=True)
            if mime != "application/pdf":
                raise FileTypeError(
                    f"Invalid file content. Expected PDF, got {mime}"
                )
        except Exception as e:
            if not isinstance(e, FileTypeError):
                pass
            else:
                raise
    else:
        if file_content[:4] != b'%PDF':
            raise FileTypeError("Invalid file content. Expected PDF file")
    
    return True


def validate_invoice_number(invoice_number: str) -> bool:
    if not invoice_number:
        return False
    
    if len(invoice_number) < 3 or len(invoice_number) > 50:
        raise ValidationError("Invoice number must be between 3 and 50 characters")
    
    return True


def validate_email(email: str) -> bool:
    import re
    
    if not email:
        return True
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    
    return True


def validate_phone(phone: str) -> bool:
    import re
    
    if not phone:
        return True
    
    cleaned = re.sub(r'[^\d+\-\(\)\s]', '', phone)
    
    if len(cleaned) < 7 or len(cleaned) > 20:
        raise ValidationError(f"Invalid phone number: {phone}")
    
    return True


def calculate_file_hash(file_content: bytes) -> str:
    return hashlib.sha256(file_content).hexdigest()


def sanitize_filename(filename: str) -> str:
    import re
    
    filename = os.path.basename(filename)
    
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    
    filename = re.sub(r'[\s]+', '_', filename)
    
    return filename[:255]
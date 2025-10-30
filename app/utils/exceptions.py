class DocumentParserException(Exception):
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class InvoiceParserException(DocumentParserException):
    pass


class DocumentAIError(InvoiceParserException):
    def __init__(self, message: str):
        super().__init__(message, "DOCUMENT_AI_ERROR")


class StorageError(InvoiceParserException):
    def __init__(self, message: str):
        super().__init__(message, "STORAGE_ERROR")


class ValidationError(InvoiceParserException):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class ParseError(InvoiceParserException):
    def __init__(self, message: str):
        super().__init__(message, "PARSE_ERROR")


class AuthenticationError(InvoiceParserException):
    def __init__(self, message: str):
        super().__init__(message, "AUTH_ERROR")


class RateLimitError(InvoiceParserException):
    def __init__(self, message: str):
        super().__init__(message, "RATE_LIMIT_ERROR")


class FileTypeError(ValidationError):
    def __init__(self, message: str):
        super().__init__(message)
        self.code = "INVALID_FILE_TYPE"


class FileSizeError(ValidationError):
    def __init__(self, message: str):
        super().__init__(message)
        self.code = "FILE_SIZE_EXCEEDED"
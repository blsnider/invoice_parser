import json
from decimal import Decimal
from datetime import date, datetime
from typing import Any


class InvoiceJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for invoice data that handles special types."""
    
    def default(self, obj: Any) -> Any:
        """Convert special types to JSON-serializable formats."""
        if isinstance(obj, Decimal):
            # Convert Decimal to string to preserve precision
            return str(obj)
        elif isinstance(obj, (date, datetime)):
            # Convert dates to ISO format strings
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            # Handle Pydantic models and other objects with __dict__
            return obj.__dict__
        
        # Let the base class handle other types
        return super().default(obj)


def dumps_invoice_data(data: dict) -> str:
    """Serialize invoice data to JSON string with custom encoder."""
    return json.dumps(data, cls=InvoiceJSONEncoder, indent=2)


def loads_invoice_data(json_str: str) -> dict:
    """Deserialize JSON string to invoice data dictionary."""
    return json.loads(json_str)
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from pythonjsonlogger import jsonlogger


class CloudRunFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super().add_fields(log_record, record, message_dict)
        
        log_record["timestamp"] = datetime.utcnow().isoformat()
        log_record["severity"] = record.levelname
        log_record["service"] = "invoice-parser"
        
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id
        
        if record.exc_info:
            log_record["error"] = self.formatException(record.exc_info)


def setup_logging(log_level: str = "INFO"):
    from app.core.config import settings
    
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.ENVIRONMENT == "production":
        formatter = CloudRunFormatter(
            "%(timestamp)s %(severity)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    
    return root_logger
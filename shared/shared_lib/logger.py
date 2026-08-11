import logging
import json
import os
import sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    
    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if os.getenv("LOG_FORMAT", "text").lower() == "json":
            handler.setFormatter(JSONFormatter())
        else:
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

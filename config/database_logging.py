
# Database-compatible logging configuration
import logging
import json
from datetime import datetime
from database.adapter import db_adapter
from config.settings import USE_DATABASE

class DatabaseLogHandler(logging.Handler):
    """Custom log handler that can optionally store logs in database."""
    
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": getattr(record, 'module', 'unknown'),
                "function": getattr(record, 'funcName', 'unknown'),
                "line": getattr(record, 'lineno', 0)
            }
            
            if hasattr(record, 'exc_info') and record.exc_info:
                log_entry["exception"] = self.format(record)
            
            # Store in database if enabled
            if USE_DATABASE:
                try:
                    db_adapter.add_log_entry(log_entry)
                except Exception:
                    # Fallback to file logging if database fails
                    pass
            
            # Always also log to file as backup
            print(json.dumps(log_entry))
            
        except Exception:
            self.handleError(record)

def setup_database_logging():
    """Setup logging to work with database."""
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add database-compatible handler
    db_handler = DatabaseLogHandler()
    db_handler.setLevel(logging.INFO)
    root_logger.addHandler(db_handler)
    root_logger.setLevel(logging.INFO)

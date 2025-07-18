import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Configure the root logger
root_logger = logging.getLogger()

# Define log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# Custom JSON formatter
class JsonFormatter(logging.Formatter):
    """Custom formatter to output logs in JSON format for better parsing"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields from the record
        if hasattr(record, "extra") and record.extra:
            log_data.update(record.extra)
            
        return json.dumps(log_data)


# Standard formatter for console output
class StandardFormatter(logging.Formatter):
    """Standard formatter for console output with colors"""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m"       # Reset
    }
    
    def format(self, record):
        log_format = "%(asctime)s - %(name)s - "
        
        # Add color to the level name if supported
        if sys.stdout.isatty():  # Check if output is to a terminal
            level_color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            log_format += f"{level_color}%(levelname)s{self.COLORS['RESET']} - "
        else:
            log_format += "%(levelname)s - "
            
        log_format += "%(message)s"
        
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_logging(log_level: str = "INFO", 
                 log_file: Optional[str] = None,
                 json_format: bool = False,
                 max_file_size_mb: int = 10,
                 backup_count: int = 5) -> None:
    """Set up logging configuration with log rotation
    
    Args:
        log_level: The minimum log level to capture (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to a log file. If None, logs will only go to console
        json_format: Whether to use JSON formatting for logs
        max_file_size_mb: Maximum size of log file in MB before rotation
        backup_count: Number of backup log files to keep
    """
    # Get the numeric log level
    numeric_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
    
    # Configure the root logger
    root_logger.setLevel(numeric_level)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:  
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    
    # Set formatter based on format preference
    if json_format:
        console_formatter = JsonFormatter()
    else:
        console_formatter = StandardFormatter()
        
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Add rotating file handler if log_file is specified
    if log_file:
        # Ensure the directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Create rotating file handler to prevent large log files
        max_bytes = max_file_size_mb * 1024 * 1024  # Convert MB to bytes
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        file_handler.setLevel(numeric_level)
        
        # Always use JSON format for file logging for better parsing
        file_formatter = JsonFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Log the configuration
    if log_file:
        logging.info(f"Logging configured with level={log_level}, file={log_file}, json_format={json_format}, max_size={max_file_size_mb}MB, backups={backup_count}")
    else:
        logging.info(f"Logging configured with level={log_level}, console_only=True, json_format={json_format}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter that adds context to log messages"""
    
    def process(self, msg, kwargs):
        # Add extra context to the log record
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra'].update(self.extra)
        return msg, kwargs


def get_context_logger(name: str, context: Dict[str, Any]) -> LoggerAdapter:
    """Get a logger with additional context information
    
    Args:
        name: The logger name
        context: Dictionary of context values to include in all log messages
        
    Returns:
        A logger adapter that includes the context in all messages
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, context)
"""Logging configuration."""

import logging
import sys

def configure_logging(level: str = "INFO") -> None:
    """Configure root logger for production and development."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Root logger config
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    if root_logger.handlers:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            
    root_logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """Helper to retrieve standard logger by name."""
    return logging.getLogger(name)

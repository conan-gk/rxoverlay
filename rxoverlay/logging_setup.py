"""Logging setup for RxOverlay."""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str = "rxoverlay.log") -> None:
    """Setup logging configuration."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        try:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            # If we can't create the log file, continue without it
            print(f"Warning: Could not create log file {log_path}: {e}")
    
    # Suppress noisy third-party loggers
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
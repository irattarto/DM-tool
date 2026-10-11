"""
Logging utilities for RPG Database Manager.
"""

import logging
import logging.handlers
import sys
from typing import Optional

from config.paths import get_data_dir


def setup_logging(
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Setup logging configuration for the application.

    Args:
        level: Logging level (default: logging.INFO)
        log_to_file: Whether to log to file (default: True)
        log_to_console: Whether to log to console (default: True)
        max_bytes: Maximum size of log file before rotation (default: 10MB)
        backup_count: Number of backup log files to keep (default: 5)

    Returns:
        Configured logger instance
    """

    # Create logger
    logger = logging.getLogger('rpg_database_manager')
    logger.setLevel(level)
    logger.propagate = False  # Prevent duplicate output via root logger (basicConfig)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(levelname)s - %(name)s - %(message)s'
    )

    # File handler (if enabled)
    if log_to_file:
        try:
            # Get log directory in app data location
            log_dir = get_data_dir() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / "rpg_database_manager.log"

            # Create rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        except Exception as e:
            print(f"Warning: Could not set up file logging: {e}")

    # Console handler (if enabled)
    # sys.stdout is None in a PyInstaller windowed EXE (console=False); skip
    # the handler in that case to avoid AttributeError on the first log write.
    if log_to_console and sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Name of the module/component

    Returns:
        Logger instance
    """
    return logging.getLogger(f'rpg_database_manager.{name}')


# Convenience functions for common logging patterns
def log_database_operation(operation: str, table: str, record_id: Optional[int] = None):
    """
    Log a database operation.

    Args:
        operation: Type of operation (INSERT, UPDATE, DELETE, SELECT)
        table: Table name
        record_id: Optional record ID for the operation
    """
    logger = get_logger('database')
    message = f"{operation} on {table}"
    if record_id:
        message += f" (ID: {record_id})"

    logger.info(message)

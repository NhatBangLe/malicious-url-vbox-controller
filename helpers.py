import io
import logging
import sys
import os
from datetime import datetime


def setup_logging(logging_dir="./logs"):
    os.makedirs(logging_dir, exist_ok=True)

    # Create a unique filename based on the current start time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logging_dir, f"audit_{timestamp}.log")

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture everything at the root level

    # Clear existing handlers if main is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. File Handler: Detailed logs (DEBUG level) for the specific run
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # 2. Stream Handler: Cleaner console output (INFO level)
    console_handler = logging.StreamHandler(
        io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    )
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s]: %(message)s", datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info(f"Logging initialized. Full log: {log_file}")

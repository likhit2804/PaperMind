import os
import sys
import logging
from datetime import datetime

# Root directory is parent of pipeline/
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(ROOT_DIR, "logs")

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)

PIPELINE_LOG_FILE = os.path.join(LOGS_DIR, "pipeline.log")

# Setup logger
logger = logging.getLogger("PaperMindPipeline")
logger.setLevel(logging.DEBUG)

# Prevent duplicate handlers if imported multiple times
if not logger.handlers:
    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # File Handler
    file_handler = logging.FileHandler(PIPELINE_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def log_info(msg):
    logger.info(msg)

def log_warn(msg):
    logger.warning(msg)

def log_error(msg, exc=None):
    if exc:
        logger.error(f"{msg} | Exception: {exc}", exc_info=True)
    else:
        logger.error(msg)

def log_debug(msg):
    logger.debug(msg)

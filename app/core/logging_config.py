# logging_config.py

"""
app/core/logging_config.py
==========================
Centralized logging configuration for the entire SCGpipeline application.

Every module imports the logger from here:
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)

Two outputs:
  - Console  : INFO level and above, concise format (for dev)
  - File     : DEBUG level and above, full format with timestamp (persistent)

Log files are stored in the logs/ folder with automatic rotation:
  logs/app.log         ← all modules (FastAPI + Celery)
  logs/celery_task.log ← dedicated copy of logs from the Celery worker
                          (app.services.detection_task), so it can be monitored
                          separately without mixing with FastAPI request logs
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")
_LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_LEVEL     = getattr(logging, _LOG_LEVEL_STR, logging.INFO)


def _build_root_logger() -> logging.Logger:
    """
    Create and configure the 'scgpipeline' root logger.
    Called once when this module is first imported.
    """
    root = logging.getLogger("scgpipeline")

    if root.handlers:
        return root

    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(levelname)-8s [%(name)s] %(message)s"
    ))

    
    file_h = RotatingFileHandler(
        _LOG_FILE,
        maxBytes    = 5 * 1024 * 1024,  # 5 MB
        backupCount = 3,
        encoding    = "utf-8",
    )
    file_h.setLevel(_LOG_LEVEL)
    file_h.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root.addHandler(console)
    root.addHandler(file_h)

    root.info(
        "Logging initialized — file: %s, level: %s",
        _LOG_FILE, _LOG_LEVEL_STR,
    )
    return root


_root_logger = _build_root_logger()


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the 'scgpipeline' namespace.

    Example:
        # In app/api_routes.py
        logger = get_logger(__name__)
        # → logger.name = "scgpipeline.app.api_routes"

    Output is automatically forwarded to the root handlers (file + console).
    """
    clean = name.replace("app.", "", 1) if name.startswith("app.") else name
    return logging.getLogger(f"scgpipeline.{clean}")


# ── Additional dedicated handler for Celery worker ──────────────────────────────────
# Logs from app.services.detection_task still go to logs/app.log via
# the root logger (default propagation), BUT are also written to this separate file
# so they can be easily monitored side-by-side (e.g., `make logs-celery`) without having
# to filter them from FastAPI request logs.
_CELERY_LOG_FILE = os.path.join(_LOG_DIR, "celery_task.log")
_celery_file_h = RotatingFileHandler(
    _CELERY_LOG_FILE,
    maxBytes    = 5 * 1024 * 1024,
    backupCount = 3,
    encoding    = "utf-8",
)
_celery_file_h.setLevel(_LOG_LEVEL)
_celery_file_h.setFormatter(logging.Formatter(
    "[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logging.getLogger("scgpipeline.services.detection_task").addHandler(_celery_file_h)
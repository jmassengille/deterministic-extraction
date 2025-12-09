"""Storage configuration and constants."""

import os
from pathlib import Path
from typing import Set

# Base directories
BASE_DIR = Path(os.getenv("DATA_DIR", "Data"))
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"

# File handling
MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "104857600"))  # 100MB default
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "8192"))  # 8KB chunks
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", "1048576"))  # 1MB for SpooledTemporaryFile

# Cleanup settings
MSF_RETENTION_HOURS = int(os.getenv("MSF_RETENTION_HOURS", "24"))
PDF_RETENTION_HOURS = int(os.getenv("PDF_RETENTION_HOURS", "1"))  # Delete PDFs quickly after processing
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL", "3600"))  # 1 hour
CLEANUP_BATCH_SIZE = int(os.getenv("CLEANUP_BATCH_SIZE", "100"))  # Process 100 files at a time

# File validation
ALLOWED_EXTENSIONS: Set[str] = {".pdf"}
ALLOWED_MIME_TYPES: Set[str] = {"application/pdf"}
MIN_FILE_SIZE = 1024  # 1KB minimum

# Storage paths
def ensure_directories() -> None:
    """Create required directories if they don't exist."""
    for directory in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


class StorageConfig:
    """Storage configuration container."""

    upload_dir = UPLOAD_DIR
    output_dir = OUTPUT_DIR
    temp_dir = TEMP_DIR
    max_file_size = MAX_FILE_SIZE
    chunk_size = CHUNK_SIZE
    buffer_size = BUFFER_SIZE
    msf_retention_hours = MSF_RETENTION_HOURS
    pdf_retention_hours = PDF_RETENTION_HOURS
    cleanup_interval = CLEANUP_INTERVAL_SECONDS
    cleanup_batch_size = CLEANUP_BATCH_SIZE
    allowed_extensions = ALLOWED_EXTENSIONS
    allowed_mime_types = ALLOWED_MIME_TYPES
    min_file_size = MIN_FILE_SIZE

    @classmethod
    def validate(cls) -> None:
        """Validate configuration settings."""
        if cls.max_file_size <= 0:
            raise ValueError("MAX_FILE_SIZE must be positive")
        if cls.chunk_size <= 0:
            raise ValueError("CHUNK_SIZE must be positive")
        if cls.cleanup_interval <= 0:
            raise ValueError("CLEANUP_INTERVAL must be positive")

    @classmethod
    def init(cls) -> None:
        """Initialize storage configuration."""
        cls.validate()
        ensure_directories()
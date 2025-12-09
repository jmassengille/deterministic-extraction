"""Core storage service for file operations."""

import asyncio
import hashlib
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional, Tuple
from uuid import uuid4

import aiofiles
import aiofiles.os
import fitz  # PyMuPDF

from .config import StorageConfig
from .exceptions import (
    FileValidationError,
    PDFValidationError,
    DiskSpaceError,
    FileOperationError,
)

logger = logging.getLogger(__name__)


def sanitize_filename_part(text: str) -> str:
    """Sanitize a single part of filename (manufacturer/model/type)."""
    if not text:
        return ""

    # Replace common separators with underscores
    replacements = {
        ' ': '_',
        '(': '_',
        ')': '_',
        '[': '_',
        ']': '_',
        '{': '_',
        '}': '_',
        ',': '_',
        ';': '_',
        ':': '_',
        '/': '_',
        '\\': '_',
        '|': '_',
        '<': '_',
        '>': '_',
        '?': '_',
        '*': '_',
        '"': '_',
        "'": '_',
        '\t': '_',
        '\n': '_',
        '\r': '_'
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove multiple consecutive underscores
    while '__' in text:
        text = text.replace('__', '_')

    # Strip leading/trailing underscores
    text = text.strip('_')

    # Keep dots and hyphens as they're safe
    # Final safety check - only allow alphanumeric, underscore, hyphen, dot
    text = "".join(c if c.isalnum() or c in '-_.' else '_' for c in text)

    # One more pass to clean up any double underscores from final safety check
    while '__' in text:
        text = text.replace('__', '_')

    return text.strip('_')


class StorageService:
    """Service for file storage operations."""

    @staticmethod
    async def save_upload(
        file_content: AsyncIterator[bytes],
        filename: str,
        expected_size: Optional[int] = None,
    ) -> Tuple[str, str, int]:
        """
        Stream save uploaded file to storage.

        Args:
            file_content: Async iterator of file chunks
            filename: Original filename
            expected_size: Expected file size for validation

        Returns:
            Tuple of (file_path, file_hash, actual_size)

        Raises:
            FileValidationError: Invalid file
            DiskSpaceError: Insufficient space
            FileOperationError: Save failed
        """
        # Validate filename
        if not filename or not filename.lower().endswith(".pdf"):
            raise FileValidationError(
                "Invalid filename",
                {"filename": filename, "allowed": list(StorageConfig.allowed_extensions)},
            )

        # Generate unique path
        file_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        file_path = StorageConfig.upload_dir / f"{file_id}_{Path(filename).name}"
        temp_path = StorageConfig.temp_dir / f"{file_id}.tmp"

        # Ensure directories exist
        StorageConfig.upload_dir.mkdir(parents=True, exist_ok=True)
        StorageConfig.temp_dir.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total_size = 0

        try:
            # Stream to temporary file
            async with aiofiles.open(temp_path, "wb") as temp_file:
                async for chunk in file_content:
                    # Check size limit
                    total_size += len(chunk)
                    if total_size > StorageConfig.max_file_size:
                        try:
                            await aiofiles.os.remove(str(temp_path))
                        except OSError as e:
                            logger.warning(f"Failed to remove temp file: {e}")
                        raise FileValidationError(
                            "File exceeds maximum size",
                            {
                                "size": total_size,
                                "max_size": StorageConfig.max_file_size,
                            },
                        )

                    # Write chunk and update hash
                    await temp_file.write(chunk)
                    hasher.update(chunk)

            # Validate size if provided
            if expected_size and total_size != expected_size:
                try:
                    await aiofiles.os.remove(str(temp_path))
                except OSError as e:
                    logger.warning(f"Failed to remove temp file: {e}")
                raise FileValidationError(
                    "File size mismatch",
                    {"expected": expected_size, "actual": total_size},
                )

            # Validate minimum size
            if total_size < StorageConfig.min_file_size:
                try:
                    await aiofiles.os.remove(str(temp_path))
                except OSError as e:
                    logger.warning(f"Failed to remove temp file: {e}")
                raise FileValidationError(
                    "File too small",
                    {"size": total_size, "min_size": StorageConfig.min_file_size},
                )

            # Move to final location
            await asyncio.get_event_loop().run_in_executor(
                None, shutil.move, str(temp_path), str(file_path)
            )

            logger.info(f"File saved: {file_path} ({total_size} bytes)")
            return str(file_path), hasher.hexdigest(), total_size

        except (FileValidationError, DiskSpaceError):
            raise
        except OSError as e:
            if "No space left" in str(e):
                raise DiskSpaceError("Insufficient disk space", {"error": str(e)})
            raise FileOperationError(f"Failed to save file: {e}", {"path": str(file_path)})
        except Exception as e:
            # Clean up temp file on error
            try:
                if temp_path.exists():
                    await aiofiles.os.remove(str(temp_path))
            except Exception:
                pass
            raise FileOperationError(f"Unexpected error saving file: {e}")

    @staticmethod
    async def validate_pdf(file_path: str) -> dict:
        """
        Validate PDF file integrity.

        Args:
            file_path: Path to PDF file

        Returns:
            Dict with validation results

        Raises:
            PDFValidationError: Invalid PDF
        """
        path = Path(file_path)
        if not path.exists():
            raise PDFValidationError("File not found", {"path": file_path})

        try:
            # Run validation in executor to avoid blocking
            loop = asyncio.get_event_loop()
            metadata = await loop.run_in_executor(None, _validate_pdf_sync, file_path)
            return metadata
        except Exception as e:
            if "PDF" in str(e) or "invalid" in str(e).lower():
                raise PDFValidationError(f"Invalid PDF: {e}", {"path": file_path})
        except Exception as e:
            raise PDFValidationError(f"PDF validation failed: {e}", {"path": file_path})

    @staticmethod
    async def delete_file(file_path: str, ignore_missing: bool = True) -> bool:
        """
        Delete file from storage.

        Args:
            file_path: Path to file
            ignore_missing: Don't raise error if file doesn't exist

        Returns:
            True if deleted, False if didn't exist
        """
        try:
            path = Path(file_path)
            if not path.exists():
                if ignore_missing:
                    return False
                raise FileOperationError("File not found", {"path": file_path})

            await aiofiles.os.remove(str(file_path))
            logger.info(f"File deleted: {file_path}")
            return True
        except Exception as e:
            raise FileOperationError(f"Failed to delete file: {e}", {"path": file_path})

    @staticmethod
    async def get_file_info(file_path: str) -> dict:
        """
        Get file metadata.

        Args:
            file_path: Path to file

        Returns:
            Dict with file metadata
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileOperationError("File not found", {"path": file_path})

            stat = await aiofiles.os.stat(str(file_path))
            return {
                "path": file_path,
                "name": path.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime),
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "extension": path.suffix.lower(),
            }
        except Exception as e:
            raise FileOperationError(f"Failed to get file info: {e}", {"path": file_path})

    @staticmethod
    def generate_output_path(job_id: str, instrument_name: str = "unknown") -> str:
        """
        Generate MSF output path.

        Args:
            job_id: Job ID
            instrument_name: Instrument name for filename

        Returns:
            Output file path
        """
        # Create job-specific subdirectory
        job_dir = StorageConfig.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Instrument name should already be sanitized, but ensure safety
        safe_name = sanitize_filename_part(instrument_name) if instrument_name else "unknown"

        # Add .msf extension
        filename = f"{safe_name}.msf"

        return str(job_dir / filename)


def _validate_pdf_sync(file_path: str) -> dict:
    """Synchronous PDF validation helper."""
    try:
        with fitz.open(file_path) as doc:
            metadata = {
                "pages": doc.page_count,
                "encrypted": doc.needs_pass,
                "has_metadata": bool(doc.metadata),
            }

            if doc.metadata:
                metadata.update({
                    "title": doc.metadata.get("title", ""),
                    "author": doc.metadata.get("author", ""),
                    "subject": doc.metadata.get("subject", ""),
                    "creator": doc.metadata.get("creator", ""),
                })

            # Try to read first page to ensure it's accessible
            if doc.page_count > 0:
                first_page = doc[0]
                _ = first_page.get_text()[:100]  # Extract small sample

            return metadata
    except Exception as e:
        raise Exception(f"PDF validation failed: {e}")
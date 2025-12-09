"""File upload routes with pluggable output format support."""

import json
from typing import List, Optional, Dict, Any, AsyncIterator, Set

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel

from backend.serializers import SerializerFactory, OutputFormat
from backend.config.settings import DEFAULT_OUTPUT_FORMAT
from ..storage.manager import FileManager
from ..storage.exceptions import StorageException, FileValidationError
from ..jobs.schemas import JobResponse

router = APIRouter(prefix="/upload", tags=["upload"])


def _get_valid_output_formats() -> Set[str]:
    """Get valid output formats from serializer registry.

    Returns:
        Set of registered format names
    """
    return {fmt.value for fmt in SerializerFactory.get_available_formats()}


class UploadResponse(BaseModel):
    """Response model for file upload."""
    job_id: str
    filename: str
    file_size: int
    output_formats: List[str]
    message: str


async def file_generator(file: UploadFile) -> AsyncIterator[bytes]:
    """Generate chunks from uploaded file."""
    try:
        while chunk := await file.read(8192):  # 8KB chunks
            yield chunk
    finally:
        await file.close()


def _validate_output_formats(formats_str: Optional[str]) -> List[str]:
    """Validate and parse output formats parameter.

    Args:
        formats_str: Comma-separated format list (e.g., "json,csv")

    Returns:
        List of validated format strings

    Raises:
        HTTPException: If formats are invalid
    """
    valid_formats = _get_valid_output_formats()

    # Use default if not specified
    if not formats_str:
        if DEFAULT_OUTPUT_FORMAT and DEFAULT_OUTPUT_FORMAT in valid_formats:
            return [DEFAULT_OUTPUT_FORMAT]
        raise HTTPException(
            status_code=400,
            detail=f"output_formats is required. Available: {sorted(valid_formats)}"
        )

    formats = [f.strip().lower() for f in formats_str.split(",")]

    validated = []
    for fmt in formats:
        if not fmt:
            continue
        if fmt not in valid_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid output format: '{fmt}'. Available: {sorted(valid_formats)}"
            )
        if fmt not in validated:
            validated.append(fmt)

    if not validated:
        raise HTTPException(
            status_code=400,
            detail=f"At least one valid output format is required. Available: {sorted(valid_formats)}"
        )

    return validated


@router.post("", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(..., description="PDF file to process"),
    output_formats: str = Form(
        None,
        description="Comma-separated output formats (from registered serializers)"
    ),
    metadata: Optional[str] = Form(None, description="Optional JSON metadata")
) -> UploadResponse:
    """
    Upload a PDF file for processing.

    Creates a new job and starts background processing.
    Output formats are validated against registered serializers.

    Args:
        file: PDF file to upload
        output_formats: Comma-separated list of formats (discovered from registry)
        metadata: Optional JSON metadata string
    """
    # Validate output formats (required, no default)
    validated_formats = _validate_output_formats(output_formats)

    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    if not file.content_type or file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Invalid content type. Expected application/pdf"
        )

    # Parse metadata if provided
    job_metadata: Dict[str, Any] = {}
    if metadata:
        try:
            job_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid metadata JSON format"
            )

    # Add output formats to job metadata
    job_metadata["output_formats"] = validated_formats

    # Process upload
    file_manager = FileManager()

    try:
        # Get file size
        file_size = 0
        if hasattr(file, 'size') and file.size:
            file_size = file.size
        else:
            # Estimate size by reading first chunk
            chunk = await file.read(8192)
            if chunk:
                file_size = len(chunk)
                # Reset file pointer
                await file.seek(0)

        result = await file_manager.process_upload(
            file_content=file_generator(file),
            filename=file.filename,
            file_size=file_size,
            metadata=job_metadata
        )

        return UploadResponse(
            job_id=str(result["job_id"]),
            filename=result["filename"],
            file_size=result["file_size"],
            output_formats=validated_formats,
            message=f"File uploaded successfully. Job {result['job_id']} created."
        )

    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=f"File validation failed: {e}")
    except StorageException as e:
        raise HTTPException(status_code=507, detail=f"Storage error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
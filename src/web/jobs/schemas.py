"""Pydantic v2 schemas for jobs domain.

Using modern Pydantic v2 patterns:
- ConfigDict instead of Config class
- field_validator instead of validator
- model_validate instead of parse_obj

Pluggable output format support:
- output_formats: List of requested formats (from registered serializers)
- output_paths: Dict mapping format name to file path(s)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.types import FilePath


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStage(str, Enum):
    """Processing stages for progress tracking."""
    QUEUED = "queued"
    LOADING_DOCUMENT = "loading_document"
    ANALYZING_STRUCTURE = "analyzing_structure"
    EXTRACTING_REGIONS = "extracting_regions"
    PROCESSING_DATA = "processing_data"
    GENERATING_OUTPUT = "generating_output"
    FINALIZING = "finalizing"


class JobBase(BaseModel):
    """Base job schema."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        ser_json_timedelta="iso8601"
    )

    filename: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., gt=0, le=104857600)  # Max 100MB
    mime_type: str = Field(default="application/pdf")

    @field_validator("mime_type")
    @classmethod
    def validate_pdf_type(cls, v: str) -> str:
        if v != "application/pdf":
            raise ValueError("Only PDF files are supported")
        return v


class JobCreate(JobBase):
    """Schema for creating a new job."""
    pdf_path: str = Field(..., description="Temporary file path")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Job metadata including file hash and PDF info"
    )
    output_formats: List[str] = Field(
        default_factory=lambda: ["json"],
        description="Requested output formats"
    )

    @field_validator("pdf_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not v or ".." in v:
            raise ValueError("Invalid file path")
        return v

    @field_validator("output_formats")
    @classmethod
    def validate_output_formats(cls, v: List[str]) -> List[str]:
        valid = {"json"}
        for fmt in v:
            if fmt.lower() not in valid:
                raise ValueError(f"Invalid output format: {fmt}")
        return [f.lower() for f in v]


class JobUpdate(BaseModel):
    """Schema for updating job status."""
    model_config = ConfigDict(str_strip_whitespace=True)

    status: Optional[JobStatus] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    current_stage: Optional[JobStage] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    # Output format fields
    output_formats: Optional[List[str]] = None
    output_paths: Optional[Dict[str, Any]] = Field(
        None,
        description="Output file paths keyed by format (str for single-file, dict for multi-file)"
    )


class JobInDB(JobBase):
    """Job as stored in database."""
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        ser_json_timedelta="iso8601"
    )

    id: UUID = Field(default_factory=uuid4)
    status: JobStatus = Field(default=JobStatus.PENDING)
    pdf_path: str
    progress: int = Field(default=0, ge=0, le=100)
    current_stage: JobStage = Field(default=JobStage.QUEUED)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_pages: List[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Pluggable output format support
    output_formats: List[str] = Field(
        default_factory=lambda: ["json"],
        description="Requested output formats (from registered serializers)"
    )
    output_paths: Dict[str, Any] = Field(
        default_factory=dict,
        description="Output file paths keyed by format (str for single-file, dict for multi-file)"
    )

    @model_validator(mode="after")
    def validate_timestamps(self) -> "JobInDB":
        """Ensure timestamp consistency."""
        if self.started_at and self.created_at:
            if self.started_at < self.created_at:
                raise ValueError("started_at cannot be before created_at")
        if self.completed_at:
            if not self.started_at:
                raise ValueError("completed_at requires started_at")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at cannot be before started_at")
        return self

    @property
    def is_terminal(self) -> bool:
        """Check if job is in terminal state."""
        return self.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}

    @property
    def can_cancel(self) -> bool:
        """Check if job can be cancelled."""
        return self.status in {JobStatus.PENDING, JobStatus.PROCESSING}

    @property
    def duration(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()


class JobResponse(JobInDB):
    """Job response for API."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "document.pdf",
                "file_size": 2048576,
                "status": "processing",
                "progress": 45,
                "current_stage": "extracting_regions",
                "output_formats": ["json"],
                "output_paths": {"json": "/output/document.json"},
                "created_at": "2025-09-13T10:30:00Z"
            }
        }
    )


class ProgressEvent(BaseModel):
    """Progress event for SSE streaming."""
    model_config = ConfigDict(str_strip_whitespace=True)

    job_id: UUID
    progress: int = Field(..., ge=0, le=100)
    stage: JobStage
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Optional[Dict[str, Any]] = None

    def to_sse(self) -> str:
        """Convert to SSE format."""
        import json
        data = {
            "job_id": str(self.job_id),
            "progress": self.progress,
            "stage": self.stage.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details or {}
        }
        return f"data: {json.dumps(data)}\n\n"


class JobListResponse(BaseModel):
    """Paginated job list response."""
    model_config = ConfigDict(from_attributes=True)

    jobs: list[JobResponse]
    total: int
    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=100)
    pages: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def calculate_pages(self) -> "JobListResponse":
        """Calculate total pages."""
        import math
        self.pages = math.ceil(self.total / self.per_page) if self.total > 0 else 0
        return self
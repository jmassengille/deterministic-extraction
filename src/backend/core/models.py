"""Core data models for the backend."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TableSpec:
    """Specification for a table extracted from PDF (vision-based extraction)."""
    page_number: int
    table_index: int
    source_path: str
    image_bytes: bytes
    extraction_method: str = "vision"
    metadata: Optional[Dict[str, Any]] = None
    page_context: Optional[Dict[str, str]] = None
    section_title: Optional[str] = None  # From TOC - which section this table belongs to

    def __post_init__(self):
        if self.image_bytes is None:
            raise ValueError(
                f"Vision-based extraction requires image_bytes but received None "
                f"for page {self.page_number}, table index {self.table_index}. "
                f"Verify TableCropper is populating image_bytes correctly."
            )
        if self.metadata is None:
            self.metadata = {}
        if self.page_context is None:
            self.page_context = {"headers": "", "footnotes": "", "page_text": ""}


@dataclass 
class InstrumentInfo:
    """Information about the instrument being processed."""
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    description: Optional[str] = None
    instrument_type: Optional[str] = None
    
    def get_display_name(self) -> str:
        """Get display name for logging."""
        parts = []
        if self.manufacturer:
            parts.append(self.manufacturer)
        if self.model:
            parts.append(self.model)
        if self.description:
            parts.append(f"({self.description})")
        return " ".join(parts) if parts else "Unknown Instrument"


@dataclass
class ExtractionResult:
    """Result of LLM extraction."""
    success: bool
    function_groups: List[Dict[str, Any]]
    extraction_notes: List[str]
    metadata: Dict[str, Any]
    error_message: Optional[str] = None
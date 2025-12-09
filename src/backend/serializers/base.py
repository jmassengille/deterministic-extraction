"""
Base classes and types for format serializers.

This module defines the abstract base class FormatSerializer and supporting
types used by all format-specific serializers.

Design Pattern: Strategy Pattern
    - FormatSerializer is the abstract strategy interface
    - Concrete serializers implement format-specific logic
    - SerializerFactory creates the appropriate strategy based on format
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional


class OutputFormat(str, Enum):
    """Supported output formats for extracted data."""

    JSON = "json"

    @property
    def file_extension(self) -> str:
        """Get the file extension for this format."""
        return f".{self.value}"

    @property
    def display_name(self) -> str:
        """Get human-readable format name."""
        names = {
            self.JSON: "JSON (JavaScript Object Notation)",
        }
        return names.get(self, self.value.upper())


@dataclass
class SerializerConfig:
    """Configuration for format serializers."""

    output_dir: Path
    instrument_name: str
    include_comments: bool = True
    scientific_notation: bool = False
    precision: int = 6
    overwrite_existing: bool = False

    def get_output_path(self, filename: str) -> Path:
        """Get full output path for a filename."""
        return self.output_dir / filename


@dataclass
class DataLossWarning:
    """
    Warning about data loss during format conversion.

    Used to track fields that cannot be represented in the target format.
    """

    field: str
    location: str
    value: str
    reason: str
    severity: str = "warning"

    def to_message(self) -> str:
        """Format warning as user-readable message."""
        return f"{self.field} at {self.location}: '{self.value}' - {self.reason}"


@dataclass
class SerializedOutput:
    """
    Result of serializing extracted data.

    Contains the generated content and metadata about the output.
    """

    filename: str
    content: str
    format: OutputFormat
    metadata: dict = field(default_factory=dict)
    warnings: list[DataLossWarning] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings were generated."""
        return len(self.warnings) > 0

    @property
    def size_bytes(self) -> int:
        """Get content size in bytes."""
        return len(self.content.encode("utf-8"))

    def write_to_path(self, output_dir: Path) -> Path:
        """
        Write content to file.

        Args:
            output_dir: Directory to write file to

        Returns:
            Path to written file
        """
        output_path = output_dir / self.filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.content, encoding="utf-8")
        return output_path


class FormatSerializer(ABC):
    """
    Abstract base class for all format serializers.

    Subclasses implement format-specific serialization logic.
    """

    def __init__(self, config: SerializerConfig):
        """
        Initialize serializer with configuration.

        Args:
            config: Serializer configuration
        """
        self.config = config

    @property
    @abstractmethod
    def format_type(self) -> OutputFormat:
        """Get the output format type this serializer produces."""
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Get the file extension for output files (without dot)."""
        pass

    @property
    @abstractmethod
    def is_multi_file(self) -> bool:
        """Check if this format produces multiple output files."""
        pass

    @abstractmethod
    def serialize(self, data: dict) -> Iterator[SerializedOutput]:
        """
        Serialize extracted data to output format.

        Args:
            data: Extracted data dictionary

        Yields:
            SerializedOutput for each generated file
        """
        pass

    def get_warnings(self, data: dict) -> list[DataLossWarning]:
        """
        Check for potential data loss before serialization.

        Args:
            data: Extracted data dictionary

        Returns:
            List of data loss warnings
        """
        return []

    def _generate_filename(
        self,
        base_name: str,
        suffix: str = "",
        extension: Optional[str] = None
    ) -> str:
        """
        Generate output filename.

        Args:
            base_name: Base name (typically instrument model)
            suffix: Optional suffix
            extension: File extension (defaults to format extension)

        Returns:
            Complete filename with extension
        """
        ext = extension or self.file_extension
        return f"{base_name}{suffix}.{ext}"

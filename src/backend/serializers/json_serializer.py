"""
JSON serializer for extracted data.

Simple serializer that outputs extracted data as formatted JSON.
"""

import json
from typing import Iterator

from .base import FormatSerializer, OutputFormat, SerializedOutput, SerializerConfig
from .factory import SerializerFactory


@SerializerFactory.register(OutputFormat.JSON)
class JSONSerializer(FormatSerializer):
    """Serializer that outputs extracted data as JSON."""

    @property
    def format_type(self) -> OutputFormat:
        return OutputFormat.JSON

    @property
    def file_extension(self) -> str:
        return "json"

    @property
    def is_multi_file(self) -> bool:
        return False

    def serialize(self, data: dict) -> Iterator[SerializedOutput]:
        """
        Serialize extracted data to JSON format.

        Args:
            data: Extracted data dictionary

        Yields:
            Single SerializedOutput containing JSON content
        """
        filename = self._generate_filename(self.config.instrument_name)
        content = json.dumps(data, indent=2, ensure_ascii=False, default=str)

        yield SerializedOutput(
            filename=filename,
            content=content,
            format=self.format_type,
            metadata={
                "instrument_name": self.config.instrument_name,
                "record_count": len(data.get("tables", [])) if isinstance(data, dict) else 0
            }
        )

"""
Format Serializers for Document Processing.

This package provides pluggable serializers for converting extracted data
to various output formats.

Usage:
    from backend.serializers import SerializerFactory, OutputFormat

    config = SerializerConfig(output_dir=Path("output"), instrument_name="doc")
    serializer = SerializerFactory.create(OutputFormat.JSON, config)

    for output in serializer.serialize(extracted_data):
        output.write_to_path(config.output_dir)
"""

from .base import (
    OutputFormat,
    SerializerConfig,
    SerializedOutput,
    DataLossWarning,
    FormatSerializer,
)
from .factory import SerializerFactory

# Import serializers to trigger registration via decorators
from . import json_serializer  # noqa: F401

__all__ = [
    "OutputFormat",
    "SerializerConfig",
    "SerializedOutput",
    "DataLossWarning",
    "FormatSerializer",
    "SerializerFactory",
]

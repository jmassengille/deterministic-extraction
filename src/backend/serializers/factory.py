"""
Serializer Factory with decorator-based registration.

This module provides a factory for creating format serializers.
Serializers register themselves using the @SerializerFactory.register decorator.

Usage:
    from backend.serializers import SerializerFactory, OutputFormat

    # Serializers auto-register on import
    from backend.serializers import acc_serializer, msf_serializer

    # Create a serializer
    serializer = SerializerFactory.create(OutputFormat.ACC, config)

Extension:
    To add a new format, create a new serializer class decorated with:

    @SerializerFactory.register(OutputFormat.NEW_FORMAT)
    class NewFormatSerializer(FormatSerializer):
        ...
"""

from typing import Type

from .base import FormatSerializer, OutputFormat, SerializerConfig


class SerializerFactory:
    """
    Factory for creating format serializers.

    Uses decorator-based registration to allow pluggable format support.
    No changes needed to factory when adding new formats.
    """

    _registry: dict[OutputFormat, Type[FormatSerializer]] = {}

    @classmethod
    def register(cls, format_type: OutputFormat):
        """
        Decorator to register a serializer class for a format.

        Usage:
            @SerializerFactory.register(OutputFormat.ACC)
            class ACCSerializer(FormatSerializer):
                ...

        Args:
            format_type: The output format this serializer handles

        Returns:
            Decorator function
        """
        def decorator(serializer_class: Type[FormatSerializer]) -> Type[FormatSerializer]:
            if format_type in cls._registry:
                existing = cls._registry[format_type].__name__
                raise ValueError(
                    f"Format {format_type.value} already registered by {existing}"
                )
            cls._registry[format_type] = serializer_class
            return serializer_class
        return decorator

    @classmethod
    def create(
        cls,
        format_type: OutputFormat,
        config: SerializerConfig
    ) -> FormatSerializer:
        """
        Create a serializer for the specified format.

        Args:
            format_type: The output format to serialize to
            config: Configuration for the serializer

        Returns:
            Configured serializer instance

        Raises:
            ValueError: If format is not registered
        """
        if format_type not in cls._registry:
            available = [f.value for f in cls._registry.keys()]
            raise ValueError(
                f"Unknown format: {format_type.value}. "
                f"Available: {available}"
            )
        return cls._registry[format_type](config)

    @classmethod
    def get_available_formats(cls) -> list[OutputFormat]:
        """Get list of registered output formats."""
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, format_type: OutputFormat) -> bool:
        """Check if a format has a registered serializer."""
        return format_type in cls._registry

    @classmethod
    def clear_registry(cls) -> None:
        """
        Clear all registered serializers.

        Primarily for testing purposes.
        """
        cls._registry.clear()

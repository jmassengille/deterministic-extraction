"""Schema loader for OpenAI function calling definitions."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class SchemaLoader:
    """Load and manage function calling schemas from YAML files."""

    def __init__(self, schemas_dir: Optional[Path] = None):
        """
        Initialize schema loader.

        Args:
            schemas_dir: Directory containing schema files.
                        Defaults to src/backend/config/schemas/
        """
        if schemas_dir is None:
            self.schemas_dir = Path(__file__).parent
        else:
            self.schemas_dir = Path(schemas_dir)

        if not self.schemas_dir.exists():
            raise FileNotFoundError(f"Schemas directory not found: {self.schemas_dir}")

        self._cache = {}
        logger.info(f"SchemaLoader initialized with directory: {self.schemas_dir}")

    def load_schema(self, schema_name: str) -> Dict[str, Any]:
        """
        Load a function calling schema from YAML file.

        Args:
            schema_name: Name of the schema file (without .yaml extension)

        Returns:
            Dictionary containing function schema with keys:
            - type: "function"
            - name: function name
            - description: function description
            - strict: bool for strict mode
            - parameters: JSON schema for parameters
        """
        if schema_name in self._cache:
            return self._cache[schema_name]

        schema_file = self.schemas_dir / f"{schema_name}.yaml"

        if not schema_file.exists():
            schema_file = self.schemas_dir / f"{schema_name}.yml"

        if not schema_file.exists():
            available = self.list_available_schemas()
            raise FileNotFoundError(
                f"Schema '{schema_name}' not found. Available: {available}"
            )

        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_config = yaml.safe_load(f)

        required_fields = ['type', 'name', 'parameters']
        for field in required_fields:
            if field not in schema_config:
                raise ValueError(f"Schema file missing required field: {field}")

        if schema_config.get('type') != 'function':
            raise ValueError(f"Schema type must be 'function', got: {schema_config.get('type')}")

        self._cache[schema_name] = schema_config
        logger.info(f"Loaded schema: {schema_name} (function: {schema_config['name']})")

        return schema_config

    def list_available_schemas(self) -> List[str]:
        """
        List all available schema files.

        Returns:
            List of schema names (without extensions)
        """
        schemas = []

        for file in self.schemas_dir.glob("*.yaml"):
            schemas.append(file.stem)

        for file in self.schemas_dir.glob("*.yml"):
            if file.stem not in schemas:
                schemas.append(file.stem)

        return sorted(schemas)

    def validate_schema(self, schema_config: Dict[str, Any]) -> bool:
        """
        Validate schema structure for OpenAI function calling.

        Args:
            schema_config: Schema configuration to validate

        Returns:
            True if valid

        Raises:
            ValueError: If schema is invalid
        """
        if 'parameters' not in schema_config:
            raise ValueError("Schema missing 'parameters' field")

        params = schema_config['parameters']

        if params.get('type') != 'object':
            raise ValueError("Schema parameters must be of type 'object'")

        if 'properties' not in params:
            raise ValueError("Schema parameters missing 'properties'")

        if schema_config.get('strict') and 'additionalProperties' not in params:
            raise ValueError("Strict schemas must specify 'additionalProperties'")

        return True


def load_schema(name: str) -> Dict[str, Any]:
    """
    Quick loader for schema configurations.

    Args:
        name: Schema name

    Returns:
        Schema configuration dictionary
    """
    loader = SchemaLoader()
    return loader.load_schema(name)

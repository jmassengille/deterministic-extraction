"""
Prompt loader utility for managing LLM prompts.
Allows easy switching between different prompt versions for testing.

Supports format-specific subdirectories:
    prompts/
    ├── default/           # Default prompts
    │   └── extraction.yaml
    ├── {domain}/          # Domain-specific prompts
    │   └── extraction.yaml
    └── universal.yaml     # Shared prompts
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from backend.config.settings import DEFAULT_PROMPT_VERSION

logger = logging.getLogger(__name__)


class PromptLoader:
    """Load and manage LLM prompts from YAML files.

    Supports format-aware prompt loading from subdirectories.
    """

    def __init__(
        self,
        prompts_dir: Optional[Path] = None,
        output_format: Optional[str] = None
    ):
        """
        Initialize prompt loader.

        Args:
            prompts_dir: Directory containing prompt files.
                        Defaults to src/backend/config/prompts/
            output_format: Target output format ('msf', 'acc', or None for root).
                          When specified, prompts are loaded from format subdir.
        """
        if prompts_dir is None:
            self.prompts_dir = Path(__file__).parent
        else:
            self.prompts_dir = Path(prompts_dir)

        if not self.prompts_dir.exists():
            raise FileNotFoundError(f"Prompts directory not found: {self.prompts_dir}")

        self.output_format = output_format
        self._cache = {}
        self._mappings = self._load_instrument_mappings()

    @property
    def effective_prompts_dir(self) -> Path:
        """Get the effective prompts directory based on output format."""
        if self.output_format:
            format_dir = self.prompts_dir / self.output_format
            if format_dir.exists():
                return format_dir
            logger.warning(
                f"Format directory '{self.output_format}' not found, "
                f"falling back to root prompts"
            )
        return self.prompts_dir
    
    def load_prompt(self, prompt_name: str = DEFAULT_PROMPT_VERSION) -> Dict[str, Any]:
        """
        Load a prompt configuration from YAML file.

        When output_format is set, looks in format subdirectory first,
        then falls back to root prompts directory.

        Args:
            prompt_name: Name of the prompt file (without .yaml extension)
                        Defaults to DEFAULT_PROMPT_VERSION from config

        Returns:
            Dictionary containing prompt configuration with keys:
            - system_prompt: System message for LLM
            - user_prompt_template: User message template
            - metadata: Version info and notes
        """
        # Include format in cache key to avoid cross-format contamination
        cache_key = f"{self.output_format or 'root'}:{prompt_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try format-specific directory first
        prompt_file = self.effective_prompts_dir / f"{prompt_name}.yaml"

        if not prompt_file.exists():
            # Fallback to .yml extension
            prompt_file = self.effective_prompts_dir / f"{prompt_name}.yml"

        # If not in format dir, try root prompts dir
        if not prompt_file.exists() and self.output_format:
            prompt_file = self.prompts_dir / f"{prompt_name}.yaml"
            if not prompt_file.exists():
                prompt_file = self.prompts_dir / f"{prompt_name}.yml"

        if not prompt_file.exists():
            available = self.list_available_prompts()
            raise FileNotFoundError(
                f"Prompt '{prompt_name}' not found in format '{self.output_format}'. "
                f"Available: {available}"
            )
        
        # Parse YAML configuration
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_config = yaml.safe_load(f)
        
        # Check mandatory configuration fields
        required_fields = ['system_prompt', 'user_prompt_template']
        for field in required_fields:
            if field not in prompt_config:
                raise ValueError(f"Prompt file missing required field: {field}")

        # Store in cache and return
        self._cache[cache_key] = prompt_config
        
        # Log version information
        if 'metadata' in prompt_config:
            meta = prompt_config['metadata']
            logger.info(f"Loaded prompt: {prompt_name} v{meta.get('version', 'unknown')}")
            if 'notes' in meta:
                logger.debug(f"Prompt notes: {meta['notes']}")
        
        return prompt_config
    
    def _load_instrument_mappings(self) -> Dict[str, Any]:
        """Load instrument type to prompt mappings."""
        mapping_file = self.prompts_dir.parent / "instrument_mappings.yaml"
        if mapping_file.exists():
            with open(mapping_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {"category_mappings": {"default": DEFAULT_PROMPT_VERSION}}
    
    def select_prompt_for_instrument(
        self,
        instrument_type: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Select appropriate prompt based on instrument category.

        Args:
            instrument_type: Type/category of instrument (DMM, Calibrator, etc.)
            model: Model number (not used - we don't hardcode models)

        Returns:
            Prompt name to use
        """
        # Only use instrument type/category, NOT specific models
        # The system must be universal for all manufacturers

        # Check instrument category mappings
        if instrument_type and "category_mappings" in self._mappings:
            type_lower = instrument_type.lower().strip()

            # 1. Try exact match first
            if type_lower in self._mappings["category_mappings"]:
                prompt = self._mappings["category_mappings"][type_lower]
                logger.info(f"Using exact match prompt: {prompt} for {instrument_type}")
                return prompt

            # 2. Try keyword matching for complex descriptions
            for mapping_key, prompt in self._mappings["category_mappings"].items():
                if mapping_key in ['default', 'unknown']:
                    continue
                # Check if mapping key is contained in detected type
                if mapping_key in type_lower:
                    logger.info(f"Using keyword match prompt: {prompt} for {instrument_type} (matched: {mapping_key})")
                    return prompt

        # Default fallback
        default = self._mappings.get("category_mappings", {}).get("default", DEFAULT_PROMPT_VERSION)
        logger.info(f"Using default prompt: {default}")
        return default
    
    def list_available_prompts(self) -> list:
        """
        List all available prompt files.

        When output_format is set, lists prompts from both
        the format directory and root (for fallback).

        Returns:
            List of prompt names (without extensions)
        """
        prompts = set()

        # Scan format-specific directory
        for file in self.effective_prompts_dir.glob("*.yaml"):
            prompts.add(file.stem)
        for file in self.effective_prompts_dir.glob("*.yml"):
            prompts.add(file.stem)

        # Also include root prompts for fallback
        if self.output_format:
            for file in self.prompts_dir.glob("*.yaml"):
                prompts.add(file.stem)
            for file in self.prompts_dir.glob("*.yml"):
                prompts.add(file.stem)

        return sorted(prompts)
    
    def format_user_prompt(
        self,
        prompt_name: str,
        table_content: str,
        context: Optional[str] = None,
        instrument_type: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Format the user prompt template with provided data.

        Args:
            prompt_name: Name of prompt to use
            table_content: Table content (text or vision instruction)
            context: Optional context string
            instrument_type: Optional instrument type
            **kwargs: Additional template variables

        Returns:
            Formatted user prompt string
        """
        prompt_config = self.load_prompt(prompt_name)
        template = prompt_config['user_prompt_template']

        # Prepare template substitution variables
        template_vars = {
            'table_content': table_content,
            'context': context or 'an instrument',
            'instrument_type': instrument_type or 'instrument',
            **kwargs
        }

        # Apply variable substitutions
        return template.format(**template_vars)
    
    def get_system_prompt(self, prompt_name: str = DEFAULT_PROMPT_VERSION) -> str:
        """
        Get the system prompt for a given prompt configuration.
        
        Args:
            prompt_name: Name of prompt to use
        
        Returns:
            System prompt string
        """
        prompt_config = self.load_prompt(prompt_name)
        return prompt_config['system_prompt']
    
    def get_metadata(self, prompt_name: str) -> Dict[str, Any]:
        """
        Get metadata for a prompt configuration.
        
        Args:
            prompt_name: Name of prompt
        
        Returns:
            Metadata dictionary or empty dict if no metadata
        """
        prompt_config = self.load_prompt(prompt_name)
        return prompt_config.get('metadata', {})


# Convenience function for quick access
def load_prompt(
    name: str = DEFAULT_PROMPT_VERSION,
    output_format: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick loader for prompt configurations.

    Args:
        name: Prompt name (defaults to latest version)
        output_format: Target format ('msf', 'acc', or None for root)

    Returns:
        Prompt configuration dictionary
    """
    loader = PromptLoader(output_format=output_format)
    return loader.load_prompt(name)
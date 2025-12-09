"""Backend configuration settings.

Domain-agnostic document processing configuration. All domain-specific
settings (schemas, prompts) are loaded from external config files.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / "./../.env"
if env_path.exists():
    load_dotenv(env_path)

# =============================================================================
# LLM Configuration
# =============================================================================

DEFAULT_PROMPT_VERSION = os.getenv("PROMPT_VERSION", "universal")
LLM_MODEL_ASYNC = os.getenv("LLM_MODEL_ASYNC", "main")  # mini, main, or nano
LLM_MODEL_SPEC_EXTRACTION = os.getenv("LLM_MODEL_EXTRACTION", "main")

# Extraction Mode: "single" (reliable, uses structured output) or "multi" (3-pass experimental)
EXTRACTION_MODE = os.getenv("EXTRACTION_MODE", "single")

# Extraction schema - defines the function calling schema for data extraction
# Configure via environment variable for different domains
EXTRACTION_SCHEMA = os.getenv("EXTRACTION_SCHEMA", "extraction")

# OpenAI API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# GPT-5 Model Configuration (using new Responses API)
# GPT-5.1 is the new flagship - better for coding/agentic tasks
GPT5_MODEL_MAIN = "gpt-5.1"  # Upgraded from gpt-5
GPT5_MODEL_MINI = "gpt-5-mini"
GPT5_MODEL_NANO = "gpt-5-nano"
GPT5_TIMEOUT_S = 600  # Increased from 360 for large table extraction

# Function Calling Configuration
FUNCTION_CALLING_ENABLED = True
FUNCTION_STRICT_MODE = True

# LLM Behavior Settings
LLM_MAX_RETRIES = 3
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "high")
LLM_VERBOSITY = os.getenv("LLM_VERBOSITY", "medium")
# Max output tokens to prevent truncation on large extraction results
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "32768"))

# Processing Configuration
MAX_CONCURRENT_LLM_CALLS = 5
DEFAULT_TIMEOUT_SECONDS = 120

# Output Configuration
DEFAULT_OUTPUT_DIR = "Data/artifacts"
TEMP_OUTPUT_DIR = "Data/temp"

# =============================================================================
# Output Configuration
# =============================================================================

# Default output format when not specified
# Note: Format should generally be explicitly specified at upload time
DEFAULT_OUTPUT_FORMAT = os.getenv("DEFAULT_OUTPUT_FORMAT", "json")

# Prompt directory for domain-specific prompts
# Configure via environment for different domains (e.g., "invoice", "contract")
PROMPT_DIRECTORY = os.getenv("PROMPT_DIRECTORY", "default")

# Data loss warning configuration
WARN_ON_DATA_LOSS = True  # Show warnings when data will be lost in conversion
BLOCK_ON_DATA_LOSS = False  # Don't block conversion, just warn

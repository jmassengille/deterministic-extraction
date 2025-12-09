"""Modern LLM client using GPT-5 Responses API with function calling.

Domain-agnostic extraction client. Schema and function names are parameterized
to support any extraction domain (invoices, contracts, specifications, etc.).
"""

import base64
import json
import logging
from typing import Any, Dict, Optional

from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..config.settings import (
    OPENAI_API_KEY,
    GPT5_MODEL_MAIN,
    GPT5_MODEL_MINI,
    GPT5_MODEL_NANO,
    GPT5_TIMEOUT_S,
    LLM_MAX_RETRIES,
    LLM_MAX_OUTPUT_TOKENS,
    LLM_REASONING_EFFORT,
    LLM_VERBOSITY,
    FUNCTION_CALLING_ENABLED,
    EXTRACTION_SCHEMA,
)
from ..config.schemas.schema_loader import SchemaLoader

logger = logging.getLogger(__name__)


class GPT5Client:
    """Async GPT-5 client using Responses API with function calling.

    Domain-agnostic: schemas are loaded dynamically based on configuration.
    """

    def __init__(self, extraction_schema: Optional[str] = None):
        """Initialize the GPT-5 client with function calling support.

        Args:
            extraction_schema: Schema name for data extraction. Defaults to
                              EXTRACTION_SCHEMA from settings.
        """
        self.client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            timeout=GPT5_TIMEOUT_S
        )

        self.models = {
            "main": GPT5_MODEL_MAIN,
            "mini": GPT5_MODEL_MINI,
            "nano": GPT5_MODEL_NANO
        }

        # Load function calling schemas from YAML - dynamically configured
        self.schema_loader = SchemaLoader()
        self.extraction_schema_name = extraction_schema or EXTRACTION_SCHEMA
        self._schema_cache: Dict[str, Any] = {}

        # Pre-load common schemas
        self._load_schema('toc_analysis')
        self._load_schema(self.extraction_schema_name)

        logger.info(f"GPT-5 client initialized with extraction schema: {self.extraction_schema_name}")

    def _load_schema(self, schema_name: str) -> Dict[str, Any]:
        """Load and cache a schema by name.

        Args:
            schema_name: Name of the schema file (without .yaml)

        Returns:
            Loaded schema dictionary
        """
        if schema_name not in self._schema_cache:
            self._schema_cache[schema_name] = self.schema_loader.load_schema(schema_name)
        return self._schema_cache[schema_name]

    def get_schema(self, schema_name: str) -> Dict[str, Any]:
        """Get a schema by name, loading if necessary.

        Args:
            schema_name: Name of the schema

        Returns:
            Schema dictionary
        """
        return self._load_schema(schema_name)

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        stop=stop_after_attempt(LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=1, max=10)
    )
    async def extract_structured_data(
        self,
        input_text: str,
        schema_name: Optional[str] = None,
        model: str = "mini",
        system_message: Optional[str] = None,
        reasoning_effort: str = LLM_REASONING_EFFORT,
        verbosity: str = LLM_VERBOSITY
    ) -> Dict[str, Any]:
        """
        Extract structured data using function calling with configurable schema.

        Args:
            input_text: The input prompt with document data
            schema_name: Schema to use for extraction. Defaults to configured extraction schema.
            model: Model variant (main, mini, nano)
            system_message: Optional system message
            reasoning_effort: Reasoning level (minimal, low, medium, high)
            verbosity: Response verbosity (low, medium, high)

        Returns:
            Extracted data as dictionary
        """
        try:
            model_name = self.models.get(model, GPT5_MODEL_MINI)
            schema_name = schema_name or self.extraction_schema_name
            schema = self._load_schema(schema_name)
            function_name = schema["name"]

            # Combine system and user prompts
            full_input = input_text
            if system_message:
                full_input = f"{system_message}\n\n{input_text}"

            logger.debug(f"Calling GPT-5 {model_name} with schema={schema_name}, reasoning={reasoning_effort}")

            # Make API call with function calling
            response = await self.client.responses.create(
                model=model_name,
                input=full_input,
                tools=[schema],
                tool_choice={
                    "type": "function",
                    "name": function_name
                },
                reasoning={"effort": reasoning_effort},
                text={"verbosity": verbosity},
                max_output_tokens=LLM_MAX_OUTPUT_TOKENS
            )

            # Extract the function call result from response
            for item in response.output:
                if hasattr(item, 'type') and item.type == "function_call":
                    if hasattr(item, 'name') and item.name == function_name:
                        arguments = item.arguments
                        if isinstance(arguments, str):
                            result = json.loads(arguments)
                        else:
                            logger.error(f"Unexpected arguments type: {type(arguments)}, value: {arguments}")
                            raise TypeError(f"Expected string arguments, got {type(arguments)}")
                        logger.debug(f"Successfully extracted data using schema {schema_name}")
                        return result

            # Fallback if no function call found
            logger.warning(f"No function call found in response for schema {schema_name}")
            return {
                "extraction_notes": ["No function call in response"],
                "metadata": None
            }

        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            logger.warning(f"Retryable error (will retry): {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(
                f"GPT-5 extraction failed: {type(e).__name__}: {e}",
                exc_info=True,
                extra={"model": self.models.get(model, GPT5_MODEL_MINI), "schema": schema_name}
            )
            raise

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        stop=stop_after_attempt(LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=1, max=10)
    )
    async def extract_structured_data_from_image(
        self,
        image_bytes: bytes,
        prompt_text: str,
        schema_name: Optional[str] = None,
        model: str = "mini",
        reasoning_effort: str = LLM_REASONING_EFFORT,
        verbosity: str = LLM_VERBOSITY
    ) -> Dict[str, Any]:
        """
        Extract structured data from image using vision with configurable schema.

        Args:
            image_bytes: PNG image bytes of the document region
            prompt_text: Prompt text with context and instructions
            schema_name: Schema to use for extraction. Defaults to configured extraction schema.
            model: Model variant (main, mini, nano)
            reasoning_effort: Reasoning level (minimal, low, medium, high)
            verbosity: Response verbosity (low, medium, high)

        Returns:
            Extracted data as dictionary
        """
        try:
            model_name = self.models.get(model, GPT5_MODEL_MINI)
            schema_name = schema_name or self.extraction_schema_name
            schema = self._load_schema(schema_name)
            function_name = schema["name"]

            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:image/png;base64,{image_b64}"

            content = [
                {
                    "type": "input_text",
                    "text": prompt_text
                },
                {
                    "type": "input_image",
                    "image_url": image_url
                }
            ]

            logger.debug(f"Calling GPT-5 {model_name} with vision + schema={schema_name}, reasoning={reasoning_effort}")

            response = await self.client.responses.create(
                model=model_name,
                input=[{"role": "user", "content": content}],
                tools=[schema],
                tool_choice={
                    "type": "function",
                    "name": function_name
                },
                reasoning={"effort": reasoning_effort},
                text={"verbosity": verbosity},
                max_output_tokens=LLM_MAX_OUTPUT_TOKENS
            )

            for item in response.output:
                if hasattr(item, 'type') and item.type == "function_call":
                    if hasattr(item, 'name') and item.name == function_name:
                        arguments = item.arguments
                        if isinstance(arguments, str):
                            result = json.loads(arguments)
                        else:
                            logger.error(f"Vision: Unexpected arguments type: {type(arguments)}")
                            raise TypeError(f"Expected string arguments, got {type(arguments)}")
                        logger.debug(f"Successfully extracted data from image using schema {schema_name}")
                        return result

            logger.warning(f"No function call found in vision response for schema {schema_name}")
            return {
                "extraction_notes": ["No function call in vision response"],
                "metadata": None
            }

        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            logger.warning(f"Retryable error in vision extraction: {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"Vision extraction failed: {type(e).__name__}: {e}")
            raise

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        stop=stop_after_attempt(LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=1, max=10)
    )
    async def analyze_toc(
        self,
        input_text: str,
        model: str = "main",
        reasoning_effort: str = "low",
        verbosity: str = "low"
    ) -> Dict[str, Any]:
        """
        Analyze table of contents using function calling.

        Args:
            input_text: The input prompt with TOC and metadata
            model: Model variant (main, mini, nano)
            reasoning_effort: Reasoning level (minimal, low, medium, high)
            verbosity: Response verbosity (low, medium, high)

        Returns:
            Dictionary with manufacturer, model, instrument_type, spec_pages, confidence
        """
        try:
            model_name = self.models.get(model, GPT5_MODEL_MAIN)

            logger.debug(f"Calling GPT-5 {model_name} for TOC analysis with function calling")

            # Make API call with function calling
            response = await self.client.responses.create(
                model=model_name,
                input=input_text,
                tools=[self.schemas['toc_analysis']],
                tool_choice={
                    "type": "function",
                    "name": "analyze_toc"
                },
                reasoning={"effort": reasoning_effort},
                text={"verbosity": verbosity},
                max_output_tokens=LLM_MAX_OUTPUT_TOKENS
            )

            # Extract the function call result from response
            for item in response.output:
                if hasattr(item, 'type') and item.type == "function_call":
                    if hasattr(item, 'name') and item.name == "analyze_toc":
                        arguments = item.arguments
                        if isinstance(arguments, str):
                            result = json.loads(arguments)
                        else:
                            logger.error(f"TOC: Unexpected arguments type: {type(arguments)}")
                            raise TypeError(f"Expected string arguments, got {type(arguments)}")
                        logger.debug(f"TOC analysis found {len(result.get('spec_pages', []))} page ranges")
                        return result

            # Fallback if no function call found
            logger.warning("No function call found in TOC analysis response")
            return {
                "manufacturer": "Unknown",
                "model": "Unknown",
                "instrument_type": "Unknown",
                "spec_pages": [],
                "confidence": 0.0
            }

        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            logger.warning(f"Retryable error in TOC analysis (will retry): {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(
                f"TOC analysis API call failed: {type(e).__name__}: {e}",
                exc_info=True,
                extra={"model": self.models.get(model, GPT5_MODEL_MAIN)}
            )
            raise

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        stop=stop_after_attempt(LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=1, max=10)
    )
    async def generate_response(
        self,
        input_text: str,
        model: str = "mini",
        system_message: Optional[str] = None,
        reasoning_effort: str = LLM_REASONING_EFFORT,
        verbosity: str = LLM_VERBOSITY,
        **kwargs
    ) -> str:
        """
        Generate response using GPT-5 Responses API (non-function calling).
        Kept for backward compatibility.

        Args:
            input_text: The input prompt
            model: Model variant (main, mini, nano)
            system_message: Optional system message
            reasoning_effort: Reasoning level (minimal, low, medium, high)
            verbosity: Response verbosity (low, medium, high)
            **kwargs: Additional parameters

        Returns:
            Generated response text
        """
        # Long function justification: Combines request building, API call,
        # and response format handling in single cohesive flow for Responses API.
        # Splitting would create artificial boundaries in atomic API interaction.

        try:
            model_name = self.models.get(model, GPT5_MODEL_MINI)

            final_input = input_text
            if system_message:
                final_input = f"{system_message}\n\n{input_text}"

            request_data = {
                "model": model_name,
                "input": final_input,
                "reasoning": {"effort": reasoning_effort},
                "text": {"verbosity": verbosity},
                "max_output_tokens": LLM_MAX_OUTPUT_TOKENS
            }

            request_data.update(kwargs)

            logger.debug(f"Calling GPT-5 {model_name} with reasoning={reasoning_effort}, verbosity={verbosity}")

            response = await self.client.responses.create(**request_data)

            # Handle both possible response formats
            if hasattr(response, 'output_text'):
                output_text = response.output_text
            elif hasattr(response, 'output') and response.output:
                # If output is an array, look for text content
                for item in response.output:
                    if hasattr(item, 'type') and item.type == "text":
                        output_text = item.content
                        break
                else:
                    output_text = str(response.output)
            else:
                output_text = str(response)

            logger.debug(f"GPT-5 response length: {len(output_text)} chars")
            return output_text

        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            logger.warning(f"Retryable error: {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"GPT-5 API call failed: {type(e).__name__}: {e}")
            raise

    async def extract_json_response(
        self,
        input_text: str,
        schema_name: Optional[str] = None,
        model: str = "mini",
        system_message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate JSON response for structured extraction.
        Uses function calling with configurable schema when enabled.

        Args:
            input_text: The input prompt
            schema_name: Schema to use. Defaults to configured extraction schema.
            model: Model variant (main, mini, nano)
            system_message: Optional system message
            **kwargs: Additional parameters

        Returns:
            Parsed JSON response
        """
        # Use function calling for extraction when enabled
        if FUNCTION_CALLING_ENABLED:
            return await self.extract_structured_data(
                input_text=input_text,
                schema_name=schema_name,
                model=model,
                system_message=system_message,
                reasoning_effort=kwargs.get('reasoning_effort', LLM_REASONING_EFFORT),
                verbosity=kwargs.get('verbosity', LLM_VERBOSITY)
            )

        # Fallback to text-based extraction (deprecated path)
        response_text = await self.generate_response(
            input_text=input_text,
            model=model,
            system_message=system_message,
            reasoning_effort=kwargs.pop('reasoning_effort', LLM_REASONING_EFFORT),
            verbosity=kwargs.pop('verbosity', LLM_VERBOSITY),
            **kwargs
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response_text[:500]}...")
            raise


# Global client instance
_client = None

async def get_client() -> GPT5Client:
    """Get or create the global GPT-5 client instance."""
    global _client
    if _client is None:
        _client = GPT5Client()
    return _client


# Backward compatibility functions
async def call_main_json_async(system_prompt: str, user_prompt: str) -> str:
    """Call GPT-5 main model for JSON extraction."""
    client = await get_client()
    result = await client.extract_json_response(
        input_text=user_prompt,
        model="main",
        system_message=system_prompt
    )
    return json.dumps(result)


async def call_mini_json_async(system_prompt: str, user_prompt: str) -> str:
    """Call GPT-5 mini model for JSON extraction."""
    client = await get_client()
    result = await client.extract_json_response(
        input_text=user_prompt,
        model="mini",
        system_message=system_prompt
    )
    return json.dumps(result)


async def call_nano_json_async(system_prompt: str, user_prompt: str) -> str:
    """Call GPT-5 nano model for JSON extraction."""
    client = await get_client()
    result = await client.extract_json_response(
        input_text=user_prompt,
        model="nano",
        system_message=system_prompt
    )
    return json.dumps(result)
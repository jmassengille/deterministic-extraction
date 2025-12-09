"""Multi-pass extraction pipeline for improved document table accuracy.

Architecture:
- Pass 0: Triage + Structure - Classify table type and analyze layout (gpt-5-mini, medium reasoning)
- Pass 1: Raw - Verbatim transcription (gpt-5-mini, low reasoning)
- Pass 2: Normalize - Apply domain rules (gpt-5-mini, high reasoning)

This 3-pass approach merges triage and structure into a single vision pass,
improving efficiency while maintaining accuracy.

Pass 0 uses medium reasoning because it's the gatekeeper - wrong decisions skip tables entirely.
Pass 2 uses high reasoning for complex normalization.
"""

import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import aiofiles
import yaml

from ..config.settings import GPT5_MODEL_NANO, GPT5_MODEL_MINI, LLM_MAX_OUTPUT_TOKENS
from ..config.schemas.schema_loader import SchemaLoader
from ..core.models import TableSpec

from .client import get_client

logger = logging.getLogger(__name__)


@dataclass
class PassConfig:
    """Configuration for a single extraction pass."""

    name: str
    model: str
    reasoning_effort: str
    verbosity: str
    schema_name: str
    prompt_file: str


# Document-type to prompt file mapping for normalization pass
# Maps keywords in document_type to specialized extraction prompts
# Load from config/instrument_mappings.yaml for domain-specific deployments
DEFAULT_PROMPT_MAP = {
    "default": "extraction.yaml",
}

# Pass configurations - optimized for accuracy and cost (3-pass system)
# NOTE: Originally 4 passes (0=triage, 1=structure, 2=raw, 3=normalize).
# Pass 0+1 merged into single triage_structure pass. Schema/prompt files
# retain original numbering (pass2_raw, pass3_normalize) for compatibility.
PASS_CONFIGS = {
    "pass0": PassConfig(
        name="triage_structure",
        model="mini",  # Upgraded from nano - gatekeeper needs accuracy
        reasoning_effort="medium",  # Critical: determines skip/process decision
        verbosity="low",
        schema_name="pass0_triage_structure",
        prompt_file="pass0_triage_structure.yaml",
    ),
    "pass1": PassConfig(
        name="raw",
        model="mini",  # Upgraded from nano - nano can't extract table cell data
        reasoning_effort="low",
        verbosity="low",
        schema_name="pass2_raw",
        prompt_file="pass2_raw.yaml",
    ),
    "pass2": PassConfig(
        name="normalize",
        model="mini",
        reasoning_effort="high",  # High reasoning for complex normalization
        verbosity="low",
        schema_name="extraction",  # Uses configured extraction schema
        prompt_file="pass3_normalize.yaml",
    ),
}


class MultiPassExtractor:
    """Multi-pass extraction pipeline for document tables.

    Improves accuracy by separating concerns:
    1. Visual parsing (Pass 0-1) uses smaller models for triage/structure/transcription
    2. Domain logic (Pass 2) uses larger model with text-only input
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
        debug_dir: Optional[Path] = None,
    ):
        """
        Initialize multi-pass extractor.

        Args:
            max_concurrent: Maximum concurrent table extractions
            progress_callback: Callback(pass_name, current, total, message)
            debug_dir: Directory for debug output (auto-created if None)
        """
        self.max_concurrent = min(max_concurrent, 5)
        self.progress_callback = progress_callback
        self._client = None

        # Load schemas
        self.schema_loader = SchemaLoader()
        self.schemas = {}
        for pass_id, config in PASS_CONFIGS.items():
            try:
                self.schemas[pass_id] = self.schema_loader.load_schema(
                    config.schema_name
                )
            except FileNotFoundError:
                logger.warning(f"Schema not found for {pass_id}: {config.schema_name}")

        # Load base prompts (extraction passes)
        self.prompts = {}
        prompts_dir = Path(__file__).parent.parent / "config/prompts/extraction"
        for pass_id, config in PASS_CONFIGS.items():
            prompt_path = prompts_dir / config.prompt_file
            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    self.prompts[pass_id] = yaml.safe_load(f)
            else:
                logger.warning(f"Prompt file not found: {prompt_path}")

        # Load domain-specific prompts (for normalization pass)
        # These are loaded from config/prompts/default or domain-specific directories
        self.domain_prompts: Dict[str, Dict[str, Any]] = {}
        from ..config.settings import PROMPT_DIRECTORY
        domain_prompts_dir = Path(__file__).parent.parent / f"config/prompts/{PROMPT_DIRECTORY}"
        if domain_prompts_dir.exists():
            for prompt_file in domain_prompts_dir.glob("*.yaml"):
                with open(prompt_file, "r", encoding="utf-8") as f:
                    self.domain_prompts[prompt_file.name] = yaml.safe_load(f)
                logger.debug(f"Loaded domain prompt: {prompt_file.name}")
        # Also load universal.yaml as fallback
        universal_path = domain_prompts_dir / "universal.yaml"
        if universal_path.exists():
            with open(universal_path, "r", encoding="utf-8") as f:
                self.domain_prompts["universal.yaml"] = yaml.safe_load(f)
            logger.debug("Loaded universal domain prompt as fallback")

        # Debug directory
        if debug_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.debug_dir = Path("Data") / "multipass_debug" / timestamp
        else:
            self.debug_dir = debug_dir
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"MultiPassExtractor initialized: {self.max_concurrent} workers, "
            f"debug_dir={self.debug_dir}"
        )

    async def _get_client(self):
        """Get or create the GPT-5 client."""
        if self._client is None:
            self._client = await get_client()
        return self._client

    def _report_progress(
        self, pass_name: str, current: int, total: int, message: str
    ) -> None:
        """Report progress to callback if registered."""
        if self.progress_callback:
            try:
                self.progress_callback(pass_name, current, total, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
        logger.info(f"[{pass_name}] {current}/{total}: {message}")

    def _get_instrument_rules(self, instrument_type: str) -> str:
        """
        Get instrument-specific extraction rules to merge with normalization prompt.

        Uses INSTRUMENT_PROMPT_MAP to find the appropriate prompt file based on
        keywords in the instrument_type string (from TOC analyzer).

        Args:
            instrument_type: Instrument type string (e.g., "DMM", "Calibrator")

        Returns:
            System prompt rules for the instrument type, or universal rules as fallback
        """
        if not instrument_type:
            logger.debug("No instrument_type provided, using universal rules")
            fallback = self.instrument_prompts.get("universal.yaml", {})
            return fallback.get("system_prompt", "")

        normalized = instrument_type.lower().strip()

        # Find matching prompt based on keywords
        for keyword, filename in INSTRUMENT_PROMPT_MAP.items():
            if keyword in normalized:
                prompt_data = self.instrument_prompts.get(filename, {})
                if prompt_data:
                    logger.info(f"Using {filename} rules for instrument_type='{instrument_type}'")
                    return prompt_data.get("system_prompt", "")

        # Fallback to universal
        logger.debug(f"No specific rules for '{instrument_type}', using universal")
        fallback = self.instrument_prompts.get("universal.yaml", {})
        return fallback.get("system_prompt", "")

    async def extract_from_tables(
        self,
        tables: List[TableSpec],
        instrument_type: str = "instrument",
        manufacturer: str = "Unknown",
        model: str = "Unknown",
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Extract specifications from multiple tables using multi-pass pipeline.

        Args:
            tables: List of TableSpec objects with image_bytes
            instrument_type: Type of instrument
            manufacturer: Manufacturer name
            model: Model name
            progress_callback: Optional async callback(tables_done, tables_total)

        Returns:
            Merged specifications dictionary
        """
        if not tables:
            return {
                "function_groups": [],
                "extraction_notes": ["No tables provided"],
                "metadata": {"tables_processed": 0},
            }

        logger.info(f"Starting multi-pass extraction for {len(tables)} tables")
        self._report_progress("init", 0, len(tables), "Starting extraction")

        semaphore = asyncio.Semaphore(self.max_concurrent)
        completed_count = 0
        total_tables = len(tables)

        # Wrapper to report progress after each table completes
        async def process_with_progress(table, index):
            nonlocal completed_count
            result = await self._process_table_multipass(
                semaphore, table, instrument_type, manufacturer, model, index, total_tables
            )
            completed_count += 1
            # Report per-table progress to external callback
            if progress_callback:
                try:
                    await progress_callback(completed_count, total_tables)
                except Exception as cb_err:
                    logger.warning(f"Progress callback error: {cb_err}")
            return result

        # Process all tables with progress tracking
        tasks = [process_with_progress(table, i) for i, table in enumerate(tables)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        valid_results = []
        skipped_count = 0
        error_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Table {i} error: {type(result).__name__}: {result}")
                error_count += 1
            elif result.get("skipped"):
                skipped_count += 1
            else:
                valid_results.append(result)

        # Merge results
        merged = self._merge_results(valid_results)

        merged["metadata"] = {
            "tables_processed": len(tables),
            "tables_successful": len(valid_results),
            "tables_skipped": skipped_count,
            "tables_errored": error_count,
            "extraction_method": "multipass",
            "passes": ["triage_structure", "raw", "normalize"],
        }

        logger.info(
            f"Extraction complete: {len(valid_results)}/{len(tables)} successful, "
            f"{skipped_count} skipped, {error_count} errors"
        )

        return merged

    async def _process_table_multipass(
        self,
        semaphore: asyncio.Semaphore,
        table: TableSpec,
        instrument_type: str,
        manufacturer: str,
        model: str,
        table_index: int,
        total_tables: int,
    ) -> Dict[str, Any]:
        """Process a single table through all passes (3-pass system)."""
        async with semaphore:
            table_id = f"p{table.page_number}_t{table.table_index}"

            try:
                # Pass 0: Triage + Structure (merged)
                self._report_progress(
                    "pass0",
                    table_index + 1,
                    total_tables,
                    f"Table {table_id}: Triage + Structure",
                )
                triage_structure_result = await self._pass0_triage_structure(
                    table, instrument_type
                )

                await self._save_pass_result(table_id, "pass0", triage_structure_result)

                if not triage_structure_result.get("is_calibration_table", False):
                    logger.info(
                        f"Table {table_id} skipped: {triage_structure_result.get('skip_reason', 'not calibration')}"
                    )
                    return {
                        "skipped": True,
                        "skip_reason": triage_structure_result.get("skip_reason"),
                        "table_type": triage_structure_result.get("table_type"),
                    }

                # Extract structure from merged pass0 result
                structure_result = triage_structure_result.get("structure", {})
                if structure_result is None:
                    # Fallback if structure is None
                    structure_result = {
                        "functions_present": [],
                        "column_meanings": [],
                        "time_period_location": "unknown",
                        "accuracy_format": "unknown",
                        "has_merged_cells": False,
                        "row_grouping": "flat",
                        "structure_notes": ["Structure was None from pass0"],
                    }

                # Pass 1: Raw extraction (was pass2) with retry logic
                max_retries = 3
                raw_result = None
                for attempt in range(max_retries):
                    self._report_progress(
                        "pass1",
                        table_index + 1,
                        total_tables,
                        f"Table {table_id}: Raw extraction (attempt {attempt + 1})",
                    )
                    try:
                        raw_result = await self._pass1_raw(
                            table, instrument_type, structure_result
                        )
                        # Check if result is valid (has raw_rows with data)
                        raw_rows = raw_result.get("raw_rows", [])
                        if raw_rows and len(raw_rows) > 0:
                            # Check if any row has actual cell values
                            has_data = any(
                                any(cell.get("value") for cell in row.get("cells", []))
                                for row in raw_rows
                            )
                            if has_data:
                                break  # Success - exit retry loop
                        logger.warning(
                            f"Table {table_id} Pass1 attempt {attempt + 1}: empty or no data, retrying..."
                        )
                    except Exception as e:
                        logger.warning(
                            f"Table {table_id} Pass1 attempt {attempt + 1} failed: {e}"
                        )
                        if attempt == max_retries - 1:
                            raw_result = {
                                "raw_rows": [],
                                "footnotes": [],
                                "extraction_notes": [f"Pass1 failed after {max_retries} attempts: {e}"],
                            }

                await self._save_pass_result(table_id, "pass1", raw_result)

                # Pass 2: Normalization (was pass3, TEXT input, no image)
                self._report_progress(
                    "pass2",
                    table_index + 1,
                    total_tables,
                    f"Table {table_id}: Normalize",
                )
                normalized_result = await self._pass2_normalize(
                    instrument_type, manufacturer, model, structure_result, raw_result
                )

                await self._save_pass_result(table_id, "pass2", normalized_result)

                # Add source metadata
                for group in normalized_result.get("function_groups", []):
                    for range_spec in group.get("ranges", []):
                        range_spec["source_page"] = table.page_number
                        range_spec["source_table"] = table.table_index

                return normalized_result

            except Exception as e:
                logger.error(f"Table {table_id} failed: {type(e).__name__}: {e}")
                return {
                    "function_groups": [],
                    "extraction_notes": [
                        f"Error on page {table.page_number}: {str(e)}"
                    ],
                    "metadata": None,
                }

    async def _pass0_triage_structure(
        self, table: TableSpec, instrument_type: str
    ) -> Dict[str, Any]:
        """Pass 0: Merged triage + structure - classify and analyze table layout."""
        config = PASS_CONFIGS["pass0"]
        prompt_config = self.prompts.get("pass0", {})
        schema = self.schemas.get("pass0")

        if not schema:
            # Fallback: assume it's a calibration table with complete structure
            return {
                "is_calibration_table": True,
                "confidence": 0.5,
                "table_type": "unknown",
                "skip_reason": None,
                "structure": {
                    "functions_present": [],
                    "column_meanings": [],
                    "time_period_location": "unknown",
                    "accuracy_format": "unknown",
                    "has_merged_cells": False,
                    "row_grouping": "flat",
                    "structure_notes": ["Schema not available"],
                },
            }

        # Build context from page metadata and TOC section
        context_parts = []

        # Include section title from TOC (critical for triage accuracy)
        if table.section_title:
            context_parts.append(f"Section from TOC: {table.section_title}")

        page_ctx = table.page_context or {}
        if page_ctx.get("headers"):
            context_parts.append(f"Page headers: {page_ctx['headers']}")
        if page_ctx.get("footnotes"):
            context_parts.append(f"Footnotes: {page_ctx['footnotes']}")
        context = "\n".join(context_parts) if context_parts else ""

        system_prompt = prompt_config.get("system_prompt", "")
        user_template = prompt_config.get("user_prompt_template", "")
        user_prompt = user_template.format(
            instrument_type=instrument_type, context=context
        )

        return await self._call_vision_with_schema(
            table=table,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            config=config,
        )

    async def _pass1_raw(
        self,
        table: TableSpec,
        instrument_type: str,
        structure: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Pass 1: Extract raw values VERBATIM - no normalization (was pass2)."""
        config = PASS_CONFIGS["pass1"]
        prompt_config = self.prompts.get("pass1", {})
        schema = self.schemas.get("pass1")

        if not schema:
            return {
                "raw_rows": [],
                "footnotes": [],
                "extraction_notes": ["Schema not available"],
            }

        # Format structure info for prompt
        functions_str = ", ".join(structure.get("functions_present", [])[:10])
        columns_str = json.dumps(structure.get("column_meanings", [])[:8], indent=2)
        time_location = structure.get("time_period_location", "unknown")

        system_prompt = prompt_config.get("system_prompt", "")
        user_template = prompt_config.get("user_prompt_template", "")
        user_prompt = user_template.format(
            functions_present=functions_str,
            column_meanings=columns_str,
            time_period_location=time_location,
        )

        return await self._call_vision_with_schema(
            table=table,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            config=config,
        )

    async def _pass2_normalize(
        self,
        instrument_type: str,
        manufacturer: str,
        model: str,
        structure: Dict[str, Any],
        raw_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Pass 2: Normalize raw data using domain rules (was pass3, TEXT input, no image)."""
        config = PASS_CONFIGS["pass2"]
        prompt_config = self.prompts.get("pass2", {})
        schema = self.schemas.get("pass2")

        if not schema:
            # Fallback to pass-through
            return {
                "function_groups": [],
                "extraction_notes": ["Normalization schema not available"],
                "metadata": {"confidence": 0.0, "table_quality": "unknown"},
            }

        # Prepare clean JSON representations
        structure_json = json.dumps(structure, indent=2)
        raw_data_json = json.dumps(raw_data, indent=2)

        # Get base normalization prompt
        base_system_prompt = prompt_config.get("system_prompt", "")

        # Get instrument-specific rules and merge with base prompt
        instrument_rules = self._get_instrument_rules(instrument_type)
        if instrument_rules:
            system_prompt = (
                f"{base_system_prompt}\n\n"
                f"INSTRUMENT-SPECIFIC RULES ({instrument_type}):\n"
                f"{instrument_rules}"
            )
        else:
            system_prompt = base_system_prompt

        user_template = prompt_config.get("user_prompt_template", "")
        user_prompt = user_template.format(
            instrument_type=instrument_type,
            manufacturer=manufacturer,
            model=model,
            structure_json=structure_json,
            raw_data_json=raw_data_json,
        )

        # Pass 2 is TEXT-ONLY (no image) - uses the extracted data
        return await self._call_text_with_schema(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            config=config,
        )

    async def _call_vision_with_schema(
        self,
        table: TableSpec,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        config: PassConfig,
    ) -> Dict[str, Any]:
        """Make vision API call with function calling schema."""
        if not table.image_bytes:
            raise ValueError(
                f"Vision extraction requires image_bytes for table "
                f"page {table.page_number}, index {table.table_index}"
            )

        client = await self._get_client()

        # Build image content
        image_b64 = base64.b64encode(table.image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{image_b64}"

        combined_prompt = f"{system_prompt}\n\n{user_prompt}"

        content = [
            {"type": "input_text", "text": combined_prompt},
            {"type": "input_image", "image_url": image_url},
        ]

        # Map model name to actual model
        model_map = {"nano": GPT5_MODEL_NANO, "mini": GPT5_MODEL_MINI}
        model_name = model_map.get(config.model, GPT5_MODEL_NANO)

        response = await client.client.responses.create(
            model=model_name,
            input=[{"role": "user", "content": content}],
            tools=[schema],
            tool_choice={"type": "function", "name": schema["name"]},
            reasoning={"effort": config.reasoning_effort},
            text={"verbosity": config.verbosity},
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
        )

        # Extract function call result
        for item in response.output:
            if hasattr(item, "type") and item.type == "function_call":
                if hasattr(item, "name") and item.name == schema["name"]:
                    arguments = item.arguments
                    if isinstance(arguments, str):
                        return json.loads(arguments)
                    else:
                        raise TypeError(f"Expected string arguments, got {type(arguments)}")

        logger.warning(f"No function call in {config.name} response")
        return {}

    async def _call_text_with_schema(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        config: PassConfig,
    ) -> Dict[str, Any]:
        """Make text-only API call with function calling schema (no image)."""
        client = await self._get_client()

        combined_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Map model name to actual model
        model_map = {"nano": GPT5_MODEL_NANO, "mini": GPT5_MODEL_MINI}
        model_name = model_map.get(config.model, GPT5_MODEL_MINI)

        response = await client.client.responses.create(
            model=model_name,
            input=combined_prompt,
            tools=[schema],
            tool_choice={"type": "function", "name": schema["name"]},
            reasoning={"effort": config.reasoning_effort},
            text={"verbosity": config.verbosity},
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
        )

        # Extract function call result
        for item in response.output:
            if hasattr(item, "type") and item.type == "function_call":
                if hasattr(item, "name") and item.name == schema["name"]:
                    arguments = item.arguments
                    if isinstance(arguments, str):
                        return json.loads(arguments)
                    else:
                        raise TypeError(f"Expected string arguments, got {type(arguments)}")

        logger.warning(f"No function call in {config.name} response")
        return {
            "function_groups": [],
            "extraction_notes": ["No function call in response"],
            "metadata": None,
        }

    def _merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple extraction results."""
        all_groups = []
        all_notes = []

        for result in results:
            all_groups.extend(result.get("function_groups", []))
            all_notes.extend(result.get("extraction_notes", []))

        return {
            "function_groups": all_groups,
            "extraction_notes": all_notes,
            "metadata": None,
        }

    async def _save_pass_result(
        self, table_id: str, pass_name: str, result: Dict[str, Any]
    ) -> None:
        """Save pass result for debugging."""
        try:
            filename = f"{table_id}_{pass_name}.json"
            filepath = self.debug_dir / filename

            async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
                await f.write(json.dumps(result, indent=2, ensure_ascii=False))

            logger.debug(f"Saved {pass_name} result to {filepath}")

        except Exception as e:
            logger.warning(f"Failed to save {pass_name} result: {e}")

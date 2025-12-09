"""Async parallel orchestrator for LLM extraction."""

import asyncio
import aiofiles
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..config.settings import (
    DEFAULT_PROMPT_VERSION,
    LLM_MODEL_ASYNC,
)
from ..core.models import TableSpec
from ..core.utils import merge_extraction_results

from .client import get_client
from ..config.prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class AsyncLLMExtractor:
    """Async parallel orchestrator for LLM extraction.

    Domain-agnostic extraction with configurable prompts and output formats.
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        model: str = None,
        output_format: str = None
    ):
        """
        Initialize the async LLM extractor.

        Args:
            max_concurrent: Maximum concurrent LLM requests (capped at 5)
            prompt_version: Default prompt version to use
            model: LLM model name (defaults to LLM_MODEL_ASYNC)
            output_format: Target output format (affects prompt directory)
        """
        self.max_concurrent = min(max_concurrent, 5)

        if model is None:
            model = LLM_MODEL_ASYNC
        self.model = model

        self.output_format = output_format
        self.prompt_version = prompt_version
        self.prompt_loader = PromptLoader(output_format=output_format)
        self.prompt_config = self.prompt_loader.load_prompt(prompt_version)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_dir = Path("Data") / "llm_responses" / timestamp
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        format_info = f", format={output_format}" if output_format else ""
        logger.info(f"Initialized: {self.max_concurrent} workers, {model} model{format_info}")
        logger.info(f"LLM responses will be logged to: {self.debug_dir}")
    
    async def extract_from_tables(
        self,
        tables: List[TableSpec],
        instrument_type: str = "Digital Multimeter",
        manufacturer: str = "Unknown",
        model: str = "Unknown",
        progress_callback: Any = None
    ) -> Dict[str, Any]:
        """Extract specifications from multiple tables.

        Args:
            tables: List of TableSpec objects
            instrument_type: Type of instrument
            manufacturer: Manufacturer name
            model: Model name
            progress_callback: Optional async callback(tables_done, tables_total)

        Returns:
            Merged specifications dictionary
        """
        if not tables:
            return {"function_groups": [], "extraction_notes": ["No tables provided"]}

        start_time = time.time()
        logger.info(f"Processing {len(tables)} tables with {self.max_concurrent} workers")

        # Track completed tables for progress reporting
        completed_count = 0
        total_tables = len(tables)
        results = []

        # Limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_with_progress(table):
            nonlocal completed_count
            result = await self._process_table(
                semaphore, table, instrument_type, manufacturer, model
            )
            completed_count += 1

            # Report per-table progress
            if progress_callback:
                try:
                    await progress_callback(completed_count, total_tables)
                except Exception as cb_err:
                    logger.warning(f"Progress callback error: {cb_err}")

            return result

        # Submit all tasks with concurrency limit
        tasks = [process_with_progress(table) for table in tables]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle errors
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing table {i}: {type(result).__name__}: {result}")
                if isinstance(result, KeyError):
                    logger.error(f"KeyError details - key was: {result.args}")
            else:
                valid_results.append(result)
        
        # Combine extracted specifications
        merged = merge_extraction_results(valid_results)
        
        # Include processing statistics
        elapsed = time.time() - start_time
        merged["metadata"] = {
            "tables_processed": len(tables),
            "tables_successful": len(valid_results),
            "workers_used": self.max_concurrent,
            "processing_time": elapsed,
            "avg_time_per_table": elapsed / len(tables),
            "model": self.model
        }
        
        logger.info(f"Completed in {elapsed:.2f}s ({len(valid_results)}/{len(tables)} successful)")
        return merged

    async def _execute_extraction_request(
        self,
        table: TableSpec,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        """
        Execute vision-based LLM extraction request.

        Args:
            table: TableSpec with image_bytes
            system_prompt: System instructions
            user_prompt: User prompt with context

        Returns:
            JSON string with extraction results
        """
        if not table.image_bytes:
            raise ValueError(
                f"Vision extraction requires image_bytes for table "
                f"page {table.page_number}, index {table.table_index}"
            )

        client = await get_client()
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        specs = await client.extract_calibration_specs_from_image(
            image_bytes=table.image_bytes,
            prompt_text=combined_prompt,
            model=self.model
        )
        result_json = json.dumps(specs)
        logger.debug(
            f"Vision extraction completed for page {table.page_number}, "
            f"table {table.table_index}: {len(result_json)} chars"
        )

        return result_json

    async def _process_table(
        self,
        semaphore: asyncio.Semaphore,
        table: TableSpec,
        instrument_type: str,
        manufacturer: str,
        model: str
    ) -> Dict[str, Any]:
        """Process a single table with LLM."""
        async with semaphore:
            try:
                # Format instrument context
                context = f"a {instrument_type}"
                if manufacturer and model:
                    context = f"{manufacturer} {model} ({context})"
                elif model:
                    context = f"model {model} ({context})"
                
                # Select appropriate prompt based on instrument type
                prompt_name = self.prompt_loader.select_prompt_for_instrument(
                    instrument_type=instrument_type,
                    model=model
                )
                prompt_config = self.prompt_loader.load_prompt(prompt_name)
                
                # Load system prompt from configuration
                system_prompt = prompt_config["system_prompt"]
                
                # Build context-aware user prompt for vision extraction
                page_ctx = table.page_context or {}
                context_str = []

                if page_ctx.get("headers"):
                    context_str.append(f"Page headers: {page_ctx['headers']}")
                if page_ctx.get("footnotes"):
                    context_str.append(f"Footnotes: {page_ctx['footnotes']}")

                # Add section title from TOC for mode disambiguation
                if table.section_title:
                    context_str.append(f"Section from TOC: {table.section_title}")

                context_info = "\n".join(context_str) if context_str else ""

                # Build vision-specific user prompt
                template = prompt_config["user_prompt_template"]

                # Define vision instruction for table analysis
                vision_instruction = (
                    "Analyze the table image provided. Extract all calibration "
                    "specifications visible in the table structure."
                )

                # Format template with vision instruction
                user_prompt = template.format(
                    table_content=vision_instruction,
                    context=context,
                    instrument_type=instrument_type or 'instrument'
                )

                # Prepend page context if available
                if context_info:
                    user_prompt = f"PAGE CONTEXT:\n{context_info}\n\n{user_prompt}"

                # Execute LLM request
                try:
                    result_json = await self._execute_extraction_request(
                        table, system_prompt, user_prompt
                    )
                except Exception as llm_error:
                    logger.error(f"LLM call failed for table on page {table.page_number}: {llm_error}")
                    raise

                await self._save_raw_response(
                    table.page_number,
                    table.table_index,
                    system_prompt,
                    user_prompt,
                    result_json
                )

                specs = json.loads(result_json)
                
                # Tag specifications with source metadata
                for group in specs.get("function_groups", []):
                    for range_spec in group.get("ranges", []):
                        range_spec["source_page"] = table.page_number
                        range_spec["source_table"] = table.table_index
                
                return specs
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for table on page {table.page_number}: {e}")
                if 'result_json' in locals():
                    logger.error(f"Raw response snippet: {result_json[:500]}")
                return {
                    "function_groups": [],
                    "extraction_notes": [f"JSON error on page {table.page_number}: {str(e)}"]
                }
            except Exception as e:
                logger.error(f"Error processing table on page {table.page_number}: {type(e).__name__}: {e}")
                return {
                    "function_groups": [],
                    "extraction_notes": [f"Error on page {table.page_number}: {str(e)}"]
                }

    async def _save_raw_response(
        self,
        page_number: int,
        table_index: int,
        system_prompt: str,
        user_prompt: str,
        raw_response: str
    ) -> None:
        """Save raw LLM response to debug directory."""
        try:
            filename = f"page_{page_number}_table_{table_index}_raw.json"
            filepath = self.debug_dir / filename

            parsed_success = True
            try:
                json.loads(raw_response)
            except json.JSONDecodeError:
                parsed_success = False

            debug_data = {
                "page": page_number,
                "table_index": table_index,
                "timestamp": datetime.now().isoformat(),
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "raw_response": raw_response,
                "parsed_success": parsed_success
            }

            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(debug_data, indent=2, ensure_ascii=False))

            logger.debug(f"Saved raw LLM response to {filepath}")

        except Exception as save_error:
            logger.warning(f"Failed to save raw LLM response: {save_error}")


"""Main pipeline orchestrator for PDF document processing.

Extracts data from PDF documents using LLM vision and generates structured output.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.config.settings import EXTRACTION_MODE
from backend.core.models import InstrumentInfo, TableSpec
from backend.core.utils import deduplicate_functions
from backend.llm.async_extractor import AsyncLLMExtractor
from backend.llm.multipass_extractor import MultiPassExtractor
from backend.pdf.table_cropper import TableCropper
from backend.pdf.toc_analyzer import TOCAnalyzer
from backend.serializers import OutputFormat, SerializerConfig, SerializerFactory

logger = logging.getLogger(__name__)

# Valid output formats
VALID_OUTPUT_FORMATS = {"json"}


class Pipeline:
    """Main pipeline for PDF document processing.

    Extracts structured data from PDFs using LLM vision and outputs JSON.
    """

    def __init__(
        self,
        max_concurrent_llm: int = 5,
        llm_model: str = "mini",
        output_formats: Optional[List[str]] = None
    ):
        """
        Initialize the pipeline.

        Args:
            max_concurrent_llm: Maximum concurrent LLM requests
            llm_model: LLM model to use ('mini' or 'main')
            output_formats: List of output formats. Defaults to ['json'].
        """
        # Validate and normalize output formats
        self.output_formats = self._validate_output_formats(output_formats)
        self.primary_format = self.output_formats[0] if self.output_formats else "json"

        self.toc_analyzer = TOCAnalyzer(model="main")
        self.table_cropper = TableCropper()

        # Choose extractor based on EXTRACTION_MODE setting
        self.extraction_mode = EXTRACTION_MODE
        if EXTRACTION_MODE == "multi":
            self.llm_extractor = MultiPassExtractor(
                max_concurrent=max_concurrent_llm
            )
            extractor_name = "MultiPassExtractor"
        else:
            self.llm_extractor = AsyncLLMExtractor(
                max_concurrent=max_concurrent_llm,
                model=llm_model,
                output_format=self.primary_format
            )
            extractor_name = "AsyncLLMExtractor"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_dir = Path("Data") / "table_extraction" / timestamp
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        formats_str = ", ".join(self.output_formats)
        logger.info(f"Pipeline initialized: formats=[{formats_str}], extractor={extractor_name}")
        logger.info(f"Table extraction debug: {self.debug_dir}")

    def _validate_output_formats(
        self,
        formats: Optional[List[str]]
    ) -> List[str]:
        """Validate and normalize output formats.

        Args:
            formats: List of requested output formats

        Returns:
            Validated list of output formats

        Raises:
            ValueError: If invalid format specified
        """
        if not formats:
            return ["json"]

        validated = []
        for fmt in formats:
            fmt_lower = fmt.lower().strip()
            if fmt_lower not in VALID_OUTPUT_FORMATS:
                raise ValueError(
                    f"Invalid output format: '{fmt}'. "
                    f"Valid formats: {VALID_OUTPUT_FORMATS}"
                )
            if fmt_lower not in validated:
                validated.append(fmt_lower)

        return validated

    def _get_section_for_page(
        self,
        page_num: int,
        page_sections: Dict[int, str]
    ) -> Optional[str]:
        """Find closest preceding section title from TOC.

        Args:
            page_num: Current page number
            page_sections: Dictionary mapping page numbers to section titles

        Returns:
            Section title from nearest preceding page, or None if not found
        """
        if not page_sections:
            return None
        matching_pages = [p for p in page_sections.keys() if p <= page_num]
        if matching_pages:
            return page_sections[max(matching_pages)]
        return None

    async def process_async(
        self,
        pdf_path: Path,
        output_path: Path,
        instrument_info: Optional[InstrumentInfo] = None,
        progress_callback: Optional[Callable] = None,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Process a PDF and generate output files.

        Args:
            pdf_path: Path to input PDF
            output_path: Path for primary output (backward compatibility)
            instrument_info: Optional document metadata
            progress_callback: Optional progress callback function
            output_dir: Optional directory for multi-format output.

        Returns:
            Dict with success status, paths, and statistics
        """
        try:
            if instrument_info is None:
                instrument_info = InstrumentInfo()

            self._report_progress(progress_callback, "toc_analysis")
            toc_result = await self.toc_analyzer.analyze_pdf(pdf_path)

            if not instrument_info.manufacturer and toc_result.get("manufacturer"):
                instrument_info.manufacturer = toc_result["manufacturer"]
            if not instrument_info.model and toc_result.get("model"):
                instrument_info.model = toc_result["model"]
            if not instrument_info.instrument_type and toc_result.get("instrument_type"):
                instrument_info.instrument_type = toc_result["instrument_type"]

            spec_pages = toc_result.get("spec_pages", [])
            page_sections = toc_result.get("page_sections", {})

            if not spec_pages:
                logger.warning("No specification pages found in PDF")
                return {
                    "success": False,
                    "error": "No specification pages detected",
                    "instrument_info": instrument_info
                }

            logger.info(f"Found {len(spec_pages)} specification pages")
            self._report_progress(progress_callback, "toc_analysis", pages_total=len(spec_pages))

            self._report_progress(
                progress_callback,
                "table_extraction",
                pages_done=0,
                pages_total=len(spec_pages)
            )

            cropped_tables = self.table_cropper.crop_tables_from_pages(
                pdf_path, spec_pages
            )

            if not cropped_tables:
                logger.warning("No tables found on specification pages")
                return {
                    "success": False,
                    "error": "No tables found",
                    "instrument_info": instrument_info
                }

            logger.info(f"Extracted {len(cropped_tables)} table images")
            self._report_progress(
                progress_callback,
                "table_extraction",
                pages_done=len(spec_pages),
                pages_total=len(spec_pages),
                tables_total=len(cropped_tables)
            )

            self._report_progress(
                progress_callback,
                "vision_processing",
                tables_done=0,
                tables_total=len(cropped_tables)
            )

            table_specs = []
            for idx, (page_num, table_idx, img_bytes) in enumerate(cropped_tables):
                page_context = self.table_cropper.extract_page_context(
                    pdf_path, page_num
                )

                self._save_table_debug_data(page_num, table_idx, img_bytes, page_context)

                section_title = self._get_section_for_page(page_num, page_sections)

                table_spec = TableSpec(
                    page_number=page_num,
                    table_index=table_idx,
                    source_path=str(pdf_path),
                    image_bytes=img_bytes,
                    extraction_method="vision",
                    page_context=page_context,
                    section_title=section_title
                )
                table_specs.append(table_spec)

                self._report_progress(
                    progress_callback,
                    "vision_processing",
                    tables_done=idx + 1,
                    tables_total=len(cropped_tables)
                )

            logger.info(f"Vision processing prepared {len(table_specs)} tables")

            self._report_progress(
                progress_callback,
                "llm_extraction",
                tables_done=0,
                tables_total=len(table_specs)
            )

            async def llm_progress(tables_done: int, tables_total: int):
                self._report_progress(
                    progress_callback,
                    "llm_extraction",
                    tables_done=tables_done,
                    tables_total=tables_total
                )

            extraction_results = await self.llm_extractor.extract_from_tables(
                tables=table_specs,
                instrument_type=instrument_info.instrument_type or "Unknown",
                manufacturer=instrument_info.manufacturer or "Unknown",
                model=instrument_info.model or "Unknown",
                progress_callback=llm_progress
            )

            logger.info("LLM extraction completed")
            self._report_progress(
                progress_callback,
                "llm_extraction",
                tables_done=len(table_specs),
                tables_total=len(table_specs)
            )

            self._report_progress(progress_callback, "consolidation")
            extraction_results = deduplicate_functions([extraction_results])
            logger.info("Deduplication completed")

            self._report_progress(progress_callback, "output_generation")

            extraction_metadata = {}
            if isinstance(extraction_results, dict):
                extraction_metadata = extraction_results.get("metadata", {})
                extraction_results = [extraction_results]
            elif extraction_results and isinstance(extraction_results[0], dict):
                extraction_metadata = extraction_results[0].get("metadata", {})

            # Generate output files for requested formats
            generated_files = await self._generate_output_files(
                extraction_results=extraction_results,
                output_path=output_path,
                output_dir=output_dir,
                instrument_info=instrument_info
            )

            self._report_progress(progress_callback, "output_generation")
            self._report_progress(progress_callback, "complete")

            source_pages = sorted(set(spec.page_number for spec in table_specs))

            return {
                "success": True,
                "output_path": str(output_path),
                "output_files": generated_files,
                "output_formats": self.output_formats,
                "instrument_info": instrument_info,
                "source_pages": source_pages,
                "statistics": {
                    "pages_analyzed": len(spec_pages),
                    "tables_found": len(cropped_tables),
                    "tables_processed": len(table_specs),
                    "extraction_metadata": extraction_metadata
                }
            }

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            self._report_progress(progress_callback, "error", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "instrument_info": instrument_info
            }

    def process(
        self,
        pdf_path: Path,
        output_path: Path,
        instrument_info: Optional[InstrumentInfo] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        return asyncio.run(
            self.process_async(pdf_path, output_path, instrument_info, progress_callback)
        )

    def _report_progress(
        self,
        callback: Optional[Callable],
        phase: str,
        pages_done: Optional[int] = None,
        pages_total: Optional[int] = None,
        tables_done: Optional[int] = None,
        tables_total: Optional[int] = None,
        **kwargs
    ) -> None:
        if callback:
            try:
                callback(
                    phase=phase,
                    pages_done=pages_done,
                    pages_total=pages_total,
                    tables_done=tables_done,
                    tables_total=tables_total,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def _save_table_debug_data(
        self,
        page_number: int,
        table_index: int,
        img_bytes: bytes,
        page_context: Dict[str, str]
    ) -> None:
        """Save table extraction debug data for analysis."""
        try:
            filename_base = f"page_{page_number}_table_{table_index}"

            img_path = self.debug_dir / f"{filename_base}.png"
            with open(img_path, 'wb') as f:
                f.write(img_bytes)

            debug_data = {
                "page": page_number,
                "table_index": table_index,
                "timestamp": datetime.now().isoformat(),
                "page_context": page_context,
                "extraction_method": "vision"
            }

            json_path = self.debug_dir / f"{filename_base}_data.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved table extraction debug data: {filename_base}")

        except Exception as save_error:
            logger.warning(f"Failed to save table debug data: {save_error}")

    async def _generate_output_files(
        self,
        extraction_results: List[Dict[str, Any]],
        output_path: Path,
        output_dir: Optional[Path],
        instrument_info: InstrumentInfo
    ) -> Dict[str, List[str]]:
        """Generate output files for all requested formats.

        Args:
            extraction_results: LLM extraction results
            output_path: Primary output path (backward compat)
            output_dir: Directory for multi-format output
            instrument_info: Document metadata

        Returns:
            Dict mapping format to list of generated file paths
        """
        generated_files: Dict[str, List[str]] = {}

        # Prepare data for serialization
        output_data = {
            "instrument_info": {
                "manufacturer": instrument_info.manufacturer,
                "model": instrument_info.model,
                "instrument_type": instrument_info.instrument_type
            },
            "extraction_results": extraction_results,
            "generated_at": datetime.now().isoformat()
        }

        # Generate each requested format
        for fmt in self.output_formats:
            try:
                target_dir = output_dir if output_dir else output_path.parent

                config = SerializerConfig(
                    output_dir=target_dir,
                    instrument_name=instrument_info.model or "output",
                    include_comments=True
                )

                serializer = SerializerFactory.create(OutputFormat(fmt), config)

                generated_paths: List[str] = []
                for output in serializer.serialize(output_data):
                    file_path = output.write_to_path(target_dir)
                    generated_paths.append(str(file_path))
                    logger.info(f"Generated {fmt.upper()} file: {file_path}")

                    for warning in output.warnings:
                        logger.warning(f"{fmt.upper()} data loss: {warning.to_message()}")

                generated_files[fmt] = generated_paths

            except Exception as e:
                logger.error(f"{fmt.upper()} generation failed: {e}", exc_info=True)
                generated_files[fmt] = []

        return generated_files

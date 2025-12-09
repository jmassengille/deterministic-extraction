"""Universal TOC analysis for identifying specification pages."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from backend.llm.client import get_client
from backend.config.settings import LLM_REASONING_EFFORT, LLM_VERBOSITY

logger = logging.getLogger(__name__)


class TOCAnalyzer:
    """Universal TOC analyzer for any instrument manual."""

    def __init__(self, model: str = "mini"):
        """Initialize TOC analyzer."""
        self.model = model
        logger.info(f"TOC Analyzer initialized with model: {model}")

    async def analyze_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Analyze PDF to find specification pages and metadata.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with spec_pages, page_sections, manufacturer, model, and confidence
        """
        # Extract basic metadata
        metadata = self._extract_metadata(pdf_path)

        # Extract TOC
        toc_entries = self._extract_toc(pdf_path)

        # Use LLM to identify spec pages and instrument info
        result = await self._analyze_with_llm(metadata, toc_entries)

        # Build page_sections mapping: page_num -> section_title
        # This helps Pass 0 triage understand what section a table belongs to
        spec_pages = result.get("spec_pages", [])
        page_sections = self._build_page_sections(toc_entries, spec_pages)
        result["page_sections"] = page_sections

        return result

    def _build_page_sections(
        self,
        toc_entries: List[Dict[str, Any]],
        spec_pages: List[int]
    ) -> Dict[int, str]:
        """
        Build mapping from page numbers to their containing section titles.

        Uses TOC entries to determine which section each spec page belongs to.
        Each page maps to the most recent section title at or before that page.

        Args:
            toc_entries: TOC entries with {level, title, page}
            spec_pages: List of specification page numbers

        Returns:
            Dict mapping page_num -> section_title
        """
        if not toc_entries or not spec_pages:
            return {}

        # Sort TOC entries by page number
        sorted_entries = sorted(toc_entries, key=lambda x: x.get("page", 0))

        page_sections: Dict[int, str] = {}
        for page_num in spec_pages:
            # Find the section this page belongs to
            # (most recent TOC entry at or before this page)
            section_title = None
            for entry in sorted_entries:
                entry_page = entry.get("page", 0)
                if entry_page <= page_num:
                    section_title = entry.get("title", "")
                else:
                    break  # TOC entries are sorted, so we can stop

            if section_title:
                page_sections[page_num] = section_title

        return page_sections

    def _extract_metadata(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract basic PDF metadata."""
        with fitz.open(str(pdf_path)) as doc:
            return {
                "title": doc.metadata.get("title", "").strip() or pdf_path.stem,
                "page_count": doc.page_count,
                "filename": pdf_path.name,
                "path": str(pdf_path)
            }

    def _extract_toc(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Extract table of contents from PDF."""
        with fitz.open(str(pdf_path)) as doc:
            toc = doc.get_toc()

            # Convert to dict format, filter to main sections only
            entries = []
            for level, title, page in toc:
                if level <= 2:  # Main and subsections only
                    entries.append({
                        "level": level,
                        "title": title,
                        "page": page
                    })

            return entries

    async def _analyze_with_llm(
        self,
        metadata: Dict[str, Any],
        toc_entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use LLM to analyze TOC and identify specifications."""
        client = await get_client()
        toc_text = self._format_toc_for_llm(toc_entries)

        system_prompt = """Analyze this calibration instrument manual's table of contents to identify specification sections containing accuracy tables and measurement performance data.

HINTS (common patterns, but not rules):
- Specification tables typically appear in later sections of manuals (often after operation/setup)
- Look for sections explicitly named "Specifications", "Accuracy", "Performance", or "Characteristics"
- Specs may be split across multiple sections (e.g., "DC Specifications", "AC Specifications")
- Some manuals put specs in appendices or at chapter ends
- Technical/electrical specifications are usually grouped together

Focus on sections likely to contain measurement accuracy tables with ranges, uncertainties, and tolerances.

Identify:
1. Manufacturer and model from document title/context
2. Page ranges containing specification tables (return as list of page numbers)
3. Instrument type (DMM, Calibrator, Pressure Controller, etc.)

"""

        user_prompt = f"""Document: {metadata['title']}
Filename: {metadata['filename']}
Total pages: {metadata['page_count']}

Table of Contents:
{toc_text}

Identify specification sections (tables with accuracy, ranges, uncertainties)."""

        try:
            # Combine system and user prompts for function calling
            full_input = f"{system_prompt}\n\n{user_prompt}"

            result = await client.analyze_toc(
                input_text=full_input,
                model=self.model,
                reasoning_effort="low",  # TOC parsing needs consistency, not complex reasoning
                verbosity="low"  # We want concise JSON output, not verbose explanations
            )

            # Ensure spec_pages is a flat list of integers
            if "spec_pages" in result:
                pages = []
                for item in result["spec_pages"]:
                    if isinstance(item, list) and len(item) == 2:
                        # Handle [start, end] range pairs
                        try:
                            start, end = int(item[0]), int(item[1])
                            pages.extend(range(start, end + 1))
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Could not parse range {item}: {e}")
                    elif isinstance(item, (int, str)):
                        # Handle single page numbers
                        try:
                            pages.append(int(item))
                        except ValueError as e:
                            logger.warning(f"Could not parse page {item}: {e}")
                    else:
                        logger.warning(f"Unexpected page format: {item}")

                # Remove duplicates and sort
                result["spec_pages"] = sorted(set(pages)) if pages else []

            return result

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"LLM analysis failed: {type(e).__name__}: {e}", exc_info=True)
            return {
                "manufacturer": "Unknown",
                "model": "Unknown",
                "instrument_type": "Unknown",
                "spec_pages": [],
                "confidence": 0.0,
                "error": str(e)
            }

    def _format_toc_for_llm(self, toc_entries: List[Dict[str, Any]]) -> str:
        """Format TOC entries for LLM consumption."""
        if not toc_entries:
            return "No table of contents found"

        lines = []
        for entry in toc_entries:
            indent = "  " * (entry["level"] - 1)
            lines.append(f"{indent}{entry['title']} ... page {entry['page']}")

        return "\n".join(lines)

"""Table image extraction from PDF using PyMuPDF."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class TableCropper:

    def __init__(self, zoom_factor: float = 2.0, table_strategy: str = "lines_strict"):
        self.zoom_factor = zoom_factor
        self.table_strategy = table_strategy  # lines_strict provides better detection for most calibration docs
        self.stats = {
            "pages_processed": 0,
            "tables_found": 0
        }
    
    def crop_tables_from_pages(
        self, 
        pdf_path: Path, 
        page_numbers: List[int]
    ) -> List[Tuple[int, int, bytes]]:
        """
        Extract table images from specified pages.
        
        Args:
            pdf_path: Path to PDF file
            page_numbers: List of page numbers (1-based)
            
        Returns:
            List of (page_num, table_idx, image_bytes) tuples
        """
        if not page_numbers:
            logger.warning("No page numbers provided for table extraction")
            return []
        
        logger.info(f"Extracting tables from {len(page_numbers)} pages")
        
        cropped_tables = []
        
        with fitz.open(str(pdf_path)) as doc:
            for page_num in page_numbers:
                if page_num < 1 or page_num > doc.page_count:
                    logger.warning(f"Page {page_num} out of range (1-{doc.page_count})")
                    continue
                
                try:
                    page = doc[page_num - 1]

                    table_finder = page.find_tables(strategy=self.table_strategy)
                    if not table_finder:
                        continue
                    
                    tables = list(table_finder.tables)
                    logger.debug(f"Page {page_num}: Found {len(tables)} tables")
                    
                    for table_idx, table in enumerate(tables):
                        bbox = fitz.Rect(table.bbox)
                        
                        matrix = fitz.Matrix(self.zoom_factor, self.zoom_factor)
                        pix = page.get_pixmap(matrix=matrix, clip=bbox)
                        
                        img_bytes = pix.pil_tobytes(format="PNG")
                        cropped_tables.append((page_num, table_idx, img_bytes))
                        self.stats["tables_found"] += 1
                    
                    self.stats["pages_processed"] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to extract tables from page {page_num}: {e}")
        
        logger.info(f"Extracted {len(cropped_tables)} table images")
        return cropped_tables
    
    def get_stats(self) -> dict:
        """Get extraction statistics."""
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset extraction statistics."""
        self.stats = {
            "pages_processed": 0,
            "tables_found": 0
        }
    
    def extract_overrange_from_pages(
        self,
        pdf_path: Path,
        page_numbers: List[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract overrange info from specification pages.
        
        Args:
            pdf_path: Path to PDF file
            page_numbers: List of page numbers to search
            
        Returns:
            Dict with footnote, percent, scope if found, else None
        """
        if not page_numbers:
            return None
            
        with fitz.open(str(pdf_path)) as doc:
            text_parts = []
            
            for page_num in page_numbers:
                # Check current and next page for footnote overflow
                for offset in [0, 1]:
                    idx = page_num + offset - 1
                    if 0 <= idx < doc.page_count:
                        text_parts.append(doc[idx].get_text())
            
            text = "".join(text_parts)
            
            # Multiple patterns for overrange detection
            patterns = [
                r'[\[\(](\d+)[\]\)]\s*(\d+(?:\.\d+)?)\s*%\s*over[-\s]?range([^.\n]*)',
                r'(\d+)\s*%\s*over[-\s]?range\s*on\s*all\s*ranges([^.\n]*)',
                r'Note\s*(\d+)[:\s]+(\d+(?:\.\d+)?)\s*%\s*over[-\s]?range([^.\n]*)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    groups = match.groups()
                    if len(groups) == 2:
                        footnote, percent = '1', groups[0]
                        scope = groups[1] if len(groups) > 1 else ''
                    else:
                        footnote = groups[0]
                        percent = groups[1]
                        scope = groups[2] if len(groups) > 2 else ''
                    
                    result = {
                        'footnote': footnote,
                        'percent': float(percent) / 100.0,
                        'scope': scope.strip()
                    }
                    
                    logger.info(
                        f"Overrange detected: {float(percent)}% "
                        f"(footnote [{footnote}], scope: '{scope.strip() or 'all ranges'}')"
                    )
                    
                    return result

        return None

    def extract_page_context(
        self,
        pdf_path: Path,
        page_number: int
    ) -> Dict[str, str]:
        """
        Extract context from page for LLM processing.

        Args:
            pdf_path: Path to PDF file
            page_number: Page number (1-based)

        Returns:
            Dict with headers, footnotes, and page context
        """
        with fitz.open(str(pdf_path)) as doc:
            if page_number < 1 or page_number > doc.page_count:
                return {"headers": "", "footnotes": "", "page_text": ""}

            page = doc[page_number - 1]
            full_text = page.get_text()

            headers = self._extract_headers(page, full_text)
            footnotes = self._extract_footnotes(page, full_text)

            # Increased from 500 to 3000 chars for better LLM context (Fix 2)
            page_preview = full_text[:3000] if len(full_text) > 3000 else full_text

            return {
                "headers": headers,
                "footnotes": footnotes,
                "page_text": page_preview
            }

    def _extract_headers(self, page, full_text: str) -> str:
        """Extract section headers from page (large/bold text at top)."""
        lines = full_text.split('\n')[:10]

        headers = []
        for line in lines:
            line = line.strip()
            if line and len(line) > 5 and len(line) < 100:
                if any(keyword in line.lower() for keyword in [
                    'specification', 'accuracy', 'performance',
                    'voltage', 'current', 'resistance', 'dc', 'ac'
                ]):
                    headers.append(line)

        return ' | '.join(headers[:3])

    def _extract_footnotes(self, page, full_text: str) -> str:
        """Extract footnotes from bottom of page."""
        lines = full_text.split('\n')

        footnotes = []
        for line in lines[-15:]:
            line = line.strip()
            if line and (
                line.startswith('[') or
                line.startswith('(') or
                'note' in line.lower() or
                'sinewave' in line.lower() or
                '%' in line
            ):
                footnotes.append(line)

        return ' | '.join(footnotes[:5])
"""Unit tests for MultiPassExtractor.

Tests the multi-pass extraction pipeline without making actual API calls.
Uses mocks to verify the correct flow and data handling.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

# Use src.backend.* imports to match project convention
from src.backend.llm.multipass_extractor import (
    MultiPassExtractor,
    PassConfig,
    PASS_CONFIGS,
)
from src.backend.core.models import TableSpec


# Sample test data
SAMPLE_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def sample_table():
    """Create a sample TableSpec for testing."""
    return TableSpec(
        page_number=5,
        table_index=0,
        image_bytes=SAMPLE_IMAGE_BYTES,
        page_context={"headers": "DC Voltage Specifications"},
    )


@pytest.fixture
def sample_triage_structure_response():
    """Sample Pass 0 merged triage + structure response."""
    return {
        "is_calibration_table": True,
        "confidence": 0.95,
        "table_type": "calibration_spec",
        "skip_reason": None,
        "structure": {
            "functions_present": ["DC Voltage", "AC Voltage"],
            "column_meanings": [
                {"index": 0, "header": "Range", "meaning": "range"},
                {"index": 1, "header": "±% rdg", "meaning": "accuracy_reading"},
                {"index": 2, "header": "±% range", "meaning": "accuracy_range"},
            ],
            "time_period_location": "columns",
            "accuracy_format": "split",
            "has_merged_cells": False,
            "row_grouping": "function_groups",
            "structure_notes": [],
        },
    }


@pytest.fixture
def sample_raw_response():
    """Sample Pass 1 raw extraction response (was pass2)."""
    return {
        "raw_rows": [
            {
                "row_header": "320.000 mV",
                "function_group": "DC Voltage",
                "cells": [
                    {"column_index": 0, "value": "320.000 mV"},
                    {"column_index": 1, "value": "0.0035%"},
                    {"column_index": 2, "value": "0.0005%"},
                ],
                "time_period": "90d",
            }
        ],
        "footnotes": [],
        "extraction_notes": [],
    }


@pytest.fixture
def sample_normalized_response():
    """Sample Pass 2 normalization response (was pass3)."""
    return {
        "function_groups": [
            {
                "base_function": "DC Voltage",
                "modifier": None,
                "ranges": [
                    {
                        "range_value": "320 mV",
                        "frequency_band": None,
                        "resolution": None,
                        "resolution_unit": None,
                        "specifications": [
                            {
                                "time_period": "90d",
                                "accuracy_reading": "0.0035%",
                                "accuracy_range": "0.0005%",
                                "floor": "0",
                            }
                        ],
                    }
                ],
            }
        ],
        "extraction_notes": [],
        "metadata": {"confidence": 0.9, "table_quality": "good"},
    }


class TestPassConfigs:
    """Tests for pass configuration constants."""

    def test_pass0_config(self):
        """Pass 0 should use nano model with low reasoning for merged triage+structure."""
        config = PASS_CONFIGS["pass0"]
        assert config.model == "nano"
        assert config.reasoning_effort == "low"
        assert config.name == "triage_structure"
        assert config.schema_name == "pass0_triage_structure"

    def test_pass1_config(self):
        """Pass 1 should use nano model with low reasoning for raw extraction."""
        config = PASS_CONFIGS["pass1"]
        assert config.model == "nano"
        assert config.reasoning_effort == "low"
        assert config.name == "raw"

    def test_pass2_config(self):
        """Pass 2 should use mini model with medium reasoning for normalization."""
        config = PASS_CONFIGS["pass2"]
        assert config.model == "mini"
        assert config.reasoning_effort == "medium"
        assert config.name == "normalize"

    def test_only_three_passes(self):
        """Should have exactly 3 passes in the 3-pass system."""
        assert len(PASS_CONFIGS) == 3
        assert "pass0" in PASS_CONFIGS
        assert "pass1" in PASS_CONFIGS
        assert "pass2" in PASS_CONFIGS
        assert "pass3" not in PASS_CONFIGS  # No pass3 in 3-pass system

    def test_all_passes_have_schemas(self):
        """All passes should have schema names defined."""
        for pass_id, config in PASS_CONFIGS.items():
            assert config.schema_name, f"Pass {pass_id} missing schema_name"

    def test_all_passes_have_prompts(self):
        """All passes should have prompt file names defined."""
        for pass_id, config in PASS_CONFIGS.items():
            assert config.prompt_file, f"Pass {pass_id} missing prompt_file"


class TestMultiPassExtractorInit:
    """Tests for MultiPassExtractor initialization."""

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_init_default_concurrency(self, mock_schema_loader):
        """Default max_concurrent should be 5."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }
        extractor = MultiPassExtractor()
        assert extractor.max_concurrent == 5

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_init_capped_concurrency(self, mock_schema_loader):
        """max_concurrent should be capped at 5."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }
        extractor = MultiPassExtractor(max_concurrent=10)
        assert extractor.max_concurrent == 5

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_init_with_progress_callback(self, mock_schema_loader):
        """Should accept progress callback."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }
        callback = MagicMock()
        extractor = MultiPassExtractor(progress_callback=callback)
        assert extractor.progress_callback == callback


class TestMultiPassExtractorExtraction:
    """Tests for the extraction pipeline."""

    @pytest.mark.asyncio
    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    async def test_extract_empty_tables(self, mock_schema_loader):
        """Should handle empty table list gracefully."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }
        extractor = MultiPassExtractor()

        result = await extractor.extract_from_tables([])

        assert result["function_groups"] == []
        assert "No tables provided" in result["extraction_notes"]


class TestProgressCallback:
    """Tests for progress reporting."""

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_progress_callback_called(self, mock_schema_loader):
        """Progress callback should be called when reporting progress."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }

        callback = MagicMock()
        extractor = MultiPassExtractor(progress_callback=callback)

        # Report progress manually (simulating internal calls)
        extractor._report_progress("pass0", 1, 1, "Triage + Structure")
        extractor._report_progress("pass1", 1, 1, "Raw")
        extractor._report_progress("pass2", 1, 1, "Normalize")

        assert callback.call_count == 3

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_progress_callback_error_handling(self, mock_schema_loader):
        """Should handle callback errors gracefully."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }

        callback = MagicMock(side_effect=Exception("Callback error"))
        extractor = MultiPassExtractor(progress_callback=callback)

        # Should not raise
        extractor._report_progress("pass0", 1, 1, "Triage + Structure")


class TestResultMerging:
    """Tests for result merging."""

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_merge_empty_results(self, mock_schema_loader):
        """Should handle empty results list."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }
        extractor = MultiPassExtractor()

        result = extractor._merge_results([])

        assert result["function_groups"] == []
        assert result["extraction_notes"] == []

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_merge_multiple_results(self, mock_schema_loader):
        """Should merge function groups from multiple tables."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }
        extractor = MultiPassExtractor()

        results = [
            {
                "function_groups": [{"base_function": "DC Voltage"}],
                "extraction_notes": ["Note 1"],
            },
            {
                "function_groups": [{"base_function": "AC Voltage"}],
                "extraction_notes": ["Note 2"],
            },
        ]

        merged = extractor._merge_results(results)

        assert len(merged["function_groups"]) == 2
        assert len(merged["extraction_notes"]) == 2


@pytest.fixture
def multi_interval_structure():
    """Structure with multiple time_period columns."""
    return {
        "functions_present": ["DC Voltage"],
        "column_meanings": [
            {"index": 0, "header": "Range", "meaning": "range"},
            {"index": 1, "header": "24h", "meaning": "time_period"},
            {"index": 2, "header": "90 Days", "meaning": "time_period"},
            {"index": 3, "header": "1 Year", "meaning": "time_period"},
        ],
        "time_period_location": "columns",
        "accuracy_format": "split",
        "has_merged_cells": False,
        "row_grouping": "flat",
        "structure_notes": [],
    }


@pytest.fixture
def multi_interval_raw_data():
    """Raw data with values for multiple time periods."""
    return {
        "raw_rows": [
            {
                "row_header": "10 V",
                "function_group": "DC Voltage",
                "cells": [
                    {"column_index": 0, "value": "10 V"},
                    {"column_index": 1, "value": "0.003%"},
                    {"column_index": 2, "value": "0.005%"},
                    {"column_index": 3, "value": "0.010%"},
                ],
                "time_period": None,
            }
        ],
        "footnotes": [],
        "extraction_notes": [],
    }


class TestMultiIntervalSupport:
    """Tests for multi-interval extraction support."""

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_pass2_prompt_includes_multi_interval_guidance(self, mock_schema_loader):
        """Pass 2 prompt should include multi-interval extraction guidance."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }
        extractor = MultiPassExtractor()
        prompt_config = extractor.prompts.get("pass2", {})
        system_prompt = prompt_config.get("system_prompt", "")

        assert "MULTI-INTERVAL TABLES" in system_prompt
        assert "time_period_location" in system_prompt
        assert "column_index" in system_prompt

    @patch("src.backend.llm.multipass_extractor.SchemaLoader")
    def test_pass2_user_prompt_includes_multi_interval_reminder(self, mock_schema_loader):
        """Pass 2 user prompt should include multi-interval reminder."""
        mock_schema_loader.return_value.load_schema.return_value = {
            "type": "function",
            "name": "test",
        }
        extractor = MultiPassExtractor()
        prompt_config = extractor.prompts.get("pass2", {})
        user_template = prompt_config.get("user_prompt_template", "")

        assert "time_period_location" in user_template
        assert "ONE specification per" in user_template

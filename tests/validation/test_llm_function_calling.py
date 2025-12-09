"""Test script for GPT-5 function calling implementation."""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path before any imports
project_root = Path(__file__).parent.parent.parent
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))

from backend.llm.client import GPT5Client, get_client
from backend.config.prompts.prompt_loader import PromptLoader

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_function_calling():
    """Test the function calling implementation with a sample table."""

    # Sample table data simulating OCR output
    sample_table = """
    DC Voltage Specifications
    Range         24 Hour        90 Day         1 Year
    100.0 mV     0.0010 + 0.0005  0.0015 + 0.0006  0.0020 + 0.0007
    1.000 V      0.0008 + 0.0003  0.0012 + 0.0004  0.0018 + 0.0005
    10.00 V      0.0007 + 0.0002  0.0010 + 0.0003  0.0015 + 0.0004
    100.0 V      0.0009 + 0.0004  0.0013 + 0.0005  0.0019 + 0.0006
    1000 V       0.0010 + 0.0005  0.0015 + 0.0006  0.0020 + 0.0007

    AC Voltage Specifications (True RMS)
    Range         Frequency      24 Hour        90 Day         1 Year
    100.0 mV     45Hz-1kHz      0.020 + 0.005  0.025 + 0.006  0.030 + 0.007
    100.0 mV     1kHz-100kHz    0.030 + 0.008  0.035 + 0.009  0.040 + 0.010
    1.000 V      45Hz-1kHz      0.018 + 0.004  0.022 + 0.005  0.028 + 0.006
    """

    try:
        # Get client instance
        client = await get_client()

        # Load prompt configuration
        prompt_loader = PromptLoader()
        prompt_config = prompt_loader.load_prompt("universal")
        system_prompt = prompt_config["system_prompt"]

        # Format user prompt
        user_prompt = prompt_loader.format_user_prompt(
            "universal",
            ocr_text=sample_table,
            instrument_type="Digital Multimeter"
        )

        # Combine prompts
        full_input = f"{system_prompt}\n\n{user_prompt}"

        logger.info("Testing function calling with sample table...")

        # Test the function calling
        result = await client.extract_calibration_specs(
            input_text=full_input,
            model="mini"
        )

        # Display results
        logger.info("Function calling successful!")
        print("\n" + "="*60)
        print("EXTRACTED SPECIFICATIONS")
        print("="*60)
        print(json.dumps(result, indent=2))
        print("="*60)

        # Validate structure
        assert "function_groups" in result, "Missing function_groups"
        assert isinstance(result["function_groups"], list), "function_groups should be a list"

        if result["function_groups"]:
            first_group = result["function_groups"][0]
            assert "base_function" in first_group, "Missing base_function"
            assert "ranges" in first_group, "Missing ranges"

            if first_group["ranges"]:
                first_range = first_group["ranges"][0]
                assert "range_value" in first_range, "Missing range_value"
                assert "specifications" in first_range, "Missing specifications"

                if first_range["specifications"]:
                    first_spec = first_range["specifications"][0]
                    assert "time_period" in first_spec, "Missing time_period"
                    assert "accuracy_reading" in first_spec, "Missing accuracy_reading"
                    assert "accuracy_range" in first_spec, "Missing accuracy_range"

        logger.info("All structure validations passed!")
        return result

    except Exception as e:
        logger.error(f"Test failed: {type(e).__name__}: {e}")
        raise


async def test_backward_compatibility():
    """Test backward compatibility functions."""
    from backend.llm.client import call_mini_json_async

    sample_input = """Extract specifications from this table:
    DC Voltage: 100mV range, 1 year accuracy: 0.002% + 0.0007%"""

    try:
        logger.info("Testing backward compatibility...")

        # Load prompt for proper formatting
        prompt_loader = PromptLoader()
        prompt_config = prompt_loader.load_prompt("universal")
        system_prompt = prompt_config["system_prompt"]

        # Call using backward compatible function
        result_json = await call_mini_json_async(system_prompt, sample_input)
        result = json.loads(result_json)

        logger.info("Backward compatibility test successful!")
        print("\n" + "="*60)
        print("BACKWARD COMPATIBILITY RESULT")
        print("="*60)
        print(json.dumps(result, indent=2))
        print("="*60)

        return result

    except Exception as e:
        logger.error(f"Backward compatibility test failed: {e}")
        raise


async def main():
    """Run all tests."""
    print("\n" + "#"*60)
    print("# GPT-5 FUNCTION CALLING TEST SUITE")
    print("#"*60)

    try:
        # Test 1: Function calling
        print("\n[TEST 1] Testing function calling implementation...")
        await test_function_calling()
        print("✓ Function calling test passed")

        # Test 2: Backward compatibility
        print("\n[TEST 2] Testing backward compatibility...")
        await test_backward_compatibility()
        print("✓ Backward compatibility test passed")

        print("\n" + "#"*60)
        print("# ALL TESTS PASSED SUCCESSFULLY!")
        print("#"*60)

    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
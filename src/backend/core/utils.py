"""Utility functions for merging extraction results."""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def merge_extraction_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge multiple LLM extraction results into a single result.
    
    Args:
        results: List of extraction result dictionaries
        
    Returns:
        Merged extraction result
    """
    if not results:
        return {"function_groups": [], "extraction_notes": ["No results to merge"]}
    
    # Collect all function groups
    all_function_groups = []
    all_notes = []
    
    for result in results:
        if not isinstance(result, dict):
            logger.warning(f"Skipping non-dict result: {type(result)}")
            continue
            
        # Extract function groups
        function_groups = result.get("function_groups", [])
        if isinstance(function_groups, list):
            all_function_groups.extend(function_groups)
        else:
            logger.warning(f"Invalid function_groups type: {type(function_groups)}")
            
        # Extract notes
        notes = result.get("extraction_notes", [])
        if isinstance(notes, list):
            all_notes.extend(notes)
        elif isinstance(notes, str):
            all_notes.append(notes)
    
    # Sort function groups for deterministic output
    sorted_function_groups = sorted(
        all_function_groups, 
        key=lambda x: (
            x.get("base_function", "") or "",
            x.get("modifier", "") or ""  # Handle None values
        )
    )
    
    return {
        "function_groups": sorted_function_groups,
        "extraction_notes": sorted(list(set(all_notes)))
    }


def deduplicate_functions(extraction_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deduplicate functions by exact signature match and merge ranges.

    Args:
        extraction_results: List of extraction result dictionaries

    Returns:
        Deduplicated extraction result
    """
    if not extraction_results:
        return {"function_groups": [], "extraction_notes": ["No results to deduplicate"]}

    all_functions = []
    all_notes = []

    for result in extraction_results:
        if not isinstance(result, dict):
            logger.warning(f"Skipping non-dict result: {type(result)}")
            continue

        function_groups = result.get("function_groups", [])
        if isinstance(function_groups, list):
            all_functions.extend(function_groups)

        notes = result.get("extraction_notes", [])
        if isinstance(notes, list):
            all_notes.extend(notes)
        elif isinstance(notes, str):
            all_notes.append(notes)

    groups = defaultdict(list)

    for func in all_functions:
        if not isinstance(func, dict):
            continue

        base = func.get("base_function", "")
        mod = func.get("modifier") or ""

        # Case-insensitive deduplication to avoid "Voltage AC" vs "Voltage, AC" duplicates (Fix 3)
        sig = (base.lower().strip(), (mod or "").lower().strip())
        groups[sig].append(func)

    deduplicated = []
    duplicate_count = 0

    for (base, mod), funcs in groups.items():
        if len(funcs) == 1:
            deduplicated.append(funcs[0])
        else:
            duplicate_count += len(funcs) - 1
            logger.info(f"Merging {len(funcs)} instances of {base} | {mod}")

            merged = {
                "base_function": base,
                "modifier": mod,
                "ranges": []
            }

            all_ranges = []
            for f in funcs:
                all_ranges.extend(f.get("ranges", []))

            unique_ranges = _deduplicate_ranges(all_ranges)
            merged["ranges"] = unique_ranges

            deduplicated.append(merged)

    notes = sorted(list(set(all_notes)))
    if duplicate_count > 0:
        notes.append(f"Deduplicated {duplicate_count} duplicate functions")

    return {
        "function_groups": deduplicated,
        "extraction_notes": notes
    }


def _deduplicate_ranges(ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate ranges by signature, merging specifications.

    Args:
        ranges: List of range dictionaries

    Returns:
        Deduplicated ranges
    """
    seen = {}

    for r in ranges:
        sig = _range_signature(r)

        if sig not in seen:
            seen[sig] = r
        else:
            existing = seen[sig]
            new_specs = r.get("specifications", [])
            existing_specs = existing.get("specifications", [])

            merged_specs = _merge_specifications(existing_specs, new_specs)
            existing["specifications"] = merged_specs

    return list(seen.values())


def _range_signature(range_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Create hashable range signature.

    Args:
        range_data: Range dictionary

    Returns:
        Tuple of (range_value, frequency_band)
    """
    return (
        range_data.get("range_value", ""),
        range_data.get("frequency_band") or ""
    )


def _merge_specifications(
    specs1: List[Dict[str, Any]],
    specs2: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge specification lists, avoiding duplicates.

    Args:
        specs1: First list of specifications
        specs2: Second list of specifications

    Returns:
        Merged specification list
    """
    seen = {}

    for spec in specs1 + specs2:
        time_period = spec.get("time_period", "")

        if time_period not in seen:
            seen[time_period] = spec
        else:
            existing = seen[time_period]
            for key in ["accuracy_reading", "accuracy_range"]:
                if key in spec and not existing.get(key):
                    existing[key] = spec[key]

    return list(seen.values())
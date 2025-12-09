#!/usr/bin/env python
"""Quick test for extraction pipeline - supports MSF and ACC output."""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backend.core.models import InstrumentInfo
from backend.core.pipeline import Pipeline


async def main():
    parser = argparse.ArgumentParser(description="Quick extraction test")
    parser.add_argument("pdf", nargs="?", default="data/baseline/multimeter_34401A_Agilent.pdf",
                        help="Path to PDF file")
    parser.add_argument("--format", "-f", choices=["msf", "acc"], default="msf",
                        help="Output format (default: msf)")
    parser.add_argument("--output", "-o", help="Output path (default: auto-generated)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return

    # Generate output path if not specified
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("Data/test_output") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else output_dir / f"{pdf_path.stem}.{args.format}"

    print(f"=" * 60)
    print(f"Quick Extraction Test")
    print(f"=" * 60)
    print(f"PDF:    {pdf_path.name}")
    print(f"Format: {args.format.upper()}")
    print(f"Output: {output_path}")
    print(f"=" * 60)

    # Initialize pipeline
    pipeline = Pipeline(llm_model="mini", output_formats=[args.format])

    # Run extraction
    result = await pipeline.process_async(
        pdf_path=pdf_path,
        output_path=output_path,
        instrument_info=InstrumentInfo()
    )

    if result["success"]:
        print(f"\n[OK] Success!")
        print(f"  Pages analyzed: {result['statistics'].get('pages_analyzed', 0)}")
        print(f"  Tables processed: {result['statistics'].get('tables_processed', 0)}")
        print(f"  Functions extracted: {result['statistics'].get('functions_extracted', 0)}")
        print(f"\nOutput files:")
        for fmt, path in result.get("output_files", {}).items():
            print(f"  {fmt}: {path}")
        print(f"\nDebug: Check Data/multipass_debug/ for pass-by-pass output")
    else:
        print(f"\n[FAIL] Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())

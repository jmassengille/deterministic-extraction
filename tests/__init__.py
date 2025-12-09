"""Test suite initialization - ensures src is in path."""

import sys
from pathlib import Path

# Add src to path at package initialization (before test collection)
project_root = Path(__file__).parent.parent
src_dir = project_root / "src"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

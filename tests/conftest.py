"""Pytest configuration for test suite."""

import sys
from pathlib import Path

# Get paths
project_root = Path(__file__).parent.parent
src_dir = project_root / "src"

# Add paths before any test imports
# Order matters: src first for "backend.*" imports, then project root for "src.*" imports
# This needs to happen at import time, not just in pytest_configure
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """Called after command line options have been parsed."""
    # Ensure paths are set (may be called before module-level code in some cases)
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

"""Pytest configuration for LLM tests - ensures paths are set up correctly."""

import sys
from pathlib import Path

# Get paths - this conftest is at tests/backend/llm/
project_root = Path(__file__).parent.parent.parent.parent
src_dir = project_root / "src"

# Add paths BEFORE any project imports can happen
# src must come first so "backend.*" imports work
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

#!/usr/bin/env python3
"""Proper API server startup script."""

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    import uvicorn

    # Run the server using import string for reload to work
    uvicorn.run(
        "web.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(src_path)]
    )
"""Vercel entry point — re-exports the FastAPI app for @vercel/python."""

import sys
from pathlib import Path

# Add project root to sys.path so `import snipgen` and `import webapp` resolve.
sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp.app import app  # noqa: E402 — must come after sys.path fix

__all__ = ["app"]

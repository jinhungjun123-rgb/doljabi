"""Vercel entry: the same app as `uvicorn app.api:app`, run as one Python function (settings: vercel.json).

ragbot is imported from this repo's src/ (an installed copy would look for config.yaml in site-packages),
and the LLM cache is off so that nothing a user types is written to disk.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
os.environ.setdefault("CACHE_MODE", "nostore")

from app.api import app  # noqa: E402

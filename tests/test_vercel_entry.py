"""The Vercel entry (api/index.py) serves the same app, from this repo's src/, with nothing stored on disk."""
import importlib.util
import os
from pathlib import Path

from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def load_entry():
    spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vercel_entry_serves_the_api():
    client = TestClient(load_entry().app)
    assert client.get("/api/health").json()["ok"] is True
    assert client.get("/api/programs").json()["programs"]


def test_vercel_entry_turns_the_llm_cache_off(monkeypatch):
    monkeypatch.setenv("CACHE_MODE", "unset")   # recorded, so the variable is restored after the test
    monkeypatch.delenv("CACHE_MODE")
    load_entry()
    assert os.environ["CACHE_MODE"] == "nostore"

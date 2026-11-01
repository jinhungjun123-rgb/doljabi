"""Model API wrapper: chat (LLM), embed, rerank, with an on-disk cache.

Works with any OpenAI-compatible server; endpoints and model names come from .env.

CACHE_MODE (env)
- live    (default): call the API and store results in .cache/. If a call fails, fall back to the cache.
- offline          : never call the API; cache only.
- nostore          : call the API and keep nothing on disk (apps that receive personal information).
"""
import hashlib
import json
import os
import re

import httpx
from dotenv import load_dotenv
from openai import OpenAI

from ragbot.config import CACHE_DIR, ROOT

load_dotenv(ROOT / ".env")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-14b")
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL") or LLM_BASE_URL
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
RERANK_BASE_URL = os.getenv("RERANK_BASE_URL") or LLM_BASE_URL
RERANK_MODEL = os.getenv("RERANK_MODEL", "bge-reranker-v2-m3")
NO_THINK = os.getenv("NO_THINK", "1") == "1"
CACHE_MODE = os.getenv("CACHE_MODE", "live")
TIMEOUT = float(os.getenv("TIMEOUT", "60"))
_API_KEY = os.getenv("LLM_API_KEY", "EMPTY")


def describe() -> str:
    return (f"LLM={LLM_MODEL} @ {LLM_BASE_URL or '(not set)'} · EMBED={EMBED_MODEL} · "
            f"RERANK={RERANK_MODEL} · cache={CACHE_MODE}")


def cached(kind: str, payload, fn):
    """Return fn() and store it under a key derived from payload. Also used by the web search layer."""
    if CACHE_MODE == "nostore":
        return fn()
    CACHE_DIR.mkdir(exist_ok=True)
    key = hashlib.sha1(json.dumps([kind, payload], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    path = CACHE_DIR / f"{kind}_{key}.json"
    if CACHE_MODE == "offline":
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        raise RuntimeError(f"CACHE_MODE=offline but no cache entry: {path.name}")
    try:
        out = fn()
    except Exception:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        raise
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def _client(base_url: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=_API_KEY, timeout=TIMEOUT, max_retries=1)


# ---------------------------------------------------------------- LLM
_THINK = re.compile(r"<think>.*?</think>\s*", re.S)
_TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def chat(messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.0) -> dict:
    """Returns {"content": str, "tool_calls": [{"id", "name", "arguments" (JSON string)}]}"""
    msgs = [dict(m) for m in messages]
    if NO_THINK:  # Qwen3: turn thinking mode off by appending /no_think to the last user message
        for m in reversed(msgs):
            if m["role"] == "user":
                m["content"] = m["content"] + " /no_think"
                break

    def call():
        kwargs = {"model": LLM_MODEL, "messages": msgs, "temperature": temperature}
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
        msg = _client(LLM_BASE_URL).chat.completions.create(**kwargs).choices[0].message
        return {
            "content": _THINK.sub("", msg.content or "").strip(),
            "tool_calls": [{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                           for tc in (msg.tool_calls or [])],
        }

    out = cached("chat", {"model": LLM_MODEL, "messages": msgs, "tools": tools, "t": temperature}, call)
    if tools and not out["tool_calls"] and "<tool_call>" in out["content"]:
        out = _parse_text_tool_calls(out["content"])
    return out


def _parse_text_tool_calls(content: str) -> dict:
    """Parse Qwen-style <tool_call>{...}</tool_call> text that the server's tool parser missed."""
    calls = []
    for n, m in enumerate(_TOOL_CALL.finditer(content)):
        obj = json.loads(m.group(1))
        calls.append({"id": f"call_text_{n}", "name": obj["name"],
                      "arguments": json.dumps(obj.get("arguments") or {}, ensure_ascii=False)})
    return {"content": _TOOL_CALL.sub("", content).strip(), "tool_calls": calls}


# ---------------------------------------------------------------- embeddings
def embed(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        def call(batch=batch):
            res = _client(EMBED_BASE_URL).embeddings.create(model=EMBED_MODEL, input=batch)
            return [d.embedding for d in res.data]

        vecs += cached("embed", {"model": EMBED_MODEL, "texts": batch}, call)
    return vecs


# ---------------------------------------------------------------- reranker
def rerank(query: str, documents: list[str]) -> list[float]:
    """Relevance score per document, in input order (handles vLLM/Jina/Cohere and TEI response shapes)."""

    def call():
        r = httpx.post(
            RERANK_BASE_URL.rstrip("/") + "/rerank",
            headers={"Authorization": f"Bearer {_API_KEY}"},
            json={"model": RERANK_MODEL, "query": query, "documents": documents, "texts": documents},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        items = data["results"] if isinstance(data, dict) else data
        scores = [0.0] * len(documents)
        for it in items:
            scores[it["index"]] = it.get("relevance_score", it.get("score"))
        return scores

    return cached("rerank", {"model": RERANK_MODEL, "q": query, "docs": documents}, call)

"""Mobile web app server.  Run from the project root:  uvicorn app.api:app --port 8000

  GET  /               the screens in web/ (HTML, CSS, JS; no build step)
  GET  /api/programs   reviewed programs and centers (data/programs/programs.json)
  POST /api/match      {"profile"} → card status per program, from the domain rules (no LLM)
  POST /api/chat       {"question", "history", "profile", "lang"} → server-sent events: progress…, answer | error
  GET  /api/health     {"ok", "index"}

Personal information stays out of the server's disk: traces are off here; run with CACHE_MODE=nostore.
"""
import json
import queue
import re
import threading
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ragbot.config import INDEX_DIR
from ragbot.domain.eligibility import match, profile_summary
from ragbot.domain.programs import load_programs

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
CHAT_TIMEOUT = 90   # seconds before the stream ends with an error event
CITATION = re.compile(r"\s*\[Source:\s*([^\]]+)\]")
ARTICLE = re.compile(r"제\d+조(?:의\d+)?")


async def _body(request: Request) -> dict | None:
    """The JSON object sent by the screen, or None if it is not valid UTF-8 JSON."""
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _bad_request() -> JSONResponse:
    return JSONResponse({"error": "bad request"}, status_code=400)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _passages(ans) -> list[dict]:
    return [p for t in ans.tool_calls if t["name"] == "search_documents" and isinstance(t.get("result"), list)
            for p in t["result"] if isinstance(p, dict)]


def _chip(label: str, passages: list[dict]) -> dict:
    """A citation chip; text = the cited passage, matched by article number and document name."""
    m = ARTICLE.search(label)
    if not m:
        return {"label": label, "text": None}
    doc = label[:m.start()].strip()
    hits = [p for p in passages if m.group(0) in p.get("section", "")]
    exact = [p for p in hits if p["section"].split(" > ")[0] == doc]
    best = (exact or hits or [None])[0]
    return {"label": label, "text": best["text"][:300] if best else None}


def present(ans) -> dict:
    """Answer text without [Source: …] tags, plus document chips and web URLs taken from those tags."""
    chips, web = [], []
    for tag in CITATION.findall(ans.answer):
        tag = tag.strip()
        if tag.startswith("web"):
            url = tag[3:].strip(" :,")
            if url and url not in web:
                web.append(url)
            continue
        label = tag.split(",", 1)[1].strip() if "," in tag else tag
        if label not in [c["label"] for c in chips]:
            chips.append(_chip(label, _passages(ans)))
    return {"answer": CITATION.sub("", ans.answer).strip(), "chips": chips, "web": web}


def create_app(bot_factory=None) -> Starlette:
    data = load_programs()
    state = {"bot": None}
    lock = threading.Lock()

    def bot():
        with lock:
            if state["bot"] is None:
                if bot_factory is None:
                    from ragbot.agent import Chatbot
                    state["bot"] = Chatbot(write_traces=False)
                else:
                    state["bot"] = bot_factory()
            return state["bot"]

    async def programs(_: Request):
        return JSONResponse(data)

    async def match_route(request: Request):
        body = await _body(request)
        if body is None:
            return _bad_request()
        return JSONResponse(match(body.get("profile") or {}, data))

    async def health(_: Request):
        return JSONResponse({"ok": True, "index": INDEX_DIR.exists() and any(INDEX_DIR.iterdir())})

    async def chat(request: Request):
        body = await _body(request)
        question = str((body or {}).get("question") or "").strip()
        if body is None or not question:
            return _bad_request()
        history = [m for m in body.get("history") or [] if m.get("role") in ("user", "assistant")][-6:]
        context = profile_summary(body["profile"]) if body.get("profile") else None
        events: queue.Queue = queue.Queue()

        def run():
            try:
                ans = bot().answer(question, history, context=context,
                                   on_progress=lambda step, d: events.put(("progress", {"step": step, **d})))
                events.put(("answer", present(ans)))
            except Exception:   # the screen shows a fallback with phone numbers; details stay in the server log
                events.put(("error", {"message": "unavailable"}))
            events.put(None)

        def stream():
            threading.Thread(target=run, daemon=True).start()
            deadline = time.monotonic() + CHAT_TIMEOUT
            while True:
                try:
                    item = events.get(timeout=max(0.1, deadline - time.monotonic()))
                except queue.Empty:
                    yield _sse("error", {"message": "unavailable"})
                    return
                if item is None:
                    return
                yield _sse(*item)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    return Starlette(routes=[
        Route("/api/programs", programs), Route("/api/match", match_route, methods=["POST"]),
        Route("/api/chat", chat, methods=["POST"]), Route("/api/health", health),
        Mount("/", StaticFiles(directory=WEB_DIR, html=True)),
    ])


app = create_app()

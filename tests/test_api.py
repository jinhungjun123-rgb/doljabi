"""App API (app/api.py) with a fake chatbot: no LLM calls."""
import json
import sys
from pathlib import Path

from starlette.testclient import TestClient

from ragbot.schemas import Answer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.api import create_app  # noqa: E402


class FakeBot:
    last_context = None

    def answer(self, question, history=None, context=None, on_progress=None):
        FakeBot.last_context = context
        on_progress("route", {"primary": "docs"})
        on_progress("tool", {"name": "search_documents"})
        on_progress("write", {})
        return Answer(answer="나이는 34세까지예요. [Source: gov ko p.2, 위기아동청년법 시행령 제11조] "
                             "[Source: web https://example.go.kr/a]",
                      tool_calls=[{"name": "search_documents", "arguments": {}, "result": [
                          {"source": "gov ko p.2", "section": "위기아동청년법 시행령 > 제11조(자기돌봄비)", "text": "① 기준은 다음과 같다"}]}])


class BrokenBot:
    def answer(self, *a, **k):
        raise RuntimeError("LLM down")


def events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_match_and_programs():
    c = TestClient(create_app(bot_factory=FakeBot))
    assert len(c.get("/api/programs").json()["programs"]) == 14
    r = c.post("/api/match", json={"profile": {"age": 20, "region": "충북"}}).json()
    assert r["center"]["phone"] == "1551-1259" and r["cards"]


def test_chat_stream():
    body = TestClient(create_app(bot_factory=FakeBot)).post(
        "/api/chat", json={"question": "q", "profile": {"age": 20}}).text
    evs = events(body)
    assert [e for e, _ in evs] == ["progress", "progress", "progress", "answer"]
    ans = evs[-1][1]
    assert "[Source" not in ans["answer"] and ans["answer"].startswith("나이는 34세")
    assert ans["chips"][0]["label"].endswith("제11조") and ans["chips"][0]["text"].startswith("①")
    assert ans["web"] == ["https://example.go.kr/a"]
    assert FakeBot.last_context and "20세" in FakeBot.last_context


def test_chat_without_profile_sends_no_context():
    TestClient(create_app(bot_factory=FakeBot)).post("/api/chat", json={"question": "q"})
    assert FakeBot.last_context is None


def test_chat_error_event():
    body = TestClient(create_app(bot_factory=BrokenBot)).post("/api/chat", json={"question": "q"}).text
    assert events(body)[-1] == ("error", {"message": "unavailable"})


def test_bad_request_body_is_400():
    c = TestClient(create_app(bot_factory=FakeBot))
    for path in ("/api/chat", "/api/match"):
        r = c.post(path, content="질문".encode("cp949"), headers={"content-type": "application/json"})
        assert r.status_code == 400
    assert c.post("/api/chat", json={"question": "  "}).status_code == 400


def test_health_and_static_home():
    c = TestClient(create_app(bot_factory=FakeBot))
    assert c.get("/api/health").json()["ok"] is True
    assert "돌잡이" in c.get("/").text

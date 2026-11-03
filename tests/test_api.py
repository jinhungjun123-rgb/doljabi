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
    assert len(c.get("/api/programs").json()["programs"]) == 13
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


def test_wrong_types_in_requests_do_not_break_the_server():
    c = TestClient(create_app(bot_factory=FakeBot))
    assert c.post("/api/match", json={"profile": {"age": "20", "conditions": 5}}).status_code == 200
    assert c.post("/api/match", json={"profile": "x"}).status_code == 200
    r = c.post("/api/chat", json={"question": "q", "history": ["x", {"role": "user", "content": "a"}], "profile": "x"})
    assert r.status_code == 200 and events(r.text)[-1][0] == "answer"


def test_chat_failure_is_logged_without_the_question(caplog):
    TestClient(create_app(bot_factory=BrokenBot)).post("/api/chat", json={"question": "비밀 질문"})
    assert "chat failed" in caplog.text and "비밀 질문" not in caplog.text


def test_only_http_links_become_web_sources():
    from app.api import present
    ans = Answer(answer="답 [Source: web javascript:alert(1)] [Source: web https://www.bokjiro.go.kr]", tool_calls=[])
    assert present(ans)["web"] == ["https://www.bokjiro.go.kr"]


def test_more_endpoint():
    c = TestClient(create_app(bot_factory=FakeBot))
    r = c.post("/api/more", json={"profile": {"age": 20, "region": "충북"}})
    assert r.status_code == 200
    out = r.json()
    items = out["ok"] + [i for g in out["maybe"] for i in g["items"]]
    assert items and all("status" in i and "conditions" in i for i in items)
    bad = c.post("/api/more", content="질문".encode("cp949"), headers={"content-type": "application/json"})
    assert bad.status_code == 400


def test_chat_about_is_cleaned():
    # 화면이 보낸 이름·링크는 쓰지 않고, 사업 번호로 서버의 정리 파일에서 찾는다
    from ragbot.domain.more import load_more
    item = load_more()["items"][0]
    c = TestClient(create_app(bot_factory=FakeBot))
    about = {"id": item["id"], "name": "가" * 500, "link": "javascript:alert(1)"}
    c.post("/api/chat", json={"question": "q", "about": about})
    assert item["name"] in FakeBot.last_context and "가가가" not in FakeBot.last_context
    assert "javascript" not in FakeBot.last_context
    for bad in ("x", {"name": "아무 사업"}, {"id": "Y:없음"}):
        c.post("/api/chat", json={"question": "q", "about": bad})
        assert FakeBot.last_context is None


def test_more_is_compressed():
    r = TestClient(create_app(bot_factory=FakeBot)).post("/api/more", json={"profile": {"age": 20}}, headers={"accept-encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


def test_backup_deploy_ships_the_app_data():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "deploy_hf.sh").read_text(encoding="utf-8")
    assert "data/programs/more.json" in script


def test_one_tag_with_several_sources_becomes_several_chips():
    # 모델이 [Source: a; b] 처럼 한 태그에 둘을 쓰면 내부 표기("gov ko p.1")가 칩 이름에 보였다
    from app.api import present
    ans = Answer(answer="답 [Source: gov ko p.3, 위기아동청년법 제13조; gov ko p.1, 위기아동청년법 시행규칙 제6조②]", tool_calls=[])
    assert [c["label"] for c in present(ans)["chips"]] == ["위기아동청년법 제13조", "위기아동청년법 시행규칙 제6조②"]

"""Agent hooks for apps: progress callback, user context in the system prompt, and a cache mode that stores nothing.
No API calls: the LLM and the router are replaced with fakes."""
from ragbot import agent, llm, router
from ragbot.config import load_config
from ragbot.tools import Context, load_all


def make_bot():
    load_all()
    bot = object.__new__(agent.Chatbot)
    bot.cfg, bot.index, bot.write_traces = load_config(), None, False
    bot.ctx = Context(None, bot.cfg)
    return bot


def test_progress_and_context(monkeypatch):
    seen, prompts = [], []
    replies = iter([{"content": "", "tool_calls": [{"id": "1", "name": "get_today", "arguments": "{}"}]},
                    {"content": "answer text", "tool_calls": []}])

    def fake_chat(messages, tools=None):
        prompts.append(messages[0]["content"])
        return next(replies)

    monkeypatch.setattr(llm, "chat", fake_chat)
    monkeypatch.setattr(router, "route", lambda *a, **k: {"primary": "docs", "fallback": [], "reason": ""})
    ans = make_bot().answer("question", context="USER_CONTEXT", on_progress=lambda step, data: seen.append(step))
    assert ans.answer == "answer text"
    assert seen == ["route", "tool", "write"]
    assert prompts[0].endswith("USER_CONTEXT")


def test_answer_without_hooks_still_works(monkeypatch):
    replies = iter([{"content": "", "tool_calls": [{"id": "1", "name": "get_today", "arguments": "{}"}]},
                    {"content": "plain", "tool_calls": []}])
    monkeypatch.setattr(llm, "chat", lambda m, tools=None: next(replies))
    monkeypatch.setattr(router, "route", lambda *a, **k: {"primary": "docs", "fallback": [], "reason": ""})
    assert make_bot().answer("question").answer == "plain"


def test_nostore_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_MODE", "nostore")
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path / "cache")
    assert llm.cached("chat", {"x": 1}, lambda: {"ok": 1}) == {"ok": 1}
    assert not (tmp_path / "cache").exists()

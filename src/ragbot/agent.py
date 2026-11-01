"""Tool-calling agent: the LLM decides which tools to call, in what order, and when to answer.

Every answer writes a trace to runs/<date>/<trace_id>.json with the full message history and tool results.
When an answer is wrong, read its trace first: it shows whether retrieval, routing or reasoning failed.
"""
import json
import re
import uuid
from collections.abc import Callable
from datetime import datetime

from ragbot import domain, llm, router
from ragbot.config import RUNS_DIR, load_config
from ragbot.index import Index, detect_lang, is_stale, load_index
from ragbot.schemas import Answer
from ragbot.tools import TOOLS, Context, load_all, spec

LANG_NAMES = {"ko": "Korean", "en": "English", "zh": "Chinese"}

# Phrases meaning "I could not find it" (en/ko/zh). Shared with evaluate.py for grading unanswerable questions.
ABSTAIN = re.compile(r"could not find|couldn't find|can't find|cannot find|"
                     r"(?:does|do|is|are) not (?:directly |explicitly )?(?:list|provide|mention|include|state|contain|specify)|"
                     r"not (?:directly |explicitly )?(?:listed|available|mentioned|included|provided|found|stated|specified)|not (?:in|available in) the|no information|no (?:specific |explicit )?mention|don't have|do not have|"
                     r"찾을 수 없|답할 수 없|확인할 수 없|정보가 없|확인되지 않|알 수 없|(?:제공|공개|명시|기재)되지 않|"
                     r"(?:나와|명시되어|기재되어|포함되어|제공되어) 있지 않|"
                     r"找不到|没有找到|无法(?:找到|确认|回答)|没有相关|未(?:提及|列出|找到)", re.I)

UNTRIED_NUDGE = ("(System check, not from the user) You are about to say the information was not found, but you have "
                 "not searched: {untried}. Search them now, in that order.{hint} Answer the user from what they "
                 "return, with sources; only if none has it, say it was not found. Do not mention this check.")

NUDGE = ("(System check, not from the user) Your reply used no tool, so it is not grounded in a source. "
         "If the user's last message asks for any information (anything beyond a greeting or small talk), call the "
         "right tool now and answer from its results. If it was only a greeting or small talk, reply to it directly "
         "and normally. Either way, answer the user; do not mention or reply to this check.")


class Chatbot:
    def __init__(self, cfg: dict | None = None, index: Index | None = None, write_traces: bool = True):
        self.cfg = cfg or load_config()
        self.index = index or load_index()
        if self.index is None or is_stale(self.index, self.cfg):
            raise RuntimeError("Document index is missing or out of date. Run: python -m ragbot build")
        problem = domain.tables_ready(self.cfg)
        if problem:
            raise RuntimeError(problem)
        load_all()
        unknown = [t for t in self.cfg["agent"]["tools"] if t not in TOOLS]
        if unknown:
            raise ValueError(f"config.yaml agent.tools lists unregistered tools: {unknown}")
        self.ctx = Context(self.index, self.cfg)
        self.write_traces = write_traces

    def system_prompt(self, plan: dict | None = None, question: str = "", context: str | None = None) -> str:
        c = self.cfg["chatbot"]
        prompt = c["system_prompt"].format(name=c["name"], today=c["today"])
        if question:   # short questions often got answers in the wrong language without this
            prompt += f"\nThe user wrote in {LANG_NAMES[detect_lang(question)]}. Write your answer in that language."
        if plan:
            fb = ", ".join(plan["fallback"]) or "none"
            prompt += (f"\nRouting plan for this question: primary source = {plan['primary']}; "
                       f"fallback = {fb}. Reason: {plan['reason']}")
        if context:   # e.g. the user's situation entered in an app; never stored by the agent
            prompt += "\n" + context
        return prompt

    def plan(self, question: str, history: list[dict] | None = None) -> dict | None:
        if not self.cfg.get("router", {}).get("enabled"):
            return None
        return router.route(question, self.cfg, self.index, history)

    def tools_for(self, plan: dict | None) -> list[dict]:
        """All enabled tools, ordered: primary source, fallback sources, other sources, utilities.
        The plan decides where to look FIRST; it never removes a source, so a wrong route can still recover."""
        enabled = self.cfg["agent"]["tools"]
        order = [plan["primary"], *plan["fallback"]] if plan else []
        order += [s for s in self.cfg["sources"] if s not in order]
        names = [t for src in order if src in self.cfg["sources"] for t in self.cfg["sources"][src]["tools"]]
        names += [t for t in enabled if t not in names]
        return [spec(t, self.cfg) for t in dict.fromkeys(names) if t in enabled]

    def source_of(self, tool_name: str) -> str | None:
        """The config source a tool belongs to (None = a utility such as calculator)."""
        return next((s for s, card in self.cfg["sources"].items() if tool_name in card["tools"]), None)

    def answer(self, question: str, history: list[dict] | None = None, context: str | None = None,
               on_progress: Callable[[str, dict], None] | None = None) -> Answer:
        """history: earlier turns [{"role": "user"|"assistant", "content": str}]
        context: extra text appended to the system prompt (e.g. the user's situation)
        on_progress(step, data): "route" {"primary"} after planning, "tool" {"name"} before each tool call,
                                 "write" {} before returning the final answer"""
        progress = on_progress or (lambda step, data: None)
        plan = self.plan(question, history)
        progress("route", {"primary": plan["primary"] if plan else None})
        tools = self.tools_for(plan)
        messages = [{"role": "system", "content": self.system_prompt(plan, question, context)}, *(history or []),
                    {"role": "user", "content": question}]
        ans = Answer(answer="", trace_id=datetime.now().strftime("%H%M%S-") + uuid.uuid4().hex[:6], plan=plan)
        # Guardrail 1 stays on even when the router says "none": the router sometimes labels real questions
        # as small talk, and the nudge itself lets true small talk be answered without tools.
        nudged = untried_nudged = False
        source_order = [s for s in ([plan["primary"], *plan["fallback"]] if plan else []) if s in self.cfg["sources"]]
        source_order += [s for s in self.cfg["sources"] if s not in source_order]
        for _ in range(self.cfg["agent"]["max_steps"]):
            out = llm.chat(messages, tools=tools)
            if not out["tool_calls"] and not ans.tool_calls and not nudged:
                # Guardrail 1: models often answer domain questions from memory (and invent citations).
                # Send it back once; a greeting or off-topic message can still be answered directly.
                nudged = True
                messages += [{"role": "assistant", "content": out["content"]}, {"role": "user", "content": NUDGE}]
                continue
            if not out["tool_calls"] and not untried_nudged and ans.tool_calls and ABSTAIN.search(out["content"]):
                # Guardrail 2: before "not found", every source must have been tried, in plan order. Covers both a
                # wrong route (web first for a document fact) and a right route that lacks the answer (0005, 0006).
                called = {t["name"] for t in ans.tool_calls}
                untried = [t for s in source_order for t in self.cfg["sources"][s]["tools"][:1]
                           if t in self.cfg["agent"]["tools"] and not set(self.cfg["sources"][s]["tools"]) & called]
                if untried:
                    untried_nudged = True
                    messages += [{"role": "assistant", "content": out["content"]},
                                 {"role": "user", "content": UNTRIED_NUDGE.format(
                                     untried=", ".join(untried), hint=self._hint())}]
                    continue
            if not out["tool_calls"]:
                progress("write", {})
                ans.answer = out["content"]
                break
            messages.append({"role": "assistant", "content": out["content"],
                             "tool_calls": [{"id": tc["id"], "type": "function",
                                             "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                                            for tc in out["tool_calls"]]})
            for tc in out["tool_calls"]:
                progress("tool", {"name": tc["name"]})
                args, result = self._call_tool(tc)
                ans.tool_calls.append({"name": tc["name"], "arguments": args, "result": result})
                self._collect_sources(self.source_of(tc["name"]), result, ans)
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": json.dumps(result, ensure_ascii=False, default=str)})
        else:
            ans.answer = "(Stopped: too many tool calls. Increase agent.max_steps in config.yaml.)"
        self._trace(question, messages, ans)
        return ans

    def _call_tool(self, tc) -> tuple[dict, object]:
        try:
            args = json.loads(tc["arguments"] or "{}")
        except json.JSONDecodeError:
            return {}, {"error": f"arguments are not valid JSON: {tc['arguments']}"}
        if tc["name"] not in TOOLS:
            return args, {"error": f"unknown tool: {tc['name']}"}
        try:
            return args, TOOLS[tc["name"]]["fn"](self.ctx, **args)
        except Exception as e:   # tell the model what went wrong; it usually retries with fixed arguments
            return args, {"error": f"{type(e).__name__}: {e}"}

    def _hint(self) -> str:
        hint = self.cfg["agent"].get("search_hint", "").strip()
        return f" {hint}" if hint else ""

    @staticmethod
    def _collect_sources(route: str | None, result, ans: Answer):
        items = result if isinstance(result, list) else [result]
        found = []
        for it in items:
            if isinstance(it, dict) and "error" not in it:
                found += [it["source"]] if it.get("source") else []
                found += it.get("sources") or []
        for s in found:
            if s not in ans.sources:
                ans.sources.append(s)
        if found and route and route not in ans.routes:
            ans.routes.append(route)

    def _trace(self, question, messages, ans: Answer):
        if not self.write_traces:
            return
        day_dir = RUNS_DIR / datetime.now().strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / f"{ans.trace_id}.json").write_text(
            json.dumps({"question": question, "model": llm.LLM_MODEL, "answer": ans.to_dict(), "messages": messages},
                       ensure_ascii=False, indent=1, default=str), encoding="utf-8")

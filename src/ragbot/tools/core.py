"""Generic tools. Their descriptions come from config.yaml (documents.*, web.official_domains), not from code."""
import ast
import operator
import re
from datetime import date

from ragbot import web
from ragbot.tools import Context, tool


# ---------------------------------------------------------------- documents
def _documents_description(cfg: dict) -> str:
    d = cfg["documents"]
    out = f"Search {d['description'].strip()}. Use it for: {d['use_for'].strip()} "
    if d.get("not_for"):
        out += f"Not for: {d['not_for'].strip()} "
    return out + "Returns passages with their edition language and page."


def _documents_parameters(cfg: dict) -> dict:
    langs = sorted(set(cfg["documents"]["files"].values()))
    params = {"query": {"type": "string", "description": "What to find, as short keywords in any language"}}
    if len(langs) > 1:
        params["lang"] = {"type": "string", "enum": langs,
                          "description": "Optional: search only one language edition"
                                         + (f" (the authoritative one is '{cfg['documents']['authoritative']}')"
                                            if cfg["documents"].get("authoritative") else "")}
    return params


@tool("search_documents", _documents_description, _documents_parameters, ["query"])
def search_documents(ctx: Context, query: str, lang: str | None = None):
    label = ctx.cfg["documents"]["citation"]
    hits = ctx.index.retrieve(query, ctx.cfg["retrieval"], lang)
    # documents.notes: how to read a passage the model tends to misread, attached wherever that passage is retrieved
    notes = [(re.compile(n["match"]), n["note"]) for n in ctx.cfg["documents"].get("notes") or []]
    return [{"source": f"{label} {c.lang} p.{c.page}", "section": " > ".join(c.path),   # note before text: read first
             **({"note": " ".join(n for p, n in notes if p.search(c.text))} if any(p.search(c.text) for p, _ in notes) else {}),
             "text": c.text.split("\n", 1)[-1],
             **({"warning": "OCR text from an image page; may contain recognition errors"} if c.low_confidence else {})}
            for c, _ in hits]


# ---------------------------------------------------------------- web
def _web_description(cfg: dict) -> str:
    domains = ", ".join(cfg["web"]["official_domains"][:5])
    return (f"Search the web, official sites first ({domains}, …). Use when the other sources do not answer the "
            "question, or the user asks for the latest information. Returns titles, URLs and snippets; cite the URL "
            "and tell the user to verify.")


@tool("web_search", _web_description,
      {"query": {"type": "string", "description": "Search query; use the language of the sites you expect to find"}},
      ["query"])
def web_search(ctx: Context, query: str):
    out = web.web_search(query, ctx.cfg)
    out["sources"] = [r["url"] for r in out["results"]]
    return out


# ---------------------------------------------------------------- utilities
@tool("get_today",
      "Return today's date (YYYY-MM-DD) and weekday. Use when the question depends on 'today', 'this week' or "
      "'how many days left'. Does not return any schedule; search the sources for that.")
def get_today(ctx: Context):
    d = date.fromisoformat(ctx.cfg["chatbot"]["today"])
    return {"today": d.isoformat(), "weekday": d.strftime("%A")}


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("only numbers and + - * / // % ** ( ) are allowed")


@tool("calculator",
      "Evaluate an arithmetic expression exactly. Use for any sum, difference, total, fee or count instead of "
      "calculating in your head.",
      {"expression": {"type": "string", "description": "e.g. '3*3 + 2*2' or '75000 * 6'"}},
      ["expression"])
def calculator(ctx: Context, expression: str):
    return {"result": _eval(ast.parse(expression, mode="eval").body)}

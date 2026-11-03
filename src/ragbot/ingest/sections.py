"""Turn kordoc blocks into sections with a heading path ["Section", "Subsection"].

How a document marks its structure differs per document, so the rules are pluggable (`SectionRules`).
The defaults use kordoc's headings (level 1 = section, level 2+ = subsection), which fits most documents.
A project whose documents mark sections differently supplies its own rules in `ragbot/domain/sections.py`.
Always check the result against `data/parsed/*.md` and `index/chunks.json`.
"""
import re
from dataclasses import dataclass
from typing import Callable

from ragbot.schemas import Section

START = "(front matter)"   # path of text that comes before the first section title


def clean(text: str) -> str:
    text = re.sub(r"</?u>", "", text or "")
    return text.replace("\\~", "~").strip()


def default_section_title(block: dict) -> str | None:
    """A level-1 heading starts a new section."""
    if block["type"] == "heading" and block.get("level") == 1:
        return clean(block["text"])
    return None


def default_is_subsection(text: str, block: dict) -> bool:
    """A level-2 (or deeper) heading starts a subsection."""
    return block["type"] == "heading" and (block.get("level") or 1) >= 2


@dataclass
class SectionRules:
    section_title: Callable[[dict], str | None] = default_section_title
    is_subsection: Callable[[str, dict], bool] = default_is_subsection
    # "Required documents: passport, photo" → subsection "Required documents" with body "passport, photo"
    split_inline_title: Callable[[str], tuple[str, str] | None] = lambda text: None
    # Blocks to drop before anything else, e.g. OCR'd logos or watermarks (decision 0003)
    is_noise: Callable[[dict], bool] = lambda block: False


def table_to_markdown(table: dict) -> str:
    rows = [[clean(c["text"]).replace("\n", "<br>").replace("|", "/") for c in row] for row in table["cells"]]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _is_ocr(block: dict) -> bool:
    return (block.get("style") or {}).get("fontName") == "ocr" or (block["type"] == "table" and "bbox" not in block)


def _list_children(block: dict, depth: int = 1) -> list[str]:
    """Sub-items of a list block (kordoc "children"), indented two spaces per level."""
    out = []
    for child in block.get("children") or []:
        text = clean(child.get("text", ""))
        if text:
            out.append(f"{'  ' * depth}- {text}")
        out.extend(_list_children(child, depth + 1))
    return out


def build_sections(doc: dict, rules: SectionRules | None = None) -> list[Section]:
    """doc: one parsed file from data/parsed/*.json"""
    rules = rules or SectionRules()
    low_pages = {w["page"] for w in doc.get("warnings") or [] if w.get("code") == "OCR_LOW_CONF"}
    sections: list[Section] = []
    path = [START]
    lines: list[str] = []
    start_page, low = 1, False

    def flush():
        nonlocal lines, low
        body = "\n".join(lines).strip()
        if body:
            sections.append(Section(doc["source"], doc["lang"], list(path), start_page, body, "text", low))
        lines, low = [], False

    for b in doc["blocks"]:
        page, kind = b["pageNumber"], b["type"]
        if kind == "image" or rules.is_noise(b):
            continue
        is_low = page in low_pages and _is_ocr(b)
        title = rules.section_title(b)
        if title is not None:
            flush()
            path, start_page = [title], page
            continue
        text = clean(b.get("text", ""))
        if kind in ("heading", "paragraph") and text and rules.is_subsection(text, b):
            flush()
            head, rest = rules.split_inline_title(text) or (text, "")
            path, start_page = [path[0], head.strip()], page
            if rest.strip():
                lines.append(rest.strip())
            low = low or is_low
            continue
        if kind == "table":
            md = table_to_markdown(b["table"])
            if md:
                sections.append(Section(doc["source"], doc["lang"], list(path), page, md, "table", is_low))
            continue
        if text:
            if not lines:
                start_page = page
            lines.append(f"- {text}" if kind == "list" else text)
            if kind == "list":
                lines.extend(_list_children(b))
            low = low or is_low
    flush()
    return sections

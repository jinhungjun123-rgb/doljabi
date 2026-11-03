"""Generic section detection and chunking (no API, no data needed). Tests for YOUR documents go in test_domain.py."""
from ragbot.chunking import split_lines, split_table
from ragbot.ingest.sections import build_sections


def test_split_lines_respects_size_and_keeps_lines():
    text = "\n".join(f"line {i} " + "x" * 30 for i in range(20))
    pieces = split_lines(text, 120, 40)
    assert all(len(p) <= 120 for p in pieces)
    assert all(line.startswith("line") for p in pieces for line in p.splitlines())


def test_split_table_repeats_header():
    md = "| a | b |\n| --- | --- |\n" + "\n".join(f"| {i} | {'y' * 20} |" for i in range(10))
    pieces = split_table(md, 100)
    assert len(pieces) > 1 and all(p.startswith("| a | b |\n| --- | --- |") for p in pieces)


def test_default_rules_follow_headings():
    """Without domain rules, kordoc headings define the structure (level 1 = section, level 2 = subsection)."""
    doc = {"source": "x.pdf", "lang": "en", "warnings": [], "blocks": [
        {"type": "paragraph", "text": "Intro", "pageNumber": 1},
        {"type": "heading", "level": 1, "text": "Returns", "pageNumber": 2},
        {"type": "heading", "level": 2, "text": "Deadline", "pageNumber": 2},
        {"type": "paragraph", "text": "30 days", "pageNumber": 2}]}
    secs = build_sections(doc)
    assert [s.path for s in secs] == [["(front matter)"], ["Returns", "Deadline"]]
    assert secs[1].text == "30 days"


def test_nested_list_items_are_kept():
    """kordoc puts sub-items of a list in "children"; they hold the actual conditions and must reach the index."""
    doc = {"source": "x.pdf", "lang": "en", "warnings": [], "blocks": [
        {"type": "heading", "level": 1, "text": "Rules", "pageNumber": 1},
        {"type": "list", "text": "1. Members", "pageNumber": 1, "children": [
            {"type": "list", "text": "a. live here", "pageNumber": 1, "children": [
                {"type": "list", "text": "i. since 2020", "pageNumber": 2}]},
            {"type": "list", "text": "b. pay fees", "pageNumber": 2}]}]}
    assert build_sections(doc)[0].text == "- 1. Members\n  - a. live here\n    - i. since 2020\n  - b. pay fees"

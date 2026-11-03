"""Tool registry and pure tools (no API)."""
import pytest

from ragbot.config import load_config
from ragbot.tools import TOOLS, load_all, spec
from ragbot.tools.core import calculator

load_all()
CFG = load_config()


def test_every_configured_tool_is_registered():
    assert set(CFG["agent"]["tools"]) <= set(TOOLS)


def test_every_source_tool_is_enabled():
    for name, card in CFG["sources"].items():
        assert set(card["tools"]) <= set(CFG["agent"]["tools"]), f"source {name} lists a tool not in agent.tools"


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_tool_spec_shape(name):
    s = spec(name, CFG)
    assert s["name"] == name and len(s["description"]) > 40
    params = s["parameters"]
    assert params["type"] == "object" and set(params["required"]) <= set(params["properties"])
    assert all("description" in p or "enum" in p for p in params["properties"].values())


def test_document_tool_describes_configured_documents():
    assert CFG["documents"]["description"].strip() in spec("search_documents", CFG)["description"]


def test_calculator():
    assert calculator(None, "(3*3 + 2*2) / 2")["result"] == 6.5


def test_calculator_rejects_code():
    with pytest.raises(ValueError):
        calculator(None, "__import__('os')")


class _FakeIndex:
    def __init__(self, chunks):
        self.chunks = chunks

    def retrieve(self, query, rcfg, lang=None):
        return [(c, 1.0) for c in self.chunks]


def _chunk(text):
    from ragbot.schemas import Chunk
    return Chunk(chunk_id=0, source="a.pdf", lang="ko", path=["A"], page=1, kind="text", text="[a]\n" + text)


def test_configured_reading_notes_are_attached_to_matching_passages():
    from ragbot.tools import Context
    from ragbot.tools.core import search_documents
    cfg = {**CFG, "documents": {**CFG["documents"], "notes": [{"match": r"X\s*Y", "note": "읽는 법"}]}}
    out = search_documents(Context(index=_FakeIndex([_chunk("앞 X Y 뒤"), _chunk("다른 문단")]), cfg=cfg), "q")
    assert out[0]["note"] == "읽는 법" and "note" not in out[1]


def test_age_limit_clauses_get_the_military_reading_note():
    # 조문이 "병역 기간을 가산한다"고만 써서 모델이 사용자 나이에 더하는 오독을 막는다 (docs/decisions/0011)
    import json
    from pathlib import Path
    from ragbot.tools import Context
    from ragbot.tools.core import search_documents
    from ragbot.schemas import Chunk
    chunks = [Chunk(**c) for c in json.loads(Path("index/chunks.json").read_text(encoding="utf-8"))]
    hits = [c for c in chunks if "병역의무를 이행한 기간을 가산" in c.text.replace("\n", "") or "병역의무 를 이행한 기간을 가산" in c.text]
    assert len(hits) >= 2
    out = search_documents(Context(index=_FakeIndex(hits), cfg=CFG), "q")
    assert all("연령 상한" in o.get("note", "") and "시행령 제11조①1" in o["note"] for o in out)
    other = search_documents(Context(index=_FakeIndex([c for c in chunks if "병역" not in c.text]), cfg=CFG), "q")
    assert not any("연령 상한" in o.get("note", "") for o in other)


def test_address_clauses_get_the_exception_reading_note():
    # 법 제13조①1다목(주소 일치)과 그 예외 시행규칙 제6조②: 원문이 "생계를 같이"라고만 써서 모델이 예외를 놓친다
    import json
    from pathlib import Path
    from ragbot.tools import Context
    from ragbot.tools.core import search_documents
    from ragbot.schemas import Chunk
    chunks = [Chunk(**c) for c in json.loads(Path("index/chunks.json").read_text(encoding="utf-8"))]
    hits = [c for c in chunks if "주소지가 일치할 것" in c.text or "학업 또는 취업을 이유로 일시적으로" in c.text]
    assert len(hits) >= 2
    out = search_documents(Context(index=_FakeIndex(hits), cfg=CFG), "q")
    assert all("시행규칙 제6조②" in o.get("note", "") for o in out)


def test_selection_clause_points_to_the_age_definition():
    # 법 제13조의 선정 요건에는 나이가 없고 법 제2조1호에 있다: 요건만 보고 답하면 나이를 빠뜨린다
    import json
    from pathlib import Path
    from ragbot.tools import Context
    from ragbot.tools.core import search_documents
    from ragbot.schemas import Chunk
    chunks = [Chunk(**c) for c in json.loads(Path("index/chunks.json").read_text(encoding="utf-8"))]
    hits = [c for c in chunks if "제13조(지원대상자 선정 등)" in " ".join(c.path)]
    out = search_documents(Context(index=_FakeIndex(hits), cfg=CFG), "q")
    assert any("① 나이" in o.get("note", "") and "법 제2조1호" in o["note"] and "34세 이하" in o["note"] for o in out)


def test_income_clauses_get_the_median_income_amounts():
    # 소득 기준 조문만 검색되고 금액 고시가 검색되지 않으면 모델이 금액을 지어냈다 ("2,340만 원")
    import json
    import re
    from pathlib import Path
    from ragbot.tools import Context
    from ragbot.tools.core import search_documents
    from ragbot.schemas import Chunk
    chunks = [Chunk(**c) for c in json.loads(Path("index/chunks.json").read_text(encoding="utf-8"))]
    hits = [c for c in chunks if re.search(r"기준\s*중위소득\s*의\s*100분의\s*100", c.text)]
    assert len(hits) >= 2
    out = search_documents(Context(index=_FakeIndex(hits), cfg=CFG), "q")
    assert all("2,564,238" in o.get("note", "") and "본인" in o["note"] and "4,199,292" not in o["note"] for o in out)

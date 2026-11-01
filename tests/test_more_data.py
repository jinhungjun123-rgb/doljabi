"""일반 지원 정리 파일 (data/programs/more.json, scripts/build_more.py 가 만든다)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MORE = ROOT / "data" / "programs" / "more.json"
GROUPS = {"life", "health", "housing", "education", "jobs", "participation"}
CANDIDATES = json.loads((ROOT / "scripts" / "program_candidates.json").read_text(encoding="utf-8"))
REVIEWED_IDS = {f"N:{c['bokjiro']}" for c in CANDIDATES if c.get("bokjiro")} | {f"Y:{c['youth']}" for c in CANDIDATES if c.get("youth")}


def test_more_file_shape():
    d = json.loads(MORE.read_text(encoding="utf-8"))
    assert d["as_of"] == "2026-11-01"
    ids = {i["id"] for i in d["items"]}
    assert 1500 < sum(i["source"] == "youth" for i in d["items"]) < 2500
    assert 100 < sum(i["source"] == "national" for i in d["items"]) < 200
    assert all(i["link"].startswith("https://") and i["group"] in GROUPS for i in d["items"])
    assert REVIEWED_IDS.isdisjoint(ids)          # 검수 14개와 겹치지 않음
    assert not any(i["source"] == "national" and i["targets"] and set(i["targets"]) <= {"보훈대상자", "다문화·탈북민"}
                   for i in d["items"])


def test_youth_items_carry_what_the_rules_need():
    d = json.loads(MORE.read_text(encoding="utf-8"))
    youth = [i for i in d["items"] if i["source"] == "youth"]
    assert all(i["scope"] in ("nation", "sido", "local") and i["sidos"] for i in youth)
    assert all(i["period"]["kind"] in ("always", "range", "tbd") for i in youth)
    assert all("\n" not in i["summary"] and len(i["summary"]) <= 90 for i in d["items"])
    assert any(i["scope"] == "nation" for i in youth) and any("12" in i["sidos"] for i in youth)


def test_youth_restriction_fields_and_zero_age():
    d = json.loads(MORE.read_text(encoding="utf-8"))
    youth = [i for i in d["items"] if i["source"] == "youth"]
    assert all({"special", "married", "extra"} <= i.keys() for i in youth)
    infants = next(i for i in youth if i["name"].startswith("가정양육수당"))
    assert infants["age"] == [0, 0]                  # 나이 제한 Y, 0~0세: 제한 없음이 아니다

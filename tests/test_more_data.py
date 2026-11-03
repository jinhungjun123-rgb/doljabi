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
    # 나이 제한 Y, 0~0세 = 범위가 글로만 적힘: 글에서 읽고, 글에도 없으면 나이 칸 없음(청년정책 기본)으로 (결정 0010)
    age = {i["name"]: i["age"] for i in youth}
    assert age["경산시 청년센터"] == [15, 39] and age["문경시청년센터 운영"] == [19, 45]
    for other in ("아픈아이 돌봄센터", "충북 다자녀 행복카드", "청년과 어르신 주거공유"):   # 아동·자녀·어르신 나이는 신청자 나이가 아님
        assert next(a for n, a in age.items() if n.startswith(other)) is None, other
    assert next(a for n, a in age.items() if n.startswith("ICT이노베이션스퀘어")) == [18, 99]
    assert next(a for n, a in age.items() if n.startswith("고용평등 심층상담")) is None
    assert not [i["name"] for i in youth if i["age"] == [0, 0]]


def test_data_quality():
    import re
    d = json.loads(MORE.read_text(encoding="utf-8"))["items"]
    assert not [i["name"] for i in d if re.search(r"&[a-z]+;|&#\d+;", i["name"] + i["summary"])]      # HTML 기호가 글자로
    keys = [(re.sub(r"\s+", "", i["name"]), i["org"]) for i in d]
    assert len(keys) == len(set(keys))                                                                  # 같은 사업 한 번만
    assert not [i["name"] for i in d if re.search(r"실태조사|조성사업|개발사업|정비사업|조정위원회 운영|위원회 운영$", i["name"])]
    assert not [i for i in d if i.get("age") == [0, 99]]                                                    # "나이 0세 이상"은 나이 제한 없음
    housing = re.compile(r"주거|주택|월세|전세|임대|기숙|거주|보금자리|원룸|셰어|하우스|숙소|이사|청약|보증금|입주|빌리지|공공분양|모기지|학사관|전입")
    assert not [i["name"] for i in d if i["group"] == "housing" and not housing.search(i["name"] + i["summary"])]


def test_system_building_is_not_support():
    import re
    d = json.loads(MORE.read_text(encoding="utf-8"))["items"]
    assert not [i["name"] for i in d if re.search(r"시스템 구축|DB\s?고도화|포인트제 도입", i["name"])]

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


def test_programs_for_schools_are_not_for_students():
    # 대학·연구소의 역량 사업은 빼고, 선정된 학교의 학생이 받는 사업은 via_school (결정 0010)
    d = json.loads(MORE.read_text(encoding="utf-8"))["items"]
    names = {i["name"]: i for i in d}
    for gone in ("AI 단과대학", "이공분야 대학중점연구소 지원사업(에너지)", "에너지기술공유대학(호남권)", "도시재생 전문인력 양성사업",
                 "스마트시티 혁신인재 육성", "대학 ICT연구센터 지원", "스포츠산업 융복합대학원 운영", "직업계고-전문대학 교육과정 연계",
                 "대학 상생협력 강화", "대학생 현장실습 제도개선", "대학기숙사 확충"):
        assert gone not in names, gone
    for via in ("천원의 아침밥", "AI·SW중심대학", "농업계대학 지원", "대학일자리플러스센터 지원", "창의융합형공학인재양성지원",
                "대학별 맞춤형 취업역량강화 프로그램 지원", "체계적인 지식재산 인재 및 리더양성", "지역산업 연계형 대학 특성화학과 혁신지원",
                "첨단분야(이차전지) 혁신융합대학", "산학일체형 도제학교 지원", "건강증진대학만들기", "대학-공공기관 연계 취업지원 프로그램"):
        assert names[via].get("via_school") is True, via
    for own in ("이공계 우수학생 국가장학금", "청년 자금지원을 위한 햇살론유스 운영", "제11기 충북청년도정참여단",
                "대학생 연합생활관(은행권,고양)"):
        assert not names[own].get("via_school"), own


def test_policy_admin_is_not_support():
    # 정책 홍보, 책임관제, 친화도시 지정, 기관의 고용 의무: 청년이 신청하는 것이 아니다
    d = json.loads(MORE.read_text(encoding="utf-8"))["items"]
    names = {i["name"] for i in d}
    for gone in ("부산 청년정책 홍보", "부산시 청년정책 책임관제 운영", "부산 청년친화도시 지정 지원", "공공기관 청년고용의무제 운영"):
        assert gone not in names, gone
    assert "청년정책협의체 운영지원" in names          # 청년이 위원으로 참여한다

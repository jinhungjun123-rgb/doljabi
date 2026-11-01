"""일반 지원 더 보기: 공공데이터(data/programs/more.json)를 프로필로 거르고 조건별로 자동 판정한다 (LLM 없이).

설계: docs/superpowers/specs/2026-11-01-doljabi-more-support-design.md. 조건 결과와 카드 상태 규칙은 eligibility.py 와 같다.
판정은 데이터에 칸으로 들어 있는 조건만 본다. 그 밖의 세부 요건은 화면이 "원문에서 확인"으로 안내한다.
"""
import json
import re
from pathlib import Path

from ragbot.config import DATA_DIR
from ragbot.domain.eligibility import card_status, clean_profile

MORE_FILE = DATA_DIR / "programs" / "more.json"
GROUP_LABELS = {"life": "생활·금융", "health": "건강·마음", "housing": "주거", "education": "교육", "jobs": "일자리",
                "participation": "참여·문화"}
# 온통청년 지역 코드 앞 두 자리. 광주·전남은 전남광주통합특별시(12) 하나로 나온다 (원본 2026-11-01)
SIDO_CODE = {"서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "12", "대전": "30", "울산": "31", "세종": "36",
             "경기": "41", "강원": "51", "충북": "43", "충남": "44", "전북": "52", "전남": "12", "경북": "47", "경남": "48", "제주": "50"}
SIDO_NAME = {"12": "광주·전남", **{code: name for name, code in SIDO_CODE.items() if code != "12"}}
# 온통청년 취업 상태·학력 코드 중 뜻을 원본 표본으로 확인한 것만 쓴다
JOB_NAME = {"0013001": "재직자", "0013003": "미취업자"}
SCHOOL_NAME = {"0049002": "고등학생", "0049005": "대학생"}
SPECIAL_NAME = {"0014001": "중소기업", "0014002": "여성", "0014003": "기초생활수급자", "0014004": "한부모가정", "0014005": "장애인",
                "0014006": "농업인", "0014007": "군인", "0014008": "지역인재", "0014009": "그 밖의 특정 대상"}
USER_JOB = {"working": {"0013001"}, "rest_6m_plus": {"0013003"}, "rest_under_6m": {"0013003"}}
USER_SCHOOL = {"middle_high": {"0049002"}, "college": {"0049005"}}
INCOME_BAND = {"none": (0, 0), "lt100": (0, 99), "100_200": (100, 199), "200_256": (200, 256), "gt256": (257, None)}  # 월, 만원
LIFE_AGES = {"청소년": (13, 18), "청년": (19, 34)}
CARE_WORDS = re.compile(r"돌봄|가족|간병|장애|자립")
# 이름에만 대상이 드러나는 사업 (특화 대상 코드가 비어 있어도)
TARGET_WORDS = re.compile(r"자립준비|보호종료|퇴소|장애|한부모|농업인|귀농|귀어|어업인|예술인|영유아|임산부|다문화|북한이탈|탈북|장병|군인|보훈|소상공인")
_ORDER = {"ok": 0, "check": 1, "no": 2}


def load_more(path: Path = MORE_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _row(key: str, label: str, result: str) -> dict:
    return {"key": key, "label": label, "result": result}


def _age_row(item: dict, age) -> dict | None:
    if item["source"] == "national":
        stages = [LIFE_AGES[s] for s in item["life"] if s in LIFE_AGES]
        label = "·".join(item["life"]) + f"({min(s[0] for s in stages)}~{max(s[1] for s in stages)}세) 대상"
        if age is None:
            return _row("age", label, "unknown")
        return _row("age", label, "ok" if any(lo <= age <= hi for lo, hi in stages) else "no")
    if not item["age"]:
        return None
    lo, hi = item["age"]
    if lo == hi == 0:                       # 나이 제한은 있는데 범위가 글로만 적힘 (원본 데이터)
        return _row("age", "나이 조건 (원문 확인)", "unknown")
    label = f"나이 {lo}~{hi}세" if lo and hi < 99 else f"나이 {hi}세 이하" if hi < 99 else f"나이 {lo}세 이상"
    if age is None:
        return _row("age", label, "unknown")
    return _row("age", label, "ok" if lo <= age <= hi else "no")


def _region_row(item: dict, profile: dict) -> dict | None | bool:
    """False: 목록에서 뺀다. None: 지역 조건 없음 (전국)."""
    if item["source"] == "national" or item["scope"] == "nation":
        return None
    code = SIDO_CODE.get(profile.get("region"))
    if code is None or code not in item["sidos"]:
        return False
    if item["scope"] == "sido":
        return _row("region", f"사는 곳: {SIDO_NAME[code]}", "ok")
    district = re.match(r"\S+\s+(\S+(?:시|군|구))(?:\s|$)", item["org"])
    label = f"사는 곳: {district.group(1) if district else item['org']}"
    mine = re.sub(r"(시|군|구)$", "", (profile.get("sigungu") or "").strip())
    if not district or len(mine) < 2:
        return _row("region", label, "unknown")
    return _row("region", label, "ok" if mine in district.group(1) else "no")


def _income_row(item: dict, band) -> dict | None:
    if item["source"] != "youth" or not item["income"]:
        return None
    lo, hi = item["income"]
    label = f"본인 연소득 {lo}~{hi}만원" if lo and hi else f"본인 연소득 {hi}만원 이하" if hi else f"본인 연소득 {lo}만원 이상"
    if band not in INCOME_BAND:
        return _row("income", label, "unknown")
    mine_lo, mine_hi = INCOME_BAND[band]
    mine_lo, mine_hi = mine_lo * 12, (mine_hi * 12 if mine_hi is not None else float("inf"))
    top = hi if hi else float("inf")
    if lo <= mine_lo and mine_hi <= top:
        return _row("income", label, "ok")
    return _row("income", label, "no" if mine_hi < lo or mine_lo > top else "unknown")


def _period_row(item: dict, today: str) -> dict | None | bool:
    if item["source"] != "youth":
        return None
    period = item["period"]
    if period["kind"] == "always":
        return _row("period", "신청: 상시", "ok")
    ranges = [(s, e) for s, e in period["ranges"] if re.fullmatch(r"\d{8}", s) and re.fullmatch(r"\d{8}", e)]
    if period["kind"] != "range" or not ranges:
        return _row("period", "신청 기간: 공고 확인", "unknown")
    if all(e < today for _, e in ranges):
        return False
    s, e = next(((s, e) for s, e in ranges if s <= today <= e), min((r for r in ranges if r[1] >= today)))
    label = f"신청 기간: {s[:4]}.{s[4:6]}.{s[6:]} ~ {e[:4]}.{e[4:6]}.{e[6:]}"
    return _row("period", label, "ok" if s <= today <= e else "unknown")


def _code_row(key: str, codes: list, names: dict, user: set | None) -> dict | None:
    if not codes:
        return None
    label = ("취업 상태: " if key == "job" else "학업: ") + "·".join(names.get(c, "그 밖의 조건") for c in dict.fromkeys(codes))
    if user is None:
        return _row(key, label, "unknown")
    if user & set(codes):
        return _row(key, label, "ok")
    return _row(key, label, "no" if set(codes) <= set(names) else "unknown")


def _target_row(item: dict, profile: dict) -> dict | None:
    if item["source"] != "national" or not item["targets"]:
        return None
    label = "대상: " + ", ".join(item["targets"])
    low_income = "저소득" in item["targets"] and profile.get("basic_livelihood") == "yes"
    return _row("target", label, "ok" if low_income else "unknown")


def _restriction_rows(item: dict, profile: dict) -> list[dict]:
    """데이터로 판정할 수 없는 대상 제한: 특화 대상, 혼인, 글로만 적힌 추가 자격 → 확인 필요."""
    out = []
    special = item.get("special") or []
    if special:
        names = "·".join(SPECIAL_NAME.get(c, "그 밖의 특정 대상") for c in dict.fromkeys(special))
        ok = "0014003" in special and profile.get("basic_livelihood") == "yes"
        out.append(_row("special", f"특정 대상: {names}", "ok" if ok else "unknown"))
    elif TARGET_WORDS.search(item["name"]):
        out.append(_row("special", f"특정 대상일 수 있음: {TARGET_WORDS.search(item['name']).group(0)}", "unknown"))
    if item.get("married"):
        out.append(_row("married", "혼인: " + ("기혼" if item["married"] == "0055001" else "미혼"), "unknown"))
    if item.get("extra") or item["source"] == "national":   # 국가 서비스는 자격이 설명 글에만 있다
        out.append(_row("extra", "그 밖의 자격 조건 (원문 확인)", "unknown"))
    return out


def judge(item: dict, profile: dict, today: str) -> dict | None:
    """item 하나의 조건별 판정. None 이면 목록에서 뺀다 (다른 시·도, 신청이 끝남)."""
    region, period = _region_row(item, profile), _period_row(item, today)
    if region is False or period is False:
        return None
    activity = profile.get("activity")
    rows = [_age_row(item, profile.get("age")), region, _income_row(item, profile.get("income_band")), period,
            _code_row("job", item.get("jobs") or [], JOB_NAME, USER_JOB.get(activity)),
            _code_row("school", item.get("schools") or [], SCHOOL_NAME, USER_SCHOOL.get(activity)),
            _target_row(item, profile), *_restriction_rows(item, profile)]
    conditions = [r for r in rows if r]
    shown = {k: item[k] for k in ("id", "source", "name", "summary", "org", "link", "group")}
    return {**shown, "local": item.get("scope") in ("sido", "local"), "status": card_status(conditions), "conditions": conditions}


def _sort_key(r: dict) -> tuple:
    care = bool(CARE_WORDS.search(r["name"] + r["summary"]))
    return _ORDER[r["status"]], not care, not r["local"], r["name"]


def more_for(profile: dict, data: dict, today: str) -> dict:
    """분야별 목록: items 는 받을 수 있어 보여요 → 확인이 필요해요, no_items 는 어려워 보여요."""
    profile = clean_profile(profile)
    judged = [r for r in (judge(i, profile, today) for i in data["items"]) if r]
    groups = []
    for key, label in GROUP_LABELS.items():
        mine = sorted((r for r in judged if r["group"] == key), key=_sort_key)
        if mine:
            groups.append({"key": key, "label": label, "items": [r for r in mine if r["status"] != "no"],
                           "no_items": [r for r in mine if r["status"] == "no"]})
    return {"as_of": data["as_of"], "groups": groups}

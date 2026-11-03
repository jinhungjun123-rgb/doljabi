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
GROUP_LABELS = {"life": "생활·금융", "health": "건강·마음", "education": "교육", "jobs": "일자리", "housing": "주거",
                "participation": "참여·문화"}
# 온통청년 지역 코드 앞 두 자리. 광주·전남은 전남광주통합특별시(12) 하나로 나온다 (원본 2026-11-01)
SIDO_CODE = {"서울": "11", "부산": "26", "대구": "27", "인천": "28", "광주": "12", "대전": "30", "울산": "31", "세종": "36",
             "경기": "41", "강원": "51", "충북": "43", "충남": "44", "전북": "52", "전남": "12", "경북": "47", "경남": "48", "제주": "50"}
# 담당 기관 이름의 첫 낱말 → 시·도 코드 (zipCd 에 전국이 적혀 있어도 시·군·구 사업인 경우를 가려낸다)
ORG_SIDO = {"서울특별시": "11", "부산광역시": "26", "대구광역시": "27", "인천광역시": "28", "광주광역시": "12", "대전광역시": "30",
            "울산광역시": "31", "세종특별자치시": "36", "경기도": "41", "강원특별자치도": "51", "강원도": "51", "충청북도": "43",
            "충청남도": "44", "전북특별자치도": "52", "전라북도": "52", "전라남도": "12", "전남광주통합특별시": "12", "경상북도": "47",
            "경상남도": "48", "제주특별자치도": "50"}
# 이름에 든 시·도 (전국으로 올라왔어도 그 지역 사업). 긴 이름부터
NAME_SIDO = re.compile("|".join(sorted([*ORG_SIDO, *SIDO_CODE], key=len, reverse=True)))
# 이 조건 중 하나는 맞아야 "받을 수 있어 보여요" (신청 기간만 맞는 카드는 사용자에 대해 확인한 것이 없다)
ABOUT_USER = {"age", "region", "income", "job", "school", "target", "special"}
SIDO_NAME = {"12": "광주·전남", **{code: name for name, code in SIDO_CODE.items() if code != "12"}}
# 온통청년 취업 상태·학력 코드 중 뜻을 원본 표본으로 확인한 것만 쓴다
JOB_NAME = {"0013001": "재직자", "0013003": "미취업자"}
SCHOOL_NAME = {"0049002": "고등학생", "0049005": "대학생"}
SPECIAL_NAME = {"0014001": "중소기업", "0014002": "여성", "0014003": "기초생활수급자", "0014004": "한부모가정", "0014005": "장애인",
                "0014006": "농업인", "0014007": "군인", "0014008": "지역인재", "0014009": "그 밖의 특정 대상"}
USER_SCHOOL = {"middle_high": {"0049002"}, "college": {"0049005"}}


def _user_job(profile: dict) -> set | None:
    """재직자 / 미취업자 코드. 학생이 일하지 않으면 미취업자인지 알 수 없다 (정책마다 재학생을 넣거나 뺀다)."""
    if profile.get("work") == "working":
        return {"0013001"}
    if profile.get("work") == "none" and profile.get("school") == "none":
        return {"0013003"}
    return None
INCOME_BAND = {"none": (0, 0), "lt100": (0, 99), "100_200": (100, 199), "200_256": (200, 256), "gt256": (257, None)}  # 월, 만원
LIFE_AGES = {"청소년": (13, 18), "청년": (19, 34)}
CARE_WORDS = re.compile(r"돌봄|간병|영케어러")   # 가족을 돌보는 사람과 관련된 사업을 먼저
# 이름에만 대상이 드러나는 사업 (특화 대상 코드가 비어 있어도)
TARGET_WORDS = re.compile(r"자립준비|보호종료|퇴소|장애|한부모|농업인|귀농|귀어|어업인|청년농|영농|스마트팜|농촌형|예술인|영유아|임산부|다문화|북한이탈|탈북|장병|군인|보훈|소상공인|피해자|의사상자|입양|위탁|자활|양육|출산|결혼|농지|특수학교|특수교육|첫만남|아이돌봄")
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
    if not item["age"]:   # 나이 칸이 없는 청년정책: 청년 나이(19~39세)가 아니면 확인 필요
        return _row("age", "나이 조건 (원문 확인)", "unknown") if age is not None and not 19 <= age <= 39 else None
    lo, hi = item["age"]
    if lo == hi == 0:                       # 나이 제한은 있는데 범위가 글로만 적힘 (원본 데이터)
        return _row("age", "나이 조건 (원문 확인)", "unknown")
    label = f"나이 {lo}~{hi}세" if lo and hi < 99 else f"나이 {hi}세 이하" if hi < 99 else f"나이 {lo}세 이상"
    if age is None:
        return _row("age", label, "unknown")
    return _row("age", label, "ok" if lo <= age <= hi else "no")


def _region_row(item: dict, profile: dict) -> dict | None | bool:
    """False: 목록에서 뺀다. None: 지역 조건 없음 (전국)."""
    if item["source"] == "national":
        return None
    code = SIDO_CODE.get(profile.get("region"))
    if item["scope"] == "nation":
        office = ORG_SIDO.get(item["org"].split(" ")[0])
        if office is None:                     # 중앙부처·공공기관: 전국. 단 이름에 시·도가 있으면 그 지역 사업
            named = NAME_SIDO.search(item["name"])
            if not named:
                return None
            place = SIDO_CODE.get(named.group(0)) or ORG_SIDO[named.group(0)]
            if code is None:
                return _row("region", f"사는 곳: {named.group(0)} (원문 확인)", "unknown")
            return _row("region", f"사는 곳: {SIDO_NAME[code]}", "ok") if code == place else False
        if code != office:
            return False
        return _district_row(item, profile) or _row("region", f"사는 곳: {SIDO_NAME[code]}", "ok")
    if code is None or code not in item["sidos"]:
        return False
    if item["scope"] == "sido":
        return _row("region", f"사는 곳: {SIDO_NAME[code]}", "ok")
    return _district_row(item, profile) or _row("region", f"사는 곳: {item['org']}", "unknown")


def _district_row(item: dict, profile: dict) -> dict | None:
    """담당 기관이 시·군·구면 입력한 시·군·구와 낱말 단위로 비교 ("용인시 수지구", "경기 용인시" → 용인시). 기관이 시·도면 None."""
    district = re.match(r"\S+\s+(\S+(?:시|군|구))(?:\s|$)", item["org"])
    if not district:
        return None
    label = f"사는 곳: {district.group(1)}"
    typed = profile.get("sigungu") if isinstance(profile.get("sigungu"), str) else ""
    stems = {w for w in (re.sub(r"(시|군|구)$", "", x) for x in typed.split()) if len(w) >= 2}
    if not stems:
        return _row("region", label, "unknown")
    return _row("region", label, "ok" if re.sub(r"(시|군|구)$", "", district.group(1)) in stems else "no")


def _income_row(item: dict, band) -> dict | None:
    if item["source"] != "youth" or not item["income"]:
        return None
    lo, hi = item["income"]
    label = f"연소득 {lo}~{hi}만원" if lo and hi else f"연소득 {hi}만원 이하" if hi else f"연소득 {lo}만원 이상"
    label += " (본인·가구 기준은 원문 확인)"
    if band not in INCOME_BAND:
        return _row("income", label, "unknown")
    mine_lo, mine_hi = INCOME_BAND[band]
    mine_lo, mine_hi = mine_lo * 12, (mine_hi * 12 if mine_hi is not None else float("inf"))
    top = hi if hi else float("inf")
    if lo <= mine_lo and mine_hi <= top:
        return _row("income", label, "ok")
    return _row("income", label, "unknown")   # 개인·가구 기준과 단위를 데이터로 알 수 없어 범위 밖이어도 "어려워 보여요"로 접지 않는다


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
    label = ("취업 상태: " if key == "job" else "학업: ") + "·".join(dict.fromkeys(names.get(c, "그 밖의 조건") for c in codes))
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
        names = "·".join(dict.fromkeys(SPECIAL_NAME.get(c, "그 밖의 특정 대상") for c in special))
        ok = "0014003" in special and profile.get("basic_livelihood") == "yes"   # 답은 수급·차상위, 코드는 수급자만
        out.append(_row("special", f"특정 대상: {names}" + (" (차상위는 원문 확인)" if ok else ""), "ok" if ok else "unknown"))
    elif TARGET_WORDS.search(item["name"]):
        out.append(_row("special", f"특정 대상일 수 있음: {TARGET_WORDS.search(item['name']).group(0)}", "unknown"))
    if item.get("via_school"):   # 대학이 공모로 선정되는 사업
        out.append(_row("via_school", "다니는 학교가 이 사업에 선정된 경우에만 (학교에 확인)", "unknown"))
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
    rows = [_age_row(item, profile.get("age")), region, _income_row(item, profile.get("income_band")), period,
            _code_row("job", item.get("jobs") or [], JOB_NAME, _user_job(profile)),
            _code_row("school", item.get("schools") or [], SCHOOL_NAME, USER_SCHOOL.get(profile.get("school"))),
            _target_row(item, profile), *_restriction_rows(item, profile)]
    conditions = [r for r in rows if r]
    status = card_status(conditions)
    if status == "ok" and not any(c["key"] in ABOUT_USER and c["result"] == "ok" for c in conditions):
        status = "check"
    shown = {k: item[k] for k in ("id", "source", "name", "summary", "org", "link", "group")}
    local = item.get("scope") in ("sido", "local") or any(c["key"] == "region" for c in conditions)
    return {**shown, "local": local, "status": status, "conditions": conditions}


MAYBE_PER_GROUP = 3        # 확인해 볼 만한 지원: 분야마다 이만큼만 (나머지는 온통청년·복지로에서)
FOR_OTHERS = {"special", "married"}   # 이 조건을 모르면 대개 다른 사람을 위한 사업 (자립준비청년, 농업인, 기혼 …)


def _unknown(r: dict) -> set:
    return {c["key"] for c in r["conditions"] if c["result"] == "unknown"}


def _care(r: dict) -> bool:
    return bool(CARE_WORDS.search(r["name"] + r["summary"]))


def _maybe_key(r: dict) -> tuple:
    """돌봄·가족 관련 → 내 지역 → 모르는 조건이 적은 것 → 지금 신청할 수 있는 것 → 이름."""
    open_now = any(c["key"] == "period" and c["result"] == "ok" for c in r["conditions"])
    return not _care(r), not r["local"], len(_unknown(r)), not open_now, r["name"]


def more_for(profile: dict, data: dict, today: str) -> dict:
    """짧은 목록: ok 는 받을 수 있어 보여요 전부, maybe 는 분야마다 확인해 볼 만한 지원 몇 개. 어려워 보여요는 보내지 않는다."""
    profile = clean_profile(profile)
    judged = [r for r in (judge(i, profile, today) for i in data["items"]) if r]
    seen = set()

    def first_time(r: dict) -> bool:          # 해마다 다시 올라온 같은 사업 ("2026 …")은 한 번만
        name = re.sub(r"^20\d\d\s*|\s+", "", r["name"])
        if name in seen:
            return False
        seen.add(name)
        return True

    ok = [r for r in sorted((r for r in judged if r["status"] == "ok"), key=lambda r: (not _care(r), not r["local"], r["name"]))
          if first_time(r)]
    for r in ok:
        r["group_label"] = GROUP_LABELS[r["group"]]
    maybe = []
    for key, label in GROUP_LABELS.items():
        mine = sorted((r for r in judged if r["group"] == key and r["status"] == "check" and not _unknown(r) & FOR_OTHERS),
                      key=_maybe_key)
        picked = []
        for r in mine:
            if len(picked) == MAYBE_PER_GROUP:
                break
            if first_time(r):
                picked.append(r)
        if picked:
            maybe.append({"key": key, "label": label, "items": picked})
    return {"as_of": data["as_of"], "ok": ok, "maybe": maybe}


def about_summary(about, data: dict) -> str | None:
    """채팅 맥락: 사용자가 일반 지원 목록에서 고른 사업. 화면은 사업 번호만 보내고, 내용은 서버의 정리 파일에서 찾는다."""
    if not isinstance(about, dict) or not isinstance(about.get("id"), str):
        return None
    item = next((i for i in data["items"] if i["id"] == about["id"]), None)
    if item is None:
        return None
    facts = [f"사업 이름: {item['name']}", f"담당: {item['org']}", f"설명: {item['summary']}", f"원문: {item['link']}"]
    return ("About this question (사용자가 앱의 '일반 지원' 목록에서 고른 사업): " + "; ".join(facts) + ". "
            "이 사업은 공공데이터(온통청년·복지로)에서 온 것이라 법령 문서에는 없습니다. web_search 로 공식 사이트를 찾아 답하고, "
            "웹 정보는 확인이 필요하다고 표시하세요. 받을 수 있는지 최종 판정은 하지 마세요.")

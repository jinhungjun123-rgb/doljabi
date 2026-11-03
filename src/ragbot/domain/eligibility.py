"""받을 수 있어 보이는지 판정 (LLM 없이). 근거: 위기아동청년법·시행령·시행규칙·고시, 검수한 사업 자료.

조건마다 결과는 ok(맞아 보임) / unknown(확인 필요) / no(맞지 않아 보임). "잘 모르겠어요"와 빈 답은 항상 unknown.
카드 상태: no가 하나라도 있으면 "no", 모두 ok면 "ok", 그 밖은 "check". 최종 판정은 센터·시군구청이 한다.
"""
from math import ceil

from ragbot.domain.programs import center_for

MEDIAN_1P = "2,564,238원"   # 2026년 1인 가구 기준 중위소득 (보건복지부고시 제2025-135호)
CARE_NEEDS = {"ltc_grade", "severe_disability", "mental_illness", "long_illness"}


_NUMBERS, _LISTS = ("age", "military_months"), ("relations", "conditions")
# 예전 4단계 답(하나만 고름) → 학교·일·쉰 기간 (docs/decisions/0014)
_FROM_ACTIVITY = {"middle_high": {"school": "middle_high"}, "college": {"school": "college"}, "working": {"work": "working"},
                  "rest_6m_plus": {"school": "none", "work": "none", "rest": "6m_plus"},
                  "rest_under_6m": {"school": "none", "work": "none", "rest": "under_6m"}}


def clean_profile(profile) -> dict:
    """형식이 틀린 항목(옛 저장값, 손으로 고친 값)을 뺀다. 빠진 항목은 답하지 않은 것과 같다."""
    if not isinstance(profile, dict):
        return {}
    out = {}
    for key, value in profile.items():
        if key in _NUMBERS:
            ok = isinstance(value, int) and not isinstance(value, bool)
        elif key in _LISTS:
            ok = isinstance(value, list) and all(isinstance(v, str) for v in value)
        else:
            ok = value is None or isinstance(value, (str, bool))
        if ok:
            out[key] = value
    if not ({"school", "work"} & out.keys()):
        out.update(_FROM_ACTIVITY.get(out.get("activity"), {}))
    out.pop("activity", None)
    return out


def _cond(label: str, law: str, result: str) -> dict:
    return {"label": label, "law": law, "result": result}


def _age(p: dict, lo: int, hi: int, law: str, military: bool = False) -> dict:
    label = f"나이 {lo}~{hi}세" + (" (군 복무 기간만큼 늘어나요)" if military else "")
    age = p.get("age")
    if age is None:
        return _cond(label, law, "unknown")
    # 실제 복무 기간을 더한다: 다 채운 해만큼은 확실하고, 남는 개월은 생일에 따라 달라 "확인 필요"
    months = (p.get("military_months") or 0) if military else 0
    if lo <= age <= hi + months // 12:
        return _cond(label, law, "ok")
    return _cond(label, law, "unknown" if lo <= age <= hi + ceil(months / 12) else "no")


def _family(p: dict) -> dict:
    ok = bool(CARE_NEEDS & set(p.get("conditions") or []))
    return _cond("돌봄이 필요한 가족 (장기요양·심한 장애·정신질환·6개월 이상 질병 등)", "돌봄대상가족 고시 제2조",
                 "ok" if ok else "unknown")


def _adult(p: dict) -> dict:
    a, exc = p.get("adult_other"), p.get("adult_other_exception")
    result = ("ok" if a == "none" or (a == "yes" and exc in ("ill_or_disabled", "absent"))
              else "no" if a == "yes" and exc == "none" else "unknown")
    return _cond("함께 사는 35세 이상 다른 가족이 없거나 예외에 해당", "법 제13조①1, 시행규칙 제6조①", result)


def _address(p: dict) -> dict:
    living = p.get("living")
    result = "ok" if living in ("together", "apart_visiting") else "no" if living == "apart" else "unknown"
    return _cond("돌보는 가족과 주소가 같음 (학업·취업으로 따로 살며 돌보는 경우 예외)", "법 제13조①1, 시행규칙 제6조②", result)


def _burden(p: dict) -> dict:
    # 객관적 기준이 없고 센터가 상담으로 판단한다: 묻지 않고 안내만, 카드 상태에 넣지 않음 (docs/decisions/0012)
    return _cond("돌봄 때문에 학업·취업에 상당한 곤란을 겪음 (청년미래센터 상담에서 판단해요)", "법 제13조①1라목", "info")


def _income(p: dict) -> dict:
    band = p.get("income_band")
    result = "ok" if band in ("none", "lt100", "100_200", "200_256") else "no" if band == "gt256" else "unknown"
    return _cond("본인 소득·재산 기준 중위소득 100% 이하 (대략 월 256만원)", "시행령 제11조①2", result)


def _together(p: dict) -> dict:
    living = p.get("living")
    result = "ok" if living == "together" else "no" if living in ("apart", "apart_visiting") else "unknown"
    return _cond("돌보는 가족과 함께 삶", "2026 일상돌봄 서비스 사업안내 15쪽", result)


def _selected() -> dict:
    return _cond("청년미래센터의 지원대상자 선정이 필요해요", "법 제13조①", "unknown")


def _age_in(p: dict, lo: int, hi: int) -> bool:
    """카드를 보여 줄지: 나이를 모르면 보여 준다."""
    return p.get("age") is None or lo <= p["age"] <= hi


def _no_school(p: dict) -> dict:
    # 고용노동부 안내 (2026.8): 재학생은 원칙적으로 참여할 수 없고, 졸업예정자·사이버·방송통신·야간대 재학생 등은 참여 가능
    school = p.get("school")
    return _cond("학교에 다니지 않음 (졸업예정자·사이버·방송통신·야간대 재학생은 참여 가능)", "고용노동부 안내 2026",
                 "ok" if school == "none" else "unknown")


def _no_work_or_school_6m(p: dict) -> dict:
    school, work, rest = p.get("school"), p.get("work"), p.get("rest")
    result = ("no" if school in ("middle_high", "college") or work == "working"
              else "ok" if school == "none" and work == "none" and rest == "6m_plus" else "unknown")
    return _cond("6개월 넘게 취업·교육 이력 없음", "고용24 2026", result)


def _local(lo: int, hi: int, law: str):
    def rule(p: dict, program: dict) -> list[dict] | None:
        if p.get("region") != program["region"]:
            return None
        return [_cond(f"{program['region']}에 살아요", law, "ok"), _age(p, lo, hi, law)]
    return rule


RULES = {
    "A01": lambda p, _: None if not _age_in(p, 13, 200) else [
        _age(p, 13, 34, "시행령 제11조①1", military=True), _family(p), _adult(p), _address(p), _burden(p), _income(p)],
    "A02": lambda p, _: None if not _age_in(p, 13, 200) else [
        _age(p, 13, 34, "법 제2조1호", military=True), _family(p), _adult(p), _address(p), _burden(p)],
    "A03": lambda p, _: None if p.get("age") is None or p["age"] >= 13 else [
        _age(p, 0, 12, "보건복지부 보도자료 2026.3.25"), _family(p)],
    "A04": lambda p, _: None if not _age_in(p, 9, 39) else [
        _age(p, 9, 39, "2026 일상돌봄 서비스 사업안내 15쪽"), _family(p), _together(p)],
    "A05": lambda p, _: None if "ltc_grade" not in (p.get("conditions") or []) else [
        _cond("가족이 장기요양 등급을 받았어요 (인지지원등급 제외)", "법 제19조②1, 시행령 제12조", "ok"), _selected()],
    "A06": lambda p, _: None if p.get("basic_livelihood") != "yes" else [
        _cond("기초생활 수급 가구", "법 제19조②3, 시행규칙 제9조", "ok"), _selected()],
    "B01": lambda p, _: None if p.get("school") != "college" else [
        _cond("대학생", "한국장학재단", "ok"), _cond("학자금 지원구간 9구간 이하", "한국장학재단", "unknown")],
    "B04": lambda p, _: None if not _age_in(p, 18, 34) else [
        _age(p, 18, 34, "고용24 2026"),
        _no_work_or_school_6m(p)],
    "B05": lambda p, _: None if not _age_in(p, 15, 34) else [
        _age(p, 15, 34, "고용24"), _no_school(p)],   # 미취업은 조건이 아님: 고용24 "15세 ~ 34세 청년 누구나"
    "C01": _local(9, 39, "서울시 공고 2026"),
    "C04": _local(13, 39, "충청북도 공고 2026"),
    "C05": _local(13, 39, "울산광역시 공고 2026"),
    "C07": _local(19, 34, "청년재단 공고 2026"),
}
_GROUP_ORDER = {"national": 0, "linked": 1, "local": 2}
_STATUS_ORDER = {"ok": 0, "check": 1, "no": 2}


def card_status(conditions: list[dict]) -> str:
    results = {c["result"] for c in conditions} - {"info"}   # info: 안내만 하는 조건
    return "no" if "no" in results else "ok" if results <= {"ok"} else "check"


def match(profile: dict, data: dict) -> dict:
    profile = clean_profile(profile)
    cards = []
    for program in data["programs"]:
        conditions = RULES[program["id"]](profile, program)
        if conditions is not None:
            cards.append({"id": program["id"], "group": program["group"], "status": card_status(conditions),
                          "conditions": conditions})
    cards.sort(key=lambda c: (_GROUP_ORDER[c["group"]], _STATUS_ORDER[c["status"]], c["id"]))
    return {"center": center_for(profile.get("region"), data), "cards": cards}


_TEXT = {
    "relations": {"parent": "엄마·아빠", "grandparent": "할머니·할아버지", "sibling": "형제·자매", "other": "그 밖의 가족"},
    "conditions": {"ltc_grade": "장기요양 등급", "severe_disability": "심한 장애", "mental_illness": "정신질환 진단",
                   "long_illness": "6개월 넘게 아프거나 큰 수술", "other": "그 밖의 이유"},
    "living": {"together": "같이 삶", "apart_visiting": "학교·일 때문에 따로 살지만 자주 가서 돌봄", "apart": "따로 삶"},
    "adult_other": {"none": "함께 사는 35세 이상 다른 가족 없음", "yes": "함께 사는 35세 이상 다른 가족 있음"},
    "adult_other_exception": {"ill_or_disabled": "그 가족도 아프거나 장애가 있음", "absent": "그 가족은 외국·병원·시설 등에 있어 집에 없음",
                              "none": "그 가족은 예외에 해당하지 않음"},
    "school": {"middle_high": "중·고등학생", "college": "대학생", "none": "학교에 다니지 않음"},
    "work": {"working": "일하고 있음 (아르바이트 포함)", "none": "일하지 않음"},
    "rest": {"6m_plus": "학교·일을 쉰 지 6개월 넘음", "under_6m": "학교·일을 쉰 지 6개월 안 됨"},
    "basic_livelihood": {"yes": "기초생활 수급·차상위 가구", "no": "기초생활 수급·차상위 아님"},
    "income_band": {"none": "본인 월 소득 없음", "lt100": "본인 월 소득 100만원 아래", "100_200": "본인 월 소득 100~200만원",
                    "200_256": "본인 월 소득 200~256만원", "gt256": "본인 월 소득 256만원 넘음"},
}


def profile_summary(profile: dict) -> str:
    """채팅에 붙이는 사용자 상황 (답한 항목만)."""
    profile = clean_profile(profile)
    parts = []
    if profile.get("age") is not None:
        parts.append(f"{profile['age']}세" + (f" (군 복무 {profile['military_months']}개월)" if profile.get("military_months") else ""))
        if profile.get("military_months"):
            # 모델이 "가산"을 나이에 더하는 것으로 잘못 읽으므로 계산 결과를 준다 (docs/decisions/0007)
            months = profile["military_months"]
            top = f"{34 + months // 12}세" if months % 12 == 0 else f"34세 + {months}개월"
            verdict = {"ok": "충족", "unknown": "확인 필요 (생일과 복무 기간에 따라 다름)", "no": "미충족"}
            parts.append(f"나이 상한 34세 + 군 복무 {months}개월 = {top} (시행령 제11조①1 단서) → 나이 조건 "
                         + verdict[_age(profile, 13, 34, "", military=True)["result"]])
    if profile.get("region"):
        parts.append(" ".join(x for x in (profile["region"], profile.get("sigungu")) if x) + " 거주")
    for key in ("relations", "conditions"):
        names = [_TEXT[key][v] for v in profile.get(key) or [] if v in _TEXT[key]]
        if names:
            parts.append(("돌보는 가족: " if key == "relations" else "가족의 상황: ") + ", ".join(names))
    for key in ("living", "adult_other", "adult_other_exception", "school", "work", "rest", "basic_livelihood", "income_band"):
        if profile.get(key) in _TEXT[key]:
            parts.append(_TEXT[key][profile[key]])
    known = "; ".join(parts) if parts else "입력한 정보 없음"
    return (f"User context (사용자가 앱에 입력한 상황): {known}. "
            "이 사용자의 상황에 맞춰 답하되, 받을 수 있는지 최종 판정은 하지 말고 청년미래센터·시군구청이 결정한다고 안내하세요.")

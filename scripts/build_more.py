"""공공데이터 원본 → data/programs/more.json ("일반 지원 더 보기", 자동 판정용).  python scripts/build_more.py [root]

출처: 온통청년 청년정책(raw/<날짜>/youth.json), 복지로 국가 서비스(raw/<날짜>/national.json). 자동 판정할 수 있는 것만 남긴다
(설계: docs/superpowers/specs/2026-11-01-doljabi-more-support-design.md). 검수한 지원사업(program_candidates.json)과 같은 사업은 뺀다.
"""
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
AS_OF = "2026-11-01"
RAW = ROOT / "data" / "programs" / "raw" / AS_OF
OUT = ROOT / "data" / "programs" / "more.json"
YOUTH_LINK = "https://www.youthcenter.go.kr/youthPolicy/ythPlcyTotalSearch/ythPlcyDetail/"

ANY_JOB, ANY_SCHOOL, ANY_SPECIAL = "0013010", "0049010", "0014010"   # 제한 없음
MARRIED = {"0055001", "0055002"}                    # 기혼, 미혼 (0055003 제한 없음)
NOTHING = re.compile(r"^(해당\s*없음|없음|-|무|x)$", re.I)
NATION_MIN_SIDOS = 15                               # 시·도 15곳 이상이면 전국
NATIONAL_THEMES = {"생활지원", "서민금융", "신체건강", "정신건강", "교육", "일자리", "주거", "보호·돌봄", "안전·위기", "법률", "문화·여가"}
ONLY_FOR_OTHERS = {"보훈대상자", "다문화·탈북민"}
# 사용자가 신청할 수 없는 행정 업무 (위원회 운영, 조사, 개발사업). "위원 모집"처럼 참여할 수 있는 것은 남긴다
NOT_SUPPORT = re.compile(r"실태조사|조성사업|개발사업|정비사업|기본계획|시행계획|연구용역|조정위원회|위원회 (구성|운영|설치)|위원회 운영$|청년참여 확대|참여비율|위촉 지정관리|교통서비스 개선|조성$|시스템 구축|DB\s?고도화|포인트제 도입|제도개선$|모니터링$|기숙사 확충|정책\s?홍보|홍보사업$|책임관제|친화도시|고용의무제")
# 대학·연구소가 신청하는 역량 사업 (연구소, 대학원, 대학 지원 체계): 학생이 신청하거나 받는 것이 없다 → 뺀다
FOR_SCHOOLS = re.compile(r"중점연구소|연구센터 지원|단과대학|대학원\s?(지원|운영)|특성화\s?대학원|대학지원체계|RISE|글로컬대학|대학혁신|인재양성체계|공유대학|학과개편|교육혁신센터|교육과정 연계|대학 상생협력")
FOR_SCHOOLS_TEXT = re.compile(r"거점대학|수행대학|연구거점")
# 대학이 공모로 선정되고 그 학교 학생이 받는 사업 → 남기고 "학교가 선정된 경우에만" (via_school)
VIA_SCHOOL = re.compile(r"중심대학|특성화\s?대학|특성화학과|혁신융합대학|중점대학|천원의\s?아침밥|대학일자리|농업계대학|마이스터대|대학별|대학\s?핵심역량|공학인재|도제학교|대학만들기")
VIA_SCHOOL_TEXT = re.compile(r"\d+\s*개\s*(교|대학)\S*\s*(공모|선정)|대학을?\s*(공모|선정)|선정\s*대학|중점대학|대학별 특성|협약을 맺은.{0,10}대학")
# 원본의 주거 분류 중 주거와 관계없는 것은 생활·금융으로
HOUSING_WORDS = re.compile(r"주거|주택|월세|전세|임대|기숙|거주|보금자리|원룸|셰어|하우스|숙소|이사|청약|보증금|입주|빌리지|공공분양|모기지|학사관|전입")
THEME_GROUP = [("정신건강", "health"), ("신체건강", "health"), ("주거", "housing"), ("일자리", "jobs"), ("교육", "education")]


def one_line(text: str, limit: int = 90) -> str:
    text = re.sub(r"\s+", " ", html.unescape(text or "")).strip(" -ㅇ○❍")
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def split(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def youth_group(p: dict) -> str:
    large, middle = split(p.get("lclsfNm"))[:1] or [""], p.get("mclsfNm") or ""
    large = large[0]
    if large.startswith("일자리"):
        return "jobs"
    if large.startswith("주거"):
        return "housing"
    if large.startswith("교육"):
        return "education"
    if large.startswith("참여"):
        return "participation"
    return "health" if "건강" in middle else "life"


def periods(p: dict) -> dict:
    kind = {"0057002": "always", "0057001": "range"}.get(p.get("aplyPrdSeCd"), "tbd")
    if kind != "range":
        return {"kind": kind, "ranges": []}
    ranges = re.findall(r"(\d{8})\s*~\s*(\d{8})", p.get("aplyYmd") or "")
    return {"kind": "range", "ranges": [list(r) for r in ranges]}


AGE_RANGE = re.compile(r"(\d{1,2})\s*세?\s*[~∼～-]\s*(?:만\s*)?(\d{1,2})\s*세")
AGE_MIN = re.compile(r"(\d{1,2})\s*세\s*이상")
AGE_MAX = re.compile(r"(\d{1,2})\s*세\s*이하")
TARGET_PART = re.compile(r"대상\s*\)?\s*[:：]?\s*([^ㅇ○\n]{0,80})")
OTHER_PERSON = re.compile(r"아동|자녀|아이|영유아|어르신|노인|어린이|초등")   # 신청자가 아닌 사람의 나이 ("12세 이하 아동")


def text_age(p: dict) -> list[int] | None:
    """나이 제한 Y, 0~0세인 정책: 대상 글(추가 자격, 지원 내용의 "(대상) …")에서 신청자 나이 범위를 읽는다. 없으면 None."""
    def own(text: str, m) -> bool:
        return not OTHER_PERSON.search(text[max(0, m.start() - 12):m.end() + 8])

    texts = [p.get("addAplyQlfcCndCn") or ""] + TARGET_PART.findall(p.get("plcySprtCn") or "")
    for text in texts:
        m = next((m for m in AGE_RANGE.finditer(text) if own(text, m) and int(m.group(1)) <= int(m.group(2))), None)
        lo_m = next((m for m in AGE_MIN.finditer(text) if own(text, m)), None)
        hi_m = next((m for m in AGE_MAX.finditer(text) if own(text, m)), None)
        if m:
            age = [int(m.group(1)), int(m.group(2))]
        elif lo_m or hi_m:
            age = [int(lo_m.group(1)) if lo_m else 0, int(hi_m.group(1)) if hi_m else 99]
        else:
            continue
        if age[1] >= 13 and age[0] <= 39:       # 청년 나이대와 겹치지 않으면 다른 사람 이야기로 보고 버린다
            return age
    return None


def number(value) -> int | None:
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def youth_items(policies: list[dict], reviewed: set[str]) -> list[dict]:
    codes_by_sido = defaultdict(set)
    for p in policies:
        for z in split(p.get("zipCd")):
            codes_by_sido[z[:2]].add(z)
    items = []
    for p in policies:
        pid = f"Y:{p['plcyNo']}"
        if pid in reviewed or p.get("earnCndSeCd") not in ("0043001", "0043002"):
            continue
        text = " ".join(p.get(k) or "" for k in ("plcyExplnCn", "plcySprtCn"))
        if FOR_SCHOOLS.search(p["plcyNm"]) or FOR_SCHOOLS_TEXT.search(text):
            continue                                  # 학교·연구소가 신청하는 사업
        period = periods(p)
        if period["kind"] == "range" and period["ranges"] and all(end < AS_OF.replace("-", "") for _, end in period["ranges"]):
            continue                                  # 신청이 끝남
        zips = split(p.get("zipCd"))
        sidos = sorted({z[:2] for z in zips})
        if not sidos:
            continue
        whole = all(codes_by_sido[s] <= set(zips) for s in sidos)
        scope = "nation" if len(sidos) >= NATION_MIN_SIDOS else "sido" if whole else "local"
        lo, hi = number(p.get("sprtTrgtMinAge")), number(p.get("sprtTrgtMaxAge"))
        age = None
        if p.get("sprtTrgtAgeLmtYn") == "Y" and (lo is not None or hi is not None):
            lo = lo or 0
            age = [lo, 99 if hi is None or (hi == 0 and lo > 0) else hi]
            if age == [0, 0]:
                age = text_age(p)                                         # 범위가 글로만 적힘: 글에서 읽고, 없으면 나이 칸 없음
            if age == [0, 99]:
                age = None                                                # 사실상 나이 제한 없음
        income = None
        if p.get("earnCndSeCd") == "0043002":
            top = number(p.get("earnMaxAmt"))
            income = [number(p.get("earnMinAmt")) or 0, top or None]
        jobs, schools = split(p.get("jobCd")), split(p.get("schoolCd"))
        items.append({
            "id": pid, "source": "youth", "name": one_line(p["plcyNm"], 60),
            "summary": one_line(p.get("plcySprtCn") or p.get("plcyExplnCn")), "org": one_line(p.get("sprvsnInstCdNm"), 40),
            "link": YOUTH_LINK + p["plcyNo"], "group": youth_group(p),
            "zips": zips if scope == "local" else [], "sidos": sidos, "scope": scope, "age": age, "income": income, "period": period,
            "jobs": [] if ANY_JOB in jobs else jobs, "schools": [] if ANY_SCHOOL in schools else schools,
            "special": [c for c in split(p.get("sbizCd")) if c != ANY_SPECIAL],
            "married": p.get("mrgSttsCd") if p.get("mrgSttsCd") in MARRIED else None,
            "extra": not NOTHING.match(re.sub(r"\s+", " ", p.get("addAplyQlfcCndCn") or "").strip() or "-"),
            "via_school": bool(VIA_SCHOOL.search(p["plcyNm"]) or VIA_SCHOOL_TEXT.search(text)),
        })
    return items


def national_items(services: list[dict], reviewed: set[str]) -> list[dict]:
    items = []
    for s in services:
        sid = f"N:{s['servId']}"
        life = [x for x in ("청소년", "청년") if x in (s.get("lifeArray") or "")]
        themes, targets = set(split(s.get("intrsThemaArray"))), split(s.get("trgterIndvdlArray"))
        link = s.get("servDtlLink") or ""
        if sid in reviewed or not life or not themes & NATIONAL_THEMES or (targets and set(targets) <= ONLY_FOR_OTHERS):
            continue
        if not link.startswith("https://"):
            continue
        group = next((g for theme, g in THEME_GROUP if theme in themes), "life")
        items.append({
            "id": sid, "source": "national", "name": one_line(s["servNm"], 60), "summary": one_line(s.get("servDgst")),
            "org": one_line(" ".join(x for x in (s.get("jurMnofNm"), s.get("jurOrgNm")) if x), 40),
            "link": link, "group": group, "life": life, "targets": targets, "online": s.get("onapPsbltYn") == "Y",
        })
    return items


def main() -> None:
    candidates = json.loads((ROOT / "scripts" / "program_candidates.json").read_text(encoding="utf-8"))
    reviewed = {f"N:{c['bokjiro']}" for c in candidates if c.get("bokjiro")} | {f"Y:{c['youth']}" for c in candidates if c.get("youth")}
    youth = json.loads((RAW / "youth.json").read_text(encoding="utf-8"))
    national = json.loads((RAW / "national.json").read_text(encoding="utf-8"))
    items, seen = [], set()
    for i in youth_items(youth, reviewed) + national_items(national, reviewed):
        key = (re.sub(r"\s+", "", i["name"]), i["org"])
        if key in seen or NOT_SUPPORT.search(i["name"]):
            continue                                  # 같은 사업이 여러 번 올라온 것, 신청할 수 없는 행정 업무
        seen.add(key)
        if i["group"] == "housing" and not HOUSING_WORDS.search(i["name"] + i["summary"]):
            i["group"] = "life"
        items.append(i)
    lines = ",\n".join(json.dumps(i, ensure_ascii=False, separators=(",", ":")) for i in items)
    OUT.write_text(f'{{"as_of": "{AS_OF}", "items": [\n{lines}\n]}}\n', encoding="utf-8")
    print(f"more.json: youth {sum(i['source'] == 'youth' for i in items)}, national {sum(i['source'] == 'national' for i in items)}")


if __name__ == "__main__":
    main()

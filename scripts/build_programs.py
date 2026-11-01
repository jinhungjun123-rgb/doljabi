"""검수 결과(data/programs/review/*_v3.json) → 앱용 data/programs/programs.json.

    python scripts/build_programs.py

검수 파일의 값은 바꾸지 않고, 앱이 쓰는 키로 옮기고 카드 한 줄 요약(SUMMARY)만 덧붙인다.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "data" / "programs" / "review" / "지원사업_초안_2026-11-01_v3.json"
OUT = ROOT / "data" / "programs" / "programs.json"

GROUP = {"A": "national", "B": "linked", "C": "local"}
REGION = {"C01": "서울", "C04": "충북", "C05": "울산", "C07": "광주"}
SUMMARY = {
    "A01": "자기계발·건강에 쓰는 1회 200만원 이용권",
    "A02": "1:1 상담과 필요한 지원 연결",
    "A03": "13세 미만 가족돌봄아동 집중 사례관리",
    "A04": "집으로 오는 돌봄·가사 서비스 바우처",
    "A05": "아픈 가족의 요양시설 이용 지원",
    "A06": "기초생활 수급 가구 자활 참여 조건 1년 유예",
    "B01": "대학 등록금 지원 (센터가 신청을 도와줘요)",
    "B03": "무료 법률 상담",
    "B04": "구직 준비 프로그램 + 참여수당",
    "B05": "미취업 청년 맞춤 프로그램",
    "C01": "서울시 자체 자기돌봄비",
    "C04": "충북 가족돌봄청년 사례관리·프로그램",
    "C05": "울산 가족돌봄청년 사례관리·자기돌봄비",
    "C07": "광주 청년 1:1 관리·식비 바우처",
}
A01_NOTICE = "일부 지역 안내는 '연 200만원'이라고 쓰지만, 법령은 1회예요."
CENTER_REGION = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주 (전남광주통합특별시)": "광주",
    "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전남 (전남광주통합특별시)": "전남",
    "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
}
MISSING = {"", "-", "확인 안 됨"}


def _notice(pid: str, row: dict) -> str | None:
    if pid == "A01":
        return A01_NOTICE
    for text in (row["지원 내용"], row["⚠ 확인할 점"]):
        m = re.search(r"\(([^()]*지역 안내 표기와 다름[^()]*)\)", text or "")
        if m:
            return m.group(1)
    return None


def program(row: dict) -> dict:
    pid = row["ID"]
    return {"id": pid, "group": GROUP[pid[0]], "name": row["사업명"], "summary": SUMMARY[pid], "region": REGION.get(pid),
            "apply_type": row["신청 구분"], "target": row["대상 (나이·조건)"], "income": row["소득 기준"],
            "benefit": row["지원 내용"], "how": row["신청 방법·신청처"], "period": row["신청 기간"], "contact": row["문의"],
            "source": row["출처"], "notice": _notice(pid, row), "closed": (row["신청 기간"] or "").startswith("2026년 마감"),
            "checked": row["자료 확인일"]}


def center(row: dict) -> dict | None:
    region = CENTER_REGION.get(row["시·도"])
    if region is None:   # "(준비 중인 지역 공통)" 같은 안내 행
        return None
    status = row["상태 (2026-11-01 청년ON 기준)"]
    is_open = status.startswith("운영")
    name = re.sub(r"\s*\(.*$", "", status.split(":", 1)[1]).strip() if is_open and ":" in status else None
    phone, email = row["전화"], row["개인정보활용동의서 제출 메일"]
    return {"region": region, "name": name, "status": "open" if is_open else "preparing",
            "phone": None if phone in MISSING else phone, "email": None if email in MISSING else email}


def main():
    src = json.loads(REVIEW.read_text(encoding="utf-8"))
    programs = [program(dict(zip(src["columns"], r))) for r in src["programs"]]
    centers = [c for c in (center(dict(zip(src["center_columns"], r))) for r in src["centers"]) if c]
    OUT.write_text(json.dumps({"updated": src["created"], "programs": programs, "centers": centers},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(OUT, len(programs), "programs,", len(centers), "centers")


if __name__ == "__main__":
    main()

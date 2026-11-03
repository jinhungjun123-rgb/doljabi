"""앱용 지원사업·센터 데이터 (data/programs/programs.json, 팀 검수 2026-11-01)."""
from ragbot.domain.programs import REGIONS, center_for, load_programs


def test_programs_file_matches_review():
    d = load_programs()
    ids = [p["id"] for p in d["programs"]]
    assert ids == ["A01", "A02", "A03", "A04", "A05", "A06", "B01", "B04", "B05", "C01", "C04", "C05", "C07"]
    a01 = next(p for p in d["programs"] if p["id"] == "A01")
    assert "1회" in a01["benefit"] and "200만원" in a01["benefit"] and a01["group"] == "national"
    c05 = next(p for p in d["programs"] if p["id"] == "C05")
    assert c05["region"] == "울산" and "지역 안내 표기와 다름" in c05["notice"]
    assert {p["id"] for p in d["programs"] if p["closed"]} == {"C01", "C07"}


def test_no_review_file_wording_reaches_users():
    for p in load_programs()["programs"]:
        text = " ".join(str(v) for v in p.values())
        assert "data/docs" not in text and "시트" not in text and "Claude" not in text, p["id"]


def test_centers_cover_all_regions():
    d = load_programs()
    assert sorted(c["region"] for c in d["centers"]) == sorted(REGIONS)
    assert sum(c["status"] == "open" for c in d["centers"]) == 12
    assert center_for("대구", d)["phone"] == "053-248-4113"
    assert center_for("전남", d)["phone"] is None and center_for("경기", d)["status"] == "preparing"
    assert center_for(None, d) is None


def test_application_pages_are_in_how_not_source():
    # 검수 파일이 출처에 적은 "… 신청 페이지 <주소>"는 출처가 아니라 신청 방법 칸의 링크로 보여 준다
    apply_url = "https://capi.kmaresearch.co.kr/survey/20260266/index_1.asp"
    progs = {p["id"]: p for p in load_programs()["programs"]}
    for p in progs.values():
        assert "신청 페이지" not in (p["source"] or "") and apply_url not in (p["source"] or ""), p["id"]
    for pid in ("A01", "A02", "C05"):
        assert apply_url in progs[pid]["how"], pid
    assert "https://mediahub.seoul.go.kr/archives/2019538" in progs["A01"]["source"]   # 정보 출처는 남김

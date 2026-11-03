"""판정 규칙 (domain/eligibility.py): 법령의 요건과 예외가 카드 상태로 맞게 나오는지."""
from ragbot.domain.eligibility import card_status, match, profile_summary
from ragbot.domain.programs import load_programs

# 충북 20세 대학생, 6개월 넘게 아픈 엄마와 함께 살며 돌봄, 35세 이상 다른 가족 없음, 소득 없음
BASE = {"age": 20, "region": "충북", "relations": ["parent"], "conditions": ["long_illness"], "living": "together",
        "adult_other": "none", "school": "college", "work": "none", "basic_livelihood": "no", "income_band": "none"}


def cards(profile):
    return {c["id"]: c for c in match(profile, load_programs())["cards"]}


def test_base_profile():
    c = cards(BASE)
    assert c["A01"]["status"] == "ok" and c["A02"]["status"] == "ok" and c["A04"]["status"] == "ok"
    assert "A03" not in c and "C04" in c and "C01" not in c and "B01" in c
    assert match(BASE, load_programs())["center"]["phone"] == "1551-1259"


def test_all_unknown():
    c = cards({})
    assert c["A01"]["status"] == "check" and c["A02"]["status"] == "check" and "A03" not in c


def test_age_edges():
    child = cards({**BASE, "age": 12})
    assert child["A03"]["status"] == "ok" and "A01" not in child
    assert cards({**BASE, "age": 35, "military_months": 24})["A01"]["status"] == "ok"
    assert cards({**BASE, "age": 35})["A01"]["status"] == "no"
    assert cards({**BASE, "age": 40})["A01"]["status"] == "no"


def test_adult_exception():   # 35세 이상 형이 함께 살지만 장애가 있으면 예외
    assert cards({**BASE, "adult_other": "yes", "adult_other_exception": "ill_or_disabled"})["A01"]["status"] == "ok"
    assert cards({**BASE, "adult_other": "yes", "adult_other_exception": "none"})["A01"]["status"] == "no"


def test_address_and_together():   # 학업·취업으로 따로 살며 돌보면 주소 예외지만, 일상돌봄은 함께 살아야 함
    c = cards({**BASE, "living": "apart_visiting"})
    assert c["A01"]["status"] == "ok" and c["A04"]["status"] == "no"


def test_income_band():
    c = cards({**BASE, "income_band": "gt256"})
    assert c["A01"]["status"] == "no" and c["A02"]["status"] == "ok"


def test_conditional_cards():
    ltc = cards({**BASE, "conditions": ["ltc_grade"]})
    assert ltc["A05"]["status"] == "check"
    assert "A05" not in cards(BASE)
    assert "A06" in cards({**BASE, "basic_livelihood": "yes"}) and "A06" not in cards(BASE)


def test_center_fallback():
    d = load_programs()
    assert match({**BASE, "region": "전남"}, d)["center"]["phone"] is None
    assert match({**BASE, "region": "경기"}, d)["center"]["status"] == "preparing"
    assert match({}, d)["center"] is None


def test_every_condition_has_law():
    for c in match(BASE, load_programs())["cards"]:
        assert all(x["law"] and x["result"] in {"ok", "unknown", "no", "info"} for x in c["conditions"])


def test_card_order_and_status_rule():
    ids = [c["id"] for c in match(BASE, load_programs())["cards"]]
    assert ids.index("A01") < ids.index("B01") < ids.index("C04")
    assert card_status([]) == "ok"
    assert card_status([{"result": "ok"}, {"result": "unknown"}]) == "check"
    assert card_status([{"result": "unknown"}, {"result": "no"}]) == "no"
    assert card_status([{"result": "ok"}, {"result": "info"}]) == "ok"


def test_profile_summary():
    s = profile_summary(BASE)
    assert "20세" in s and "충북" in s and "최종" in s


def test_profile_summary_states_the_age_limit_raised_by_military_service():
    # 시행령 제11조①1 단서: 34세 상한에 병역 기간을 더한다. 계산은 코드가 하고, 채팅 모델에는 결과를 준다.
    s = profile_summary({**BASE, "age": 35, "military_months": 24})
    assert "36세" in s and "충족" in s
    assert "36세" not in profile_summary({**BASE, "age": 35})


def test_part_of_a_service_year_needs_checking():
    # 시행령 제11조①1 단서는 실제 복무 기간을 더한다: 35세 + 1개월은 생일 뒤 한 달만 해당하므로 "확인 필요"
    age = cards({**BASE, "age": 35, "military_months": 1})["A01"]["conditions"][0]
    assert age["result"] == "unknown"
    assert cards({**BASE, "age": 36, "military_months": 24})["A01"]["conditions"][0]["result"] == "ok"
    s = profile_summary({**BASE, "age": 35, "military_months": 1})
    assert "나이 조건 확인 필요" in s and "나이 조건 충족" not in s


def test_wrong_field_types_count_as_unanswered():
    # 옛 형식이나 손으로 고친 저장값: 판정이 멈추지 않고 그 항목만 모르는 것으로 본다
    for bad in ({"age": "20"}, {"conditions": 5}, {"relations": "parent"}, {"military_months": "x", "age": 35},
                {"age": True}, {"living": ["together"]}):
        c = cards({**BASE, **bad})
        assert c["A01"]["status"] in ("ok", "check", "no")
        profile_summary({**BASE, **bad})


def test_study_work_hardship_is_left_to_the_center():
    # 법 제13조①1라목 "학업 및 취업에 상당한 곤란"은 객관적 기준이 없고 센터가 상담으로 판단한다: 묻지 않고 안내만 (결정 0012)
    for pid in ("A01", "A02"):
        row = next(x for x in cards(BASE)[pid]["conditions"] if "곤란" in x["label"])
        assert row["result"] == "info" and row["law"] == "법 제13조①1라목" and "상담" in row["label"]
    old = {**BASE, "burden": "none"}   # 예전에 저장된 답은 판정에 쓰지 않는다
    assert cards(old)["A01"]["status"] == "ok"
    assert "힘듦" not in profile_summary(old)


SCHOOL_ONLY = "학교에 다니지 않음 (졸업예정자·사이버·방송통신·야간대 재학생은 참여 가능)"


def test_college_student_who_works():
    # 4단계는 학교와 일을 따로 묻는다: 대학에 다니면서 일하는 청년 (결정 0014)
    c = cards({**BASE, "school": "college", "work": "working"})
    assert "B01" in c                                                       # 대학생이면 장학금 (일해도 됨)
    b05 = {x["label"]: x["result"] for x in c["B05"]["conditions"]}
    assert b05[SCHOOL_ONLY] == "unknown" and c["B05"]["status"] == "check"  # 재학생은 원칙적으로 어렵고 예외 있음
    assert c["B04"]["status"] == "no"                                       # 6개월 넘게 취업·교육 이력 없음이 아님


def test_youth_growth_project_is_open_to_working_youth():
    # 고용24: "15세 ~ 34세 청년 누구나", 복지로: "입사 초기 청년을 위한 프로그램도 있어요" → 미취업 조건 없음
    c = cards({**BASE, "school": "none", "work": "working"})
    assert c["B05"]["status"] == "ok" and "B01" not in c
    assert "미취업" not in " ".join(x["label"] for x in c["B05"]["conditions"])


def test_challenge_needs_six_months_without_work_or_school():
    assert cards({**BASE, "school": "none", "work": "none", "rest": "6m_plus"})["B04"]["status"] == "ok"
    assert cards({**BASE, "school": "none", "work": "none", "rest": "under_6m"})["B04"]["status"] == "check"
    assert cards({**BASE, "school": "none", "work": "working"})["B04"]["status"] == "no"


def test_old_single_activity_answer_still_works():
    # 예전 4단계 답(activity 하나)은 학교·일로 옮겨 판정한다
    assert "B01" in cards({**{k: v for k, v in BASE.items() if k not in ("school", "work")}, "activity": "college"})
    old = {k: v for k, v in BASE.items() if k not in ("school", "work")}
    assert cards({**old, "activity": "rest_6m_plus"})["B04"]["status"] == "ok"
    assert cards({**old, "activity": "working"})["B05"]["status"] == "check"    # 학교에 다니는지는 몰랐다


def test_profile_summary_has_school_and_work():
    s = profile_summary({**BASE, "school": "college", "work": "working"})
    assert "대학생" in s and "일하고 있음" in s

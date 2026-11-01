"""판정 규칙 (domain/eligibility.py): 법령의 요건과 예외가 카드 상태로 맞게 나오는지."""
from ragbot.domain.eligibility import card_status, match, profile_summary
from ragbot.domain.programs import load_programs

# 충북 20세 대학생, 6개월 넘게 아픈 엄마와 함께 살며 돌봄, 35세 이상 다른 가족 없음, 돌봄 때문에 학업이 많이 힘듦, 소득 없음
BASE = {"age": 20, "region": "충북", "relations": ["parent"], "conditions": ["long_illness"], "living": "together",
        "adult_other": "none", "activity": "college", "burden": "high", "basic_livelihood": "no", "income_band": "none"}


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
        assert all(x["law"] and x["result"] in {"ok", "unknown", "no"} for x in c["conditions"])


def test_card_order_and_status_rule():
    ids = [c["id"] for c in match(BASE, load_programs())["cards"]]
    assert ids.index("A01") < ids.index("B01") < ids.index("C04")
    assert card_status([]) == "ok"
    assert card_status([{"result": "ok"}, {"result": "unknown"}]) == "check"
    assert card_status([{"result": "unknown"}, {"result": "no"}]) == "no"


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

"""일반 지원 자동 판정 (domain/more.py): 공공데이터의 구조화된 조건만으로 ok / unknown / no."""
from ragbot.domain.more import GROUP_LABELS, judge, load_more, more_for

TODAY = "20261101"


def youth(**kw):
    base = {"id": "Y:1", "source": "youth", "name": "청년 정책", "summary": "설명", "org": "충청북도 청주시 청년정책과",
            "link": "https://www.youthcenter.go.kr/x", "group": "life", "zips": [], "sidos": ["43"], "scope": "sido",
            "age": None, "income": None, "period": {"kind": "always", "ranges": []}, "jobs": [], "schools": []}
    return {**base, **kw}


def national(**kw):
    base = {"id": "N:1", "source": "national", "name": "국가 서비스", "summary": "설명", "org": "보건복지부",
            "link": "https://www.bokjiro.go.kr/x", "group": "life", "life": ["청년"], "targets": [], "online": True}
    return {**base, **kw}


def rows(item, profile):
    r = judge(item, profile, TODAY)
    return {c["key"]: c["result"] for c in r["conditions"]}


ME = {"age": 20, "region": "충북"}


def test_age_income_job_conditions():
    assert rows(youth(age=[19, 34]), ME)["age"] == "ok"
    assert rows(youth(age=[19, 34]), {**ME, "age": 40})["age"] == "no"
    assert rows(youth(income=[0, 5000]), {**ME, "income_band": "lt100"})["income"] == "ok"
    assert rows(youth(income=[0, 2400]), {**ME, "income_band": "gt256"})["income"] == "no"
    assert rows(youth(income=[0, 2000]), {**ME, "income_band": "100_200"})["income"] == "unknown"
    assert rows(youth(jobs=["0013003"]), {**ME, "activity": "working"})["job"] == "no"
    assert rows(youth(jobs=["0013003"]), {**ME, "activity": "rest_6m_plus"})["job"] == "ok"
    assert rows(youth(jobs=["0013003"]), {**ME, "activity": "college"})["job"] == "unknown"
    assert "job" not in rows(youth(), {**ME, "activity": "working"})
    assert rows(youth(schools=["0049005"]), {**ME, "activity": "college"})["school"] == "ok"


def test_region_rows():
    assert rows(youth(), ME)["region"] == "ok"
    local = youth(scope="local", zips=["43111"])
    assert rows(local, {**ME, "sigungu": "청주"})["region"] == "ok"
    assert rows(local, {**ME, "sigungu": "충주시"})["region"] == "no"      # 같은 도의 다른 시·군
    assert rows(local, ME)["region"] == "unknown"
    assert rows(youth(scope="local", org="충청북도 청년정책과"), {**ME, "sigungu": "청주"})["region"] == "unknown"
    assert judge(youth(), {**ME, "region": "서울"}, TODAY) is None          # 다른 시·도는 목록에서 뺌


def test_no_region_keeps_nationwide_only():
    assert judge(youth(), {"age": 20}, TODAY) is None
    nation = judge(youth(scope="nation", sidos=["11", "43"]), {"age": 20}, TODAY)
    assert nation and "region" not in {c["key"] for c in nation["conditions"]}
    assert judge(national(), {"age": 20}, TODAY) is not None


def test_gwangju_jeonnam_use_code_12():
    for region in ("광주", "전남"):
        assert rows(youth(sidos=["12"]), {"age": 20, "region": region})["region"] == "ok"


def test_period():
    def period(kind, ranges=()):
        return youth(period={"kind": kind, "ranges": [list(r) for r in ranges]})
    assert rows(period("always"), ME)["period"] == "ok"
    assert rows(period("range", [("20261001", "20261130")]), ME)["period"] == "ok"
    assert rows(period("range", [("20261201", "20261231")]), ME)["period"] == "unknown"
    assert judge(period("range", [("20260101", "20260301")]), ME, TODAY) is None
    assert rows(period("tbd"), ME)["period"] == "unknown"


def test_odd_application_dates():
    assert rows(youth(period={"kind": "range", "ranges": []}), ME)["period"] == "unknown"
    assert rows(youth(period={"kind": "range", "ranges": [["2026", "x"]]}), ME)["period"] == "unknown"


def test_national_life_and_targets():
    assert rows(national(), ME)["age"] == "ok"
    assert rows(national(), {**ME, "age": 15})["age"] == "no"
    assert rows(national(life=["청소년"]), {**ME, "age": 15})["age"] == "ok"
    assert rows(national(targets=["저소득"]), {**ME, "basic_livelihood": "yes"})["target"] == "ok"
    assert rows(national(targets=["저소득"]), {**ME, "basic_livelihood": "no"})["target"] == "unknown"
    assert rows(national(targets=["장애인"]), ME)["target"] == "unknown"


def test_empty_profile():
    data = load_more()
    judged = [judge(i, {}, TODAY) for i in data["items"]]
    assert all(r is None or r["status"] != "no" for r in judged)
    assert any(r for r in judged)


def test_more_for_real_file():
    out = more_for({"age": 20, "region": "충북", "activity": "college"}, load_more(), TODAY)
    keys = [g["key"] for g in out["groups"]]
    assert out["as_of"] == "2026-11-01" and keys == [k for k in GROUP_LABELS if k in keys] and len(keys) >= 5
    order = {"ok": 0, "check": 1}
    for g in out["groups"]:
        assert g["label"] == GROUP_LABELS[g["key"]]
        statuses = [order[i["status"]] for i in g["items"]]
        assert statuses == sorted(statuses)
        assert all(i["status"] == "no" for i in g["no_items"])


def test_restrictions_written_elsewhere_need_checking():
    # 특화 대상(자립준비청년 등 '기타'), 혼인 조건, 글로만 적힌 추가 자격은 판정할 수 없으므로 "확인 필요" 행이 된다
    assert rows(youth(special=["0014009"]), ME)["special"] == "unknown"
    assert rows(youth(special=["0014003"]), {**ME, "basic_livelihood": "yes"})["special"] == "ok"
    assert rows(youth(married="0055001"), ME)["married"] == "unknown"
    assert rows(youth(extra=True), ME)["extra"] == "unknown"
    assert judge(youth(extra=True), ME, TODAY)["status"] == "check"


def test_ages_and_national_rules_only_in_text_need_checking():
    # 온통청년의 "나이 제한 있음, 0~0세"는 범위가 글로만 적힌 것 (630개). 복지로 국가 서비스는 자격이 설명 글에만 있다
    assert rows(youth(age=[0, 0]), ME)["age"] == "unknown"
    assert rows(national(), ME)["extra"] == "unknown"
    assert judge(national(), ME, TODAY)["status"] == "check"


def test_target_named_only_in_the_title_needs_checking():
    assert rows(youth(name="자립준비청년 디지털 진로지원"), ME)["special"] == "unknown"
    assert rows(youth(name="청년 예술인 창작 지원"), ME)["special"] == "unknown"
    assert "special" not in rows(youth(name="청년 문화예술패스"), ME)

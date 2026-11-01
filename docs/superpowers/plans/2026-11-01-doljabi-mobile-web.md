# 돌잡이 모바일 웹 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 질문 5단계 → 받을 수 있어 보이는 지원 카드(법령 근거) → 채팅으로 이어 묻기를 하는 모바일 웹앱 "돌잡이"를 오늘 완성해 Hugging Face에 배포한다.

**Architecture:** 판정은 LLM 없이 `src/ragbot/domain/eligibility.py`의 규칙 코드가 하고, 지원사업·센터는 검수한 `data/programs/programs.json`에서 읽는다. `app/api.py`(Starlette)가 화면 파일, `/api/programs`, `/api/match`, `/api/chat`(SSE, 기존 `Chatbot`)을 제공한다. 화면은 빌드 없는 `web/` (HTML·CSS·JS).

**Tech Stack:** Python 3.11, Starlette 1.10.0 + uvicorn 0.54.0 (이미 requirements.lock에 있음), pytest + starlette TestClient(httpx 0.28.1), 바닐라 JS, Pretendard, Docker on Hugging Face Spaces.

**Spec:** `docs/superpowers/specs/2026-11-01-doljabi-mobile-web-design.md`

## Global Constraints

- 새 의존성 추가 금지 (requirements.lock 그대로). 배포도 git push로 한다 (huggingface_hub 설치 안 함).
- 도메인 단어(자기돌봄비, 가족돌봄, 청년미래센터, 충북, 보도자료 …)는 `src/ragbot/domain/`, `config.yaml`, `web/`, `data/`에만. `app/*.py`와 나머지 `src/ragbot/` 금지 (`tests/test_core_is_domain_free.py`).
- 층 규칙 (`tests/test_architecture.py`): `domain`은 config·llm·schemas·ingest·tools·domain만 import.
- `data/docs/`, `data/tables/` 원본 수정 금지. 검수 결과의 값은 바꾸지 않는다 (`data/programs/review/*_v3.json`이 원본).
- 앱 이름 "돌잡이 (돌봄길잡이)", 코랄 테마, Pretendard, 한국어/영어 UI.
- 결과는 "받을 수 있어 보여요 / 확인이 필요해요 / 어려워 보여요"만. 최종 판정 문구 금지, 화면마다 "최종 결정은 청년미래센터와 시·군·구청이 해요".
- 법령과 다른 지역 표기는 법령 기준 + "지역 안내 표기와 다름". 소득 기준은 2026 1인 가구 기준 중위소득 2,564,238원, 항상 "대략".
- 개인정보: 내 정보는 브라우저 localStorage에만. 앱 서버는 `runs/` 기록 끄고(`write_traces=False`), `CACHE_MODE=nostore`.
- Python 실행: `PY="$USERPROFILE/miniforge3/envs/my_ragbot/python.exe"` (Git Bash). 모든 명령은 저장소 루트에서.
- 커밋은 브랜치 `feat/doljabi-app`에서만.

## Review Focus

1. 모든 질문에 "잘 모르겠어요" 또는 빈 값 → 판정이 예외 없이 동작하고 자기돌봄비·사례관리는 "확인이 필요해요" (Task 2 `test_all_unknown`).
2. 나이 경계: 12세 → 드림스타트만 국가 제도로, 35세 + 군 24개월 → 자기돌봄비 나이 ✅, 40세 → 자기돌봄비 나이 ❌인데 카드는 이유와 함께 보임 (Task 2 `test_age_edges`).
3. 센터가 준비 중이거나 전화번호가 빈 지역(전남 전화 없음, 경기 준비 중) → `center.phone`이 `None`, 화면은 "청년ON · 129"로 대체, "📞 undefined" 금지 (Task 2 `test_center_fallback`, Task 5 수동 확인).
4. LLM 서버 무응답·예외 → `/api/chat`이 `error` 이벤트로 끝나고 매달리지 않음, `/api/match`는 영향 없음 (Task 4 `test_chat_error_event`).
5. 깨진 localStorage 프로필(옛 형식, JSON 오류) → 앱이 프로필을 지우고 1단계부터 시작 (Task 5 수동 확인 단계).

---

### Task 1: 앱용 데이터 파일과 읽기 모듈

**Files:**
- Create: `scripts/collect_programs.py`, `scripts/build_review.py` (임시 폴더의 `fetch_lists.py`+`fetch_details.py`, `build_review.py`를 옮김. 경로 인자는 그대로)
- Create: `scripts/build_programs.py`
- Create: `data/programs/programs.json` (생성물, 커밋함)
- Create: `src/ragbot/domain/programs.py`
- Test: `tests/test_programs.py`
- Modify: `.gitignore` (`.superpowers/`, `data/programs/raw/`, `build/` 추가)

**Interfaces:**
- Produces: `load_programs(path: Path = PROGRAMS_FILE) -> dict` → `{"updated": str, "programs": [Program], "centers": [Center]}`
  - `Program`: `{"id","group"("national"|"linked"|"local"),"name","summary","region"(str|None),"apply_type","target","income","benefit","how","period","contact","source","notice"(str|None),"closed"(bool),"checked"(str)}`
  - `Center`: `{"region","name","status"("open"|"preparing"),"phone"(str|None),"email"(str|None)}`
  - `REGIONS: list[str]` = `["서울","부산","대구","인천","광주","대전","울산","세종","경기","강원","충북","충남","전북","전남","경북","경남","제주"]`
  - `center_for(region: str | None, data: dict) -> Center | None`

- [ ] **Step 1:** `git checkout -b feat/doljabi-app`. `.gitignore`에 세 줄 추가.
- [ ] **Step 2: 실패하는 테스트 작성** — `tests/test_programs.py`
  ```python
  def test_programs_file_matches_review():
      d = load_programs()
      ids = [p["id"] for p in d["programs"]]
      assert ids == ["A01","A02","A03","A04","A05","A06","B01","B03","B04","B05","C01","C04","C05","C07"]
      a01 = next(p for p in d["programs"] if p["id"] == "A01")
      assert "1회" in a01["benefit"] and "200만원" in a01["benefit"] and a01["group"] == "national"
      c05 = next(p for p in d["programs"] if p["id"] == "C05")
      assert c05["region"] == "울산" and "지역 안내 표기와 다름" in c05["notice"]
      assert {p["id"] for p in d["programs"] if p["closed"]} == {"C01", "C07"}

  def test_centers_cover_all_regions():
      d = load_programs()
      assert sorted(c["region"] for c in d["centers"]) == sorted(REGIONS)
      assert sum(c["status"] == "open" for c in d["centers"]) == 12
      assert center_for("대구", d)["phone"] == "053-248-4113"
      assert center_for("전남", d)["phone"] is None and center_for("경기", d)["status"] == "preparing"
      assert center_for(None, d) is None
  ```
- [ ] **Step 3:** `$PY -m pytest tests/test_programs.py -q` → FAIL (모듈 없음).
- [ ] **Step 4:** `scripts/build_programs.py` 작성: 입력 `data/programs/review/지원사업_초안_2026-11-01_v3.json`의 `programs`(최종 행, 열 이름은 `columns`)와 `centers` → `data/programs/programs.json`.
  - group: id 첫 글자 A→national, B→linked, C→local. region: C01 서울, C04 충북, C05 울산, C07 광주, 나머지 None.
  - closed: `신청 기간`에 "마감" 포함. notice: `지원 내용`이나 `⚠` 칸에 "지역 안내 표기와 다름"이 있으면 그 문장, A01은 `"일부 지역 안내는 '연 200만원'이라고 쓰지만, 법령은 1회예요."`.
  - summary (고정 문구): A01 "자기계발·건강에 쓰는 1회 200만원 이용권" · A02 "1:1 상담과 필요한 지원 연결" · A03 "13세 미만 가족돌봄아동 집중 사례관리" · A04 "집으로 오는 돌봄·가사 서비스 바우처" · A05 "아픈 가족의 요양시설 이용 지원" · A06 "기초생활 수급 가구 자활 참여 조건 1년 유예" · B01 "대학 등록금 지원 (센터가 신청을 도와줘요)" · B03 "무료 법률 상담" · B04 "구직 준비 프로그램 + 참여수당" · B05 "미취업 청년 맞춤 프로그램" · C01 "서울시 자체 자기돌봄비" · C04 "충북 가족돌봄청년 사례관리·프로그램" · C05 "울산 가족돌봄청년 사례관리·자기돌봄비" · C07 "광주 청년 1:1 관리·식비 바우처".
  - 센터: 이름의 시·도를 REGIONS 약칭으로 ("광주 (전남광주통합특별시)"→광주, "전남 (…)"→전남), "(준비 중인 지역 공통)" 행은 버림. status: 상태가 "운영"으로 시작하면 open. phone/email: "-"·"확인 안 됨"이면 None. name: 상태 문자열의 "운영: " 뒤, 괄호 앞.
  - 실행: `$PY scripts/build_programs.py` → 파일 생성.
- [ ] **Step 5:** `src/ragbot/domain/programs.py`에 `PROGRAMS_FILE = DATA_DIR / "programs" / "programs.json"`, `REGIONS`, `load_programs`, `center_for` 구현 (시작 시 필수 키 검사, 없으면 `ValueError`).
- [ ] **Step 6:** `$PY -m pytest tests/test_programs.py -q` → PASS, `$PY -m ragbot check --fast` → PASS.
- [ ] **Step 7:** 커밋 `feat: 검수한 지원사업·센터 데이터와 읽기 모듈` (scripts, programs.json, review 폴더의 v3 xlsx/json, domain/programs.py, 테스트, .gitignore).

### Task 2: 판정 규칙

**Files:**
- Create: `src/ragbot/domain/eligibility.py`
- Test: `tests/test_eligibility.py`

**Interfaces:**
- Consumes: Task 1 `load_programs`, `center_for`, `REGIONS`
- Produces:
  - 프로필 (화면과 API가 같은 키 사용, 모두 생략 가능):
    `age:int|None, military_months:int|None, region:str|None, sigungu:str|None,
     relations:list["parent"|"grandparent"|"sibling"|"other"],
     conditions:list["ltc_grade"|"severe_disability"|"mental_illness"|"long_illness"|"other"|"unknown"],
     living:"together"|"apart_visiting"|"apart"|"unknown", adult_other:"none"|"yes"|"unknown",
     adult_other_exception:"ill_or_disabled"|"absent"|"none"|"unknown",
     activity:"middle_high"|"college"|"working"|"rest_6m_plus"|"rest_under_6m"|"other"|"unknown",
     burden:"high"|"some"|"none"|"unknown", basic_livelihood:"yes"|"no"|"unknown",
     income_band:"none"|"lt100"|"100_200"|"200_256"|"gt256"|"unknown"`
  - `match(profile: dict, data: dict) -> dict` → `{"center": Center|None, "cards": [{"id": str, "status": "ok"|"check"|"no", "conditions": [{"label": str, "law": str, "result": "ok"|"unknown"|"no"}]}]}`
  - `card_status(conditions: list[dict]) -> str` — ❌ 하나라도 → "no", 전부 ok(빈 목록 포함) → "ok", 그 밖 → "check"
  - `profile_summary(profile: dict) -> str` — 채팅 맥락용 한 문단 (Task 4)

**규칙 표** (조건 문구 = label, 근거 = law. 표에 없는 사업은 표시 조건이 안 맞으면 카드에서 뺀다):

| 조건 키 | label | law | ok / unknown / no |
|---|---|---|---|
| age(lo,hi,병역) | `나이 {lo}~{hi}세` (+ `(군 복무 기간만큼 늘어나요)`) | 사업별 | 범위 안 / age None / 밖. 병역이면 hi += ceil(military_months/12) |
| family | 돌봄이 필요한 가족 (장기요양·심한 장애·정신질환·6개월 이상 질병 등) | 돌봄대상가족 고시 제2조 | 앞 4개 중 하나 / "other"·"unknown"·빈 목록 / — |
| adult | 함께 사는 35세 이상 다른 가족이 없거나 예외에 해당 | 법 제13조①1, 시행규칙 제6조① | "none" 또는 yes+예외(ill_or_disabled, absent) / unknown / yes+"none" |
| address | 돌보는 가족과 주소가 같음 (학업·취업으로 따로 살며 돌보는 경우 예외) | 법 제13조①1, 시행규칙 제6조② | together·apart_visiting / unknown / apart |
| burden | 돌봄 때문에 학업·취업이 많이 힘듦 | 법 제13조①1 | high / some·unknown / none |
| income | 본인 소득·재산 기준 중위소득 100% 이하 (대략 월 256만원) | 시행령 제11조①2 | none·lt100·100_200·200_256 / unknown / gt256 |
| together | 돌보는 가족과 함께 삶 | 2026 일상돌봄 서비스 사업안내 15쪽 | together / unknown / apart·apart_visiting |
| selected | 청년미래센터의 지원대상자 선정이 필요해요 | 법 제13조① | 항상 unknown |

| 사업 | 보이는 조건 | 판정 조건 |
|---|---|---|
| A01 자기돌봄비 | age None 또는 ≥13 | age(13,34,병역; law 시행령 제11조①1), family, adult, address, burden, income |
| A02 사례관리 | age None 또는 ≥13 | age(13,34,병역; law 법 제2조1호), family, adult, address, burden |
| A03 드림스타트 | age < 13 | age(0,12; law 보건복지부 보도자료 2026.3.25), family |
| A04 일상돌봄 | age None 또는 9~39 | age(9,39; law 2026 일상돌봄 서비스 사업안내 15쪽), family, together |
| A05 장기요양 시설급여 | "ltc_grade" in conditions | `가족이 장기요양 등급을 받았어요 (인지지원등급 제외)` 법 제19조②1·시행령 제12조 = ok, selected |
| A06 자활 유예 | basic_livelihood == "yes" | `기초생활 수급 가구` 법 제19조②3·시행규칙 제9조 = ok, selected |
| B01 국가장학금 | activity == "college" | `대학생` 한국장학재단 = ok, `학자금 지원구간 9구간 이하` = unknown |
| B03 마을변호사 | age None 또는 ≥13 | (없음 → ok) |
| B04 청년도전 | age None 또는 18~34 | age(18,34; law 고용24 2026), `6개월 넘게 취업·교육 이력 없음` rest_6m_plus=ok, working·college·middle_high=no, 그 밖 unknown |
| B05 청년성장 | age None 또는 15~34 | age(15,34; law 고용24), `미취업` rest_*=ok, working=no, 그 밖 unknown |
| C01·C04·C05·C07 | profile.region == program.region | `{region}에 살아요` = ok, age(C01 9~39, C04 13~39, C05 13~39, C07 19~34; law 해당 사업 공고) |

카드 순서: group(national → linked → local), 같은 group 안에서 status(ok → check → no), 그다음 id.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_eligibility.py`, 기준 프로필 `BASE = {"age":20,"region":"충북","relations":["parent"],"conditions":["long_illness"],"living":"together","adult_other":"none","activity":"college","burden":"high","basic_livelihood":"no","income_band":"none"}`
  ```python
  def cards(p): return {c["id"]: c for c in match(p, load_programs())["cards"]}
  def test_base_profile():
      c = cards(BASE)
      assert c["A01"]["status"] == "ok" and c["A02"]["status"] == "ok" and c["A04"]["status"] == "ok"
      assert "A03" not in c and "C04" in c and "C01" not in c and "B01" in c
      assert match(BASE, load_programs())["center"]["phone"] == "1551-1259"
  def test_all_unknown():
      c = cards({})
      assert c["A01"]["status"] == "check" and c["A02"]["status"] == "check" and "A03" not in c
  def test_age_edges():
      assert cards({**BASE, "age": 12})["A03"]["status"] == "ok" and "A01" not in cards({**BASE, "age": 12})
      assert cards({**BASE, "age": 35, "military_months": 24})["A01"]["status"] == "ok"
      assert cards({**BASE, "age": 40})["A01"]["status"] == "no"
  def test_adult_exception():   # 38세 형이 있지만 장애
      assert cards({**BASE, "adult_other": "yes", "adult_other_exception": "ill_or_disabled"})["A01"]["status"] == "ok"
      assert cards({**BASE, "adult_other": "yes", "adult_other_exception": "none"})["A01"]["status"] == "no"
  def test_address_and_together():
      c = cards({**BASE, "living": "apart_visiting"})
      assert c["A01"]["status"] == "ok" and c["A04"]["status"] == "no"
  def test_income_band():
      assert cards({**BASE, "income_band": "gt256"})["A01"]["status"] == "no"
      assert cards({**BASE, "income_band": "gt256"})["A02"]["status"] == "ok"
  def test_conditional_cards():
      assert "A05" in cards({**BASE, "conditions": ["ltc_grade"]}) and cards({**BASE, "conditions": ["ltc_grade"]})["A05"]["status"] == "check"
      assert "A06" in cards({**BASE, "basic_livelihood": "yes"})
  def test_center_fallback():
      d = load_programs()
      assert match({**BASE, "region": "전남"}, d)["center"]["phone"] is None
      assert match({**BASE, "region": "경기"}, d)["center"]["status"] == "preparing"
  def test_every_condition_has_law():
      for c in match(BASE, load_programs())["cards"]:
          assert all(x["law"] and x["result"] in {"ok","unknown","no"} for x in c["conditions"])
  def test_profile_summary():
      s = profile_summary(BASE)
      assert "20세" in s and "충북" in s and "최종" in s
  ```
- [ ] **Step 2:** `$PY -m pytest tests/test_eligibility.py -q` → FAIL.
- [ ] **Step 3:** `eligibility.py` 구현: 조건 함수들, `RULES: dict[str, Callable[[dict], list[dict] | None]]` (None = 숨김), `card_status`, `match`, `profile_summary`. `profile_summary`는 답한 항목만 한국어로 나열하고 끝에 `"이 사용자의 상황에 맞춰 답하되, 받을 수 있는지 최종 판정은 하지 말고 청년미래센터·시군구청이 결정한다고 안내하세요."`를 붙인다.
- [ ] **Step 4:** `$PY -m pytest tests/test_eligibility.py tests/test_architecture.py -q` → PASS.
- [ ] **Step 5:** 커밋 `feat: 법령 기반 판정 규칙`.

### Task 3: 코어 최소 수정 (진행 콜백, 사용자 맥락, 저장 안 함)

**Files:**
- Modify: `src/ragbot/llm.py:5-8,39-55` (`CACHE_MODE=nostore`: `fn()`만 호출, 읽기·쓰기 없음. 모듈 docstring에 한 줄)
- Modify: `src/ragbot/agent.py` (`system_prompt`, `answer`)
- Create: `docs/decisions/0006-app-core-hooks.md`
- Test: `tests/test_agent_hooks.py`

**Interfaces:**
- Produces:
  - `Chatbot.answer(question, history=None, context: str | None = None, on_progress: Callable[[str, dict], None] | None = None) -> Answer`
  - 진행 이벤트: `("route", {"primary": str})` 계획 직후, `("tool", {"name": str})` 각 도구 호출 직전, `("write", {})` 최종 답 직전
  - `Chatbot.system_prompt(plan=None, question="", context=None)` — context가 있으면 맨 끝에 `"\n" + context`

- [ ] **Step 1: 실패하는 테스트** — `tests/test_agent_hooks.py` (API 없음: `monkeypatch`로 `llm.chat`, `router.route`를 가짜로; `Chatbot`은 `object.__new__`로 만들고 `cfg=load_config()`, `ctx`, `write_traces=False`, `index=None`을 직접 넣는다)
  ```python
  def test_progress_and_context(monkeypatch):
      seen, prompts = [], []
      replies = iter([{"content": "", "tool_calls": [{"id": "1", "name": "get_today", "arguments": "{}"}]},
                      {"content": "답", "tool_calls": []}])
      monkeypatch.setattr(llm, "chat", lambda m, tools=None: prompts.append(m[0]["content"]) or next(replies))
      monkeypatch.setattr(router, "route", lambda *a, **k: {"primary": "docs", "fallback": [], "reason": ""})
      ans = make_bot().answer("질문", context="USER_CONTEXT", on_progress=lambda s, d: seen.append(s))
      assert ans.answer == "답" and seen == ["route", "tool", "write"] and prompts[0].endswith("USER_CONTEXT")

  def test_nostore_cache(monkeypatch, tmp_path):
      monkeypatch.setattr(llm, "CACHE_MODE", "nostore"); monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
      assert llm.cached("chat", {"x": 1}, lambda: {"ok": 1}) == {"ok": 1}
      assert not list(tmp_path.iterdir())
  ```
- [ ] **Step 2:** `$PY -m pytest tests/test_agent_hooks.py -q` → FAIL.
- [ ] **Step 3:** 구현. `llm.cached`는 `CACHE_DIR.mkdir`보다 먼저 nostore 분기. `agent.answer`는 콜백이 None이면 아무것도 하지 않음 (기존 호출 그대로).
- [ ] **Step 4:** `$PY -m ragbot check --fast` → PASS (기존 테스트 포함).
- [ ] **Step 5:** 결정 기록 0006 (배경: 앱의 진행 표시·맥락·개인정보, 결정: 선택 인자 2개 + nostore, 결과: check --fast 수치, 대안: 별도 에이전트 복사 — 중복이라 기각). 커밋 `feat: 에이전트 진행 콜백·사용자 맥락, 캐시 저장 안 함 모드`.

### Task 4: API 서버와 챗봇 설정

**Files:**
- Create: `app/api.py`
- Modify: `config.yaml` (chatbot.name `돌잡이 (돌봄길잡이)`, translations.en.name `Doljabi (Care Guide)`, about의 문서 목록을 7개로, system_prompt Rules에 `- If a "User context" paragraph is given, tailor the answer to it, but never give a final yes/no on eligibility.`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: Task 1 `load_programs`, Task 2 `match`, `profile_summary`, Task 3 `Chatbot.answer(..., context, on_progress)`
- Produces (HTTP, JSON UTF-8):
  - `GET /api/programs` → programs.json 그대로
  - `POST /api/match` body `{"profile": {...}}` → `match()` 결과
  - `POST /api/chat` body `{"question": str, "history": [{"role","content"}], "profile": {...}|null, "lang": "ko"|"en"}` → `text/event-stream`:
    `event: progress` `{"step": "route"|"tool"|"write", "name"?: str}` · `event: answer` `{"answer": str, "chips": [{"label": str, "text": str|null}], "web": [url]}` · `event: error` `{"message": "unavailable"}`
  - `GET /api/health` → `{"ok": true, "index": bool}`
  - `GET /` 와 정적 파일 → `web/` (`StaticFiles(directory="web", html=True)`, `/api` 뒤에 마운트)
  - `create_app(bot_factory=None) -> Starlette` (테스트에서 가짜 봇 주입). 기본 봇: `Chatbot(write_traces=False)`를 처음 채팅 때 한 번 만듦.
  - 출처 칩: 답의 `[Source: …]` 괄호를 본문에서 지우고, 쉼표 뒤 부분(예 "위기아동청년법 시행령 제11조")을 label로. text는 `ans.tool_calls` 중 `search_documents` 결과에서 `section`에 label의 조문 번호(정규식 `제\d+조(의\d+)?`)가 들어간 첫 passage의 `text` 앞 300자, 없으면 null. 웹 출처(`[Source: web URL]`)는 `web` 목록으로.

- [ ] **Step 1: 실패하는 테스트** — `tests/test_api.py` (TestClient, 가짜 봇)
  ```python
  def test_match_and_programs():
      c = TestClient(create_app(bot_factory=FakeBot))
      assert len(c.get("/api/programs").json()["programs"]) == 14
      r = c.post("/api/match", json={"profile": {"age": 20, "region": "충북"}}).json()
      assert r["center"]["phone"] == "1551-1259" and r["cards"]
  def test_chat_stream():   # FakeBot.answer: on_progress("route",…), ("tool",{"name":"search_documents"}), ("write",{}) 후
      # Answer(answer="나이는 34세까지예요. [Source: gov ko p.2, 위기아동청년법 시행령 제11조]",
      #        tool_calls=[{"name":"search_documents","result":[{"section":"위기아동청년법 시행령 > 제11조(자기돌봄비)","text":"① …"}]}])
      body = TestClient(create_app(bot_factory=FakeBot)).post("/api/chat", json={"question": "q", "profile": {"age": 20}}).text
      assert body.index("event: progress") < body.index("event: answer")
      ans = json.loads(body.split("event: answer\ndata: ")[1].split("\n")[0])
      assert "[Source" not in ans["answer"] and ans["chips"][0]["label"].endswith("제11조") and ans["chips"][0]["text"].startswith("①")
      assert FakeBot.last_context and "20세" in FakeBot.last_context
  def test_chat_error_event():   # 봇이 예외를 던지면
      body = TestClient(create_app(bot_factory=BrokenBot)).post("/api/chat", json={"question": "q"}).text
      assert "event: error" in body
  def test_static_home():
      assert "돌잡이" in TestClient(create_app(bot_factory=FakeBot)).get("/").text   # Task 5 전에는 web/index.html 임시 파일
  ```
- [ ] **Step 2:** `$PY -m pytest tests/test_api.py -q` → FAIL.
- [ ] **Step 3:** `app/api.py` 구현. 채팅은 스레드에서 `bot.answer`를 돌리고 `queue.Queue`로 이벤트를 받아 동기 제너레이터로 `StreamingResponse` (Starlette가 스레드풀에서 순회). 타임아웃 90초면 error. `web/index.html`은 `<title>돌잡이</title>` 한 줄짜리 임시 파일로 시작 (Task 5에서 교체).
- [ ] **Step 4:** `$PY -m pytest tests/test_api.py -q && $PY -m ragbot check --fast` → PASS.
- [ ] **Step 5: 인덱스 빌드와 실제 연결 확인** — `$PY -m ragbot index` (임베딩 API 호출) → `index/` 생성. `CACHE_MODE=nostore $PY -m uvicorn app.api:app --port 8000` 실행 후 `curl -N -X POST localhost:8000/api/chat -H 'content-type: application/json' -d '{"question":"자기돌봄비는 얼마예요?"}'` → progress 이벤트 뒤 answer에 "200만원"과 칩. `runs/`에 새 파일이 생기지 않았는지 확인.
- [ ] **Step 6:** 커밋 `feat: Starlette API (programs, match, chat SSE)와 앱 이름 돌잡이`.

### Task 5: 화면 — 질문, 결과, 상세, 센터 찾기

**Files:**
- Create: `web/index.html`, `web/style.css`, `web/app.js`, `web/i18n.js`, `web/manifest.webmanifest`
- Modify: `tests/test_api.py` (`test_static_home`이 실제 index.html로 통과)

**Interfaces:**
- Consumes: Task 4 API, Task 2 프로필 키 (그대로 사용)
- Produces: `window.Dol = { state, go(screen, params), api }`, 상세 화면의 "이 지원에 대해 물어보기"는 `Dol.go("chat", {programId})` (Task 6이 사용). localStorage 키 `doljabi.profile.v1`, `doljabi.lang`.

화면과 문구는 spec 4절과 `.superpowers/brainstorm/*/content/{questions,results,style}.html` 시안을 따른다.
- 테마 (style.css `:root`): 배경 `#fff8f2`, 헤더 `#ffe9db`, 주색 `#f07c5a`, 진한 주색 `#d0573a`, 카드 테두리 `#f6dccd`, 본문 `#3a2a22`, ok `#e4f4e5/#2d7a37`, check `#fff1c9/#8a6400`, no `#f9e1dc/#a3412b`. 글꼴 Pretendard (`https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css`). 최대 폭 480px 가운데, 하단 탭 고정.
- 질문 5단계: 각 단계 진행 막대, "다음/이전", 모든 질문에 "잘 모르겠어요". 1단계 맨 위 `🔒 입력한 정보는 이 휴대폰에만 남고 서버에 저장되지 않아요`. 시·도는 `REGIONS` 17개 버튼/선택, 시·군·구는 선택 입력칸. 35~40세면 군 복무 개월 입력.
- 결과: 헤더 요약 + "수정" + "내 정보 지우기"(확인 후 localStorage 삭제, 1단계로), 내 담당 센터(전화 `tel:` 링크, 청년ON `https://www.mohw2030.co.kr`; phone이 null이거나 준비 중이면 "청년ON 온라인 · 주민센터 · 📞 129"), 그룹 제목 "가족돌봄 국가 제도 / 센터가 연결해 주는 지원 / {지역} 지역 사업", 카드(배지 법령 확인·센터 연계·지역명, 상태 한 줄, closed면 "2026년 마감" 배지), "+ 함께 받을 수 있는 일반 지원 더 보기 (준비 중)" 비활성 카드, 복지로·온통청년·129 안내 카드, 하단 고정 문구.
- 상세: summary, 조건 목록(✅❔❌ + law), notice(⚠), 대상·지원 내용·신청 방법·기간·문의·출처·확인일, 센터 전화 버튼, "💬 이 지원에 대해 물어보기".
- 센터 찾기: 내 지역 강조, 운영 12곳(전화 링크), 준비 중 5곳 묶음 + 안내, 129.
- 언어: i18n.js에 UI 문구 ko/en, 지원사업 내용은 한국어 그대로.

- [ ] **Step 1:** 파일 작성. 서버 실행 `$PY -m uvicorn app.api:app --port 8000`.
- [ ] **Step 2: 브라우저 확인 (Chrome 개발자 도구 휴대폰 모드 390px)** — 기준 프로필(충북 20세 대학생, 6개월 넘게 아픈 엄마, 함께 삶, 소득 없음)로 끝까지 → 자기돌봄비·사례관리·일상돌봄 "받을 수 있어 보여요", 국가장학금, 충북 사업, 센터 1551-1259. 모든 질문 "잘 모르겠어요" → 자기돌봄비 "확인이 필요해요". 지역 전남 → 센터 블록이 "청년ON · 129"로 대체되고 "undefined" 없음.
- [ ] **Step 3: 깨진 저장값 확인** — 개발자 도구 콘솔에서 `localStorage.setItem("doljabi.profile.v1","{깨짐")` 후 새로고침 → 오류 없이 1단계부터.
- [ ] **Step 4:** `$PY -m pytest tests/test_api.py -q` → PASS. 커밋 `feat: 질문·결과·상세·센터 화면 (코랄 테마)`.

### Task 6: 화면 — 물어보기 (채팅)

**Files:**
- Modify: `web/app.js`, `web/style.css`, `web/i18n.js`
- Create: `web/chat.js`

**Interfaces:**
- Consumes: `POST /api/chat` 이벤트 (Task 4), `Dol.go("chat", {programId})` (Task 5)

- 진행 표시: route → "🧭 어디서 찾을지 정하는 중", tool search_documents → "📘 법령에서 찾는 중", web_search → "🌐 웹에서 찾는 중", write → "✍️ 답을 쓰는 중". 단계마다 ✓.
- 답: 출처 칩(📘 label), 누르면 text 펼침(null이면 펼침 없음). `web` URL은 "🌐 웹 · 확인 필요" 칩(새 탭 링크). 답 아래 작은 글씨 "답이 틀릴 수 있어요. 최종 결정은 센터·시군구청이 해요."
- 카드에서 오면 "💬 {name} 카드에서 왔어요" + 추천 질문 3개 ("신청은 어디서 해요?", "서류는 뭐가 필요해요?", "{name} 조건을 자세히 알려 주세요"), 첫 질문에 사업명 포함.
- 프로필이 있으면 항상 함께 보냄 (스위치 없음, 팀 결정). history는 최근 6개 메시지.
- error 이벤트·네트워크 실패: "지금은 답을 만들 수 없어요" + 센터 전화·129 버튼 + "다시 보내기". 보내는 동안 입력 잠금.
- 한/영 전환은 UI와 `lang` 전송.

- [ ] **Step 1:** 구현.
- [ ] **Step 2: 브라우저 확인** — 질문 "군대 2년 다녀와서 35살인데 자기돌봄비 받을 수 있어요?" → 진행 단계가 순서대로 ✓, 답과 📘 칩, 칩을 누르면 조문 원문. 서버를 끈 채 질문 → 오류 안내와 다시 보내기. 자기돌봄비 상세 → 물어보기 → 맥락 표시와 추천 질문.
- [ ] **Step 3:** 커밋 `feat: 물어보기 화면 (진행 단계, 출처 칩, 내 정보 맥락)`.

### Task 7: Hugging Face 배포

**Files:**
- Create: `Dockerfile`, `scripts/deploy_hf.sh`, `deploy/README.space.md`

**Interfaces:**
- Consumes: 전체 앱. `.env`의 `HF_TOKEN`, `HF_SPACE` (예 `사용자이름/doljabi`) — 사람이 넣음.

- `Dockerfile`: `python:3.11-slim`, `pip install -r requirements.lock && pip install -e . --no-deps`, `COPY src app web config.yaml data/parsed data/programs/programs.json index`, `ENV CACHE_MODE=nostore PORT=7860`, `CMD uvicorn app.api:app --host 0.0.0.0 --port 7860`. `.env`, `data/programs/raw`, `data/docs`, `node_modules`, `runs`, `.cache`은 넣지 않음.
- `deploy/README.space.md`: HF 머리말 `title: 돌잡이`, `emoji: 🌱`, `sdk: docker`, `app_port: 7860`, `colorFrom: red`, `colorTo: yellow` + 한 줄 설명.
- `scripts/deploy_hf.sh`: `build/space/`에 Dockerfile·README(머리말)·필요한 파일을 복사 → 그 폴더를 git 저장소로 만들어 `https://user:${HF_TOKEN}@huggingface.co/spaces/${HF_SPACE}`에 force push. 토큰은 `.env`에서 읽고 화면에 출력하지 않음 (`set +x`, 원격 URL을 로그에 찍지 않음).

- [ ] **Step 1 (사람):** huggingface.co에서 Space 만들기 (Docker, Blank, Public). Settings → Variables and secrets에 Secrets로 `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `EMBED_BASE_URL`, `EMBED_MODEL`, `RERANK_BASE_URL`, `RERANK_MODEL`, `NO_THINK`. `.env`에 `HF_TOKEN=`(write 토큰), `HF_SPACE=` 추가.
- [ ] **Step 2:** 로컬에서 이미지 확인이 가능하면 `docker build -t doljabi . && docker run -p 7860:7860 --env-file .env doljabi` (Docker가 없으면 건너뜀).
- [ ] **Step 3:** `bash scripts/deploy_hf.sh` → Space 빌드 로그가 Running.
- [ ] **Step 4: 배포 확인** — `https://<space>.hf.space/api/health` → `{"ok": true, "index": true}`. 휴대폰으로 URL을 열어 Task 5 Step 2의 흐름 한 번, 채팅 질문 하나 (학교 LLM 서버가 해외에서 응답하는지). 실패하면 spec 7절 예비 계획(학교 서버 등)을 사람에게 보고하고 멈춤.
- [ ] **Step 5 (사람):** cron-job.org에서 `https://<space>.hf.space/api/health`를 하루 1회 호출하도록 등록.
- [ ] **Step 6:** 커밋 `feat: Hugging Face Spaces 배포 설정`.

### Task 8: 채팅 점검 10개와 개선

**Files:**
- Modify: `eval/golden_qa.jsonl` (10줄)
- Create: `docs/decisions/0007-chat-check-10.md`
- Modify: 원인에 따라 `config.yaml` system_prompt / `retrieval` (질문 전용 규칙 금지, AGENTS.md 경계)

- 질문: GOAL.md 후보 1~12 중 10개 (1, 2, 3, 4, 5, 6, 7, 8, 10, 12). 각 줄: `id`(K01~K10), `lang` ko, `route` docs(12번은 web), `question`, `reference_answer`, `evidence`(문서·조문), `key_points`(짧은 사실), 필요하면 `must_not` (2번 `"연 200만원"`, `"매년"`).
- [ ] **Step 1:** 정답 초안 작성 → **사람에게 보여 주고 확인받는다** (확인 전 실행 금지).
- [ ] **Step 2:** `$PY -m ragbot eval` → `runs/eval_*.json`. 정답 수 기록.
- [ ] **Step 3:** 틀린 질문마다 trace(`runs/<날짜>/<trace_id>.json`)로 층 판정 (검색에 맞는 조문이 있었나 → 없으면 검색, 있으면 답 생성). 일반 규칙으로만 수정 (예: 시스템 프롬프트 "단서·예외 조항(다만, 예외, 가산)을 반드시 적용"), 한 번에 하나.
- [ ] **Step 4:** `$PY -m ragbot eval` 다시 → 이전보다 낮아진 수정은 되돌림. `$PY -m ragbot check --fast` → PASS.
- [ ] **Step 5:** 0007 결정 기록 (전후 수치, 바꾼 것, 템플릿 20~30개·thresholds 대신 10개로 한 이유, 정답 확인자). 커밋 `eval: 채팅 점검 10개와 개선`. 배포에 반영하려면 `bash scripts/deploy_hf.sh`.

### Task 9: 문서 정리

**Files:**
- Modify: `docs/DATA.md` (센터 현황 12/5, 검수 데이터 위치, 자기돌봄비 소득인정액 제외, 일상돌봄 가족 범위), `AGENTS.md` (제목 "돌잡이", 목표 한 문단, 완료 기준을 `check --fast` + 해당 테스트로, 골든 QA 20~30개 요구 삭제), `README.md` (맨 위에 앱 실행·배포 명령 4줄), `tasks/`의 03·06·08 상태 문구 ("팀 결정으로 대체: spec 링크")

- [ ] **Step 1:** 수정.
- [ ] **Step 2:** `$PY -m ragbot check --fast` → PASS. `git status`에 `.superpowers/`, `data/programs/raw/`, `.env`가 없음을 확인.
- [ ] **Step 3:** 커밋 `docs: 돌잡이 앱 기준으로 문서 정리`.

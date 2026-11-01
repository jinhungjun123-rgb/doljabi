# 일반 지원 더 보기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 결과 화면의 "일반 지원 더 보기"를 온통청년 청년정책 + 복지로 국가 서비스의 자동 판정 목록, 상세, 채팅 연결로 채운다.

**Architecture:** `scripts/build_more.py` 가 raw 공공데이터를 `data/programs/more.json` 으로 정리한다. `src/ragbot/domain/more.py` 가 프로필로
거르고 조건별 ok/unknown/no 를 판정한다 (LLM 없음). `app/api.py` 의 `POST /api/more` 가 분야별 목록을 주고, `/api/chat` 은 선택 `about` 을 맥락에 붙인다.
화면은 `web/app.js` 에 목록·상세 화면 두 개.

**Tech Stack:** Python 3.11, Starlette, pytest, vanilla JS. 새 의존성 없음.

**Spec:** `docs/superpowers/specs/2026-11-01-doljabi-more-support-design.md`

## Global Constraints
- 실행 중 공공 API 호출 금지. 데이터 기준일 `2026-11-01` 을 화면에 표시.
- 판정 결과는 `ok` / `unknown` / `no`, 카드 상태는 기존 `card_status` 그대로. 답하지 않은 항목은 항상 `unknown`.
- 배지 문구 "자동 확인", 안내 문구 "공공데이터를 자동으로 정리하고 판정한 목록이에요 (2026-11-01 기준). 받을 수 있는지는 원문과 담당 기관에서 확인하세요."
- 모든 항목 아래 "그 밖의 세부 요건은 원문에서 확인" (조건 행이 아님).
- 도메인 단어는 `src/ragbot/domain/` 과 `config.yaml` 에만 (`tests/test_core_is_domain_free.py` 는 `app/*.py` 도 검사). 층 규칙 `tests/test_architecture.py`.
- `data/programs/more.json` 은 생성물: 손으로 고치지 않음. 서버는 사용자 정보를 디스크에 쓰지 않음.
- 매 변경 후 `"$USERPROFILE/miniforge3/envs/my_ragbot/python.exe" -m pytest -q` (아래 `PY -m pytest`).

## 코드표 (원본 표본으로 확인함, 2026-11-01)
- 시·도 → 온통청년 지역 코드 앞 두 자리: 서울 11, 부산 26, 대구 27, 인천 28, 대전 30, 울산 31, 세종 36, 경기 41, 강원 51, 충북 43, 충남 44,
  전북 52, 경북 47, 경남 48, 제주 50, **광주·전남 12** (전남광주통합특별시).
- 취업 상태 `jobCd`: 0013001 재직자, 0013003 미취업자, 0013010 제한 없음 (그 밖의 코드는 뜻을 쓰지 않음).
  앱 `activity` → 코드: working → {0013001}, rest_6m_plus·rest_under_6m → {0013003}; college·middle_high·other → 모름.
- 학력 `schoolCd`: 0049002 고교 재학, 0049005 대학 재학, 0049010 제한 없음. 앱 `activity`: middle_high → {0049002}, college → {0049005}; 나머지 모름.
- 소득 `earnCndSeCd`: 0043001 무관, 0043002 연소득(`earnMinAmt`~`earnMaxAmt` 만원, max 0 이면 상한 없음), 0043003 기타(제외).
  앱 `income_band`(월, 만원) 구간: none [0,0], lt100 [0,99], 100_200 [100,199], 200_256 [200,256], gt256 [257,∞) → ×12 로 비교.
- 신청 기간 `aplyPrdSeCd`: 0057001 기간 지정(`aplyYmd` "YYYYMMDD ~ YYYYMMDD", 여러 개면 줄바꿈), 0057002 상시, 0057003 미정.

## Review Focus
1. 지역을 답하지 않은 사용자 → 청년정책은 전국 대상만, 국가 서비스는 모두; 목록이 비지 않고 지역 조건 행은 없음 (Task 2 `test_no_region_keeps_nationwide_only`).
2. 광주 또는 전남 사용자 → 코드 12 정책이 내 지역으로 잡힘 (Task 2 `test_gwangju_jeonnam_use_code_12`).
3. `aplyYmd` 가 비었거나 형식이 다르거나 여러 줄 → 예외 없이 `unknown` (Task 2 `test_odd_application_dates`).
4. `about` 에 긴 글이나 `javascript:` 링크 → 잘리고 링크는 빠짐 (Task 3 `test_chat_about_is_cleaned`).
5. 공공데이터 이름·설명에 `<`, `&` 가 들어 있음 → 화면에 글자 그대로 (Task 4 화면 점검에서 `esc` 사용 확인).

---

### Task 1: 정리 파일 만들기

**Files:**
- Create: `scripts/build_more.py`, `data/programs/more.json` (생성)
- Test: `tests/test_more_data.py`

**Interfaces:**
- Produces: `data/programs/more.json` = `{"as_of": "2026-11-01", "items": [item, ...]}`. item:
  `{"id": "Y:<plcyNo>"|"N:<servId>", "source": "youth"|"national", "name", "summary"(≤90자, 줄바꿈 없음), "org", "link"(https),
  "group": "life"|"health"|"housing"|"education"|"jobs"|"participation",
  "zips": [str] (youth만, 5자리), "age": [min, max] | null, "income": [min, max] | null (만원/년, null=무관),
  "period": {"kind": "always"|"range"|"tbd", "ranges": [["YYYYMMDD","YYYYMMDD"], ...]} (youth만), "jobs": [codes], "schools": [codes],
  "life": ["청소년"|"청년", ...] (national만), "targets": [str] (national만), "online": bool (national만)}`.

- [ ] **Step 1: 실패하는 테스트** `tests/test_more_data.py`
```python
def test_more_file_shape():
    d = json.loads(MORE.read_text(encoding="utf-8"))
    assert d["as_of"] == "2026-11-01"
    ids = {i["id"] for i in d["items"]}
    assert 1500 < sum(i["source"] == "youth" for i in d["items"]) < 2500
    assert 100 < sum(i["source"] == "national" for i in d["items"]) < 200
    assert all(i["link"].startswith("https://") and i["group"] in GROUPS for i in d["items"])
    assert REVIEWED_IDS.isdisjoint(ids)          # 검수 14개(program_candidates.json 의 bokjiro/youth)와 겹치지 않음
    assert not any(i["source"] == "national" and set(i["targets"]) <= {"보훈대상자", "다문화·탈북민"} and i["targets"] for i in d["items"])
```
- [ ] **Step 2:** `PY -m pytest tests/test_more_data.py` → FAIL (파일 없음)
- [ ] **Step 3:** `scripts/build_more.py [root]` 구현. 거르기: youth 는 `earnCndSeCd` 0043003 제외, 기간 지정이고 모든 기간이 2026-11-01 전에 끝난 것 제외;
  national 은 `lifeArray` 에 청소년/청년, 관심 주제가 {생활지원, 서민금융, 신체건강, 정신건강, 교육, 일자리, 주거, 보호·돌봄, 안전·위기, 법률, 문화·여가} 중 하나 이상,
  대상이 보훈·다문화뿐인 것 제외. 검수 ID 제외. 분야: youth 대분류 일자리*→jobs, 주거→housing, 교육*→education, 참여*→participation, 금융·복지·문화/복지문화는 중분류에 "건강" 있으면 health 아니면 life;
  national 주제 우선순위 정신·신체건강→health, 주거→housing, 일자리→jobs, 교육→education, 나머지→life. youth 링크: 온통청년 정책 상세 URL
  (`https://www.youthcenter.go.kr/youthPolicy/ythPlcyTotalSearch/ythPlcyDetail/<plcyNo>` 가 200 인지 curl 로 한 번 확인; 아니면 `refUrlAddr1` → `aplyUrlAddr` → 온통청년 첫 화면).
- [ ] **Step 4:** `PY scripts/build_more.py .` 후 테스트 PASS, 전체 `PY -m pytest -q` PASS
- [ ] **Step 5:** 커밋 `feat: 일반 지원 정리 파일 (온통청년 + 복지로 국가 서비스)`

### Task 2: 판정과 거르기

**Files:**
- Create: `src/ragbot/domain/more.py`
- Test: `tests/test_more.py`

**Interfaces:**
- Consumes: `more.json` (Task 1), `clean_profile`, `card_status` (`domain/eligibility.py`)
- Produces:
  - `load_more(path=MORE_FILE) -> dict`
  - `judge(item: dict, profile: dict, today: str) -> dict | None` — None 이면 목록에서 뺌 (다른 시·도, 신청 끝남). 아니면 `{**표시용 필드, "status", "conditions": [{"label", "result"}]}`
  - `more_for(profile: dict, data: dict, today: str) -> {"as_of", "groups": [{"key", "label", "items": [...], "no_items": [...]}]}` — 분야 순서 life, health, housing, education, jobs, participation; 빈 분야는 뺌
  - `about_summary(about: dict) -> str | None`(Task 3에서 사용)
  - `GROUP_LABELS = {"life": "생활·금융", "health": "건강·마음", "housing": "주거", "education": "교육", "jobs": "일자리", "participation": "참여·문화"}`

- [ ] **Step 1: 실패하는 테스트** (작은 가짜 item 으로; 실제 파일은 마지막 하나만)
```python
TODAY = "20261101"
def test_age_income_job_conditions(): ...      # 20세 범위 [19,34] ok, 40세 no; 월 lt100 ×12 vs [0,5000] ok, gt256 vs [0,2400] no, 100_200 vs [0,2000] unknown;
                                               # working vs jobs [0013003] no, rest_6m_plus ok, college unknown; jobs [0013010] → 행 없음
def test_region_rows():                        # 충북 + zips 전체(시·도 전체) ok; 일부 시·군·구이고 sigungu "청주" 가 org 에 있으면 ok, 없으면 unknown; 서울 사용자 → judge None
def test_no_region_keeps_nationwide_only():    # region 없음 → 전국(15개 이상 시·도) 정책만 남고 지역 행 없음
def test_gwangju_jeonnam_use_code_12():        # region "광주" 와 "전남" 모두 zips ["12110"] 정책 통과
def test_period():                             # always ok; range 진행 중 ok, 시작 전 unknown, 모두 끝남 → None; tbd unknown
def test_odd_application_dates():              # ranges [] / [["2026", "x"]] → unknown, 예외 없음
def test_national_life_and_targets():          # 청년 서비스: 20세 ok, 15세 no(청소년 아님); 저소득 + basic_livelihood yes ok, no unknown; 장애인 → unknown
def test_empty_profile():                      # {} → 예외 없음, 모든 상태가 check (no 없음)
def test_more_for_real_file():                 # 충북 20세 대학생: groups 키 순서가 GROUP_LABELS 순서의 부분열, 각 그룹 items 는 ok 가 check 보다 앞, no 는 no_items 에만
```
- [ ] **Step 2:** `PY -m pytest tests/test_more.py` → FAIL (모듈 없음)
- [ ] **Step 3:** `more.py` 구현 (판정은 위 코드표와 설계 문서 표). 정렬: 상태(ok, unknown) → 이름·설명에 돌봄|가족|간병|장애|자립 → 시·도 단위 이하 정책 → 이름.
  "전국" = 서로 다른 시·도 앞자리 15개 이상. "시·도 전체" = 데이터 전체에서 본 그 시·도 코드 집합을 모두 포함 (load 시 계산).
- [ ] **Step 4:** PASS, 전체 테스트 PASS
- [ ] **Step 5:** 커밋 `feat: 일반 지원 자동 판정 (domain/more.py)`

### Task 3: API

**Files:**
- Modify: `app/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `load_more`, `more_for`, `about_summary` (Task 2), `clean_profile`
- Produces: `POST /api/more {"profile"}` → `more_for(...)` JSON, 오늘은 `Asia/Seoul` 날짜. `POST /api/chat` 의 선택 `about: {name, org, summary, link}`.

- [ ] **Step 1: 실패하는 테스트**
```python
def test_more_endpoint(): # {"profile": {"age": 20, "region": "충북"}} → 200, groups 비지 않음, 각 item 에 status/conditions; 잘못된 JSON → 400
def test_chat_about_is_cleaned(): # about 의 name 500자 → 컨텍스트에 80자까지, link "javascript:x" → 링크 없음, about 이 dict 아님 → 무시; FakeBot.last_context 에 사업 이름
```
- [ ] **Step 2:** FAIL 확인
- [ ] **Step 3:** 구현. `about_summary` 가 문장을 만든다 (도메인 단어는 more.py 에): 사업 이름·기관·설명·링크, "공공데이터의 사업으로 법령 문서에는 없음, 공식 사이트 웹 검색으로 확인하고 웹 정보 확인 필요 표시".
  필드는 str 만, name/org 80자, summary 200자, link 는 `https?://` 만. 맥락은 profile 문장과 about 문장을 줄바꿈으로 잇는다.
- [ ] **Step 4:** PASS + 전체 테스트
- [ ] **Step 5:** 커밋 `feat: /api/more 와 채팅 about 맥락`

### Task 4: 화면

**Files:**
- Modify: `web/app.js`, `web/chat.js`, `web/i18n.js`, `web/style.css`

**Interfaces:**
- Consumes: `/api/more`, `/api/chat` 의 `about`
- Produces: 화면 `more`(목록), `moreDetail`(params.moreId); `state.more` 에 마지막 응답 보관; 채팅은 `params.moreId` 이면 `about` 을 보내고 "{이름}에 대해: " 를 붙임

- [ ] **Step 1:** 결과 화면의 `.card.more` 를 버튼으로 (`data-go="more"`), 문구 "준비 중 · …" → "청년정책·국가 서비스 · 자동 확인".
- [ ] **Step 2:** 목록 화면: 안내 문구, 분야 제목, 분야당 4개 + "N개 더 보기" 펼침, "조건이 맞지 않아 보이는 N개" 접힘. 카드: "자동 확인" 배지, 상태, 이름, 설명, 출처(청년정책/국가 서비스). 모든 글자 `esc`.
- [ ] **Step 3:** 상세 화면: 조건 행 ✅❓❌, "그 밖의 세부 요건은 원문에서 확인", 기관, 신청 기간 문구, "원문 보기 ↗"(새 창), "물어보기".
- [ ] **Step 4:** `chat.js`: `ctxProgram` 처럼 `ctxMore()` → 추천 질문 3개("어떻게 신청해요?", "누가 받을 수 있어요?", "언제까지 신청해요?")와 `about` 전송.
- [ ] **Step 5:** 390px 헤드리스 점검 (scratchpad/ui 스크립트 방식): 결과 → 더 보기 → 펼치기 → 상세 → 원문 링크 href https → 물어보기(채팅 맥락 표시), JS 오류 0, "undefined" 없음, 빈 프로필·광주 사용자도 목록 표시.
  `PY -m pytest -q` PASS
- [ ] **Step 6:** 커밋 `feat: 일반 지원 목록·상세 화면과 채팅 연결`

### Task 5: 문서, 배포, 리뷰

**Files:**
- Create: `docs/decisions/0010-more-support.md`
- Modify: `docs/DATA.md` (생성물 표에 more.json), `AGENTS.md` (명령어 표에 build_more.py, 데이터 사실: 광주·전남 코드 12)

- [ ] **Step 1:** 문서 작성 (배경, 결정, 결과 표: 테스트 수 전후, 충북 20세·서울 28세 항목 수와 상태 분포)
- [ ] **Step 2:** `PY -m pytest -q` PASS, 커밋 `docs: 일반 지원 더 보기 결정과 데이터`
- [ ] **Step 3:** 브랜치 전체 리뷰(새 리뷰어) → Critical/Important 수정 (RED→GREEN) → `main` 에 fast-forward → `git push origin main` → 실제 사이트에서 `/api/more` 와 390px 흐름 확인

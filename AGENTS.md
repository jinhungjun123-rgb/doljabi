# AGENTS.md — 돌잡이 (돌봄길잡이)

이 저장소에서 일하는 코딩 에이전트(Claude Code, Codex, Cursor …)를 위한 지시문입니다.
사람은 README.md 부터 읽으세요. 앱 설계: `docs/superpowers/specs/2026-11-01-doljabi-mobile-web-design.md`.

## 목표

가족을 돌보는 13~34세 아동·청년이 받을 수 있는 국가·지역 지원을 법령 근거로 안내하는 모바일 웹앱 "돌잡이".
질문 5단계에 답하면 **규칙 코드**(`src/ragbot/domain/eligibility.py`, LLM 없음)가 검수한 지원사업 13개(`data/programs/programs.json`)를
"받을 수 있어 보여요 / 확인이 필요해요 / 어려워 보여요"로 판정하고 (화면에는 앞의 둘만), 채팅은 RAG 챗봇이 법령 문서로 답한다 (출처 칩, 사용자의 언어,
모르면 "찾을 수 없음" + 129·청년미래센터). 최종 자격 판정은 하지 않는다.
채팅에서는 질문마다 **라우터가 먼저 답이 있을 소스를 정하고**, 에이전트가 그 소스를 검색하며, "찾을 수 없음" 전에 나머지 소스도 찾아봅니다.

1. **문서** (비정형): `data/docs/` 의 위기아동청년법·시행령·시행규칙, 보건복지부 고시 3개, 보도자료 (모두 한국어)
2. **지원사업·센터** (앱 화면 전용, 채팅 도구 아님): `data/programs/programs.json` ← 팀 검수 `data/programs/review/*_v3.*`
3. **웹**: 공식 사이트 우선. 나머지가 다루지 않는 모든 것.

각 소스가 다루는 것과 다루지 않는 것은 `config.yaml → sources` (소스 카드)에 있습니다.
목표, 사용자, 성공 수치, 범위 밖은 `docs/GOAL.md` 에 있습니다. 동작을 바꾸기 전에 읽으세요.

## 명령어

Python 3.11 환경에서 저장소 루트에서 실행합니다. **이 PC에서는 `PYTHONPATH=src` 를 붙입니다**: conda 환경 `my_ragbot` 의
`ragbot` 이 다른 폴더(`Downloads/rag_chatbot_template`)에 editable 설치되어 있어서, 붙이지 않으면 그쪽 코드와 config.yaml 이 실행됩니다
(pytest 는 pyproject 의 `pythonpath` 덕분에 괜찮음).

| 명령 | 하는 일 |
|---|---|
| `PYTHONPATH=src CACHE_MODE=nostore uvicorn app.api:app --port 8000` | 앱 서버 (화면 `web/`, API `/api/*`). 내 정보가 디스크에 남지 않게 nostore |
| `python scripts/build_programs.py` | 검수 결과 → `data/programs/programs.json` (손으로 고치지 않음) |
| `python scripts/build_more.py` | 공공데이터 원본 → `data/programs/more.json` ("일반 지원 더 보기", 손으로 고치지 않음) |
| `git push origin main` | Vercel 배포 (GitHub 연결, 설정 `vercel.json`, 키는 Vercel 환경 변수). `index/` 를 바꿨으면 함께 커밋 |
| `bash scripts/deploy_hf.sh` | 예비: Hugging Face Space 배포 (`DRY_RUN=1` 이면 묶음만 만듦) |
|---|---|
| `python -m ragbot build` | ingest + tables + index (데이터, `chunking`, `tables` 설정 변경 후) |
| `python -m ragbot ingest` | kordoc 이 문서를 파싱 → `data/parsed/*.json` + `*.md` (파일 해시로 캐시) |
| `python -m ragbot tables` | 도메인 hook: 표 → SQLite (표가 없으면 건너뜀) |
| `python -m ragbot index` | `data/parsed/` → `index/` (청크 + bge-m3 임베딩) |
| `python -m ragbot ask "질문"` | 답 하나와 도구 호출, 라우팅, 출처, trace 파일 이름 |
| `python -m ragbot eval [--route R]` | 골든 QA → 지표, `runs/eval_*.json` 저장; `eval/thresholds.yaml` 미달이면 exit 1 |
| `python -m ragbot check --fast` | 단위 테스트만 (API 호출 없음). 코드 변경마다 실행 |
| `python -m ragbot check` | **완료 기준**: 단위 테스트와 평가 기준 |
| `streamlit run app/streamlit_app.py` | 채팅 UI + 📊 평가 페이지 |

## 완료 기준

작업은 다음이 **모두** 성립할 때만 완료입니다 (팀 결정 2026-11-01: 템플릿의 골든 QA 20~30개·평가 기준 대신, `docs/decisions/0007`):
1. `python -m ragbot check --fast` 통과. 판정 규칙을 바꿨다면 `tests/test_eligibility.py` 에 그 경우의 테스트가 있다.
2. 화면을 바꿨다면 휴대폰 크기(390px)에서 질문 → 결과 → 상세 → 물어보기를 한 번 확인했다.
3. 채팅 답을 바꾸는 수정(프롬프트, 검색 설정)은 `eval/golden_qa.jsonl` 의 점검 질문 10개로 전후 정답 수를 확인했다.
4. 동작이나 데이터 계약을 바꿨다면 `docs/decisions/` 에 짧은 기록이 있다.

## 경계

**절대 하지 말 것**
- `data/docs/` 와 `data/tables/` 의 원본 파일 수정 (읽기 전용 원본 데이터);
- `docs/GOAL.md` 나 `eval/golden_qa.jsonl` 을 사람 대신 처음부터 작성하기. 비어 있으면 멈추고 사람에게 요청할 것
  (무엇이 정답인지는 사람이 정합니다);
- 실행을 통과시키려고 `eval/` 의 `reference_answer`, 채점 키(`key_points`, `any_of`, `must_not`), `eval/thresholds.yaml` 수정.
  대신 질문을 추가하고, 각 질문에는 데이터에서 직접 확인한 `reference_answer` + `evidence` 를 붙일 것;
- 평가 질문의 답이나 특정 질문 전용 규칙을 프롬프트나 코드에 넣기 (숨겨진 질문으로도 평가합니다);
- LLM이 SQL을 쓰게 하기. 표 질의는 `src/ragbot/domain/queries.py` 의 필터를 거칠 것;
- 도메인 단어를 코어 코드에 넣기. `config.yaml` 이나 `src/ragbot/domain/` 에 둘 것
  (`tests/test_core_is_domain_free.py` 가 검사);
- `.env` 나 API 키를 커밋하거나 출력하기;
- 결정 기록 없이 `src/ragbot/schemas.py` 의 필드 변경.

**먼저 사람에게 물을 것**: 생성된 데이터(`data/parsed/`, `index/`, `.cache/`) 삭제, 의존성 추가,
LLM이나 임베딩 모델 변경, 소스 우선순위 규칙 변경.

## 아키텍처 (자세히: docs/ARCHITECTURE.md)

```
                                    질문 ─▶ 라우터 (소스 카드) ─▶ 계획 {primary, fallback, reason}
                                                                                │
문서 ─kordoc─▶ data/parsed ─sections─▶ chunks ─bge-m3─▶ index/ ─▶ search_documents ─┐   ▼
표 ─load─▶ SQLite ───────────────────────────────────────────────▶ 도메인 도구 ─────┼─▶ 에이전트 ─▶ Answer (+plan)
DuckDuckGo (공식 사이트 우선) ────────────────────────────────────▶ web_search ─────┘
```

에이전트 가드레일 (프롬프트가 아니라 코드): (1) 도구를 하나도 쓰지 않은 답은 한 번 되돌려 보냄;
(2) "찾을 수 없음" 답은 아직 안 찾아본 모든 소스를 계획 순서대로 찾도록 한 번 되돌려 보냄.
계획은 순서만 정하고, 소스를 없애지 않습니다.

코어와 도메인: `src/ragbot/domain/` 은 이 챗봇에만 해당하는 모든 것(섹션 규칙, 표와 그 도구)을,
나머지 `src/ragbot/` 는 범용 코드이며 문구는 `config.yaml` 에서 가져옵니다. `docs/ADAPTING.md` 참고.

층(layer) 규칙, `tests/test_architecture.py` 가 검사: `config, schemas → llm → ingest/web → chunking → domain →
index → tools → router → agent → evaluate → cli/app`. 모듈은 자기 왼쪽 층에서만 import 합니다.

## 일하는 방법

1. 앱 작업은 `docs/superpowers/plans/` 의 계획을, 그 밖에는 `tasks/` 카드 하나를 고릅니다. 작업을 섞지 않습니다.
   정답(점검 질문의 reference_answer, 검수 데이터의 값)은 사람이 정합니다. 초안을 쓸 수는 있지만 사람 확인 전에는 쓰지 않습니다.
2. 코드를 바꾸기 전에 문제를 증거로 재현합니다: `python -m ragbot ask` 나 `eval --route …` 를 실행하고 `runs/` 의 trace 를 엽니다.
3. 원인을 고치는 가장 작은 변경을 합니다. 변경마다 `python -m ragbot check --fast`.
4. 채팅 답을 바꿨다면 점검 질문 10개를 다시 돌리고 마지막 `runs/eval_*.json` 과 비교합니다. 정답 수를 떨어뜨린 수정은 되돌립니다.

## 디버깅 지도: 증상 → 볼 곳

| 증상 | 볼 곳 | 흔한 원인 |
|---|---|---|
| 평가 출력에 `⚠router`: 계획이 엉뚱한 소스를 고름 | trace → `answer.plan.reason` | `config.yaml → sources` 소스 카드 (특히 `not_covers`); `router.py` 프롬프트 |
| 소스는 맞지만 느림 (2–3개 소스 검색) | trace → 도구 호출 순서 | 같음: 라우터가 처음에 빗나감; router_accuracy 확인 |
| PDF에는 있는데 검색되지 않음 | `data/parsed/*.md` | 파싱에서 사라짐 (이미지 페이지 → OCR, 표 분리) |
| 검색된 문단에 맥락이 없음 (섹션 이름 없이 "서류: 여권…") | `index/chunks.json` breadcrumb | `domain/sections.py` 의 섹션 규칙 |
| 맞는 문단이 6위 이하 | trace → `search_documents` 결과 | `retrieval` 설정, 질의 표현, 재순위화 |
| 맞는 소스를 찾았지만 도구 인자가 틀림 | trace → 도구 호출 | 도구 설명 (`config.yaml documents.*`, `domain/tools.py`), 시스템 프롬프트 |
| 표의 값이 틀림 | trace → 도메인 도구 결과 | `domain/queries.py` 필터, `domain/tables.py` 파싱; LLM 탓이 아님 |
| 답의 언어가 틀리거나 출처가 없음 | trace 의 마지막 메시지 | `config.yaml` 시스템 프롬프트 |
| 아무것도 못 찾았는데 자신 있게 답함 | trace: 빈 결과, 확신에 찬 답 | 시스템 프롬프트의 기권 규칙; `unanswerable` 평가 질문 추가 |
| `python -m ragbot …` 가 "TODO 챗봇 이름" 설정이나 0 chunks 로 돈다 | `python -c "import ragbot; print(ragbot.__file__)"` | 다른 폴더의 템플릿이 import 됨 → `PYTHONPATH=src` |
| 결과 카드 상태가 법령과 다름 | `src/ragbot/domain/eligibility.py` 의 `RULES`, `tests/test_eligibility.py` | 조건 함수의 ok/unknown/no 분기; LLM 탓이 아님 |
| 화면에 "data/docs", "시트" 같은 내부 문구 | `scripts/build_programs.py` 의 `USER_WORDING` | 검수 파일의 표현이 그대로 넘어옴 (`test_no_review_file_wording_reaches_users`) |
| 채팅이 조문을 인용하고도 결론이 틀림 (예: 병역 가산) | trace 의 마지막 메시지와 `search_documents` 결과 (`note`) | 검색은 맞음 → 그 문단에 읽는 법 `config.yaml → documents.notes` (`docs/decisions/0011`). 프롬프트 규칙은 다른 문항을 떨어뜨림 (0007) |
| 원문에 있는 목·호가 검색되지 않음 | `index/chunks.json` 에서 그 문장 찾기 | 목록의 하위 항목(`children`)이 빠짐 → `ingest/sections.py`, 색인 다시 만들기 |
| 채팅 요청이 500 | 서버 로그 | 요청 본문이 UTF-8 JSON이 아님 (Windows curl) → 400 으로 처리됨 |

## 에이전트가 틀리기 쉬운 데이터 사실 (자세히: docs/DATA.md)

- **자기돌봄비는 1회 200만원 이용권**(고시 제3조). 인천·울산 공고, 온통청년, 청년ON 신청 페이지도 "연 200만원"으로 쓰지만 법령은 1회다.
- **나이 34세 상한은 병역 기간만큼 늘어난다** (시행령 제11조①1 단서). 35세라고 바로 탈락시키지 말 것.
- **"35세 이상 다른 가족"과 "주소 일치" 요건에는 예외가 있다** (시행규칙 제6조①②): 그 가족이 장애·중증질환 등이거나, 학업·취업으로 따로 살며 돌보는 경우.
- **온통청년 지역 코드에서 광주·전남은 `12`(전남광주통합특별시) 하나**다 (강원 51, 전북 52). 29·46 이 아니다.
  "나이 제한 있음, 0~0세"는 범위가 글로만 적힌 것(594개): `build_more.py text_age()` 가 대상 글에서 읽고(아동·자녀·어르신 나이 제외), 없으면 나이 칸 없음(19~39세 기본).
  복지로 국가 서비스는 자격이 설명 글에만 있다 → 자동 판정은 "확인 필요". 신청 주체(학교·기업) 칸이 없다 → 이름 낱말로 거른다 (`docs/decisions/0010`).
- **청년미래센터는 2026-11-01 기준 12곳 운영, 5곳(경기·경북·경남·제주·세종) 준비 중** (청년ON). 보도자료(2026.3)의 "4곳"은 낡은 정보.
- **서울의 "자기돌봄비"는 두 가지**: 국가(1회 200만원, 13~34세, 2026.10.1~ 서울복지포털 접수)와 서울형(월 30만원, 9~39세, 2026년 마감).
- `data/programs/programs.json` 은 생성물이다. 고칠 때는 검수 파일과 `scripts/build_programs.py` 를 고치고 다시 생성한다.

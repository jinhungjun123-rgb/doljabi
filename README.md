# 돌잡이 (돌봄길잡이)

가족을 돌보는 13~34세 청년이 받을 수 있는 지원을 법령 근거로 찾아 주는 모바일 웹앱입니다.
질문 5단계 → 받을 수 있어 보이는 지원 카드 → 채팅으로 이어 묻기. 설계: `docs/superpowers/specs/2026-11-01-doljabi-mobile-web-design.md`

```bash
PYTHONPATH=src python -m ragbot index                                   # 문서 인덱스 (처음 한 번, 임베딩 API)
PYTHONPATH=src CACHE_MODE=nostore uvicorn app.api:app --port 8000       # 앱: http://localhost:8000
python scripts/build_programs.py                                        # 검수 결과 → data/programs/programs.json
git push origin main                                                    # Vercel 배포 (docs/decisions/0008)
```

`PYTHONPATH=src`: 이 PC의 conda 환경 `my_ragbot`은 다른 폴더(원본 템플릿)에 설치되어 있어서, 붙이지 않으면 그쪽 코드가 실행됩니다.

아래는 이 프로젝트가 출발한 수업 템플릿의 안내입니다.

---

# 나의 RAG 챗봇 — 학생 프로젝트 템플릿

수업 예제(**CBNU 유학생 도우미**, `rag_chatbot_starter`)의 **코어는 그대로 두고, 도메인을 비워 둔** 템플릿입니다.
여러분이 직접 고른 주제(도서관 도우미, 사내 규정 도우미, 제품 지원 …)로 자기만의 챗봇을 만듭니다.

이미 동작하는 것 (✅ 그대로 사용):
라우터 → 에이전트 루프 → 가드레일, kordoc 파싱, 섹션 단위 청킹, bge-m3 검색과 재순위화, 공식 사이트 우선 웹 검색,
골든 QA 평가와 기준(gate), Streamlit 채팅과 📊 평가 페이지, 아키텍처 테스트.

여러분이 채울 것 (🔁 TODO):

| | 파일 | 내용 |
|---|---|---|
| 🔁 | `docs/GOAL.md` | 사용자, 질문, 범위 밖, 목표 수치 |
| 🔁 | `data/` | 나의 문서(`data/docs/`)와 표(`data/tables/`, 선택) |
| 🔁 | `docs/DATA.md` | 데이터를 직접 읽고 발견한 사실과 빈틈 |
| 🔁 | `eval/golden_qa.jsonl` | 직접 검증한 질문 20–30개 (형식: `eval/golden_qa.example.jsonl`) |
| 🔁 | `config.yaml` | 페르소나, 시스템 프롬프트, 소스 카드, 문서 설명, 공식 사이트 |
| 🔁 | `src/ragbot/domain/` | 섹션 규칙, 표 → SQLite, 표 질의, 도메인 도구 |
| ✏️ | `AGENTS.md`, `tasks/` | 코딩 에이전트에게 줄 규칙과 작업 카드 |

## 순서 (강의 슬라이드 25 "시작점: 정답부터 정의하라")

`tasks/` 의 카드를 **번호 순서대로, 한 번에 하나씩** 합니다.

| 단계 | 카드 | 누가 |
|---|---|---|
| 0 | `00_setup` 환경 설정 | 여러분 |
| 1 | `01_goal` 목표 정의 | **여러분만** (에이전트에게 맡기지 말 것) |
| 2 | `02_data` 데이터 넣고 직접 읽기 | 여러분 (+ 에이전트가 파싱 실행) |
| 3 | `03_golden_qa` 골든 QA 20–30개 | **여러분만** |
| 4 | `04_sections` 섹션 규칙과 청크 | 여러분 + 코딩 에이전트 |
| 5 | `05_tables` 표와 도메인 도구 (선택) | 여러분 + 코딩 에이전트 |
| 6 | `06_config_baseline` 설정, 첫 기준 점수 | 여러분 + 코딩 에이전트 |
| 7 | `07_agents_md` 에이전트 규칙 완성 | 여러분 |
| 8 | `08_improve` 개선 반복 | 여러분 + 코딩 에이전트 |

> 1–3단계는 여러분만 할 수 있습니다. 코딩 에이전트는 코드를 쓸 수 있지만, 무엇이 정답인지는 정할 수 없습니다.
> 엉성한 버전부터 측정하세요. 측정하지 않은 변경은 좋아 보이기만 합니다.

## 설정

미리 설치할 것은 **conda 하나**입니다 ([Miniforge](https://github.com/conda-forge/miniforge) 권장).
Python 3.11 과 Node.js 20 은 스크립트가 conda 환경 안에 설치합니다. 모든 패키지 버전이 고정되어 있어
(`requirements.lock`, `package-lock.json`) 모두가 같은 환경을 갖게 됩니다.

```bash
bash setup.sh                                          # macOS / Linux
powershell -ExecutionPolicy Bypass -File setup.ps1     # Windows
```

스크립트가 하는 일: conda 환경 `my_ragbot` 생성 → 고정 버전 패키지 설치 → kordoc 엔진(`npm ci`) →
`.env` 생성(이미 있으면 그대로) → `python -m ragbot check --fast`. 여러 번 실행해도 안전합니다.
끝나면 `conda activate my_ragbot` 하고 `.env` 에 LLM / 임베딩 / 재순위화 주소와 키를 채우세요.

<details><summary>수동 설치</summary>

```bash
conda env create -f environment.yml && conda activate my_ragbot
pip install -r requirements.lock && pip install -e ".[dev]" --no-deps
npm ci
cp .env.example .env
python -m ragbot check --fast
```
</details>

## 명령어

| 명령 | 하는 일 |
|---|---|
| `python -m ragbot build` | ingest + tables + index (데이터, `chunking`, `tables` 설정을 바꾼 뒤) |
| `python -m ragbot ingest` | kordoc 으로 문서 파싱 → `data/parsed/*.json` + `*.md` |
| `python -m ragbot tables` | 표 → SQLite (표가 없으면 건너뜀) |
| `python -m ragbot index` | `data/parsed/` → `index/` (청크 + 임베딩) |
| `python -m ragbot ask "질문"` | 답 하나: 라우팅 계획, 도구 호출, 출처, 실행 기록(trace) 파일 이름 |
| `python -m ragbot eval [--route R]` | 골든 QA 평가 → `runs/eval_*.json`, 기준 미달이면 exit 1 |
| `python -m ragbot check --fast` | 단위 테스트만 (API 호출 없음). 코드를 바꿀 때마다 |
| `python -m ragbot check` | **완료 기준**: 단위 테스트 + 평가 기준 |
| `streamlit run app/streamlit_app.py` | 채팅 + 📊 평가 페이지 |

## 참고

- 완성된 예시: `rag_chatbot_starter` (같은 코어, CBNU 도메인). 막히면 같은 이름의 파일을 비교해 보세요.
- `docs/ARCHITECTURE.md` 구조와 층(layer) 규칙 · `docs/EVAL.md` 골든 QA 형식과 지표 ·
  `docs/ADAPTING.md` 무엇을 유지하고 무엇을 바꾸는지 · `docs/decisions/starter/` 코어 설계 결정의 이유
- 도메인 단어가 코어 코드에 들어가면 `tests/test_core_is_domain_free.py` 가 실패합니다. 그런 단어는
  `config.yaml` 이나 `src/ragbot/domain/` 으로 옮기세요.

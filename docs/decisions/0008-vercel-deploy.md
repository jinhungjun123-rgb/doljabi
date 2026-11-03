# 0008 — 배포를 Hugging Face Spaces 에서 GitHub + Vercel 로

**상태:** 채택 · 2026-11-01 · 0006 의 "저장 안 함" 원칙은 그대로

## 배경
심사위원이 아무 때나 주소를 연다. 무료 HF Space 는 48시간 동안 아무도 쓰지 않으면 잠들고, 깨우는 데 수십 초가 걸린다.
서버도 해외에 있어 학교 LLM 서버까지 멀다. 사용자(팀)가 GitHub `jinhungjun123-rgb` 저장소와 Vercel 을 쓰기로 했다.

## 결정
- `api/index.py` 가 `app.api:app` 을 그대로 Python 함수 하나로 실행한다. `src/` 를 sys.path 맨 앞에 넣는다
  (설치된 ragbot 은 config.yaml 을 site-packages 에서 찾는다). `CACHE_MODE` 기본값은 `nostore`.
- `vercel.json`: 화면(`web/`)은 정적 파일로, `/api/*` 만 함수로. 리전 `icn1`(서울), 최대 120초 (채팅 시간 제한 90초).
  Node 설치(`package.json` 의 kordoc 엔진)는 건너뛴다: 앱 서버는 문서를 파싱하지 않는다.
- `index/`(약 0.6MB)를 저장소에 넣는다. Vercel 은 GitHub 의 파일만 받는다. 문서나 청킹을 바꾸면 `ragbot index` 후 함께 커밋.
- 키는 Vercel Project → Settings → Environment Variables 에만 넣는다.
- HF 용 `Dockerfile`, `scripts/deploy_hf.sh` 는 예비로 남긴다.

## 결과
| | 전 | 후 |
|---|---|---|
| `check --fast` | 51 passed, 2 skipped | 53 passed, 2 skipped (`test_vercel_entry.py`) |
| 평가 지표 | 변화 없음 (답 생성 코드 그대로) | 같음 |

## 대안
- HF Spaces 유지: 준비는 끝났지만 잠들기와 거리 때문에 기각.
- 화면까지 함수로 서빙: 정적 파일을 CDN 에 두는 편이 빠르고, 저장소 파일이 그대로 노출될 일도 없어 기각.

## 추가 (Python 버전 고정, 2026-11-03)
Vercel 이 `requires-python = ">=3.11"` 을 보고 Python 3.12 를 고르기 시작했는데, 이전 빌드 캐시의 잠금은 3.11 기준이라
`pyarrow==26.0.1` 설치에서 빌드가 실패했다 (cp311 wheel 만 있음). `.python-version` 에 `3.11` 을 적어 로컬 개발 환경(3.11)과 맞췄다.

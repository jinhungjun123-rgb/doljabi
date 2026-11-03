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

## 추가 (pyarrow 26.0.1 제외, 2026-11-03)
배포가 `uv sync` 에서 실패했다: Vercel 은 Python 3.12 로 빌드하는데, 그날 올라온 `pyarrow==26.0.1` (streamlit 이 설치)은 cp311 wheel 만 있었다.
캐시 없이 다시 빌드해도 같았고, `.python-version` 3.11 고정도 실패해서 되돌렸다. `pyproject.toml → [tool.uv] constraint-dependencies = ["pyarrow!=26.0.1"]`
로 그 버전만 피한다 (26.0.0 설치). 26.0.1 파일이 다 올라오면 지워도 된다.

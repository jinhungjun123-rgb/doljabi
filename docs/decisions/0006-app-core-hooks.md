# 0006 — 앱을 위한 코어 최소 수정: 진행 콜백, 사용자 맥락, 저장 안 함 캐시

**상태:** 채택 · 2026-11-01 · 설계: `docs/superpowers/specs/2026-11-01-doljabi-mobile-web-design.md`

## 배경
모바일 웹앱 "돌잡이"의 채팅은 (1) 답을 기다리는 10~30초 동안 진행 단계를 보여 주고, (2) 사용자가 입력한 상황(나이, 지역, 돌봄 상황)을
질문과 함께 보내며, (3) 그 정보를 서버에 남기지 않아야 한다. 기존 `Chatbot.answer()`는 끝날 때까지 아무것도 알리지 않고,
`llm.cached`는 모든 LLM·임베딩 응답을 `.cache/`에 쓴다.

## 결정
- `Chatbot.answer(question, history=None, context=None, on_progress=None)`: 선택 인자 두 개.
  `context`는 시스템 프롬프트 끝에 덧붙고, `on_progress(step, data)`는 `route`(계획 직후) · `tool`(도구 호출 직전) · `write`(최종 답 직전)에 불린다.
  둘 다 생략하면 기존 동작과 같다.
- `CACHE_MODE=nostore`: API를 부르고 디스크에 아무것도 쓰지 않는다 (실패 시 캐시 대체도 없음). 앱 서버는 이 모드와 `write_traces=False`로 실행한다.
- 도메인 단어는 코어에 넣지 않았다. 사용자 상황 문장은 `domain/eligibility.py`의 `profile_summary`가 만든다.

## 결과
| | 전 | 후 |
|---|---|---|
| `check --fast` | 30 passed, 2 skipped (Task 1 후) | 44 passed, 2 skipped (판정 규칙·훅 테스트 포함) |
| 평가 지표 | 골든 QA 없음 | 같음 |

## 대안
- 앱 전용 에이전트를 따로 복사: 가드레일·라우팅이 두 벌이 되어 기각.
- 진행 표시 없이 응답만 기다리기: 30초 동안 멈춘 것처럼 보여 기각.
- `.cache/`를 주기적으로 지우기: 지우기 전까지는 남아 있어서 기각.

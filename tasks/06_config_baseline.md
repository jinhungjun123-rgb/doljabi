# 06 — 설정과 첫 기준 점수 (얇은 파이프라인)

**상태:** 팀 결정으로 대체 (2026-11-01) · 설정 완료, 기준 점수는 채팅 점검 10개로 (`docs/decisions/0007`)

## 목표
처음부터 끝까지 돌아가는 가장 단순한 챗봇을 만들고, **점수가 나빠도** 측정해서 기준점(baseline)으로 저장한다.
원본 프로젝트의 첫 점수는 0.50이었습니다. 이 기준이 없으면 어떤 변경도 효과를 증명할 수 없습니다.

## 파일
- `config.yaml` (`chatbot`, `sources`, `documents`, `web`, `agent`)
- `docs/decisions/`

## 완료 조건
- [x] `config.yaml` 에 `TODO` 가 하나도 남지 않았다 (`grep -n TODO config.yaml`)
- [x] 시스템 프롬프트: 도구를 먼저 쓴다, 출처를 밝힌다, 사용자의 언어로 답한다, 모르면 "찾을 수 없음" + 안내처
- [x] 소스 카드마다 `covers` 와 `not_covers` 를 썼다. `not_covers` 에는 골든 QA 에서 발견한 "있을 것 같지만 없는" 것들
  (지금은 DATA.md 4절 빈틈 기준. 골든 QA 를 쓰며 더할 것)
- [x] `web.official_domains` 를 실제 공식 사이트로 바꿨다 (`example.com` 없음)
- [ ] `python -m ragbot build` 후 `python -m ragbot eval` 을 실행했다. 첫 점수를 `docs/decisions/0002-baseline.md` 에
      기록했다 (accuracy, route_accuracy, router_accuracy, by_route, by_lang, 실행 파일 이름)
- [x] 앱에서 예시 질문 2개를 물어보고, 출처 배지와 도구 호출이 보이는지 확인했다
  (2026-10-29: 두 질문 모두 🧭 계획 docs → web, 📘 문서 배지, Sources, 🔧 search_documents 1회 표시.
  발견: 출처 쪽수·조문이 틀린 인용이 있음 — "본인부담금 5% 할인" 을 법 제19조로 인용(실제는 보도자료 붙임1, 5%p),
  "자기돌봄비 200만 원" 을 p.1 로 인용(실제 p.2) → tasks/08)

## 확인
```
python -m ragbot build
python -m ragbot eval
streamlit run app/streamlit_app.py
```
이 단계에서는 기준 미달이어도 괜찮습니다. 수치를 기록하는 것이 완료 조건입니다.

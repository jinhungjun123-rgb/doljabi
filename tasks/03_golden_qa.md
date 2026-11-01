# 03 — 골든 QA: 사람이 직접 검증한 정답지

**상태:** 팀 결정으로 대체 (2026-11-01) · 템플릿의 20~30개 대신 채팅 점검 질문 10개. 설계: `docs/superpowers/specs/2026-11-01-doljabi-mobile-web-design.md`, 기록: `docs/decisions/0007`

## 목표
챗봇이 "잘한다"를 숫자로 잴 수 있게, 정답과 근거가 있는 질문 20–30개를 만든다.

## 파일
- `eval/golden_qa.jsonl` (형식 예시: `eval/golden_qa.example.jsonl`, 필드 설명: `docs/EVAL.md`)

## 완료 조건
- [ ] 질문 20개 이상, 한 줄에 하나. 01 에서 모은 실제 질문에서 출발했다
- [ ] 모든 질문에 `reference_answer` 와 `evidence` (파일 + 페이지, 표의 행, 또는 웹사이트) 가 있고, 직접 확인했다
- [ ] `route` 는 `config.yaml → sources` 의 이름(`docs`, `web`, 표가 있으면 그 이름) 또는 `none` / `any`
- [ ] 소스마다 질문이 있다 (표가 있다면 표 질문 5개 이상). 지원하는 언어마다 질문이 있다
- [ ] 데이터로 답할 수 없는 질문(`"unanswerable": true`) 2개 이상, 인사말(`route: none`) 1개
- [ ] 채점 키: `key_points`(반드시 포함), `any_of`(여러 표기 중 하나), 지어내기 쉬운 내용에는 `must_not`
- [ ] 키는 짧은 사실 하나씩이다 (숫자, 코드, 고유명사). 문장 전체를 키로 쓰지 않았다

## 확인
```
python -m pytest tests/test_eval.py -q
```
그리고 다른 사람이 `evidence` 만 보고 같은 답을 찾을 수 있는지 한두 개 확인해 보세요.

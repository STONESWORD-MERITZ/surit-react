# SURIT-PROGRESS-001: 동일 자료 고지 결과 결정성 보장 계획 반영

## 목적

`PROGRESS.md`에서 메리츠 추천연도 관련 항목을 제거하고, 동일 자료 반복 분석 시 고지 결과가 항상 같아야 한다는 요구사항을 최우선 진행 계획으로 기록한다.

## Owner

Codex

## 범위

- `PROGRESS.md`
- `.agent-harness/decisions.md`
- `.agent-harness/handoff.md`
- `.agent-harness/locks.md`
- `.agent-harness/tasks/SURIT-PROGRESS-001-deterministic-disclosure.md`

## 요구사항

- 메리츠 추천연도 문구를 `PROGRESS.md`에서 제거한다.
- 동일 자료 반복 실행 시 아래 결정론 결과가 항상 같아야 함을 명시한다.
  - 고지 대상 질병코드
  - 질병명
  - 건수
  - 질문 분류(Q1~Q4)
  - 결정론 근거(입원/수술/통원/투약)
- AI 분석이 필요한 추가검사/재검사 소견 문장 또는 보조 판단 설명은 변동 가능 영역으로 분리한다.
- 사용자가 제공한 PDF 비밀번호는 검증 참고로만 사용하고 저장소 문서에는 기록하지 않는다.

## Verify

- `git diff --check`
- `rg -n "메리츠 추천연도|메리츠 룰 출처" PROGRESS.md`
- `rg -n "동일 자료 결과 결정성 보장|Deterministic Disclosure Results" PROGRESS.md .agent-harness/decisions.md`
- `npm run lint`
- `npm test`
- `npm run build`

## Publish

- Commit message: `SURIT-PROGRESS-001: 메리츠 추천연도 제거 + 동일자료 고지 결과 결정성 계획 반영`
- Push: `git push origin main`

## Notes

이 태스크는 문서·계획 정리다. 실제 결정성 보장 구현은 후속 코드 태스크에서 진행한다.

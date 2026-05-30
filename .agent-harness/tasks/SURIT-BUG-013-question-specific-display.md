# SURIT-BUG-013: 질문별 필요한 고지 지표만 표시

## 목적

결과 카드가 모든 질문에 통원, 입원일수, 입원횟수, 수술횟수, 투약 칩을 공통 표시해 화면이 과도하게 복잡하고, 확인할 필요 없는 추가검사/치료 중 의심 정보가 일부 문항에 노출되는 문제를 개선한다.

## Owner

Codex

## 범위

- `src/pages/Disclosure.tsx`
- `.agent-harness/handoff.md`
- `.agent-harness/locks.md`

## 요구사항

- 고지 결과 카드의 통원/입원/수술/투약 칩은 각 질문 문항에서 확인이 필요한 지표만 표시한다.
- 건강체 Q3는 발동 근거인 입원/수술/통원 7회 이상/투약 30일 이상만 표시한다.
- 간편 Q2는 입원·수술 지표만 표시한다.
- 건강체 Q3와 간편 Q2에서는 추가검사 의심, 치료 중, 종결 같은 AI 보조 확인 태그/문구를 표시하지 않는다.
- 백엔드 결정론 결과값은 변경하지 않는다.

## Verify

- `npx tsc -p tsconfig.app.json --noEmit`
- `npm run lint`
- `npm run build`

## Publish

- Commit message: `SURIT-BUG-013: 질문별 필요 고지 지표만 표시 + Q3/easy Q2 의심소견 숨김`
- Push: `git push origin main`

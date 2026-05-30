# SURIT-LAUNCH-002: BOHUMFIT.ai 정식 오픈 전 신뢰도 정리

project: SURIT
owner: Codex
status: completed

## Goal

정식 오픈 전 사용자에게 노출되는 placeholder, 오래된 도메인/브랜드, 미완성 기능 진입점, 과도한 속도 표현을 정리한다.

## Scope

Editable files:

- `src/components/Footer.tsx`
- `src/pages/PrivacyPolicy.tsx`
- `src/pages/Terms.tsx`
- `src/pages/Home.tsx`
- `src/components/Layout.tsx`
- `src/App.tsx`
- `public/og-image.svg`
- `BOHUMFIT_OPEN_RISK_CHECKLIST.md`
- `.agent-harness/handoff.md`
- `.agent-harness/locks.md`

Do not edit:

- `.env`
- `dist/`
- `node_modules/`
- backend analysis logic

## Requirements

- Remove visible TODO/registration placeholder text from public legal pages.
- Keep BOHUMFIT/보험핏 public naming and avoid guarantee language.
- Replace old `surit-react.vercel.app` OG exposure with `bohumfit.ai`.
- Hide or gate the unfinished 보장분석 feature before public launch.
- Replace exact "5분" marketing claims with a safer data-volume-dependent expression.
- Update the open-risk checklist with already verified domain/CORS/Auth smoke checks and remaining human/legal QA.

## Verify

- `npx tsc -p tsconfig.app.json --noEmit`
- `npx tsc -p tsconfig.node.json --noEmit`
- `npm run lint`
- `npm test`
- `npm run build`
- `git diff --check`

## Publish

- Codex handles Git staging, commit, and push after verification.
- Commit message: `SURIT-LAUNCH-002: BOHUMFIT.ai 정식 오픈 전 법적 placeholder + 공개 신뢰도 정리`

## Notes

- Exact business registration details were not provided. Public placeholder text is removed, and final business/legal review remains a Human launch gate.

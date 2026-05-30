# BOHUMFIT-002: git remote 교체 + package name 정리

project: BOHUMFIT
owner: Codex
status: completed

## Goal

리브랜딩 마무리로 local git `origin`을 `STONESWORD-MERITZ/bohumfit.git`로 교체하고, npm package name을 `bohumfit`으로 정리한다.

## Scope

Editable files:

- `package.json`
- `package-lock.json`
- `.agent-harness/handoff.md`
- `.agent-harness/locks.md`

Allowed local git config change:

- `git remote set-url origin https://github.com/STONESWORD-MERITZ/bohumfit.git`

Do not edit:

- Vercel/Railway/Supabase/Sentry dashboard settings
- CORS/API URL
- historical `SURIT-*` task IDs/comments
- local folder name `surit-react`

## Requirements

- Record remote before/after.
- Run `git fetch origin` after URL change and stop on failure.
- Change only package name fields from `surit-react` to `bohumfit`.
- Do not run `npm install` unless lock consistency breaks.

## Verify

- `git remote -v`
- `git fetch origin`
- `npx tsc -p tsconfig.app.json --noEmit`
- `npx tsc -p tsconfig.node.json --noEmit`
- `npm run build`
- `git diff --check`

## Publish

- Commit and push to the new `origin/main` after verification.
- Commit message: `BOHUMFIT-002: git remote bohumfit 전환 + package name 정리`

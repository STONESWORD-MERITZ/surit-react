# Agent Collaboration Rules

This repository uses a lightweight harness so Claude, Codex, and the user can work on the same project without losing context.

## Project

- Name: SURIT
- Local path: `C:\Users\18_rk\surit-react`
- Task prefix: `SURIT`
- Existing Claude guide: `CLAUDE.md`

Claude should continue following `CLAUDE.md`. When this file and `CLAUDE.md` overlap, follow both. If there is a conflict, prefer task-specific instructions in `.agent-harness/tasks/` and record the conflict in `.agent-harness/handoff.md`.

## Agent Roles

- Claude: architecture review, broad code reading, first-pass implementation, refactor proposals.
- Codex: implementation follow-up, verification, tests, local browser checks, bug fixes, scoped Git staging, commit, and push when the task or user asks to publish.
- User: priority, product direction, final approval for product decisions and risky or destructive actions.

Roles may change per task, but each task must name one current owner.

## Required Workflow

1. Read this file first.
2. Read `CLAUDE.md` when using Claude or when project behavior preferences matter.
3. Read the relevant task in `.agent-harness/tasks/`.
4. Check `.agent-harness/locks.md` before editing files.
5. Check `git status --short` before making changes.
6. Edit only files inside the task scope.
7. Run the verification commands listed in the task or `.agent-harness/verify.md`.
8. Update `.agent-harness/handoff.md` with changed files, verification results, and remaining issues.
9. If the task or user asks to publish, Codex checks `git status --short`, stages only task-scoped files, creates a task-labeled commit, pushes the branch, and records the result in `handoff.md`.
10. Release any file locks in `.agent-harness/locks.md` when done.

## Safety Rules

- Do not overwrite work from another agent or the user.
- Do not modify unrelated files.
- Do not commit generated build output unless the task explicitly asks for it.
- Do not guess hidden requirements; record assumptions in the task or handoff.
- If verification cannot be run, write the exact reason in `handoff.md`.
- Keep task changes small enough that another agent can review them quickly.
- Do not stage, commit, or push unrelated user or agent changes.
- If unrelated changes are present, Codex must leave them unstaged and mention them in the final report.

## Harness Files

- `.agent-harness/tasks/`: task queue and task templates.
- `.agent-harness/handoff.md`: latest implementation notes and next-agent handoff.
- `.agent-harness/decisions.md`: project decisions that should persist.
- `.agent-harness/locks.md`: temporary file ownership during active work.
- `.agent-harness/verify.md`: standard commands for validation.

## 에이전트 역할 분담

### Claude (Cowork) — 주로 담당
- 큰 설계, 아키텍처 변경
- 기존 코드 구조 파악 후 리팩터링
- UI/UX 구현 (React 컴포넌트, 스타일)
- 보고서/문서 작성

### Codex — 주로 담당
- 추가 구현, 버그 수정
- 테스트 작성/보강
- 검증 실행 (lint, test, build)
- 로컬 실행 확인
- 검증 통과 시 git 반영 — 태스크 범위 파일만 `git add` → `git commit` → `git push origin main`
- 커밋 메시지: 한국어, `{태스크ID}: {변경 요지}` 형식 (필요 시 끝에 `(#{테스트/변경 요약})` 부기 — 예: `SURIT-002: 처방 PDF 분류 우선순위 보정`)

### 공통 규칙
- 한 태스크 안에서 owner는 한 명만
- 리뷰는 owner가 아닌 쪽이 수행
- 사람이 최종 승인
- 본인이 처리할 수 없는 영역이면 handoff의 Next에 다른 에이전트 지정

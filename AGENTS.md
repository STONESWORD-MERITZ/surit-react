# Codex Operating Rules

This repository is now run with Codex as the single working agent.

## Project

- Name: SURIT
- Local path: `C:\Users\18_rk\surit-react`
- Task prefix: `SURIT`
- Legacy project guide: `CLAUDE.md`

`CLAUDE.md` is kept as a legacy knowledge and convention document. Codex should read it when project behavior, stack details, or historical preferences matter, but new work should follow this file and the active task file first.

## Agent Roles

- Codex: planning, code reading, architecture judgment, implementation, refactoring, tests, lint/build verification, browser smoke checks, handoff notes, scoped Git staging, commit, and push when the user asks to publish.
- User: priority, product direction, production approval, and decisions that affect business behavior or risky data changes.
- Claude/Cowork: not part of the default workflow. Old Claude entries in `.agent-harness/handoff.md` are historical context only.

Each active task should have one current owner: Codex, unless the user explicitly says otherwise.

## Required Workflow

1. Read this file first.
2. Read `.agent-harness/handoff.md` for the latest project state.
3. Read `CLAUDE.md` only as legacy project context when useful.
4. Read or create the relevant task file in `.agent-harness/tasks/`.
5. Check `.agent-harness/locks.md` before editing files.
6. Check `git status --short -uall` before making changes.
7. Keep edits inside the task scope unless the user approves an expanded scope.
8. Run the verification commands listed in the task or `.agent-harness/verify.md`.
9. Update `.agent-harness/handoff.md` with changed files, verification results, notes, and remaining issues.
10. Release any file locks in `.agent-harness/locks.md`.
11. If the task or user asks to publish, stage only task-scoped files, create a task-labeled commit, push the branch, and record the result.

## Safety Rules

- Do not overwrite user work or unrelated local changes.
- Do not stage, commit, or push unrelated files.
- Do not commit generated build output unless the task explicitly asks for it.
- Do not guess hidden requirements; record assumptions in the task or handoff.
- If verification cannot be run, write the exact reason in `handoff.md`.
- Keep task changes small enough to review quickly.
- For production-impacting changes, finish local verification first and leave final live validation to the user unless explicitly asked to check deployment.

## Standard Verification

Use `.agent-harness/verify.md` as the source of truth. Current standard commands:

```powershell
npm run lint
npm test
npm run build
```

Backend changes normally also require:

```powershell
cd backend
python -m pytest -q
```

For UI changes, also run the app locally and perform a browser smoke check when practical.

## Harness Files

- `.agent-harness/tasks/`: task queue and task-specific instructions.
- `.agent-harness/handoff.md`: latest implementation notes and completion records.
- `.agent-harness/decisions.md`: persistent decisions.
- `.agent-harness/locks.md`: temporary file ownership during active work.
- `.agent-harness/verify.md`: standard validation commands.

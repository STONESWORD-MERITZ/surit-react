# Locks

Use this file to record active Codex file ownership during a task.

## Active

- none

## Rules

- New work is Codex-only unless the user explicitly assigns another owner.
- Add active locks before editing task-scoped files.
- Release locks when the task is complete, blocked, or handed back to the user.
- Keep this file operational and short. Historical lock detail lives in git history and `handoff.md`.

## Released

- 2026-05-30 `SURIT-PROGRESS-001` - Codex - progress determinism plan updated; locks released.
- 2026-05-30 `SURIT-HARNESS-CODEX-ONLY` - Codex - final check/plan/publish completed; locks released.
- 2026-05-30 `SURIT-HARNESS-CODEX-ONLY` - Codex - documentation cleanup completed; locks released.

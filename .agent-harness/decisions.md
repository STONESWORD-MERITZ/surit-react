# Decisions

Record durable project decisions here. Keep entries short and dated.

### 2026-05-30 Codex-Only Harness

Decision:
SURIT work will proceed with Codex as the single working agent by default.

Reason:
The previous Claude/Cowork -> Codex verification sequence created unnecessary handoff overhead.

Impact:
Codex owns implementation, verification, handoff notes, scoped staging, commit, and push when the user requests publication. Historical Claude/Cowork entries remain archival context only.

### 2026-05-30 Deterministic Disclosure Results

Decision:
For identical input PDFs and the same reference settings, disclosure-deterministic fields must be stable across repeated runs.

Reason:
The user observed that running the same materials repeatedly can change disclosure results, which breaks trust in the rule engine.

Impact:
Disease code, disease name, counts, question classification, and deterministic evidence must not change run-to-run. AI-assisted extra-exam/recheck opinion text may vary, but it must not mutate deterministic disclosure counts or disease identity.

## Template

### YYYY-MM-DD Decision Title

Decision:

Reason:

Impact:

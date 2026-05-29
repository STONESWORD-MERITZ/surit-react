# SURIT-HARNESS-CODEX-ONLY: Codex 단독 하네스 문서 정리

## 목적

기존 Claude/Codex → Codex 검증·푸시 흐름을 정리하고, 이후 SURIT 작업을 Codex 단독 하네스 기준으로 진행하도록 문서를 맞춘다.

## 우선순위

운영 문서 정리

## Owner

Codex

## 범위

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `PROGRESS.md`
- `.agent-harness/*.md`
- `.agent-harness/tasks/*.md`

## 범위 외

- 코드 파일
- 설정 파일
- `node_modules/`, `dist/`, 캐시 파일

## 작업 내용

- `AGENTS.md`와 `CLAUDE.md`를 Codex 단독 운영 기준으로 정리한다.
- task template과 task 문서의 신규 진행 기준을 Codex 단독 구현·검증·푸시로 맞춘다.
- `locks.md`는 현재 active lock 중심의 간결한 운영 파일로 정리한다.
- `handoff.md` 상단에 워크플로우 전환 기록을 남긴다.
- 과거 Claude/Codex handoff 내용은 삭제하지 않고 역사 기록으로만 둔다.

## 검증

- `git diff --check`
- `rg -n "Cowork|Claude \\(|Claude/Cowork" .agent-harness/tasks --glob "!SURIT-HARNESS-CODEX-ONLY.md"` (no matches expected)
- `rg -n "Handoff To|다음 에이전트" AGENTS.md CLAUDE.md README.md .agent-harness/tasks .agent-harness/verify.md .agent-harness/decisions.md .github`
- `rg -n "Next: Codex 검증 \\+ 푸시|검증 \\+ 푸시" .agent-harness/tasks --glob "!SURIT-HARNESS-CODEX-ONLY.md"` (no matches expected)

## 완료 조건

- 새 작업 규칙 문서가 Codex 단독 기준을 명시한다.
- 신규 태스크 템플릿이 Codex 단독 owner/publish 흐름을 사용한다.
- locks active가 비어 있고, 이번 문서 정리 잠금이 released 상태로 남는다.
- handoff.md 상단에 이번 문서 정리 결과가 기록된다.

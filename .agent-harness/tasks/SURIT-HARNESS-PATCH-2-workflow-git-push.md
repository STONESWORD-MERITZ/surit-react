# SURIT-HARNESS-PATCH-2: 워크플로우 문서 — Codex git push 담당 반영

## 목적
SURIT-002부터 적용된 워크플로우 변경(검증 통과 후 git 커밋·푸시까지 Codex 담당)을
AGENTS.md와 CLAUDE.md에 반영하여 다음 태스크부터 일관성을 유지한다.

## 우선순위
운영 (태스크 진행 전 필수 정리)

## 예상 소요
~10분

## Owner
Codex (문서 수정 작업)

## 범위 (수정 허용 파일)
- `AGENTS.md`
- `CLAUDE.md`
- `.agent-harness/handoff.md` (완료 기록)
- `.agent-harness/locks.md` (잠금 관리)

## 범위 외 (수정 금지)
- 코드 파일 일체
- 태스크 파일 일체 (기존 것 소급 수정 불필요)

## 작업 내용
### AGENTS.md
"Required Workflow" 또는 "에이전트 역할 분담" 섹션에 아래 내용 추가:
- Codex 담당 항목에 "검증 통과 시 git add → git commit → git push origin main" 명시
- 커밋 메시지 규칙: 한국어, "{태스크ID}: {변경 요지} (#{테스트/변경 요약})" 형식

### CLAUDE.md
"검증 게이트" 또는 "Required Workflow" 관련 섹션에 아래 내용 추가:
- 검증 통과 후 Codex가 푸시까지 담당한다는 점 명시
- Codex는 handoff.md의 Next에 "Codex 단독 검증·푸시" 명시하도록 규칙 추가

## 완료 조건
- AGENTS.md에 Codex git push 담당 명시됨
- CLAUDE.md에 워크플로우 반영됨
- 두 파일 모두 기존 내용과 자연스럽게 통합됨 (섹션 구조 깨지 않기)
- handoff.md 표준 포맷 기록 완료
- locks.md 잠금 해제

## 비고
- SURIT-002 Codex 턴부터 이미 적용 중 — 소급 변경 아닌 문서화 작업
- 이후 모든 태스크에 적용

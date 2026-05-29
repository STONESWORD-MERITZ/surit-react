# SURIT

보험설계사용 알릴의무(고지의무) 분석 플랫폼입니다.

## 현재 운영 방식

SURIT 저장소는 이제 **Codex 단독 하네스 방식**으로 진행합니다.

- 최상위 규칙: `AGENTS.md`
- 프로젝트 세부 관례: `CLAUDE.md` (파일명은 유지, 내용은 Codex 기준)
- 태스크: `.agent-harness/tasks/`
- 최신 작업 기록: `.agent-harness/handoff.md`
- 잠금 관리: `.agent-harness/locks.md`
- 검증 명령: `.agent-harness/verify.md`

과거 handoff/task에 남아 있는 Claude 또는 Cowork 표기는 역사 기록입니다. 새 작업의 구현, 검증, 커밋, 푸시는 Codex가 단독으로 담당합니다.

## 기술 스택

- Frontend: React 19, TypeScript, Vite, Tailwind CSS
- Backend: FastAPI, Python, pdfplumber, pandas, google-genai
- Deploy: Vercel(frontend), Railway(backend)

## 기본 검증

```powershell
npm run lint
npm test
npm run build
```

백엔드 변경 시:

```powershell
cd backend
python -m pytest -q
```

프런트 변경 시:

```powershell
npx tsc -p tsconfig.app.json --noEmit
npx tsc -p tsconfig.node.json --noEmit
```

## 작업 원칙

1. `AGENTS.md`를 먼저 읽고 하네스 절차를 따른다.
2. 작업 전 `git status --short -uall`과 `.agent-harness/locks.md`를 확인한다.
3. 태스크 범위 안에서만 수정한다.
4. 검증 결과와 남은 이슈를 `handoff.md` 상단에 남긴다.
5. 사용자가 publish를 요청했거나 태스크 완료 조건에 push가 있으면 Codex가 직접 커밋·푸시한다.

<!--
표준 포맷 (최신 항목을 위에 쌓기):
## YYYY-MM-DD HH:MM [에이전트명] [태스크ID]
### Changed
- (변경 파일 경로 + 한 줄 설명)
### Verified
- [ ] npm run lint
- [ ] npm test
- [ ] npm run build
- [ ] 수동 확인 항목
### Notes
- (주의사항, 미해결 이슈)
### Next
- (다음 에이전트 + 할 일)
-->

# Handoff

Use newest entries at the top.

## 2026-05-25 13:40 Codex SURIT-HARNESS-PATCH-2
### Changed
- `AGENTS.md`, `CLAUDE.md`, `.agent-harness/tasks/SURIT-HARNESS-PATCH-2-workflow-git-push.md` 검증 시도.
- 커밋/푸시 미수행: `git status --short`에서 요청한 예상 범위 밖 변경이 확인되어 중단.
### Verified
- [x] AGENTS.md, CLAUDE.md, 최신 handoff, locks, SURIT-HARNESS-PATCH-2 task 확인
- [x] locks에 Codex 잠금 추가 후 해제
- [x] git status 범위 확인 — 실패. 범위 밖 변경 존재
- [ ] 커밋 1 `SURIT-002` — 미수행
- [ ] 커밋 2 `SURIT-HARNESS-PATCH-2` — 미수행
- [ ] git push 완료 — 미수행
### Notes
- 예상 범위 내로 보이는 변경: `AGENTS.md`, `CLAUDE.md`, `backend/pipeline/pdf_parser.py`, `backend/tests/test_pdf_parser.py`, `.agent-harness/tasks/SURIT-HARNESS-PATCH-2-workflow-git-push.md`.
- 범위 밖 변경 목록: `backend/requirements.txt`, 삭제된 `새 텍스트 문서.txt`, untracked `PROGRESS.md`, untracked `SURIT_종합감사보고서_2026-05-20.md`.
- `.agent-harness/` 전체가 untracked로 보여 task 파일만 분리 staging이 가능하긴 하나, 현재 지시의 "범위 외 파일이 있으면 중단" 조건을 우선 적용함.
### Next
- Human: 범위 밖 변경(`backend/requirements.txt`, 삭제된 텍스트 파일, `PROGRESS.md`, 감사보고서)을 먼저 커밋/보류/정리할지 결정.
- Codex: 작업트리가 예상 범위만 남으면 두 커밋 분리 후 `git push origin main` 재시도.
- Human: 최종 검토 + SURIT-003 진행 여부 결정.

## 2026-05-25 04:26 Claude SURIT-HARNESS-PATCH-2
### Changed
- `AGENTS.md` — 한국어 "에이전트 역할 분담"의 Codex 항목에 git 반영(`git add` → `commit` → `push origin main`)과 한국어 커밋 메시지 규칙(`{태스크ID}: {변경 요지}`) 추가
- `CLAUDE.md` — 검증 게이트에 "검증 통과 후 Codex가 커밋·푸시 담당" 명시, 진입 지침 절대 규칙에 handoff Next "Codex: 검증 + 푸시" 작성 규칙 추가
- `.agent-harness/tasks/SURIT-HARNESS-PATCH-2-workflow-git-push.md` — 태스크 파일 신규 생성
### Verified
- 문서 패치, 빌드 검증 불필요
- 육안 확인 — 기존 섹션 구조 유지, 내용 추가만 수행 (삭제·재구성 없음)
### Notes
- 진단: AGENTS.md 영문 섹션(Agent Roles·Required Workflow 9번·Safety Rules)과 task TEMPLATE.md의 Publish 섹션은 Codex의 HARNESS-GIT-PUBLISH 턴에서 이미 반영돼 있었음 → 중복 추가하지 않고, 미반영 상태였던 한국어 "에이전트 역할 분담" 섹션과 CLAUDE.md만 보강.
- 소급 변경 아님 — SURIT-002 Codex 턴부터 적용 중인 워크플로우의 문서화.
- 마운트 캐시 지연으로 일부 변경이 mnt에서 즉시 안 보였으나 Windows 원본 정본 확인 완료.
### Next
- Codex (검증 불필요, git push만): 본 문서 패치 변경분(`AGENTS.md`, `CLAUDE.md`, 신규 태스크 파일) 커밋·푸시. SURIT-002 코드 변경분(`pdf_parser.py`, `test_pdf_parser.py`)의 작업트리 정리·커밋은 별건으로 남아 있음 — 아래 13:10 Codex SURIT-002 항목 참조.

## 2026-05-25 13:10 Codex SURIT-002
### Changed
- `backend/pipeline/pdf_parser.py`, `backend/tests/test_pdf_parser.py` 검증 시도.
- 커밋/푸시 미수행: `git status --short`에서 SURIT-002 허용 범위 밖 변경이 함께 확인되어 중단.
### Verified
- [x] `cd backend && python -m pytest -q` — 97 passed
- [x] scope 확인 — 실패. 범위 밖 변경 존재
- [ ] `_resolve_ftype` 상세 로직 리뷰 — 중단 조건 발생으로 미완료
- [ ] 회귀 테스트 6건 상세 리뷰 — 중단 조건 발생으로 미완료
- [ ] git push 완료 — 미수행
### Notes
- 범위 밖 변경 목록: `CLAUDE.md`, `backend/requirements.txt`, 삭제된 `새 텍스트 문서.txt`, untracked `AGENTS.md`, `PROGRESS.md`, `SURIT_종합감사보고서_2026-05-20.md`.
- `.agent-harness/` 전체가 untracked로 보이며, 내부에는 SURIT-002 허용 파일 외에도 `decisions.md`, `verify.md`, `tasks/README.md`, `tasks/TEMPLATE.md`, `tasks/SURIT-001-backend-deps-pinning.md` 등이 포함됨.
- Cowork SURIT-002 자체 검증과 Codex 재검증 모두 pytest 97 passed는 확인됨. 다만 지시된 scope clean 조건을 만족하지 않아 커밋/푸시는 보류.
- 범위 외 후보: 현재 하네스/문서/requirements 변경 묶음을 먼저 정리하거나 별도 커밋으로 분리한 뒤 SURIT-002를 재검증/커밋해야 함.
### Next
- Human: 범위 밖 변경 정리 방식 최종 결정.
- Codex: 작업트리가 SURIT-002 scope만 남도록 정리된 뒤 `_resolve_ftype` 로직 리뷰, 회귀 테스트 리뷰, 커밋/푸시 재시도.
- Cowork: SURIT-HARNESS-PATCH-2 필요. 이번 턴부터 검증 통과 시 Codex가 git push까지 담당하는 워크플로우를 `AGENTS.md`, `CLAUDE.md`에 문서화.

## 2026-05-25 Codex HARNESS-GIT-PUBLISH
### Changed
- Updated `AGENTS.md` so Codex owns scoped Git staging, commit, and push when a task or the user asks to publish.
- Added a `Publish` section to the task template.
### Verified
- [x] Confirmed the new Codex Git publish responsibility appears in `AGENTS.md`.
- [x] Confirmed the task template includes the commit message format.
### Notes
- Existing SURIT working tree changes were not touched: `CLAUDE.md`, backend files, `PROGRESS.md`, the report markdown, and the tracked deletion of `새 텍스트 문서.txt`.
### Next
- Use task prompts that explicitly say whether Codex should publish after verification.

## 2026-05-25 03:30 Claude SURIT-002
### Changed
- `backend/pipeline/pdf_parser.py` — PDF 표 타입 분류 우선순위 보정
  - `_strong_header_ftype()` 신규 — 헤더가 `_FTYPE_KW` 키워드와 명확히 일치하는 강(强)신호만 분리 판정
  - `detect_file_type()` 리팩터(동작 보존) — 강신호 → 구조 휴리스틱(약신호) 2단 구조로 명시
  - `_detect_ftype_by_page_text()` — 섹션 표제어를 공백 제거 후 대조(줄바꿈·공백 견고성 보강)
  - `_resolve_ftype()` 신규 — 강신호 헤더 우선 → 약신호면 본문 섹션 신호 우선 → 둘 다 없으면 휴리스틱
  - `parse_single_pdf()` — 표 타입 결정을 `_resolve_ftype()` 호출로 교체
- `backend/tests/test_pdf_parser.py` — SURIT-002 회귀 테스트 6건 추가
- `.agent-harness/tasks/SURIT-002-prescription-pdf-misclassification.md` — 태스크 파일 신규 생성
### Verified
- [x] `cd backend && python -m pytest -q` — 97 passed (기존 91 + 신규 6)
- [x] `pdf_parser.py` 구문 검사(`ast.parse`) 통과
- [ ] npm lint/test/build — 해당 없음 (백엔드 전용 변경)
### Notes
- **1단계 진단 — 부분 보정됨 + 미흡.** 본문 텍스트 fallback(`_detect_ftype_by_page_text`)은 이미 존재했으나, `parse_single_pdf`가 `header_ftype != "unknown"`일 때만 헤더를 채택 → 헤더 OCR이 약신호로 *오분류*(예: 처방표 헤더가 detail 구조 휴리스틱에만 걸림)되면 본문의 "처방조제" 신호가 전혀 반영되지 않았다. 이것이 처방 PDF → 진료내역 오분류 경로. 미흡 판정 → 2단계 보정 진행.
- **변경 전/후 동작 차이:** 강신호 헤더(키워드 일치)는 종전대로 헤더 우선 — 정상 PDF는 동작 불변. 약신호 헤더(키워드 미일치·구조 휴리스틱 추정)일 때만, 본문 섹션 신호가 있으면 본문을 우선한다. `_resolve_ftype` docstring에도 명시.
- 작업 중 mnt 마운트 캐시 지연·부분동기화로 pytest 수집 오류(`ImportError`) 발생 → mnt 파일을 정본으로 재기록 + `__pycache__`/`.pytest_cache` 제거 후 재검증 통과. Windows 원본 무결 확인 완료.
- 테스트 리소스에 실제 처방 PDF 샘플이 없어 분류 결정 함수(`detect_file_type`·`_resolve_ftype`·`_detect_ftype_by_page_text`)를 합성 케이스 단위 테스트로 검증.
### Next
- Codex: SURIT-002 검증 — `cd backend && python -m pytest -q` 97개 재확인, `_resolve_ftype` 우선순위 로직 리뷰

## 2026-05-25 12:05 Codex SURIT-001
### Changed
- `backend/requirements.txt` 직접 수정 없음. Cowork SURIT-001 작업분 재검증만 수행.
- 로컬 현재 Python 환경이 일부 고정 버전과 달라 `python -m pip install -r backend/requirements.txt`로 현재 환경을 requirements 기준에 맞춤.
### Verified
- [x] `cd backend && python -m pytest -q` — 91 passed
- [x] `pip check` — No broken requirements found
- [x] 클린 임시 venv에서 `pip install -r backend/requirements.txt` 성공
- [x] 클린 임시 venv에서 `pip check` 성공
- [x] `backend/requirements.txt` 10줄 모두 `==` 고정 확인
- [x] 현재 로컬 Python 환경의 10개 직접 의존성 버전이 `backend/requirements.txt`와 일치함
- [x] Cowork 작업분 검증 결과: 이상 없음. 마운트 캐시 지연 이슈는 현재 파일 내용 기준 재현되지 않음
- [ ] npm lint/test/build — 해당 없음 (SURIT-001 backend deps 범위)
### Notes
- 검증 중 현재 로컬 Python 환경은 처음에 `fastapi`, `uvicorn`, `pandas`, `python-multipart`, `google-genai` 등이 고정값과 달랐음. 태스크 범위 내 보강으로 `python -m pip install -r backend/requirements.txt` 실행 후 재검증 완료.
- 범위 외 후보: pip 간접 의존성까지 완전 잠그려면 추후 별도 태스크로 `constraints.txt` 또는 lockfile 도입 검토.
### Next
- Human: 최종 검토 + SURIT-002 진행 여부 결정

## 2026-05-25 01:30 Claude SURIT-001
### Changed
- `backend/requirements.txt` — 미고정 의존성 전부 `==` 고정
  - 신규 고정(버전 지정 없던 항목): `fastapi==0.136.3`, `uvicorn==0.48.0`, `pdfplumber==0.11.9`, `pandas==2.3.3`, `python-multipart==0.0.29`, `google-genai==2.6.0`
  - `>=` → `==` 전환: `python-dotenv==1.2.2`, `slowapi==0.1.9`, `sentry-sdk[fastapi]==2.60.0`, `httpx==0.28.1`
- `.agent-harness/tasks/SURIT-001-backend-deps-pinning.md` — 태스크 파일 신규 생성
### Verified
- [x] `cd backend && python -m pytest -q` — 91 passed
- [x] 고정본 클린 설치(`pip install -r requirements.txt`) 성공 · `pip check` 대상 패키지 충돌 없음
- [ ] npm lint/test/build — 해당 없음 (백엔드 전용 변경)
### Notes
- Cowork 샌드박스에 프로젝트 전용 venv가 없어 `requirements.txt` 기준 신규 설치 후 `pip freeze` 결과로 버전 확정. 고정 버전은 2026-05-25 PyPI 최신 해결본 기준.
- 고정 도중 마운트 캐시 지연으로 파일이 일시적으로 잘려 보이는 현상 발생 → 재동기화 후 10줄 정상 확인 완료(원본 무결).
### Next
- Codex: SURIT-001 검증 — `requirements.txt` 고정본 리뷰 및 `cd backend && python -m pytest -q` 91개 재확인

## 2026-05-24 13:03 Claude SURIT-HARNESS-PATCH
### Changed
- CLAUDE.md 진입 지침 추가
- AGENTS.md 역할 분담 섹션 추가
- handoff.md 표준 포맷 주석 추가
- verify.md 점검 완료
### Verified
- 문서 패치만 수행, 빌드 검증 불필요
### Notes
- 다음 태스크부터 표준 포맷 적용
### Next
- Human: 첫 실전 태스크(SURIT-001) 선정

### 2026-05-24 Codex

Changed:

- Added the initial agent harness structure for SURIT.
- Added shared collaboration rules in `AGENTS.md`, linked with the existing `CLAUDE.md`.
- Removed obvious local cleanup targets: zero-byte temporary text files, ignored cache folders, and ignored `dist` build output.

Verified:

- Confirmed `.agent-harness/` files exist.
- Confirmed SURIT verification commands are recorded in `.agent-harness/verify.md`.

Remaining:

- The report file `SURIT_종합감사보고서_2026-05-20.md` was preserved because it contains content.
- `새 텍스트 문서.txt` was a zero-byte tracked file and now appears as a deletion in Git status.

## Template

### YYYY-MM-DD Agent

Changed:

- 

Verified:

- 

Remaining:

- 

# SURIT 진행 상황 (PROGRESS)

> 최종 업데이트: 2026-05-30 · 브랜치 `main` (origin 동기화 완료)
> 상세 감사 내역: `SURIT_종합감사보고서_2026-05-20.md`
> 운영 방식: Codex 단독 하네스 진행 (`AGENTS.md` 기준)

---

## ① 완료된 작업

### 종합 감사 — 2026-05-20
6개 역할군(준법·QA·보안·분석정확도·아키텍처·운영) 감사로 P0 9건 / P1 / P2 도출.
산출물: `SURIT_종합감사보고서_2026-05-20.md`.

### 메리츠 추천연도 + 메인 카피 — `a598e98`
메리츠 추천연도 입원일수 정확화, 메인 화면 카피를 KCD-9 중심으로 정리.

### P0 9건 — `a6b1c85`
출시 차단 이슈 일괄 수정.
- `filters._max_presc` SUM 버그 → MAX 일관화
- Supabase 토큰 인트로스펙션 인증 (`main.py`)
- 업로드 파일 크기·개수 제한 / Gemini 429 재시도
- 결과 화면 면책 박스 / 민감정보 처리 동의 게이트
- 분석 진행 표시(`AnalysisProgress`) / Q3 라벨 분리(10년 유지) / Footer·처리방침 플레이스홀더
- 변경: `filters.py` `main.py` `keywords.json` `pipeline/ai_judgment.py` `pipeline/result_builder.py` `src/pages/Disclosure.tsx` 외

### P1 1차 — `230b6d0`
Z·U코드 비질병 결정론 제외 / AI 의료판단 실패의 사용자 노출 / 서버측 분석 타임아웃 /
Sentry release 태깅 / Supabase 환경변수 가드 / 과장 카피 수정 / 오류 메시지 한국어화.

### detail 수술 감지 강화 — `7088aa4`
세부진료 수술 감지 로직 보강.

### CI 워크플로우 — `7763c3d`
`.github/workflows/ci.yml` — 필수 체크 워크플로우 추가.

### P1 2차 + _pharma_seen + 날짜 경계 — `96ea2bb`(백엔드) · `2e44db1`(프런트)
- 백엔드: CORS 운영 가드, PDF 매직바이트 검증, 메리츠 표현 완화
- 프런트: 접근성(ARIA·heading·탭 role·튜토리얼 dialog), 비밀번호 10자
- `_pharma_seen` 중복키에 병원명·투약일수 추가 (정상 처방 오스킵 방지)
- 날짜 창 경계 오프바이원 실측 검증(이상 없음 확인) + 회귀 테스트 `test_date_boundary.py` 신설

### P2 정리 5건 — `cba4fde`
1. 결과 사유 "확정" → "확인 / 진단 기록" 완화 (`filters.py` 14곳)
2. 빈 진료일자 행 누락 경고 (`pipeline/disease_aggregator.py`)
3. 빈/이미지 PDF 오류 메시지 구분 (`pipeline/pdf_parser.py` · `analyzer.py`)
4. 결과표 모바일 가로스크롤 (`src/pages/Disclosure.tsx` — `min-w-[680px]`)
5. 데드코드 19개 파일 삭제 (`analyzer_backup.py` + `components/disclosure/*` 트리, 약 2,700줄 제거)
- 신규/보강 테스트: `test_pdf_parser.py`, `test_date_boundary.py`

**검증 현황** — 백엔드 `pytest` 91개 통과 · 프런트 `tsc` (app/node) 통과.

---

## ② 진행 중 작업

없음 — 최신 코드 작업은 커밋·푸시 완료된 상태이며, 이후 작업은 Codex 단독 하네스로 진행.

### Codex 단독 운영 기준
- 새 작업은 `AGENTS.md` → 최신 `handoff.md` → task 파일 → `locks.md` → `git status` 순서로 시작한다.
- 구현, 테스트, handoff, scoped staging, commit, push까지 Codex가 한 흐름으로 처리한다.
- Human은 실제 배포 후 PDF 재테스트, 약관 해석, 사업자/정책 입력처럼 제품·운영 판단이 필요한 지점만 결정한다.
- 과거 Claude/Cowork 기록은 참조용 이력이며, 새 작업의 Next/Owner는 Codex 또는 Human만 사용한다.

---

## ③ 남은 백로그

### 우선 처리 후보
| 우선순위 | 항목 | 예상 | 비고 |
|---|---|---|---|
| P0 | 실제 PDF 배포 후 재테스트 | ~15분 | 오성심/박화자 PDF로 질염 14회, 간편 Q2, truncation_warning 상태 확인 |
| P1 | 투약 30일 기준 결정 | ~20분 | 현재는 처방 에피소드별 최대/계속 일수. 누적 30일 약관 기준이면 별도 구현 필요 |
| P1 | CI 기준 최신화 | ~30분 | 현재 로컬 검증 명령과 GitHub Actions가 동일한지 점검 |
| P2 | 테스트 태그/부분 실행 스크립트 | ~30분 | 문서 변경, 백엔드 변경, 프런트 변경별 빠른 검증 경로 명확화 |
| P2 | 실제 PDF 회귀 fixture 전략 | ~1~2시간 | 개인정보 제거/합성 fixture로 오성심·박화자급 사례를 자동화 |
| P3 | 운영 로그·헬스체크 정리 | ~30분 | Railway 장애 원인 추적 효율 개선 |

### 사용자 작업 (대시보드·정책)
| 우선순위 | 항목 | 비고 |
|---|---|---|
| 출시 전 필수 | Footer·개인정보처리방침·약관 사업자정보 입력 | 사업자 정보 필요 |
| P1 | GCP Gemini API 키 제한 | HTTP 리퍼러/IP 제한 |
| P1 | Supabase RLS 정책 검증 | 행 수준 보안 |
| P2 | 메리츠 룰 출처(약관명·개정일) 표기 | 보험업법 표시규제 소지 |

---

## ④ 다음 작업 추천

**실제 PDF 배포 후 재테스트**를 먼저 권장합니다.

최근 핵심 변경은 분석 정확도와 응답 시간에 직접 연결되어 있어, 로컬 테스트가 통과해도 운영 배포 환경에서 한 번 더 확인하는 편이 좋습니다. 확인 포인트는 다음 네 가지입니다.

- 오성심 PDF: 건강체 Q3에 급성질염(N76.0) 통원 14회 표시
- 오성심 PDF: 기침(R05) 통원 7회 유지
- 간편 탭 Q2: 10년 이내 입원·수술만 표시
- 박화자급 대용량 PDF: truncation_warning 없이 응답 완료

그다음은 **투약 30일 기준 결정**을 권장합니다. 현재 구현은 `_max_presc` 기준의 최대/계속 처방일수이며, 약관상 누적 투약일수라면 코드와 테스트를 별도 태스크로 보정해야 합니다.

## ⑤ Codex 단독 진행 효율 조언

- 작업 요청은 `태스크 목표 / 수정 허용 파일 / 검증 명령 / 커밋 메시지` 네 줄만 있어도 충분하다.
- PDF 재현 이슈는 가능하면 `PDF 이름 + 비밀번호 여부 + 기대 결과 + 현재 결과`를 함께 남긴다.
- 매번 전체 검증이 필요 없는 문서 작업은 `git diff --check` + 관련 문서 검색으로 빠르게 끝내고, 코드 변경 때만 pytest/tsc/build를 풀로 돌린다.
- 분석 정확도 변경은 최소 1개 이상의 회귀 테스트를 먼저 추가하거나 같이 추가한다.
- 배포 후 확인 항목은 handoff의 `Next: Human`에 짧게 남겨, 로컬 검증과 운영 검증을 분리한다.

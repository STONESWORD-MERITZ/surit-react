# SURIT 진행 상황 (PROGRESS)

> 최종 업데이트: 2026-05-24 · 브랜치 `main` (origin 동기화 완료)
> 상세 감사 내역: `SURIT_종합감사보고서_2026-05-20.md`

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

없음 — 모든 코드 작업이 커밋·푸시 완료된 상태.

---

## ③ 남은 백로그

### 코드 작업
| 우선순위 | 항목 | 예상 | 비고 |
|---|---|---|---|
| P1 | 백엔드 의존성 버전 고정 | ~15분 | `requirements.txt` 대부분 미고정 — 배포 재현성 위험 |
| P1 | 처방 PDF 오분류 보정 | ~30분 | 헤더 OCR 누락 시 페이지 텍스트 신호를 신뢰하도록 |
| P2 | 윤년 컷오프 보정 | ~30분 | 1825/3650일 고정 → 윤년 2~3일 누락. 모든 경계 이동, 의미상 결정 필요 |
| P2 | 초대용량 PDF 잘림 사용자 경고 | ~20분 | `filtered_lines`·30,000자 잘림이 무경고 |
| P3 | 날짜 창 로직 중앙화 | ~30분 | `filters`/`helpers` `_dts_in_range` 중복 제거 |
| P3 | `run_analysis` 함수 분해 | ~1~2시간 | 함수 과대 — 가독성·테스트성 |
| P3 | 깊은 헬스체크 / 구조화 로깅 | 각 ~30분 | 운영 관측성 |
| P3 | `main.py` 카카오 포맷 로직 → 파이프라인 이동 | ~30분 | 표현 로직 분리 |

### 사용자 작업 (대시보드·정책)
| 우선순위 | 항목 | 비고 |
|---|---|---|
| 출시 전 필수 | Footer·개인정보처리방침·약관 사업자정보 입력 | 사업자 정보 필요 |
| P1 | GCP Gemini API 키 제한 | HTTP 리퍼러/IP 제한 |
| P1 | Supabase RLS 정책 검증 | 행 수준 보안 |
| P2 | 메리츠 룰 출처(약관명·개정일) 표기 | 보험업법 표시규제 소지 |

---

## ④ 다음 작업 추천

**백엔드 의존성 버전 고정 (P1, ~15분)** 을 권장합니다.

현재 `requirements.txt`의 `fastapi`·`uvicorn`·`pdfplumber`·`pandas`·`google-genai`가
버전 미고정 상태라, 의존성 신규 릴리스 한 건으로 Railway 빌드가 깨질 수 있습니다.
출시 안정성에 직결되고 작업이 짧습니다 — 현재 설치 버전을 `==` 로 고정하면 됩니다.

그다음은 분석 정확도에 직결되는 **처방 PDF 오분류 보정**을 권장합니다.

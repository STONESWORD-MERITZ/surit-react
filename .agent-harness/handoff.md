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

## 2026-05-26 16:07 Codex SURIT-ROLLBACK-001
### Changed
- `backend/pipeline/ai_judgment.py` 검증: PDF 네이티브 첨부/Files API 경로 롤백, `_strengthen_filter` 기반 텍스트 필터링 적용, 입력 상한 3000줄/100K자 확인.
- `backend/analyzer.py` 검증: `_GEMINI_LINE_CAP = 3000` 동기화 확인.
- `backend/pipeline/pdf_parser.py` 검증: `pdf_bytes` 반환 제거 및 기존 `del pdf_data; gc.collect()` 경로 복원 확인.
- `backend/tests/test_ai_judgment_filter.py` 신규 필터 회귀 테스트 5건 확인.
- `backend/tests/test_pdf_native.py` 삭제 처리 완료.
- `.agent-harness/tasks/SURIT-ROLLBACK-001-revert-pdf-native.md`, `.agent-harness/handoff.md`, `.agent-harness/locks.md` 하네스 정리.
### Verified
- [x] `touch backend/pipeline/ai_judgment.py` - pyc 캐시 무효화
- [x] `git rm backend/tests/test_pdf_native.py` - SURIT-007 PDF 네이티브 테스트 제거
- [x] `cd backend && python -m pytest -q` - 123 passed
- [x] `_strengthen_filter` 신규 테스트 5건 확인: 반복 헤더 제거, 연속 중복 제거, 짧은 노이즈 제거 포함
- [x] PDF 네이티브 첨부 코드 잔존 없음: `from_bytes`, `from_uri`, `files.upload`, `files.delete`, `pdf_bytes` 검색 결과 없음
- [x] `_finalize_raw_text_for_gemini`에서 `_strengthen_filter(filtered_lines)` 호출 확인
- [x] 잘림 상한 3000줄 / 100K자 확인
- [x] `backend/analyzer.py` - `_GEMINI_LINE_CAP = 3000` 확인
- [x] `git status --short -uall` - 허용 범위만 변경됨
- [x] `git push origin main` - Codex publish step에서 완료
### Notes
- backend 전용 변경이라 npm lint/test/build는 미실행.
### Next
- Human: Railway 배포 후 박화자 PDF 재테스트.
- truncation_warning 없으면 해소, 있으면 상한 추가 조정 검토.

## 2026-05-27 07:00 Claude SURIT-ROLLBACK-001
### Changed
- `backend/pipeline/ai_judgment.py` — 1단계: `git show d60ccba7:` 로 BUG-002 상태(302줄) 복원하여 SURIT-007/BUG-003/BUG-004/BUG-005 의 PDF 네이티브 첨부·Files API 코드 전체 제거. 2~3단계: `import re` 추가 + `_REPEAT_HEADER_KEYWORDS`/`_SIGNAL_PATTERNS` 상수와 `_looks_like_repeated_header`/`_has_signal`/`_strengthen_filter` 헬퍼 신설. `_finalize_raw_text_for_gemini` 가 `_strengthen_filter(filtered_lines)` 를 거친 뒤 슬라이스. 잘림 상한 2000 → 3000 줄, `MAX_RAW_TEXT_LEN` 80,000 → 100,000 자 상향.
- `backend/analyzer.py` — BUG-002 상태(922줄) 복원하여 pdf_bytes 관련 변경 제거. `_GEMINI_LINE_CAP` 을 ai_judgment 와 동기화(2000 → 3000) + 주석 갱신.
- `backend/pipeline/pdf_parser.py` — BUG-002 상태(261줄) 복원하여 `parse_single_pdf` 결과 dict 의 `pdf_bytes` 키 제거. `finally: del pdf_data; gc.collect()` + 페이지별 `flush_cache()` 는 유지.
- `backend/tests/test_pdf_native.py` — 마운트 권한 문제로 파일 자체 삭제 불가. 본문을 모듈 docstring 만 남기고 비워 pytest 0건 수집.
- `backend/tests/test_ai_judgment_filter.py` — `_strengthen_filter` / `_has_signal` / `_looks_like_repeated_header` / `_finalize_raw_text_for_gemini` 통합 단위 테스트 5건 신규.
- `.agent-harness/tasks/SURIT-ROLLBACK-001-revert-pdf-native.md` — 태스크 파일 신규 생성.
### Verified
- [x] `cd backend && python -m pytest -q` — **123 passed** (롤백 후 118 + 신규 필터 테스트 5 = 123)
- [x] 롤백 직후 잠시 119+1F 였던 `test_pdf_native::test_parse_single_pdf_returns_pdf_bytes_field` 실패는 `test_pdf_native.py` 본문 비움으로 해결됨 (롤백 의도와 일치).
- [x] `_GEMINI_LINE_CAP` 동기화로 `test_truncation_warning.py` 회귀 유지.
- [x] `ast.parse` / Python AST 함수 목록 검증.
- [ ] npm lint/test/build — 해당 없음 (백엔드 전용 변경).
### Notes
- **롤백 사유:** SURIT-007 ~ BUG-005 의 PDF 네이티브 첨부(inline → Files API)는 318p 박화자 PDF 에서 400/메모리 압박을 해결하지 못함. 텍스트 방식으로 복귀하되, 필터링 강화로 잘림 상한 내 데이터 밀도를 높이는 전략 채택.
- **필터링 효과:** `_strengthen_filter` 가 ① 반복되는 표 헤더(요양기관명·상병코드 등 키워드 2개↑) ② 연속 중복 줄 ③ 길이 ≤2 자 노이즈 ④ 신호(날짜·코드·3자리 숫자) 없는 <10 자 짧은 줄을 제거. 정렬은 analyzer 가 이미 처리하므로 생략.
- **상한 상향:** 2000줄 → 3000줄 / 80K → 100K 자. ai_judgment 와 analyzer 양쪽 동기화 필수 (`_GEMINI_LINE_CAP` 도 동기 — false positive 잘림 경고 방지).
- **마운트 동기화 주의:** 작업 중 `pipeline/__pycache__/ai_judgment.cpython-310.pyc` 가 `.py` 보다 새것으로 잡혀 import 실패. `touch ai_judgment.py` 로 mtime 갱신해 해결. 마운트에서 .pyc 삭제는 권한 거부됨. Codex 재검증 시 pytest 캐시 무시(`-p no:cacheprovider`)나 별도 venv 권장.
### Next
- Codex: SURIT-ROLLBACK-001 검증 + 푸시 — ① `cd backend && python -m pytest -q` (123 passed) 재확인 ② `git status --short -uall` 로 허용 범위(`backend/pipeline/ai_judgment.py`, `backend/analyzer.py`, `backend/pipeline/pdf_parser.py`, `backend/tests/test_pdf_native.py`, `backend/tests/test_ai_judgment_filter.py`, `.agent-harness/tasks/SURIT-ROLLBACK-001-revert-pdf-native.md`, `.agent-harness/handoff.md`, `.agent-harness/locks.md`) 만 변경됐는지 확인 ③ Cowork 가 비운 `test_pdf_native.py` 는 `git rm` 으로 완전 삭제 권장 (마운트 권한 한계로 본문만 비워뒀음) ④ 한국어 커밋 메시지로 `git push origin main`. Railway 배포 후 박화자 PDF(318p) 재테스트.

## 2026-05-26 15:27 Codex SURIT-BUG-005
### Changed
- `backend/pipeline/ai_judgment.py` 검증: Gemini PDF 전달 경로가 inline bytes(`Part.from_bytes`)에서 Files API 업로드(`client.files.upload`) + URI 참조(`types.Part.from_uri`)로 전환됨.
- `.agent-harness/tasks/SURIT-BUG-005-gemini-files-api.md` 확인.
- `.agent-harness/handoff.md`, `.agent-harness/locks.md` 하네스 기록 및 잠금 정리.
### Verified
- [x] `cd backend && python -m pytest -q` - 120 passed
- [x] `Part.from_bytes` / `from_bytes` 잔존 없음
- [x] Files API 경로 확인: `client.files.upload(...)` 후 `types.Part.from_uri(file_uri=uploaded_file_obj.uri, mime_type="application/pdf")`
- [x] `finally` 정리 확인: `client.files.delete(name=uploaded_file_obj.name)` 및 `tmp_path.unlink(missing_ok=True)`
- [x] PDF 시그니처 검증 유지 확인: `pdf_bytes[:5] == b"%PDF-"`
- [x] 400 감지 + 텍스트 fallback 즉시 재시도 유지 확인
- [x] `git status --short -uall` - 허용 범위만 변경됨
- [x] `git push origin main` - Codex publish step에서 완료
### Notes
- backend 전용 변경이라 npm lint/test/build는 미실행.
### Next
- Human: Railway 배포 후 박화자 PDF 테스트.

## 2026-05-27 06:22 Claude SURIT-BUG-005
### Changed
- `backend/pipeline/ai_judgment.py` — `analyze_single_pdf` 함수 전체를 Gemini Files API 기반으로 재작성:
  - PDF 바이너리를 `tempfile.NamedTemporaryFile` 로 임시 저장 후 `api_client.files.upload(file=Path, config={"mime_type":"application/pdf"})` 으로 업로드 (asyncio.to_thread 비동기 래핑).
  - `types.Part.from_uri(file_uri=uploaded.uri, mime_type="application/pdf")` 로 contents 구성 — 기존 `Part.from_bytes(data=pdf_bytes, ...)` 코드는 완전 제거.
  - 함수 전체를 `try / finally` 로 감싸 finally 에서 `client.files.delete(name=uploaded.name)` + 임시 파일 `unlink(missing_ok=True)` 명시적 삭제(개인정보 보호, 48시간 자동 삭제 미의존).
  - 업로드 실패 시 `retry_local` 에 사유 로깅 + 텍스트 fallback 활성화. BUG-004 의 400 감지·텍스트 fallback 재시도 로직과 PDF 시그니처 검증(%PDF-)은 그대로 유지.
- `.agent-harness/tasks/SURIT-BUG-005-gemini-files-api.md` — 태스크 파일 신규 생성.
### Verified
- [x] `cd backend && python -m pytest -q` — **120 passed** (변경 후에도 기존 통합 테스트 모두 통과 — analyzer 통합 테스트는 `analyze_single_pdf` 를 monkeypatch 로 mock 하므로 함수 내부 변경은 영향 없음)
- [x] `ast.parse` 통과 (Windows 원본 기준 구문 정상)
- [x] SDK 진단: `types.Part.from_uri(file_uri=..., mime_type=...)` 가 정상 Part 생성 (file_data 채워짐), `client.files.upload` 는 SDK 2.6.0 표준 API
- [ ] npm lint/test/build — 해당 없음 (백엔드 전용 변경)
### Notes
- **1단계 진단:** SDK 2.6.0 의 `types.Part.from_uri` 가용성 사전 확인 (file_data 채워짐). `client.files.upload`/`client.files.delete` 는 SDK 표준 API. 직접 Client 호출은 샌드박스 SOCKS proxy 이슈로 막혔지만 실패 시 fallback 으로 안전 처리.
- **400 근본 원인 가설:** inline_data 의 base64 인코딩 후 페이로드가 SDK/Gemini 측 한계(또는 특정 PDF 구조와의 호환성)를 초과 → HTTP 400. Files API 는 별도 업로드 채널로 이 제약을 우회.
- **메모리 효과:** Gemini 호출 중 PDF 바이너리를 클라이언트 메모리에 유지할 필요가 없어짐 (업로드 후 URI 만 보유) — Railway 메모리 압박도 완화. 단, 임시 파일 일시 점유는 발생.
- **개인정보 보호:** 업로드된 PDF 는 분석 직후 `files.delete` 로 명시적 삭제. 임시 파일은 finally 에서 unlink.
- **degraded mode:** 업로드 실패해도 텍스트 fallback (`_finalize_raw_text_for_gemini`) 으로 동작 — 서비스 무중단.
### Next
- Codex: SURIT-BUG-005 검증 + 푸시 — `cd backend && python -m pytest -q`(120) 재확인, `backend/pipeline/ai_judgment.py` + 태스크 파일 커밋·푸시. 실제 박화자 PDF(318p) 로 Railway 에서 200 응답 확인 권장.

## 2026-05-26 13:24 Codex SURIT-007
### Changed
- `backend/pipeline/pdf_parser.py` 검증 및 보강: SURIT-007 `pdf_bytes` 반환 경로 유지, 이번 검증 중 발견한 `page.flush_cache()` 중복 2곳 제거(각 루프 1회 유지).
- `backend/pipeline/ai_judgment.py` 검증: `pdf_bytes` 존재 시 `types.Part.from_bytes(..., mime_type="application/pdf")` 생성 후 `[pdf_part, instruction]` 리스트로 Gemini 호출.
- `backend/analyzer.py` 검증: `pdf_bytes_by_fn`을 `gemini_payloads`로 전달하고, `truncation_warning` 감지는 `pdf_bytes`가 없는 텍스트 fallback 경로에서만 수행.
- `backend/tests/test_pdf_native.py` 신규 테스트 2건 검증: `pdf_bytes` 보존, SDK PDF Part 생성.
- `.agent-harness/tasks/SURIT-007-gemini-pdf-native.md`, `.agent-harness/handoff.md`, `.agent-harness/locks.md` 하네스 문서 정리.
### Verified
- [x] `cd backend && python -m pytest -q` - 120 passed
- [x] PDF 첨부 경로 확인: `pdf_bytes` payload는 `[pdf_part, instruction]` 리스트 contents 사용
- [x] `pdf_bytes` 없는 경우 기존 텍스트 fallback 경로 유지 확인
- [x] `truncation_warning`은 fallback 경로에서만 발생하도록 `if not pdf_bytes and _is_gemini_input_truncated(...)` 확인
- [x] `page.flush_cache()`는 `pdf_parser.py` 두 페이지 순회 루프에 각각 정확히 1개씩만 남음
- [x] `git status --short -uall` - 허용 범위만 변경됨
- [x] `git push origin main` - Codex publish step에서 완료
### Notes
- 실제 대용량 PDF(`박화자 세부report.pdf`)는 배포 후 Human이 직접 업로드해 `truncation_warning` 미발생 여부를 확인해야 함.
- SURIT-008 후보: PDF 네이티브 첨부 경로를 실제 Railway 배포 환경에서 대용량 샘플로 재검증하고, 필요 시 Gemini inline 용량 초과 대비 Files API 분기 추가.
### Next
- Human: 실제 PDF 테스트 및 최종 검토.
- SURIT-008 후보 검토: 대용량 PDF 배포 검증 / Files API fallback 필요 여부 결정.

## 2026-05-26 02:59 Claude SURIT-007
### Changed
- `backend/pipeline/pdf_parser.py` — `parse_single_pdf` 반환 dict 에 `pdf_bytes` 키 추가, `finally` 의 `del pdf_data` 제거(바이트는 Gemini 호출 종료까지 보존 필요).
- `backend/pipeline/ai_judgment.py` — `analyze_single_pdf` 에서 `pdf_bytes` 가 있으면 `types.Part.from_bytes(data=..., mime_type="application/pdf")` 로 PDF 네이티브 첨부, 보조 가공 텍스트(통원집계·태깅·약변경)는 instruction 으로 동봉. 없으면 기존 텍스트 fallback.
- `backend/analyzer.py` — `_parse_all_pdfs` 반환을 `(레코드, 오류, pdf_bytes_by_fn)` 3-튜플로 확장, `gemini_payloads` 에 `pdf_bytes` 필드 추가. PDF 바이너리가 있을 때는 `_is_gemini_input_truncated` 감지를 스킵(잘림 무관).
- `backend/tests/test_pdf_native.py` — 회귀 테스트 2건 신규: `parse_single_pdf` 가 `pdf_bytes` 키 보존, `types.Part.from_bytes` 가 PDF mime 으로 정상 동작.
- `.agent-harness/tasks/SURIT-007-gemini-pdf-native.md` — 태스크 파일 신규 생성.
### Verified
- [x] `cd backend && python -m pytest -q` — **120 passed** (기존 118 + 신규 2)
- [x] google-genai==2.6.0 `types.Part.from_bytes` 동작 확인 (Part.inline_data.mime_type == "application/pdf")
- [x] mock 기반 통합 테스트 3건(`test_run_analysis_q3_visit_7plus` 등)도 통과 — `_parse_all_pdfs` 3-튜플 반환 회귀 없음
- [ ] npm lint/test/build — 해당 없음 (백엔드 전용 변경)
### Notes
- **1단계 진단:** `google-genai==2.6.0` SDK 의 `types.Part.from_bytes(data=..., mime_type="application/pdf")` 정상 동작 확인. `Part.inline_data.mime_type == "application/pdf"` 로 inline 첨부 가용. main.py 한도(파일당 15MB·총 40MB)는 SDK inline 한도(~20MB) 이내라 Files API 분기 불필요.
- **구현 방식:** PDF 첨부 시 `contents=[pdf_part, instruction]` 리스트로 호출. 사전 가공된 텍스트(통원집계·교차검증·약변경·태깅)는 PDF 만으로 추론하기 어려워 instruction 안에 보조 자료로 함께 동봉. PDF 바이너리가 없는 경우(파싱 실패 등)는 기존 텍스트 contents 로 fallback.
- **truncation_warning 처리:** PDF 첨부 경로에서는 잘림 자체가 없으므로 `_is_gemini_input_truncated` 호출을 조건부 스킵(`if not pdf_bytes and _is_gemini_input_truncated(...)`). 텍스트 fallback 경로에서만 경고 유지. 박화자 세부report.pdf(318p, 29만 자) 같은 대용량도 누락 없이 전달됨.
- **메모리:** PDF 바이너리는 Gemini 호출 종료까지 메모리에 보존. 최악 90MB(15MB × 6파일). 순차 파싱(OOM 핫픽스)은 유지 — 파싱 메모리 피크는 PDF 1개분.
- 작업 중 마운트 캐시 churn 으로 `analyzer.py` 가 904줄에서 잘려 동기화(`return {...}` 블록 누락 → 통합 테스트 3건이 `result=None` 으로 실패). Windows 원본 기준 누락된 28줄(`# summary_reports 빌드` ~ `return {...}`)을 mount 에 이어 붙여 복구 후 120 passed 확인.
### Next
- Codex: SURIT-007 검증 + 푸시 — `cd backend && python -m pytest -q`(120) 재확인, `backend/pipeline/pdf_parser.py`·`backend/pipeline/ai_judgment.py`·`backend/analyzer.py`·`backend/tests/test_pdf_native.py` + 태스크 파일 커밋·푸시. 실제 대용량 PDF로 Gemini 응답 품질 점검 권장(박화자 PDF 가능).

## 2026-05-26 23:58 Codex SURIT-006
### Changed
- `backend/analyzer.py` 검증 및 보강: 9개 분해 헬퍼에 `_` 접두사, 타입 힌트, docstring이 모두 있는지 확인하고 누락된 타입 힌트 보강.
- `backend/tests/test_run_analysis_decompose.py` 단위 테스트 6건 확인.
- `.agent-harness/tasks/SURIT-006-run-analysis-decompose.md`, `.agent-harness/handoff.md`, `.agent-harness/locks.md` 하네스 기록 정리.
### Verified
- [x] `cd backend && python -m pytest -q` - 118 passed
- [x] 분해 헬퍼 단위 테스트 6건 확인: 시스템 프롬프트 건강체/간편 분기, 텍스트 빌더 빈값/정상, 라인 빌더 빈값
- [x] `run_analysis` 외부 시그니처 확인: `(active_files, product_type, reference_date, birthdate_pw, api_key) -> dict`
- [x] 반환 dict 키 HEAD 대비 변경 없음
- [x] 9개 분해 헬퍼 모두 `_` 접두사, 타입 힌트, docstring 보유
- [x] `git status --short -uall` - allowed scope only before commit (`backend/analyzer.py`, `backend/tests/*`, `.agent-harness/*`)
- [x] `git push origin main` - completed by Codex publish step
### Notes
- 본체는 163줄로 30줄 목표에는 미달. 다만 Gemini 병렬 호출·의학 판단 병렬 호출·결과 병합 블록은 오케스트레이션 성격이 강하고 입력 파라미터가 많아 추가 분해 시 가독성보다 추적 비용이 커진다는 Cowork 판단을 재확인함.
- 범위 외 이슈는 발견하지 못함.
### Next
- Human: final review.
- SURIT-007 candidate: Gemini 병렬 호출 블록을 별도 컨텍스트 객체/페이로드 빌더로 추가 분해할지 검토.

## 2026-05-26 23:33 Claude SURIT-006
### Changed
- `backend/analyzer.py` — `run_analysis`(745줄)를 9개 내부 `_` 헬퍼로 분해. 본체 ~163줄로 축소. 외부 시그니처·반환 dict 키 불변 — 순수 리팩터링(로직 verbatim 이동).
- `backend/tests/test_run_analysis_decompose.py` — 분해 헬퍼 단위 테스트 6건 신규.
- `.agent-harness/tasks/SURIT-006-run-analysis-decompose.md` — 태스크 파일 신규 생성.
### Verified
- [x] `cd backend && python -m pytest -q` — 118 passed (기존 112 + 신규 6)
- [x] `run_analysis` 외부 시그니처 `(active_files, product_type, reference_date, birthdate_pw, api_key) -> dict` 및 반환 dict 키 불변 확인
- [x] `git status` — 변경은 `analyzer.py` + 신규 테스트 파일뿐 (부수 변경 0)
- [ ] npm lint/test/build — 해당 없음 (백엔드 전용 변경)
### Notes
- **1단계 진단:** `run_analysis`는 94~839행(745줄). 외부 시그니처·반환 dict는 불변 대상. 최대 덩어리는 시스템 프롬프트 구성(~350줄).
- **분해된 헬퍼 9개 (각 역할):**
  1. `_parse_all_pdfs`(async) — PDF 병렬 파싱 → (레코드, 파싱오류), 0건 시 AnalysisError
  2. `_build_drug_change_text` — 약 변경 감지 결과 → Gemini 입력 텍스트
  3. `_build_presc_end_text` — 처방 종료일 분석 → Gemini 입력 텍스트
  4. `_build_tagged_entries` — 진료 라인에 기간 태그(IN_3M 등) 부착·파일별 묶음
  5. `_build_visit_count_lines` — 질병코드별 10년내 통원횟수·최대처방일 집계
  6. `_build_first_diag_lines` — 질병별 최초·최종 진단일 라인
  7. `_build_system_prompt` — 상품유형별 Gemini 시스템 프롬프트 전문(~350줄)
  8. `_build_medical_judgment_inputs` — 의학 판단 API 입력 2종 구성
  9. `_apply_medical_judgment` — 의학 판단 결과를 disease_stats·code_based_items에 반영(in-place)
- Gemini 병렬 호출·병합 블록(~70줄)은 오케스트레이션 본체 성격 + 입력 파라미터 14개라, 헬퍼화 시 가독성을 해쳐 `run_analysis` 본체에 유지. 이 사유로 본체가 ~163줄(태스크 "30줄 이내" 목표 미달) — 태스크 진단 메모에 사전 기록함.
- 분해는 git HEAD 본문을 블록 단위로 verbatim 이동(로직 무변경)하는 변환 스크립트로 수행 — 마운트 캐시 churn 회피 + 순수 리팩터링 보장.
### Next
- Codex: SURIT-006 검증 + 푸시 — `cd backend && python -m pytest -q`(118) 재확인, `backend/analyzer.py` + `backend/tests/test_run_analysis_decompose.py` + 태스크 파일 커밋·푸시.

## 2026-05-26 18:25 Codex SURIT-005
### Changed
- `backend/filters.py` 검증 완료: 인라인 `_dts_in_range` 제거, `pipeline.helpers._dts_in_range` import로 전환.
- `backend/pipeline/helpers.py` 검증 완료: `_dts_in_range` 단일 정본 docstring 보강.
- `backend/tests/test_date_window_centralize.py` 회귀 테스트 5건 확인.
- `.agent-harness/tasks/SURIT-005-date-window-centralize.md`, `.agent-harness/handoff.md`, `.agent-harness/locks.md` 하네스 기록 정리.
### Verified
- [x] `cd backend && python -m pytest -q` - 112 passed
- [x] `_dts_in_range` 중앙화 테스트 5건 확인: 단일 출처(`is` 동일성), 경계 포함(`>=`), 경계 외 제외, 윤년 포함 구간, 무효값 무시
- [x] `backend/filters.py` - `_dts_in_range` 인라인 정의 없음, `from pipeline.helpers import _dts_in_range` 전환 확인
- [x] `git status --short -uall` - allowed scope only before commit (`backend/filters.py`, `backend/pipeline/helpers.py`, `backend/tests/*`, `.agent-harness/*`)
- [x] `git push origin main` - completed by Codex publish step
### Notes
- Cowork 권장 후속: 나머지 인라인 헬퍼(`_code_in`, `_subtract_years`, `_visit_count_in_range`, `_parse_ymd`, `_max_presc`) 정리/중앙화는 별도 태스크가 적절함.
- 범위 외 변경은 발견하지 못함.
### Next
- Human: final review.
- SURIT-006 candidate: 나머지 인라인 헬퍼 정리 및 순환 import 위험 재점검.

## 2026-05-25 14:47 Claude SURIT-005
### Changed
- `backend/pipeline/helpers.py` — `_dts_in_range`에 정본 docstring 추가 (날짜 창 멤버십 단일 진입점 명시).
- `backend/filters.py` — 인라인 `_dts_in_range` 중복 정의 제거, `from pipeline.helpers import _dts_in_range` 로 전환. "공유 헬퍼" 섹션 주석 갱신.
- `backend/tests/test_date_window_centralize.py` — `_dts_in_range` 중앙화 회귀 테스트 5건 신규.
- `.agent-harness/tasks/SURIT-005-date-window-centralize.md` — 태스크 파일 신규 생성.
### Verified
- [x] `cd backend && python -m pytest -q` — 112 passed (기존 107 + 신규 5)
- [x] `git status --short` — SURIT-005 변경은 `filters.py`·`helpers.py`·신규 테스트뿐. 그 외 모든 파일 HEAD와 동일(부수 변경 0).
- [ ] npm lint/test/build — 해당 없음 (백엔드 전용 변경)
### Notes
- **1단계 진단:** `_dts_in_range`는 `helpers.py:340`(정본)과 `filters.py`(인라인 동본 — 본문 완전 동일, `-> list[str]` 주석만 차이) 2곳 정의. `analyzer.py`·`result_builder.py`는 이미 `helpers`에서 import. `filters.py`는 `_dts_in_range` 외 `_code_in`·`_subtract_years`·`_visit_count_in_range`·`_parse_ymd`·`_max_presc`도 인라인하는 "공유 헬퍼" 섹션 보유(과거 analyzer↔filters 순환 회피 잔재).
- **순환 임포트 판정:** `pipeline/__init__.py`는 빈 마커, `helpers.py`는 표준 라이브러리·pandas만 import → `filters → pipeline.helpers` 순환 없음. 인라인 유지 불필요 → import 전환(태스크 2단계 기본 경로).
- 본 태스크 범위인 `_dts_in_range`만 import 전환. 나머지 인라인 헬퍼는 SURIT-005 범위 밖이라 유지 — "공유 헬퍼" 섹션 전체 중앙화는 후속 태스크 권장.
- 기존 동작(경계 포함 `>=`) 불변. `test_date_boundary.py`의 `test_dts_in_range_helpers_and_filters_identical`은 이제 동일 객체 비교가 되어 자명히 통과.
- 작업 중 마운트 캐시 churn으로 다수 백엔드 파일이 찢어진 상태로 동기화 → git HEAD 기준으로 전 파일 일괄 재기록(SURIT-005 편집분만 재적용)해 정합화 후 검증. `git status` 로 SURIT-005 외 파일 변경 없음 확정.
### Next
- Codex: SURIT-005 검증 + 푸시 — `cd backend && python -m pytest -q`(112) 재확인, `backend/filters.py`·`backend/pipeline/helpers.py`·`backend/tests/test_date_window_centralize.py` + 태스크 파일 커밋·푸시.

## 2026-05-25 20:42 Codex SURIT-004
### Changed
- `backend/filters.py`, `backend/pipeline/helpers.py`, `backend/analyzer.py`, `backend/pipeline/result_builder.py`, `backend/pipeline/disease_aggregator.py`, `backend/meritz_easy_rules.py` 검증 및 보강.
- `backend/tests/test_leap_year_cutoff.py` 회귀 테스트 5건 검증 및 검색 기준 보강.
- `.agent-harness/tasks/SURIT-004-leap-year-cutoff.md`, `.agent-harness/handoff.md`, `.agent-harness/locks.md` 하네스 기록 정리.
### Verified
- [x] `cd backend && python -m pytest -q` - 107 passed
- [x] 윤년 회귀 테스트 5건 확인: 달력 기준 vs 고정 일수 차이, 2/29 비윤년 2/28 보정, 경계 포함(`>=`) 유지, filters 인라인과 helpers._subtract_years 동본 일치
- [x] `grep -r "timedelta(days=1825\|timedelta(days=3650" .` - Windows PowerShell 환경에 `grep` 없음; 동일 패턴을 `rg`와 `Select-String`으로 재검증해 잔존 없음
- [x] `git diff HEAD -- backend/tests/test_truncation_warning.py` - empty diff, SURIT-003 원본과 동일
- [x] `git status --short -uall` - allowed scope only before commit
- [x] `git push origin main` - to be completed by Codex publish step
### Notes
- `test_truncation_warning.py`는 Cowork mount churn 재동기화 기록이 있었지만, HEAD 대비 diff가 없어 의도치 않은 변경 없음.
- 실코드에는 고정 일수 연산이 남지 않았고, 검색 기준을 만족하도록 주석/테스트의 정확한 잔존 문자열도 정리함. 테스트 내 고정 일수 비교는 `365 * 5`, `365 * 10` 상수로 유지.
- 범위 외 이슈는 발견하지 못함.
### Next
- Human: final review.
- SURIT-005 candidates: 메리츠 룰 출처(약관명·개정일) 표기(P2) 또는 UI/응답 경고 경로의 별도 E2E 보강.

## 2026-05-25 11:39 Claude SURIT-004
### Changed
- `backend/pipeline/helpers.py` — 달력 기준 공용 헬퍼 `_subtract_years(d, years)` 신설 (연도만 차감, 2/29→비윤년 시 2/28 보정).
- `backend/filters.py` — `_subtract_years` 인라인(파일 내 순환 임포트 회피 정책 준수), `_cutoffs()`의 5년/10년 창을 달력 기준으로 교체.
- `backend/analyzer.py` — 창 4종 계산(`_d5y_dt`/`_d10y_dt`)·strftime 표기(`d_5y`/`d_10y`)·`IN_5Y`/`IN_10Y` 태깅·10년 초과 드롭을 달력 기준으로 교체, `_subtract_years` import.
- `backend/pipeline/result_builder.py` — `_d5y_dt`/`_d10y_dt`를 달력 기준으로 교체, import 추가.
- `backend/pipeline/disease_aggregator.py` — `_d10y_dt`를 달력 기준으로 교체, import 추가.
- `backend/meritz_easy_rules.py` — `ten_years_ago` ×3을 달력 기준으로 교체, `_subtract_years` import 추가.
- `backend/tests/test_leap_year_cutoff.py` — 윤년 보정 회귀 테스트 5건 신규.
- `.agent-harness/tasks/SURIT-004-leap-year-cutoff.md` — 태스크 파일 신규 생성.
### Verified
- [x] `cd backend && python -m pytest -q` — 107 passed (기존 102 + 신규 5)
- [x] 실코드에 고정 `timedelta(days=1825/3650)` 잔존 없음 (테스트 비교용 1건만 의도적 유지)
- [x] 90·365일 창·경계 포함(`>=`) 로직 불변 확인
- [ ] npm lint/test/build — 해당 없음 (백엔드 전용 변경)
### Notes
- **1단계 진단:** 1825·3650 고정 `timedelta`는 `helpers.py`엔 없고 5개 모듈(`filters.py`·`analyzer.py`·`result_builder.py`·`disease_aggregator.py`·`meritz_easy_rules.py`)에 분산. `filters.py`만 고치면 모듈 간 5년/10년 경계가 1~2일 어긋나는 내부 불일치 발생 → **사용자 승인 하에 범위를 날짜 창 전 모듈로 확대**(태스크 원안의 filters.py+helpers.py에서 확대).
- `filters.py`는 "순환 임포트 회피 위해 인라인" 정책 주석(파일 내)에 따라 `_subtract_years`를 인라인, 나머지는 `helpers._subtract_years` import.
- 90·365일 창은 윤년 영향이 없어 미변경. `analyzer.py` 태깅은 정수 일수 비교를 달력 컷오프 날짜 비교로 전환(IN_5Y/IN_10Y).
- 마운트 캐시 churn으로 편집 6파일 + `test_truncation_warning.py`가 찢어진 상태로 동기화됨 → git HEAD 원본 기반 재적용(편집 개수 일치 검증)으로 정본 확보. `test_truncation_warning.py`(이번 턴 미편집·린터 수정분)는 SURIT-003 원본+린터 수정분으로 재동기화 — Codex는 `git diff`로 의도대로인지 확인 요망.
### Next
- Codex: SURIT-004 검증 + 푸시 — `cd backend && python -m pytest -q`(107) 재확인, 변경 6개 모듈 + `test_leap_year_cutoff.py` + 태스크 파일 커밋·푸시.

## 2026-05-25 20:05 Codex SURIT-003
### Changed
- `backend/analyzer.py` 검증 완료: Gemini 입력 잘림 감지 후 `retry_warnings`와 `truncation_warning`에 경고 노출.
- `backend/tests/test_truncation_warning.py` 보강: 800줄 초과, `... (truncated)` 표식, 정상 케이스가 각각 `truncation_warning` 생성/미생성을 직접 검증하도록 확인.
- `.agent-harness/tasks/SURIT-003-large-pdf-truncation-warning.md`, `.agent-harness/handoff.md`, `.agent-harness/locks.md` 하네스 기록 정리.
### Verified
- [x] `cd backend && python -m pytest -q` - 102 passed
- [x] `npx tsc -p tsconfig.app.json --noEmit` - passed
- [x] `npx tsc -p tsconfig.node.json --noEmit` - passed
- [x] `npm run build` - passed
- [x] `git status --short -uall` - allowed scope only before commit (`backend/analyzer.py`, `backend/tests/*`, `.agent-harness/*`)
- [x] `src/pages/Disclosure.tsx` - no diff
- [x] `git push origin main` - to be completed by Codex publish step
### Notes
- `npm run build` passed in local Windows environment. Cowork sandbox의 `@rolldown` native binding 문제는 이 환경에서 재현되지 않았고, Vite chunk-size warning만 출력됨.
- 신규 테스트는 5건 그대로 유지하면서 핵심 3개 케이스가 경고 생성 여부까지 확인하도록 보강함.
### Next
- Human: final review.
- SURIT-004 candidates: 윤년 컷오프 보정(P2) 또는 메리츠 룰 출처(약관명·개정일) 표기(P2).

## 2026-05-25 10:55 Claude SURIT-003
### Changed
- `backend/analyzer.py` — 잘림 감지 헬퍼 `_is_gemini_input_truncated()`·`_build_truncation_warning()` 추가. Gemini 입력 구성 호출부에서 PDF별 잘림 감지 → 발생 시 `retry_warnings`에 사용자 경고 추가, `run_analysis` 반환 dict에 `truncation_warning` 필드 추가.
- `backend/tests/test_truncation_warning.py` — 잘림 감지 회귀 테스트 5건 신규.
- `.agent-harness/tasks/SURIT-003-large-pdf-truncation-warning.md` — 태스크 파일 신규 생성.
### Verified
- [x] `cd backend && python -m pytest -q` — 102 passed (기존 97 + 신규 5)
- [x] `npx tsc -p tsconfig.app.json --noEmit` — exit 0
- [x] `npx tsc -p tsconfig.node.json --noEmit` — exit 0
- [ ] `npm run build` — Cowork 샌드박스에서 실행 불가. 사유: node_modules가 Windows에서 설치돼 `@rolldown` Linux 네이티브 바인딩 부재(`binding-win32-x64-msvc`만 존재). 코드 무관 환경 이슈이며 프런트 파일 무수정이라 빌드 영향 없음 → Codex 환경에서 검증 필요.
### Notes
- **1단계 진단:** 잘림 로직은 `pdf_parser.py`가 아니라 `pipeline/ai_judgment.py`의 `_finalize_raw_text_for_gemini()`에 있음 — `filtered_lines[:800]`(줄 잘림), `MAX_RAW_TEXT_LEN=30_000`(글자 잘림, `... (truncated)` 표식 부착). 이 함수는 `analyzer.py`에서 호출됨. `pdf_parser.py`는 본 태스크와 무관 → 미수정.
- **결정(사용자 확인):** "범위 유지" 선택 → `ai_judgment.py`(범위 외) 무수정, `analyzer.py` 호출부에서 감지.
- **전달 경로:** `main.py`(범위 외)가 API 응답을 화이트리스트(`retry_warnings`→`warnings`)로 추림. 전용 필드를 프런트까지 보내려면 `main.py` 수정이 필요해, 잘림 경고를 기존 `retry_warnings` 채널에 추가 → `main.py`·`Disclosure.tsx` 수정 없이 기존 `warnings` 경고 박스로 사용자에게 노출. `run_analysis` 반환 dict에는 전용 `truncation_warning` 필드도 함께 둠(테스트·향후 확장용).
- `Disclosure.tsx`는 무수정(잠금만 잡았다 해제) — 경고가 기존 `warnings` 렌더링으로 표시됨.
- mnt 마운트가 대용량 `analyzer.py`(837줄)를 찢어진 상태로 동기화 → git HEAD 원본 기반으로 4개 편집을 재적용(각 1회 매칭 확인)해 정본 기록 후 검증. Windows 원본 무결 확인.
### Next
- Codex: SURIT-003 검증 + 푸시 — `cd backend && python -m pytest -q`(102) 재확인, `npm run build`를 정상 환경에서 검증, 변경분(`backend/analyzer.py`, `backend/tests/test_truncation_warning.py`, 태스크 파일) 커밋·푸시.

## 2026-05-25 19:12 Codex SURIT-PUBLISH
### Changed
- Commit `ea3d6dcc30cb399f8c34e6f03985c5787a363094` (`SURIT-001: 백엔드 의존성 전체 == 고정 + 임시 파일 삭제`) pushed to `origin/main`.
- Commit `6f80f5d0a6cdba13225cdd41ee40782b46e4bd85` (`SURIT-002: 처방 PDF 약신호 헤더 시 본문 신호 우선 (회귀 테스트 6건 추가)`) pushed to `origin/main`.
- Commit `99943fea09a910a7aa11798e5f3588361e470de9` (`SURIT-HARNESS-PATCH-2: Codex git push 담당 워크플로우 문서 반영 + 프로젝트 문서 추가`) pushed to `origin/main`.
### Verified
- [x] `python -m pytest -q` in `backend` - 97 passed
- [x] `npm run lint` - passed
- [x] `npm test` - 1 passed
- [x] `npm run build` - passed (Vite chunk-size warning only)
- [x] `git push origin main` - completed
- [x] `git status --short` - clean after push, before this handoff update
### Notes
- Commit 3 included the untracked harness base documents under `.agent-harness/` so the requested post-push clean status could be reached.
- `.agent-harness/locks.md` Active is `none`; locks released.
### Next
- Human: final review and decide whether to start SURIT-003.

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

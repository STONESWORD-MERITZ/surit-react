# SURIT-007: Gemini PDF 네이티브 첨부 전환

## 목적
현재 pdfplumber 텍스트 추출 → 잘림 → Gemini 텍스트 전달 방식을
PDF 바이너리를 Gemini에 직접 첨부하는 방식으로 전환한다.
318페이지 대용량 PDF도 누락 없이 전체 분석이 가능해진다.

## 배경
- 박화자 세부report.pdf: 318페이지, 약 29만 자
- 현행 상한(2000줄/80K자): 51페이지에서 잘림 → 84% 누락
- 정확도 최우선 원칙에 따라 근본 해결 필요

## 우선순위
P1 (정확도 직결)

## 예상 소요
~2~3시간

## Owner
Cowork

## 범위 (수정 허용 파일)
- backend/pipeline/ai_judgment.py (Gemini 호출 방식 전환 핵심)
- backend/pipeline/pdf_parser.py (PDF 바이너리 경로 반환 추가)
- backend/analyzer.py (파이프라인 연결 수정)
- backend/tests/ (회귀 테스트 보강)

## 범위 외
- 프런트 코드 일체
- main.py (업로드 처리 로직 무변경)
- filters.py, result_builder.py 등

## 작업 절차
### 1단계: 현재 구조 진단
1. ai_judgment.py의 Gemini 호출부 확인:
   - 현재 텍스트를 어떻게 전달하는지
   - google-genai SDK의 PDF 첨부 방식 확인
     (types.Part.from_bytes 또는 types.File 업로드 방식)
2. pdf_parser.py에서 PDF 파일 경로/바이너리 접근 가능 여부 확인
3. analyzer.py의 파이프라인 흐름 확인
4. 진단 결과 handoff Notes에 기록

### 2단계: 구현
#### ai_judgment.py
- Gemini 호출 시 텍스트 대신 PDF 바이너리 첨부로 전환
- google-genai SDK 방식:
```python
  types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
```
- 텍스트 추출 기반 입력은 PDF 첨부가 불가능한 경우 fallback으로 유지
- truncation_warning 로직 제거 (잘림 자체가 없어지므로)
- _GEMINI_LINE_CAP, MAX_RAW_TEXT_LEN 상수 제거 또는 fallback용으로만 유지

#### pdf_parser.py
- parse_single_pdf가 PDF 바이너리(bytes)도 함께 반환하도록 수정
- 기존 텍스트 추출 로직은 fallback용으로 유지

#### analyzer.py
- _parse_all_pdfs에서 PDF 바이너리를 ai_judgment로 전달
- truncation_warning 감지 로직 제거 또는 조건부 처리

### 3단계: 검증
- cd backend && python -m pytest -q (118 passed 유지)
- PDF 네이티브 첨부 경로 단위 테스트 추가
- truncation_warning 관련 테스트 조건부 처리

## 완료 조건
- 대용량 PDF도 전체 내용이 Gemini에 전달됨
- truncation_warning 미발생
- pytest 전체 통과
- handoff.md 표준 포맷 기록
- Next: Codex 검증 + 푸시
- locks.md 잠금 해제

## 비고
- google-genai SDK 버전 확인 필수 (requirements.txt 기준)
- Railway 메모리 한도 내에서 PDF 바이너리 처리 가능한지 확인
  (박화자 세부report.pdf 2.69MB 기준)
- Gemini File API(대용량) vs inline bytes(소용량) 분기 필요 시 구현
  · 일반적으로 20MB 이하는 inline bytes로 처리 가능

## 진단 메모 (1단계 결과)
- **SDK 지원 확인:** `google-genai==2.6.0`(requirements.txt 고정본)에서
  `types.Part.from_bytes(data=..., mime_type="application/pdf")` 정상 동작.
  결과 `Part` 객체에 `inline_data` 속성 포함 → inline bytes 첨부 방식 가용.
- **첨부 분기:** main.py 한도(파일당 15MB·총 40MB)는 SDK inline 한도(~20MB)
  이내 → Files API 분기 불필요, 항상 inline bytes로 처리.
- **현재 호출 위치 (ai_judgment.py):**
  - `analyze_single_pdf` (line ~218): `contents = f"고객 기준일: ...\n진료 데이터:\n{raw_text}"`
    → 리스트 `[pdf_part, instruction_text]`로 전환.
  - `_finalize_raw_text_for_gemini`: 사전 가공된 텍스트(통원집계·교차검증·약변경·태깅 진료라인)는
    PDF에서 즉시 추론하기 어려운 가공 메타데이터라, PDF와 함께 **보조 자료로 동봉 유지** 권장.
- **현재 PDF 바이너리 흐름 (pdf_parser.py):**
  - `parse_single_pdf` (line 200): `pdf_data = uploaded_file.read()` 후
    `finally: del pdf_data; gc.collect()`로 폐기. 결과 dict는 `records`·`parse_errors`만.
    → 반환 dict에 `pdf_bytes` 필드 추가, finally 의 `del` 제거.
- **analyzer.py 파이프라인:**
  - `_parse_all_pdfs` → run_analysis 본체의 `gemini_payloads` 빌드 → `analyze_single_pdf`
  - `pdf_bytes_by_fn` 사전을 `_parse_all_pdfs`에서 누적·반환, `gemini_payloads`에서
    각 페이로드의 `pdf_bytes`로 첨부, `analyze_single_pdf`에서 PDF 분기.
- **truncation_warning:** PDF 첨부 시 원본 전체가 전달되므로 잘림이 의미 없음 →
  `_is_gemini_input_truncated` 호출 자체를 조건부 비활성화(텍스트 fallback 시에만 유지).

## 구현 설계 (2단계 상세)
1. `parse_single_pdf` 반환 dict에 `pdf_bytes` 키 추가. 메모리 누수 방지 위해
   `del pdf_data`만 제거하고 `gc.collect()`는 유지.
2. `_parse_all_pdfs` 반환을 `(all_records, parse_errors, pdf_bytes_by_fn)`로 확장.
3. `run_analysis` 본체에서 `gemini_payloads` 빌드 시 `pdf_bytes` 필드 동봉.
   truncation_warning 감지는 `pdf_bytes` 존재 시 스킵.
4. `analyze_single_pdf`에서 `parsed_data.get("pdf_bytes")` 확인 → PDF Part + 보조 텍스트
   리스트로 호출, fallback은 기존 텍스트 경로 유지.
5. 회귀 테스트: PDF Part 페이로드 빌드 단위 테스트, fallback 경로 테스트.

## 메모리·성능 고려
- 파일당 15MB × 6개 = 최대 90MB 바이너리 동시 보존(Gemini 호출 종료까지).
- 순차 파싱(OOM 핫픽스)은 유지 — 바이너리 보존 단계는 변경.
- Gemini 호출은 PDF별 병렬 → Google 서버에서 처리되므로 클라이언트 메모리는 바이너리 + 응답만.

# SURIT-BUG-005: Gemini Files API 전환

## 목적
inline bytes 방식(Part.from_bytes)이 400 Bad Request를 유발하는
근본 원인(inline 크기 제한)을 해결한다.
PDF를 Gemini Files API로 먼저 업로드한 후 URI로 참조하는 방식으로 전환.
318페이지 대용량 PDF도 누락 없이 100% 전달 가능.

## 우선순위
P0 (서비스 오류 직결)

## 예상 소요
~1시간

## Owner
Cowork

## 범위 (수정 허용 파일)
- backend/pipeline/ai_judgment.py
- backend/tests/

## 범위 외
- 프런트 코드 일체
- main.py, analyzer.py, pdf_parser.py 등

## 작업 절차
### 1단계: 현재 코드 진단
1. ai_judgment.py의 현재 PDF 첨부 방식 확인
   - Part.from_bytes 호출 위치
   - BUG-004 fallback 로직 위치
2. google-genai 2.6.0 SDK에서 Files API 지원 확인
   - client.files.upload() 메서드 존재 여부
   - types.Part.from_uri() 지원 여부
3. 진단 결과 handoff Notes에 기록

### 2단계: Files API 전환 구현
analyze_single_pdf 함수에서:
1. PDF를 임시 파일로 저장 후 Files API 업로드
2. Gemini 호출 완료 후 업로드 파일 + 임시 파일 삭제 (finally)
3. 업로드 실패 시 텍스트 fallback 유지
4. 기존 Part.from_bytes 코드 제거
5. PDF 시그니처 검증(%PDF-) 유지

### 3단계: 회귀 테스트
- Files API 업로드 경로 mock 테스트 추가
- 기존 120개 테스트 전부 통과 유지

## 검증 명령
cd backend && python -m pytest -q ← 120개 + 신규 통과

## 수동 확인 체크리스트
- [ ] Part.from_bytes 코드 잔존하지 않는가
- [ ] 임시 파일 finally 삭제 확인
- [ ] 업로드 파일 Gemini 측 삭제 확인
- [ ] fallback 경로 유지 확인

## 완료 조건
- Files API 전환 완료
- pytest 전체 통과 (120 + 신규)
- handoff.md 표준 포맷 기록
- Next: Codex 검증 + 푸시
- locks.md 잠금 해제

## 비고
- Files API 업로드된 파일은 48시간 후 자동 삭제되나
  분석 완료 즉시 명시적 삭제 권장 (개인정보 보호)
- 업로드 실패 시 fallback이 작동하므로
  서비스 중단 없이 degraded mode로 동작

## 진단 메모 (1단계 결과)
- **SDK 지원 확인:** `google-genai==2.6.0`(requirements.txt 고정본).
  - `types.Part.from_uri(file_uri=..., mime_type=...)` 정상 동작 — `Part.file_data` 채워짐 확인.
  - `client.files.upload(file=Path, config={"mime_type":"application/pdf"})` — SDK 2.6.0 표준
    API. Client 인스턴스 생성은 샌드박스 SOCKS proxy 이슈로 직접 호출 검증은 불가했으나
    SDK 소스 기준 가용. 실패 시 fallback 으로 안전.
  - `client.files.delete(name=...)` — 업로드 후 명시적 삭제용. 마찬가지로 SDK 표준.
- **현재 PDF 첨부 코드 (ai_judgment.py analyze_single_pdf):**
  - line 218~339, 약 122줄.
  - `pdf_bytes` 추출(224) + 시그니처 검증(BUG-004, 227~230).
  - `_build_contents(use_pdf)` 헬퍼(250~260) 안에서 `types.Part.from_bytes(data=pdf_bytes, ...)`
    로 inline_data 채움. 텍스트도 `Part.from_text` 로 Part 통일.
  - retry 루프 내 400 감지 → 텍스트 fallback 즉시 재시도(BUG-004, 311~318).
- **변경 방향:**
  - `Part.from_bytes` 제거, 함수 시작 부분에서 PDF 를 `tempfile.NamedTemporaryFile` 로
    임시 저장 후 `client.files.upload` 비동기 호출 (asyncio.to_thread).
  - 업로드 결과의 `.uri` 를 `Part.from_uri` 에 넘겨 contents 구성.
  - 함수 전체를 `try / finally` 로 감싸 finally 에서 `client.files.delete(name=...)`
    + 임시 파일 `unlink(missing_ok=True)` 보장.
  - 업로드 실패는 `retry_local` 로그 + 텍스트 fallback (BUG-004 의 400 fallback 로직 유지).

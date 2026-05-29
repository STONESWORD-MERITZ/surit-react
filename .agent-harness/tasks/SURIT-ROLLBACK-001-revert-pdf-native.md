# SURIT-ROLLBACK-001: PDF 네이티브 첨부 롤백 + 텍스트 필터링 강화

## 목적
SURIT-007 ~ BUG-005(PDF 네이티브 첨부 시도)를 롤백하고
텍스트 방식으로 복귀한다. 동시에 텍스트 필터링을 강화해
318페이지 PDF에서도 유효 진료 데이터를 최대한 커버한다.

## 롤백 대상 커밋
- 7769951 SURIT-007 PDF 네이티브 첨부
- 578cbf7 BUG-003 Part.from_text 수정
- 7505402 BUG-004 400 로깅 + fallback
- 9f21e63 BUG-005 Files API 전환

## 롤백 기준점
BUG-002 상태 (텍스트 방식 + 잘림 상한 2000줄/80K자)
커밋: d60ccba7

## 작업 절차
### 1단계: 롤백
git show 또는 git checkout 으로 아래 파일을 BUG-002(d60ccba) 상태로 복원:
- backend/pipeline/ai_judgment.py
- backend/analyzer.py (pdf_bytes 관련 변경 제거)
- backend/pipeline/pdf_parser.py (pdf_bytes 반환 제거 — BUG-002 시점)
- backend/tests/test_pdf_native.py 삭제 (SURIT-007 신규)

rollback 후 pytest 120 passed → 118 passed로 줄어드는 것 확인

### 2단계: 텍스트 필터링 강화
ai_judgment.py 의 _finalize_raw_text_for_gemini() 에서:
1. 반복 헤더 제거 (요양기관명·상병코드·진료시작일 등 키워드 2개↑ 포함 줄)
2. 연속 중복 줄 제거
3. 노이즈 줄 제거 (숫자·날짜·코드 패턴 전혀 없는 짧은 텍스트)
4. (정렬은 analyzer 가 이미 시간 역순 비슷하게 넘기므로 별도 정렬 안 함)

### 3단계: 잘림 상한 조정
- filtered_lines 상한 2000 → 3000
- MAX_RAW_TEXT_LEN 80,000 → 100,000
- analyzer._GEMINI_LINE_CAP 도 동기화 (false positive 경고 방지)

### 4단계: 회귀 테스트
- 기존 118개 전부 통과 확인
- _strengthen_filter 단위 테스트 1~3건 추가

## 검증 명령
cd backend && python -m pytest -q

## 완료 조건
- PDF 네이티브 첨부 코드 완전 제거
- 텍스트 필터링 강화 적용
- pytest 전체 통과
- handoff.md 표준 포맷 기록
- Next: Codex 단독 검증·푸시
- locks.md 잠금 해제

## 진단 메모 (1단계 확인)
- git log 확인: d60ccba7 = BUG-002, 그 이후 SURIT-007/BUG-003/4/5 가 PDF 네이티브 첨부 4단계 커밋.
- BUG-002 시점 변경 파일: `analyzer.py` + `pipeline/ai_judgment.py` (pdf_parser.py 는 BUG-001 까지만 변경됨).
- 롤백 방식: `git show d60ccba7:<file>` 출력을 작업 트리에 덮어쓰기 (3 파일).
- pdf_parser.py 도 BUG-002 시점 상태로 복원 (SURIT-007 의 `pdf_bytes` 필드 추가 제거).
- test_pdf_native.py 는 SURIT-007 (7769951) 에서 추가됐으므로 삭제.

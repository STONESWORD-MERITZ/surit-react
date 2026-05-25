# SURIT-003: 초대용량 PDF 잘림 사용자 경고

## 목적
현재 pdf_parser.py의 filtered_lines·30,000자 잘림이 무경고으로 처리된다.
사용자가 분석 결과가 불완전할 수 있다는 사실을 모른 채 결과를 신뢰하는 위험을 제거한다.
잘림 발생 시 사용자에게 명확한 경고를 노출한다.

## 우선순위
P2

## 예상 소요
~20분

## Owner
Cowork (백엔드 파이프라인 + 프런트 경고 표시)

## 범위 (수정 허용 파일)
- backend/pipeline/pdf_parser.py (잘림 감지 + 플래그 반환)
- backend/analyzer.py (플래그 전달, 필요 시)
- src/pages/Disclosure.tsx (경고 UI 표시, 필요 시)
- backend/tests/ (회귀 테스트 추가)

## 범위 외
- 기타 백엔드 모듈, 프런트 컴포넌트 일체

## 작업 절차
### 1단계: 현재 상태 진단
1. pdf_parser.py에서 filtered_lines·30,000자 잘림 로직 위치 확인
2. 잘림 발생 여부를 호출부(analyzer.py)에 전달하는 경로가 있는지 확인
3. 프런트(Disclosure.tsx)에서 경고를 표시할 수 있는 필드가 응답에 있는지 확인
4. 진단 결과를 handoff.md Notes에 기록

### 2단계: 백엔드 — 잘림 감지 + 플래그
1. 잘림 발생 시 truncated: true 또는 truncation_warning: str 필드를 반환
2. analyzer.py가 해당 플래그를 결과에 포함하도록 전달
3. 기존 잘림 로직(30,000자 상한)은 변경하지 않음 — 감지·경고만 추가

### 3단계: 프런트 — 경고 UI
1. 응답에 truncation_warning 있을 때 Disclosure.tsx에 경고 박스 표시
   - 예: "PDF 용량이 커서 일부 내용이 분석에서 제외됐을 수 있습니다."
   - 기존 면책 박스 스타일과 통일
2. 경고 없을 때는 UI 변화 없음

### 4단계: 회귀 테스트
- 잘림 발생 케이스 → truncation_warning 필드 포함 확인
- 잘림 없는 케이스 → 필드 없음 또는 null 확인
- 기존 97개 테스트 전부 통과 유지

## 검증 명령
cd backend && python -m pytest -q   ← 97개 + 신규 통과
npx tsc -p tsconfig.app.json --noEmit
npm run build

## 수동 확인 체크리스트
- [ ] 잘림 발생 시 경고 박스가 화면에 표시되는가
- [ ] 잘림 없을 때 경고 박스가 표시되지 않는가
- [ ] 기존 분석 결과 표시에 회귀 없는가

## 완료 조건
- 잘림 감지 + 경고 UI 동작
- pytest 전체 통과 (97 + 신규)
- tsc + build 통과
- handoff.md 표준 포맷 기록
- Next: Codex 검증 + 푸시
- locks.md 잠금 해제

## 진단 메모 (1단계 결과)
- 잘림 로직은 `pdf_parser.py`가 아니라 `pipeline/ai_judgment.py`의
  `_finalize_raw_text_for_gemini()`에 있다 — `filtered_lines[:800]`(줄 잘림),
  `MAX_RAW_TEXT_LEN = 30_000`(글자 잘림, 표식 `... (truncated)` 부착).
- 이 함수는 `analyzer.py` 호출부에서 호출되므로, 범위 내(`analyzer.py`)
  호출부에서 잘림을 감지한다. `ai_judgment.py`는 수정하지 않는다.
- 따라서 본 태스크에서 `pdf_parser.py`는 수정 대상이 아니다.

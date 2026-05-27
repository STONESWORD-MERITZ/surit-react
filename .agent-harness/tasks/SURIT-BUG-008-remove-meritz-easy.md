# SURIT-BUG-008: 메리츠 간편심사 완전 제거

## 목적
메리츠 간편심사 판단 로직을 백엔드·프런트 전체에서 완전 제거한다.
- Gemini 3번째 호출(~119초) 제거 → 전체 소요 ~170초로 단축
- truncation_warning 해소 (처리량 감소로 상한 여유 확보)
- 향후 회사별 기준 추가 시 새로 구현

## 우선순위
P0 (신뢰도·성능 직결)

## 예상 소요
~1~2시간

## Owner
Cowork

## 범위 (수정 허용 파일)
### 백엔드
- backend/pipeline/ai_judgment.py (간편 Gemini 호출 제거)
- backend/analyzer.py (간편 판단 흐름 제거)
- backend/filters.py (간편 필터 제거)
- backend/meritz_easy_rules.py (파일 전체 삭제)
- backend/pipeline/result_builder.py (간편 결과 빌드 제거)
- backend/keywords.json (간편 관련 키워드 제거)
- backend/tests/ (관련 테스트 제거 또는 수정)
### 프런트
- src/pages/Disclosure.tsx
  (메리츠 간편 결과 섹션·간편심사 고지 건수·추천 연도 UI 제거)

## 범위 외
- main.py (API 시그니처 변경 최소화)
- 기타 파일

## 작업 절차
### 1단계: 현재 상태 진단
1. 메리츠 간편 관련 코드 전수 확인:
   - ai_judgment.py: 간편 Gemini 호출 위치
   - analyzer.py: 간편 판단 흐름 위치
   - filters.py: 간편 필터 함수 목록
   - result_builder.py: 간편 결과 빌드 위치
   - Disclosure.tsx: 간편 결과 표시 UI 위치
2. 제거 시 영향받는 반환값 키 목록 확인
   (main.py API 응답에서 간편 관련 키 확인)
3. 진단 결과 handoff Notes에 기록

### 2단계: 백엔드 제거
1. ai_judgment.py — 간편 Gemini 호출 함수·호출부 제거
2. analyzer.py — 간편 판단 흐름 제거
3. filters.py — 간편 필터 함수 제거
   (건강체 필터는 유지)
4. meritz_easy_rules.py — 파일 삭제
5. result_builder.py — 간편 결과 빌드 제거
6. keywords.json — 간편 관련 항목 제거
7. 관련 테스트 제거 또는 수정

### 3단계: 프런트 제거
Disclosure.tsx에서:
1. 메리츠 간편 결과 섹션 제거
2. 간편심사 고지 건수 카드 제거
3. 메리츠 추천 연도 표시 제거
4. 관련 타입·상태 변수 제거

### 4단계: 검증
- cd backend && python -m pytest -q
- npx tsc -p tsconfig.app.json --noEmit
- npm run build

## 완료 조건
- 메리츠 간편 관련 코드 잔존 없음
- meritz_easy_rules.py 삭제됨
- pytest 전체 통과
- tsc + build 통과
- handoff.md 표준 포맷 기록
- Next: Codex 검증 + 푸시
- locks.md 잠금 해제

## 비고
- 건강체 판단 로직은 유지
- main.py API 응답 구조 변경 최소화
  (프런트가 없는 키를 무시하도록 처리)
- 제거된 테스트 목록을 handoff에 명시

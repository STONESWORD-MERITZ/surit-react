# SURIT-VERIFY-001: AI 판단 프롬프트 안정화

## 목적
동일한 PDF로 반복 분석 시 AI 판단 결과가
매번 달라지는 현상을 최소화한다.
결정론 룰(filters.py)은 항상 동일 → 유지.
AI 판단(ai_judgment.py)은 확률적 → 프롬프트 안정화로 일관성 향상.

## 우선순위
P1 (신뢰도 직결)

## 예상 소요
~1시간

## Owner
Codex

## 범위
- backend/pipeline/ai_judgment.py (프롬프트 + 호출 파라미터)
- backend/tests/ (일관성 회귀 테스트 추가)

## 범위 외
- filters.py (결정론 영역 — 수정 불필요)
- analyzer.py, main.py 등

## 작업 절차
### 1단계: 현재 불안정 원인 진단
1. ai_judgment.py의 Gemini 호출 파라미터 확인:
   - temperature 설정 여부 (미설정 시 기본값 사용 → 불안정)
   - top_p, top_k 설정 여부
2. 시스템 프롬프트에 모호한 지시 여부 확인:
   - "판단하라" 같은 열린 지시 → 구체적 기준으로 교체 필요
   - 출력 형식이 엄격하게 지정됐는지 확인
3. 진단 결과 handoff Notes에 기록

### 2단계: 프롬프트 안정화 적용
1. temperature = 0 설정
   - Gemini generate_content config에 temperature=0 추가
   - temperature=0 → 결정론적 출력 (동일 입력 = 동일 출력)
2. 출력 형식 강제
   - JSON 출력 형식을 더 엄격하게 지정
   - 판단 기준을 수치/날짜 기반으로 명확화
   - 예: "5년 이내" → "기준일로부터 1825일 이내"
3. 모호한 지시 제거
   - "추가검사가 필요한 경우" → 구체적 조건 명시

### 3단계: 검증
1. 결정론 영역 확인:
   - filters.py 단위 테스트 전부 통과 (동일 입력 = 동일 출력)
2. AI 영역 안정화 확인:
   - temperature=0 설정 확인
   - 동일 입력으로 2회 이상 호출 시 동일 출력 여부
     (샌드박스에서 실제 API 호출 불가 시 mock으로 대체)
3. pytest 104 passed 유지

## 검증 명령
cd backend && python -m pytest -q

## 완료 조건
- temperature=0 설정 완료
- 프롬프트 모호한 지시 개선
- pytest 104 passed
- handoff.md 표준 포맷 기록
- Next: Codex 단독 검증·푸시
- locks.md 잠금 해제

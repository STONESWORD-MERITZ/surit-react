# SURIT-009: 고지 질문 구조 전면 재구성

## 목적
건강체/간편 질문 구조를 아래 기준으로 재구성한다.

| 질문 | 건강체 | 간편 | 판단 |
|---|---|---|---|
| Q1 | 3개월이내 질병확정진단·추가검사·재검사·투약변경 | 동일 | 결정론 룰 |
| Q2 | 1년이내 질병확정진단 전체 → Gemini 추가검사·재검사 의심 소견 | 10년이내 입원·수술 | 결정론(1차)+Gemini(소견) |
| Q3 | 10년이내 입원·수술 | 5년이내 6대질환 | 결정론 룰 |
| Q4 | 5년이내 11대질환 | 없음 | 결정론 룰 |

## 우선순위
P0 (정확도·신뢰도 직결)

## 예상 소요
~3시간

## Owner
Codex

## 범위
- backend/filters.py
- backend/analyzer.py
- backend/pipeline/ai_judgment.py
- backend/pipeline/result_builder.py
- backend/pipeline/helpers.py
- backend/keywords.json
- src/pages/Disclosure.tsx
- backend/tests/

## 작업 절차
### 1단계: 현재 구조 진단
1. filters.py에서 현재 Q1~Q4 관련 함수 목록 확인
2. 현재 3개월/1년/5년/10년 날짜 창 함수 위치 확인
3. result_builder.py 반환 구조 확인
4. Disclosure.tsx 현재 질문 섹션 구조 확인
5. 진단 결과 handoff Notes에 기록

### 2단계: 백엔드 filters.py 재구성
- Q1 (건강체/간편 공통): _build_q1_items
- Q2 건강체: _build_q2_health_items (1년 진단 전체)
- Q2 간편: _build_q2_easy_items (10년 입원/수술)
- Q3 건강체: _build_q3_health_items (10년 입원/수술)
- Q3 간편: _build_q3_easy_items (5년 6대질환)
- Q4 건강체: _build_q4_health_items (5년 11대질환)

### 3단계: Gemini Q2 소견 연동
- Q2 건강체 항목별 "추가검사·재검사 의심 소견" 텍스트 생성
- temperature=0, seed=42 유지

### 4단계: result_builder.py 반환 구조
```
{
  "q1": [...],
  "q2_health": [...],
  "q2_easy": [...],
  "q3_health": [...],
  "q3_easy": [...],
  "q4_health": [...],
}
```

### 5단계: Disclosure.tsx 반영
- 건강체/간편 탭 구분 유지
- Q1~Q4 섹션 새 라벨로 표시

### 6단계: 테스트 보강
- Q1~Q4 각 함수 단위 테스트
- 기존 109개 회귀 없음 확인

## 검증 명령
cd backend && python -m pytest -q
npx tsc -p tsconfig.app.json --noEmit
npm run build

## 주의사항
- main.py API 시그니처 변경 최소화
- 6대질환 KCD 코드: C00-D48(암), I20-I25(심장), I60-I69(뇌혈관), I10-I15(고혈압), E10-E14(당뇨), K70-K77(간질환)
- 11대질환: 6대질환 + 신장(N00-N29) + 정신(F20-F33) + 근골격(M05-M14) + 호흡기(J40-J47) 등 — keywords.json 정의 사용

## 완료 조건
- Q1~Q4 구조 백엔드·프런트 모두 반영
- Gemini Q2 소견 안정적 연동
- pytest 전체 통과
- tsc + build 통과
- handoff.md 표준 포맷 기록
- Next: Codex 단독 검증·푸시
- locks.md 잠금 해제

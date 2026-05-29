# SURIT-BUG-010: 간편 탭 분류 오류 + Q2 의심 소견 범위 수정

## 목적
1. 간편 탭이 건강체와 동일하게 표시되는 버그 수정
2. Q2 의심 소견이 전체 문항에 적용되는 버그 수정

## 버그 1: 간편 탭 표시 오류
- 현재: 간편 탭에서 건강체 Q1~Q4 그대로 표시
- 정상: 간편 탭에서
  - Q1: "3개월이내 확정진단·추가검사·처방변경" (q1)
  - Q2: "10년이내 입원·수술" (q2_easy)
  - Q3: "5년이내 6대질환" (q3_easy)

## 버그 2: Q2 의심 소견 범위 오류
- 정상:
  - 건강체: Q1, Q2 에만 적용
  - 간편: Q1 에만 적용
  - Q3, Q4 에는 부착 금지

## 범위
- src/pages/Disclosure.tsx
- backend/pipeline/ai_judgment.py
- backend/analyzer.py
- backend/pipeline/result_builder.py (분류 분리 시그니처 변경)

## 검증
- npx tsc -p tsconfig.app.json --noEmit
- npm run build
- cd backend && python -m pytest -q (119+7skip 유지)

## 완료 조건
- 간편 탭 Q1/Q2/Q3 정상 분류 + Q4 미표시
- 의심 소견: 건강체 Q1·Q2, 간편 Q1 만
- pytest/tsc/build 통과
- Next: Codex 단독 검증·푸시
- locks.md 해제

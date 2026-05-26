# SURIT-BUG-007: 프런트 타임아웃 서버와 동기화

## 목적
현재 프런트 fetch 타임아웃이 ~180초로
서버 타임아웃(300초)보다 짧아 대용량 PDF 분석 시
"signal timed out" 오류가 발생한다.
프런트 타임아웃을 350초로 연장하여 서버보다 여유있게 설정한다.

## 우선순위
P0 (서비스 오류 직결)

## 예상 소요
~10분

## Owner
Cowork

## 범위 (수정 허용 파일)
- src/pages/Disclosure.tsx (fetch 타임아웃 상수)

## 범위 외
- 기타 모든 파일

## 작업 절차
1. Disclosure.tsx에서 fetch AbortController 타임아웃 위치 확인
2. 현재값 확인 후 350000ms(350초)로 변경
   - 서버 300초보다 50초 여유
   - 기존값 주석 보존, 변경 이유 명시
3. 변경 후 확인

## 검증
- npx tsc -p tsconfig.app.json --noEmit
- npm run build

## 완료 조건
- 프런트 타임아웃 350초로 변경
- tsc + build 통과
- handoff.md 표준 포맷 기록
- Next: Codex 검증 + 푸시
- locks.md 잠금 해제

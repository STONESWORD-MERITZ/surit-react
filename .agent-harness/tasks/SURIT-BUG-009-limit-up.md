# SURIT-BUG-009: 잘림 상한 대폭 상향

## 목적
318페이지 PDF(약 13,000줄 / 293,000자)가 3000줄/100K자 상한을
초과해 truncation_warning이 발생한다.
메리츠 간편 제거(BUG-008)로 Gemini 호출이 2번으로 줄었으니
상한을 대폭 올려 truncation_warning을 완전 제거한다.

## 우선순위
P0 (신뢰도 직결)

## 예상 소요
~15분

## Owner
Cowork

## 범위
- backend/pipeline/ai_judgment.py
- backend/analyzer.py

## 작업 절차
### 1단계: 현재 filtered_lines 실제 길이 진단
318p PDF 기준으로 _strengthen_filter 통과 후
실제 filtered_lines 길이가 얼마인지 확인:
- ai_judgment.py의 _finalize_raw_text_for_gemini에
  임시 로그 추가:
  logger.info(f"filtered_lines 길이: {len(filtered_lines)}")
  → 실제 값 확인 후 적절한 상한 결정
- 단, 로그 추가는 진단용이므로 최종 코드에는 제거

### 2단계: 상한 결정 기준
- filtered_lines 실제 길이가 X줄이면:
  · X < 5000: 상한 5000줄 / 150K자
  · X < 8000: 상한 8000줄 / 250K자
  · X >= 8000: 상한 13000줄 / 300K자 (전체 커버)
- 타임아웃 기준: BUG-008 이후 Gemini 2번 호출
  각 ~45초 예상 → 총 ~150초로 300초 한도 여유 있음

### 3단계: 상한 적용
- ai_judgment.py: filtered_lines 상한 + MAX_RAW_TEXT_LEN 변경
- analyzer.py: _GEMINI_LINE_CAP 동기화
- 기존값 주석 보존

### 4단계: 검증
- cd backend && python -m pytest -q (104 passed 유지)

## 완료 조건
- 상한 변경 완료
- pytest 104 passed
- handoff.md 표준 포맷 기록
- Next: Codex 검증 + 푸시
- locks.md 잠금 해제

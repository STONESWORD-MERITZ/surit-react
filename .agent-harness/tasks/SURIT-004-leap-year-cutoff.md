# SURIT-004: 윤년 컷오프 보정

## 목적
현재 분석 창이 1825일(5년)·3650일(10년) 고정값으로 계산돼,
윤년 포함 구간에서 실제 달력 기준 5년/10년보다 2~3일 짧아지는 문제를 보정한다.
보험 심사 기준은 달력 연도(anniversary) 기준이므로, 고정 일수 대신
relativedelta 또는 날짜 직접 연산으로 정확한 경계일을 구한다.

## 우선순위
P2

## 예상 소요
~30분

## Owner
Codex (백엔드 날짜 로직 수정)

## 범위 (수정 허용 파일)
- backend/filters.py (1825·3650일 상수 사용 위치)
- backend/pipeline/helpers.py (_dts_in_range 등 날짜 헬퍼)
- backend/tests/ (회귀 테스트 추가)

## 범위 외
- 프런트 코드 일체
- analyzer.py, main.py 등 날짜 로직 무관 모듈

## 작업 절차
### 1단계: 현재 상태 진단
1. filters.py와 helpers.py에서 1825·3650 상수 사용 위치 전수 확인
2. timedelta(days=1825) 방식인지, 다른 방식인지 확인
3. relativedelta 또는 date.replace() 방식이 이미 일부 적용됐는지 확인
4. 90일·365일 창은 윤년 영향 없으므로 수정 불필요 확인
5. 진단 결과를 handoff.md Notes에 기록

### 2단계: 보정
1825·3650일 고정 timedelta를 아래 방식으로 교체:
- 5년 창: today - relativedelta(years=5) 또는 date.replace(year=today.year-5)
- 10년 창: today - relativedelta(years=10) 또는 date.replace(year=today.year-10)
- dateutil 미설치 시 date.replace() 방식 사용 (표준 라이브러리)
- 경계일 포함(>=) 기존 로직은 그대로 유지
- 기존 상수(1825·3650)는 주석으로 보존, 변경 이유 명시

### 3단계: 회귀 테스트
- 윤년 포함 구간(예: 2020-02-29 기준)에서 5년/10년 경계가
  달력 기준으로 정확히 계산되는지 검증
- 기존 102개 테스트 전부 통과 유지

## 검증 명령
cd backend && python -m pytest -q   ← 102개 + 신규 통과

## 수동 확인 체크리스트
- [ ] 1825·3650 고정 timedelta가 코드에 잔존하지 않는가
- [ ] 90·365일 창은 변경되지 않았는가
- [ ] 경계일 포함(>=) 로직 회귀 없는가

## 완료 조건
- 5년·10년 창이 달력 연도 기준으로 계산됨
- pytest 전체 통과 (102 + 신규)
- handoff.md 표준 포맷 기록
- Next: Codex 단독 검증·푸시
- locks.md 잠금 해제

## 진단 메모 / 범위 확대 (1단계 결과)
- 1825·3650 고정 timedelta는 `helpers.py`에 없고, **5개 모듈에 분산**돼 있다:
  `filters.py`(`_cutoffs`), `analyzer.py`(창 4종 + `IN_5Y`/`IN_10Y` 태깅),
  `pipeline/result_builder.py`, `pipeline/disease_aggregator.py`,
  `meritz_easy_rules.py`(`ten_years_ago` ×3).
- `filters.py`만 고치면 모듈 간 5년/10년 경계가 1~2일 어긋나 같은 진료기록이
  모듈별로 다르게 판정되는 내부 불일치가 발생 → **사용자 승인 하에 범위를
  날짜 창 전 모듈로 확대**한다.
- 확대 범위: `helpers.py`(공용 헬퍼 `_subtract_years` 신설), `filters.py`,
  `analyzer.py`, `pipeline/result_builder.py`, `pipeline/disease_aggregator.py`,
  `meritz_easy_rules.py`, `backend/tests/`.
- `filters.py`는 순환 임포트 회피 정책(파일 내 주석)에 따라 `_subtract_years`를
  인라인하고, 나머지 모듈은 `helpers._subtract_years`를 import 한다.
- 90·365일 창은 윤년 영향이 없어 그대로 둔다.

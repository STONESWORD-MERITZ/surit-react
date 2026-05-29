# SURIT-005: 날짜 창 로직 중앙화

## 목적
filters.py와 helpers.py에 분산된 _dts_in_range 중복 로직을 제거하고,
날짜 창 계산을 단일 진입점으로 중앙화한다.
SURIT-004에서 _subtract_years 헬퍼를 helpers.py에 신설했으므로,
날짜 창 관련 헬퍼도 같은 모듈에 통합하는 것이 자연스럽다.

## 우선순위
P3

## 예상 소요
~30분

## Owner
Codex (백엔드 리팩터링)

## 범위 (수정 허용 파일)
- backend/pipeline/helpers.py (중앙화 대상)
- backend/filters.py (중복 제거 + import 전환)
- backend/analyzer.py (필요 시 import 전환)
- backend/pipeline/result_builder.py (필요 시)
- backend/pipeline/disease_aggregator.py (필요 시)
- backend/meritz_easy_rules.py (필요 시)
- backend/tests/ (회귀 테스트 추가)

## 범위 외
- 프런트 코드 일체
- main.py

## 작업 절차
### 1단계: 현재 상태 진단
1. filters.py와 helpers.py에서 _dts_in_range 구현 위치 전수 확인
2. 두 구현이 동일한지, 차이가 있는지 비교
3. 각 모듈에서 _dts_in_range를 호출하는 위치 파악
4. filters.py 순환 임포트 회피 정책(39행 주석) 재확인
   - 인라인 유지가 필요한지, import 전환 가능한지 판단
5. 진단 결과를 handoff.md Notes에 기록

### 2단계: 중앙화
1. helpers.py에 _dts_in_range 정본 1개만 유지
2. 각 모듈에서 중복 구현 제거 후 helpers._dts_in_range import로 전환
3. filters.py 순환 임포트 이슈가 있으면:
   - SURIT-004와 동일하게 인라인 유지 + 주석으로 "helpers 정본과 동본" 명시
4. 기존 동작(경계 포함 >= 등) 변경 없음

### 3단계: 회귀 테스트
- 중앙화 후 기존 107개 테스트 전부 통과 확인
- _dts_in_range 단위 테스트 추가 (경계 포함, 경계 외, 윤년 포함 구간)

## 검증 명령
cd backend && python -m pytest -q   ← 107개 + 신규 통과

## 수동 확인 체크리스트
- [ ] _dts_in_range 중복 구현이 제거됐는가
- [ ] 순환 임포트 없이 import 전환됐는가 (또는 인라인 동본 주석 명시)
- [ ] 기존 날짜 창 동작 회귀 없는가

## 완료 조건
- _dts_in_range 중앙화 완료
- pytest 전체 통과 (107 + 신규)
- handoff.md 표준 포맷 기록
- Next: Codex 단독 검증·푸시
- locks.md 잠금 해제

## 진단 메모 (1단계 결과)
- `_dts_in_range` 정의는 2곳: `helpers.py`(정본, 무주석)와 `filters.py`(인라인
  동본, `-> list[str]` 주석만 차이 — 본문 완전 동일).
- 호출처: `filters.py`(다수 + `_visit_count_in_range`), `helpers.py`(내부),
  `result_builder.py`·`analyzer.py`는 이미 `helpers`에서 import.
- `filters.py`는 `_dts_in_range` 외에도 `_code_in`·`_subtract_years`·
  `_visit_count_in_range`·`_parse_ymd`·`_max_presc`를 인라인하는 "공유 헬퍼"
  섹션을 둔다(과거 `analyzer.py`↔`filters.py` 순환 회피 잔재).
- `pipeline/__init__.py`는 1줄 빈 마커, `helpers.py`는 표준 라이브러리·pandas만
  import → **`filters → pipeline.helpers` 순환 임포트 없음**. import 전환 가능.
- 본 태스크 범위(`_dts_in_range`)만 `helpers` 정본 import 로 전환한다. 나머지
  인라인 헬퍼 전체 정리는 후속 태스크 권장.

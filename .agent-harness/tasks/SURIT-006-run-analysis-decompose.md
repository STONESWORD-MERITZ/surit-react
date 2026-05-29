# SURIT-006: run_analysis 함수 분해

## 목적
backend/analyzer.py의 run_analysis 함수가 과대하여
가독성·테스트성이 낮다. 논리적 단계별로 내부 헬퍼 함수로 분해하여
각 단계를 독립적으로 읽고 테스트할 수 있게 한다.

## 우선순위
P3

## 예상 소요
~1~2시간

## Owner
Codex (백엔드 리팩터링)

## 범위 (수정 허용 파일)
- backend/analyzer.py (분해 대상)
- backend/tests/ (단위 테스트 추가)

## 범위 외
- 프런트 코드 일체
- main.py, filters.py, pipeline/* 등 analyzer 외 모듈
  (호출 시그니처 변경 없으면 무수정)

## 작업 절차
### 1단계: 현재 상태 진단
1. run_analysis 함수 전체 구조 파악
   - 총 줄 수, 논리적 단계 구분
   - 현재 내부 헬퍼(_로 시작) 현황
2. 분해 후보 단계 목록 작성 (예시):
   - 입력 검증 / PDF 파싱 / 질병 집계 /
     필터 적용 / AI 판단 / 결과 빌드 등
3. main.py의 run_analysis 호출 시그니처 확인
   - 외부 시그니처(인수·반환값)는 절대 변경 금지
4. 진단 결과를 handoff.md Notes에 기록
   - 분해 후보 단계 목록 포함

### 2단계: 분해
1. 각 논리 단계를 _로 시작하는 내부 헬퍼 함수로 추출
2. run_analysis 본체는 헬퍼 호출 흐름만 남김
   - 목표: run_analysis 본체 30줄 이내
3. 헬퍼 함수 규칙:
   - _ 접두사 (모듈 내부용)
   - 단일 책임 (한 단계만 담당)
   - 인수·반환값을 명확히 타입 힌트로 명시
   - docstring으로 단계 역할 한 줄 설명
4. 기존 로직·동작 변경 없음 (순수 리팩터링)

### 3단계: 단위 테스트
- 분해된 헬퍼 함수 중 독립 테스트 가능한 것 우선
- 기존 112개 테스트 전부 통과 유지

## 검증 명령
cd backend && python -m pytest -q   ← 112개 + 신규 통과

## 수동 확인 체크리스트
- [ ] run_analysis 외부 시그니처 변경 없는가
- [ ] run_analysis 본체가 헬퍼 호출 흐름 위주로 정리됐는가
- [ ] 각 헬퍼에 _ 접두사·타입 힌트·docstring 있는가
- [ ] 기존 동작 회귀 없는가

## 완료 조건
- run_analysis 분해 완료
- pytest 전체 통과 (112 + 신규)
- handoff.md 표준 포맷 기록
- Next: Codex 단독 검증·푸시
- locks.md 잠금 해제

## 진단 메모 (1단계 결과)
- `run_analysis`는 94~839행(약 745줄). 외부 시그니처
  `run_analysis(active_files, product_type, reference_date, birthdate_pw, api_key) -> dict`
  와 반환 dict 키는 절대 불변(순수 리팩터링).
- 가장 큰 덩어리는 시스템 프롬프트 구성(279~630행, ~350줄) — 입력 6개
  (product_type·today_str·d_3m·d_1y·d_5y·d_10y), 출력 1개(system_prompt)로
  완전 자기완결 → 추출 시 최대 효과·최소 위험.
- 분해 후보(내부 `_` 헬퍼): `_parse_all_pdfs`, `_build_drug_change_text`,
  `_build_presc_end_text`, `_build_tagged_entries`, `_build_visit_count_lines`,
  `_build_first_diag_lines`, `_build_system_prompt`, `_build_medical_judgment_inputs`,
  `_apply_medical_judgment`.
- Gemini 병렬 호출·병합 블록(690~759행)은 오케스트레이션 본체 성격이고
  입력 파라미터가 14개에 달해, 헬퍼 추출이 오히려 가독성을 해칠 위험이 커
  run_analysis 본체에 유지한다(본체 30줄 목표는 이 사유로 ~90줄 수준).

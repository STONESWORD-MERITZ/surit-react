# SURIT-BUG-012: 간편 Q2 순수화 + 건강체 Q3 OR 확장

## 목적
SURIT-009 신구조 이후 두 결함을 교정한다.

1. **건강체 Q3** — 활성 경로(`_build_q3_health_items`)가 `_build_q2_easy_items` 를
   재라벨링만 해 **입원·수술만** 생성. 통원7회·투약30일 OR 트리거가 누락됨
   (옛 deprecated `_build_health` 에만 존재).
2. **간편 Q2** — filters 의 `_build_q2_easy_items` 는 이미 입원·수술만 생성하지만,
   `result_builder` 가 탭 구분 없이 건강체 창/라벨을 적용 중.
   `_build_pool`·`_build_reports_for_product` 의 `q_since` 맵이 Q2→1년(건강체 창),
   라벨도 "1년 이내 진단(의심 소견)" 으로 고정 → 간편 Q2 입원·수술의 1년 초과분 누락 + 라벨 오표기.

## 우선순위
P0 (분석 정확도·신뢰도 직결)

## Owner
Codex — 구현·검증·푸시 단독 담당.

## 확정 규칙
### 건강체 Q3 (OR — 하나라도 충족 시 고지)
- 10년내 입원 **OR** 10년내 수술 **OR** 동일질병 통원 7회 이상 **OR** 동일질병 투약 30일 이상
- 입원 = 기본진료만, 수술 = 세부진료만, 창 3650일(달력 10년) 경계 포함(`>=`)
- 동일질병 판정 = KCD 코드 정규화 기준
- 투약 30일 = 현 '투약 N일' 산출 경로(`_max_presc`) 재사용.
  ※ `_max_presc` 는 **처방 에피소드별 최대값(= 계속 처방일수)** 이며 누적 합계가 아님.
  약관이 '누적 30일' 이면 별도 태스크 필요 — 본 태스크는 현 경로 유지(handoff 플래그).
- 통원 7회 / 투약 30일은 모듈 상수로 두고 매직넘버 주석.

### 간편 Q2 (순수 — 입원 OR 수술만)
- 통원·투약·1년진단·추가검사 의심·Gemini 의심 판단 전부 미적용.
- filters 의 `_build_q2_easy_items` 로직 자체는 이미 입원·수술만 → 유지.
- result_builder 의 탭별 창/라벨 분리로 건강체 Q2 로직(1년 창·의심 소견 라벨) 호출을 끊는다.
  - 간편 창: Q1→3개월, Q2→10년, Q3→5년
  - 건강체 창: Q1→3개월, Q2→1년, Q3→10년, Q4→5년

## 주의
- 건강체 Q2 로직(`_build_q2_health_items`) 자체는 건드리지 말 것.
- `main.py` API 시그니처 변경 최소화.

## 범위
- backend/filters.py — `_build_q3_health_items` 실 빌더화 + Q3 통원/투약 상수
- backend/pipeline/result_builder.py — `_build_pool`/`_build_reports_for_product` 탭 인지(창·라벨)
- backend/pipeline/disease_aggregator.py — (잠금만; 수정 예상 없음)
- src/pages/Disclosure.tsx — 간편 Q2 라벨/칩 정리(통원·투약·의심 태그 노출), 건강체 Q3 통원·투약 단독 표시 확인
- backend/tests/ — 회귀 테스트

## 검증 명령
```
cd backend && python -m pytest -q
npx tsc -p tsconfig.app.json --noEmit
npx tsc -p tsconfig.node.json --noEmit
npm run build
```
ast.parse 사용 시 UTF-8 명시 (Windows cp949 회피):
`python -c "import ast; ast.parse(open('backend/filters.py', encoding='utf-8').read()); print('OK')"`

## 회귀 테스트
- 간편 Q2: 입원/수술만 매칭, 1년진단·의심·통원·투약 미혼입
- 건강체 Q3: 통원 7회(고지)/6회(미고지), 투약 30일(고지)/29일(미고지) 경계
- 통원·투약 룰이 간편 Q2 에서 미발동

## 통원 7회 룰 디버깅 — 질염 누락 (이전 조사 기록)
실측: 오성심 PDF — 기침(R05) 통원 7회 / 급성질염(N76.0) 통원 14회인데 질염이 7회 룰에 안 잡힘.

- 가설 1 (진료과 제외): **기각**. 결정론 dept 필터는 `disease_aggregator.py:220,268` 의 `dept=="일반의"` 단 하나. 산부인과/치과/피부과/항문 제외 로직 없음(해당 단어는 `analyzer.py` Gemini 프롬프트에만 존재).
- 가설 3 (4단위 코드 탈락): **기각**. `non_disease_code_prefixes` = Z00~Z27 뿐(N76 미포함). `helpers.normalize_code`/`_KCD_RE` 가 N760 정상 처리.
- 가설 2 (약국 코드 차이): **확정(방향)**. 정확한 원인은 `helpers.row_is_junk`(helpers.py:191). 행 전체 문자열에 `$`/`해당없음` 이 하나라도 있으면 행 통째 폐기 → 질염 병원행은 약국코드 칸이 `$ 해당없음` 이라 14건 전부 탈락, 기침행은 약국코드가 R05계열이라 생존.

샌드박스 재현 확증: 기침(약국코드 정상) → group `R05`, 통원 7회, `R-H-Q3-VISIT-7` 발동 / 질염(약국코드 `$ 해당없음`) → group 미생성(`group_keys=['R05']`), 통원 0회.

수정(helpers.py, 사용자 승인 후 범위 확장): `row_is_junk` 를 "마커가 있어도 진단/행위/약품 식별 필드에 실내용이 남아 있으면 junk 아님" 으로 교정.

## 완료 조건
- 건강체 Q3 통원·투약 단독 트리거 동작
- 간편 Q2 순수성 + 탭별 창/라벨 분리
- pytest 전체 통과, tsc(app·node)·build 통과
- handoff.md 표준 포맷 기록 (Notes: 투약 누적vs계속 약관 플래그)
- Next: Codex 단독 검증·푸시
- locks.md 잠금 해제

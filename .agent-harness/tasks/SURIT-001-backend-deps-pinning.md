# SURIT-001: 백엔드 의존성 버전 고정

## 목적
`backend/requirements.txt`의 미고정 의존성을 현재 설치 버전 기준으로 `==` 고정하여
Railway 배포 재현성을 확보한다. 의존성 신규 릴리스 한 건으로 빌드가 깨지는 위험을 제거한다.

## 우선순위
P1 (출시 안정성 직결)

## 예상 소요
~15분

## Owner
Codex (requirements.txt 코드 수정 작업)

## 범위 (수정 허용 파일)
- `backend/requirements.txt`

## 범위 외 (수정 금지)
- `backend/` 하위 파이썬 코드 일체
- 프런트 코드 일체

## 작업 절차
1. `backend/` 디렉터리에서 현재 설치된 패키지 버전 확인
   ```powershell
   cd backend
   pip freeze
   ```
2. `requirements.txt`의 미고정 항목을 `pip freeze` 결과 기준으로 `==`로 고정
   - 대상(PROGRESS.md 기준): `fastapi`, `uvicorn`, `pdfplumber`, `pandas`, `google-genai`
   - 그 외에 미고정 항목이 있다면 함께 고정
3. 이미 고정되어 있던 항목은 그대로 둔다 (불필요한 버전 변경 금지)
4. 고정 후 새 가상환경에서 재설치하여 충돌 없음 확인 (가능한 경우)

## 검증 명령
```powershell
cd backend
python -m pytest -q
```
- 91개 테스트 전부 통과해야 한다 (현재 baseline)

## 수동 확인 체크리스트
- [ ] `requirements.txt`에 미고정(`==` 없는) 항목이 남아있지 않은가
- [ ] 버전 표기가 `pip freeze` 결과와 일치하는가
- [ ] pytest 91개 전부 pass

## 완료 조건
- requirements.txt의 모든 의존성이 `==`로 고정됨
- backend pytest 91개 통과
- handoff.md 상단에 표준 포맷으로 결과 기록
- locks.md 잠금 해제

## 비고
- 본 태스크는 코드 로직을 변경하지 않는다. 버전 충돌이 발견되면 별도 태스크로 분리한다.
- 후속 추천: 처방 PDF 오분류 보정 (P1, ~30분) → SURIT-002 후보

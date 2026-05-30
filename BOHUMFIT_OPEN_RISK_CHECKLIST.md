# BOHUMFIT.ai 오픈 전 리스크 체크리스트

## 브랜드/광고 문구
- [x] 외부 노출 브랜드를 `BOHUMFIT` / `보험핏`으로 전환했다.
- [x] `bohumfit.ai`를 1차 운영 도메인으로 사용한다.
- [x] "가입 확정", "승인 보장", "가입 가능 확정", "보험금 지급 보장"처럼 결과를 단정하는 문구를 사용하지 않는다.
- [x] 권장 문구를 "고지 리스크 점검", "청약 전 확인", "보험사 심사 전 참고자료", "가입 전 확인자료"로 통일했다.
- [x] 공개 OG 이미지에서 기존 `SURIT`/`surit-react.vercel.app` 노출을 제거했다.
- [x] 정식 오픈 전 미완성 보장분석 기능의 공개 내비게이션 진입점을 숨겼다.

## 개인정보/민감정보
- [x] 업로드 전 건강정보 처리 동의 체크를 필수로 둔다.
- [x] 설계사가 고객 자료를 업로드하는 경우 정보주체 동의 확보 확인 체크를 필수로 둔다.
- [x] 개인정보처리방침에 Google Gemini, Supabase, Vercel, Railway 위탁 처리 내용을 명시했다.
- [x] 서비스 서버는 PDF와 추출 의료정보를 저장하지 않는 정책을 안내했다.
- [x] 약관/개인정보처리방침의 화면상 TODO/등록 예정 placeholder를 제거했다.
- [ ] 사업자 정보, 개인정보 보호책임자, 문의 이메일, 약관/개인정보처리방침 시행일은 Human이 실제 운영 정보로 최종 법무 검토한다.

## 보안/비용 방어
- [x] `/api/analyze`는 Supabase JWT 검증을 통과해야 호출할 수 있다.
- [x] 파일 개수, 개별 파일 용량, 총 업로드 용량, PDF 형식 검증을 적용했다.
- [x] Sentry 전송 전 인증헤더, 쿠키, 요청 본문, 대용량 진료 데이터 컨텍스트를 필터링한다.
- [x] 운영 Supabase Auth Site URL과 Redirect URL이 `https://bohumfit.ai` 기준으로 동작하는지 OAuth 302로 확인했다.
- [x] Railway CORS preflight가 `https://bohumfit.ai`와 `https://www.bohumfit.ai`에서 통과하는지 확인했다.
- [ ] Railway `SERVICE_ENV=production` 설정 후 `/api/health`의 `env`가 `production`인지 확인한다.
- [ ] Railway `CORS_ORIGINS=https://bohumfit.ai,https://www.bohumfit.ai`를 명시 설정해 이전 Vercel 도메인 허용 여부를 의도적으로 결정한다.
- [ ] 운영 Sentry DSN 설정 여부를 결정한다. 미설정 오픈 시 초기 운영 리스크로 기록한다.
- [ ] Vercel 환경변수 `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_SITE_URL`이 운영값인지 확인한다.

## 배포/도메인
- [x] Vercel에 `bohumfit.ai`를 연결했다.
- [x] `www.bohumfit.ai`는 `bohumfit.ai`로 308 redirect된다.
- [x] 배포 후 `bohumfit.ai`, `www.bohumfit.ai`, 로그인 OAuth redirect, API CORS를 실제 네트워크 요청으로 확인했다.

## 실제 QA
- [ ] 실제 로그인 세션으로 오성심 PDF 3종 end-to-end 분석을 수행한다.
- [ ] 같은 PDF 반복 분석 시 고지 질병코드·질병명·건수·질문 분류가 동일한지 확인한다.
- [ ] 추가검사/재검사 의심 소견은 AI 판단 영역으로 분리해 변동 가능 항목으로 기록한다.
- [ ] 동의 체크 전 분석이 실행되지 않는지 확인한다.
- [ ] 허용 용량 초과 PDF가 명확한 오류로 차단되는지 확인한다.
- [ ] 결과 복사 문구에 면책 문구가 포함되는지 확인한다.
- [ ] 모바일/데스크톱에서 첫 화면, 업로드, 결과 카드, 탭 UI가 깨지지 않는지 확인한다.

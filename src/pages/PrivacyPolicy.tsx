import { Link } from "react-router-dom";

// TODO(사업자 정보): 사업자 등록 후 아래 값을 채워주세요.
//   값이 비어 있으면 화면에는 "(... 등록 예정)" 으로 표시됩니다.
const COMPANY = {
  privacyOfficer: "",   // 개인정보 보호책임자 성명
  privacyContact: "",   // 연락처
  privacyEmail: "",     // 이메일
  effectiveDate: "",    // 시행일 (예: 2026-06-01)
};
const _ph = (v: string, label: string): string => (v ? v : `(${label} 등록 예정)`);

const SECTIONS: { title: string; body: string }[] = [
  {
    title: "제1조 (목적)",
    body:
      "본 개인정보처리방침은 SURIT(이하 '서비스')이 보험 알릴의무 분석 서비스를 제공함에 있어 이용자의 개인정보를 어떤 항목에서, 어떤 목적으로, 어떤 방식으로 처리하는지를 안내하기 위해 마련되었습니다.",
  },
  {
    title: "제2조 (수집하는 개인정보 항목 및 수집 방법)",
    body:
      "① 회원가입·로그인: 이메일, OAuth 제공자(카카오, 구글)가 전달하는 식별자 및 기본 프로필 정보(이름, 프로필 이미지).\n" +
      "② 알릴의무 분석: 이용자가 업로드한 건강보험심평원 진료기록·세부진료·처방조제 PDF 파일.\n" +
      "③ 자동 수집: 접속 로그(IP, 접속 일시), 브라우저 종류, 쿠키(서비스 운영에 필요한 최소 범위).",
  },
  {
    title: "제3조 (개인정보의 처리 목적)",
    body:
      "수집된 개인정보는 (1) 회원 식별 및 로그인 유지, (2) 업로드된 PDF의 알릴의무 항목 추출·분석 결과 제공, (3) 서비스 부정이용 방지·법적 의무 이행 목적에 한해 사용됩니다. 수집 시점에 명시한 목적 외의 용도로는 사용되지 않습니다.",
  },
  {
    title: "제4조 (개인정보의 보유 및 이용 기간)",
    body:
      "① 회원정보: 회원 탈퇴 시까지 보유, 탈퇴 후 즉시 파기.\n" +
      "② 업로드 PDF 및 추출 의료정보: 분석 처리 직후 서버 메모리에서 폐기되며, 어떠한 경우에도 서버나 데이터베이스에 저장하지 않습니다.\n" +
      "③ 접속 로그: 통신비밀보호법 등 관계 법령이 정하는 기간 동안 보관 후 파기.",
  },
  {
    title: "제5조 (개인정보의 제3자 제공 및 처리 위탁)",
    body:
      "① 본 서비스는 이용자의 동의 없이 개인정보를 제3자에게 제공하지 않습니다.\n" +
      "② 다만 분석 처리 과정에서 다음 위탁이 발생합니다:\n" +
      "   - Google LLC (Gemini API): 추출된 진료내역 텍스트의 AI 의학 판단 처리. 위탁 데이터는 Google 의 API 약관에 따라 보관되며, 본 서비스는 위탁 처리 외 목적으로 사용되지 않도록 관리합니다.\n" +
      "   - Supabase Inc.: 회원 인증 및 식별 정보 보관.\n" +
      "   - Vercel Inc. / Railway Corp.: 서비스 호스팅(서버 인프라).\n" +
      "③ 위탁사가 변경될 경우 본 방침을 통해 사전 또는 사후 지체 없이 공지합니다.",
  },
  {
    title: "제6조 (민감정보 처리에 관한 사항)",
    body:
      "본 서비스가 처리하는 진료내역에는 개인정보보호법 제23조에 따른 민감정보(건강에 관한 정보)가 포함됩니다. 이용자는 분석 시작 전 별도 동의 절차를 통해 민감정보 처리에 동의해 주셔야 합니다. 동의를 거부할 권리가 있으며, 거부 시 분석 서비스 제공이 제한될 수 있습니다.",
  },
  {
    title: "제7조 (이용자의 권리와 행사 방법)",
    body:
      "이용자는 언제든 본인의 개인정보 열람·정정·삭제·처리정지를 요청할 수 있으며, 회원 탈퇴를 통해 서비스에서 자신의 정보를 일괄 삭제할 수 있습니다. 요청은 본 방침 하단의 연락처를 통해 접수할 수 있습니다.",
  },
  {
    title: "제8조 (개인정보 보호책임자)",
    body:
      `성명: ${_ph(COMPANY.privacyOfficer, "보호책임자 성명")}\n연락처: ${_ph(COMPANY.privacyContact, "연락처")}\n이메일: ${_ph(COMPANY.privacyEmail, "이메일")}\n\n이용자는 개인정보 처리와 관련하여 위 보호책임자에게 문의·신고할 수 있으며, 필요시 개인정보보호위원회(privacy.go.kr) 및 한국인터넷진흥원 개인정보침해신고센터(privacy.kisa.or.kr, 국번없이 118) 의 도움을 받을 수 있습니다.`,
  },
  {
    title: "제9조 (방침의 변경)",
    body:
      `본 개인정보처리방침은 법령 및 서비스 정책 변경 시 사전 공지 후 개정될 수 있습니다. 시행일자: ${_ph(COMPANY.effectiveDate, "시행일")}`,
  },
];

export default function PrivacyPolicy() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="text-2xl font-extrabold text-gray-900">개인정보처리방침</h1>
      <p className="mt-2 text-xs text-gray-400">최종 개정 시행일: {_ph(COMPANY.effectiveDate, "시행일")}</p>
      <div className="mt-8 space-y-7">
        {SECTIONS.map((s) => (
          <section key={s.title}>
            <h2 className="text-sm font-bold text-gray-900">{s.title}</h2>
            <p className="mt-2 whitespace-pre-line text-[13px] leading-6 text-gray-600">
              {s.body}
            </p>
          </section>
        ))}
      </div>
      <div className="mt-10 text-xs text-gray-400">
        <Link to="/" className="underline hover:text-gray-600">홈으로 돌아가기</Link>
      </div>
    </main>
  );
}

import { Link } from "react-router-dom";

const SECTIONS: { title: string; body: string }[] = [
  {
    title: "제1조 (목적)",
    body:
      "본 약관은 SURIT(이하 '회사')이 제공하는 보험 알릴의무 분석 서비스(이하 '서비스')의 이용과 관련하여 회사와 이용자의 권리·의무 및 책임사항을 규정함을 목적으로 합니다.",
  },
  {
    title: "제2조 (서비스의 정의)",
    body:
      "본 서비스는 이용자가 업로드한 건강보험심평원 PDF 자료를 기반으로 보험 가입 또는 보험금 청구 시 알려야 할 의무가 있는 병력 항목을 AI 보조 분석 도구를 통해 정리하여 제공하는 정보 서비스입니다.",
  },
  {
    title: "제3조 (서비스의 책임 한계)",
    body:
      "① 본 서비스가 제공하는 분석 결과는 참고용 보조 정보이며, 보험 가입·청구의 최종 결정은 보험회사의 언더라이팅 정책 및 약관에 따라 이루어집니다.\n" +
      "② 본 서비스는 AI 모델(Google Gemini)의 판단을 일부 활용하며, 모델 특성상 오류·누락이 발생할 수 있습니다. 이용자는 본 서비스의 결과만으로 보험사에 대한 고지 여부를 최종 결정해서는 안 되며, 필요한 경우 보험회사·보험설계사·의료전문가와 직접 상담해야 합니다.\n" +
      "③ 회사는 분석 결과의 활용으로 인해 발생한 보험 가입·청구·심사·분쟁 결과에 대해 법적 책임을 지지 않습니다.",
  },
  {
    title: "제4조 (이용자의 의무)",
    body:
      "① 이용자는 본인 또는 본인이 정당한 권한을 가진 자의 진료기록만을 업로드해야 합니다.\n" +
      "② 타인의 진료기록을 무단으로 업로드·분석할 경우 발생하는 모든 법적 책임은 이용자에게 있습니다.\n" +
      "③ 이용자는 서비스를 부정한 목적(허위 자료 생성, 보험 사기 등)으로 이용해서는 안 됩니다.",
  },
  {
    title: "제5조 (회사의 의무)",
    body:
      "회사는 관련 법령과 본 약관에 따라 안정적이고 지속적인 서비스 제공을 위해 노력하며, 이용자의 개인정보를 별도의 개인정보처리방침에 따라 보호합니다.",
  },
  {
    title: "제6조 (서비스 이용의 제한 및 해지)",
    body:
      "이용자가 본 약관 및 관련 법령을 위반하는 경우 회사는 사전 통지 후(긴급한 경우 사후 통지) 서비스 이용을 제한·중단할 수 있습니다. 이용자는 언제든지 회원 탈퇴를 통해 서비스 이용을 종료할 수 있습니다.",
  },
  {
    title: "제7조 (분쟁의 해결)",
    body:
      "본 약관에 관한 분쟁은 대한민국 법령에 따르며, 회사 본점 소재지를 관할하는 법원을 1심 관할 법원으로 합니다.",
  },
  {
    title: "부칙",
    body: "본 약관은 TODO(시행일자)부터 시행합니다.",
  },
];

export default function Terms() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="text-2xl font-extrabold text-gray-900">이용약관</h1>
      <p className="mt-2 text-xs text-gray-400">최종 개정 시행일: TODO</p>
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

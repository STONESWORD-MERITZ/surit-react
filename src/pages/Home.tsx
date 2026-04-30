import { Link } from "react-router-dom";

const cards = [
  {
    label: "기능 01",
    title: "알릴의무 필터",
    desc: "심평원 PDF를 업로드하면 AI가 고지 항목을 자동 추출합니다.",
    to: "/disclosure",
  },
  {
    label: "기능 02",
    title: "보장분석 비포&에프터",
    desc: "기존·신규 보장을 비교해 리모델링 근거를 제시합니다.",
    to: "/before-after",
  },
];

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-120px)] py-16 px-4">
      {/* 배지 */}
      <span className="inline-flex items-center bg-[#EEF2FF] text-[#4F46E5] text-xs font-bold tracking-wider px-4 py-1.5 rounded-full mb-8">
        설계사 전용 AI 플랫폼
      </span>

      {/* 로고 */}
      <h1 className="text-4xl font-black text-gray-900 tracking-tight mb-4">
        SUR<span className="text-[#4F46E5]">IT</span>
      </h1>

      {/* 헤드라인 */}
      <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 tracking-tight leading-snug text-center mb-4 break-keep">
        보험의 확신,{" "}
        <span className="text-[#4F46E5]">슈릿</span>에서 간편하게.
      </h2>

      {/* 설명 */}
      <p className="text-gray-400 text-center leading-relaxed mb-12 break-keep max-w-md">
        심평원 진료 데이터를 AI가 분석해 알릴의무 항목을 자동 추출하고
        <br />
        기존·신규 보장을 한눈에 비교해 드립니다.
      </p>

      {/* 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full max-w-2xl mb-16">
        {cards.map((c) => (
          <Link key={c.to} to={c.to} className="no-underline group">
            <div className="bg-white rounded-2xl p-7 shadow-[0_2px_12px_rgba(0,0,0,0.06)] hover:shadow-[0_8px_30px_rgba(0,0,0,0.1)] transition-all duration-200 hover:-translate-y-0.5">
              <div className="text-[0.68rem] font-bold tracking-wider text-[#4F46E5] mb-3">
                {c.label}
              </div>
              <div className="text-lg font-extrabold text-gray-900 mb-2 tracking-tight">
                {c.title}
              </div>
              <div className="text-sm text-gray-400 leading-relaxed mb-5 break-keep">
                {c.desc}
              </div>
              <span className="inline-flex items-center gap-1.5 text-sm font-bold text-[#4F46E5] group-hover:gap-2.5 transition-all">
                시작하기 <span aria-hidden>→</span>
              </span>
            </div>
          </Link>
        ))}
      </div>

      {/* 푸터 */}
      <p className="text-xs text-gray-300 tracking-wide">
        SURIT · 설계사에게 확신을 주다 · Powered by Google Gemini
      </p>
    </div>
  );
}

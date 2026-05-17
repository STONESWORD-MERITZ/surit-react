import { Link } from "react-router-dom";

const roleCards = [
  {
    label: "고객용",
    title: "내 보험 고지 점검",
    desc: "이미 가입한 보험이 청약 당시 병력 고지를 빠뜨리지 않았는지 점검합니다.",
    detail: "보험금 청구 때 문제가 될 수 있는 병력, 입원, 수술, 장기투약 기록을 먼저 확인합니다.",
    to: "/check",
    cta: "무료 점검 시작",
    accent: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  {
    label: "설계사용",
    title: "알릴의무 필터",
    desc: "건강보험심평원 PDF를 기준으로 상품 가입 전 고지 대상 병력을 정리합니다.",
    detail: "건강체, 간편심사 기준을 나눠 고객 상담용 결과와 전송 메시지를 빠르게 만듭니다.",
    to: "/disclosure?mode=agent",
    cta: "설계사용으로 이동",
    accent: "border-indigo-200 bg-indigo-50 text-indigo-700",
  },
];

const proofPoints = [
  {
    title: "고지는 가입 후가 아니라 청구 때 드러납니다",
    body: "가벼운 통원처럼 보여도 같은 코드로 반복되거나 30일 이상 투약되면 분쟁 포인트가 될 수 있습니다.",
  },
  {
    title: "기억이 아니라 원자료로 확인합니다",
    body: "기본진료, 세부진료, 처방조제 PDF를 함께 대조해 같은 결과가 반복되도록 설계했습니다.",
  },
  {
    title: "권유보다 점검에 맞춘 상담 흐름",
    body: "고객에게는 기존 가입의 안전성 점검으로, 설계사에게는 고지 누락 방지 도구로 안내합니다.",
  },
];

export default function Home() {
  return (
    <div className="space-y-10 pb-12">
      <section className="pt-8 md:pt-14">
        <div className="grid gap-8 md:grid-cols-[1.05fr_0.95fr] md:items-end">
          <div>
            <span className="inline-flex rounded-full bg-white px-3 py-1 text-xs font-bold text-[#4F46E5] shadow-sm">
              보험 고지사항 점검 플랫폼
            </span>
            <h1 className="mt-5 text-4xl font-black leading-tight tracking-tight text-gray-950 md:text-5xl">
              고지 누락은 작게 시작해도,
              <br />
              보험금 청구 때 크게 돌아옵니다.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-gray-600 break-keep">
              SURIT은 건강보험심평원 병력 PDF를 분석해 고객이 알렸어야 할 병력과
              설계사가 확인해야 할 고지 포인트를 한 화면에 정리합니다. 보험 가입
              권유가 아니라, 이미 가입한 보험이 안전한지 확인하는 점검 도구로도
              활용할 수 있습니다.
            </p>
          </div>

          <div className="rounded-[8px] border border-gray-200 bg-white p-5 shadow-[0_10px_35px_rgba(15,23,42,0.08)]">
            <p className="text-xs font-bold text-gray-400">무료 점검 안내 멘트</p>
            <p className="mt-3 text-lg font-extrabold leading-7 text-gray-900 break-keep">
              "보험 가입을 권유드리려는 게 아니라, 기존에 가입하신 보험이 병력
              고지사항을 잘 지켜서 가입됐는지 무료로 점검해드리고 있습니다."
            </p>
            <div className="mt-5 grid grid-cols-3 gap-2 text-center text-xs font-bold">
              <div className="rounded-[8px] bg-gray-50 px-2 py-3 text-gray-600">병력 PDF</div>
              <div className="rounded-[8px] bg-gray-50 px-2 py-3 text-gray-600">고지 기준</div>
              <div className="rounded-[8px] bg-gray-50 px-2 py-3 text-gray-600">누락 점검</div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {roleCards.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="group block rounded-[8px] border border-gray-200 bg-white p-6 shadow-[0_2px_12px_rgba(15,23,42,0.06)] transition hover:-translate-y-0.5 hover:shadow-[0_14px_35px_rgba(15,23,42,0.10)]"
          >
            <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-extrabold ${card.accent}`}>
              {card.label}
            </span>
            <h2 className="mt-4 text-2xl font-black tracking-tight text-gray-950">
              {card.title}
            </h2>
            <p className="mt-3 text-sm leading-6 text-gray-600 break-keep">{card.desc}</p>
            <p className="mt-3 text-xs leading-5 text-gray-400 break-keep">{card.detail}</p>
            <span className="mt-6 inline-flex items-center text-sm font-extrabold text-[#4F46E5]">
              {card.cta}
              <span className="ml-2 transition group-hover:translate-x-1" aria-hidden>
                →
              </span>
            </span>
          </Link>
        ))}
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        {proofPoints.map((item) => (
          <div key={item.title} className="rounded-[8px] border border-gray-200 bg-white p-5">
            <h3 className="text-sm font-extrabold text-gray-900 break-keep">{item.title}</h3>
            <p className="mt-2 text-xs leading-5 text-gray-500 break-keep">{item.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

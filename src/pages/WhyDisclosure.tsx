import { Link } from "react-router-dom";

const STATS = [
  {
    figure: "41.8%",
    label: "생명보험 보험금 부지급 사유 중 고지의무 위반 비중",
    note: "2023년 하반기 기준 · 약관상 면·부책에 이은 2번째 사유",
    source: "https://www.newstomato.com/ReadNews.aspx?no=1226350",
  },
  {
    figure: "88%",
    label: "손해보험 피해구제 신청 중 보험금 관련 분쟁 비중",
    note: "2022~2025년 상반기 접수 2,459건 중 2,165건",
    source: "https://www.khan.co.kr/article/202511091538001",
  },
  {
    figure: "64.2%",
    label: "손해보험 피해구제 사유 중 '보험금 미지급' 비중",
    note: "전체 신청의 절반 이상이 보험금을 못 받은 사례",
    source: "https://www.khan.co.kr/article/202511091538001",
  },
];

const CASES = [
  {
    tag: "설계사 구두 고지 미기록",
    title: "분명히 말했는데 — 기록이 없어 계약이 해지된 사례",
    body:
      "가입 전 위염 치료 사실을 설계사에게 구두로 알렸으나 보험사가 이를 기록하지 않아 " +
      "고지의무 위반으로 계약이 해지됐습니다. 분쟁조정을 거쳐서야 해지가 철회되고 " +
      "암진단비 5,000만원 지급이 권고됐습니다.",
    surit:
      "SURIT 은 심평원 PDF 원자료로 점검합니다. 기억·구두 확인이 아니라 객관적 기록 " +
      "기반이라 '말했다 / 못 들었다' 분쟁 자체가 생기지 않습니다.",
    source: "https://dazabi.com/insurance_magazine/article.php?id=6525",
  },
  {
    tag: "처방만 받고 미복용",
    title: "약을 먹지 않았어도 — 처방 사실 자체가 고지 대상",
    body:
      "가입 전 의료기관에서 투약 처방을 받았으나 실제로 복용하지 않아 고지하지 않은 사례. " +
      "금융분쟁조정위원회는 처방 사실 자체가 '질병 치료' 행위로 고지 대상이며 실제 복용 " +
      "여부와 무관하다고 보아 보험사의 해지를 정당하다고 판단했습니다.",
    surit:
      "SURIT 은 처방조제 PDF 까지 함께 분석합니다. 본인도 잊고 있던 처방 이력을 빠짐없이 " +
      "확인해 '몰라서 누락' 하는 위험을 막습니다.",
    source: "https://dazabi.com/insurance_magazine/article.php?id=6522",
  },
  {
    tag: "단 1건의 진단 누락",
    title: "고지혈증 하나를 빠뜨리고 — 뇌경색 보험금을 못 받은 사례",
    body:
      "척추 디스크 수술·전립선염 투약·고지혈증 진단 중 고지혈증 진단 이력만 빠뜨리고 " +
      "가입했다가, 이후 뇌경색 진단 시 계약 해지·보험금 부지급됐습니다.",
    surit:
      "SURIT 은 기본진료·세부진료·처방조제를 교차 분석해 질환별로 빠짐없이 정리합니다. " +
      "'이건 별거 아니겠지' 하고 넘어가는 항목을 시스템이 대신 잡아냅니다.",
    source: "https://www.insnews.co.kr/news/articleView.html?idxno=79080",
  },
];

const HOW = [
  {
    n: "01",
    title: "3종 PDF 교차 분석",
    body: "기본진료·세부진료·처방조제를 동시에 올려 통원·입원·수술·투약을 교차 검증합니다.",
  },
  {
    n: "02",
    title: "KCD 코드 룰셋",
    body: "100+ 개 KCD 코드 단위 결정론적 룰로 건강체·간편심사 고지 문항을 자동 분류합니다.",
  },
  {
    n: "03",
    title: "AI 의학 판단",
    body: "추가검사·재검사 여부와 치료 종결 여부를 AI 가 의학적 관점에서 추가 판단합니다.",
  },
];

export default function WhyDisclosure() {
  return (
    <div className="-mx-5 -mt-8">

      {/* ── HERO (다크) ──────────────────────────────────────── */}
      <section className="relative flex min-h-[52vh] items-center overflow-hidden bg-[#0F172A]">
        <div className="absolute inset-0 bg-gradient-to-br from-[#0F172A] via-[#1E1B4B] to-[#0F172A]" />
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
        <div className="relative mx-auto max-w-4xl px-6 py-20 text-center">
          <Link to="/" className="mb-8 inline-flex items-center gap-1.5 text-xs font-semibold text-gray-400 hover:text-gray-200 transition">
            ← 홈으로
          </Link>
          <p className="mt-4 text-xs font-bold uppercase tracking-[0.3em] text-indigo-300">
            Why It Matters
          </p>
          <h1 className="mt-5 text-4xl font-extrabold leading-tight text-white md:text-5xl break-keep">
            고지 누락은<br className="hidden md:inline" /> 작은 실수가 아닙니다
          </h1>
          <p className="mt-6 text-[15px] leading-8 text-gray-300 break-keep">
            수십 년 납입한 보험이 보험금 청구 순간 무너집니다.
            통계와 실제 분쟁 사례로 고지의무의 무게를 확인하세요.
          </p>
        </div>
      </section>

      {/* ── STATS (라이트) ───────────────────────────────────── */}
      <section className="bg-white py-20">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-12 text-center">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-600">The numbers</p>
            <h2 className="mt-4 text-2xl font-extrabold text-gray-950 md:text-3xl">숫자로 보는 현실</h2>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {STATS.map((s) => (
              <div
                key={s.figure}
                className="rounded-2xl border border-gray-200 bg-gray-50 px-8 py-9 text-center"
              >
                <p className="text-5xl font-extrabold text-indigo-600 md:text-6xl">{s.figure}</p>
                <p className="mt-4 text-[14px] font-semibold leading-6 text-gray-800 break-keep">
                  {s.label}
                </p>
                <p className="mt-2 text-xs leading-5 text-gray-400 break-keep">{s.note}</p>
                <a
                  href={s.source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-block text-xs text-gray-400 underline underline-offset-2 hover:text-indigo-500 transition"
                >
                  출처 보기
                </a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CASES (라이트) ───────────────────────────────────── */}
      <section className="bg-gray-50 py-20">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-12">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-600">Real cases</p>
            <h2 className="mt-4 text-2xl font-extrabold text-gray-950 md:text-3xl break-keep">
              실제 분쟁 사례
            </h2>
          </div>
          <div className="space-y-6">
            {CASES.map((c) => (
              <div key={c.tag} className="rounded-2xl border border-gray-200 bg-white p-8">
                <span className="inline-flex rounded-full bg-red-50 px-3 py-1 text-[11px] font-bold text-red-600">
                  {c.tag}
                </span>
                <h3 className="mt-4 text-lg font-bold text-gray-950 break-keep">{c.title}</h3>
                <p className="mt-3 text-[14px] leading-7 text-gray-600 break-keep">{c.body}</p>
                <div className="mt-5 rounded-xl bg-indigo-50 border border-indigo-100 px-6 py-4">
                  <p className="text-[13px] leading-6 text-indigo-700 break-keep">
                    <strong className="text-indigo-800">SURIT 은 </strong>
                    {c.surit.replace(/^SURIT 은 /, "")}
                  </p>
                </div>
                <a
                  href={c.source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 inline-block text-xs text-gray-400 underline underline-offset-2 hover:text-indigo-500 transition"
                >
                  출처 보기
                </a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW SURIT HELPS (다크) ───────────────────────────── */}
      <section className="bg-[#0F172A] py-20">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-12 text-center">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-300">How SURIT helps</p>
            <h2 className="mt-4 text-2xl font-extrabold text-white md:text-3xl break-keep">
              SURIT 이 이 문제를 해결하는 방법
            </h2>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {HOW.map((h) => (
              <div key={h.n} className="rounded-2xl border border-white/10 bg-white/5 px-7 py-8">
                <p className="text-xs font-mono font-bold text-indigo-400">{h.n}</p>
                <h3 className="mt-3 text-base font-bold text-white">{h.title}</h3>
                <p className="mt-2 text-[13px] leading-6 text-gray-400 break-keep">{h.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA (다크) ───────────────────────────────────────── */}
      <section className="bg-[#0F172A] pb-24 pt-4">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <Link
            to="/check"
            className="inline-flex rounded-xl bg-indigo-600 px-8 py-4 text-base font-bold text-white hover:bg-indigo-500 transition"
          >
            지금 무료로 점검하기 →
          </Link>
        </div>
      </section>

      {/* ── 면책 + 홈 링크 ───────────────────────────────────── */}
      <section className="bg-[#0a1020] py-10">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <p className="text-xs leading-6 text-gray-600 break-keep">
            ※ 본 페이지의 통계와 사례는 금융감독원 분쟁조정·보험협회 공시·언론 보도 자료를
            인용한 것으로, 개별 보험 계약의 해석은 약관과 보험회사 심사에 따릅니다.
            SURIT 은 참고용 점검 도구입니다.
          </p>
          <Link to="/" className="mt-6 inline-block text-xs font-semibold text-gray-500 hover:text-gray-300 transition">
            ← 홈으로
          </Link>
        </div>
      </section>

    </div>
  );
}

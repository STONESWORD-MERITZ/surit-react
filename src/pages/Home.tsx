import { Link } from "react-router-dom";
import SampleResultPreview from "../components/SampleResultPreview";

const STATS = [
  { value: "5분", label: "PDF 업로드부터 결과까지" },
  { value: "100+", label: "검증된 KCD 룰셋" },
  { value: "3종",  label: "심평원 PDF 동시 분석" },
];

const STEPS = [
  {
    n: "01",
    title: "설계사용 또는 고객용 선택",
    body: "청약 전 상담은 설계사용, 기존 보험 점검은 고객용에서 시작합니다.",
  },
  {
    n: "02",
    title: "청약 예정일 입력",
    body: "고지 기간 계산의 기준일입니다. 기존 보험 점검은 실제 가입일을 넣어 주세요.",
  },
  {
    n: "03",
    title: "PDF 첨부",
    body: "기본진료, 세부진료, 처방조제 PDF를 올리고 암호가 있으면 비밀번호를 입력합니다.",
  },
  {
    n: "04",
    title: "병력 요약 펼치기 또는 접기",
    body: "전체 병력 요약은 처음에는 접힌 상태입니다. 필요할 때 펼쳐 원자료 집계를 확인합니다.",
  },
  {
    n: "05",
    title: "카카오톡 복사하기",
    body: "상품 기준별 고지 메시지를 복사해 고객 안내나 내부 검토에 활용합니다.",
  },
  {
    n: "06",
    title: "하단 병력 확인하기",
    body: "질병별 카드에서 통원, 입원, 수술, 투약, 추가검사 의심 내용을 최종 확인합니다.",
  },
];

const ROLES = [
  {
    badge: "고객용",
    badgeClass: "text-emerald-700 bg-emerald-50 border-emerald-100",
    title: "내 보험 고지 점검",
    desc: "이미 가입한 보험이 청약 당시 병력 고지를 빠뜨리지 않았는지 무료로 확인합니다.",
    bullets: [
      "보험금 청구 때 분쟁이 될 만한 병력·입원·투약 기록을 미리 점검",
      "로그인 없이 즉시 사용 가능",
    ],
    to: "/check",
    cta: "무료 점검 시작",
    primary: true,
  },
  {
    badge: "설계사용",
    badgeClass: "text-indigo-700 bg-indigo-50 border-indigo-100",
    title: "알릴의무 필터",
    desc: "심평원 PDF 기준으로 건강체·간편심사 가입 전 고지 대상 병력을 자동 정리합니다.",
    bullets: [
      "고객 상담용 카카오톡 메시지 자동 생성",
      "메리츠 간편심사 예외질환 룰 내장",
    ],
    to: "/disclosure?mode=agent",
    cta: "설계사용 시작",
    primary: false,
  },
];

const PROOF_POINTS = [
  {
    title: "원자료 기반 분석",
    body: "기억이 아니라 심평원 PDF 원본을 직접 파싱합니다. 같은 자료로 같은 결과가 반복됩니다.",
  },
  {
    title: "AI 의학 판단 결합",
    body: "Google Gemini 의학 판단으로 '추가검사·재검사 여부' 와 '치료 종결 여부' 를 자동 분류합니다.",
  },
  {
    title: "보험사 룰셋 내장",
    body: "건강체 4문항·간편심사 3문항·메리츠 예외질환까지 코드 단위로 적용합니다.",
  },
];

export default function Home() {
  return (
    <div className="-mx-5 -mt-8 bg-gradient-to-b from-white via-white to-gray-50">
      {/* ── HERO ───────────────────────────────────────────── */}
      <section className="px-5 pt-14 pb-16 md:pt-20 md:pb-20">
        <div className="grid gap-10 md:grid-cols-[1.1fr_0.9fr] md:items-center">
          <div>
            <span className="inline-flex items-center rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">
              보험 알릴의무 점검 플랫폼
            </span>
            <h1 className="mt-5 text-4xl font-extrabold tracking-tight leading-[1.15] text-gray-950 md:text-5xl md:leading-[1.1] break-keep">
              PDF 한 번 올리면,
              <br className="hidden md:inline" /> 알릴의무 한 화면에.
            </h1>
            <p className="mt-5 max-w-xl text-[15px] leading-7 text-gray-600 break-keep">
              건강보험심평원 PDF 3장만 있으면 충분합니다. 통원·입원·수술·투약 기록을
              KCD 코드 단위로 자동 분류해 보험 가입·청구 때 알려야 할 항목을 한
              화면에 정리합니다.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link
                to="/check"
                className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-indigo-700 transition"
              >
                무료 점검 시작
                <span aria-hidden className="ml-2">→</span>
              </Link>
              <Link
                to="/disclosure?mode=agent"
                className="inline-flex items-center justify-center rounded-xl border border-gray-300 bg-white px-5 py-3 text-sm font-bold text-gray-800 hover:border-gray-400 transition"
              >
                설계사용 보기
              </Link>
            </div>
            <p className="mt-4 text-xs text-gray-400">
              본 결과는 AI 보조 도구가 제공하는 참고 자료입니다. 최종 판단은 보험회사 약관·언더라이팅에 따릅니다.
            </p>
          </div>

          {/* 우측: 샘플 결과 미니 */}
          <div className="hidden md:block">
            <SampleResultPreview />
          </div>
        </div>
      </section>

      {/* ── STATS ──────────────────────────────────────────── */}
      <section className="px-5 pb-16">
        <div className="grid gap-4 md:grid-cols-3">
          {STATS.map((s) => (
            <div
              key={s.label}
              className="rounded-2xl border border-gray-200 bg-white px-6 py-7 text-center md:text-left"
            >
              <p className="text-3xl md:text-4xl font-extrabold tracking-tight text-gray-950">
                {s.value}
              </p>
              <p className="mt-2 text-sm text-gray-500 break-keep">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── HOW IT WORKS ───────────────────────────────────── */}
      <section className="px-5 pb-20">
        <div className="mb-10">
          <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">
            How it works
          </p>
          <h2 className="mt-2 text-2xl md:text-3xl font-bold tracking-tight text-gray-950">
            처음 이용하는 순서
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step) => (
            <div
              key={step.n}
              className="rounded-2xl border border-gray-200 bg-white px-6 py-7"
            >
              <p className="text-xs font-mono font-bold text-indigo-600">{step.n}</p>
              <h3 className="mt-3 text-base font-bold text-gray-950">{step.title}</h3>
              <p className="mt-2 text-[13px] leading-6 text-gray-500 break-keep">
                {step.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── TWO PATHS ──────────────────────────────────────── */}
      <section className="px-5 pb-20">
        <div className="mb-10">
          <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">
            Use cases
          </p>
          <h2 className="mt-2 text-2xl md:text-3xl font-bold tracking-tight text-gray-950">
            누구를 위한 도구인가요
          </h2>
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          {ROLES.map((r) => (
            <Link
              key={r.to}
              to={r.to}
              className={`group block rounded-2xl border bg-white p-7 transition hover:-translate-y-0.5 hover:shadow-[0_14px_35px_rgba(15,23,42,0.08)] ${
                r.primary ? "border-indigo-200 shadow-[0_2px_12px_rgba(79,70,229,0.08)]" : "border-gray-200"
              }`}
            >
              <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${r.badgeClass}`}>
                {r.badge}
              </span>
              <h3 className="mt-4 text-xl font-bold tracking-tight text-gray-950">
                {r.title}
              </h3>
              <p className="mt-3 text-[14px] leading-6 text-gray-600 break-keep">
                {r.desc}
              </p>
              <ul className="mt-4 space-y-1.5">
                {r.bullets.map((b) => (
                  <li key={b} className="flex items-start gap-2 text-[13px] text-gray-500">
                    <span className="mt-1 inline-block h-1 w-1 rounded-full bg-gray-400 shrink-0" />
                    <span className="break-keep">{b}</span>
                  </li>
                ))}
              </ul>
              <span className={`mt-6 inline-flex items-center text-sm font-bold ${r.primary ? "text-indigo-600" : "text-gray-700"}`}>
                {r.cta}
                <span aria-hidden className="ml-2 transition group-hover:translate-x-1">
                  →
                </span>
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* ── PROOF POINTS ───────────────────────────────────── */}
      <section className="px-5 pb-24">
        <div className="mb-10">
          <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">
            Why SURIT
          </p>
          <h2 className="mt-2 text-2xl md:text-3xl font-bold tracking-tight text-gray-950">
            기억이 아니라 데이터로 점검합니다
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {PROOF_POINTS.map((p) => (
            <div
              key={p.title}
              className="rounded-2xl border border-gray-200 bg-white px-6 py-7"
            >
              <h3 className="text-base font-bold text-gray-950 break-keep">
                {p.title}
              </h3>
              <p className="mt-2 text-[13px] leading-6 text-gray-500 break-keep">
                {p.body}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

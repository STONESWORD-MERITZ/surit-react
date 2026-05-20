import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

// ── 카운트업 훅 ───────────────────────────────────────────────
function useCountUp(target: number, duration = 1800, active = false) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!active) return;
    setCount(0);
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - elapsed, 3);
      setCount(Math.round(eased * target));
      if (elapsed < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [target, duration, active]);
  return count;
}

function StatCard({ value, suffix, label, delay }: { value: number; suffix: string; label: string; delay: number }) {
  const [active, setActive] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const count = useCountUp(value, 1800, active);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setActive(true); obs.disconnect(); } },
      { threshold: 0.4 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={ref} className="text-center" style={{ transitionDelay: `${delay}ms` }}>
      <p className="text-5xl font-extrabold tabular-nums text-white md:text-6xl">
        {count}<span className="text-indigo-400">{suffix}</span>
      </p>
      <p className="mt-3 text-sm leading-relaxed text-gray-400 break-keep">{label}</p>
    </div>
  );
}

// ── 데이터 ────────────────────────────────────────────────────
const STATS = [
  { value: 100, suffix: "+", label: "검증된 KCD 코드 룰셋" },
  { value: 7,   suffix: "개", label: "자동 분류 알릴의무 문항" },
  { value: 3,   suffix: "종", label: "동시 분석 심평원 PDF" },
  { value: 5,   suffix: "분", label: "업로드부터 결과까지" },
];

const ROADMAP = [
  {
    phase: "STEP 01", status: "현재 운영",
    title: "알릴의무 점검",
    body: "심평원 PDF 를 분석해 보험 가입·청구 시 알려야 할 병력을 자동 정리.",
    active: true,
  },
  {
    phase: "STEP 02", status: "개발 예정",
    title: "보장분석 필터",
    body: "기존 보장과 신규 제안서를 비교해 중복·공백을 한눈에.",
    active: false,
  },
  {
    phase: "STEP 03", status: "로드맵",
    title: "권리 보호 서비스 통합",
    body: "보험 소비자·설계사 권리 증진을 위한 서비스를 단계적으로 통합.",
    active: false,
  },
];

const VALUES = [
  { k: "정확성", e: "Accuracy",     body: "KCD 코드 단위 결정론적 룰 + AI 의학 판단으로 누락 없이 분류." },
  { k: "중립성", e: "Neutrality",   body: "특정 보험사·상품을 권유하지 않습니다. 사실만 정리합니다." },
  { k: "투명성", e: "Transparency", body: "왜 이 항목이 고지 대상인지 근거를 함께 보여줍니다." },
  { k: "안전성", e: "Privacy",      body: "분석 결과는 서버에 저장되지 않습니다. 본인 디바이스에서만." },
];

// ── 페이드인 공통 래퍼 ─────────────────────────────────────────
function FadeIn({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [vis, setVis] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVis(true); obs.disconnect(); } },
      { threshold: 0.1 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: vis ? 1 : 0,
        transform: vis ? "translateY(0)" : "translateY(24px)",
        transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

export default function Home() {
  return (
    <div className="-mx-5 -mt-8">

      {/* ── 1. HERO (다크 풀스크린) ──────────────────────────── */}
      <section className="relative flex min-h-[88vh] items-center overflow-hidden bg-[#0F172A]">
        <div className="absolute inset-0 bg-gradient-to-br from-[#0F172A] via-[#1E1B4B] to-[#0F172A]" />
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
        <div className="relative mx-auto max-w-6xl px-6 py-20">
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-indigo-300">
            Insurance Disclosure Intelligence
          </p>
          <h1 className="mt-6 text-5xl font-extrabold leading-[1.05] tracking-tight text-white md:text-7xl">
            KNOW BEFORE
            <br />
            YOU SIGN
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-8 text-gray-300 break-keep">
            보험은 가입하는 순간이 아니라 보험금을 청구하는 순간 진실이 드러납니다.
            SURIT 은 건강보험심평원 원자료를 분석해 고객과 설계사가 알아야 할
            고지 사항을 한 화면에 정리합니다.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link
              to="/check"
              className="rounded-xl bg-indigo-600 px-6 py-3.5 text-sm font-bold text-white hover:bg-indigo-500 transition"
            >
              무료 점검 시작 →
            </Link>
            <Link
              to="/why"
              className="rounded-xl border border-white/25 px-6 py-3.5 text-sm font-bold text-white hover:bg-white/10 transition"
            >
              왜 중요한가요?
            </Link>
          </div>
        </div>
      </section>

      {/* ── 2. MISSION (라이트) ──────────────────────────────── */}
      <section className="bg-white py-24">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <FadeIn>
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-600">Our Mission</p>
            <h2 className="mt-5 text-3xl font-extrabold leading-snug text-gray-950 md:text-4xl break-keep">
              보험 가입 시 고객과 설계사 모두의 권리를 지킵니다
            </h2>
            <p className="mt-6 text-[15px] leading-8 text-gray-600 break-keep">
              고지 누락은 가입자에게는 보험금 부지급·계약 해지의 위험으로,
              설계사에게는 불완전판매 분쟁의 위험으로 돌아옵니다. SURIT 은 기억이나
              구두 확인이 아닌 <strong>원자료 기반 점검</strong>으로 양측 모두를 보호합니다.
            </p>
          </FadeIn>
        </div>
      </section>

      {/* ── 3. STATS (다크, 카운트업) ────────────────────────── */}
      <section className="bg-[#0F172A] py-24">
        <div className="mx-auto max-w-6xl px-6">
          <FadeIn className="mb-14 text-center">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-300">By the numbers</p>
          </FadeIn>
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
            {STATS.map((s, i) => (
              <StatCard key={s.label} value={s.value} suffix={s.suffix} label={s.label} delay={i * 100} />
            ))}
          </div>
        </div>
      </section>

      {/* ── 4. SERVICE ROADMAP (라이트) ──────────────────────── */}
      <section className="bg-gray-50 py-24">
        <div className="mx-auto max-w-6xl px-6">
          <FadeIn className="mb-14">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-600">Service Roadmap</p>
            <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-gray-950 md:text-4xl break-keep">
              지금의 SURIT 과 앞으로의 SURIT
            </h2>
          </FadeIn>
          <div className="grid gap-6 md:grid-cols-3">
            {ROADMAP.map((r, i) => (
              <FadeIn key={r.phase} delay={i * 120}>
                <div
                  className={`rounded-2xl border p-7 h-full ${
                    r.active
                      ? "border-indigo-200 bg-white shadow-[0_2px_20px_rgba(79,70,229,0.09)]"
                      : "border-gray-200 bg-white"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-4">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
                        r.active
                          ? "bg-indigo-600 text-white"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {r.phase}
                    </span>
                    <span
                      className={`text-[11px] font-semibold ${
                        r.active ? "text-indigo-600" : "text-gray-400"
                      }`}
                    >
                      {r.status}
                    </span>
                  </div>
                  <h3
                    className={`text-lg font-bold tracking-tight ${
                      r.active ? "text-gray-950" : "text-gray-500"
                    }`}
                  >
                    {r.title}
                  </h3>
                  <p className="mt-2 text-[13px] leading-6 text-gray-500 break-keep">{r.body}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── 5. CORE VALUES (라이트) ──────────────────────────── */}
      <section className="bg-white py-24">
        <div className="mx-auto max-w-6xl px-6">
          <FadeIn className="mb-14">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-600">Core Values</p>
            <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-gray-950 md:text-4xl">
              우리가 지키는 원칙
            </h2>
          </FadeIn>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map((v, i) => (
              <FadeIn key={v.k} delay={i * 80}>
                <div className="rounded-2xl border border-gray-200 bg-gray-50 px-6 py-7 h-full">
                  <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-indigo-600">{v.e}</p>
                  <h3 className="mt-2 text-xl font-extrabold text-gray-950">{v.k}</h3>
                  <p className="mt-3 text-[13px] leading-6 text-gray-500 break-keep">{v.body}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── 6. WHY 진입 (다크) ───────────────────────────────── */}
      <section className="bg-[#0F172A] py-24">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <FadeIn>
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-300">Why It Matters</p>
            <h2 className="mt-5 text-3xl font-extrabold leading-snug text-white md:text-4xl break-keep">
              고지 누락은 작은 실수가 아닙니다
            </h2>
            <p className="mt-6 text-[15px] leading-8 text-gray-300 break-keep">
              생명보험 보험금 부지급 사유의{" "}
              <strong className="text-white">41.8%</strong> 가 고지의무 위반입니다.
              손해보험 피해구제 신청의{" "}
              <strong className="text-white">88%</strong> 가 보험금 분쟁입니다.
              실제 분쟁 사례와 통계로 그 위험을 확인하세요.
            </p>
            <Link
              to="/why"
              className="mt-8 inline-flex rounded-xl bg-white px-6 py-3.5 text-sm font-bold text-[#0F172A] hover:bg-gray-100 transition"
            >
              고지 누락 피해 사례 보기 →
            </Link>
          </FadeIn>
        </div>
      </section>

      {/* ── 7. TWO PATHS (라이트) ────────────────────────────── */}
      <section className="bg-white py-24">
        <div className="mx-auto max-w-6xl px-6">
          <FadeIn className="mb-14">
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-indigo-600">Use cases</p>
            <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-gray-950 md:text-4xl break-keep">
              누구를 위한 도구인가요
            </h2>
          </FadeIn>
          <div className="grid gap-6 md:grid-cols-2">
            <FadeIn delay={0}>
              <Link
                to="/check"
                className="group block rounded-2xl border border-indigo-200 bg-white p-8 shadow-[0_2px_12px_rgba(79,70,229,0.08)] transition hover:-translate-y-0.5 hover:shadow-[0_14px_35px_rgba(79,70,229,0.12)] h-full"
              >
                <span className="inline-flex rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700">
                  고객용
                </span>
                <h3 className="mt-4 text-xl font-bold tracking-tight text-gray-950">내 보험 고지 점검</h3>
                <p className="mt-3 text-[14px] leading-6 text-gray-600 break-keep">
                  이미 가입한 보험이 청약 당시 병력 고지를 빠뜨리지 않았는지 무료로 확인합니다.
                </p>
                <ul className="mt-4 space-y-1.5">
                  {["보험금 청구 때 분쟁이 될 만한 병력·입원·투약 기록을 미리 점검", "로그인 없이 즉시 사용 가능"].map(b => (
                    <li key={b} className="flex items-start gap-2 text-[13px] text-gray-500">
                      <span className="mt-1.5 inline-block h-1 w-1 shrink-0 rounded-full bg-gray-400" />
                      <span className="break-keep">{b}</span>
                    </li>
                  ))}
                </ul>
                <span className="mt-6 inline-flex items-center text-sm font-bold text-indigo-600">
                  무료 점검 시작
                  <span aria-hidden className="ml-2 transition group-hover:translate-x-1">→</span>
                </span>
              </Link>
            </FadeIn>
            <FadeIn delay={120}>
              <Link
                to="/disclosure?mode=agent"
                className="group block rounded-2xl border border-gray-200 bg-white p-8 transition hover:-translate-y-0.5 hover:shadow-[0_14px_35px_rgba(15,23,42,0.07)] h-full"
              >
                <span className="inline-flex rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-0.5 text-[11px] font-bold text-indigo-700">
                  설계사용
                </span>
                <h3 className="mt-4 text-xl font-bold tracking-tight text-gray-950">알릴의무 필터</h3>
                <p className="mt-3 text-[14px] leading-6 text-gray-600 break-keep">
                  심평원 PDF 기준으로 건강체·간편심사 가입 전 고지 대상 병력을 자동 정리합니다.
                </p>
                <ul className="mt-4 space-y-1.5">
                  {["고객 상담용 카카오톡 메시지 자동 생성", "메리츠 간편심사 예외질환 룰 내장"].map(b => (
                    <li key={b} className="flex items-start gap-2 text-[13px] text-gray-500">
                      <span className="mt-1.5 inline-block h-1 w-1 shrink-0 rounded-full bg-gray-400" />
                      <span className="break-keep">{b}</span>
                    </li>
                  ))}
                </ul>
                <span className="mt-6 inline-flex items-center text-sm font-bold text-gray-700">
                  설계사용 시작
                  <span aria-hidden className="ml-2 transition group-hover:translate-x-1">→</span>
                </span>
              </Link>
            </FadeIn>
          </div>
        </div>
      </section>

      {/* ── 8. CTA (다크) ────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-[#0F172A] py-28">
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "radial-gradient(circle, #fff 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />
        <div className="relative mx-auto max-w-4xl px-6 text-center">
          <FadeIn>
            <h2 className="text-3xl font-extrabold text-white md:text-5xl break-keep">
              지금 바로 확인하세요
            </h2>
            <p className="mt-5 text-[15px] leading-8 text-gray-400 break-keep">
              PDF 3장이면 충분합니다. 5분 안에 알릴의무 전체를 정리합니다.
            </p>
            <Link
              to="/check"
              className="mt-8 inline-flex rounded-xl bg-indigo-600 px-8 py-4 text-base font-bold text-white hover:bg-indigo-500 transition"
            >
              무료 점검 시작 →
            </Link>
            <p className="mt-4 text-xs text-gray-600">
              본 결과는 AI 보조 도구가 제공하는 참고 자료입니다. 최종 판단은 보험회사 약관·언더라이팅에 따릅니다.
            </p>
          </FadeIn>
        </div>
      </section>

    </div>
  );
}

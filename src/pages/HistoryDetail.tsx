import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getDisclosureResult, type SavedResult } from "../lib/disclosureStorage";
import { DisclaimerBox, DisclosureSection } from "../components/disclosure";
import type { AudienceMode, SummaryItem } from "../types/disclosure";

type StoredReports = {
  standard?: Record<string, SummaryItem[]>;
  easy?: Record<string, SummaryItem[]>;
  standard_kakao?: string;
  easy_kakao?: string;
  all_disease_summary?: unknown[];
  meritz_easy_message?: string;
  parse_errors?: string[];
  warnings?: string[];
};

export default function HistoryDetail() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<SavedResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getDisclosureResult(id)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "조회 실패"));
  }, [id]);

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10 text-red-600">{error}</main>
    );
  }
  if (!data) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10 text-gray-400">불러오는 중…</main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-gray-400">
            {new Date(data.created_at).toLocaleString("ko-KR")} 저장
          </p>
          <h1 className="mt-1 text-2xl font-extrabold text-gray-950">
            {data.title || `${data.ref_date} 점검`}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {data.product_type} · 기준일 {data.ref_date}
          </p>
        </div>
        <Link
          to="/history"
          className="shrink-0 text-sm font-bold text-gray-600 hover:text-gray-900"
        >
          ← 기록 목록
        </Link>
      </div>

      <ResultReplay saved={data} />
    </main>
  );
}

function ResultReplay({ saved }: { saved: SavedResult }) {
  const [tab, setTab] = useState<"standard" | "easy">("standard");
  const reports = saved.summary_reports as StoredReports;

  const standardReports = reports.standard ?? {};
  const easyReports = reports.easy ?? {};
  const standardKakao = reports.standard_kakao ?? "";
  const easyKakao = reports.easy_kakao ?? "";
  const meritzMsg = reports.meritz_easy_message ?? "";
  const parseErrors = reports.parse_errors ?? [];
  const warnings = reports.warnings ?? [];

  const stdCount = Object.values(standardReports).reduce((s, arr) => s + arr.length, 0);
  const easyCount = Object.values(easyReports).reduce((s, arr) => s + arr.length, 0);

  const activeReports = tab === "standard" ? standardReports : easyReports;
  const activeMemo = tab === "standard" ? standardKakao : easyKakao;
  const activeLabel = tab === "standard" ? "건강체/표준체" : "간편심사";

  // Determine mode from product_type for memo label text
  const mode: AudienceMode = saved.product_type === "고객 점검" ? "customer" : "agent";

  return (
    <div>
      {parseErrors.map((e, i) => (
        <div
          key={`parse-${i}`}
          className="mb-3 rounded-[8px] bg-amber-50 p-3 text-sm font-semibold text-amber-700"
        >
          {e}
        </div>
      ))}

      {warnings.map((w, i) => (
        <div key={`warn-${i}`} className="mb-3 rounded-[8px] bg-gray-50 p-3 text-sm text-gray-600">
          {w}
        </div>
      ))}

      {meritzMsg && (
        <div className="mb-4 whitespace-pre-wrap rounded-[8px] border border-orange-200 bg-orange-50 p-4 text-xs leading-relaxed text-orange-800">
          {meritzMsg}
        </div>
      )}

      <section className="mb-5 overflow-hidden rounded-[8px] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
        <div className="flex border-b border-gray-100">
          {(["standard", "easy"] as const).map((t) => {
            const label = t === "standard" ? "건강체/표준체" : "간편심사";
            const count = t === "standard" ? stdCount : easyCount;
            const active = tab === t;
            return (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`relative flex-1 py-3.5 text-sm font-bold transition-all ${
                  active ? "text-[#4F46E5]" : "text-gray-400 hover:text-gray-600"
                }`}
              >
                {label}
                {count > 0 && (
                  <span
                    className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs font-semibold ${
                      active ? "bg-indigo-100 text-indigo-600" : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {count}
                  </span>
                )}
                {active && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4F46E5]" />
                )}
              </button>
            );
          })}
        </div>

        <div className="p-4">
          <DisclosureSection
            reports={activeReports}
            memo={activeMemo}
            label={`${activeLabel} 고지 대상 항목이 없습니다.`}
            mode={mode}
          />
        </div>
      </section>

      <DisclaimerBox show />
    </div>
  );
}

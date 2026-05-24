import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AnalysisProgress from "../components/AnalysisProgress";
import { useAuth } from "../lib/auth-context";

const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

type AudienceMode = "customer" | "agent";

function connectionErrorMessage(apiBase: string): string {
  if (typeof console !== "undefined") {
    console.error("[SURIT] API 연결 실패:", apiBase);
  }
  return "서버에 연결하지 못했어요. 인터넷 연결을 확인하시고 잠시 후 다시 시도해 주세요. 문제가 계속되면 관리자에게 문의해 주세요.";
}

type DiseaseSummary = {
  code: string;
  display_code?: string;
  name: string;
  first_date: string;
  latest_date: string;
  visit_count: number;
  inpatient_count: number;
  inpatient_days: number;
  surgery_count: number;
  med_days: number;
  hospitals: string[];
};

type SummaryItem = {
  first_date: string;
  latest_date: string;
  first_diagnosis_date: string;
  code: string;
  display_code?: string;
  name: string;
  visit: number;
  med_days: number;
  med_days_30plus?: boolean;
  inpatient: number;
  inpatient_count: number;
  inpatient_periods?: { start: string; end: string; days: number }[];
  surgery_count?: number;
  surgeries: string[];
  procedures?: string[];
  surgery_suspected?: string[];
  additional_test_hit?: boolean;
  additional_test_reason?: string;
  treatment_ongoing?: boolean | null;
  treatment_ongoing_reason?: string;
  hospitals: string[];
  first_hospital?: string;
  last_hospital?: string;
  detail: string;
};

type AnalyzeResult = {
  flagged_count: number;
  total_q_count: number;
  total_visit_sum: number;
  total_med_sum: number;
  standard_reports: Record<string, SummaryItem[]>;
  easy_reports: Record<string, SummaryItem[]>;
  all_disease_summary: DiseaseSummary[];
  standard_kakao: string;
  easy_kakao: string;
  parse_errors: string[];
  warnings: string[];
  meritz_easy_message: string;
};

type Risk = "red" | "orange" | "gray" | "yellow" | "green";
type TourPhase = "pre" | "post";

const TOUR_STORAGE_KEY = "surit_tour_seen_v1";
function readTourSeen(): { pre: boolean; post: boolean } {
  if (typeof window === "undefined") return { pre: false, post: false };
  try {
    const raw = window.localStorage.getItem(TOUR_STORAGE_KEY);
    if (!raw) return { pre: false, post: false };
    const v = JSON.parse(raw);
    return { pre: !!v.pre, post: !!v.post };
  } catch {
    return { pre: false, post: false };
  }
}
function markTourSeen(phase: "pre" | "post") {
  if (typeof window === "undefined") return;
  try {
    const cur = readTourSeen();
    cur[phase] = true;
    window.localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify(cur));
  } catch { /* localStorage 비활성 환경 무시 */ }
}
type TourStep = {
  target: string;
  title: string;
  body: string;
};

const modeCopy: Record<AudienceMode, {
  badge: string;
  title: string;
  subtitle: string;
  dateLabel: string;
  dateHelp: string;
  uploadHelp: string;
  button: string;
  emptyTitle: string;
  resultTitle: string;
  memoLabel: string;
}> = {
  customer: {
    badge: "고객용 무료 점검",
    title: "내 보험 고지 점검",
    subtitle: "이전에 가입한 보험이 청약 당시 병력 고지사항을 잘 지켜 가입됐는지 확인합니다.",
    dateLabel: "가입일 또는 점검 기준일",
    dateHelp: "이미 가입한 보험을 확인할 때는 해당 상품의 청약일을 넣어 주세요.",
    uploadHelp: "건강e음에서 발급한 기본진료, 세부진료, 처방조제 PDF를 올려 주세요.",
    button: "내 고지 리스크 점검",
    emptyTitle: "현재 기준으로 뚜렷한 고지 검토 항목이 없습니다.",
    resultTitle: "가입 당시 고지 검토 결과",
    memoLabel: "고객 안내용 점검 메모",
  },
  agent: {
    badge: "설계사용",
    title: "알릴의무 필터",
    subtitle: "심평원 병력 PDF를 기준으로 건강체와 간편심사 고지 대상 병력을 정리합니다.",
    dateLabel: "청약 예정일",
    dateHelp: "상품 가입 예정일 기준으로 3개월, 1년, 5년, 10년 기간을 계산합니다.",
    uploadHelp: "기본진료, 세부진료, 처방조제 PDF를 함께 올리면 정확도가 올라갑니다.",
    button: "AI 고지사항 추출",
    emptyTitle: "선택한 상품 기준의 고지 대상 항목이 없습니다.",
    resultTitle: "상품별 고지사항",
    memoLabel: "카카오 전송용 메시지",
  },
};

function riskOf(item: SummaryItem): Risk {
  const surgN = item.surgery_count ?? item.surgeries?.length ?? 0;
  const procN = item.procedures?.length ?? 0;
  const suspN = item.surgery_suspected?.length ?? 0;
  if (item.inpatient > 0 || surgN > 0) return "red";
  if (procN > 0) return "orange";
  if (suspN > 0) return "gray";
  if (item.med_days >= 30 || item.visit >= 7) return "yellow";
  return "green";
}

const RISK: Record<Risk, { border: string }> = {
  red: { border: "border-red-400" },
  orange: { border: "border-orange-400" },
  gray: { border: "border-gray-400" },
  yellow: { border: "border-amber-400" },
  green: { border: "border-emerald-400" },
};

function Chip({ label, tone = "gray" }: { label: string; tone?: string }) {
  const tones: Record<string, string> = {
    gray: "bg-gray-100 text-gray-600",
    "gray-light": "border border-gray-200 bg-gray-50 text-gray-500",
    red: "bg-red-100 text-red-600",
    "red-light": "border border-red-200 bg-red-50 text-red-500",
    amber: "bg-amber-100 text-amber-700",
    emerald: "bg-emerald-100 text-emerald-700",
    orange: "bg-orange-100 text-orange-600",
    indigo: "bg-indigo-100 text-indigo-600",
    rose: "bg-rose-100 text-rose-600",
  };
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tones[tone] ?? tones.gray}`}>
      {label}
    </span>
  );
}

function extractQNumber(qTitle: string): string {
  const exact = qTitle.match(/(\d+)\s*번\s*질문/);
  if (exact) return `Q${exact[1]}`;
  if (qTitle.includes("참고")) return "참고";
  const any = qTitle.match(/\d+/);
  return any ? `Q${any[0]}` : "Q";
}

function cleanQTitle(qTitle: string): string {
  return qTitle.replace(/^\[.*?\]\s*/, "");
}

function AllDiseaseSection({ diseases }: { diseases: DiseaseSummary[] }) {
  const [open, setOpen] = useState(false);

  if (!diseases.length) return null;

  return (
    <section data-tour="summary" className="mb-5 overflow-hidden rounded-[8px] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <span className="text-sm font-extrabold text-gray-900">전체 병력 요약</span>
          <span className="ml-2 text-xs font-semibold text-gray-400">{diseases.length}개 질환</span>
        </div>
        <span className="text-xs font-bold text-gray-400">{open ? "접기" : "펼치기"}</span>
      </button>

      {open && (
        <div className="border-t border-gray-100">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-gray-500">
                  <th className="px-4 py-2.5 text-left">코드</th>
                  <th className="px-4 py-2.5 text-left">질병명</th>
                  <th className="px-4 py-2.5 text-left">진료기간</th>
                  <th className="px-4 py-2.5 text-center">통원</th>
                  <th className="px-4 py-2.5 text-center">입원</th>
                  <th className="px-4 py-2.5 text-center">수술</th>
                  <th className="px-4 py-2.5 text-center">투약</th>
                  <th className="px-4 py-2.5 text-left">병원</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {diseases.map((d, i) => (
                  <tr key={`${d.code}-${i}`} className="hover:bg-gray-50/60">
                    <td className="px-4 py-2 font-mono text-gray-500">{d.display_code || d.code}</td>
                    <td className="max-w-[180px] truncate px-4 py-2 font-semibold text-gray-800">{d.name || "-"}</td>
                    <td className="whitespace-nowrap px-4 py-2 text-gray-500">
                      {d.first_date}
                      {d.latest_date && d.latest_date !== d.first_date ? ` ~ ${d.latest_date}` : ""}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {d.visit_count > 0 ? (
                        <span className={`font-semibold ${d.visit_count >= 7 ? "text-amber-600" : "text-gray-600"}`}>
                          {d.visit_count}회
                        </span>
                      ) : <span className="text-gray-300">-</span>}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {d.inpatient_days > 0 ? (
                        <span className="font-semibold text-red-500">{d.inpatient_days}일</span>
                      ) : <span className="text-gray-300">-</span>}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {d.surgery_count > 0 ? (
                        <span className="font-semibold text-red-500">{d.surgery_count}건</span>
                      ) : <span className="text-gray-300">-</span>}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {d.med_days > 0 ? (
                        <span className={`font-semibold ${d.med_days >= 30 ? "text-amber-600" : "text-emerald-600"}`}>
                          {d.med_days}일
                        </span>
                      ) : <span className="text-gray-300">-</span>}
                    </td>
                    <td className="max-w-[180px] truncate px-4 py-2 text-gray-500">
                      {(d.hospitals || []).slice(0, 2).join(", ") || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

function DiseaseCard({ item, qNum }: { item: SummaryItem; qNum: string }) {
  const risk = riskOf(item);
  const surgN = item.surgery_count ?? item.surgeries?.length ?? 0;
  const procN = item.procedures?.length ?? 0;
  const suspN = item.surgery_suspected?.length ?? 0;
  const period = item.first_date && item.latest_date && item.first_date !== item.latest_date
    ? `${item.first_date} ~ ${item.latest_date}`
    : (item.first_date || "");
  const hasBottom = suspN > 0 || item.additional_test_hit || item.treatment_ongoing != null;

  return (
    <article className={`border-l-4 px-5 py-4 ${RISK[risk].border}`}>
      <div className="mb-1 flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="text-[15px] font-bold text-gray-900">{item.name || "질병명 없음"}</span>
          {item.code && (
            <span className="shrink-0 rounded bg-gray-100 px-2 py-0.5 font-mono text-[11px] text-gray-500">
              {item.display_code || item.code}
            </span>
          )}
        </div>
        <span className="shrink-0 rounded-[8px] bg-[#4F46E5] px-2 py-0.5 text-[11px] font-bold text-white">
          {qNum}
        </span>
      </div>

      <div className="mb-2.5 space-y-0.5 text-xs text-gray-500">
        {period && (
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-gray-400">진료기간</span>
            <span>{period}</span>
            {item.last_hospital && <span className="truncate text-gray-400">{item.last_hospital}</span>}
          </div>
        )}
        {item.first_diagnosis_date && (
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-gray-400">최초진단</span>
            <span>{item.first_diagnosis_date}</span>
            {item.first_hospital && <span className="truncate text-gray-400">{item.first_hospital}</span>}
          </div>
        )}
      </div>

      {item.detail && (
        <div className="mb-3 text-[13px] font-medium leading-relaxed text-gray-700">
          {item.detail}
        </div>
      )}

      <div className="mb-2 flex flex-wrap gap-2">
        <Chip label={`통원 ${item.visit ?? 0}회`} tone={(item.visit ?? 0) >= 7 ? "amber" : "gray"} />
        <Chip label={`입원 ${item.inpatient ?? 0}일`} tone={(item.inpatient ?? 0) > 0 ? "red" : "gray"} />
        <Chip label={`입원 ${item.inpatient_count ?? 0}회`} tone={(item.inpatient_count ?? 0) > 0 ? "red-light" : "gray"} />
        <Chip label={`수술 ${surgN}건`} tone={surgN > 0 ? "red" : "gray"} />
        <Chip
          label={`투약 ${item.med_days ?? 0}일`}
          tone={(item.med_days ?? 0) >= 30 ? "amber" : (item.med_days ?? 0) > 0 ? "emerald" : "gray"}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {procN > 0 && <Chip label={`시술 ${procN}건`} tone="orange" />}
        {suspN > 0 && <Chip label={`수술 의심 ${suspN}건`} tone="gray-light" />}
        {item.additional_test_hit && <Chip label="추가검사 의심" tone="indigo" />}
        {item.treatment_ongoing === true && <Chip label="치료 중" tone="rose" />}
        {item.treatment_ongoing === false && <Chip label="종결" tone="emerald" />}
      </div>

      {hasBottom && (
        <div className="mt-3 space-y-1 border-t border-gray-100 pt-2.5 text-xs leading-relaxed">
          {suspN > 0 && (
            <p className="text-gray-500">
              <span className="mr-1.5 text-gray-400">의심 행위</span>
              {item.surgery_suspected!.slice(0, 3).join(", ")}
            </p>
          )}
          {item.additional_test_hit && item.additional_test_reason && (
            <p className="text-indigo-600">
              <span className="mr-1.5 text-indigo-300">추가검사</span>
              {item.additional_test_reason}
            </p>
          )}
          {item.treatment_ongoing === true && item.treatment_ongoing_reason && (
            <p className="text-rose-600">
              <span className="mr-1.5 text-rose-300">치료 중</span>
              {item.treatment_ongoing_reason}
            </p>
          )}
          {item.treatment_ongoing === false && item.treatment_ongoing_reason && (
            <p className="text-emerald-600">
              <span className="mr-1.5 text-emerald-400">종결</span>
              {item.treatment_ongoing_reason}
            </p>
          )}
        </div>
      )}
    </article>
  );
}

function DisclosureSection({
  reports,
  memo,
  label,
  mode,
}: {
  reports: Record<string, SummaryItem[]>;
  memo: string;
  label: string;
  mode: AudienceMode;
}) {
  const [memoOpen, setMemoOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const copy = modeCopy[mode];
  const hasItems = Object.keys(reports).length > 0;

  const handleCopy = () => {
    void navigator.clipboard.writeText(memo);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      {memo && (
        <section data-tour="copy" className="mb-4 overflow-hidden rounded-[8px] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="flex items-center justify-between gap-3 px-5 py-4">
            <button type="button" onClick={() => setMemoOpen(!memoOpen)} aria-expanded={memoOpen} className="text-left text-sm font-bold text-gray-800">
              {copy.memoLabel}
              <span className="ml-2 text-xs text-gray-400">{memoOpen ? "접기" : "펼치기"}</span>
            </button>
            <button
              onClick={handleCopy}
              className="rounded-[8px] bg-[#FEE500] px-4 py-2 text-sm font-bold text-[#191919]"
            >
              {copied ? "복사 완료" : "복사하기"}
            </button>
          </div>
          {memoOpen && (
            <pre className="whitespace-pre-wrap bg-gray-50 px-5 py-4 font-sans text-xs leading-relaxed text-gray-600">
              {memo}
            </pre>
          )}
        </section>
      )}

      {hasItems ? (
        <div data-tour="cards" className="space-y-4">
          {Object.entries(reports).map(([qTitle, items]) => {
            const qNum = extractQNumber(qTitle);
            return (
              <section key={qTitle} className="overflow-hidden rounded-[8px] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
                <div className="flex items-center gap-2.5 border-b border-gray-100 px-5 py-3.5">
                  <span className="shrink-0 rounded-[8px] bg-[#4F46E5] px-2.5 py-1 text-xs font-bold text-white">
                    {qNum}
                  </span>
                  <h3 className="text-sm font-bold text-gray-800">{cleanQTitle(qTitle)}</h3>
                </div>
                <div className="divide-y divide-gray-50">
                  {[...items].sort((a, b) => {
                    const al = a.latest_date || a.first_date || "";
                    const bl = b.latest_date || b.first_date || "";
                    if (al !== bl) return bl.localeCompare(al);
                    return (b.first_date || "").localeCompare(a.first_date || "");
                  }).map((item, idx) => (
                    <DiseaseCard key={`${item.code}-${idx}`} item={item} qNum={qNum} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div data-tour="cards" className="rounded-[8px] bg-emerald-50 p-8 text-center shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <p className="text-sm font-bold text-emerald-700">{label}</p>
        </div>
      )}
    </div>
  );
}

function DisclaimerBox() {
  return (
    <div className="mt-5 rounded-[8px] border border-gray-200 bg-gray-50 p-4 text-[11px] leading-5 text-gray-500">
      <p className="font-bold text-gray-600">분석 결과 이용 시 유의사항</p>
      <p className="mt-1.5 break-keep">
        본 결과는 업로드한 진료자료를 바탕으로 AI가 산출한 <b className="font-bold">참고용 보조자료</b>이며,
        의학적 진단이나 보험 인수 여부를 확정하지 않습니다. 실제 알릴의무(고지) 대상과 범위는
        보험사별 청약서 문항·약관·인수지침에 따라 달라질 수 있으므로, 청약 전 반드시 해당 청약서
        문항과 대조해 주세요. 고지 누락에 대한 최종 책임은 청약자 본인에게 있으며, 본 서비스는
        분석 결과의 사용으로 인한 법적 책임을 지지 않습니다.
      </p>
    </div>
  );
}

function ResultView({ result, mode }: { result: AnalyzeResult; mode: AudienceMode }) {
  const [productTab, setProductTab] = useState<"standard" | "easy">("standard");
  const activeReports = productTab === "standard" ? result.standard_reports : result.easy_reports;
  const activeMemo = productTab === "standard" ? result.standard_kakao : result.easy_kakao;
  const activeLabel = productTab === "standard" ? "건강체/표준체" : "간편심사";
  const stdCount = Object.values(result.standard_reports).reduce((s, arr) => s + arr.length, 0);
  const easyCount = Object.values(result.easy_reports).reduce((s, arr) => s + arr.length, 0);
  const copy = modeCopy[mode];

  return (
    <div>
      {(result.parse_errors || []).map((e, i) => (
        <div key={`parse-${i}`} className="mb-3 rounded-[8px] bg-amber-50 p-3 text-sm font-semibold text-amber-700">
          {e}
        </div>
      ))}

      {(result.warnings || []).map((w, i) => (
        <div key={`warning-${i}`} className="mb-3 rounded-[8px] bg-gray-50 p-3 text-sm text-gray-600">
          {w}
        </div>
      ))}

      {result.meritz_easy_message && (
        <div className="mb-4 whitespace-pre-wrap rounded-[8px] border border-orange-200 bg-orange-50 p-4 text-xs leading-relaxed text-orange-800">
          {result.meritz_easy_message}
        </div>
      )}

      <div className="mb-5 rounded-[8px] bg-white p-5 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
        <h2 className="text-xs font-bold text-[#4F46E5]">{copy.resultTitle}</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-4">
          <Metric label="건강체 고지" value={`${stdCount}건`} tone={stdCount ? "text-amber-600" : "text-emerald-600"} />
          <Metric label="간편심사 고지" value={`${easyCount}건`} tone={easyCount ? "text-amber-600" : "text-emerald-600"} />
          <Metric label="전체 병력" value={`${result.all_disease_summary.length}개`} />
          <Metric label="총 투약일" value={`${result.total_med_sum}일`} />
        </div>
      </div>

      <AllDiseaseSection diseases={result.all_disease_summary} />

      <section className="mb-5 overflow-hidden rounded-[8px] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
        <div role="tablist" aria-label="심사 유형" className="flex border-b border-gray-100">
          {(["standard", "easy"] as const).map((tab) => {
            const label = tab === "standard" ? "건강체/표준체" : "간편심사";
            const count = tab === "standard" ? stdCount : easyCount;
            const active = productTab === tab;
            return (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setProductTab(tab)}
                className={`relative flex-1 py-3.5 text-sm font-bold transition-all ${
                  active ? "text-[#4F46E5]" : "text-gray-400 hover:text-gray-600"
                }`}
              >
                {label}
                {count > 0 && (
                  <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs font-semibold ${
                    active ? "bg-indigo-100 text-indigo-600" : "bg-gray-100 text-gray-500"
                  }`}>
                    {count}
                  </span>
                )}
                {active && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4F46E5]" />}
              </button>
            );
          })}
        </div>

        <div role="tabpanel" className="p-4">
          <DisclosureSection
            reports={activeReports}
            memo={activeMemo}
            label={`${activeLabel} ${copy.emptyTitle}`}
            mode={mode}
          />
        </div>
      </section>

      <DisclaimerBox />
    </div>
  );
}

function Metric({ label, value, tone = "text-gray-900" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-[8px] bg-gray-50 px-4 py-3">
      <p className="text-xs font-semibold text-gray-400">{label}</p>
      <p className={`mt-1 text-xl font-black ${tone}`}>{value}</p>
    </div>
  );
}

function ModeSwitch({ mode }: { mode: AudienceMode }) {
  return (
    <div data-tour="role" className="mb-5 grid gap-3 md:grid-cols-2">
      <Link
        to="/check"
        className={`rounded-[8px] border p-4 transition ${
          mode === "customer"
            ? "border-emerald-300 bg-emerald-50"
            : "border-gray-200 bg-white hover:border-emerald-200"
        }`}
      >
        <p className="text-sm font-extrabold text-gray-900">고객용</p>
        <p className="mt-1 text-xs leading-5 text-gray-500">기존 가입 보험의 고지 누락 가능성을 점검합니다.</p>
      </Link>
      <Link
        to="/disclosure?mode=agent"
        className={`rounded-[8px] border p-4 transition ${
          mode === "agent"
            ? "border-indigo-300 bg-indigo-50"
            : "border-gray-200 bg-white hover:border-indigo-200"
        }`}
      >
        <p className="text-sm font-extrabold text-gray-900">설계사용</p>
        <p className="mt-1 text-xs leading-5 text-gray-500">청약 전 알릴의무 필터와 상담 메시지를 만듭니다.</p>
      </Link>
    </div>
  );
}

const preTourSteps: TourStep[] = [
  {
    target: "role",
    title: "설계사용 또는 고객용 선택",
    body: "청약 전 상담은 설계사용, 기존 보험 점검은 고객용에서 시작합니다.",
  },
  {
    target: "date",
    title: "청약 예정일 입력",
    body: "고지 기간 계산의 기준일입니다. 기존 보험 점검은 실제 가입일을 넣어 주세요.",
  },
  {
    target: "upload",
    title: "PDF 첨부",
    body: "기본진료, 세부진료, 처방조제 PDF를 올리고 암호가 있으면 비밀번호를 입력합니다.",
  },
];

const postTourSteps: TourStep[] = [
  {
    target: "summary",
    title: "병력 요약 펼치기 또는 접기",
    body: "전체 병력은 처음에는 접혀 있습니다. 필요할 때 펼쳐 원자료 집계를 확인합니다.",
  },
  {
    target: "copy",
    title: "카카오톡 복사하기",
    body: "상품 기준별 고지 메시지를 복사해 고객 안내나 내부 검토에 활용합니다.",
  },
  {
    target: "cards",
    title: "하단 병력 확인하기",
    body: "질병별 카드에서 통원, 입원, 수술, 투약, 추가검사 의심 내용을 최종 확인합니다.",
  },
];

function TourOverlay({
  phase,
  index,
  onNext,
  onSkip,
}: {
  phase: TourPhase;
  index: number;
  onNext: () => void;
  onSkip: () => void;
}) {
  const steps = phase === "pre" ? preTourSteps : postTourSteps;
  const step = steps[index];
  const [rect, setRect] = useState<DOMRect | null>(null);
  const displayIndex = phase === "pre" ? index + 1 : index + 4;
  const isLast = index === steps.length - 1;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onSkip();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSkip]);

  useEffect(() => {
    const target = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
    if (!target) {
      const emptyTimer = window.setTimeout(() => setRect(null), 0);
      return () => window.clearTimeout(emptyTimer);
    }

    const updateRect = () => setRect(target.getBoundingClientRect());
    target.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
    updateRect();
    const timer = window.setTimeout(updateRect, 220);

    window.addEventListener("resize", updateRect);
    window.addEventListener("scroll", updateRect, true);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", updateRect);
      window.removeEventListener("scroll", updateRect, true);
    };
  }, [step.target]);

  const spotlightStyle = rect
    ? {
        left: Math.max(12, rect.left - 10),
        top: Math.max(12, rect.top - 10),
        width: rect.width + 20,
        height: rect.height + 20,
        borderRadius: 16,
        boxShadow: "0 0 0 9999px rgba(17, 24, 39, 0.68), 0 24px 70px rgba(0, 0, 0, 0.28)",
      }
    : undefined;

  const cardStyle = (() => {
    if (!rect || typeof window === "undefined") return undefined;
    const cardWidth = Math.min(360, window.innerWidth - 32);
    const below = rect.bottom + 34;
    const above = rect.top - 294;
    const top = below + 260 < window.innerHeight ? below : Math.max(18, above);
    const left = Math.min(Math.max(16, rect.left + rect.width / 2 - cardWidth / 2), window.innerWidth - cardWidth - 16);
    return { width: cardWidth, top, left };
  })();

  return (
    <div className="fixed inset-0 z-[1000]">
      {rect ? (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed border-2 border-white bg-transparent ring-2 ring-[#4F46E5]/40"
          style={spotlightStyle}
        />
      ) : (
        <div aria-hidden="true" className="absolute inset-0 bg-gray-950/70" />
      )}

      <section
        role="dialog"
        aria-modal="true"
        aria-label="사용 안내 튜토리얼"
        className={`fixed rounded-[8px] bg-white p-5 shadow-[0_22px_70px_rgba(15,23,42,0.3)] ${
          cardStyle ? "" : "left-1/2 top-1/2 w-[min(360px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2"
        }`}
        style={cardStyle}
      >
        <div className="mb-6 flex items-center justify-between text-sm font-semibold text-gray-400">
          <span>{displayIndex} / 6</span>
          <button type="button" onClick={onSkip} className="hover:text-gray-700">
            건너뛰기
          </button>
        </div>
        <div className="mb-5">
          <p className="text-lg font-extrabold text-gray-900 break-keep">{step.title}</p>
          <p className="mt-3 text-sm leading-7 text-gray-600 break-keep">{step.body}</p>
        </div>
        <div className="flex items-center justify-between gap-4">
          <div className="flex gap-1.5">
            {Array.from({ length: 6 }).map((_, dotIndex) => (
              <span
                key={dotIndex}
                className={`h-2 rounded-full ${
                  dotIndex + 1 === displayIndex ? "w-7 bg-[#4F46E5]" : "w-2 bg-gray-200"
                }`}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={onNext}
            className="rounded-[8px] bg-[#4F46E5] px-5 py-3 text-sm font-extrabold text-white shadow-sm hover:bg-[#4338CA]"
          >
            {isLast ? "완료" : "다음"}
          </button>
        </div>
      </section>
    </div>
  );
}

export default function Disclosure({ initialMode = "agent" }: { initialMode?: AudienceMode }) {
  const [searchParams] = useSearchParams();
  const requestedMode = searchParams.get("mode");
  const mode: AudienceMode = requestedMode === "customer" || requestedMode === "agent" ? requestedMode : initialMode;
  const copy = modeCopy[mode];

  const { session } = useAuth();
  const [refDate, setRefDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [birthdate, setBirthdate] = useState("");
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [tourPhase, setTourPhase] = useState<TourPhase | null>(() => (readTourSeen().pre ? null : "pre"));
  const [tourIndex, setTourIndex] = useState(0);
  const [postTourShown, setPostTourShown] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/health`).catch(() => {});
  }, []);

  const handleTourNext = () => {
    if (!tourPhase) return;
    const steps = tourPhase === "pre" ? preTourSteps : postTourSteps;
    if (tourIndex >= steps.length - 1) {
      markTourSeen(tourPhase);
      setTourPhase(null);
      return;
    }
    setTourIndex((value) => value + 1);
  };

  const handleTourSkip = () => {
    if (tourPhase) markTourSeen(tourPhase);
    setTourPhase(null);
  };

  const replayTour = (phase: TourPhase) => {
    setTourPhase(phase);
    setTourIndex(0);
  };

  const showPostTour = () => {
    if (readTourSeen().post) return;
    setTourPhase("post");
    setTourIndex(0);
    setPostTourShown(true);
  };

  const analyze = async () => {
    const files = fileRef.current?.files;
    if (!files?.length) {
      setError("PDF 파일을 업로드해 주세요.");
      return;
    }
    if (files.length > 6) {
      setError("PDF는 최대 6개까지 업로드할 수 있습니다.");
      return;
    }
    const nonPdf = Array.from(files).find((f) => !f.name.toLowerCase().endsWith(".pdf"));
    if (nonPdf) {
      setError(`PDF 파일만 업로드할 수 있어요. (${nonPdf.name})`);
      return;
    }
    if (!consent) {
      setError("민감정보(건강정보) 처리 동의가 필요합니다. 동의 항목을 확인해 주세요.");
      return;
    }
    const token = session?.access_token;
    if (!token) {
      setError("로그인이 필요합니다. 다시 로그인한 뒤 시도해 주세요.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const form = new FormData();
    for (const f of files) form.append("files", f);
    form.append("reference_date", refDate);
    if (birthdate) form.append("birthdate_pw", birthdate);

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
        signal: AbortSignal.timeout(180_000),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || "분석 중 문제가 발생했어요. 잠시 후 다시 시도해 주세요.");
      }
      const data = await res.json();
      setResult(data);
      if (!postTourShown) {
        window.setTimeout(showPostTour, 0);
      }
    } catch (e: unknown) {
      if (e instanceof TypeError && e.message.includes("fetch")) {
        setError(connectionErrorMessage(API_BASE));
      } else {
        setError(e instanceof Error ? e.message : "알 수 없는 오류가 발생했습니다.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <ModeSwitch mode={mode} />
      <div className="-mt-2 mb-5 flex justify-end">
        <button
          type="button"
          onClick={() => replayTour(result ? "post" : "pre")}
          className="rounded-[8px] border border-gray-200 bg-white px-3 py-2 text-xs font-bold text-gray-500 hover:border-[#4F46E5]/40 hover:text-[#4F46E5]"
        >
          {result ? "결과 가이드 다시보기" : "필터 가이드 다시보기"}
        </button>
      </div>

      <div className="mb-6">
        <p className="mb-1 text-xs font-bold tracking-wider text-[#4F46E5]">{copy.badge}</p>
        <h1 className="text-2xl font-extrabold tracking-tight text-gray-900">{copy.title}</h1>
        <p className="mt-1 text-sm leading-6 text-gray-500 break-keep">{copy.subtitle}</p>
      </div>

      <section className="mb-5 rounded-[8px] bg-white p-6 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div data-tour="date">
            <label className="mb-2 block text-sm font-semibold text-gray-700">{copy.dateLabel}</label>
            <input
              type="date"
              value={refDate}
              onChange={(e) => setRefDate(e.target.value)}
              className="w-full rounded-[8px] bg-gray-50 px-4 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#4F46E5]/30"
            />
            <p className="mt-2 text-xs leading-5 text-gray-400">{copy.dateHelp}</p>
          </div>

          <div>
            <label className="mb-2 block text-sm font-semibold text-gray-700">
              PDF 비밀번호 <span className="font-normal text-gray-300">선택</span>
            </label>
            <input
              type="text"
              placeholder="예: 19900101"
              value={birthdate}
              onChange={(e) => setBirthdate(e.target.value)}
              className="w-full rounded-[8px] bg-gray-50 px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-[#4F46E5]/30"
            />
            <p className="mt-2 text-xs leading-5 text-gray-400">암호화 PDF라면 생년월일 8자리를 입력해 주세요.</p>
          </div>
        </div>

        <div data-tour="upload" className="mt-5 rounded-[8px] border-2 border-dashed border-indigo-200 bg-indigo-50 p-6 text-center transition hover:border-indigo-400">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            multiple
            className="block w-full cursor-pointer text-sm text-gray-600 file:mr-4 file:rounded-[8px] file:border-0 file:bg-[#4F46E5] file:px-5 file:py-2.5 file:text-sm file:font-bold file:text-white hover:file:bg-[#4338CA]"
          />
          <p className="mt-3 text-xs text-gray-500">{copy.uploadHelp}</p>
        </div>

        <label className="mt-4 flex items-start gap-2.5 rounded-[8px] bg-gray-50 px-4 py-3 text-xs leading-5 text-gray-600">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-[#4F46E5]"
          />
          <span className="break-keep">
            업로드하는 진료자료에는 <b className="font-bold text-gray-700">민감정보(건강에 관한 정보)</b>가 포함됩니다.
            알릴의무 분석 목적의 처리에 동의하며, 자료는 분석 직후 서버에서 폐기되고 저장되지 않습니다.
            <Link to="/privacy" className="ml-1 underline hover:text-gray-800">개인정보처리방침</Link>
          </span>
        </label>

        <button
          onClick={analyze}
          disabled={loading || !consent}
          className="mt-5 w-full rounded-[8px] bg-[#4F46E5] py-3 text-sm font-bold text-white shadow-[0_2px_8px_rgba(79,70,229,0.3)] transition-colors hover:bg-[#4338CA] disabled:opacity-50"
        >
          {loading ? "분석 중..." : copy.button}
        </button>
      </section>

      {mode === "customer" && !result && (
        <section className="mb-5 rounded-[8px] border border-emerald-100 bg-emerald-50 p-5">
          <p className="text-sm font-extrabold text-emerald-800">고객 안내 포인트</p>
          <p className="mt-2 text-xs leading-6 text-emerald-700 break-keep">
            이 점검은 보험 가입 권유가 아니라 기존 보험의 고지 누락 가능성을 미리 확인하는 절차입니다.
            분석 결과는 최종 법률 판단이 아니며, 실제 청약서 질문과 보험사 심사 기준에 맞춰 한 번 더 대조해야 합니다.
          </p>
        </section>
      )}

      {error && (
        <div className="mb-5 rounded-[8px] bg-red-50 p-4 text-sm font-semibold text-red-600">{error}</div>
      )}

      {loading && (
        <div aria-live="polite" className="mb-5">
          <AnalysisProgress />
        </div>
      )}

      {result && <ResultView result={result} mode={mode} />}

      {!result && !loading && !error && (
        <section className="rounded-[8px] bg-white p-8 text-center shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <p className="text-sm font-bold text-gray-800">심평원 진료자료 PDF를 업로드해 주세요.</p>
          <p className="mt-2 text-xs leading-6 text-gray-400 break-keep">
            기본진료, 세부진료, 처방조제 3종을 함께 올리면 통원, 입원, 수술, 투약 기록을 더 정확하게 교차검증할 수 있습니다.
          </p>
        </section>
      )}

      {tourPhase && (
        <TourOverlay
          phase={tourPhase}
          index={tourIndex}
          onNext={handleTourNext}
          onSkip={handleTourSkip}
        />
      )}
    </div>
  );
}

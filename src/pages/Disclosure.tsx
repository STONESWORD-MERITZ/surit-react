import { useState, useRef, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

type SummaryItem = {
  first_date: string;
  latest_date: string;
  code: string;
  name: string;
  visit: number;
  med_days: number;
  inpatient: number;
  surgeries: string[];
  hospitals: string[];
  detail: string;
  weight: string;
};

type AnalyzeResult = {
  flagged_count: number;
  total_q_count: number;
  total_visit_sum: number;
  total_med_sum: number;
  summary_reports: Record<string, SummaryItem[]>;
  kakao_message: string;
  parse_errors: string[];
  warnings: string[];
  verdict: string;
  verdict_reason: string;
  recommend: string;
};

function CollapsibleSection({
  title,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string;
  badge?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)] mb-4 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {badge && (
            <span className="text-xs font-bold bg-[#4F46E5] text-white px-2.5 py-1 rounded-lg">
              {badge}
            </span>
          )}
          <span className="text-sm font-bold text-gray-800">{title}</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="px-5 pb-4">{children}</div>}
    </div>
  );
}

const weightLabel: Record<string, string> = {
  critical: "위험",
  high: "높음",
  mid: "보통",
  low: "낮음",
};

const weightStyle: Record<string, string> = {
  critical: "bg-red-50 text-red-600",
  high: "bg-amber-50 text-amber-600",
  mid: "bg-gray-100 text-gray-500",
  low: "bg-gray-50 text-gray-400",
};

export default function Disclosure() {
  const [productType, setProductType] = useState("standard");
  const [refDate, setRefDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [birthdate, setBirthdate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // 페이지 로드 시 백엔드 wake-up (cold start 대비)
  useEffect(() => {
    fetch(`${API_BASE}/api/health`).catch(() => {});
  }, []);

  const analyze = async () => {
    const files = fileRef.current?.files;
    if (!files?.length) {
      setError("PDF 파일을 업로드해 주세요.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);

    const form = new FormData();
    for (const f of files) form.append("files", f);
    form.append("product_type", productType);
    form.append("reference_date", refDate);
    if (birthdate) form.append("birthdate_pw", birthdate);

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        body: form,
        signal: AbortSignal.timeout(180_000),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `서버 오류 (${res.status})`);
      }
      setResult(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "알 수 없는 오류");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!result?.kakao_message) return;
    navigator.clipboard.writeText(result.kakao_message);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      {/* 헤더 */}
      <div className="mb-6">
        <p className="text-xs font-bold text-[#4F46E5] tracking-wider mb-1">AI 고지 분석</p>
        <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">알릴의무 필터</h1>
        <p className="text-sm text-gray-400 mt-1">
          심평원 진료 PDF를 업로드하면 AI가 고지 의무 항목을 자동으로 추출합니다.
        </p>
      </div>

      {/* 설정 카드 */}
      <div className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)] p-6 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* 심사 기준 */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">심사 기준</label>
            <div className="flex gap-2">
              {[
                { value: "standard", label: "건강체/표준체" },
                { value: "easy", label: "간편심사" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setProductType(opt.value)}
                  className={`flex-1 py-2.5 px-3 rounded-xl text-sm font-semibold transition-all ${
                    productType === opt.value
                      ? "bg-[#4F46E5] text-white shadow-[0_2px_8px_rgba(79,70,229,0.3)]"
                      : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* 기준일 */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">기준일 (청약예정일)</label>
            <input
              type="date"
              value={refDate}
              onChange={(e) => setRefDate(e.target.value)}
              className="w-full bg-gray-50 rounded-xl px-4 py-2.5 text-sm text-gray-800 focus:ring-2 focus:ring-[#4F46E5]/30 focus:outline-none"
            />
          </div>

          {/* 생년월일 */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              생년월일 <span className="text-gray-300 font-normal">(선택)</span>
            </label>
            <input
              type="text"
              placeholder="예: 19900101"
              value={birthdate}
              onChange={(e) => setBirthdate(e.target.value)}
              className="w-full bg-gray-50 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-300 focus:ring-2 focus:ring-[#4F46E5]/30 focus:outline-none"
            />
          </div>
        </div>

        {/* 업로드 */}
        <div className="mt-5 bg-indigo-50 border-2 border-dashed border-indigo-200 rounded-2xl p-6 text-center hover:border-indigo-400 hover:bg-indigo-100/50 transition-all duration-200">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            multiple
            className="block w-full text-sm text-gray-600 file:mr-4 file:py-3 file:px-6 file:rounded-xl file:border-0 file:text-sm file:font-bold file:bg-[#4F46E5] file:text-white file:shadow-md hover:file:bg-[#4338CA] hover:file:shadow-lg hover:file:scale-105 file:transition-all file:duration-200 cursor-pointer"
          />
          <p className="text-xs text-gray-500 mt-3">
            건강e음 기본진료·세부진료·처방조제 PDF (1개 이상)
          </p>
        </div>

        {/* 분석 버튼 */}
        <button
          onClick={analyze}
          disabled={loading}
          className="w-full mt-5 py-3 bg-[#4F46E5] hover:bg-[#4338CA] disabled:opacity-50 text-white font-bold rounded-xl text-sm transition-colors shadow-[0_2px_8px_rgba(79,70,229,0.3)]"
        >
          {loading ? "분석 중..." : "AI 고지사항 추출"}
        </button>
      </div>

      {/* 에러 */}
      {error && (
        <div className="bg-red-50 rounded-2xl p-4 mb-5 text-sm text-red-600 font-semibold shadow-[0_2px_8px_rgba(0,0,0,0.04)]">
          {error}
        </div>
      )}

      {/* 결과 */}
      {result && (
        <div>
          {/* 카카오톡 복사 (설계매니저 전송용) */}
          {result.kakao_message && (
            <div className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)] mb-6 overflow-hidden">
              <div className="px-5 py-4 flex items-center justify-between">
                <span className="text-sm font-bold text-gray-800">카카오톡 전송용 메시지</span>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl font-bold text-sm transition-colors"
                  style={{ background: "#FEE500", color: "#191919" }}
                >
                  <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
                    <path
                      d="M9 1C4.58 1 1 3.8 1 7.24c0 2.22 1.48 4.17 3.7 5.27l-.94 3.47c-.08.3.26.54.52.36L8.05 13.7c.31.03.63.05.95.05 4.42 0 8-2.8 8-6.24S13.42 1 9 1Z"
                      fill="#191919"
                    />
                  </svg>
                  {copied ? "복사 완료!" : "복사하기"}
                </button>
              </div>
              <pre className="text-xs text-gray-600 whitespace-pre-wrap font-sans leading-relaxed bg-gray-50 px-5 py-4 mx-0">
                {result.kakao_message}
              </pre>
            </div>
          )}

          {/* 요약 수치 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {[
              { label: "고지 질병 수", value: result.flagged_count, warn: result.flagged_count > 0 },
              { label: "해당 질문 수", value: result.total_q_count, warn: result.total_q_count > 3 },
              { label: "총 통원 횟수", value: result.total_visit_sum, warn: false },
              { label: "총 투약일수", value: result.total_med_sum, warn: result.total_med_sum >= 30 },
            ].map((s) => (
              <div
                key={s.label}
                className="bg-white rounded-2xl p-4 shadow-[0_2px_12px_rgba(0,0,0,0.06)]"
              >
                <div className="text-xs text-gray-400 font-semibold mb-1">{s.label}</div>
                <div className={`text-3xl font-bold font-mono leading-none ${s.warn ? "text-red-500" : "text-gray-900"}`}>
                  {s.value}
                </div>
              </div>
            ))}
          </div>

          {/* 경고 */}
          {result.parse_errors.map((e, i) => (
            <div key={i} className="bg-amber-50 rounded-xl p-3 mb-2 text-sm text-amber-600 font-semibold">
              {e}
            </div>
          ))}

          {/* 고지 항목 - 접기/펼치기 */}
          {Object.entries(result.summary_reports)
            .sort(([a], [b]) => {
              const numA = parseInt(a.match(/(\d+)번질문/)?.[1] ?? a.match(/\d+/)?.[0] ?? "999", 10);
              const numB = parseInt(b.match(/(\d+)번질문/)?.[1] ?? b.match(/\d+/)?.[0] ?? "999", 10);
              return numA - numB;
            })
            .map(([qTitle, items]) => {
            const badge = qTitle.match(/Q\d+|간편\d+번/)?.[0] || "Q";
            const title = qTitle.replace(/^\[.*?\]\s*/, "");

            return (
              <CollapsibleSection key={qTitle} title={title} badge={badge} defaultOpen>
                {items.map((item, idx) => (
                  <div
                    key={idx}
                    className={`rounded-xl p-4 mb-2 last:mb-0 bg-gray-50`}
                  >
                    {/* 질병명 + 코드 */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-sm font-bold text-gray-800">{item.name}</span>
                      {item.code && (
                        <span className="font-mono text-[0.7rem] text-gray-400 bg-gray-200 px-1.5 py-0.5 rounded">
                          {item.code}
                        </span>
                      )}
                    </div>

                    {/* 날짜 / 병원 */}
                    <div className="text-xs text-gray-400 mb-2">
                      {item.first_date && item.latest_date && item.first_date !== item.latest_date
                        ? `${item.first_date} ~ ${item.latest_date}`
                        : item.first_date || item.latest_date}
                      {item.hospitals?.length > 0 && ` · ${item.hospitals.join(", ")}`}
                    </div>

                    {/* 사유 */}
                    {item.detail && (
                      <div className="text-xs text-[#4F46E5] font-semibold bg-[#EEF2FF] rounded-lg px-3 py-2 mb-2">
                        {item.detail}
                      </div>
                    )}

                    {/* 배지 */}
                    <div className="flex flex-wrap gap-1.5">
                      {item.inpatient > 0 && (
                        <span className="text-[0.7rem] px-2.5 py-1 rounded-lg font-semibold bg-red-50 text-red-500">
                          🏥 입원 {item.inpatient}일
                        </span>
                      )}
                      {item.surgeries?.length > 0 && (
                        <span className="text-[0.7rem] px-2.5 py-1 rounded-lg font-semibold bg-orange-50 text-orange-500">
                          🔪 수술: {item.surgeries.join(", ")}
                        </span>
                      )}
                      {item.med_days > 0 && (
                        <span className="text-[0.7rem] px-2.5 py-1 rounded-lg font-semibold bg-emerald-50 text-emerald-600">
                          💊 투약 {item.med_days}일
                        </span>
                      )}
                      {item.visit > 0 && (
                        <span className="text-[0.7rem] px-2.5 py-1 rounded-lg font-semibold bg-gray-100 text-gray-500">
                          통원 {item.visit}회
                        </span>
                      )}
                      <span className={`text-[0.7rem] px-2.5 py-1 rounded-lg font-semibold ${weightStyle[item.weight] || weightStyle.mid}`}>
                        {weightLabel[item.weight] || item.weight}
                      </span>
                    </div>
                  </div>
                ))}
              </CollapsibleSection>
            );
          })}

          {/* 고지 항목 없음 */}
          {Object.keys(result.summary_reports).length === 0 && (
            <div className="bg-emerald-50 rounded-2xl p-6 text-center shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
              <span className="text-3xl">✅</span>
              <p className="text-sm font-bold text-emerald-700 mt-2">고지 대상 항목이 없습니다</p>
            </div>
          )}

        </div>
      )}

      {/* 빈 상태 */}
      {!result && !loading && !error && (
        <div className="text-center py-16 bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="text-5xl mb-4">📂</div>
          <div className="text-sm font-bold text-gray-700 mb-1">심평원 진료자료 PDF를 업로드하세요</div>
          <div className="text-xs text-gray-400 leading-relaxed">
            건강e음에서 기본진료·세부진료·처방조제 3종을 발급받아 올려주세요.
            <br />
            1개만 올려도 분석 가능합니다.
          </div>
        </div>
      )}
    </div>
  );
}

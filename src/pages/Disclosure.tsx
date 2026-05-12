import { useState, useRef, useEffect } from "react";

const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

function connectionErrorMessage(apiBase: string): string {
  return (
    "서버에 연결할 수 없습니다(Failed to fetch). " +
    (typeof window !== "undefined" && window.location.hostname !== "localhost"
      ? `프론트 배포 환경에서는 VITE_API_URL로 백엔드 주소를 설정해야 합니다. (현재 요청: ${apiBase}) `
      : "") +
    "백엔드가 실행 중인지, CORS 설정을 확인해 주세요."
  );
}

type SummaryItem = {
  first_date: string;
  latest_date: string;
  first_diagnosis_date: string;
  code: string;
  name: string;
  visit: number;
  med_days: number;
  inpatient: number;
  inpatient_count: number;
  surgery_count?: number;
  surgeries: string[];
  procedures?: string[];
  procedure_dates?: string[];
  surgery_suspected?: string[];
  surgery_suspected_dates?: string[];
  additional_tests?: string[];
  additional_test_hit?: boolean;
  additional_test_reason?: string;
  treatment_ongoing?: boolean | null;
  treatment_ongoing_reason?: string;
  hospitals: string[];
  detail: string;
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
  meritz_easy_message: string;
};

// ── 위험도 판정 ──────────────────────────────────────────────
type Risk = "red" | "orange" | "gray" | "yellow" | "green";

function riskOf(item: SummaryItem): Risk {
  const surgN   = item.surgery_count ?? item.surgeries?.length ?? 0;
  const procN   = item.procedures?.length ?? 0;
  const suspN   = item.surgery_suspected?.length ?? 0;
  if (item.inpatient > 0 || surgN > 0) return "red";
  if (procN > 0) return "orange";
  if (suspN > 0) return "gray";
  if (item.med_days >= 30 || item.visit >= 7) return "yellow";
  return "green";
}

const RISK: Record<Risk, { border: string; label: string; pill: string }> = {
  red:    { border: "border-red-400",     label: "text-red-600",     pill: "bg-red-100 text-red-600" },
  orange: { border: "border-orange-400",  label: "text-orange-600",  pill: "bg-orange-100 text-orange-600" },
  gray:   { border: "border-gray-400",    label: "text-gray-500",    pill: "bg-gray-100 text-gray-600" },
  yellow: { border: "border-amber-400",   label: "text-amber-600",   pill: "bg-amber-100 text-amber-700" },
  green:  { border: "border-emerald-400", label: "text-emerald-600", pill: "bg-emerald-100 text-emerald-700" },
};


// ── 결과 뷰 ─────────────────────────────────────────────────
function ResultView({
  result, copied, kakaoOpen,
  setKakaoOpen, handleCopy,
}: {
  result: AnalyzeResult;
  copied: boolean;
  kakaoOpen: boolean;
  setKakaoOpen: (v: boolean) => void;
  handleCopy: () => void;
}) {

  return (
    <div>
      {/* 카카오톡 메시지 */}
      {result.kakao_message && (
        <div className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)] mb-6 overflow-hidden">
          <div className="px-5 py-4 flex items-center justify-between">
            <button
              onClick={() => setKakaoOpen(!kakaoOpen)}
              className="flex items-center gap-2 text-left"
            >
              <svg
                className={`w-4 h-4 text-gray-400 transition-transform ${kakaoOpen ? "rotate-180" : ""}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
              <span className="text-sm font-bold text-gray-800">카카오톡 전송용 메시지</span>
            </button>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl font-bold text-sm"
              style={{ background: "#FEE500", color: "#191919" }}
            >
              <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
                <path d="M9 1C4.58 1 1 3.8 1 7.24c0 2.22 1.48 4.17 3.7 5.27l-.94 3.47c-.08.3.26.54.52.36L8.05 13.7c.31.03.63.05.95.05 4.42 0 8-2.8 8-6.24S13.42 1 9 1Z" fill="#191919" />
              </svg>
              {copied ? "복사 완료!" : "복사하기"}
            </button>
          </div>
          {kakaoOpen && (
            <pre className="text-xs text-gray-600 whitespace-pre-wrap font-sans leading-relaxed bg-gray-50 px-5 py-4">
              {result.kakao_message}
            </pre>
          )}
        </div>
      )}

      {/* 상단 요약 카드 4개 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {/* 고지 질환 수 */}
        <div className="bg-white rounded-2xl p-4 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="text-xs text-gray-400 font-semibold mb-1">고지 질환 수</div>
          <div className={`text-3xl font-bold font-mono leading-none ${result.flagged_count > 0 ? "text-red-500" : "text-gray-900"}`}>
            {result.flagged_count}
            <span className="text-sm font-semibold ml-1 text-gray-500">개</span>
          </div>
        </div>

        {/* 해당 질문 수 */}
        <div className="bg-white rounded-2xl p-4 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="text-xs text-gray-400 font-semibold mb-1">해당 질문 수</div>
          <div className={`text-3xl font-bold font-mono leading-none ${result.total_q_count > 2 ? "text-amber-500" : "text-gray-900"}`}>
            {result.total_q_count}
            <span className="text-sm font-semibold ml-1 text-gray-500">개</span>
          </div>
        </div>

        {/* 총 통원 횟수 */}
        <div className="bg-white rounded-2xl p-4 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="text-xs text-gray-400 font-semibold mb-1">총 통원 횟수</div>
          <div className="text-3xl font-bold font-mono leading-none text-gray-900">
            {result.total_visit_sum}
            <span className="text-sm font-semibold ml-1 text-gray-500">회</span>
          </div>
        </div>

        {/* 총 투약일수 */}
        <div className="bg-white rounded-2xl p-4 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="text-xs text-gray-400 font-semibold mb-1">총 투약일수</div>
          <div className="text-3xl font-bold font-mono leading-none text-gray-900">
            {result.total_med_sum}
            <span className="text-sm font-semibold ml-1 text-gray-500">일</span>
          </div>
        </div>
      </div>

      {/* 파싱 오류 (심각한 것만) */}
      {result.parse_errors
        .filter(e => e.includes("🔒") || e.includes("손상") || e.includes("비밀번호"))
        .map((e, i) => (
          <div key={i} className="bg-amber-50 rounded-xl p-3 mb-3 text-sm text-amber-700 font-semibold">
            {e}
          </div>
        ))}

      {/* 메리츠 간편 예외질환 경고 */}
      {result.meritz_easy_message && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 mb-4 text-xs text-orange-800 whitespace-pre-wrap leading-relaxed">
          {result.meritz_easy_message}
        </div>
      )}

      {/* 질환 섹션별 카드 */}
      {Object.keys(result.summary_reports).length > 0 ? (
        <div className="space-y-4">
          {Object.entries(result.summary_reports).map(([qTitle, items]) => {
            // "[간편1번질문] 3개월 이내..." → badge: "간편1번", title: "3개월 이내..."
            const badgeMatch = qTitle.match(/\[(.*?)번질문\]/);
            const badge      = badgeMatch ? badgeMatch[1] + "번" : (qTitle.match(/Q\d+/)?.[0] ?? "Q");
            const sectionTitle = qTitle.replace(/^\[.*?\]\s*/, "");

            return (
              <div key={qTitle} className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)] overflow-hidden">
                {/* 섹션 헤더 */}
                <div className="px-5 py-3.5 flex items-center gap-2.5 border-b border-gray-100">
                  <span className="text-xs font-bold bg-[#4F46E5] text-white px-2.5 py-1 rounded-md shrink-0">
                    {badge}
                  </span>
                  <span className="text-sm font-bold text-gray-800">{sectionTitle}</span>
                </div>

                {/* 질환 카드 목록 */}
                <div className="divide-y divide-gray-50">
                  {items.map((item, idx) => {
                    const risk  = riskOf(item);
                    const sc    = RISK[risk];
                    const surgN = item.surgery_count ?? item.surgeries?.length ?? 0;
                    const procN = item.procedures?.length ?? 0;
                    const suspN = item.surgery_suspected?.length ?? 0;
                    const hosp  = (item.hospitals as string[])?.[0] ?? "";

                    return (
                      <div key={idx} className={`px-5 py-4 border-l-4 ${sc.border}`}>
                        {/* 질병명 + 코드 */}
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[15px] font-bold text-gray-900">
                            {item.name || "질병명 없음"}
                          </span>
                          {item.code && (
                            <span className="font-mono text-[11px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded shrink-0">
                              {item.code}
                            </span>
                          )}
                        </div>

                        {/* 날짜 · 병원 */}
                        <div className="text-xs text-gray-400 mb-2.5">
                          {item.first_date}{hosp ? ` · ${hosp}` : ""}
                        </div>

                        {/* 고지 이유 박스 */}
                        {item.detail && (
                          <div className="bg-indigo-50 text-indigo-700 text-xs rounded-lg px-3 py-2 mb-3 leading-relaxed">
                            {item.detail}
                          </div>
                        )}

                        {/* 통계 칩 */}
                        <div className="flex flex-wrap gap-1.5">
                          {item.visit > 0 && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-gray-100 text-gray-600">
                              통원 {item.visit}회
                            </span>
                          )}
                          {item.inpatient > 0 && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-red-100 text-red-600">
                              입원 {item.inpatient}일
                            </span>
                          )}
                          {item.inpatient_count > 0 && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-red-50 text-red-500 border border-red-200">
                              입원 {item.inpatient_count}회
                            </span>
                          )}
                          {surgN > 0 && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-red-100 text-red-600">
                              수술 {surgN}건
                            </span>
                          )}
                          {procN > 0 && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-orange-100 text-orange-600">
                              시술 {procN}건
                            </span>
                          )}
                          {suspN > 0 && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-gray-100 text-gray-500">
                              ⚠️ 수술 의심 {suspN}건
                            </span>
                          )}
                          {item.med_days > 0 && (
                            <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                              item.med_days >= 30
                                ? "bg-amber-100 text-amber-700"
                                : "bg-emerald-100 text-emerald-700"
                            }`}>
                              투약 {item.med_days}일
                            </span>
                          )}
                          {item.additional_test_hit && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-indigo-100 text-indigo-600">
                              재검사
                            </span>
                          )}
                          {item.treatment_ongoing === true && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-rose-100 text-rose-600">
                              치료 중
                            </span>
                          )}
                          {item.treatment_ongoing === false && (
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-emerald-100 text-emerald-700">
                              종결
                            </span>
                          )}
                        </div>

                        {/* 수술 의심 행위명 + 의학 판단 보조 텍스트 */}
                        {(suspN > 0 || item.additional_test_hit || item.treatment_ongoing != null) && (
                          <div className="mt-2 space-y-0.5">
                            {suspN > 0 && (
                              <p className="text-xs text-gray-400">
                                의심 행위: {item.surgery_suspected!.slice(0, 3).join(", ")}
                              </p>
                            )}
                            {item.additional_test_hit && item.additional_test_reason && (
                              <p className="text-xs text-indigo-500">
                                재검사: {item.additional_test_reason}
                              </p>
                            )}
                            {item.treatment_ongoing != null && (
                              <p className={`text-xs ${item.treatment_ongoing ? "text-rose-500" : "text-emerald-600"}`}>
                                {item.treatment_ongoing ? "치료 중" : "종결"}: {item.treatment_ongoing_reason}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-emerald-50 rounded-2xl p-8 text-center shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="text-4xl mb-3">✅</div>
          <p className="text-sm font-bold text-emerald-700">고지 대상 항목이 없습니다</p>
        </div>
      )}
    </div>
  );
}

// ── 메인 ────────────────────────────────────────────────────
export default function Disclosure() {
  const [productType, setProductType] = useState("standard");
  const [refDate, setRefDate]         = useState(() => new Date().toISOString().slice(0, 10));
  const [birthdate, setBirthdate]     = useState("");
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");
  const [result, setResult]           = useState<AnalyzeResult | null>(null);
  const [copied, setCopied]           = useState(false);
  const [kakaoOpen, setKakaoOpen]     = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/health`).catch(() => {});
  }, []);

  const analyze = async () => {
    const files = fileRef.current?.files;
    if (!files?.length) { setError("PDF 파일을 업로드해 주세요."); return; }
    setLoading(true); setError(""); setResult(null);

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
      if (e instanceof TypeError && e.message.includes("fetch"))
        setError(connectionErrorMessage(API_BASE));
      else
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
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">심사 기준</label>
            <div className="flex gap-2">
              {[
                { value: "standard", label: "건강체/표준체" },
                { value: "easy",     label: "간편심사" },
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

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">기준일 (청약예정일)</label>
            <input
              type="date"
              value={refDate}
              onChange={(e) => setRefDate(e.target.value)}
              className="w-full bg-gray-50 rounded-xl px-4 py-2.5 text-sm text-gray-800 focus:ring-2 focus:ring-[#4F46E5]/30 focus:outline-none"
            />
          </div>

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
        <div className="bg-red-50 rounded-2xl p-4 mb-5 text-sm text-red-600 font-semibold">
          {error}
        </div>
      )}

      {/* 결과 */}
      {result && (
        <ResultView
          result={result}
          copied={copied}
          kakaoOpen={kakaoOpen}
          setKakaoOpen={setKakaoOpen}
          handleCopy={handleCopy}
        />
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

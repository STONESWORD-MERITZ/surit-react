import { useState, useRef } from "react";

type CovRow = { name: string; before: string; after: string; diff: "up" | "dn" | "eq" };

const demoCoverage: CovRow[] = [
  { name: "암 진단금", before: "3,000만원", after: "5,000만원", diff: "up" },
  { name: "뇌졸중 진단금", before: "2,000만원", after: "2,000만원", diff: "eq" },
  { name: "심근경색 진단금", before: "2,000만원", after: "2,000만원", diff: "eq" },
  { name: "실손의료비", before: "구실손 (5%)", after: "4세대 실손", diff: "up" },
];

const dotColor = { up: "bg-emerald-400", dn: "bg-red-400", eq: "bg-gray-300" };
const valStyle = {
  up: "text-emerald-600 font-bold",
  dn: "text-red-500 font-bold",
  eq: "text-gray-600",
};

export default function BeforeAfter() {
  const [analyzed, setAnalyzed] = useState(false);
  const beforeRef = useRef<HTMLInputElement>(null);
  const afterRef = useRef<HTMLInputElement>(null);

  const handleAnalyze = () => {
    if (!beforeRef.current?.files?.length) return;
    setAnalyzed(true);
  };

  return (
    <div>
      {/* 헤더 */}
      <div className="mb-6">
        <p className="text-xs font-bold text-[#4F46E5] tracking-wider mb-1">보장 분석</p>
        <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">비포 & 에프터</h1>
        <p className="text-sm text-gray-400 mt-1">
          기존 보장내역과 신규 제안서를 비교하여 리모델링 근거를 제시하세요.
        </p>
      </div>

      {/* 업로드 카드 */}
      <div className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)] p-6 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              기존 보장분석 PDF <span className="text-red-400 text-xs">필수</span>
            </label>
            <div className="bg-gray-50 rounded-xl p-4">
              <input
                ref={beforeRef}
                type="file"
                accept=".pdf"
                className="block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-[#4F46E5] file:text-white hover:file:bg-[#4338CA] cursor-pointer"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              신규 제안서 PDF <span className="text-gray-300 text-xs font-normal">최대 4개</span>
            </label>
            <div className="bg-gray-50 rounded-xl p-4">
              <input
                ref={afterRef}
                type="file"
                accept=".pdf"
                multiple
                className="block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-[#4F46E5] file:text-white hover:file:bg-[#4338CA] cursor-pointer"
              />
            </div>
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          className="w-full mt-5 py-3 bg-[#4F46E5] hover:bg-[#4338CA] text-white font-bold rounded-xl text-sm transition-colors shadow-[0_2px_8px_rgba(79,70,229,0.3)]"
        >
          분석 시작
        </button>
      </div>

      {/* 결과 */}
      {analyzed ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* 기존 */}
          <div className="bg-white rounded-2xl overflow-hidden shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
            <div className="px-5 py-3.5 bg-amber-50 text-sm font-bold text-amber-700">
              기존 보장 (BEFORE)
            </div>
            {demoCoverage.map((row) => (
              <div
                key={row.name}
                className="flex items-center gap-3 px-5 py-3 text-sm"
              >
                <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor[row.diff]}`} />
                <span className="flex-1 text-gray-500">{row.name}</span>
                <span className="font-mono text-xs text-gray-700">{row.before}</span>
              </div>
            ))}
            <div className="flex items-center px-5 py-3.5 bg-gray-50">
              <span className="flex-1 text-sm text-gray-500 font-bold">월 보험료</span>
              <span className="font-mono text-sm font-extrabold text-gray-900">114,000원</span>
            </div>
          </div>

          {/* 신규 */}
          <div className="bg-white rounded-2xl overflow-hidden shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
            <div className="px-5 py-3.5 bg-emerald-50 text-sm font-bold text-emerald-700">
              신규 제안 (AFTER)
            </div>
            {demoCoverage.map((row) => (
              <div
                key={row.name}
                className="flex items-center gap-3 px-5 py-3 text-sm"
              >
                <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor[row.diff]}`} />
                <span className="flex-1 text-gray-500">{row.name}</span>
                <span className={`font-mono text-xs ${valStyle[row.diff]}`}>
                  {row.after}
                  {row.diff === "up" && " ▲"}
                  {row.diff === "dn" && " ▼"}
                </span>
              </div>
            ))}
            <div className="flex items-center px-5 py-3.5 bg-gray-50">
              <span className="flex-1 text-sm text-gray-500 font-bold">월 보험료</span>
              <span className="font-mono text-sm font-extrabold text-emerald-600">
                128,000원{" "}
                <span className="text-xs font-normal text-gray-400">(+14,000)</span>
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-16 bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="text-5xl mb-4">🔄</div>
          <div className="text-sm font-bold text-gray-700 mb-1">
            PDF를 업로드하고 분석을 시작하세요
          </div>
          <div className="text-xs text-gray-400 leading-relaxed">
            기존 보장분석 PDF와 신규 제안서 PDF를 업로드하면
            <br />
            AI가 보장 항목을 자동으로 비교합니다.
          </div>
        </div>
      )}
    </div>
  );
}

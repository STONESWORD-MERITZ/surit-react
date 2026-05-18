import { useEffect, useState } from "react";

const STEPS = [
  { key: "parse",  label: "PDF 파싱",     hint: "기본진료·세부진료·처방조제를 읽고 있어요" },
  { key: "rule",   label: "고지 룰 적용", hint: "KCD 코드 단위로 알릴의무 4문항을 분류해요" },
  { key: "ai",     label: "AI 의학 판단", hint: "추가검사 여부·치료 종결 여부를 확인해요" },
  { key: "merge",  label: "결과 정리",    hint: "질환별로 묶어 카드로 보여드릴 준비 중이에요" },
] as const;

// 평균 분석 시간 약 12~25초 가정. 단계별 누적 milliseconds.
const STEP_TIMING_MS = [3000, 6000, 14000, 18000];

export default function AnalysisProgress() {
  const [activeIdx, setActiveIdx] = useState(0);
  const [start] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => {
      const elapsed = Date.now() - start;
      let next = STEP_TIMING_MS.findIndex((t) => elapsed < t);
      if (next === -1) next = STEPS.length - 1;
      setActiveIdx(next);
    }, 300);
    return () => clearInterval(id);
  }, [start]);

  return (
    <div className="rounded-2xl border border-indigo-100 bg-indigo-50/40 px-5 py-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="inline-block h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
        <p className="text-sm font-bold text-indigo-700">분석 중…</p>
      </div>
      <ol className="space-y-3">
        {STEPS.map((s, i) => {
          const state =
            i < activeIdx ? "done" : i === activeIdx ? "active" : "pending";
          return (
            <li key={s.key} className="flex items-start gap-3">
              <span
                className={`mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold shrink-0
                  ${state === "done"    ? "bg-indigo-600 text-white" : ""}
                  ${state === "active"  ? "bg-white text-indigo-600 border-2 border-indigo-600 animate-pulse" : ""}
                  ${state === "pending" ? "bg-white text-gray-400 border border-gray-200" : ""}`}
              >
                {state === "done" ? "✓" : i + 1}
              </span>
              <div className="min-w-0">
                <p className={`text-sm font-semibold ${
                  state === "pending" ? "text-gray-400" : "text-gray-900"
                }`}>
                  {s.label}
                </p>
                {state === "active" && (
                  <p className="text-xs text-gray-500 mt-0.5">{s.hint}</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <p className="mt-5 text-[11px] text-gray-400">
        PDF 페이지가 많을수록 시간이 더 걸릴 수 있어요. 페이지를 닫지 말고 잠시만 기다려주세요.
      </p>
    </div>
  );
}

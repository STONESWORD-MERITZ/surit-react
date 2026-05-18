import { memo, useState } from "react";
import type { SummaryItem } from "../../types/disclosure";
import { extractQNumber, cleanQTitle } from "../../lib/disclosureUtils";
import { modeCopy, type AudienceMode } from "../../lib/disclosureTypes";
import DiseaseCard from "./DiseaseCard";

function DisclosureSection({
  reports,
  memo: memoText,
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
    void navigator.clipboard.writeText(memoText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      {memoText && (
        <section className="mb-4 overflow-hidden rounded-[8px] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <div className="flex items-center justify-between gap-3 px-5 py-4">
            <button
              onClick={() => setMemoOpen((o) => !o)}
              className="text-left text-sm font-bold text-gray-800"
            >
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
              {memoText}
            </pre>
          )}
        </section>
      )}

      {hasItems ? (
        <div className="space-y-4">
          {Object.entries(reports).map(([qTitle, items]) => {
            const qNum = extractQNumber(qTitle);
            return (
              <section
                key={qTitle}
                className="overflow-hidden rounded-[8px] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)]"
              >
                <div className="flex items-center gap-2.5 border-b border-gray-100 px-5 py-3.5">
                  <span className="shrink-0 rounded-[8px] bg-[#4F46E5] px-2.5 py-1 text-xs font-bold text-white">
                    {qNum}
                  </span>
                  <span className="text-sm font-bold text-gray-800">{cleanQTitle(qTitle)}</span>
                </div>
                <div className="divide-y divide-gray-50">
                  {items.map((item, idx) => (
                    <DiseaseCard key={`${item.code}-${idx}`} item={item} qNum={qNum} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div className="rounded-[8px] bg-emerald-50 p-8 text-center shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <p className="text-sm font-bold text-emerald-700">{label}</p>
        </div>
      )}
    </div>
  );
}

export default memo(DisclosureSection);

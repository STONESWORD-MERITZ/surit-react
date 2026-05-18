import { memo } from "react";
import { Link } from "react-router-dom";

interface ResultActionBarProps {
  onPrint: () => void;
  onReset: () => void;
  onSave: () => void;
  saving: boolean;
  savedId: string | null;
  showSave: boolean;
}

function ResultActionBar({
  onPrint,
  onReset,
  onSave,
  saving,
  savedId,
  showSave,
}: ResultActionBarProps) {
  return (
    <div className="mt-2 mb-3 flex flex-wrap items-center gap-2 print:hidden">
      <button
        type="button"
        onClick={onPrint}
        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-bold text-gray-700 hover:border-gray-400"
      >
        🖨️ 인쇄·PDF 저장
      </button>
      <button
        type="button"
        onClick={onReset}
        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-bold text-gray-700 hover:border-gray-400"
      >
        🔄 다시 분석
      </button>
      {showSave && !savedId && (
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-bold text-gray-700 hover:border-gray-400 disabled:opacity-50"
        >
          💾 {saving ? "저장 중…" : "결과 저장"}
        </button>
      )}
      {savedId && (
        <Link
          to={`/history/${savedId}`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white"
        >
          ✓ 저장됨 — 기록 보기
        </Link>
      )}
    </div>
  );
}

export default memo(ResultActionBar);

import { memo } from "react";

const TONES: Record<string, string> = {
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

function Chip({ label, tone = "gray" }: { label: string; tone?: string }) {
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${TONES[tone] ?? TONES.gray}`}>
      {label}
    </span>
  );
}

export default memo(Chip);

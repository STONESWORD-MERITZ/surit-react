import type { SummaryItem } from "../types/disclosure";

export type RiskLevel = "red" | "orange" | "gray" | "yellow" | "green";

export const RISK: Record<RiskLevel, { border: string }> = {
  red: { border: "border-red-400" },
  orange: { border: "border-orange-400" },
  gray: { border: "border-gray-400" },
  yellow: { border: "border-amber-400" },
  green: { border: "border-emerald-400" },
};

export function riskOf(item: SummaryItem): RiskLevel {
  const surgN = item.surgery_count ?? item.surgeries?.length ?? 0;
  const procN = item.procedures?.length ?? 0;
  const suspN = item.surgery_suspected?.length ?? 0;
  if (item.inpatient > 0 || surgN > 0) return "red";
  if (procN > 0) return "orange";
  if (suspN > 0) return "gray";
  if (item.med_days >= 30 || item.visit >= 7) return "yellow";
  return "green";
}

export function extractQNumber(qTitle: string): string {
  const exact = qTitle.match(/(\d+)\s*번\s*질문/);
  if (exact) return `Q${exact[1]}`;
  const any = qTitle.match(/\d+/);
  return any ? `Q${any[0]}` : "Q";
}

export function cleanQTitle(qTitle: string): string {
  return qTitle.replace(/^\[.*?\]\s*/, "");
}

export function buildPeriod(first?: string, latest?: string): string {
  if (first && latest && first !== latest) return `${first} ~ ${latest}`;
  return first || latest || "";
}

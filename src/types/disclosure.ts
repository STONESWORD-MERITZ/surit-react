export type AudienceMode = "customer" | "agent";

export interface SummaryItem {
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
}

export interface DiseaseSummary {
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
}

export interface AnalyzeResult {
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
}

import { memo } from "react";
import type { SummaryItem } from "../../types/disclosure";
import { riskOf, RISK, buildPeriod } from "../../lib/disclosureUtils";
import Chip from "./Chip";

function DiseaseCard({ item, qNum }: { item: SummaryItem; qNum: string }) {
  const risk = riskOf(item);
  const surgN = item.surgery_count ?? item.surgeries?.length ?? 0;
  const procN = item.procedures?.length ?? 0;
  const suspN = item.surgery_suspected?.length ?? 0;
  const period = buildPeriod(item.first_date, item.latest_date);
  const hasBottom = suspN > 0 || item.additional_test_hit || item.treatment_ongoing != null;

  return (
    <article className={`surit-result-card border-l-4 px-5 py-4 ${RISK[risk].border}`}>
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
            {item.last_hospital && (
              <span className="truncate text-gray-400">{item.last_hospital}</span>
            )}
          </div>
        )}
        {item.first_diagnosis_date && (
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-gray-400">최초진단</span>
            <span>{item.first_diagnosis_date}</span>
            {item.first_hospital && (
              <span className="truncate text-gray-400">{item.first_hospital}</span>
            )}
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
        <Chip
          label={`입원 ${item.inpatient ?? 0}일`}
          tone={(item.inpatient ?? 0) > 0 ? "red" : "gray"}
        />
        <Chip
          label={`입원 ${item.inpatient_count ?? 0}회`}
          tone={(item.inpatient_count ?? 0) > 0 ? "red-light" : "gray"}
        />
        <Chip label={`수술 ${surgN}건`} tone={surgN > 0 ? "red" : "gray"} />
        <Chip
          label={`투약 ${item.med_days ?? 0}일`}
          tone={
            (item.med_days ?? 0) >= 30 ? "amber" : (item.med_days ?? 0) > 0 ? "emerald" : "gray"
          }
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

export default memo(DiseaseCard);

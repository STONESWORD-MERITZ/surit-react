import { memo, useState } from "react";
import type { DiseaseSummary } from "../../types/disclosure";

function AllDiseaseSection({ diseases }: { diseases: DiseaseSummary[] }) {
  const [open, setOpen] = useState(false);

  if (!diseases.length) return null;

  return (
    <section className="mb-5 overflow-hidden rounded-[8px] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <span className="text-sm font-extrabold text-gray-900">전체 병력 요약</span>
          <span className="ml-2 text-xs font-semibold text-gray-400">{diseases.length}개 질환</span>
        </div>
        <span className="text-xs font-bold text-gray-400">{open ? "접기" : "펼치기"}</span>
      </button>

      {open && (
        <div className="border-t border-gray-100">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-gray-500">
                  <th className="px-4 py-2.5 text-left">코드</th>
                  <th className="px-4 py-2.5 text-left">질병명</th>
                  <th className="px-4 py-2.5 text-left">진료기간</th>
                  <th className="px-4 py-2.5 text-center">통원</th>
                  <th className="px-4 py-2.5 text-center">입원</th>
                  <th className="px-4 py-2.5 text-center">수술</th>
                  <th className="px-4 py-2.5 text-center">투약</th>
                  <th className="px-4 py-2.5 text-left">병원</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {diseases.map((d, i) => (
                  <tr key={`${d.code}-${i}`} className="hover:bg-gray-50/60">
                    <td className="px-4 py-2 font-mono text-gray-500">{d.display_code || d.code}</td>
                    <td className="max-w-[180px] truncate px-4 py-2 font-semibold text-gray-800">
                      {d.name || "-"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-gray-500">
                      {d.first_date}
                      {d.latest_date && d.latest_date !== d.first_date
                        ? ` ~ ${d.latest_date}`
                        : ""}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {d.visit_count > 0 ? (
                        <span
                          className={`font-semibold ${d.visit_count >= 7 ? "text-amber-600" : "text-gray-600"}`}
                        >
                          {d.visit_count}회
                        </span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {d.inpatient_days > 0 ? (
                        <span className="font-semibold text-red-500">{d.inpatient_days}일</span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {d.surgery_count > 0 ? (
                        <span className="font-semibold text-red-500">{d.surgery_count}건</span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {d.med_days > 0 ? (
                        <span
                          className={`font-semibold ${d.med_days >= 30 ? "text-amber-600" : "text-emerald-600"}`}
                        >
                          {d.med_days}일
                        </span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="max-w-[180px] truncate px-4 py-2 text-gray-500">
                      {(d.hospitals || []).slice(0, 2).join(", ") || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

export default memo(AllDiseaseSection);

import { memo } from "react";
import { Link } from "react-router-dom";
import type { AudienceMode } from "../../types/disclosure";

function ModeSwitch({ mode }: { mode: AudienceMode }) {
  return (
    <div className="mb-5 grid gap-3 md:grid-cols-2">
      <Link
        to="/check"
        className={`rounded-[8px] border p-4 transition ${
          mode === "customer"
            ? "border-emerald-300 bg-emerald-50"
            : "border-gray-200 bg-white hover:border-emerald-200"
        }`}
      >
        <p className="text-sm font-extrabold text-gray-900">고객용</p>
        <p className="mt-1 text-xs leading-5 text-gray-500">
          기존 가입 보험의 고지 누락 가능성을 점검합니다.
        </p>
      </Link>
      <Link
        to="/disclosure?mode=agent"
        className={`rounded-[8px] border p-4 transition ${
          mode === "agent"
            ? "border-indigo-300 bg-indigo-50"
            : "border-gray-200 bg-white hover:border-indigo-200"
        }`}
      >
        <p className="text-sm font-extrabold text-gray-900">설계사용</p>
        <p className="mt-1 text-xs leading-5 text-gray-500">
          청약 전 알릴의무 필터와 상담 메시지를 만듭니다.
        </p>
      </Link>
    </div>
  );
}

export default memo(ModeSwitch);

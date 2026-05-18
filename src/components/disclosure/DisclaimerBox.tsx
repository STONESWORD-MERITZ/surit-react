import { memo } from "react";

function DisclaimerBox({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div className="mt-8 rounded-xl border border-gray-200 bg-gray-50 px-5 py-4 text-[12px] leading-6 text-gray-600">
      <p className="mb-1 font-bold text-gray-700">⚠️ 분석 결과 활용 안내</p>
      본 분석 결과는 건강보험심평원 PDF 자료와 AI 의학 판단을 기반으로 한{" "}
      <b>참고 자료</b>입니다. 보험 가입·청구의 최종 판단은 보험회사 언더라이팅 및 약관에 따라
      결정되며, 본 서비스는 그에 따른 법적 책임을 지지 않습니다. 정확한 고지 여부는 가입하려는
      보험사 또는 보험설계사, 필요시 의료전문가와 직접 상담하시기 바랍니다.
    </div>
  );
}

export default memo(DisclaimerBox);

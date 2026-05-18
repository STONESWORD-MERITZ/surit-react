// AudienceMode 타입은 src/types/disclosure.ts 에서 관리
export type { AudienceMode } from "../types/disclosure";

export const modeCopy: Record<
  import("../types/disclosure").AudienceMode,
  {
    badge: string;
    title: string;
    subtitle: string;
    dateLabel: string;
    dateHelp: string;
    uploadHelp: string;
    button: string;
    emptyTitle: string;
    resultTitle: string;
    memoLabel: string;
  }
> = {
  customer: {
    badge: "고객용 무료 점검",
    title: "내 보험 고지 점검",
    subtitle:
      "이전에 가입한 보험이 청약 당시 병력 고지사항을 잘 지켜 가입됐는지 확인합니다.",
    dateLabel: "가입일 또는 점검 기준일",
    dateHelp: "이미 가입한 보험을 확인할 때는 해당 상품의 청약일을 넣어 주세요.",
    uploadHelp: "건강e음에서 발급한 기본진료, 세부진료, 처방조제 PDF를 올려 주세요.",
    button: "내 고지 리스크 점검",
    emptyTitle: "현재 기준으로 뚜렷한 고지 검토 항목이 없습니다.",
    resultTitle: "가입 당시 고지 검토 결과",
    memoLabel: "고객 안내용 점검 메모",
  },
  agent: {
    badge: "설계사용",
    title: "알릴의무 필터",
    subtitle:
      "심평원 병력 PDF를 기준으로 건강체와 간편심사 고지 대상 병력을 정리합니다.",
    dateLabel: "청약 예정일",
    dateHelp:
      "상품 가입 예정일 기준으로 3개월, 1년, 5년, 10년 기간을 계산합니다.",
    uploadHelp:
      "기본진료, 세부진료, 처방조제 PDF를 함께 올리면 정확도가 올라갑니다.",
    button: "AI 고지사항 추출",
    emptyTitle: "선택한 상품 기준의 고지 대상 항목이 없습니다.",
    resultTitle: "상품별 고지사항",
    memoLabel: "카카오 전송용 메시지",
  },
};

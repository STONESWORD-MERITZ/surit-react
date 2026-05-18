export type FriendlyError = {
  title: string;
  body: string;
  hint?: string;        // 사용자가 해볼 만한 조치
  retryable: boolean;   // 재시도 버튼을 보여줄지
};

const PATTERNS: { match: RegExp; build: (raw: string) => FriendlyError }[] = [
  // 네트워크
  {
    match: /Failed to fetch|NetworkError|ECONNREFUSED|연결/i,
    build: () => ({
      title: "서버에 연결할 수 없어요",
      body: "네트워크 상태를 확인하고 다시 시도해 주세요.",
      hint: "Wi-Fi/모바일 데이터 연결, VPN 설정을 확인해 보세요.",
      retryable: true,
    }),
  },
  // PDF 비밀번호
  {
    match: /비밀번호|password|encrypted/i,
    build: () => ({
      title: "PDF 비밀번호가 필요해요",
      body: "건강보험심평원 PDF 는 보통 생년월일(YYYYMMDD)이 비밀번호입니다.",
      hint: "분석 시작 화면에서 '생년월일'을 입력하고 다시 시도해 주세요.",
      retryable: true,
    }),
  },
  // PDF 손상
  {
    match: /손상|syntax|지원하지 않는/i,
    build: (raw) => ({
      title: "PDF 를 읽을 수 없어요",
      body: "파일이 손상되었거나 지원하지 않는 형식입니다.",
      hint: "심평원에서 다시 다운로드 후 시도해 주세요. (" + raw.slice(0, 60) + ")",
      retryable: true,
    }),
  },
  // 데이터 없음
  {
    match: /데이터를 추출하지/i,
    build: () => ({
      title: "분석할 데이터가 부족해요",
      body: "업로드한 PDF 에서 진료 데이터를 찾지 못했어요.",
      hint: "기본진료·세부진료·처방조제 PDF 가 모두 올라갔는지, 비밀번호가 맞는지 확인해 주세요.",
      retryable: true,
    }),
  },
  // API 키/서버 설정
  {
    match: /GOOGLE_API_KEY|서비스 점검|서버에서 분석/i,
    build: () => ({
      title: "서비스 점검 중이에요",
      body: "잠시 후 다시 시도해 주세요.",
      hint: "지속되면 페이지 하단 문의처로 알려 주세요.",
      retryable: true,
    }),
  },
  // 입력 검증
  {
    match: /YYYY-MM-DD|reference_date|product_type/i,
    build: () => ({
      title: "입력 정보를 다시 확인해 주세요",
      body: "기준일이나 심사 유형이 올바르지 않아요.",
      retryable: true,
    }),
  },
];

export function toFriendlyError(raw: unknown): FriendlyError {
  const s =
    typeof raw === "string"
      ? raw
      : (raw as { message?: string })?.message ?? "";
  for (const p of PATTERNS) {
    if (p.match.test(s)) return p.build(s);
  }
  return {
    title: "분석 중 문제가 생겼어요",
    body: "잠시 후 다시 시도해 주세요. 같은 문제가 반복되면 페이지 하단 문의처로 알려 주세요.",
    retryable: true,
  };
}

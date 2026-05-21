import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Disclosure from "./Disclosure";

vi.mock("../lib/auth-context", () => ({
  useAuth: () => ({
    session: { access_token: "test-access-token" },
  }),
}));

const mockAnalyzeResult = {
  flagged_count: 1,
  total_q_count: 1,
  total_visit_sum: 14,
  total_med_sum: 50,
  standard_reports: {
    "3번 질문: 10년 이내 입원/수술/7회이상통원/30일이상투약": [
      {
        first_date: "2022-08-09",
        latest_date: "2025-07-22",
        first_diagnosis_date: "2022-08-09",
        code: "M54",
        display_code: "M54",
        name: "등통증(경추 및 요추)",
        visit: 14,
        med_days: 50,
        med_days_30plus: true,
        inpatient: 0,
        inpatient_count: 0,
        inpatient_periods: [],
        surgery_count: 0,
        surgeries: [],
        procedures: [],
        surgery_suspected: [],
        additional_test_hit: false,
        treatment_ongoing: null,
        hospitals: ["가보자한의원"],
        first_hospital: "명제한의원",
        last_hospital: "가보자한의원",
        detail: "기본진료 확정",
      },
    ],
  },
  easy_reports: {},
  all_disease_summary: [
    {
      code: "M54",
      display_code: "M54",
      name: "등통증(경추 및 요추)",
      first_date: "2022-08-09",
      latest_date: "2025-07-22",
      visit_count: 14,
      inpatient_count: 0,
      inpatient_days: 0,
      surgery_count: 0,
      med_days: 50,
      hospitals: ["가보자한의원"],
    },
  ],
  standard_kakao: "테스트 카카오 메시지",
  easy_kakao: "",
  parse_errors: [],
  warnings: [],
  meritz_easy_message: "",
};

describe("Disclosure guided tour", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/analyze")) {
          return new Response(JSON.stringify(mockAnalyzeResult), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows pre-filter steps first and post-result steps after analysis", async () => {
    const user = userEvent.setup();

    const { container } = render(
      <MemoryRouter initialEntries={["/disclosure?mode=agent"]}>
        <Disclosure />
      </MemoryRouter>,
    );

    expect(await screen.findByText("1 / 6")).toBeInTheDocument();
    expect(screen.getByText("설계사용 또는 고객용 선택")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "다음" }));
    expect(await screen.findByText("2 / 6")).toBeInTheDocument();
    expect(screen.getByText("청약 예정일 입력")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "다음" }));
    expect(await screen.findByText("3 / 6")).toBeInTheDocument();
    expect(screen.getByText("PDF 첨부")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "완료" }));
    await user.upload(
      container.querySelector("input[type='file']") as HTMLInputElement,
      new File(["mock"], "sample.pdf", { type: "application/pdf" }),
    );
    const analyzeButton = screen.getByRole("button", { name: "AI 고지사항 추출" });
    expect(analyzeButton).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(analyzeButton).toBeEnabled();
    await user.click(analyzeButton);

    expect(await screen.findByText("4 / 6")).toBeInTheDocument();
    expect(screen.getByText("병력 요약 펼치기 또는 접기")).toBeInTheDocument();
    expect(screen.getAllByText("등통증(경추 및 요추)")[0]).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("전체 병력 요약").closest("button")).toHaveTextContent("펼치기");
    });
  });
});

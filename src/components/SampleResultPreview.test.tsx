import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SampleResultPreview from "./SampleResultPreview";

describe("SampleResultPreview", () => {
  it("샘플 두 질환과 요약 카드를 렌더한다", () => {
    render(
      <MemoryRouter>
        <SampleResultPreview />
      </MemoryRouter>,
    );
    // 요약
    expect(screen.getByText(/고지 질환/)).toBeInTheDocument();
    expect(screen.getByText(/추천 심사/)).toBeInTheDocument();
    expect(screen.getByText(/건강체 가능/)).toBeInTheDocument();
    // 질환 카드 2개
    expect(screen.getByText(/만성 단순치주염/)).toBeInTheDocument();
    expect(screen.getByText(/K05\.30/)).toBeInTheDocument();
    expect(screen.getByText(/자궁체부의 용종/)).toBeInTheDocument();
    expect(screen.getByText(/N84\.0/)).toBeInTheDocument();
    // 칩
    expect(screen.getByText(/통원 30회/)).toBeInTheDocument();
    expect(screen.getByText(/입원 1일·1회/)).toBeInTheDocument();
  });

  it("DOM 스냅샷이 안정적이다", () => {
    const { asFragment } = render(
      <MemoryRouter>
        <SampleResultPreview />
      </MemoryRouter>,
    );
    expect(asFragment()).toMatchSnapshot();
  });
});

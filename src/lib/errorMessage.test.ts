import { toFriendlyError } from "./errorMessage";

describe("toFriendlyError", () => {
  it("네트워크 오류를 감지한다", () => {
    const r = toFriendlyError(new Error("Failed to fetch"));
    expect(r.title).toMatch(/연결/);
    expect(r.retryable).toBe(true);
  });

  it("비밀번호 오류를 감지한다", () => {
    const r = toFriendlyError("PDF 비밀번호가 걸려있습니다");
    expect(r.title).toMatch(/비밀번호/);
    expect(r.hint).toMatch(/생년월일/);
  });

  it("PDF 손상 메시지를 감지한다", () => {
    const r = toFriendlyError("syntax error in pdf 손상");
    expect(r.title).toMatch(/읽을 수 없/);
  });

  it("데이터 없음 메시지를 감지한다", () => {
    const r = toFriendlyError("데이터를 추출하지 못했습니다");
    expect(r.title).toMatch(/부족/);
    expect(r.retryable).toBe(true);
  });

  it("미매치 시 기본 메시지로 폴백한다", () => {
    const r = toFriendlyError("뭔가 알 수 없는 메시지");
    expect(r.title).toMatch(/문제가 생겼어요/);
    expect(r.retryable).toBe(true);
  });

  it("Error 객체를 처리한다", () => {
    const r = toFriendlyError(new Error("NetworkError: connection refused"));
    expect(r.retryable).toBe(true);
  });

  it("null/undefined 를 기본 메시지로 처리한다", () => {
    const r = toFriendlyError(null);
    expect(r.title).toBeTruthy();
    expect(r.retryable).toBe(true);
  });
});

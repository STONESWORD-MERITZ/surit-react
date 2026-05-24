import { useState } from "react";
import { Link } from "react-router-dom";
import { supabase } from "../lib/supabase";

export default function Signup() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);
  const [agreeMedical, setAgreeMedical] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agreeTerms || !agreePrivacy || !agreeMedical) return;
    setError("");
    setLoading(true);
    const { error } = await supabase.auth.signUp({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
    } else {
      setDone(true);
    }
  };

  if (done) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F8F9FC] px-4">
        <div className="w-full max-w-sm text-center">
          <h2 className="mb-2 text-lg font-extrabold text-gray-900">이메일을 확인해 주세요</h2>
          <p className="mb-6 text-sm leading-6 text-gray-400">
            {email} 주소로 인증 메일을 보냈습니다.
            <br />
            메일의 링크를 누르면 가입이 완료됩니다.
          </p>
          <Link to="/login" className="text-sm font-bold text-[#4F46E5] hover:underline">
            로그인으로 돌아가기
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F8F9FC] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-10 text-center">
          <h1 className="text-3xl font-black tracking-tight text-gray-900">
            SUR<span className="text-[#4F46E5]">IT</span>
          </h1>
          <p className="mt-2 text-sm text-gray-400">설계사용 계정 만들기</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            placeholder="이메일"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded-[8px] bg-white px-4 py-3 text-sm text-gray-800 shadow-[0_1px_3px_rgba(0,0,0,0.06)] placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-[#4F46E5]/30"
          />
          <input
            type="password"
            placeholder="비밀번호 10자 이상"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={10}
            className="w-full rounded-[8px] bg-white px-4 py-3 text-sm text-gray-800 shadow-[0_1px_3px_rgba(0,0,0,0.06)] placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-[#4F46E5]/30"
          />

          <div className="mt-4 space-y-2 text-sm">
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                required
                checked={agreeTerms}
                onChange={(e) => setAgreeTerms(e.target.checked)}
                className="mt-0.5 shrink-0"
              />
              <span>
                <a href="/terms" target="_blank" className="font-semibold underline">이용약관</a>에 동의합니다 (필수)
              </span>
            </label>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                required
                checked={agreePrivacy}
                onChange={(e) => setAgreePrivacy(e.target.checked)}
                className="mt-0.5 shrink-0"
              />
              <span>
                <a href="/privacy" target="_blank" className="font-semibold underline">개인정보처리방침</a>에 동의합니다 (필수)
              </span>
            </label>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                required
                checked={agreeMedical}
                onChange={(e) => setAgreeMedical(e.target.checked)}
                className="mt-0.5 shrink-0"
              />
              <span>
                민감정보(건강·의료정보) 처리에 동의합니다. 동의하지 않을 경우 분석 기능 이용이 제한됩니다. (필수)
              </span>
            </label>
          </div>

          {error && <p className="text-xs font-semibold text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={loading || !agreeTerms || !agreePrivacy || !agreeMedical}
            className="w-full rounded-[8px] bg-[#4F46E5] py-3 text-sm font-bold text-white shadow-[0_2px_8px_rgba(79,70,229,0.3)] transition-colors hover:bg-[#4338CA] disabled:opacity-50"
          >
            {loading ? "가입 중..." : "회원가입"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-gray-400">
          이미 계정이 있나요?{" "}
          <Link to="/login" className="font-bold text-[#4F46E5] hover:underline">
            로그인
          </Link>
        </p>
      </div>
    </div>
  );
}

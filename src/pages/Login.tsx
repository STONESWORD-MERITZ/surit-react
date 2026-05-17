import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
    } else {
      navigate("/");
    }
  };

  const handleKakao = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "kakao",
      options: { redirectTo: window.location.origin },
    });
  };

  const handleGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F8F9FC] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-10 text-center">
          <h1 className="text-3xl font-black tracking-tight text-gray-900">
            SUR<span className="text-[#4F46E5]">IT</span>
          </h1>
          <p className="mt-2 text-sm text-gray-400">설계사용 고지 필터에 로그인하세요</p>
        </div>

        <div className="space-y-3">
          <button
            onClick={handleKakao}
            className="flex w-full items-center justify-center rounded-[8px] py-3 text-sm font-bold transition-colors"
            style={{ background: "#FEE500", color: "#191919" }}
          >
            카카오로 시작하기
          </button>

          <button
            onClick={handleGoogle}
            className="flex w-full items-center justify-center rounded-[8px] border border-gray-200 bg-white py-3 text-sm font-bold text-gray-700 shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-colors hover:bg-gray-50"
          >
            Google로 시작하기
          </button>
        </div>

        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-gray-200" />
          <span className="text-xs font-semibold text-gray-300">또는</span>
          <div className="h-px flex-1 bg-gray-200" />
        </div>

        <form onSubmit={handleEmail} className="space-y-3">
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
            placeholder="비밀번호"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded-[8px] bg-white px-4 py-3 text-sm text-gray-800 shadow-[0_1px_3px_rgba(0,0,0,0.06)] placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-[#4F46E5]/30"
          />

          {error && <p className="text-xs font-semibold text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-[8px] bg-[#4F46E5] py-3 text-sm font-bold text-white shadow-[0_2px_8px_rgba(79,70,229,0.3)] transition-colors hover:bg-[#4338CA] disabled:opacity-50"
          >
            {loading ? "로그인 중..." : "이메일로 로그인"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-gray-400">
          아직 계정이 없나요?{" "}
          <Link to="/signup" className="font-bold text-[#4F46E5] hover:underline">
            회원가입
          </Link>
        </p>
        <p className="mt-4 text-center text-xs text-gray-400">
          고객용 무료 점검은{" "}
          <Link to="/check" className="font-bold text-emerald-600 hover:underline">
            로그인 없이 이용
          </Link>
          할 수 있습니다.
        </p>
      </div>
    </div>
  );
}

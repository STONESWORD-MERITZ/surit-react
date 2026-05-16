import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth-context";

export default function Layout() {
  const { user, signOut } = useAuth();

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-5 h-14 flex items-center text-sm font-semibold transition-colors whitespace-nowrap ${
      isActive
        ? "text-[#4F46E5] font-bold"
        : "text-gray-400 hover:text-gray-700"
    }`;

  return (
    <div className="min-h-screen bg-[#F8F9FC]">
      <nav className="sticky top-0 z-50 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)]">
        <div className="max-w-5xl mx-auto flex items-center px-4">
          <NavLink
            to="/"
            className="px-4 h-14 flex items-center text-base font-black text-gray-900 hover:text-[#4F46E5] tracking-tight"
          >
            SUR<span className="text-[#4F46E5]">IT</span>
          </NavLink>
          <NavLink to="/disclosure" className={linkClass}>
            알릴의무 필터
          </NavLink>
          <NavLink to="/before-after" className={linkClass}>
            보장분석
          </NavLink>

          <div className="ml-auto flex items-center gap-3">
            {user ? (
              <>
                <span className="text-xs text-gray-400 hidden sm:inline">
                  {user.email}
                </span>
                <button
                  onClick={signOut}
                  className="px-4 py-1.5 text-xs font-semibold text-gray-500 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  로그아웃
                </button>
              </>
            ) : (
              <NavLink
                to="/login"
                className="px-4 py-1.5 text-xs font-bold text-white bg-[#4F46E5] hover:bg-[#4338CA] rounded-lg transition-colors"
              >
                로그인
              </NavLink>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}

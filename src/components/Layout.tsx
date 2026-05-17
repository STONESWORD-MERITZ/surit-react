import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth-context";

export default function Layout() {
  const { user, signOut } = useAuth();

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-4 h-14 flex items-center text-sm font-semibold transition-colors whitespace-nowrap ${
      isActive
        ? "text-[#4F46E5] font-bold"
        : "text-gray-500 hover:text-gray-800"
    }`;

  return (
    <div className="min-h-screen bg-[#F8F9FC]">
      <nav className="sticky top-0 z-50 border-b border-gray-100 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center px-4">
          <NavLink
            to="/"
            className="flex h-14 items-center px-3 text-base font-black tracking-tight text-gray-950 hover:text-[#4F46E5]"
          >
            SUR<span className="text-[#4F46E5]">IT</span>
          </NavLink>
          <NavLink to="/check" className={linkClass}>
            고객 점검
          </NavLink>
          <NavLink to="/disclosure?mode=agent" className={linkClass}>
            설계사 필터
          </NavLink>
          <NavLink to="/before-after" className={linkClass}>
            보장분석
          </NavLink>

          <div className="ml-auto flex items-center gap-3">
            {user ? (
              <>
                <span className="hidden text-xs text-gray-400 sm:inline">{user.email}</span>
                <button
                  onClick={signOut}
                  className="rounded-[8px] bg-gray-100 px-4 py-1.5 text-xs font-semibold text-gray-600 transition-colors hover:bg-gray-200"
                >
                  로그아웃
                </button>
              </>
            ) : (
              <NavLink
                to="/login"
                className="rounded-[8px] bg-[#4F46E5] px-4 py-1.5 text-xs font-bold text-white transition-colors hover:bg-[#4338CA]"
              >
                로그인
              </NavLink>
            )}
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-5 py-8">
        <Outlet />
      </main>
    </div>
  );
}

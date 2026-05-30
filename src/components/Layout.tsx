import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth-context";
import Footer from "./Footer";

export default function Layout() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen bg-[#F8F9FC]">
      <header className="sticky top-0 z-30 border-b border-gray-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link
            to="/"
            className="text-lg font-extrabold tracking-tight text-gray-950 hover:text-indigo-600 transition-colors"
          >
            BOHUM<span className="text-indigo-600">FIT</span>
          </Link>

          <nav className="flex items-center gap-5 text-sm font-semibold text-gray-600">
            <NavLink
              to="/why"
              className={({ isActive }) =>
                isActive ? "text-indigo-600" : "hover:text-gray-900 transition-colors"
              }
            >
              왜 중요한가
            </NavLink>
            <NavLink
              to="/check"
              className={({ isActive }) =>
                isActive ? "text-indigo-600" : "hover:text-gray-900 transition-colors"
              }
            >
              고객 점검
            </NavLink>
            <NavLink
              to="/disclosure"
              className={({ isActive }) =>
                isActive ? "text-indigo-600" : "hover:text-gray-900 transition-colors"
              }
            >
              설계사 필터
            </NavLink>
          </nav>

          <div className="flex items-center gap-3 text-sm">
            {user ? (
              <>
                <span className="hidden text-xs text-gray-400 sm:inline">{user.email}</span>
                <button
                  onClick={signOut}
                  className="rounded-lg bg-gray-100 px-4 py-1.5 text-xs font-semibold text-gray-600 transition-colors hover:bg-gray-200"
                >
                  로그아웃
                </button>
              </>
            ) : (
              <NavLink
                to="/login"
                className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-bold text-white transition-colors hover:bg-indigo-700"
              >
                로그인
              </NavLink>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

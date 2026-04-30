import { NavLink, Outlet } from "react-router-dom";

export default function Layout() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-5 h-14 flex items-center text-sm font-semibold transition-colors whitespace-nowrap ${
      isActive
        ? "text-[#4F46E5] font-bold"
        : "text-gray-400 hover:text-gray-700"
    }`;

  return (
    <div className="min-h-screen bg-[#F8F9FC]">
      <nav className="sticky top-0 z-50 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)]">
        <div className="max-w-5xl mx-auto flex items-center gap-1 px-4">
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
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}

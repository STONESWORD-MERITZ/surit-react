/* eslint-disable react-refresh/only-export-components */
import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import * as Sentry from "@sentry/react";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Home from "./pages/Home";
import Disclosure from "./pages/Disclosure";
import BeforeAfter from "./pages/BeforeAfter";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import Terms from "./pages/Terms";
import History from "./pages/History";
import HistoryDetail from "./pages/HistoryDetail";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function FallbackUI() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6 text-center">
      <div className="max-w-md">
        <p className="text-2xl font-extrabold text-gray-900">잠시 문제가 생겼어요</p>
        <p className="mt-2 text-sm text-gray-600">
          페이지를 새로고침하거나, 잠시 후 다시 시도해 주세요.
        </p>
        <button
          onClick={() => location.reload()}
          className="mt-5 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-bold text-white"
        >
          새로고침
        </button>
      </div>
    </div>
  );
}

function App() {
  useEffect(() => {
    void fetch(`${API_BASE}/api/health`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    }).catch(() => {
      // Warm-up call should never block initial render.
    });
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route
            path="disclosure"
            element={<ProtectedRoute><Disclosure initialMode="agent" /></ProtectedRoute>}
          />
          <Route path="check" element={<Disclosure initialMode="customer" />} />
          <Route
            path="before-after"
            element={<ProtectedRoute><BeforeAfter /></ProtectedRoute>}
          />
          <Route path="privacy" element={<PrivacyPolicy />} />
          <Route path="terms" element={<Terms />} />
          <Route
            path="history"
            element={<ProtectedRoute><History /></ProtectedRoute>}
          />
          <Route
            path="history/:id"
            element={<ProtectedRoute><HistoryDetail /></ProtectedRoute>}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default Sentry.withErrorBoundary(App, { fallback: <FallbackUI /> });

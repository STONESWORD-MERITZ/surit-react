import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Home from "./pages/Home";
import Disclosure from "./pages/Disclosure";
import BeforeAfter from "./pages/BeforeAfter";
import Login from "./pages/Login";
import Signup from "./pages/Signup";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
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
            element={<ProtectedRoute><Disclosure /></ProtectedRoute>}
          />
          <Route
            path="before-after"
            element={<ProtectedRoute><BeforeAfter /></ProtectedRoute>}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

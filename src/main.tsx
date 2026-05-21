import * as Sentry from "@sentry/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { AuthProvider } from "./lib/AuthContext";

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.MODE,
    release: __APP_RELEASE__,
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0.0,   // 세션 리플레이 비활성(PII 보호)
    replaysOnErrorSampleRate: 0.0,
    beforeSend(event) {
      // 폼 입력값 등 PII 제거
      if (event.request?.data) delete event.request.data;
      if (event.request?.cookies) delete event.request.cookies;
      return event;
    },
  });
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);

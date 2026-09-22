/**
 * main.tsx — 진입점. `?view=ops` 면 관제 화면, 아니면 내비.  (DECISIONS §214-4)
 *
 * ★ 관제는 **나중에 읽는다**(lazy). 차량 단말에서 내비만 쓰는데 관제 코드를 같이 받을
 *   이유가 없다. 한 앱 · 한 배포 · 한 데이터(`../data/`)이고 화면만 둘이다.
 */
import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

const OpsApp = lazy(() => import("./OpsApp"));
const view = new URLSearchParams(location.search).get("view");
if (view === "ops") document.title = "Fire-Lane 관제";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {view === "ops"
      ? <Suspense fallback={<div style={{ padding: 24 }}>관제 화면 불러오는 중…</div>}><OpsApp /></Suspense>
      : <App />}
  </StrictMode>,
);

/**
 * main.tsx — 진입점. **관제가 루트(`/`)고 내비가 `/navi/`** 다.  (§214-4 · §258)
 *
 * ★ 2026-09-25 (§258). 종전에는 관제의 공개 주소가 `navi/?view=ops` 였고 루트는
 *   거기로 튕기는 리다이렉트였다. 쿼리스트링은 주소가 아니다 — 남한테 보낼 링크가
 *   못 되고 북마크도 안 된다. 그래서 **배포가 루트에 관제를 앉힌다**:
 *   `build-navi` 가 빌드본을 루트로 복사하고 `window.__FL_VIEW="ops"` 를 박는다.
 *   자산 경로가 절대(`/<repo>/navi/assets/`)라 루트에서 그대로 뜬다.
 *
 * ★ 경로로 판정하지 않는다. dev 서버의 루트는 `web/navi` 라 `location.pathname`
 *   이 `/` 다 — 경로로 보면 **개발에서 기본 화면이 내비에서 관제로 뒤집힌다.**
 *   박아 넣은 표시를 읽으면 그 사고가 없다. `?view=` 는 종전대로 이긴다.
 *
 * ★ 관제는 **나중에 읽는다**(lazy). 차량 단말에서 내비만 쓰는데 관제 코드를 같이 받을
 *   이유가 없다. 한 앱 · 한 배포 · 한 데이터(`../data/`)이고 화면만 둘이다.
 */
import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

const OpsApp = lazy(() => import("./OpsApp"));
declare global { interface Window { __FL_VIEW?: string } }
const view = new URLSearchParams(location.search).get("view") ?? window.__FL_VIEW ?? null;
if (view === "ops") document.title = "Fire-Lane 관제";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {view === "ops"
      ? <Suspense fallback={<div style={{ padding: 24 }}>관제 화면 불러오는 중…</div>}><OpsApp /></Suspense>
      : <App />}
  </StrictMode>,
);

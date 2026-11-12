/**
 * playwright.config.ts — **브라우저 스모크.**  (DECISIONS §700 · PLAN #223)
 *
 * ★ 무엇을 묻나 — 「뜨는가」와 「콘솔이 조용한가」 둘뿐이다. 화면의 내용 · 모양 · 글자는 안 묻는다(고칠 때마다 시험이 운다).
 * ★ 왜 있나 — vitest 546개는 node 환경의 문자열 렌더라 번들 · 모듈 해시 · 서비스 워커 · 브라우저 전역이 없다. 그래서
 *   관제가 두 달 동안 흰 화면이 될 수 있었는데 시험은 초록이었다(DECISIONS §699).
 * ★ 둘을 돈다 — `dev`(개발 서버. 오늘의 결함이 산 자리) · `built`(빌드본을 `tools/serve.py` 가 배포 모양으로 내준다. 번들 쪽 중복).
 *   빌드본은 `dist/` 가 있어야 하고 CI 는 항상 빌드한다. 로컬에서 `dist/` 가 없으면 `built` 는 **건너뛴다고 말한다**(조용히 빼지 않는다).
 * ★ CI 만 돈다(`tools/gatefast.py` 의 LAYERS) — 브라우저 내려받기 + 개발 서버 재시작 시험은 훅 예산(30초) 밖이다.
 *   로컬에서 보려면 `cd web/navi && npx playwright install --only-shell chromium && npm run smoke`.
 *
 * IN    개발 서버(5184) · `web/navi/dist` + `tools/serve.py`(4173)
 * OUT   종료 코드 · 실패한 화면의 흔적(`node_modules/.playwright-results/`)
 * PARAM 화면이 떴다고 볼 최소 글자 수는 `e2e/smoke.spec.ts` 의 `MIN_TEXT`
 */
import fs from "node:fs";
import { defineConfig } from "@playwright/test";

const CI = !!process.env.CI;
const HAS_DIST = fs.existsSync("dist/index.html");
if (!CI && !HAS_DIST) console.warn("[smoke] dist/ 가 없다 — `built` 는 건너뛴다(`npm run build` 후 다시)");

const DEV = "http://127.0.0.1:5184/fire-lane/navi/";
const BUILT = "http://127.0.0.1:4173/fire-lane/navi/";
// ★ 헤드리스 셸에서 지도(WebGL)가 그려지게 소프트웨어 렌더러를 쓴다 — 지도 로드 오류도 콘솔에 나오므로 그려져야 한다.
const GL = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"];

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  retries: 0,                    // 흔들리는 시험을 재시도로 덮지 않는다
  workers: 1,                    // 개발 서버 하나를 같이 쓰고 재시작 시험이 포트를 쥔다
  reporter: CI ? [["list"], ["github"]] : "list",
  outputDir: "node_modules/.playwright-results",   // node_modules 안 — 실패 흔적(error-context.md)이 「문서 넷 밖의 문서」로 안 센다
  use: { launchOptions: { args: GL }, trace: "off" },
  projects: [
    { name: "dev", use: { baseURL: DEV } },
    ...(CI || HAS_DIST ? [{ name: "built", use: { baseURL: BUILT } }] : []),
  ],
  webServer: [
    {
      command: "npx vite --port 5184 --strictPort --host 127.0.0.1",
      url: DEV, reuseExistingServer: false, timeout: 60_000,
      env: { FL_VITE_CACHE: "node_modules/.vite-smoke" },
    },
    ...(CI || HAS_DIST ? [{
      command: "python3 ../../tools/serve.py 4173",
      url: BUILT, reuseExistingServer: false, timeout: 30_000,
    }] : []),
  ],
});

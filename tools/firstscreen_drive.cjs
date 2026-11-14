// tools/firstscreen_drive.cjs — `tools/firstscreen.py` 의 브라우저 쪽. 한 화면을 열고 **서버가 새 응답을 안 낼 때까지** 기다린다.
//
// 인자  <기준 주소> <경로+쿼리>      예: http://127.0.0.1:4180 /fire-lane/navi/?dev=1
// 하는 일  헤드리스 크로미움(소프트웨어 GL · 서비스 워커 차단 = 콜드 캐시)으로 열고, 서버의 `/__log` 길이가 4초 동안 안 변하면 닫는다.
// 안 하는 일  바이트를 안 센다 — 서버가 응답마다 기록한다(지도 워커가 내는 요청은 브라우저 쪽 측정기가 못 본다 · DECISIONS §787-C).
const { createRequire } = require("module");
const path = require("path");
const req = createRequire(path.join(__dirname, "..", "web", "navi", "package.json"));
const { chromium } = req("@playwright/test");

const GL = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"];
const [base, url] = process.argv.slice(2);
const QUIET_MS = 4000, MIN_MS = 6000, CAP_MS = 90000;

(async () => {
  const b = await chromium.launch({ args: GL });
  const ctx = await b.newContext({ serviceWorkers: "block", viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  await page.goto(base + url, { waitUntil: "commit" });
  let n = -1, changed = Date.now();
  while (Date.now() - t0 < CAP_MS) {
    const log = await (await fetch(base + "/__log")).json().catch(() => null);
    if (log && log.length !== n) { n = log.length; changed = Date.now(); }
    if (Date.now() - changed > QUIET_MS && Date.now() - t0 > MIN_MS) break;
    await page.waitForTimeout(250);
  }
  const canvas = await page.locator("canvas.maplibregl-canvas").count();
  await b.close();
  process.exit(canvas ? 0 : 3);       // 지도 캔버스가 없으면 「뜨지 않았다」 — 바이트가 적은 것이 좋은 소식이 아니다
})().catch((e) => { console.error(e); process.exit(2); });

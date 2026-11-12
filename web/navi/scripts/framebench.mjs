/**
 * scripts/framebench.mjs — **한 프레임이 어디서 먹히는지 수로 잰다.**  (DECISIONS §722 · §723)
 *
 *     cd web/navi && npm run dev                      (다른 터미널 — 또는 `npm run build` 뒤 `python3 ../../tools/serve.py 4173`)
 *     FRAME_URL=http://127.0.0.1:5173/fire-lane/navi/ npm run framebench -- drive 10
 *
 *     drive    시연 ×1 로 주행 중(`?demo=1`) — 카메라 추종 루프가 매 프레임 `jumpTo` 를 부른다
 *     ops      관제 유휴
 *     opsmove  관제에서 카메라를 20Hz 로 움직인다(`jumpTo`) — 추종 루프와 같은 호출
 *
 * ★ 재기만 한다. 잰 것: ① rAF 간격(중앙 · p95 · 최대 · 50ms 초과 수) ② **긴 작업**(main 을 50ms 넘게 막은 것 — 개수 · 합) ③ CDP 프로파일러의 자기 시간 상위 함수
 *   ④ 도로명 라벨 갱신(`querySourceFeatures` · `setData`)의 **호출 수 · 한 번의 비용**(`?debug=1` 로 지도 객체가 노출될 때).
 * ★ **한계 — 헤드리스 크로미움은 소프트웨어 GL(swiftshader)이다.** 프레임 간격은 GPU 가 아니라 CPU 에뮬레이션이 정한다(주행 1~1.4fps) — **간격만으로는 JS 의 몫을 못 가린다.**
 *   그래서 ② 와 ④ 가 쓸모다: GL 이 어떻든 main 스레드를 JS 가 얼마나 막았는가. 실기 GPU 의 프레임 시간은 이 도구가 못 잰다.
 * IN    FRAME_URL(기본 5173) · 시나리오 · 초
 * OUT   표준출력 한 줄(JSON) + 상위 함수 목록
 */
import { chromium } from "@playwright/test";

const BASE = process.env.FRAME_URL ?? "http://127.0.0.1:5173/fire-lane/navi/";
const [scen = "drive", secs = "10"] = process.argv.slice(2);
const ORDER = "vehicle=pump-js&station=지산&incident=126.921389,35.154563&label=동구%20경양로%20293";
const URLS = { drive: `${BASE}?demo=1&debug=1&${ORDER}`, ops: `${BASE}?view=ops&debug=1`, opsmove: `${BASE}?view=ops&debug=1` };
if (!URLS[scen]) { console.error(`시나리오는 ${Object.keys(URLS).join(" · ")} 중 하나다`); process.exit(2); }

const stat = (a) => {
  if (!a?.length) return null;
  const s = [...a].sort((x, y) => x - y);
  return { n: a.length, median_ms: +s[Math.floor(s.length / 2)].toFixed(1), max_ms: +s.at(-1).toFixed(1), sum_ms: +a.reduce((x, y) => x + y, 0).toFixed(0) };
};

const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const pg = await b.newPage({ viewport: { width: 1280, height: 800 } });
await pg.goto(URLS[scen], { waitUntil: "domcontentloaded" });
await pg.waitForTimeout(9000);
if (scen === "drive") { await pg.getByText("안내 시작").click(); await pg.waitForTimeout(4000); }   // 시연 ×1 이 달리기 시작할 때까지

await pg.evaluate(() => {
  const m = window.__flMap; window.__q = []; window.__sd = [];
  if (m) {
    const q = m.querySourceFeatures.bind(m);
    m.querySourceFeatures = (...a) => { const t = performance.now(); const r = q(...a); window.__q.push(performance.now() - t); return r; };
    const s = m.getSource("road_labels");
    if (s) { const sd = s.setData.bind(s); s.setData = (...a) => { const t = performance.now(); const r = sd(...a); window.__sd.push(performance.now() - t); return r; }; }
  }
  window.__f = []; window.__lt = [];
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({ entryTypes: ["longtask"] }); } catch { /* 긴 작업을 못 본다 */ }
  let last = performance.now();
  const tick = (t) => { window.__f.push(t - last); last = t; window.__r = requestAnimationFrame(tick); };
  window.__r = requestAnimationFrame(tick);
});
const cdp = await pg.context().newCDPSession(pg);
await cdp.send("Profiler.enable"); await cdp.send("Profiler.setSamplingInterval", { interval: 500 }); await cdp.send("Profiler.start");
if (scen === "opsmove") {
  await pg.evaluate((ms) => new Promise((res) => {
    const m = window.__flMap, c = m.getCenter(); let i = 0; const t0 = performance.now();
    const id = setInterval(() => { i++; m.jumpTo({ center: [c.lng + i * 0.00004, c.lat + i * 0.00002], zoom: 17 }); if (performance.now() - t0 > ms) { clearInterval(id); res(); } }, 50);
  }), Number(secs) * 1000);
} else await pg.waitForTimeout(Number(secs) * 1000);
const { profile } = await cdp.send("Profiler.stop");
const r = await pg.evaluate(() => { cancelAnimationFrame(window.__r); return { f: window.__f.slice(2), lt: window.__lt, q: window.__q, sd: window.__sd }; });

const self = new Map(), nodes = new Map(profile.nodes.map((n) => [n.id, n]));
let total = 0;
profile.samples.forEach((id, i) => {
  const cf = nodes.get(id).callFrame, d = profile.timeDeltas[i] / 1000; total += d;
  const k = `${cf.functionName || "(익명)"} · ${(cf.url || "").split("/").slice(-2).join("/")}`;
  self.set(k, (self.get(k) ?? 0) + d);
});
const top = [...self.entries()].sort((x, y) => y[1] - x[1]).slice(0, 10).map(([k, v]) => `${v.toFixed(0)}ms ${(100 * v / total).toFixed(1)}% ${k}`);
const f = [...r.f].sort((x, y) => x - y), qn = (p) => f[Math.min(f.length - 1, Math.floor(p * f.length))];
const res = {
  scen, secs: Number(secs), fps: +(f.length / Number(secs)).toFixed(1), frame_median_ms: +qn(0.5).toFixed(1), frame_p95_ms: +qn(0.95).toFixed(1), frame_max_ms: +f.at(-1).toFixed(1),
  over50: f.filter((x) => x > 50).length, longtasks: r.lt.length, longtask_sum_ms: r.lt.reduce((x, y) => x + y, 0),
  label_query: stat(r.q), label_setData: stat(r.sd),
};
console.log(JSON.stringify(res));
console.log(top.join("\n"));
await b.close();

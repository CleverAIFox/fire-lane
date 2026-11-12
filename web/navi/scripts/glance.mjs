/**
 * scripts/glance.mjs — **주행 중 화면을 시선 규범의 수로 잰다.**  (DECISIONS §702)
 *
 *     cd web/navi && npm run dev            (다른 터미널)
 *     cd web/navi && npm run glance         GLANCE_URL=http://127.0.0.1:5173/fire-lane/navi/ 가 기본값
 *
 * ★ 재기만 한다 — 화면을 안 고친다. 고칠 자리는 사람이 수를 보고 가른다.
 * ★ 잰 것(차량 UI 규범 · 출처는 `tools/uicheck.py` 머리말): 한 줄에 보이는 **글자 수**(20 초과) · **글자 크기**(24px 미만) · **터치 타깃**(76px 미만) ·
 *   **자동으로 도는 것**. 줄은 브라우저가 실제로 꺾은 줄이다(글자마다 위치를 재서 묶는다). 지도 위 글자(캔버스)와 개발 막대(DevBar)는 안 센다.

 * ★ 병목 패널은 **기본(열림)** · 「자세히」 열림(정차 중 상세 · 참고) · 닫힘을 따로 잰다(DECISIONS §703).
 * ★ 상태 18개를 DevBar 의 「시연 상태」로 차례로 띄운다 — 그래서 `?dev=1` 이다. 병목 패널은 열린 것과 닫힌 것을 따로 잰다.
 * ★ **관제 화면은 안 잰다** — 운전 중이 아니다(앉아서 여러 정보를 동시에 보는 화면이라 규범이 다르다).
 * 한계: 헤드리스 크로미움 1280×800 · CSS px = dp 로 본다(1x). 실제 단말의 화면 크기 · 밀도는 다르다.
 */
import { chromium } from "@playwright/test";

const BASE = process.env.GLANCE_URL ?? "http://127.0.0.1:5173/fire-lane/navi/";
const URL = `${BASE}?dev=1&vehicle=pump-js&station=지산&incident=126.921389,35.154563&label=동구%20경양로%20293`;
const GLANCE = 20, FONT = 24, TARGET = 76;
const KEYS = ["safe", "fast", "approach", "reroute", "noCctv", "gpsWeak", "offline", "restored", "dataDelayed", "serviceError",
  "noRoute", "noData", "arrived", "blocked", "detour", "detourAccess", "noDetour", "reported"];

// 페이지 안에서 도는 코드는 **문자열**이다 — 이 파일은 Node 에서 도므로 `document` 를 쓰는 함수를 직접 적으면 린트가 미정의로 운다.
const MEASURE = `(() => {
  const vw = innerWidth, vh = innerHeight;
  const devbar = [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "처음부터")?.parentElement;
  const skip = (el) => (devbar && devbar.contains(el)) || el.closest(".maplibregl-ctrl, .maplibregl-canvas-container, .maplibregl-control-container");
  const visible = (el) => { const cs = getComputedStyle(el); if (cs.display === "none" || cs.visibility === "hidden" || +cs.opacity === 0) return false;
    const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0 && r.left < vw && r.top < vh; };
  const lines = [];
  const w = document.createTreeWalker(document.getElementById("root"), NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) {
    const t = n.nodeValue; if (!t.trim()) continue;
    const el = n.parentElement; if (!el || skip(el) || !visible(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    const rg = document.createRange(); const byTop = new Map();
    for (let i = 0; i < t.length; i++) { rg.setStart(n, i); rg.setEnd(n, i + 1); const rr = rg.getClientRects()[0];
      if (!rr || rr.width === 0 || rr.right < 0 || rr.left > vw || rr.bottom < 0 || rr.top > vh) continue;
      const k = Math.round(rr.top / 4); byTop.set(k, (byTop.get(k) || "") + t[i]); }
    for (const s of byTop.values()) { const L = s.trim(); if (L) lines.push({ L, n: [...L].length, fs }); }
  }
  const targets = [];
  for (const el of document.querySelectorAll("button, a, input, select, [role=button], [onclick]")) {
    if (skip(el) || !visible(el)) continue;
    const r = el.getBoundingClientRect();
    targets.push({ w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.left), y: Math.round(r.top), t: (el.textContent || el.getAttribute("aria-label") || el.tagName).trim().slice(0, 14) });
  }
  const anims = [...new Set(document.getAnimations().filter((a) => a.playState === "running" && a.effect?.target && !(devbar && devbar.contains(a.effect.target))).map((a) => a.animationName || "?"))];
  // 잘린 글자 — 말줄임(overflow:hidden)이 걸린 칸에서 글자 폭이 칸 폭보다 큰 것. 주행 화면에서 **말이 잘리면** 그 말은 없는 것이다.
  const clipped = [];
  for (const el of document.querySelectorAll("#root div, #root span")) {
    if (skip(el) || !visible(el) || el.children.length > 0) continue;
    const cs = getComputedStyle(el);
    if ((cs.overflow === "hidden" || cs.textOverflow === "ellipsis") && el.scrollWidth > el.clientWidth + 1) clipped.push(el.textContent.trim().slice(0, 24));
  }
  return { lines, targets, anims, clipped };
})()`;
const WORST = `(() => {
  // 최악의 회전 안내를 **실제 칸에** 넣어 본다 — 가장 긴 거리 · 가장 긴 지시 · 긴 도로명. 칸 폭은 그대로(CSS)다.
  const set = (k, t) => { const e = document.querySelector('[data-turn="' + k + '"]'); if (e) e.textContent = t; return e; };
  const dist = set("dist", "12.50km 앞"), word = set("word", "오른쪽 방향"), road = set("road", "동명로14번길 123-45");
  if (!word) return null;
  const mic = document.querySelector("button[aria-label='음성']").getBoundingClientRect();
  const right = (e) => { const r = document.createRange(); r.selectNodeContents(e); return Math.round(r.getBoundingClientRect().right); };
  const clippedRoad = road.scrollWidth > road.clientWidth + 1;
  return { micLeft: Math.round(mic.left), dist: dist && right(dist), word: right(word), road: road && right(road), roadClipped: clippedRoad,
           wordFits: right(word) <= mic.left - 8, distFits: !dist || right(dist) <= mic.left - 8 };
})()`;

const overlaps = (T) => { let n = 0; for (let i = 0; i < T.length; i++) for (let j = i + 1; j < T.length; j++) { const a = T[i], b = T[j]; if (a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1 && a.y < b.y + b.h - 1 && b.y < a.y + a.h - 1) n++; } return n; };
const row = (name, m) => {
  const over = m.lines.filter((x) => x.n > GLANCE), small = m.lines.filter((x) => x.fs < FONT), t = m.targets.filter((x) => Math.min(x.w, x.h) < TARGET);
  console.log(`${name.padEnd(26)} 줄 ${String(m.lines.length).padStart(3)} | ${GLANCE}자↑ ${String(over.length).padStart(2)} (최장 ${Math.max(0, ...m.lines.map((x) => x.n))}) | ${FONT}px↓ ${String(small.length).padStart(2)}줄 | 터치 ${TARGET}↓ ${t.length}/${m.targets.length} (최소 ${Math.min(999, ...m.targets.map((x) => Math.min(x.w, x.h)))} · 겹침 ${overlaps(m.targets)}) | 도는 것 ${m.anims.join(",") || "—"} | 잘림 ${m.clipped.length}${m.clipped.length ? " [" + m.clipped.join(" / ") + "]" : ""}`);
  return { over, t };
};

const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const pg = await b.newPage({ viewport: { width: 1280, height: 800 } });
await pg.goto(URL);
await pg.waitForSelector("text=안내 시작", { timeout: 60_000 });
await pg.waitForTimeout(2500);
console.log(`뷰포트 1280×800 · 기준 한 줄 ${GLANCE}자 · 글자 ${FONT}px · 터치 ${TARGET}px (정차 쪽은 참고)`);
const seen = new Map();
const grab = async (name) => { const m = await pg.evaluate(MEASURE); const r = row(name, m); r.over.forEach((x) => seen.set(x.L, x)); return m; };
await grab("정차: 경로 카드(참고)");
await pg.click("text=안내 시작");
await pg.waitForTimeout(3500);
await grab("주행: 신호대로");
const worst = await pg.evaluate(WORST);
console.log("최악 회전 안내(12.50km 앞 · 오른쪽 방향 · 긴 도로명):", JSON.stringify(worst));
await pg.locator("button", { hasText: /^병목$/ }).first().click();
await pg.waitForTimeout(1200);
await grab("주행: 병목 패널 열림");
await pg.locator("button", { hasText: /^자세히$/ }).first().click();
await pg.waitForTimeout(800);
await grab("주행: 병목 자세히 열림(참고)");
await pg.locator("button", { hasText: /^접기$/ }).first().click();
await pg.locator("button[aria-label='접기']").first().click();
await pg.waitForTimeout(800);
await grab("주행: 병목 패널 닫힘");
const cur = pg.locator("button", { hasText: /^(시연 .*|신호대로)$/ }).first();
const next = cur.locator("xpath=following-sibling::button[1]");
for (const k of KEYS) { await next.click(); await pg.waitForTimeout(700); await grab(`주행: 상태 ${k}`); }
console.log(`\n${GLANCE}자를 넘은 줄(고유):`);
[...seen.values()].forEach((x) => console.log(`  ${String(x.n).padStart(3)}자 ${x.fs}px  ${x.L}`));
await b.close();

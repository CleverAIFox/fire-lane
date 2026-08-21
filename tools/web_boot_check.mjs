#!/usr/bin/env node
/* tools/web_boot_check.mjs — web/js 부팅 스모크 테스트
   ════════════════════════════════════════════════════════════
   maplibre 를 스텁으로 갈아끼우고 main.js 를 실제로 import 해서
   map.on("load") 까지 돌린다. 문법·그래프 검사가 못 잡는 것을 잡는다.

   ★ 실제로 잡은 것 2건 (2026-08-21, app.js → web/js 분리 중):
     1. layers/signs.js 최상단에 `placeSigns();` 가 딸려 들어왔다.
        원본에서는 map.on("load") 본문 안이라 map 이 이미 있었다.
        모듈 최상단은 import 시점이라 S.map 이 null 이다 → 지도 안 뜸.
     2. icons/{truck,ops119,cctv}.js 가 SIGN_PX 를 참조하는데 그 상수는
        signs.js 에 있었다. 원본에서는 같은 스코프였다 → ReferenceError.

     둘 다 `node --check` 도 import 그래프 검사도 통과한다. 실행해야 나온다.

   ★ 한계 — 이걸로 "지도가 제대로 그려진다"는 보장은 안 된다.
     WebGL 이 없어 렌더링 결과는 못 본다. 확인하는 것은
     "모듈 배선이 성립하고 레이어 호출이 전부 나가는가" 까지다.
     화면은 사람이 봐야 한다:  cd web && python -m http.server 8000

   실행:  node tools/web_boot_check.mjs      (jsdom 필요)
   ════════════════════════════════════════════════════════════ */
import { resolve, dirname } from "node:path";
const ROOT = resolve(dirname(new URL(import.meta.url).pathname), "..");

import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const dom = new JSDOM(readFileSync(ROOT + "/web/index.html", "utf8"),
                      { runScripts: "outside-only", url: "http://localhost:8000/" });
const w = dom.window;

/* config.js 를 실행한다.
   ★ 간접 eval 의 최상위 const 는 그 eval 의 선언적 환경에 들어가고 끝나면
     버려진다(실측: eval("const X=1") 뒤 typeof X === "undefined").
     진짜 <script> 태그와 다르다. 그래서 같은 eval 안에서 밖으로 넘긴다.
   ★ const 가 window 프로퍼티가 되지 않는다는 사실 자체는 vm.Script 로
     따로 실측했다. 여기서 재현할 필요는 없다 — 이 하네스의 목적은
     모듈 배선 확인이다. 어차피 node ESM 은 jsdom 의 전역 어휘 환경을
     못 보므로 그 경로는 여기서 재현 불가능하다. */
w.eval(readFileSync(ROOT + "/web/config.js", "utf8") + "\n; globalThis.__CFG = CONFIG;");

const calls = { addSource: [], addLayer: [], on: [], addImage: [], addControl: 0, loadCbs: [] };
function stubMap(){
  const m = {
    on: (ev, a, b) => { calls.on.push(typeof a === "string" ? `${ev}:${a}` : ev);
                        const cb = typeof a === "function" ? a : b;
                        if (ev === "load") calls.loadCbs.push(cb); },
    addSource: (id) => calls.addSource.push(id),
    addLayer: (spec) => calls.addLayer.push(spec.id),
    addImage: (id) => calls.addImage.push(id),
    hasImage: () => false, getLayer: () => null, getSource: () => null,
    setPaintProperty(){}, setLayoutProperty(){}, setFilter(){}, moveLayer(){},
    setTerrain(){}, addControl: () => calls.addControl++,
    getCanvas: () => ({ clientWidth: 1200, clientHeight: 800, style: {} }),
    getZoom: () => 16, getPitch: () => 45, getBearing: () => -18,
    getCenter: () => ({ lat: 35.15, lng: 126.92, distanceTo: () => 500 }),
    unproject: () => ({ distanceTo: () => 100, lat: 35.15, lng: 126.92 }),
    flyTo(){}, transform: { cameraToCenterDistance: 1200 },
  };
  Object.assign(this, m);
  globalThis.__maps = (globalThis.__maps||[]).concat(this);
  return this;
}
w.maplibregl = { Map: stubMap, NavigationControl: class {}, ScaleControl: class {},
                 Popup: class { setLngLat(){return this;} setHTML(){return this;} addTo(){return this;} } };
w.requestAnimationFrame = () => 0;
Object.defineProperty(w, "performance", { value: { now: () => 0 }, configurable: true });

// data.js 의 fetch 를 실제 web/data 파일로 연결
w.fetch = async (u) => {
  const p = ROOT + "/web/" + u.replace("./", "");
  return { ok: true, status: 200, json: async () => JSON.parse(readFileSync(p, "utf8")) };
};

globalThis.window = w; globalThis.document = w.document;
for (const k of ["maplibregl","fetch","requestAnimationFrame","performance","location","HTMLCanvasElement","Image"])
  globalThis[k] = w[k];
globalThis.innerWidth = 1200;
// CONFIG: 클래식 스크립트 선언적 전역을 모듈 스코프에서 보이게
globalThis.CONFIG = w.__CFG;

// 캔버스 2D 스텁 (아이콘 굽기)
w.HTMLCanvasElement.prototype.getContext = function () {
  const noop = new Proxy(() => noop, { get: () => noop });
  return new Proxy({}, { get: (t, k) => k === "getImageData"
      ? () => ({ data: new Uint8ClampedArray(4), width: 192, height: 192 }) : noop });
};

await import(ROOT + "/web/js/main.js");
/* map.on("load") 콜백을 실제로 실행시킨다 — 여기가 원본 880줄의 자리다. */
if (!calls.loadCbs.length) { console.error("★ load 핸들러가 등록되지 않았다"); process.exit(1); }
for (const cb of calls.loadCbs) await cb();

console.log("addSource :", calls.addSource.length, calls.addSource.join(" "));
console.log("addLayer  :", calls.addLayer.length);
console.log("addImage  :", calls.addImage.join(" "));
console.log("on        :", calls.on.join(" "));
console.log("addControl:", calls.addControl);

/* ── 기대치 대조 ──────────────────────────────────────────── */
const MUST_LAYERS = ["seg-l","bld-3d","bnd-l","mask-l","mask-soft-l",
                     "hyd-pulse","hyd-pulse2","mk-3d","poi-dot","poi-label",
                     "q-pin-l","mbnd-l","mroute-l","mview-f","mview-halo","mview-l"];
const missing = MUST_LAYERS.filter(l => !calls.addLayer.includes(l));
if (missing.length) {
  console.error("\n★ 레이어 누락:", missing.join(" "));
  process.exit(1);
}
if (!calls.loadCbs.length || calls.addSource.length < 12) {
  console.error("\n★ 초기화가 끝까지 안 갔다");
  process.exit(1);
}
console.log("\nOK  부팅 · 필수 레이어 " + MUST_LAYERS.length + "개 전부 생성");

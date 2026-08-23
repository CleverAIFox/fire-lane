/* Fire-Lane · 데이터 접근 단일 지점
   ════════════════════════════════════════════════════════════
   ★ 이 파일 하나가 정적 → API 전환 비용을 0 으로 만든다.

   지금은      fetch("./data/segments.geojson")
   나중에는    fetch(`${API}/segments`)

   갈아끼울 자리가 아래 `SOURCE` 한 곳뿐이다. 레이어 모듈은 전부
   `getSegments()` 처럼 이름으로만 부르므로, 그것들을 열어볼 필요가 없다.

   PLAN §2-3 "serving 스키마 하나만 보고 GeoJSON 을 받는다" 를 프론트에서
   강제하는 장치다. 종전 app.js 는 `fetch("./data/...")` 가 map.on("load")
   본문 여기저기에 흩어져 있어, API 로 바꾸려면 880줄을 훑어야 했다.

   ★ 캐시를 두는 이유.
     원본은 읽은 GeoJSON 을 `DATA.poiRaw` · `DATA.bldRaw` · `DATA.segRaw`
     같은 별칭에 다시 담아 재사용했다. 별칭이 늘어나면 "정본이 무엇인가"가
     흐려진다. 여기서 한 번 읽고 캐시하면 별칭이 필요 없다.

   ★ 파일명이 키와 다른 것들(hyd → hydrants.geojson)은 여기서만 안다.
     종전에는 `FILES` 손딕셔너리가 app.js 안에 있었다.
   ════════════════════════════════════════════════════════════ */
import { CONFIG } from "./config-access.js";

/* ── 캐시 무효화 ─────────────────────────────────────────────
   ★ 2026-08-22. segments.geojson 은 파이프라인을 돌릴 때마다 바뀐다.
     브라우저가 옛 것을 물고 있으면 **판정 색이 틀린 지도**가 뜬다.
     관제사에게는 그것이 최악의 실패다.

   ★ 순환을 어디서 끊는가.
     스탬프는 view.json 의 build 에 있는데, view.json 자체도 데이터라
     캐시된다. 그래서 view.json **만** 매 로드 고유한 URL 로 받는다
     (?t=Date.now()). 1KB 짜리라 비용이 없고, 그 뒤 모든 데이터는
     내용 해시 스탬프를 달아 캐시가 정상 동작한다.

   ★ 스탬프는 판정 데이터의 내용 해시다(publish_web.py). 타임스탬프가
     아니므로 데이터가 그대로면 URL 도 그대로고 캐시가 그대로 산다. */
let _build = "";

/* ── 갈아끼우는 곳 ───────────────────────────────────────────
   API 로 넘어갈 때 이 함수 하나만 고친다. 호출부는 안 건드린다. */
const SOURCE = name =>
  `./data/${name}.geojson${_build ? `?v=${_build}` : ""}`;

/* 키 → 실제 파일명. 이름이 같으면 적지 않는다. */
const FILENAME = {
  hyd  : "hydrants",
  sta  : "stations",
  light: "streetlights",
};

const _cache = new Map();

async function _get(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`데이터 로드 실패 ${r.status} — ${url}`);
  return r.json();
}

/* GeoJSON 하나. 같은 이름을 두 번 부르면 네트워크를 다시 타지 않는다. */
export function load(key) {
  if (!_cache.has(key)) _cache.set(key, _get(SOURCE(FILENAME[key] || key)));
  return _cache.get(key);
}

/* 여러 개를 동시에. `{seg, bld} = await loadAll(["seg","bld"])` 형태. */
export async function loadAll(keys) {
  const vals = await Promise.all(keys.map(load));
  return Object.fromEntries(keys.map((k, i) => [k, vals[i]]));
}

/* ── 스코프 ──────────────────────────────────────────────────
   ★ 좌표를 코드에 하드코딩하지 않는다. web/data/view.json 이 정본이고
     그것은 publish_web.py 산출물이다. 동명동 bbox 는 약 1.04 x 1.04 km.
   ★ view.json 은 .geojson 이 아니라 SOURCE() 를 안 탄다.
   ★ 여기만 매 로드 고유 URL 이다. 캐시 사슬을 끊는 자리이므로
     ?t= 를 지우지 마라 — 지우면 스탬프 자체가 낡는다. */
export const loadView = () => {
  if (!_cache.has("__view")) {
    _cache.set("__view", _get(`./data/view.json?t=${Date.now()}`)
      .then(v => { _build = v.build || ""; return v; }));
  }
  return _cache.get("__view");
};

/* ── 마커 데이터 목록 ────────────────────────────────────────
   ★ CONFIG.markers 의 spec.data 에서 뽑는다. 여기에 손나열을 두면
     마커를 추가할 때 config 와 이 파일 두 곳을 고쳐야 한다.
     (원본 app.js 의 MKF 와 같은 계산이다) */
export const markerKeys = () =>
  [...new Set(CONFIG.markers.map(m => m.data).filter(Boolean))];

/* 화면이 처음 뜨는 데 필요한 전부. main.js 가 이것 하나만 부른다. */
/* ★ 2026-08-23 lightpoles 추가. 발행만 되고 아무도 안 읽던 레이어다.
   `test_web_data_has_no_unintended_orphan` 의 화이트리스트에서도 뺀다. */
export const BASE_KEYS = ["segments", "buildings", "boundary", "poi",
                          "lightpoles"];

export async function loadInitial() {
  // ★ view.json 을 **먼저** 받는다. 그래야 _build 가 채워지고 이후
  //   데이터 URL 에 스탬프가 붙는다. 병렬로 돌리면 경합이 생겨
  //   어떤 파일은 스탬프 없이 나가고 어떤 파일은 붙는다.
  const view = await loadView();
  const keys = [...BASE_KEYS, ...markerKeys()];
  const [data, mask, maskSoft] = await Promise.all([
    loadAll(keys),
    load("mask"),
    load("mask_soft"),
  ]);
  return { ...data, view, mask, maskSoft };
}

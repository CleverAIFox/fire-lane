/**
 * components/layers.ts — 지도 레이어 선언. **스타일만 담는다.**
 *
 * ── 왜 뺐나 ─────────────────────────────────────────────────────
 * `NaviMap.tsx` 가 지도 생성 · 카메라 루프 · 데이터 갱신을 이미 지고 있다.
 * 레이어는 **무엇을 어떻게 그리나** 하나만 답하므로 따로 산다.
 *
 * ── ★ 2026-09-21 · 주간 테마 · 경로 어휘 (지혜님 와이어프레임 09-21) ──
 * 와이어프레임이 **밝은 낮 도시**다. 배경·건물·도로를 `tokens.ts::MAP` 으로
 * 옮겼다. 그리고 경로를 판정 4색으로 칠하던 것을 **파랑 한 줄 + 겹칠 곳만
 * 겹쳐 그리기**로 바꿨다 —
 *
 *     clear      파랑 (기본)
 *     needs_cv   빨강·노랑 줄무늬 — 병목 (04)
 *     unknown    보라 — CCTV 로 검증되지 않는 골목 (07)
 *     신고 구간   진한 빨강 — 통행 불가 (16)
 *
 *   판정의 **뜻**은 그대로이고 **색 어휘**만 지혜님 것이다. `blocked` 는
 *   경로에 안 올라온다(A* 가 막는다).
 *
 * ── ★ 판정색을 여기서 만들지 않는다 ────────────────────────────
 * 배경 도로의 판정 음영(레이어 단추로 켠다)은 여전히 `style` 에서 **파생**한다.
 * `config.js` 에 새 색을 늘리지 않는다 — 정본은 하나로 남는다.
 *
 * ★ 마커는 전부 `web/data` 의 발행물을 그대로 읽는다. 좌표를 코드에
 *   박지 않는다 — 안전센터 3곳도 `stations.geojson` 이 든다.
 */
import type { StyleSpecification, LayerSpecification } from "maplibre-gl";
import type { VerdictStyle } from "../domain/types";
import { C, MAP } from "../ui/tokens";

const FONT = ["Open Sans Regular"];
export const GLYPHS = "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf";

/** 어느 줌부터 켜는가. 다 켜면 골목에서 글자가 겹쳐 아무것도 못 읽는다. */
const Z = { road: 16, bldg: 16, hydrant: 16.5, cctv: 16.5, poi: 17.5 } as const;

/**
 * 판정색을 배경 쪽으로 당겨 **배경선용 음영**을 만든다.
 * ★ 새 색을 정의하는 것이 아니라 정본 색에서 파생하는 것이다.
 */
function shade(css: string, keep = 0.55): string {
  const m = css.match(/(\d+)\D+(\d+)\D+(\d+)/);
  if (!m) return css;
  const rgb = [Number(m[1]), Number(m[2]), Number(m[3])];
  const out = rgb.map((v, i) => Math.round(v * keep + MAP.bg[i] * (1 - keep)));
  return `rgb(${out[0]},${out[1]},${out[2]})`;
}

export function sources(dataUrl: string): StyleSpecification["sources"] {
  return {
    buildings: { type: "geojson", data: dataUrl + "buildings.geojson" },
    segments: { type: "geojson", data: dataUrl + "segments.geojson" },
    poi: { type: "geojson", data: dataUrl + "poi.geojson" },
    stations: { type: "geojson", data: dataUrl + "stations.geojson" },
    cctv: { type: "geojson", data: dataUrl + "cctv.geojson" },
    hydrants: { type: "geojson", data: dataUrl + "hydrants.geojson" },
  };
}

/**
 * 배경 — 도로와 건물.
 * @param style `navi_graph.json.style`. 판정 4색의 정본이 여기로 흘러온다.
 */
export function baseLayers(style: Record<string, VerdictStyle>): LayerSpecification[] {
  const tint = (k: string) => shade(style[k]?.color ?? "rgb(120,128,140)");
  const w = (a: number, b: number) =>
    ["interpolate", ["linear"], ["zoom"], 15, a, 19, b] as unknown as number;

  return [
    { id: "bg", type: "background",
      paint: { "background-color": `rgb(${MAP.bg.join(",")})` } },

    // 도로 — 테두리 + 흰 면. 와이어프레임의 낮 도로다.
    { id: "seg-case", type: "line", source: "segments",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": w(3.5, 16), "line-color": MAP.roadCase } },
    { id: "seg-road", type: "line", source: "segments",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": w(2.2, 13), "line-color": MAP.road } },

    // 판정 음영 — 레이어 단추로 켠다. 경로가 없어도 어디가 좁은 골목인지 보인다.
    { id: "seg-tint", type: "line", source: "segments",
      layout: { "line-cap": "round", visibility: "none" },
      paint: {
        "line-width": w(2, 9),
        "line-color": ["match", ["get", "verdict"],
          "clear", tint("clear"), "needs_cv", tint("needs_cv"),
          "blocked", tint("blocked"), tint("unknown")],
        "line-opacity": .85,
      } },

    // 건물 — z(지반고) 위에 h(높이)만큼.
    // ★ base 를 z 로 두지 않으면 경사지에서 뜨거나 묻힌다. 기복 86.6m.
    { id: "bldg", type: "fill-extrusion", source: "buildings",
      paint: {
        "fill-extrusion-color": ["interpolate", ["linear"], ["get", "flo"],
          1, MAP.bldgLow, 12, MAP.bldgHigh],
        "fill-extrusion-height": ["+", ["get", "z"], ["get", "h"]],
        "fill-extrusion-base": ["get", "z"],
        "fill-extrusion-opacity": .96,
        "fill-extrusion-vertical-gradient": true,
      } },
  ];
}

const RW = (a: number, b: number) =>
  ["interpolate", ["linear"], ["zoom"], 15, a, 19, b] as unknown as number;

/**
 * 비교용 둘째 경로(02). 주 경로 **밑에** 깐다.
 * ★ 와이어프레임 02 가 빠른 경로를 주황으로 그렸다.
 */
export function altRouteLayers(): LayerSpecification[] {
  return [
    { id: "alt-case", type: "line", source: "route-alt",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": RW(9, 24), "line-color": "#ffffff", "line-opacity": .95 } },
    { id: "alt-line", type: "line", source: "route-alt",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": RW(5, 15), "line-color": C.routeAlt } },
  ];
}

/**
 * 주 경로. 파랑 한 줄 위에 **겹칠 곳만** 겹친다.
 *
 * ★ `look` 이 `pending` 이면 점선 하늘색 — 새 경로가 서기 전(06 · 12 · 13 · 14).
 *   옛 경로를 실선으로 두면 그 길로 가라는 말이 된다.
 */
export function routeLayers(): LayerSpecification[] {
  const isLook = (v: string) => ["==", ["get", "look"], v] as unknown as boolean;
  return [
    { id: "route-case", type: "line", source: "route",
      filter: ["!", isLook("pending")] as never,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": RW(11, 30), "line-color": "#ffffff",
               "line-opacity": ["case", isLook("faded"), .45, .95] as never } },
    { id: "route-line", type: "line", source: "route",
      filter: ["!", isLook("pending")] as never,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": RW(7, 21), "line-color": C.route,
               "line-opacity": ["case", isLook("faded"), .45, 1] as never } },

    // 07 — CCTV 로 검증되지 않는 골목
    { id: "route-unverified", type: "line", source: "route",
      filter: ["all", ["==", ["get", "verdict"], "unknown"], ["!", isLook("pending")]] as never,
      layout: { "line-cap": "butt", "line-join": "round" },
      paint: { "line-width": RW(7, 21), "line-color": C.routeUnverified } },
    { id: "route-unverified-dash", type: "line", source: "route",
      filter: ["all", ["==", ["get", "verdict"], "unknown"], ["!", isLook("pending")]] as never,
      layout: { "line-cap": "butt" },
      paint: { "line-width": RW(1.5, 4), "line-color": "#ffffff",
               "line-dasharray": [2, 3] } },

    // 04 — 병목. 노랑 바탕에 빨강 줄무늬
    { id: "route-bottleneck", type: "line", source: "route",
      filter: ["all", ["==", ["get", "verdict"], "needs_cv"], ["!", isLook("pending")]] as never,
      layout: { "line-cap": "butt" },
      paint: { "line-width": RW(7, 21), "line-color": C.toneYellow } },
    { id: "route-bottleneck-stripe", type: "line", source: "route",
      filter: ["all", ["==", ["get", "verdict"], "needs_cv"], ["!", isLook("pending")]] as never,
      layout: { "line-cap": "butt" },
      paint: { "line-width": RW(7, 21), "line-color": C.routeBottleneck,
               "line-dasharray": [0.6, 0.6] } },

    // 16 — 현장에서 통행 불가로 신고한 구간
    { id: "route-blocked", type: "line", source: "blocked",
      layout: { "line-cap": "round" },
      paint: { "line-width": RW(7, 21), "line-color": "#991b1b",
               "line-dasharray": [1, 0.8] } },

    // 06 · 12 · 13 · 14 — 경로가 서지 않았다
    { id: "route-pending", type: "line", source: "route",
      filter: isLook("pending") as never,
      layout: { "line-cap": "round" },
      paint: { "line-width": RW(4, 10), "line-color": C.routePending,
               "line-dasharray": [0.1, 1.8] } },

    // 진행 방향 갈매기표. 아이콘은 NaviMap 이 캔버스로 굽는다(글꼴 없이 돈다).
    { id: "route-chevron", type: "symbol", source: "route",
      filter: ["!", isLook("pending")] as never,
      layout: {
        "symbol-placement": "line", "symbol-spacing": 70,
        "icon-image": "chev", "icon-size": ["interpolate", ["linear"], ["zoom"], 15, .35, 19, .8] as never,
        "icon-rotation-alignment": "map", "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      } },

    // 05 — 최종 접근 지점에서 사건 위치까지 (차량이 못 들어가는 구간)
    { id: "final-leg", type: "line", source: "final-leg",
      layout: { "line-cap": "round" },
      paint: { "line-width": RW(3, 7), "line-color": C.incident,
               "line-dasharray": [1.2, 1.2] } },
  ];
}

/**
 * 지형지물 마커 · 라벨.
 *
 * ★ 소화전과 CCTV 는 **출동 판단에 직접 쓰인다.** 소화전은 도착 후 급수
 *   지점이고, CCTV 는 그 구간의 판정이 영상으로 검증될 수 있는지를
 *   말한다(`unknown` 354 는 전부 CCTV 25m 밖이다).
 */
export function markerLayers(): LayerSpecification[] {
  const halo = { "text-halo-color": MAP.labelHalo, "text-halo-width": 1.8 };
  return [
    { id: "hydrant", type: "circle", source: "hydrants", minzoom: Z.hydrant,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 16, 3, 19, 6],
        "circle-color": "#ef4444",
        "circle-stroke-width": 1.5, "circle-stroke-color": "#ffffff",
      } },
    { id: "cctv", type: "circle", source: "cctv", minzoom: Z.cctv,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 16, 4, 19, 9],
        "circle-color": "#facc15",
        "circle-stroke-width": 2, "circle-stroke-color": "#111827",
      } },
    { id: "lbl-road", type: "symbol", source: "segments", minzoom: Z.road,
      layout: {
        "symbol-placement": "line", "text-field": ["get", "road_name"],
        "text-font": FONT, "text-size": 11, "text-max-angle": 40,
        "symbol-spacing": 260, "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#475569", ...halo } },
    { id: "lbl-bldg", type: "symbol", source: "buildings", minzoom: Z.bldg,
      filter: ["has", "BULD_NM"],
      layout: {
        "text-field": ["get", "BULD_NM"], "text-font": FONT, "text-size": 12,
        "text-allow-overlap": false, "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": MAP.label, ...halo } },
    { id: "lbl-poi", type: "symbol", source: "poi", minzoom: Z.poi,
      layout: {
        "text-field": ["get", "name"], "text-font": FONT, "text-size": 10,
        "text-offset": [0, .7], "text-anchor": "top",
        "text-allow-overlap": false, "text-optional": true,
        "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#64748b", ...halo } },
  ];
}

/**
 * 안전센터 3곳. **출동 기점이라 항상 보인다.**
 * ★ `kind` 로 안전센터(center)와 소방서(station)를 가른다.
 */
export function stationLayers(): LayerSpecification[] {
  return [
    { id: "station-dot", type: "circle", source: "stations",
      paint: {
        "circle-radius": ["case", ["==", ["get", "kind"], "center"], 7, 5],
        "circle-color": ["case", ["==", ["get", "kind"], "center"], C.station, "#64748b"],
        "circle-stroke-width": 2.5, "circle-stroke-color": "#ffffff",
      } },
    { id: "lbl-station", type: "symbol", source: "stations",
      layout: {
        // 발행 필드명이 한글 한 칸이다. 정본은 stations.geojson 이므로 이름을 안 바꾼다.
        "text-field": ["get", "소방서 및 안전센터명"],
        "text-font": FONT, "text-size": 12, "text-offset": [0, 1.3],
        "text-anchor": "top", "text-allow-overlap": true,
        "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#1e3a8a", "text-halo-color": "#fff", "text-halo-width": 2 } },
  ];
}

/** 캔버스로 굽는 갈매기표. 글꼴 서버 없이 돈다(시연장 와이파이를 믿지 않는다). */
export function chevronImage(): ImageData {
  const n = 48;
  const cv = document.createElement("canvas");
  cv.width = n; cv.height = n;
  const g = cv.getContext("2d")!;
  g.strokeStyle = "#ffffff"; g.lineWidth = 8; g.lineCap = "round"; g.lineJoin = "round";
  g.beginPath(); g.moveTo(14, 12); g.lineTo(32, 24); g.lineTo(14, 36); g.stroke();
  return g.getImageData(0, 0, n, n);
}

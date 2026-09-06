/**
 * components/layers.ts — 지도 레이어 선언. **스타일만 담는다.**
 *
 * ── 왜 뺐나 ─────────────────────────────────────────────────────
 * `NaviMap.tsx` 가 지도 생성 · 카메라 루프 · 데이터 갱신을 이미 지고 있다.
 * 레이어는 **무엇을 어떻게 그리나** 하나만 답하므로 따로 산다.
 *
 * ── ★ 판정색을 여기서 만들지 않는다 ────────────────────────────
 * 2026-09-06. 배경 도로선의 어두운 색(`#2f5f47` 등)을 **여기에 박았다.**
 * 판정색은 `navi_graph.json.style` 로 상속받아 놓고 정작 배경선은 사본을
 * 만든 것이다 — 상속 관계가 한 군데 샜다.
 *
 * 이제 `style` 을 받아 **런타임에 어둡게 만든다.** `config.js` 에
 * `darkColor` 를 새로 추가하지 않는 이유는, 정본에 필드를 늘리면 지도와
 * 내비 양쪽이 그것을 채워야 하고 한쪽만 채우면 다시 갈리기 때문이다.
 * 색을 **파생**하면 정본은 하나로 남는다.
 *
 * ★ 마커는 전부 `web/data` 의 발행물을 그대로 읽는다. 좌표를 코드에
 *   박지 않는다 — 안전센터 3곳도 `stations.geojson` 이 든다.
 */
import type { StyleSpecification, LayerSpecification } from "maplibre-gl";
import type { VerdictStyle } from "../domain/types";

const FONT = ["Open Sans Regular"];
export const GLYPHS = "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf";

/** 어느 줌부터 켜는가. 다 켜면 골목에서 글자가 겹쳐 아무것도 못 읽는다. */
const Z = { road: 16, bldg: 16, hydrant: 16.5, cctv: 16.5, poi: 17.5 } as const;

/** 지도 배경. 판정색을 이 위로 섞어 어둡게 만든다. */
const MAP_BG: [number, number, number] = [11, 14, 20];

/**
 * 판정색을 배경 쪽으로 당겨 **배경선용 음영**을 만든다.
 *
 * ★ 새 색을 정의하는 것이 아니라 정본 색에서 파생하는 것이다.
 *   `config.js` 가 바뀌면 이것도 자동으로 따라온다.
 */
function shade(css: string, keep = 0.32): string {
  const m = css.match(/(\d+)\D+(\d+)\D+(\d+)/);
  if (!m) return css;
  const rgb = [Number(m[1]), Number(m[2]), Number(m[3])];
  const out = rgb.map((v, i) => Math.round(v * keep + MAP_BG[i] * (1 - keep)));
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
 * 배경 — 건물과 도로.
 *
 * @param style `navi_graph.json.style`. 판정 4색의 정본이 여기로 흘러온다.
 */
export function baseLayers(
  style: Record<string, VerdictStyle>,
): LayerSpecification[] {
  // 판정색에서 파생한 음영. 없으면 회색으로 떨어진다.
  const dark = (k: string) => shade(style[k]?.color ?? "rgb(90,98,114)");

  return [
    { id: "bg", type: "background",
      paint: { "background-color": `rgb(${MAP_BG.join(",")})` } },

    // 도로 — 전 구간을 판정 음영으로. 경로가 없어도 어디가 좁은 골목인지
    // 보인다. 이것이 이 앱의 배경 지도다.
    { id: "seg-base", type: "line", source: "segments",
      layout: { "line-cap": "round" },
      paint: {
        "line-width": ["interpolate", ["linear"], ["zoom"], 15, 2, 19, 8],
        "line-color": ["match", ["get", "verdict"],
          "clear", dark("clear"),
          "needs_cv", dark("needs_cv"),
          "blocked", dark("blocked"),
          dark("unknown")],
        "line-opacity": .9,
      } },

    // 건물 — z(지반고) 위에 h(높이)만큼.
    // ★ base 를 z 로 두지 않으면 경사지에서 뜨거나 묻힌다. 기복 86.6m.
    { id: "bldg", type: "fill-extrusion", source: "buildings",
      paint: {
        "fill-extrusion-color": ["interpolate", ["linear"], ["get", "flo"],
          1, "#1a202b", 5, "#232b39", 15, "#2d3646"],
        "fill-extrusion-height": ["+", ["get", "z"], ["get", "h"]],
        "fill-extrusion-base": ["get", "z"],
        "fill-extrusion-opacity": .95,
        "fill-extrusion-vertical-gradient": true,
      } },
  ];
}

/** 경로. 판정별로 분절해 그리는 것이 이 앱의 존재 이유다. */
export function routeLayers(): LayerSpecification[] {
  return [
    { id: "route-halo", type: "line", source: "route",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-width": ["interpolate", ["linear"], ["zoom"], 15, 12, 19, 30],
        "line-color": ["get", "color"], "line-opacity": .2, "line-blur": 7,
      } },
    { id: "route-line", type: "line", source: "route",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-width": ["interpolate", ["linear"], ["zoom"], 15, 6, 19, 16],
        "line-color": ["get", "color"], "line-opacity": .95,
      } },
  ];
}

/**
 * 지형지물 마커.
 *
 * ★ 소화전과 CCTV 는 **출동 판단에 직접 쓰인다.** 소화전은 도착 후 급수
 *   지점이고, CCTV 는 그 구간의 판정이 영상으로 검증될 수 있는지를
 *   말한다(`unknown` 354 는 전부 CCTV 25m 밖이다).
 */
export function markerLayers(): LayerSpecification[] {
  return [
    { id: "hydrant", type: "circle", source: "hydrants", minzoom: Z.hydrant,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 16, 3, 19, 6],
        "circle-color": "#4ad1ff",
        "circle-stroke-width": 1.5, "circle-stroke-color": "#0b0e14",
        "circle-opacity": .9,
      } },
    { id: "cctv", type: "circle", source: "cctv", minzoom: Z.cctv,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 16, 3.5, 19, 7],
        "circle-color": "#ffd54a",
        "circle-stroke-width": 1.5, "circle-stroke-color": "#0b0e14",
        "circle-opacity": .9,
      } },

    { id: "lbl-road", type: "symbol", source: "segments", minzoom: Z.road,
      layout: {
        "symbol-placement": "line", "text-field": ["get", "road_name"],
        "text-font": FONT, "text-size": 11, "text-max-angle": 40,
        "symbol-spacing": 240, "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#9fb0c8", "text-halo-color": "#0b0e14",
               "text-halo-width": 1.6 } },

    { id: "lbl-bldg", type: "symbol", source: "buildings", minzoom: Z.bldg,
      filter: ["has", "BULD_NM"],
      layout: {
        "text-field": ["get", "BULD_NM"], "text-font": FONT, "text-size": 12,
        "text-allow-overlap": false, "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#dfe7f2", "text-halo-color": "#0b0e14",
               "text-halo-width": 1.8 } },

    // 상가는 17.5 부터. 더 일찍 켜면 골목에서 글자가 겹쳐 못 읽는다.
    { id: "lbl-poi", type: "symbol", source: "poi", minzoom: Z.poi,
      layout: {
        "text-field": ["get", "name"], "text-font": FONT, "text-size": 10,
        "text-offset": [0, .7], "text-anchor": "top",
        "text-allow-overlap": false, "text-optional": true,
        "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#8b9ab0", "text-halo-color": "#0b0e14",
               "text-halo-width": 1.4 } },
  ];
}

/**
 * 안전센터 3곳. **출동 기점이라 항상 보인다.**
 *
 * ★ `kind` 로 안전센터(center)와 소방서(station)를 가른다. 출동은
 *   소방서가 아니라 안전센터에서 나간다(`seg/params.py::STATIONS`).
 */
export function stationLayers(): LayerSpecification[] {
  return [
    { id: "station-glow", type: "circle", source: "stations",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 14, 12, 19, 30],
        "circle-color": "#ff4d3d", "circle-opacity": .18, "circle-blur": .7,
      } },
    { id: "station-dot", type: "circle", source: "stations",
      paint: {
        "circle-radius": ["case", ["==", ["get", "kind"], "center"], 8, 6],
        "circle-color": ["case", ["==", ["get", "kind"], "center"],
          "#ff4d3d", "#c2410c"],
        "circle-stroke-width": 2.5, "circle-stroke-color": "#ffffff",
      } },
    { id: "lbl-station", type: "symbol", source: "stations",
      layout: {
        // 발행 필드명이 한글 한 칸이다. 정본은 stations.geojson 이므로
        // 여기서 이름을 바꾸지 않는다.
        "text-field": ["get", "소방서 및 안전센터명"],
        "text-font": FONT, "text-size": 12, "text-offset": [0, 1.3],
        "text-anchor": "top", "text-allow-overlap": true,
        "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#ffd6d1", "text-halo-color": "#0b0e14",
               "text-halo-width": 2 } },
  ];
}

/** 목적지 · 출발지 핀. 앱이 GeoJSON 을 채운다. */
export function pinLayers(): LayerSpecification[] {
  return [
    { id: "pin-halo", type: "circle", source: "pins",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 14, 10, 19, 24],
        "circle-color": ["get", "color"], "circle-opacity": .22, "circle-blur": .6,
      } },
    { id: "pin-dot", type: "circle", source: "pins",
      paint: {
        "circle-radius": 9, "circle-color": ["get", "color"],
        "circle-stroke-width": 3, "circle-stroke-color": "#ffffff",
      } },
    { id: "pin-label", type: "symbol", source: "pins",
      layout: {
        "text-field": ["get", "label"], "text-font": FONT, "text-size": 12,
        "text-offset": [0, 1.4], "text-anchor": "top",
        "text-allow-overlap": true, "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#ffffff", "text-halo-color": "#0b0e14",
               "text-halo-width": 2 } },
  ];
}

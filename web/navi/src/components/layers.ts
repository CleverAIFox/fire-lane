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
 * ── ★ 2026-09-22 · 바탕을 **면**으로 (DECISIONS §213-4) ─────────────
 * 도로를 판정 구간 중심선으로만 그리니 흰 선 위에 흰 건물이라 대비가 없었다.
 * 수치지형도 도로경계 면 + 실폭도로 면(`road_area.geojson`)을 짙은 아스팔트로,
 * 보도(`sidewalk.geojson`)를 한 단 밝게 깐다. 면이 없는 최협소 골목은 구간 선을
 * 같은 아스팔트색으로 그어 메운다. 폭 7m 이상 구간에만 중앙 점선을 둔다 —
 * 와이어프레임의 차선이고, **판정이 아니라 장식**이다(폭 판정은 여전히 선이 든다).
 *
 * 건물은 벽(중간 회색) 위에 0.6m 지붕 판(밝은 회백)을 한 겹 더 올린다.
 * fill-extrusion 은 윗면 색을 따로 못 주므로 얇은 판을 얹는 것이 유일한 방법이다.
 *
 * ── ★ 2026-09-22 · 와이어프레임 충실도 (DECISIONS §214-2) ─────────────
 *   · CCTV · 소화전을 6px 점 → **원형 아이콘 배지**(캔버스로 굽는다 — 글꼴 서버 없이)
 *   · 건물 · 상호 이름을 글자+후광 → **흰 알약**. 적게 — 층수 순으로 겹치면 버린다
 *   · 경로를 굵게, 갈매기표를 크게
 *   · 병목(판정 보류)을 노랑·빨강 → **정본 주황 · 흰 줄무늬**. 판정 보류는 CV 를 돌리면
 *     초록이나 빨강으로 **바뀌는** 유일한 색이고(사용자 정의), 빨강은 「CV 없이 통행 불가」
 *     다. 경로 위에 빨강이 섞이면 「못 지나간다」 로 읽힌다 — 빨강은 신고 구간 전용이다
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
    road_area: { type: "geojson", data: dataUrl + "road_area.geojson" },
    sidewalk: { type: "geojson", data: dataUrl + "sidewalk.geojson" },
    segments: { type: "geojson", data: dataUrl + "segments.geojson" },
    poi: { type: "geojson", data: dataUrl + "poi.geojson" },
    stations: { type: "geojson", data: dataUrl + "stations.geojson" },
    cctv: { type: "geojson", data: dataUrl + "cctv.geojson" },
    hydrants: { type: "geojson", data: dataUrl + "hydrants.geojson" },
    // ★ §216-3. 과속방지턱 · 단속카메라 · 보호구역 시설 — 받아 두고 안 쓰던 데이터
    context: { type: "geojson", data: dataUrl + "context.geojson" },
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

    // 보도 → 도로면 → (면이 없는 골목) 구간 선 → 중앙 점선
    { id: "sidewalk", type: "fill", source: "sidewalk",
      paint: { "fill-color": MAP.sidewalk } },
    { id: "road-area", type: "fill", source: "road_area",
      paint: { "fill-color": MAP.asphalt, "fill-outline-color": MAP.asphaltEdge } },
    { id: "seg-road", type: "line", source: "segments",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": w(2.2, 12), "line-color": MAP.asphalt } },
    { id: "seg-marking", type: "line", source: "segments", minzoom: 16,
      filter: [">=", ["coalesce", ["get", "width_min_m"], 0], 7] as never,
      layout: { "line-cap": "butt" },
      paint: { "line-width": w(0.6, 2), "line-color": MAP.marking,
               "line-opacity": .85, "line-dasharray": [4, 4] } },

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

    // 건물 — 땅(0)에서 h(높이)만큼.
    // ★ 2026-09-22 (DECISIONS §216-2) 사용자 보고 「줌을 당기니 건물이 공중에 뜬다」.
    //   종전에는 base 를 z(해발 지반고 5.5~130m · 중앙 16.6m)로 뒀다. 그것은 **지형을 켠**
    //   옛 지도(web/js · setTerrain)의 규칙이고, 내비 · 관제는 지형을 안 켠다 — 평평한 땅
    //   위에 건물이 16m 떠 있었다. 지형 없이 z 를 쓰지 않는다.
    // ★ 지붕 판(`bldg-roof`)을 뺐다. 같은 12,736동을 **한 번 더** 압출하는 레이어였고,
    //   소프트웨어 렌더에서 프레임 시간의 큰 몫이었다(§216-2 계측). 윗면 명도는
    //   vertical-gradient 가 낸다.
    { id: "bldg", type: "fill-extrusion", source: "buildings", minzoom: 14.5,
      paint: {
        "fill-extrusion-color": ["interpolate", ["linear"], ["get", "flo"],
          1, MAP.bldgLow, 12, MAP.bldgHigh],
        "fill-extrusion-height": ["get", "h"],
        "fill-extrusion-base": 0,
        "fill-extrusion-opacity": 1,
        "fill-extrusion-vertical-gradient": true,
      } },
    // 평면 건물 — 관제(위에서 본 평면)용. 압출이 필요 없는 화면에서 압출 대신 켠다
    { id: "bldg-flat", type: "fill", source: "buildings",
      layout: { visibility: "none" },
      paint: { "fill-color": MAP.roof, "fill-outline-color": MAP.bldgHigh } },
  ];
}

const RW = (a: number, b: number) =>
  ["interpolate", ["linear"], ["zoom"], 15, a * 1.25, 19, b * 1.3] as unknown as number;

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
export function routeLayers(style: Record<string, VerdictStyle> = {}): LayerSpecification[] {
  // 판정 보류의 정본 주황. 정본이 없으면(시험 · 데이터 전) 토큰의 경고색
  const amber = style.needs_cv?.color ?? C.warn;
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

    // 04 — 병목(판정 보류). 정본 주황 바탕에 흰 줄무늬
    { id: "route-bottleneck", type: "line", source: "route",
      filter: ["all", ["==", ["get", "verdict"], "needs_cv"], ["!", isLook("pending")]] as never,
      layout: { "line-cap": "butt" },
      paint: { "line-width": RW(7, 21), "line-color": amber } },
    { id: "route-bottleneck-stripe", type: "line", source: "route",
      filter: ["all", ["==", ["get", "verdict"], "needs_cv"], ["!", isLook("pending")]] as never,
      layout: { "line-cap": "butt" },
      paint: { "line-width": RW(7, 21), "line-color": "#ffffff", "line-opacity": .85,
               "line-dasharray": [0.5, 0.7] } },

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
        "symbol-placement": "line", "symbol-spacing": 90,
        "icon-image": "chev", "icon-size": ["interpolate", ["linear"], ["zoom"], 15, .45, 19, 1.15] as never,
        "icon-rotation-alignment": "map", "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      } },

    // 05 — 최종 접근 지점에서 사건 위치까지 (차량이 못 들어가는 구간)
    { id: "final-leg", type: "line", source: "final-leg",
      layout: { "line-cap": "round" },
      paint: { "line-width": RW(4, 9), "line-color": C.incident,
               "line-dasharray": [1.1, 1.1] } },
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
  return [
    { id: "hydrant", type: "symbol", source: "hydrants", minzoom: Z.hydrant,
      layout: {
        "icon-image": "ic-hyd", "icon-allow-overlap": true, "icon-pitch-alignment": "viewport",
        "icon-size": ["interpolate", ["linear"], ["zoom"], 16.5, .42, 19, .8] as never,
      } },
    { id: "cctv", type: "symbol", source: "cctv", minzoom: Z.cctv,
      layout: {
        "icon-image": "ic-cctv", "icon-allow-overlap": true, "icon-pitch-alignment": "viewport",
        "icon-size": ["interpolate", ["linear"], ["zoom"], 16.5, .42, 19, .8] as never,
      } },
    // ★ §216-3 주변 사정. 판정과 무관하다 — 작게, 가까이서만
    { id: "ctx", type: "symbol", source: "context", minzoom: 16,
      layout: {
        "icon-image": ["match", ["get", "kind"],
          "speedbump", "ic-bump", "speedcam", "ic-cam", "ic-zone"] as never,
        "icon-allow-overlap": false, "icon-pitch-alignment": "viewport",
        "icon-size": ["interpolate", ["linear"], ["zoom"], 16, .34, 19, .62] as never,
      } },
    { id: "lbl-road", type: "symbol", source: "segments", minzoom: Z.road,
      layout: {
        "symbol-placement": "line", "text-field": ["get", "road_name"],
        "text-font": FONT, "text-size": 11, "text-max-angle": 40,
        "symbol-spacing": 260, "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": MAP.roadLabel, "text-halo-color": MAP.roadLabelHalo,
               "text-halo-width": 1.6 } },
    // 이름 알약 — 와이어프레임의 흰 배지. **적게.** 층수 높은 것부터, 겹치면 버린다
    { id: "lbl-bldg", type: "symbol", source: "buildings", minzoom: Z.bldg + 0.6,
      // ★ 2026-09-22 검수 — 이름 칸이 **빈 문자열**인 건물이 `has` 를 통과해 글자 없는 흰
      //   알약이 화면을 덮었다. 길이로 거른다. 4층 미만은 뺀다(와이어프레임도 몇 개뿐이다)
      filter: ["all", [">", ["length", ["coalesce", ["get", "BULD_NM"], ""]], 1],
               [">=", ["coalesce", ["get", "flo"], 0], 4]] as never,
      layout: {
        "text-field": ["get", "BULD_NM"], "text-font": FONT, "text-size": 12.5,
        "icon-image": "pill", "icon-text-fit": "both", "icon-text-fit-padding": [4, 9, 4, 9],
        "symbol-sort-key": ["-", 0, ["coalesce", ["get", "flo"], 0]] as never,
        "text-allow-overlap": false, "icon-allow-overlap": false,
        "text-pitch-alignment": "viewport", "icon-pitch-alignment": "viewport",
        "text-padding": 28,
      },
      paint: { "text-color": MAP.label } },
    { id: "lbl-poi", type: "symbol", source: "poi", minzoom: Z.poi + 0.8,
      filter: [">", ["length", ["coalesce", ["get", "name"], ""]], 1] as never,
      layout: {
        "text-field": ["get", "name"], "text-font": FONT, "text-size": 11,
        "icon-image": "pill", "icon-text-fit": "both", "icon-text-fit-padding": [3, 7, 3, 7],
        "text-offset": [0, .9], "text-anchor": "top",
        "text-allow-overlap": false, "icon-allow-overlap": false, "text-optional": false,
        "text-pitch-alignment": "viewport", "icon-pitch-alignment": "viewport",
        "text-padding": 24,
      },
      paint: { "text-color": "#334155" } },
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
  const n = 64;
  const cv = document.createElement("canvas");
  cv.width = n; cv.height = n;
  const g = cv.getContext("2d")!;
  g.strokeStyle = "#ffffff"; g.lineWidth = 10; g.lineCap = "round"; g.lineJoin = "round";
  g.beginPath(); g.moveTo(18, 14); g.lineTo(42, 32); g.lineTo(18, 50); g.stroke();
  return g.getImageData(0, 0, n, n);
}

/**
 * 지도 아이콘을 캔버스로 굽는다. **글꼴 · 스프라이트 서버 없이** 돈다(시연장 와이파이를 믿지 않는다).
 * 2배 해상도로 그리고 `pixelRatio: 2` 로 넣는다.
 */
function canvas(n: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const cv = document.createElement("canvas");
  cv.width = n; cv.height = n;
  return [cv, cv.getContext("2d")!];
}

/** 와이어프레임의 노란 CCTV 배지 */
export function cctvIcon(): ImageData {
  const n = 96; const [, g] = canvas(n);
  g.beginPath(); g.arc(48, 48, 42, 0, Math.PI * 2);
  g.fillStyle = "#facc15"; g.fill(); g.lineWidth = 6; g.strokeStyle = "#111827"; g.stroke();
  g.fillStyle = "#111827";
  g.save(); g.translate(48, 46); g.rotate(-0.35);
  g.fillRect(-24, -10, 36, 20);                       // 몸통
  g.beginPath(); g.moveTo(12, -6); g.lineTo(26, -12); g.lineTo(26, 12); g.lineTo(12, 6); g.fill();
  g.restore();
  g.fillRect(28, 56, 6, 16); g.fillRect(20, 68, 22, 6); // 기둥
  g.beginPath(); g.arc(34, 46, 4, 0, Math.PI * 2); g.fillStyle = "#facc15"; g.fill();
  return g.getImageData(0, 0, n, n);
}

/** 과속방지턱 — 노란 마름모 안 둔덕(도로교통 안전표지의 모양) */
export function bumpIcon(): ImageData {
  const n = 96; const [, g] = canvas(n);
  g.beginPath(); g.moveTo(48, 6); g.lineTo(90, 48); g.lineTo(48, 90); g.lineTo(6, 48); g.closePath();
  g.fillStyle = "#facc15"; g.fill(); g.lineWidth = 6; g.strokeStyle = "#111827"; g.stroke();
  g.beginPath(); g.moveTo(24, 60); g.quadraticCurveTo(48, 26, 72, 60); g.closePath();
  g.fillStyle = "#111827"; g.fill();
  return g.getImageData(0, 0, n, n);
}

/** 단속카메라 — 파란 원 안 카메라 */
export function camIcon(): ImageData {
  const n = 96; const [, g] = canvas(n);
  g.beginPath(); g.arc(48, 48, 42, 0, Math.PI * 2);
  g.fillStyle = "#2563eb"; g.fill(); g.lineWidth = 6; g.strokeStyle = "#ffffff"; g.stroke();
  g.fillStyle = "#ffffff"; g.fillRect(24, 36, 40, 26);
  g.beginPath(); g.moveTo(64, 42); g.lineTo(76, 34); g.lineTo(76, 64); g.lineTo(64, 56); g.fill();
  g.beginPath(); g.arc(40, 49, 7, 0, Math.PI * 2); g.fillStyle = "#2563eb"; g.fill();
  return g.getImageData(0, 0, n, n);
}

/** 보호구역 시설 — 흰 바탕 붉은 테 원(규제표지 모양) 안 사람 */
export function zoneIcon(): ImageData {
  const n = 96; const [, g] = canvas(n);
  g.beginPath(); g.arc(48, 48, 42, 0, Math.PI * 2);
  g.fillStyle = "#ffffff"; g.fill(); g.lineWidth = 9; g.strokeStyle = "#dc2626"; g.stroke();
  g.fillStyle = "#111827";
  g.beginPath(); g.arc(48, 30, 8, 0, Math.PI * 2); g.fill();
  g.fillRect(42, 40, 12, 22); g.fillRect(38, 62, 8, 14); g.fillRect(50, 62, 8, 14);
  return g.getImageData(0, 0, n, n);
}

/** 와이어프레임의 붉은 소화전 배지 */
export function hydrantIcon(): ImageData {
  const n = 96; const [, g] = canvas(n);
  g.beginPath(); g.arc(48, 48, 42, 0, Math.PI * 2);
  g.fillStyle = "#ef2d2d"; g.fill(); g.lineWidth = 6; g.strokeStyle = "#ffffff"; g.stroke();
  g.fillStyle = "#ffffff";
  g.beginPath(); g.arc(48, 34, 11, Math.PI, 0); g.fill();   // 머리
  g.fillRect(37, 33, 22, 30);                               // 몸통
  g.fillRect(27, 42, 42, 9);                                // 양쪽 토출구
  g.fillRect(33, 63, 30, 7);                                // 받침
  g.beginPath(); g.arc(48, 47, 4.5, 0, Math.PI * 2); g.fillStyle = "#ef2d2d"; g.fill();
  return g.getImageData(0, 0, n, n);
}

/** 이름 알약 — 늘어나는 흰 둥근 사각형(9-slice). `addImage(…, pillOptions)` 로 넣는다 */
export function pillImage(): ImageData {
  const w = 64, h = 44, r = 20;
  const cv = document.createElement("canvas");
  cv.width = w; cv.height = h;
  const g = cv.getContext("2d")!;
  g.shadowColor = "rgba(15,23,42,.28)"; g.shadowBlur = 5; g.shadowOffsetY = 2;
  g.beginPath();
  g.moveTo(r + 2, 3); g.lineTo(w - r - 2, 3); g.arc(w - r - 2, h / 2, r - 1, -Math.PI / 2, Math.PI / 2);
  g.lineTo(r + 2, h - 3); g.arc(r + 2, h / 2, r - 1, Math.PI / 2, -Math.PI / 2); g.closePath();
  g.fillStyle = "#ffffff"; g.fill();
  return g.getImageData(0, 0, w, h);
}
export const pillOptions = {
  pixelRatio: 2, stretchX: [[22, 42]] as [number, number][], stretchY: [[20, 24]] as [number, number][],
  content: [14, 8, 50, 36] as [number, number, number, number],
};

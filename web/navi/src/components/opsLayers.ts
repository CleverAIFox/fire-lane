/**
 * opsLayers.ts — **관제 전용 지도 층.**  (DECISIONS §311 · §312)
 *
 * ★ 2026-09-29 에 `layers.ts` 에서 갈라 나왔다. 그 파일이 길이 상한(600)을 치면서
 *   나눌 자리를 찾았는데, 가장 자연스러운 금이 **화면 경계**였다 — §311 이
 *   「두 화면의 일이 다르다」고 적었고, 그 말이 코드에도 서야 했다.
 *
 * ★ 여기 있는 층은 **내비가 한 개도 안 쓴다.** 판정 4색 전 도로 · 도달 불가 ·
 *   119 이력 열지도 · CCTV 유효범위 · 미리보기 경로 — 전부 「전체를 훑는」 화면의
 *   것이다. 그래서 `tools/uicheck.py` 의 공유 층 계산에도 한쪽에만 든다.
 *
 * IN    ui/tokens(색) · domain/types
 * OUT   MapLibre 층 명세
 * 밖    **바탕 층은 안 든다** — `layers.ts` 의 `baseLayers` 가 두 화면 공용이다.
 *       **무엇을 보일지 안 고른다** — `OpsMap.tsx` 가 켜고 끈다.
 */
import type { LayerSpecification } from "maplibre-gl";

/**
 * 지형지물 마커 · 라벨.
 *
 * ★ 소화전과 CCTV 는 **출동 판단에 직접 쓰인다.** 소화전은 도착 후 급수
 *   지점이고, CCTV 는 그 구간의 판정이 영상으로 검증될 수 있는지를
 *   말한다(`unknown` 354 는 전부 CCTV 25m 밖이다).
 */
/**
 * 관제 판정선 — 굵기 = 최소 유효폭 비례(2~12m 로 자른다 · 광장 · 교차로가 얼룩이 되지 않게).
 *
 * ★ 2026-09-22 (DECISIONS §217-3) — 종전 `["+", W, 2]` 는 **무효 식**이었다. `["zoom"]` 은
 *   `interpolate` · `step` 의 **맨 바깥**에만 올 수 있는데, 줌 보간 W 를 `+` 로 감쌌다.
 *   MapLibre 는 그 레이어를 **조용히 안 올린다**(콘솔 경고 하나) — 테두리 · 도달 불가 점선 ·
 *   선택 강조 셋이 v0.33 부터 한 번도 안 그려졌다. 타입 검사도 빌드도 초록이었다.
 *   지금은 더하기를 보간 **안쪽**(멈춤점마다)에 넣고, `test/style.test.ts` 가 모든 레이어를
 *   style-spec 검증기에 통과시킨다.
 */
/** 판정 4색 식. 기본 모드의 구간 색이고, 모드를 되돌릴 때도 이것을 다시 건다 */
export function opsVerdictColor(col: (k: string) => string): unknown {
  return ["match", ["get", "verdict"],
    "clear", col("clear"), "needs_cv", col("needs_cv"),
    "blocked", col("blocked"), col("unknown")];
}

export function opsSegLayers(col: (k: string) => string): LayerSpecification[] {
  const wm = ["min", 12, ["max", 2, ["coalesce", ["get", "width_min_m"], 3]]];
  const W = (add = 0) => ["interpolate", ["linear"], ["zoom"],
    14, ["+", add, ["*", 0.25, wm]], 18, ["+", add, ["*", 1.5, wm]]] as never;
  return [
    { id: "ops-verdict-case", type: "line", source: "segments",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": W(2), "line-color": "#1f2937", "line-opacity": .55 } },
    { id: "ops-verdict", type: "line", source: "segments",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-width": W(),
        "line-color": opsVerdictColor(col) as never,
      } },
    { id: "ops-unreach", type: "line", source: "segments",
      layout: { "line-cap": "butt", visibility: "none" },
      paint: { "line-width": W(1), "line-color": "#111827",
               "line-opacity": .75, "line-dasharray": [0.6, 0.6] } },
    { id: "ops-selected", type: "line", source: "segments",
      filter: ["==", ["get", "seg_uid"], ""] as never,
      paint: { "line-width": W(7), "line-color": "#1d4ed8", "line-opacity": .55 } },
  ];
}

/**
 * 관제 **여유폭 모드**의 구간 색 식.  (DECISIONS §219 → §220)
 *
 * 고른 차의 요구폭을 빼서 네 단으로 칠한다 — `domain/clearance.ts` 의 뺄셈을 지도
 * 표현식으로 옮긴 것이다. 같은 문턱(0 · `TUNING.tightMarginM` · `CLEARANCE_WIDE_M`)을
 * 인자로 받으므로 카드의 수와 지도의 색이 갈릴 수 없다.
 *
 * ★ 2026-09-23. `width_min_m` 은 **null 로 발행되는 칸이 있다**(1,281 중 2). `["get"]` 은
 *   null 을 그대로 내고 그것을 `["-"]` 에 넣으면 그 레이어가 통째로 무효가 된다(§217-3 이
 *   겪은 자리). `coalesce` 로 있을 수 없는 수(-999)를 세우고 **그 칸을 먼저 걸러낸다.**
 *
 * @param needM 요구폭(m) — `requiredWidth(spec)`
 * @param col   구간 키 → 색. `ui/clearanceMeaning.ts::CLEARANCE_SCALE` 이 든다
 */
export function opsClearanceColor(
  needM: number, tightM: number, wideM: number, col: (k: string) => string,
): unknown {
  const c = ["-", ["coalesce", ["get", "width_min_m"], -999], needM];
  return ["case",
    ["<", c, -900], col("unknown"),
    ["<", c, 0], col("neg"),
    ["<", c, tightM], col("tight"),
    ["<", c, wideM], col("mid"),
    col("wide")];
}

/** 같은 식의 **구간 키** 판. 여유폭 모드의 거르기가 이것을 쓴다 */
export function opsClearanceBand(needM: number, tightM: number, wideM: number): unknown {
  return opsClearanceColor(needM, tightM, wideM, (k) => k);
}

/** 관제 지형 음영 (§217-2) — 위에서 본 평면에서도 등성이 · 골이 보인다 */
export function hillshadeLayer(): LayerSpecification {
  return { id: "hillshade", type: "hillshade", source: "dem",
    paint: { "hillshade-shadow-color": "#000000", "hillshade-highlight-color": "#3b4d6b",
             "hillshade-accent-color": "#0b1220", "hillshade-exaggeration": 0.45 } };
}

/** 관제 출동 이력 (§216-3) — 밀도 + 실제 도착 시간 색 */
export function opsHistoryLayers(): LayerSpecification[] {
  return [
    { id: "hist-heat", type: "heatmap", source: "history", maxzoom: 17,
      layout: { visibility: "none" },
      paint: {
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 13, 14, 16, 34] as never,
        "heatmap-intensity": 0.8, "heatmap-opacity": 0.55,
        "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"],
          0, "rgba(0,0,0,0)", 0.3, "#7c3aed", 0.6, "#f97316", 1, "#fde047"] as never,
      } },
    { id: "hist-pt", type: "circle", source: "history", minzoom: 14.5,
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 14.5, 3, 18, 7] as never,
        // 실제 출동 → 현장 도착. 5분 · 8분 경계는 **표시용 가정값**이다(기준 문헌 없음)
        "circle-color": ["case", ["!", ["has", "resp_s"]], "#64748b",
          ["<=", ["get", "resp_s"], 300], "#22c55e",
          ["<=", ["get", "resp_s"], 480], "#f59e0b", "#ef4444"] as never,
        "circle-stroke-color": "#0b1220", "circle-stroke-width": 1.2,
      } },
  ];
}

/** 관제 덧그림 — CCTV 유효 반경(줌 14 · 20 에서의 픽셀 반지름) · 출동 미리보기 · 출동 대 경로 */
export function opsOverlayLayers(r14: number, r20: number): LayerSpecification[] {
  return [
    { id: "cctv-cov", type: "circle", source: "cctv",
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["exponential", 2], ["zoom"],
          14, r14, 20, r20] as never,
        "circle-color": "#facc15", "circle-opacity": .14,
        "circle-stroke-color": "#ca8a04", "circle-stroke-width": 1, "circle-stroke-opacity": .6,
        "circle-pitch-alignment": "map",
      } },
    { id: "preview-walk", type: "line", source: "preview-walk",
      paint: { "line-width": 4, "line-color": "#ef2d2d", "line-dasharray": [1.2, 1.2] } },
    { id: "preview-case", type: "line", source: "preview",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": 11, "line-color": "#ffffff" } },
    { id: "preview", type: "line", source: "preview",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": 6, "line-color": "#2563eb" } },
    { id: "unit-routes", type: "line", source: "unit-routes",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": 5, "line-color": "#7c3aed", "line-opacity": .9,
               "line-dasharray": [2, 1] } },
  ];
}

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
 * ★ 2026-10-09 (DECISIONS §444 · PLAN #148). **지점 핀이 여기 산다.** 처음에는
 *   `layers.ts` 에 뒀는데 그 파일이 **진입 청크**에 들어가 무게가 127 → 128KB 로
 *   늘었다(`naviweight --build` 가 울었다). 핀은 관제만 쓰므로 자리가 여기가
 *   맞고, 옮기니 무게가 그대로다 — **옳은 자리가 싼 자리였다.**
 *
 * 밖    **바탕 층은 안 든다** — `layers.ts` 의 `baseLayers` 가 두 화면 공용이다.
 *       **무엇을 보일지 안 고른다** — `OpsMap.tsx` 가 켜고 끈다.
 */
import type { LayerSpecification, StyleSpecification } from "maplibre-gl";
import type { Landmark } from "../domain/types";

// ★ 지도 글자. `layers.ts` 의 `FONT` 와 **같은 값이어야 한다** —
//   저장소에서 뽑는 글꼴 이름이고 정본은 `web/navi/scripts/glyphs.mjs` 다.
const FONT = ["LiberationSans"];

/**
 * 지형지물 마커 · 라벨.
 *
 * ★ 소화전과 CCTV 는 **출동 판단에 직접 쓰인다.** 소화전은 도착 후 급수
 *   지점이고, CCTV 는 그 구간의 판정이 영상으로 검증될 수 있는지를
 *   말한다(`unknown` 354 는 전부 CCTV 19m 밖이다).
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

/**
 * 둘째 채널 — 판정마다 **다른 선 패턴.**  (DECISIONS §448 · PLAN #145)
 *
 * ★ 색 하나로 넷을 가르고 있었다. 실측에서 `blocked` ↔ `unknown` 의 **정상시야
 *   휘도비가 1.00** 이다(§383) — 색각 이상이 아니라 **밝기만 보는 상황**(저조도
 *   벽 화면 · 사진 인쇄 · 흑백 복사)에서 그 둘이 같은 선이 된다.
 *
 * ★ 패턴은 **파내는 방식**이다. MapLibre 의 `line-dasharray` 는 자료 기반 식을
 *   못 받으므로(색처럼 `match` 로 못 쓴다) 판정마다 레이어를 하나씩 더 깔고
 *   **바탕색으로** 점선을 그어 색 선에 틈을 낸다. 색은 한 글자도 안 바뀐다 —
 *   `web/config.js` 가 계약 파일이라 색을 건드리면 계약 배치가 된다(#145).
 *
 * ★ `clear` 는 **실선**이다. 기준이 하나 있어야 나머지가 「무늬가 있다」로 읽힌다.
 */
export const VERDICT_DASH: Record<string, [number, number]> = {
  needs_cv: [2.4, 1.0],   // 성긴 파선
  blocked: [0.6, 0.9],    // 촘촘한 점선
  unknown: [5.0, 1.4],    // 긴 파선
};

/**
 * ── ★ 2026-11-04 (PLAN #62 · DECISIONS §614) 발행 범위 밖 구간을 **흐리게** ──────
 * `scope_tier` 가 `reference` 인 구간(527)은 발행 범위(target · corridor · listed)가
 * 아니다. **끄지 않는다** — 거기 막힌 길(blocked) 118 개가 있다. 흐리게 보이고,
 * 끄는 길(`showRef=false` → 0)은 남긴다.
 *
 * ★ 레이어를 쪼개지 않는다. 같은 층의 `line-opacity` 만 tier 의 함수로 둔다 —
 *   쪼개면 클릭 · 호버 · 경로 하이라이트가 두 벌이 된다.
 * ★ 판정색은 건드리지 않는다(`config.js` 가 계약). 불투명도만 곱한다.
 * ★ 숨겨도(0) 선은 **눌린다** — 불투명도는 질의를 막지 않는다.
 * ★ 곱셈이다(절대값이 아니다) — 층마다 기존 불투명도(.55 · .9 · 1)가 달라서,
 *   절대값을 박으면 테두리가 색선보다 짙어지는 등 층 사이 위계가 깨진다.
 */
export const REF_FACTOR = { general: 0.3, blocked: 0.7 } as const;

/** 층별 기존 불투명도. 발행 범위 안(target · corridor · listed)은 이 값 그대로다. */
export const OPS_SEG_OPACITY = {
  "ops-verdict-case": 0.55, "ops-verdict": 1,
  "ops-verdict-dash-needs_cv": 0.9, "ops-verdict-dash-blocked": 0.9, "ops-verdict-dash-unknown": 0.9,
  "ops-unreach": 0.75,
  "seg-tint": 0.85,
} as const;

/** 한 구간의 불투명도. 표현식(`refOpacity`)과 같은 표에서 나온다 — 시험이 이쪽을 든다. */
export function refOpacityValue(show: boolean, tier: string | null | undefined,
                                verdict: string | null | undefined, base: number): number {
  if (tier !== "reference") return base;
  if (!show) return 0;
  return base * (verdict === "blocked" ? REF_FACTOR.blocked : REF_FACTOR.general);
}

/** `line-opacity` 식. `scope_tier` 가 없는 구간(옛 발행물)은 기존값을 받는다. */
export function refOpacity(show: boolean, base: number): unknown {
  return ["case", ["==", ["get", "scope_tier"], "reference"],
    show
      ? ["match", ["get", "verdict"], "blocked", base * REF_FACTOR.blocked, base * REF_FACTOR.general]
      : 0,
    base];
}

/**
 * 숨김(`show=false`)일 때만 reference 를 **질의에서 뺀다**. 흐림(`true`)은 보이니까 눌려야 맞다.
 * 불투명도 0 은 `queryRenderedFeatures` 를 막지 않아서 보이지 않는 선이 눌렸다.
 * 반환 `null` = 거르지 않는다. 다른 거르기와는 `andFilter` 로 합친다.
 */
export function refFilter(show: boolean): unknown[] | null {
  return show ? null : ["!=", ["get", "scope_tier"], "reference"];
}

/** 거르기 식을 `all` 로 합친다. 없는 것(null)은 건너뛴다. 다 없으면 null. */
export function andFilter(...fs: (unknown[] | null)[]): unknown[] | null {
  const xs = fs.filter((f): f is unknown[] => f !== null);
  return xs.length === 0 ? null : xs.length === 1 ? xs[0] : ["all", ...xs];
}

/**
 * `?ref=0` 이면 reference 를 숨기고 `?ref=1` 이면 흐리게 보인다. **그 밖(없음 · 잘못된 값)은
 * 기본 = 보임.** `?terrain=0` 과 같은 꼴이되, 모르는 값을 「끔」으로 읽지 않는다 —
 * 막힌 길을 오타 하나로 지우지 않으려는 쪽이다.
 * ★ 읽기만 한다(초기값). `?terrain` 도 그렇다 — 토글이 주소를 다시 쓰지 않는다.
 */
export function parseShowRef(search: string): boolean {
  const v = new URLSearchParams(search).get("ref");
  return v === "0" ? false : true;
}

export function opsSegLayers(col: (k: string) => string, showRef = true): LayerSpecification[] {
  const op = (id: keyof typeof OPS_SEG_OPACITY) => refOpacity(showRef, OPS_SEG_OPACITY[id]) as never;
  const wm = ["min", 12, ["max", 2, ["coalesce", ["get", "width_min_m"], 3]]];
  const W = (add = 0) => ["interpolate", ["linear"], ["zoom"],
    14, ["+", add, ["*", 0.25, wm]], 18, ["+", add, ["*", 1.5, wm]]] as never;
  return [
    { id: "ops-verdict-case", type: "line", source: "segments",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-width": W(2), "line-color": "#1f2937", "line-opacity": op("ops-verdict-case") } },
    { id: "ops-verdict", type: "line", source: "segments",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-width": W(),
        "line-color": opsVerdictColor(col) as never,
        "line-opacity": op("ops-verdict"),
      } },
    // ★ 둘째 채널. 색 선 **위에** 바탕색 점선을 그어 틈을 낸다 — 색이 안 보여도
    //   무늬로 갈린다. `clear` 는 실선이라 여기 없다(기준).
    ...Object.entries(VERDICT_DASH).map(([k, dash]) => ({
      id: `ops-verdict-dash-${k}`, type: "line", source: "segments",
      filter: ["==", ["get", "verdict"], k] as never,
      layout: { "line-cap": "butt" },
      paint: { "line-width": W(), "line-color": "#0b1220",
               "line-opacity": op(`ops-verdict-dash-${k}` as keyof typeof OPS_SEG_OPACITY),
               "line-dasharray": dash },
    } as LayerSpecification)),
    { id: "ops-unreach", type: "line", source: "segments",
      layout: { "line-cap": "butt", visibility: "none" },
      paint: { "line-width": W(1), "line-color": "#111827",
               "line-opacity": op("ops-unreach"), "line-dasharray": [0.6, 0.6] } },
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

/**
 * 지점 핀의 소스. **좌표는 인자로만 온다** — 이 파일에 점을 적지 않는다.
 *
 * ★ 2026-10-09 (DECISIONS §444 · PLAN #148). 옛 발행물에는 `landmarks` 가 없다.
 *   그때는 **빈 모음**을 낸다 — 레이어는 서고 핀만 없다. 소스를 아예 안 만들면
 *   `addLayer` 가 없는 소스를 가리켜 지도 전체가 죽는다.
 */
export function landmarkSource(lms?: Landmark[]): StyleSpecification["sources"][string] {
  return {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: (lms ?? []).map((l) => ({
        type: "Feature" as const,
        properties: { name: l.name, note: l.note ?? "" },
        geometry: { type: "Point" as const, coordinates: [l.lng, l.lat] },
      })),
    },
  };
}

/**
 * 지점 핀. **안전센터와 같은 층**에 선다(§412-3).
 *
 * ★ 판정 4색을 쓰지 않는다. 이 점은 판정 대상이 아니라 **위치**이고, 4색 중
 *   하나를 쓰면 「이 지점이 통행 가능하다」로 읽힌다. 그래서 테두리만 있는
 *   흰 고리다 — 색 채널을 안 먹고 휘도로만 선다(교안 p.25 Note 3).
 * ★ 경로에 안 붙는 점이라 **지도에서도 길과 안 닿게** 생겼다 — 고리이고
 *   채워진 점이 아니다. 안전센터(채운 점)와 꼴로 갈린다.
 */
export function landmarkLayers(): LayerSpecification[] {
  return [
    { id: "landmark-ring", type: "circle", source: "landmarks",
      paint: {
        "circle-radius": 6.5,
        "circle-color": "rgba(0,0,0,0)",
        "circle-stroke-width": 2.5,
        "circle-stroke-color": "#e2e8f0",
      } },
    { id: "lbl-landmark", type: "symbol", source: "landmarks",
      layout: {
        "text-field": ["get", "name"],
        "text-font": FONT, "text-size": 11, "text-offset": [0, 1.2],
        "text-anchor": "top", "text-allow-overlap": false, "text-padding": 4,
        "text-pitch-alignment": "viewport",
      },
      paint: { "text-color": "#e2e8f0", "text-halo-color": "#0b1220", "text-halo-width": 1.6 } },
  ];
}

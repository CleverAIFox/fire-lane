/**
 * components/landuse.ts — 토지이용 바탕 면(소스 · 층 · 얹는 법). **진입 청크 밖에 산다.**  (PLAN 행 235)
 *
 * ── 왜 따로 사나 ────────────────────────────────────────────────
 * `layers.ts` 는 `NaviMap` 이 정적으로 받으므로 **통째로 진입 청크**에 실린다. 토지이용 면은 첫 화면에 안 필요한
 * 바탕 칠이다 — 층 명세(약 620B)와 두 소스(`landuse.geojson` 245KB · `daeji.geojson` 333KB)를 첫 화면이 받을 까닭이 없다.
 * 그래서 내비는 `map.on('load')` 뒤에 이 모듈을 **동적 import** 해 `attachLanduse` 로 얹고(도로명 `roadLabels` 와 같은 길),
 * 관제는 제 청크(`OpsMap`)에서 정적으로 받아 첫 스타일에 넣는다(색만 어둡게 바꾼다 — DECISIONS §775).
 *
 * ★ 순서 규칙은 하나다 — **`bg` 바로 뒤.** 길 · 보도 · 건물 · 판정 색이 전부 이 면 위다(`tools/themecheck.py` 의
 *   `stack_faults` 가 문다 · DECISIONS §778 C). `withLanduse`(목록에 끼우기)와 `attachLanduse`(뜬 지도에 얹기)가 같은 규칙을 쓴다.
 * ★ 켜고 끄는 것은 이 파일이 아니다 — `NaviMap.tsx` · `OpsMap.tsx` 의 `LAND_ON`(지금 둘 다 꺼짐 · DECISIONS §778).
 */
import type { LayerSpecification, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { MAP } from "../ui/tokens";

/** 면이 끼는 자리의 기준 층 — 이 층 **바로 뒤**. */
const AFTER = "bg";

/**
 * 토지이용 두 소스. 칠하는 면일 뿐 판정이 아니다.
 *   landuse  공원 · 녹지 · 광장 · 공공공지 · 지목별 면(도시계획시설 `vworld_uq153` 등 · `publish_basemap` 이 낸다) — 갈래는 속성 `cls`
 *   daeji    연속지적도 **대지**를 합친 면(바탕 맨 아래 · 크기가 커 따로 낸다 · DECISIONS §768)
 */
export function landuseSources(dataUrl: string): StyleSpecification["sources"] {
  return {
    landuse: { type: "geojson", data: dataUrl + "landuse.geojson" },
    daeji: { type: "geojson", data: dataUrl + "daeji.geojson" },
  };
}

/**
 * 토지이용 면(PLAN 행 144(닫힘)) — 공원 · 녹지 · 광장 · 공공공지. 내비가 이 값으로 깔고, 관제는 같은 층 명세를 **어두운 값으로 바꿔** 깐다(`OpsMap.tsx` 의 `opsLand` ·
 * id `ops-` · DECISIONS §775 — 그 전에는 관제에 없었다. 공유 층 래칫 12 는 같은 id 만 센다). 바탕(`bg`) 바로 위, 보도 · 도로면 아래에 들어간다 — `withLanduse`.
 */
export function landuseLayers(): LayerSpecification[] {
  return [
    // ★ 맨 아래 — 대지(마당 · 주차장 · 공터)를 합친 면. 눈에 안 띄는 바탕이다(DECISIONS §768).
    { id: "daeji", type: "fill", source: "daeji", paint: { "fill-color": MAP.landDaeji } },
    // 도시계획시설(공원 · 광장 · 학교 · 청사 …)과 지적도 지목별로 합친 면. **판정 색 · 아이콘 · 길 · 건물이 이 층 위다**(`withLanduse` 가 `bg` 바로 뒤에 낀다).
    { id: "landuse", type: "fill", source: "landuse", filter: ["==", ["geometry-type"], "Polygon"] as never,
      paint: { "fill-color": ["match", ["get", "cls"],
        ["green", "jm_green"], MAP.landGreen, ["inst", "jm_inst"], MAP.landInst,
        "jm_forest", MAP.landForest, "jm_farm", MAP.landFarm, "jm_water", MAP.landWater, "jm_paved", MAP.landPaved,
        MAP.landPlaza] as never } },
    // 대학(UQV35)과 틀의 10% 넘는 면은 **칠하지 않고 경계선만**(캠퍼스 안에 길이 있다).
    { id: "landuse-campus", type: "line", source: "landuse", filter: ["==", ["geometry-type"], "LineString"] as never,
      paint: { "line-color": MAP.landCampus, "line-width": 1.2, "line-opacity": 0.8 } },
  ];
}

/** 바탕 층 목록의 `bg` 바로 뒤에 토지이용 면을 끼운다 — 길 · 건물 아래다. */
export function withLanduse(base: LayerSpecification[]): LayerSpecification[] {
  const i = base.findIndex((l) => l.id === "bg");
  return [...base.slice(0, i + 1), ...landuseLayers(), ...base.slice(i + 1)];
}

/**
 * **뜬 지도**에 토지이용 면을 얹는다 — 소스 둘을 세우고 층을 `bg` 바로 뒤(= 그다음 층 앞)에 차례로 넣는다.
 * ★ 두 번 불러도 한 번만 얹는다(층이 이미 있으면 건너뛴다) — `addLayer` 는 같은 id 에 던지고, 던지면 그 뒤 배선이 죽는다.
 * ★ `bg` 가 맨 위(뒤 층이 없다)면 `before` 가 없어 맨 위에 얹힌다 — 그때도 `bg` 바로 뒤다.
 */
export function attachLanduse(m: Pick<MapLibreMap, "getLayersOrder" | "getSource" | "addSource" | "getLayer" | "addLayer">, dataUrl: string): void {
  const order = m.getLayersOrder();
  const before = order[order.indexOf(AFTER) + 1];
  for (const [id, s] of Object.entries(landuseSources(dataUrl))) if (!m.getSource(id)) m.addSource(id, s);
  for (const L of landuseLayers()) if (!m.getLayer(L.id)) m.addLayer(L, before);
}

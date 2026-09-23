/**
 * domain/egobox.ts — 자차를 **실측 크기 상자**로 놓는다. 순수 함수만 담는다.
 *
 * ── 왜 생겼나 ────────────────────────────────────────────────────
 * ★ 2026-09-24 (DECISIONS §232). 자차 표시가 DOM 마커(SVG)였다. DOM 마커는
 *   **화면 픽셀**로 그려지므로 줌이 바뀌면 차와 길의 비율이 바뀐다 —
 *   줌 아웃에서는 차가 골목을 통째로 덮고, 줌 인에서는 점이 된다.
 *   **「이 차가 이 골목에 들어가나」를 눈으로 가늠할 수 없다.** 그것이 이
 *   화면의 존재 이유인데.
 *
 *   `fill-extrusion` 으로 놓으면 좌표가 **미터**다. 줌·피치와 무관하게
 *   실제 비율이 유지되고, 높이도 실제 전고가 된다.
 *
 * ── 제원이 없으면 상자를 안 놓는다 ───────────────────────────────
 * ★ `fleet.json` 의 열 편성 중 전장·전고가 있는 것은 **셋**뿐이다
 *   (`pump-js` · `pump-di` 8.0×3.2 · `chem` 9.0×3.4). 없는 차에 기본값을
 *   주면 **없는 숫자를 그림으로 주장하는 것**이다. 그 경우 `null` 을 내고
 *   화면은 종전 납작 마커로 남는다 — `canTurn` · `offtracking` 이
 *   미검증 값으로 안 막는 것과 같은 규율(DECISIONS §81 · §86-4).
 *
 * ★ **전폭은 판정 폭이 아니다.** 상자는 `width_m`(실제 전폭 2.5)로 그린다.
 *   판정에 쓰는 `requiredWidth` 는 전폭 + 여유 3.0 이고, 그 여유는 사람이
 *   내릴 공간이지 차체가 아니다. 상자를 3.0 으로 그리면 화면이 차를
 *   실제보다 넓게 주장한다.
 */

import type { VehicleSpec } from "./types";

/** 지구 반지름(m). 좌표 변환은 국소 평면 근사로 충분하다 — 차 한 대 크기다. */
const R = 6378137;

export interface Box {
  /** 시계방향 네 꼭짓점 + 첫 점(닫힘). `[lon, lat]` */
  ring: [number, number][];
  /** 전고(m). `fill-extrusion-height` 로 간다 */
  heightM: number;
}

/**
 * 자차 상자. 제원이 모자라면 `null`.
 *
 * @param lon 현재 경도
 * @param lat 현재 위도
 * @param bearingDeg 진행 방향(도 · 북 0 · 시계방향)
 */
export function egoBox(spec: VehicleSpec | null | undefined,
                       lon: number, lat: number, bearingDeg: number): Box | null {
  if (!spec) return null;
  const L = spec.length_m, H = spec.height_m, W = spec.width_m;
  if (L == null || H == null || !(L > 0) || !(H > 0) || !(W > 0)) return null;

  const br = (bearingDeg * Math.PI) / 180;
  const cos = Math.cos(br), sin = Math.sin(br);
  // 차 기준 좌표 — x 는 오른쪽(전폭 절반), y 는 앞(전장 절반)
  const hw = W / 2, hl = L / 2;
  const corners: [number, number][] = [[-hw, hl], [hw, hl], [hw, -hl], [-hw, -hl]];

  // 국소 평면 → 경위도. 방위각은 **북 기준 시계방향**이므로
  //   동(m) = x·cos(br) + y·sin(br)
  //   북(m) = −x·sin(br) + y·cos(br)
  const mPerLat = (Math.PI * R) / 180;
  const mPerLon = mPerLat * Math.cos((lat * Math.PI) / 180);
  const ring = corners.map(([x, y]): [number, number] => {
    const east = x * cos + y * sin;
    const north = -x * sin + y * cos;
    return [lon + east / mPerLon, lat + north / mPerLat];
  });
  ring.push(ring[0]);
  return { ring, heightM: H };
}

/** MapLibre 가 먹는 모양. 레이어 하나가 이 소스를 압출한다. */
export function egoFeature(box: Box | null): GeoJSON.FeatureCollection {
  if (!box) return { type: "FeatureCollection", features: [] };
  return {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      properties: { h: box.heightM },
      geometry: { type: "Polygon", coordinates: [box.ring] },
    }],
  };
}

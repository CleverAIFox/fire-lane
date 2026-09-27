/**
 * domain/serviceArea.ts — 측위가 **우리 데이터 범위 안인가.**  (DECISIONS §275)
 *
 * ── 왜 생겼나 (2026-09-27 실측) ─────────────────────────────────
 * GPS 가 **안 잡히는** 경우는 이미 안내가 있다 — 데스크톱 · 권한 거부는
 * `createGpsSource` 가 `onError` 를 내고 "시연은 아래 ▶ 로 주행한다" 가 뜬다.
 *
 * ★ **잡히는데 엉뚱한 데서 잡히는 경우가 구멍이었다.** 서울에서 열면 GPS 가
 *   정상으로 서울 좌표를 준다. 에러가 아니므로 아무 안내도 안 뜨고, 경로는
 *   동명동인데 현위치는 200km 밖이다. 맵매칭이 조용히 실패하거나 엉뚱한
 *   간선에 붙는다 — **조용한 실패**다.
 *
 * ★ 이 저장소는 광주 동명동 한 동네의 데이터만 든다. 개발은 그 밖에서 한다 —
 *   즉 **범위 밖이 예외가 아니라 평소**다. 그래서 이건 시연용 임시 장치가
 *   아니라 정규 경로다 — 지우지 않는다.
 *
 * IN    측위 한 점 · `view.json` 의 `maxBounds`
 * OUT   범위 밖인가 · 얼마나 밖인가(m)
 * 밖    **무엇을 할지는 안 정한다** — 위치원을 갈아탈지, 안내만 띄울지는
 *       `usePositionSource` 가 정한다. 여기는 **재기만** 한다.
 *       **경계를 만들지도 않는다** — `view.json` 이 정본이고 그것은
 *       `publish_web.py` 가 쓴다. 여기서 상수를 박으면 두 벌이 된다.
 */
import type { LngLat } from "./geo";

/**
 * 경계 밖 여유. 이만큼까지는 «안» 으로 본다.
 *
 * ★ `maxBounds` 는 지도가 못 벗어나게 하는 상자라 데이터보다 이미 조금 넓다.
 *   거기에 또 여유를 크게 주면 「경계 바로 밖에서 잡힌 GPS」가 안으로 세어지고,
 *   그러면 맵매칭이 실패하는데 안내는 안 뜬다. 100m 는 **GPS 오차 한 번치**다 —
 *   그보다 멀면 오차가 아니라 다른 동네다.
 */
export const EDGE_MARGIN_M = 100;

/** 위도 1도 ≈ 111,320m. 경도는 위도에 따라 줄어든다. */
const LAT_M = 111_320;

function lonM(lat: number): number {
  return LAT_M * Math.cos((lat * Math.PI) / 180);
}

/** 상자 밖으로 얼마나 나갔나(m). 안이면 0. */
export function metresOutside(
  p: LngLat,
  box: readonly [LngLat, LngLat] | undefined,
): number {
  // ★ **모르면 막지 않는다.** `maxBounds` 가 없는 판(`view.json` 이 옛것이거나
  //   손으로 만든 픽스처)에서 「범위 밖」으로 몰면, 멀쩡한 기계에서 실제 GPS 가
  //   못 쓰인다. 오탐이 본문을 덮으면 사람이 장치를 끈다.
  if (!box) return 0;
  const [[w, s], [e, n]] = box;
  const [lon, lat] = p;
  const dLat = Math.max(s - lat, lat - n, 0) * LAT_M;
  const dLon = Math.max(w - lon, lon - e, 0) * lonM(lat);
  return Math.hypot(dLat, dLon);
}

/** 이 측위로는 안내할 수 없는가. */
export function outsideServiceArea(
  p: LngLat,
  box: readonly [LngLat, LngLat] | undefined,
  marginM: number = EDGE_MARGIN_M,
): boolean {
  return metresOutside(p, box) > marginM;
}

/**
 * 사람이 읽는 사유. **무슨 일이 일어났고 무엇으로 바뀌었는지**를 한 줄로 든다.
 *
 * ★ 거리를 적는 이유 — 「범위 밖」만 적으면 GPS 가 조금 튄 것인지 다른 도시인지
 *   구분이 안 된다. 200km 라고 적히면 사람이 바로 안다.
 */
export function outsideNotice(metres: number): string {
  const far = metres >= 1000
    ? `${Math.round(metres / 1000)}km`
    : `${Math.round(metres)}m`;
  return `현위치가 데이터 범위 밖이다 (${far}) — 실제 GPS 로는 안내할 수 없다. 경로 주행으로 바꿨다`;
}

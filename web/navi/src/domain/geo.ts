/**
 * domain/geo.ts — 좌표 · 각도 · 거리. 순수 함수만.
 *
 * ★ 이 계층은 React·MapLibre·fetch 를 모른다. `seg/vehicle.py` 가
 *   "파일도 경로도 모른다" 고 한 것과 같은 규율이다(MASTER §5-1).
 *   그래야 브라우저 없이 단위 테스트가 돈다.
 *
 * ── 좌표계 ──────────────────────────────────────────────────────
 * WGS84 → 등거리 근사(위도 35.151 기준). 파이프라인의 EPSG:5186 을
 * 브라우저로 가져오지 않는다 — proj4 를 싣지 않으려는 것이고, 계약(§5-2)도
 * 4326 이다.
 *
 * ★ 2026-10-11 (DECISIONS §473). 여기 **「오차가 cm 급이다」**라고 적혀
 *   있었고 그것이 **천 배 틀린 주장**이었다 — 옛 상수로 3.3km 에서 실측
 *   11.09m 다. 상수를 `pyproj` 로 재서 고쳤고 지금은 0.30m 다. 그 수는
 *   `tests/test_localplane.py` 가 **잰다** — 머리말에 적고 끝내지 않는다.
 */

/** 동명동 중심 위도. 등거리 근사의 기준이다. */
export const LAT0 = 35.151;

/** 기준 경도. 상수를 **어디서 쟀는가**를 적어 둔다 — 안 적으면 다시 못 잰다. */
export const LON0 = 126.9266;

/**
 * 기준점에서 **경도** 1도의 미터. `pyproj` 실측 91,120.151 의 정수다.
 *
 * ★ 2026-10-11 (DECISIONS §473). 종전은 `111320 * cos(LAT0)` = 91,019 로
 *   **0.111% 작았다** — 그 꼴은 회전타원체를 구로 본다.
 */
export const MX = 91120;

/**
 * 기준점에서 **위도** 1도의 미터. `pyproj` 실측 110,943.342 의 정수다.
 *
 * ★ 2026-10-11 (DECISIONS §473). 종전은 **110,574** 였고 그것은 **적도**의
 *   자오선 1도다 — 이 위도보다 0.333% 짧다. 그리고 번들 안에 같은 수가
 *   네 벌이었다(여기 110,574 · `context.ts` 110,540 · `egobox.ts` 적도
 *   반지름에서 111,319.5 · `serviceArea.ts` 111,320). 넷 다 틀렸다.
 *
 * ★ 파이썬 정본(`src/firelane/localplane.py`)과 **같은 수**이고,
 *   `tests/test_localplane.py` 가 이 파일을 열어 그 둘을 댄다.
 */
export const MY = 110943;

export type LngLat = [number, number];

/** WGS84 → 로컬 미터. */
export function toM(p: LngLat): [number, number] {
  return [p[0] * MX, p[1] * MY];
}

/** 로컬 미터 → WGS84. */
export function toLngLat(x: number, y: number): LngLat {
  return [x / MX, y / MY];
}

/** 두 WGS84 점 사이 거리(m). */
export function distM(a: LngLat, b: LngLat): number {
  return Math.hypot((b[0] - a[0]) * MX, (b[1] - a[1]) * MY);
}

/**
 * a → b 방위각(도, 0=북, 시계방향).
 *
 * ★ `atan2(dx, dy)` 다. `atan2(dy, dx)` 가 아니다 — 북을 0 으로 잡고
 *   시계방향으로 재는 나침반 규약이라 인자 순서가 뒤집힌다.
 */
export function bearing(a: LngLat, b: LngLat): number {
  const dx = (b[0] - a[0]) * MX;
  const dy = (b[1] - a[1]) * MY;
  return ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
}

/** 각도 a→b 최단 차이(-180~180). 359°→1° 을 358도로 세지 않는다. */
export function angleDelta(a: number, b: number): number {
  let d = (b - a) % 360;
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return d;
}

/** 각도 차이를 0~90 으로 접는다. 매칭에서는 역주행도 같은 도로다. */
export function foldedDiff(a: number, b: number): number {
  let d = Math.abs(a - b) % 360;
  if (d > 180) d = 360 - d;
  return d > 90 ? 180 - d : d;
}

/** 좌표열의 누적 거리(m). 첫 원소는 0. */
export function cumulative(coords: LngLat[]): number[] {
  const cum = [0];
  for (let i = 1; i < coords.length; i++) {
    cum.push(cum[i - 1] + distM(coords[i - 1], coords[i]));
  }
  return cum;
}

/**
 * 좌표열 위에서 시작점부터 `alongM` 만큼 간 지점과 그때의 진행방향.
 * 시뮬레이션 주행과 "다음 구간까지 남은 거리" 가 함께 쓴다.
 */
export function pointAlong(
  coords: LngLat[], cum: number[], alongM: number,
): { point: LngLat; heading: number } {
  const total = cum[cum.length - 1];
  const d = Math.max(0, Math.min(total, alongM));
  let i = 1;
  while (i < cum.length - 1 && cum[i] < d) i++;
  const segLen = cum[i] - cum[i - 1] || 1;
  const f = (d - cum[i - 1]) / segLen;
  const a = coords[i - 1];
  const b = coords[i];
  return {
    point: [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f],
    heading: bearing(a, b),
  };
}

/** 점에서 선분에 내린 수선의 발과 거리. 스냅의 최소 단위다. */
export function projectOnSegment(
  px: number, py: number, ax: number, ay: number, bx: number, by: number,
): { t: number; cx: number; cy: number; dist: number } {
  const dx = bx - ax;
  const dy = by - ay;
  const dd = dx * dx + dy * dy;
  const t = dd === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / dd));
  const cx = ax + t * dx;
  const cy = ay + t * dy;
  return { t, cx, cy, dist: Math.hypot(px - cx, py - cy) };
}

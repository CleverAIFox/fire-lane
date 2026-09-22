/**
 * domain/turning.ts — 코너를 이 차가 돌 수 있는가. **제원 완성 차종만** 본다.  (DECISIONS §218-2)
 *
 * ── 정책 (사용자 결정 2026-09-22) ─────────────────────────────────
 * 회전반경은 제원이 다 확보된 차종에만 쓴다 — 전장 · 전폭 · 전고 · 축거 · 최소회전반경이 전부
 * 제원표에 있고 편성 대장과 **확정** 대응인 차(`fleet.json` 의 `spec_complete`). 지금은 중형
 * 펌프차 · 대형 물탱크차 둘이다. 값은 제작규격 대표값이지 그 차를 잰 것이 아니라서
 * **막지 않는다** — 통행 규칙과 같이 비용을 올리고 경고한다(§215-1).
 *
 * ── 모형 ─────────────────────────────────────────────────────────
 * 폭 w 인 두 길이 꺾임각 θ 로 만나는 코너에서, 차의 중심선이 벽에서 전폭/2 를 지키며 그릴 수
 * 있는 가장 큰 원호의 반지름은 (안쪽 모서리를 스치고 바깥 벽에 닿는 원호)
 *
 *     R_max = c / (1 − cos(θ/2)),   c = w − 전폭     (중심선이 쓸 수 있는 폭)
 *
 * 차가 필요한 중심선 반지름은 최소회전반경(바깥 앞바퀴) − 전폭/2 다. R_max 가 그보다 작으면
 * 「코너가 좁다」. 90° · w 5m · 펌프차(7.3m) → c 2.5 · R_max 8.5 ≥ 6.05 로 돈다. w 4m 면 5.1 로 못 돈다.
 *
 * ★ 보수적이다 — w 는 두 구간 **최소 폭** 중 작은 것이라 교차로의 실제 너른 공간(모서리 가각)을
 *   모른다. 그래서 막지 않는다. 폭을 모르는 구간이 끼면 점검하지 않는다(모르면 말하지 않는다).
 * ★ `TIGHT_TURN_M` 은 **근거 없는 가정값**이다 — 좁은 코너 한 번을 400m 우회와 같게 본다.
 */
import { bearing, angleDelta, distM, type LngLat } from "./geo";
import type { GraphEdge, NaviGraph, VehicleSpec } from "./types";

export const TIGHT_TURN_M = 400;
/** 이보다 완만한 꺾임은 코너로 안 본다(°) */
export const MIN_DEFLECTION = 30;
/** 방향을 잴 때 노드에서 떨어진 거리(m) — 짧은 꼭짓점 하나에 방향이 휘둘리지 않게 */
const PROBE_M = 8;

/** 이 차가 코너 점검을 받는가 — 제원 완성 차종만 값이 있다 */
export function turnCheckRadius(spec: VehicleSpec): number | null {
  return spec.turn_check_radius_m ?? null;
}

/** 노드 `n` 에서 엣지 `e` 를 따라 나가는 방향(°) */
function outBearing(e: GraphEdge, n: number): number | null {
  const c: LngLat[] = e.a === n ? e.coords : [...e.coords].reverse();
  if (c.length < 2) return null;
  let far = c[1];
  for (let i = 1; i < c.length; i++) {
    far = c[i];
    if (distM(c[0], c[i]) >= PROBE_M) break;
  }
  return bearing(c[0], far);
}

/** 들어온 엣지 → 노드 → 나갈 엣지의 꺾임각(0 = 직진, 180 = 유턴) */
export function deflection(inE: GraphEdge, n: number, outE: GraphEdge): number | null {
  const bi = outBearing(inE, n);
  const bo = outBearing(outE, n);
  if (bi == null || bo == null) return null;
  const heading = (bi + 180) % 360;          // 노드로 들어올 때의 진행 방향
  return Math.abs(angleDelta(heading, bo));
}

/** 코너가 쓸 수 있는 중심선 반지름(m). 점검할 수 없으면 null */
export function cornerRadiusMax(widthM: number | null, vehicleW: number, defl: number | null): number | null {
  if (widthM == null || defl == null) return null;
  if (defl < MIN_DEFLECTION) return Infinity;
  const c = widthM - vehicleW;
  if (c <= 0) return 0;
  return c / (1 - Math.cos(((defl / 2) * Math.PI) / 180));
}

export interface TightTurn { needM: number; haveM: number; defl: number }

/**
 * 코너에서 쓸 수 있는 폭 — **벽~벽 최대 폭**(`width_max_m`)을 먼저 쓴다.
 * ★ 최소 폭(`width_min_m`)은 구간의 **가장 좁은 병목**이지 모서리의 폭이 아니다. 그것으로 재면
 *   전이의 절반 가까이(4,472 중 2,038)가 「좁은 코너」 가 됐다 — 차는 모서리에서 보도 · 가각까지
 *   쓴다. 벽~벽 값이 없는 구간만 최소 폭으로 잰다.
 */
export function cornerWidth(e: GraphEdge): number | null {
  return e.width_max_m ?? e.width_min_m ?? null;
}

/** 이 전이가 이 차에게 좁은 코너인가. 점검 대상이 아니거나 넉넉하면 null */
export function tightTurn(
  graph: NaviGraph, spec: VehicleSpec, inIdx: number, node: number, outIdx: number,
): TightTurn | null {
  const R = turnCheckRadius(spec);
  if (R == null) return null;
  const a = graph.edges[inIdx], b = graph.edges[outIdx];
  if (!a || !b) return null;
  const wa = cornerWidth(a), wb = cornerWidth(b);
  const w = wa == null || wb == null ? null : Math.min(wa, wb);
  const defl = deflection(a, node, b);
  const have = cornerRadiusMax(w, spec.width_m, defl);
  const need = R - spec.width_m / 2;
  if (have == null || have >= need) return null;
  return { needM: need, haveM: have, defl: defl ?? 0 };
}

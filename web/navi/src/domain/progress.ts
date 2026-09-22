/**
 * domain/progress.ts — **GPS 로 경로 위 어디쯤인지 추정한다.** 턴바이턴의 입력이다.
 *
 * ══ 왜 생겼나 (2026-09-22 · DECISIONS §213-2) ═══════════════════
 * 종전 흐름은 「GPS → 구간 스냅(seg_uid) → 그 구간이 경로의 몇 번째인가 → 주행거리」
 * 였다. 세 군데가 약했다.
 *
 *   1. 스냅은 교차로에서 `confident: false` 가 잦고 그때 **옛 값을 붙든다.**
 *      회전 안내가 정작 교차로에서 멈춘다.
 *   2. 경로가 같은 구간을 두 번 지나면(되돌아 나오기) 첫 번째 것만 찾는다.
 *   3. 순간이동을 모른다. GPS 가 음영(고가 · 빌딩 숲)에서 8초 끊겼다가 250m
 *      앞에서 다시 잡히면, 그 사이 회전들을 전부 「이미 지남」 으로 버리는 것까지는
 *      했지만 **새 위치에 맞는 안내를 즉시 다시 내지 않았다.**
 *
 * 그리고 이 셋이 한 번도 안 드러났다 — 시뮬레이션은 **경로 자체를 따라 걷는 점**
 * 이라 추정이 틀려도 맞아 보였다. 폐루프가 돈 적이 없다.
 *
 * ══ 무엇을 하나 ══════════════════════════════════════════════
 * 경로 선형(polyline) 위로 GPS 를 투영하고, **직전 추정 + 속도 × 경과시간** 으로
 * 예측한 자리와 가까운 투영을 고른다.
 *
 *     비용 = 수직거리 + 방향 벌점 + λ·|s − s예측|
 *
 *   · 예측이 있으니 되돌아 나오는 경로에서도 지금 몇 번째 통과인지 가른다(2).
 *   · 구간 스냅이 아니라 선형 투영이라 교차로에서 끊기지 않는다(1).
 *   · 고른 자리가 예측에서 문턱(`jumpM`) 넘게 벗어나면 **순간이동**으로 보고
 *     `jumped: true` 를 낸다. 받는 쪽(useVoice)이 말하던 것을 끊고 그 자리 안내를
 *     바로 낸다(3). 이동은 **받아들인다** — GPS 가 맞고 예측이 틀린 것이다.
 *   · 수직거리가 `offM` 을 `offFixes` 번 연속 넘으면 이탈이다. 한 번 튄 것으로
 *     재탐색하지 않는다.
 *
 * ★ 거리 단위가 둘이다. 선형 길이(좌표로 잰 것)와 `edge.length_m`(파이프라인이
 *   잰 것)이 조금 다르다. 회전 지점(`extractManeuvers`)이 `length_m` 합으로
 *   서 있으므로 **결과 `s` 는 `length_m` 공간**으로 옮겨 낸다 — 엣지 안에서
 *   선형 비례로. 안 옮기면 회전 안내가 몇 m 씩 밀린다.
 *
 * ★ 순수하다. React · MapLibre · 시계를 모른다 — 시각은 인자로 받는다.
 */
import { MX, MY, bearing as brgOf, angleDelta, type LngLat } from "./geo";
import type { RoutePlan } from "./types";

export interface ProgressKnobs {
  /** 이 수직거리(m) 안의 투영만 후보로 본다. 밖이면 이탈 후보 */
  offM: number;
  /** 이탈로 확정하기까지 연속으로 벗어나야 하는 측위 수 */
  offFixes: number;
  /** 예측과의 거리 1m 당 벌점(m). 작으면 GPS 를 믿고, 크면 예측을 믿는다 */
  lambda: number;
  /** 진행방향과 90도 넘게 어긋난 선분 벌점(m) — 되돌아 나오는 경로에서 반대 차로를 거른다 */
  backPenaltyM: number;
  /** 순간이동 문턱의 바닥(m). 실제 문턱은 max(이것, 속도×경과×배수 + 여유) */
  jumpM: number;
  /**
   * 측위가 이만큼(초) 끊겼다 다시 오면 예측과 가까워도 **재동기화**로 본다.
   * ★ 8초 음영 뒤 예측이 우연히 20m 안에 맞아도, 그 8초 동안 말했어야 할 안내는
   *   못 나갔다. 새 자리 기준으로 다시 말해야 한다 — 문턱은 거리만이 아니다.
   */
  gapSec: number;
  /** 예측을 이 시간(초) 넘게 늘리지 않는다 — 오래 끊기면 예측은 의미가 없다 */
  maxPredictSec: number;
}

export const PROGRESS_KNOBS: ProgressKnobs = {
  offM: 30, offFixes: 2, lambda: 0.08, backPenaltyM: 25, jumpM: 60, maxPredictSec: 6,
  gapSec: 3,
};

/** 경로를 미터 좌표로 한 번 구워 둔다. **경로당 한 번.** */
export interface RouteGeom {
  xy: [number, number][];
  /** 선형 누적 길이(m) */
  cum: number[];
  /** 꼭짓점 i 가 속한 엣지 번호(선분 i→i+1 기준) */
  edgeOf: number[];
  /** 엣지 i 의 선형 [시작, 끝] */
  gSpan: [number, number][];
  /** 엣지 i 의 length_m 공간 [시작, 끝] */
  mSpan: [number, number][];
  totalM: number;
  coords: LngLat[];
}

export function routeGeom(plan: RoutePlan): RouteGeom {
  const xy: [number, number][] = [];
  const cum: number[] = [];
  const edgeOf: number[] = [];
  const gSpan: [number, number][] = [];
  const mSpan: [number, number][] = [];
  const coords: LngLat[] = [];
  let acc = 0;
  let macc = 0;
  plan.edges.forEach((e, i) => {
    const c = plan.forward[i] ? e.coords : [...e.coords].reverse();
    const g0 = xy.length ? cum[cum.length - 1] : 0;
    for (let k = xy.length ? 1 : 0; k < c.length; k++) {
      const p: [number, number] = [c[k][0] * MX, c[k][1] * MY];
      if (xy.length) acc += Math.hypot(p[0] - xy[xy.length - 1][0], p[1] - xy[xy.length - 1][1]);
      xy.push(p); cum.push(acc); coords.push(c[k]);
      edgeOf.push(i);
    }
    gSpan.push([g0, acc]);
    const L = e.length_m ?? (acc - g0);
    mSpan.push([macc, macc + L]);
    macc += L;
  });
  // 선분 i→i+1 은 끝점의 엣지에 속한다(이어붙인 첫 점은 앞 엣지의 끝점이다)
  for (let i = 0; i + 1 < edgeOf.length; i++) edgeOf[i] = edgeOf[i + 1];
  return { xy, cum, edgeOf, gSpan, mSpan, totalM: macc, coords };
}

/** 선형 길이 → length_m 공간 */
function toM(geom: RouteGeom, g: number, edge: number): number {
  const [g0, g1] = geom.gSpan[edge];
  const [m0, m1] = geom.mSpan[edge];
  const f = g1 > g0 ? (g - g0) / (g1 - g0) : 0;
  return m0 + Math.max(0, Math.min(1, f)) * (m1 - m0);
}

/** length_m 공간 → 선형 길이 */
function toG(geom: RouteGeom, m: number): number {
  const n = geom.mSpan.length;
  for (let i = 0; i < n; i++) {
    const [m0, m1] = geom.mSpan[i];
    if (m <= m1 || i === n - 1) {
      const [g0, g1] = geom.gSpan[i];
      const f = m1 > m0 ? (m - m0) / (m1 - m0) : 0;
      return g0 + Math.max(0, Math.min(1, f)) * (g1 - g0);
    }
  }
  return 0;
}

/** 경로 위 s(length_m 공간)의 좌표 · 진행방향 · 엣지. 마커 · 카메라가 쓴다 */
export function pointAtM(geom: RouteGeom, s: number): { point: LngLat; bearing: number; edge: number } {
  const g = toG(geom, Math.max(0, Math.min(geom.totalM, s)));
  const { cum, coords } = geom;
  let i = 1;
  while (i < cum.length - 1 && cum[i] < g) i++;
  const seg = cum[i] - cum[i - 1] || 1;
  const f = (g - cum[i - 1]) / seg;
  const a = coords[i - 1];
  const b = coords[i] ?? a;
  return {
    point: [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f],
    bearing: brgOf(a, b),
    edge: geom.edgeOf[i - 1] ?? 0,
  };
}

/** 추정기가 들고 다니는 것. 불변 값으로 주고받는다 */
export interface ProgressState {
  s: number;
  /** m/s. 평활한 경로 방향 속도 */
  v: number;
  /** 마지막 측위 시각(ms) */
  t: number;
  /** 연속 이탈 측위 수 */
  offCount: number;
}

export interface ProgressResult {
  /** 경로 시작부터 온 거리(m, length_m 공간) */
  s: number;
  /** 경로까지 수직거리(m) */
  lateralM: number;
  onRoute: boolean;
  /** 예측에서 크게 벗어난 곳으로 옮겨 붙었다 — 안내를 다시 내야 한다 */
  jumped: boolean;
  /** 옮겨 붙은 거리(m). 앞이 양수 */
  jumpM: number;
  /** 지금 밟고 있는 `plan.edges` 번호 */
  edge: number;
  point: LngLat;
  bearing: number;
}

export interface FixIn {
  lon: number;
  lat: number;
  heading: number | null;
  /** 측위 시각(ms). 시뮬레이션·재생도 이것을 채운다 */
  t: number;
}

/**
 * 측위 하나를 먹고 새 상태와 결과를 낸다.
 * @param prev 첫 측위면 null — 예측 없이 가장 가까운 투영을 고른다
 */
export function locate(
  geom: RouteGeom, fix: FixIn, prev: ProgressState | null,
  k: ProgressKnobs = PROGRESS_KNOBS,
): { state: ProgressState; result: ProgressResult } {
  const px = fix.lon * MX;
  const py = fix.lat * MY;
  const dt = prev ? Math.max(0, Math.min(k.maxPredictSec, (fix.t - prev.t) / 1000)) : 0;
  const sPred = prev ? prev.s + prev.v * dt : null;

  let best = { cost: Infinity, g: 0, edge: 0, dist: Infinity, brg: 0 };
  let nearest = { dist: Infinity, g: 0, edge: 0, brg: 0 };
  const { xy, cum, edgeOf } = geom;
  for (let i = 0; i + 1 < xy.length; i++) {
    const [ax, ay] = xy[i];
    const [bx, by] = xy[i + 1];
    const dx = bx - ax, dy = by - ay;
    const dd = dx * dx + dy * dy;
    const t = dd === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / dd));
    const cx = ax + t * dx, cy = ay + t * dy;
    const dist = Math.hypot(px - cx, py - cy);
    const g = cum[i] + t * Math.sqrt(dd);
    const brg = ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
    if (dist < nearest.dist) nearest = { dist, g, edge: edgeOf[i], brg };
    if (dist > k.offM) continue;
    let cost = dist;
    if (fix.heading != null && Number.isFinite(fix.heading)
        && Math.abs(angleDelta(fix.heading, brg)) > 100) cost += k.backPenaltyM;
    if (sPred != null) cost += k.lambda * Math.abs(toM(geom, g, edgeOf[i]) - sPred);
    if (cost < best.cost) best = { cost, g, edge: edgeOf[i], dist, brg };
  }

  // ── 경로 밖 ────────────────────────────────────────────────
  if (!Number.isFinite(best.cost)) {
    const offCount = (prev?.offCount ?? 0) + 1;
    const s = prev?.s ?? toM(geom, nearest.g, nearest.edge);
    const at = pointAtM(geom, s);
    return {
      state: { s, v: prev?.v ?? 0, t: fix.t, offCount },
      result: {
        s, lateralM: nearest.dist, onRoute: offCount < k.offFixes,
        jumped: false, jumpM: 0, edge: at.edge, point: at.point, bearing: at.bearing,
      },
    };
  }

  const s = toM(geom, best.g, best.edge);
  let v = prev?.v ?? 0;
  let jumped = false;
  let jumpM = 0;
  if (prev && sPred != null) {
    const gate = Math.max(k.jumpM, Math.abs(prev.v) * dt * 1.5 + 25);
    jumpM = s - sPred;
    const wallGap = (fix.t - prev.t) / 1000;
    if (Math.abs(jumpM) > gate || (wallGap > k.gapSec && Math.abs(s - prev.s) > 30)) {
      jumped = true;
      // 끊겼던 동안의 평균 속도는 모른다. 합리적 범위면 쓰고 아니면 둔다
      const vv = wallGap > 0 ? (s - prev.s) / wallGap : 0;
      if (vv > 0 && vv < 40) v = vv;
    } else if (dt > 0.05) {
      const inst = (s - prev.s) / dt;
      if (inst > -3 && inst < 40) v = v * 0.6 + Math.max(0, inst) * 0.4;
    }
  }
  const at = pointAtM(geom, s);
  return {
    state: { s, v, t: fix.t, offCount: 0 },
    result: {
      s, lateralM: best.dist, onRoute: true, jumped, jumpM,
      edge: best.edge, point: at.point, bearing: at.bearing,
    },
  };
}

/**
 * 측위 사이를 메운다(추측항법). 카메라 · 마커가 60fps 로 부른다.
 * ★ 마지막 측위에서 `capSec` 넘게 앞서 가지 않는다. GPS 가 끊겼는데 차가
 *   계속 달리는 것처럼 그리면 그것이 「가정만 하는 내비」 다.
 */
export function predictS(st: ProgressState, nowMs: number, totalM: number, capSec = 1.5): number {
  const dt = Math.max(0, Math.min(capSec, (nowMs - st.t) / 1000));
  return Math.max(0, Math.min(totalM, st.s + st.v * dt));
}

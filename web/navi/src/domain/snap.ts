/**
 * domain/snap.ts — GPS 좌표를 구간에 붙인다.  (PLAN #61)
 *
 * 좌표 하나 → 가장 그럴듯한 seg_uid · 진행률 · **진행방향** 방위각.
 * 내비의 나머지 전부가 이 함수 위에 선다.
 *
 * ── 왜 상용 map-matching 을 안 쓰는가 ─────────────────────────
 * 구간이 1,101 개뿐이다. 브루트포스가 2.2ms 다. HMM 을 얹을 이유가 없다.
 * 대신 네 신호를 섞는다 — 거리 · 방위각 · 직전 스냅 · 경로.
 *
 *   거리만                 70%
 *   + 방위각               79%
 *   + 직전 스냅(연속주행)   91%      GPS σ=4m · 방위 σ=15° · n=300
 *
 * ── ★ 경로를 알아야 한다 ────────────────────────────────────────
 * 2026-09-05. 경로 위를 달리는데 **옆 골목에 붙는 일이 12%** 였다
 * (GPS σ=4m · n=120). 화면이 "경로 최소폭 3.68m" 라면서 동시에
 * "현재 구간 폭 0.97m" 를 띄웠다 — 0.97m 는 `edgeCost` 가 막으므로
 * 경로에 있을 수 없는 값이다.
 *
 * ★ **하드 제한이 아니라 할인이다.** 경로 밖을 아예 못 붙게 하면
 *   이탈을 영원히 감지하지 못한다. 실제로 벗어나면 할인을 이기고 밖에
 *   붙어야 하고, 그것이 재탐색 신호다(#63 ④).
 *
 * ── ★ bearing 은 진행방향이지 형상 방향이 아니다 ────────────────
 * `segments.geojson` 의 선이 어느 쪽으로 그려졌는지는 임의다. 북쪽으로
 * 그려진 길을 남쪽으로 달리면 180도 어긋난다. `heading` 이 주어지면
 * 그쪽으로 뒤집어 맞추고, 없으면 `bearingKnown: false` 로 알린다.
 */

import {
  MX, MY, foldedDiff, angleDelta, projectOnSegment,
  type LngLat,
} from "./geo";
import type { SnapResult, Verdict } from "./types";

export interface SnapSegment {
  seg_uid: string;
  verdict: Verdict;
  width_min_m: number | null;
  seg_label?: string;
  coords: LngLat[];
}

/** 갈아끼울 계수. 근거가 생기면 여기를 고친다. */
export interface SnapKnobs {
  /** 방위각 1도당 몇 m 의 벌점으로 칠 것인가 */
  bearingW: number;
  /** 직전 구간 할인(m). 크면 안 떨어지고, 작으면 튄다 */
  stickyM: number;
  /**
   * 활성 경로 위 구간 할인(m).
   * ★ 12% 오스냅을 잡을 만큼 크되 **실제 이탈을 가릴 만큼 크면 안 된다.**
   *   20m 는 GPS 오차(σ 4m)의 다섯 배라 잡음은 이기고, 한 블록 벗어나면
   *   (보통 30m+) 진다.
   */
  routeM: number;
  /** 이 거리를 넘으면 도로 밖으로 본다 */
  offroadM: number;
  /** 1등과 2등 비용 차가 이 값 미만이면 안 믿는다 */
  ambiguousM: number;
}

export const SNAP_KNOBS: SnapKnobs = {
  bearingW: 0.15, stickyM: 8, routeM: 20, offroadM: 25, ambiguousM: 3,
};

export interface Prepared {
  seg: SnapSegment;
  xy: [number, number][];
  cum: number[];
  len: number;
}

/**
 * 구간 목록을 미리 미터 좌표로 바꿔둔다. **한 번만 호출한다.**
 * 매 틱마다 다시 만들면 그것이 병목이 된다.
 */
export function prepare(segments: SnapSegment[]): Prepared[] {
  return segments.map((seg) => {
    const xy = seg.coords.map(([lon, lat]) => [lon * MX, lat * MY] as [number, number]);
    const cum = [0];
    for (let i = 1; i < xy.length; i++) {
      cum.push(cum[i - 1] + Math.hypot(xy[i][0] - xy[i - 1][0], xy[i][1] - xy[i - 1][1]));
    }
    return { seg, xy, cum, len: cum[cum.length - 1] };
  });
}

export interface SnapOpts {
  heading?: number | null;
  prevUid?: string | null;
  onRoute?: Set<string> | null;
  knobs?: SnapKnobs;
}

export function snap(
  lon: number, lat: number, prepared: Prepared[], opts: SnapOpts = {},
): SnapResult | null {
  const { heading, prevUid, onRoute, knobs = SNAP_KNOBS } = opts;
  const px = lon * MX;
  const py = lat * MY;

  let bestCost = Infinity;
  let second = Infinity;
  let best: { p: Prepared; dist: number; along: number; brg: number; cx: number; cy: number }
    | null = null;

  for (const p of prepared) {
    const onR = onRoute?.has(p.seg.seg_uid) ?? false;
    const { xy } = p;
    for (let i = 0; i < xy.length - 1; i++) {
      const [ax, ay] = xy[i];
      const [bx, by] = xy[i + 1];
      const { cx, cy, dist, t } = projectOnSegment(px, py, ax, ay, bx, by);
      const brg = ((Math.atan2(bx - ax, by - ay) * 180) / Math.PI + 360) % 360;

      let cost = dist;
      if (heading != null && Number.isFinite(heading)) {
        cost += foldedDiff(heading, brg) * knobs.bearingW;
      }
      if (prevUid && p.seg.seg_uid === prevUid) cost -= knobs.stickyM;
      if (onR) cost -= knobs.routeM;

      if (cost < bestCost) {
        second = bestCost;
        bestCost = cost;
        const along = p.cum[i] + t * Math.hypot(bx - ax, by - ay);
        best = { p, dist, along, brg, cx, cy };
      } else if (cost < second) second = cost;
    }
  }
  if (!best) return null;

  // ★ 형상 방향을 진행방향으로 뒤집는다.
  let bearing = best.brg;
  let bearingKnown = false;
  if (heading != null && Number.isFinite(heading)) {
    if (Math.abs(angleDelta(heading, bearing)) > 90) bearing = (bearing + 180) % 360;
    bearingKnown = true;
  }

  return {
    seg_uid: best.p.seg.seg_uid,
    verdict: best.p.seg.verdict,
    width_min_m: best.p.seg.width_min_m,
    seg_label: best.p.seg.seg_label,
    progress: best.p.len > 0 ? best.along / best.p.len : 0,
    dist_m: Math.round(best.dist * 100) / 100,
    bearing: Math.round(bearing * 10) / 10,
    bearingKnown,
    point: [best.cx / MX, best.cy / MY],
    // 1등과 2등이 팽팽하면 믿지 않는다. 교차로에서 흔하다.
    confident: best.dist <= knobs.offroadM && second - bestCost >= knobs.ambiguousM,
    onRoute: onRoute?.has(best.p.seg.seg_uid) ?? false,
  };
}

/**
 * 연속 위치를 받는 쪽에서 쓰는 상태 보관용 래퍼.
 *
 * ★ heading 이 없으면 **직전 위치와의 차이로 만들어 넣는다.** GPS 의
 *   heading 은 저속에서 null 이 오거나 튄다. 이동량 2m 이상이면 그쪽이
 *   훨씬 믿을 만하다.
 */
export function createTracker(prepared: Prepared[], knobs: SnapKnobs = SNAP_KNOBS) {
  let prevUid: string | null = null;
  let prev: LngLat | null = null;
  let route: Set<string> | null = null;

  return {
    /** 활성 경로를 알린다. null 이면 할인 없음. */
    setRoute(uids: Set<string> | null) { route = uids; },

    update(lon: number, lat: number, heading?: number | null): SnapResult | null {
      let h = heading;
      if ((h == null || !Number.isFinite(h)) && prev) {
        const dx = (lon - prev[0]) * MX;
        const dy = (lat - prev[1]) * MY;
        if (Math.hypot(dx, dy) >= 2) {
          h = ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
        }
      }
      const r = snap(lon, lat, prepared, { heading: h, prevUid, onRoute: route, knobs });
      if (r?.confident) { prevUid = r.seg_uid; prev = [lon, lat]; }
      return r;
    },
    reset() { prevUid = null; prev = null; route = null; },
    get current() { return prevUid; },
  };
}

export type Tracker = ReturnType<typeof createTracker>;

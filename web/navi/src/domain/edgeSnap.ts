/**
 * domain/edgeSnap.ts — 좌표를 **통행가능 구간 위**로 투영한다.  (DECISIONS §218-3)
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `domain/graph.ts` 가 상한(600)을 넘었다. 투영은 A* 와 **다른 물음**이다 —
 *   「이 점은 어느 구간의 어디인가」 와 「저기까지 어느 길로 가나」. A* 를 고치러 온
 *   사람이 형상 자르기를 읽고 지나갈 이유가 없다.
 *
 * ★ 2026-09-22. 출발·도착을 가장 가까운 **노드**에 붙이면 구간 한가운데 선 사람이
 *   교차점으로 옮겨진다. 웅토피아(DECISIONS §134)가 같은 결함으로 20m 를 1,172m 로
 *   안내했다. 가장 가까운 **통행가능 구간**에 투영하고 부분 구간 비용을 셈에 넣는다.
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 *
 * IN    NaviGraph · Adjacency(통행가능의 기준) · 좌표
 * OUT   EdgeSnap — 구간 인덱스 · 투영점 · 형상 비율 · 양끝까지 부분 길이
 * 밖    경로를 내지 않는다. 투영점을 끝점으로 받아 길을 내는 쪽은 `graph.ts` 다.
 */

import { distM, MX, MY, type LngLat } from "./geo";
import { usableEdges, type Adjacency } from "./adjacency";
import type { GraphEdge, NaviGraph } from "./types";

/** 이보다 짧은 부분 구간(형상 m)은 노드 위에 선 것으로 본다 */
export const NODE_EPS_M = 0.05;

/** 구간 위 투영 결과 */
export interface EdgeSnap {
  /** `graph.edges` 인덱스 */
  idx: number;
  edge: GraphEdge;
  /** 투영점 */
  point: LngLat;
  /** 형상(a→b) 위 비율 0~1 */
  t: number;
  /** 원점 → 투영점 직선거리(m) */
  distM: number;
  /** 투영점 → a · → b 부분 길이(m, `length_m` 공간) */
  toA_M: number;
  toB_M: number;
}

export function geomLen(coords: LngLat[]): number {
  let L = 0;
  for (let i = 1; i < coords.length; i++) L += distM(coords[i - 1], coords[i]);
  return L;
}

/** 형상(a→b)의 비율 t0..t1 부분. a→b 순서로 낸다 */
export function clipCoords(coords: LngLat[], t0: number, t1: number): LngLat[] {
  const total = geomLen(coords);
  if (coords.length < 2 || total <= 0) return [coords[0], coords[coords.length - 1]];
  const d0 = t0 * total, d1 = t1 * total;
  const at = (d: number): LngLat => {
    let acc = 0;
    for (let i = 1; i < coords.length; i++) {
      const s = distM(coords[i - 1], coords[i]);
      if (acc + s >= d || i === coords.length - 1) {
        const f = s > 0 ? Math.max(0, Math.min(1, (d - acc) / s)) : 0;
        const p = coords[i - 1], q = coords[i];
        return [p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f];
      }
      acc += s;
    }
    return coords[coords.length - 1];
  };
  const out: LngLat[] = [at(d0)];
  let acc = 0;
  for (let i = 1; i < coords.length - 1; i++) {
    acc += distM(coords[i - 1], coords[i]);
    if (acc > d0 && acc < d1) out.push(coords[i]);
  }
  out.push(at(d1));
  return out;
}

/**
 * 좌표에서 가장 가까운 **통행가능 구간**과 그 위 투영점.
 * 통행가능 = 인접리스트에 실린 구간(`nearestNode` 와 같은 기준 — 막힘 · 폭 미달 · 신고 제외는 빠진다).
 */
export function snapToEdge(graph: NaviGraph, adj: Adjacency, p: LngLat): EdgeSnap | null {
  const px = p[0] * MX, py = p[1] * MY;
  let best: { idx: number; d2: number; along: number; total: number; pt: LngLat } | null = null;
  for (const idx of usableEdges(adj)) {
    const c = graph.edges[idx].coords;
    let acc = 0;
    let total = 0;
    for (let i = 1; i < c.length; i++) total += distM(c[i - 1], c[i]);
    for (let i = 1; i < c.length; i++) {
      const ax = c[i - 1][0] * MX, ay = c[i - 1][1] * MY;
      const bx = c[i][0] * MX, by = c[i][1] * MY;
      const dx = bx - ax, dy = by - ay;
      const L2 = dx * dx + dy * dy;
      const f = L2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L2)) : 0;
      const qx = ax + dx * f, qy = ay + dy * f;
      const d2 = (px - qx) ** 2 + (py - qy) ** 2;
      if (!best || d2 < best.d2) {
        best = { idx, d2, along: acc + Math.sqrt(L2) * f, total, pt: [qx / MX, qy / MY] };
      }
      acc += Math.sqrt(L2);
    }
  }
  if (!best) return null;
  const edge = graph.edges[best.idx];
  const t = best.total > 0 ? Math.max(0, Math.min(1, best.along / best.total)) : 0;
  const L = edge.length_m ?? best.total;
  return {
    idx: best.idx, edge, point: best.pt, t, distM: Math.sqrt(best.d2),
    toA_M: L * t, toB_M: L * (1 - t),
  };
}

/**
 * 자른 사본의 선형 비율(a→b, 0~1) → 원본 구간 비율. 자르지 않은 구간은 그대로.
 * 스냅의 `progress` 는 원본 기준이라 둘을 오갈 때 쓴다.
 */
export function fullProgress(e: GraphEdge, f01: number): number {
  return e.clip ? e.clip.t0 + f01 * (e.clip.t1 - e.clip.t0) : f01;
}

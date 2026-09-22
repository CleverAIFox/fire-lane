/**
 * domain/access.ts — **차가 사건 지점까지 못 들어갈 때 어디에 댈 것인가.**  (DECISIONS §214-2)
 *
 * ══ 왜 생겼나 ═══════════════════════════════════════════════════
 * 종전에는 경로가 안 나오면 13(「차량 경로 없음 · 다른 접근 지점 필요」)을 띄우고
 * **끝났다.** 다른 접근 지점이 어디인지는 사람에게 넘겼다. 통행 불가 신고(16) 뒤에도
 * 우회가 없으면 17 이 아니라 13 으로 떨어졌다(2026-09-22 검수 — 와이어프레임은 16 → 17).
 *
 * 현장은 이렇게 한다 — **차가 닿는 가장 가까운 곳에 대고 거기서 걸어 들어간다**(호스를
 * 끌고). 그래서 A* 가 실패하면 출발점에서 **닿는 노드 전부**를 한 번에 펼치고, 그중
 * 사건 지점과 직선으로 가장 가까운 노드를 대체 접근 지점으로 고른다.
 *
 * ★ 직선 거리다. 걸어 들어가는 길(보도 · 계단 · 사유지)은 모른다 — 화면이 「도보 NNm」
 *   를 **직선**이라고 말해야 한다.
 * ★ `MAX_WALK_M` 은 **근거 없는 값**이다. 소방 호스 한 본 15m · 통상 연장 수 본을 넘는
 *   거리면 차량 접근이라고 부를 수 없다는 감으로 잡았다. D-30 인터뷰 항목이다.
 * ★ 순수하다. 그래프와 인접리스트만 받는다.
 */
import { distM, type LngLat } from "./geo";
import type { Adjacency } from "./graph";
import type { NaviGraph } from "./types";

/** 이보다 멀면 대체 접근 지점으로 치지 않는다(m, 직선). 근거 없음 — D-30 */
export const MAX_WALK_M = 300;

/** `from` 에서 닿는 노드 전부 (다익스트라 — 비용 순). */
export function reachable(adj: Adjacency, from: number): Map<number, number> {
  const g = new Map<number, number>([[from, 0]]);
  const done = new Set<number>();
  const open: [number, number][] = [[0, from]];
  while (open.length) {
    open.sort((a, b) => a[0] - b[0]);
    const [c, n] = open.shift()!;
    if (done.has(n)) continue;
    done.add(n);
    for (const { to, cost } of adj.get(n) ?? []) {
      const nc = c + cost;
      if (nc < (g.get(to) ?? Infinity)) { g.set(to, nc); open.push([nc, to]); }
    }
  }
  return g;
}

export interface Access {
  node: number;
  point: LngLat;
  /** 대체 접근 지점 → 사건 지점 직선 거리(m) */
  walkM: number;
}

/**
 * 닿는 노드 중 `target` 에 가장 가까운 것. 없거나 `maxWalkM` 밖이면 null.
 * @param reach `reachable()` 결과를 이미 가졌으면 넘긴다(두 번 펼치지 않게)
 */
export function alternateAccess(
  graph: NaviGraph, adj: Adjacency, from: number, target: LngLat,
  maxWalkM = MAX_WALK_M, reach?: Map<number, number>,
): Access | null {
  const r = reach ?? reachable(adj, from);
  let best: Access | null = null;
  for (const n of r.keys()) {
    const p = graph.nodes[n];
    if (!p) continue;
    const d = distM(p, target);
    if (d <= maxWalkM && (!best || d < best.walkM)) best = { node: n, point: p, walkM: d };
  }
  return best;
}

/** 출발점에서 닿는 **구간** 집합 — 관제 화면의 「도달 가능」 겹침이 쓴다 */
export function reachableEdges(graph: NaviGraph, adj: Adjacency, from: number): Set<string> {
  const r = reachable(adj, from);
  const out = new Set<string>();
  for (const n of r.keys()) {
    for (const { edge } of adj.get(n) ?? []) out.add(edge.seg_uid);
  }
  void graph;
  return out;
}

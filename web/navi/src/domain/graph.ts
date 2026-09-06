/**
 * domain/graph.ts — 인접리스트 · A* · 경로 파생값.
 *
 * `MASTER §20-5` 가 "하지 않았다" 고 남겨둔 자리를 닫는다.
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 */

import { distM, angleDelta, type LngLat } from "./geo";
import { edgeCost, requiredWidth, type TuningKnobs, TUNING } from "./vehicle";
import type { GraphEdge, NaviGraph, RoutePlan, VehicleSpec } from "./types";

interface Adj { to: number; cost: number; edge: GraphEdge }
export type Adjacency = Map<number, Adj[]>;
export type CostMode = "safe" | "fastest";

/**
 * 그래프를 A* 용 인접리스트로 굽는다. **한 번만 호출한다.**
 *
 * @param mode "fastest" 면 통행 가부는 그대로 보되 **비용을 실거리로** 쓴다.
 *   ★ "fastest" 라도 `blocked` 와 필요폭 미만은 막는다. 소방차가 못
 *     지나가는 길은 빠른 것이 아니라 못 가는 길이다.
 * ★ 자기루프(a===b)는 뺀다. `seg/graph.py` 가 버리는 것과 같다.
 */
export function buildAdjacency(
  graph: NaviGraph, spec: VehicleSpec, lenient = false,
  mode: CostMode = "safe", tuning: TuningKnobs = TUNING,
): Adjacency {
  const adj: Adjacency = new Map();
  for (const e of graph.edges) {
    if (e.a === e.b) continue;
    const penalized = edgeCost(
      spec, e.length_m, e.width_min_m, e.verdict, null, lenient, tuning);
    if (!Number.isFinite(penalized)) continue;
    const cost = mode === "fastest" ? (e.length_m ?? penalized) : penalized;
    for (const [from, to] of [[e.a, e.b], [e.b, e.a]] as const) {
      let list = adj.get(from);
      if (!list) adj.set(from, (list = []));
      list.push({ to, cost, edge: e });
    }
  }
  return adj;
}

/** 좌표에서 가장 가까운 통행가능 노드. */
export function nearestNode(graph: NaviGraph, adj: Adjacency, p: LngLat): number {
  let best = -1;
  let bd = Infinity;
  for (const n of adj.keys()) {
    const d = distM(graph.nodes[n], p);
    if (d < bd) { bd = d; best = n; }
  }
  return best;
}

/**
 * A*.
 *
 * ── 휴리스틱이 admissible 한 이유 ────────────────────────────────
 * `edgeCost` 의 배수 최솟값은 **1.0** 이다. 따라서 비용 ≥ 실거리이고
 * 직선거리를 그대로 휴리스틱으로 써도 과대추정하지 않는다.
 * ★ `TUNING` 에 1.0 미만 배수를 넣으면 이 성질이 깨진다(PLAN §4-2).
 *
 * ── ★ 진행방향을 기록한다 ───────────────────────────────────────
 * 2026-09-06. 주행거리가 앞뒤로 튀어 안내가 늦거나 이미 지나서 나왔다.
 * 원인은 **경로가 구간을 거꾸로 지나는 경우가 21%** 인데(측정: 경로 40개
 * 1,267구간 중 263) 스냅의 `progress` 는 구간 **형상** 시작점 기준이라
 * 역방향에서 0.2 가 실제로는 80% 지점이었다.
 *
 * 그래서 엣지별 진행방향(`forward`)을 경로에 실어 보낸다. 거리를 세는
 * 쪽이 전부 이것을 본다 — `progressAlongRoute` · `extractManeuvers`.
 */
export function findRoute(
  graph: NaviGraph, adj: Adjacency,
  startNode: number, goalNode: number, heuristic = true,
): RoutePlan | null {
  if (startNode < 0 || goalNode < 0) return null;
  const goal = graph.nodes[goalNode];
  const h = (n: number) => (heuristic ? distM(graph.nodes[n], goal) : 0);

  const g = new Map<number, number>([[startNode, 0]]);
  const from = new Map<number, { node: number; edge: GraphEdge }>();
  const done = new Set<number>();
  const open: { n: number; f: number }[] = [{ n: startNode, f: h(startNode) }];

  while (open.length) {
    open.sort((p, q) => p.f - q.f);
    const cur = open.shift()!;
    if (cur.n === goalNode) break;
    if (done.has(cur.n)) continue;
    done.add(cur.n);
    for (const { to, cost, edge } of adj.get(cur.n) ?? []) {
      if (done.has(to)) continue;
      const ng = (g.get(cur.n) ?? Infinity) + cost;
      if (ng < (g.get(to) ?? Infinity)) {
        g.set(to, ng);
        from.set(to, { node: cur.n, edge });
        open.push({ n: to, f: ng + h(to) });
      }
    }
  }
  if (!g.has(goalNode)) return null;

  const edges: GraphEdge[] = [];
  let cur = goalNode;
  while (cur !== startNode) {
    const step = from.get(cur);
    if (!step) return null;
    edges.unshift(step.edge);
    cur = step.node;
  }

  // 좌표 이어붙이기 + **진행방향 기록**.
  const coords: LngLat[] = [];
  const forward: boolean[] = [];
  const nodes: number[] = [startNode];
  const byVerdict: Record<string, number> = {};
  let node = startNode;
  let lengthM = 0;
  for (const e of edges) {
    const fwd = e.a === node;
    forward.push(fwd);
    const c = fwd ? e.coords : [...e.coords].reverse();
    for (let i = coords.length ? 1 : 0; i < c.length; i++) coords.push(c[i]);
    node = fwd ? e.b : e.a;
    nodes.push(node);
    const L = e.length_m ?? 0;
    lengthM += L;
    byVerdict[e.verdict] = (byVerdict[e.verdict] ?? 0) + L;
  }

  return {
    edges, forward, nodes, coords,
    cost: g.get(goalNode)!, lengthM, byVerdict,
  };
}

/** 경로 구간 집합. 스냅이 경로를 알게 하는 데 쓴다. */
export function routeUids(plan: RoutePlan): Set<string> {
  return new Set(plan.edges.map((e) => e.seg_uid));
}

/**
 * 경로 시작점부터 현재 위치까지 실제로 온 거리(m).
 *
 * ★ **진행방향을 본다.** 경로가 구간을 거꾸로 지나면 스냅의 `progress`
 *   를 뒤집어야 한다 — 21% 가 그런 구간이고, 안 뒤집으면 주행거리가
 *   앞뒤로 튀어 안내가 늦거나 이미 지나서 나온다(2026-09-06).
 *
 * ★ 경로 밖이면 null 이다. 이탈 중에는 남은 거리를 말하지 않는다.
 */
export function progressAlongRoute(
  plan: RoutePlan, current: { seg_uid: string; progress: number } | null,
): number | null {
  if (!current) return null;
  let acc = 0;
  for (let i = 0; i < plan.edges.length; i++) {
    const e = plan.edges[i];
    const L = e.length_m ?? 0;
    if (e.seg_uid === current.seg_uid) {
      const p = plan.forward[i] ? current.progress : 1 - current.progress;
      return acc + L * Math.max(0, Math.min(1, p));
    }
    acc += L;
  }
  return null;
}

/**
 * 현재 위치에서 `aheadM` 앞에 있는 구간.
 *
 * ★ 판정 안내를 **진입 전에** 하려고 있다. 회색 구간에 들어가 놓고
 *   "주행 중" 이라고 하면 운전자가 이미 결정을 내린 뒤라 쓸모가 없다.
 */
export function lookAhead(
  plan: RoutePlan, drivenM: number, aheadM: number,
): GraphEdge | null {
  const target = drivenM + aheadM;
  let acc = 0;
  for (const e of plan.edges) {
    const L = e.length_m ?? 0;
    if (acc + L > target) return acc > drivenM ? e : null;
    acc += L;
  }
  return null;
}

/**
 * 경로를 **하이브리드 경계**로 자른다.
 *
 * 폭 3.0m 이상 구간은 상용 도로망에 있고(1,101건 전량 대조: 89%), 그
 * 아래는 없다(23%). 경계값을 발명하지 않았다 — `requiredWidth(spec)` 과
 * 같은 숫자이고, 그것이 우연이 아니라는 것이 이 설계의 논거다.
 */
export function splitAtHybridBoundary(
  plan: RoutePlan, spec: VehicleSpec,
): { sdk: GraphEdge[][]; own: GraphEdge[][] } {
  const need = requiredWidth(spec);
  const sdk: GraphEdge[][] = [];
  const own: GraphEdge[][] = [];
  let run: GraphEdge[] = [];
  let wide: boolean | null = null;
  const flush = () => {
    if (run.length && wide !== null) (wide ? sdk : own).push(run);
    run = [];
  };
  for (const e of plan.edges) {
    const w = e.width_min_m != null && e.width_min_m >= need;
    if (wide !== null && w !== wide) flush();
    wide = w;
    run.push(e);
  }
  flush();
  return { sdk, own };
}

export { angleDelta };

/**
 * domain/graph.ts — 인접리스트 · A* · 경로 파생값.
 *
 * `MASTER §20-5` 가 "하지 않았다" 고 남겨둔 자리를 닫는다.
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 */

import { distM, angleDelta, MX, MY, type LngLat } from "./geo";
import { edgeCost, requiredWidth, type TuningKnobs, TUNING } from "./vehicle";
import { directionFactor, edgeIndex, routeRuleWarnings, turnBan, TURN_BAN_M } from "./rules";
import { tightTurn, TIGHT_TURN_M } from "./turning";
import type { GraphEdge, NaviGraph, RoutePlan, VehicleSpec } from "./types";

/** `idx` 는 `graph.edges` 인덱스 — 회전 금지가 인덱스로 적혀 있다 */
interface Adj { to: number; cost: number; edge: GraphEdge; idx: number }
export type Adjacency = Map<number, Adj[]>;
export type CostMode = "safe" | "fastest";

/** 인접리스트를 구운 차 — 코너 회전 점검(§218-2)이 전이마다 차를 알아야 한다 */
const ADJ_SPEC = new WeakMap<Adjacency, VehicleSpec>();
const TIGHT_CACHE = new WeakMap<Adjacency, Map<string, boolean>>();

/** 이 인접리스트의 차에게 `(들어온, 노드, 나갈)` 전이가 좁은 코너인가. 캐시한다 */
function isTight(graph: NaviGraph, adj: Adjacency, inIdx: number, node: number, outIdx: number): boolean {
  const spec = ADJ_SPEC.get(adj);
  if (!spec?.turn_check_radius_m) return false;
  let m = TIGHT_CACHE.get(adj);
  if (!m) TIGHT_CACHE.set(adj, (m = new Map()));
  const k = `${inIdx}|${node}|${outIdx}`;
  let v = m.get(k);
  if (v === undefined) m.set(k, (v = tightTurn(graph, spec, inIdx, node, outIdx) !== null));
  return v;
}

/** 인접리스트를 구운 차. 경고를 다시 셀 때 쓴다 */
export function adjacencySpec(adj: Adjacency): VehicleSpec | undefined {
  return ADJ_SPEC.get(adj);
}

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
  excluded?: ReadonlySet<string>,
): Adjacency {
  const adj: Adjacency = new Map();
  ADJ_SPEC.set(adj, spec);
  const index = edgeIndex(graph);
  for (const e of graph.edges) {
    if (e.a === e.b) continue;
    // ★ 2026-09-21 (와이어프레임 16·17). 현장에서 「통행 불가」로 신고한
    //   구간은 **그래프에서 뺀다.** 비용을 올리는 것이 아니다 — 올리면 다른
    //   길이 더 비쌀 때 그 구간으로 다시 안내한다. 사람이 막혔다고 말한
    //   길을 계산이 되살리면 안 된다.
    if (excluded?.has(e.seg_uid)) continue;
    const penalized = edgeCost(
      spec, e.length_m, e.width_min_m, e.verdict, null, lenient, tuning);
    if (!Number.isFinite(penalized)) continue;
    // ★ 안전 경로는 폭을 아는 확인 필요 구간을 피한다(`TuningKnobs.avoidUncertain`).
    //   연결성 우선(lenient)에서는 안 피한다 — 그 모드는 닿는 것이 먼저다.
    const avoid = mode === "safe" && !lenient && e.width_min_m != null
      && (e.verdict === "needs_cv" || e.verdict === "unknown") ? tuning.avoidUncertain : 1;
    const cost = mode === "fastest" ? (e.length_m ?? penalized) : penalized * avoid;
    const idx = index.get(e)!;
    // ★ 2026-09-22 (§215-1). 일방통행은 **방향마다** 값이 다르다. 두 모드 다 건다 —
    //   「빠른 길」 이 역주행이면 빠른 것이 아니라 어기는 것이다. 빼지는 않는다(rules.ts).
    for (const [from, to] of [[e.a, e.b], [e.b, e.a]] as const) {
      let list = adj.get(from);
      if (!list) adj.set(from, (list = []));
      list.push({ to, cost: cost * directionFactor(e, from === e.a), edge: e, idx });
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

// ── 구간 위 투영 (DECISIONS §218-3) ──────────────────────────────────────
//
// ★ 2026-09-22. 출발·도착을 가장 가까운 **노드**에 붙이면 구간 한가운데 선 사람이
//   교차점으로 옮겨진다. 웅토피아(DECISIONS §134)가 같은 결함으로 20m 를 1,172m 로
//   안내했다. 가장 가까운 **통행가능 구간**에 투영하고 부분 구간 비용을 셈에 넣는다.

/** 이보다 짧은 부분 구간(형상 m)은 노드 위에 선 것으로 본다 */
const NODE_EPS_M = 0.05;

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

const USABLE = new WeakMap<Adjacency, number[]>();

/** 인접리스트에 실린(= nearestNode 가 통행가능으로 보는) 구간 인덱스 */
function usableEdges(adj: Adjacency): number[] {
  let u = USABLE.get(adj);
  if (!u) {
    const s = new Set<number>();
    for (const list of adj.values()) for (const x of list) s.add(x.idx);
    USABLE.set(adj, (u = [...s].sort((p, q) => p - q)));
  }
  return u;
}

function geomLen(coords: LngLat[]): number {
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

/** 인접리스트가 이 구간의 한 방향에 매긴 비용(배수 · 일방통행 포함). 없으면 Infinity */
function dirCost(adj: Adjacency, e: GraphEdge, idx: number, forward: boolean): number {
  const [from, to] = forward ? [e.a, e.b] : [e.b, e.a];
  for (const x of adj.get(from) ?? []) if (x.idx === idx && x.to === to) return x.cost;
  return Infinity;
}

/**
 * 자른 사본의 선형 비율(a→b, 0~1) → 원본 구간 비율. 자르지 않은 구간은 그대로.
 * 스냅의 `progress` 는 원본 기준이라 둘을 오갈 때 쓴다.
 */
export function fullProgress(e: GraphEdge, f01: number): number {
  return e.clip ? e.clip.t0 + f01 * (e.clip.t1 - e.clip.t0) : f01;
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

  // ★ 2026-09-22 (§215-1). 상태는 **(노드, 들어온 엣지)** 다. 회전 금지는 「어느 길로
  //   와서 어느 길로 나가나」 에 걸리므로 노드만 상태로 두면 표현이 안 된다. 금지가 없는
  //   그래프에서는 결과가 노드 상태 A* 와 같다(같은 노드에 여러 상태가 생길 뿐 비용은 같다).
  type St = { n: number; via: number };
  const key = (s: St) => `${s.n}:${s.via}`;
  const start: St = { n: startNode, via: -1 };
  const g = new Map<string, number>([[key(start), 0]]);
  const from = new Map<string, { prev: St; edge: GraphEdge }>();
  const done = new Set<string>();
  const open: { s: St; f: number }[] = [{ s: start, f: h(startNode) }];
  let end: St | null = null;

  while (open.length) {
    open.sort((p, q) => p.f - q.f);
    const cur = open.shift()!;
    const ck = key(cur.s);
    if (done.has(ck)) continue;
    if (cur.s.n === goalNode) { end = cur.s; break; }
    done.add(ck);
    const base = g.get(ck) ?? Infinity;
    // ★ 되돌아가기 금지. 들어온 엣지의 반대쪽 노드로 곧장 돌아가는 전이는 안 연다.
    //   상태에 「들어온 엣지」 를 넣는 순간 「옆 구간으로 나갔다가 그대로 돌아오기」 가
    //   합법이 되고, 그것이 금지 회전 벌점(200m)보다 싸면 라우터가 **골목 한가운데 유턴**으로
    //   금지를 피했다 — 발행 그래프에서 금지 5건 중 3건(엣지 60 · 46 · 28m)이 그랬고 경고도
    //   없었다(독립 검토 2026-09-22). 소방차는 골목에서 유턴을 못 한다. 노드 상태 A* 에서는
    //   되돌아가기가 이득일 수 없었으므로 규칙이 없는 그래프의 결과는 그대로다.
    const back = cur.s.via >= 0 ? otherEnd(graph.edges[cur.s.via], cur.s.n) : -1;
    for (const { to, cost, edge, idx } of adj.get(cur.s.n) ?? []) {
      if (to === back) continue;
      const nx: St = { n: to, via: idx };
      const nk = key(nx);
      if (done.has(nk)) continue;
      const ban = cur.s.via >= 0 && turnBan(graph, cur.s.via, cur.s.n, idx) !== undefined;
      // ★ 좁은 코너(§218-2) — 제원 완성 차종만. 막지 않고 벌점(돌아갈 길이 있으면 그리로)
      const tight = cur.s.via >= 0 && isTight(graph, adj, cur.s.via, cur.s.n, idx);
      const ng = base + cost + (ban ? TURN_BAN_M : 0) + (tight ? TIGHT_TURN_M : 0);
      if (ng < (g.get(nk) ?? Infinity)) {
        g.set(nk, ng);
        from.set(nk, { prev: cur.s, edge });
        open.push({ s: nx, f: ng + h(to) });
      }
    }
  }
  if (!end) return null;

  const edges: GraphEdge[] = [];
  let st = end;
  while (st.n !== startNode || st.via !== -1) {
    const step = from.get(key(st));
    if (!step) return null;
    edges.unshift(step.edge);
    st = step.prev;
  }
  const total = g.get(key(end))!;

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
    cost: total, lengthM, byVerdict,
    rules: routeRuleWarnings(graph, { edges, forward, nodes }, ADJ_SPEC.get(adj)),
  };
}

function otherEnd(e: GraphEdge, n: number): number {
  return e.a === n ? e.b : e.a;
}

/** 경로의 한쪽 끝 — 노드 하나이거나 구간 위 투영점 */
export type RouteEnd = { node: number } | EdgeSnap;

/**
 * 좌표 → 좌표 경로. 출발·도착을 **구간에 투영**하고 부분 구간을 값에 넣는다(DECISIONS §218-3).
 * 통행가능 구간이 없거나 닿지 못하면 null.
 */
export function findRouteFromPoints(
  graph: NaviGraph, adj: Adjacency, from: LngLat, to: LngLat,
): RoutePlan | null {
  const s = snapToEdge(graph, adj, from);
  const g = snapToEdge(graph, adj, to);
  return s && g ? findRouteBetween(graph, adj, s, g) : null;
}

/**
 * `findRoute` 를 구간 위 끝점으로 넓힌 것.
 *
 * ── 어떻게 ──────────────────────────────────────────────────────
 * 출발 구간 E 의 **두 끝점**에서 A* 를 시작한다. 초기 비용 = 그 방향 인접리스트 비용 ×
 * 부분 비율 — 배수 · 일방통행(`directionFactor`)이 부분 구간에도 그대로 걸린다. 시작 상태의
 * 「들어온 엣지」 는 E 다 → 되돌아가기 금지 · 회전 금지 · 좁은 코너가 E 에서 나가는 전이에
 * `findRoute` 와 똑같이 걸린다. 도착 구간 G 는 두 끝점 어느 쪽에서든 들어가 투영점까지의
 * 부분 비용을 더하는 **가상 종점**으로 둔다(들어갈 때의 회전 규칙 포함). 같은 구간이면
 * 구간을 따라 곧장 가는 후보를 하나 더 둔다 — 역방향이면 역주행 배수가 붙어, 돌아가는
 * 길이 더 싸면 그리로 간다.
 *
 * ── 결과 ────────────────────────────────────────────────────────
 * 모양은 `findRoute` 와 같다. 첫 · 끝 엣지는 투영점에서 **자른 사본**(`GraphEdge.clip`)이라
 * `coords` 가 투영점에서 시작해 투영점에서 끝나고, `length_m` 합(= `lengthM`)에 부분만 들어간다.
 * 그래서 거리를 `length_m` 합으로 세는 쪽(진행 · 회전 · ETA · 시뮬레이션)이 고칠 것 없이 맞는다.
 * `nodes[0]` 은 첫 엣지의 (명목상) 시작 노드다 — 투영점 뒤쪽 끝점.
 */
export function findRouteBetween(
  graph: NaviGraph, adj: Adjacency, fromEnd: RouteEnd, toEnd: RouteEnd, heuristic = true,
): RoutePlan | null {
  type St = { n: number; via: number };
  const key = (s: St) => `${s.n}:${s.via}`;

  // ── 시작 상태 ────────────────────────────────────────────────
  const seeds: { s: St; g: number }[] = [];
  const S = "idx" in fromEnd ? fromEnd : null;
  if (S) {
    const e = S.edge, Lg = geomLen(e.coords);
    for (const fwd of [true, false]) {
      const part = fwd ? 1 - S.t : S.t;           // 가는 쪽 끝점까지 비율
      const n = fwd ? e.b : e.a;
      if (part * Lg < NODE_EPS_M) { seeds.push({ s: { n, via: -1 }, g: 0 }); continue; }
      const c = dirCost(adj, e, S.idx, fwd) * part;
      if (Number.isFinite(c)) seeds.push({ s: { n, via: S.idx }, g: c });
    }
  } else if ((fromEnd as { node: number }).node >= 0) {
    seeds.push({ s: { n: (fromEnd as { node: number }).node, via: -1 }, g: 0 });
  }
  if (!seeds.length) return null;

  // ── 가상 종점 ────────────────────────────────────────────────
  // guard ≥ 0 이면 구간 G 로 들어가는 전이다 — 회전 규칙이 걸린다. -1 이면 노드 도착
  type Goal = { n: number; extra: number; guard: number; t0: number; t1: number; fwd: boolean };
  const goals: Goal[] = [];
  const G = "idx" in toEnd ? toEnd : null;
  if (G) {
    const e = G.edge, Lg = geomLen(e.coords);
    for (const fwd of [true, false]) {
      const part = fwd ? G.t : 1 - G.t;           // 들어가는 끝점에서 투영점까지 비율
      const n = fwd ? e.a : e.b;
      if (part * Lg < NODE_EPS_M) { goals.push({ n, extra: 0, guard: -1, t0: 0, t1: 0, fwd }); continue; }
      const c = dirCost(adj, e, G.idx, fwd) * part;
      if (Number.isFinite(c)) {
        goals.push({ n, extra: c, guard: G.idx, t0: fwd ? 0 : G.t, t1: fwd ? G.t : 1, fwd });
      }
    }
  } else if ((toEnd as { node: number }).node >= 0) {
    goals.push({ n: (toEnd as { node: number }).node, extra: 0, guard: -1, t0: 0, t1: 0, fwd: true });
  }
  if (!goals.length) return null;

  const h = (n: number) => {
    if (!heuristic) return 0;
    let m = Infinity;
    for (const q of goals) m = Math.min(m, distM(graph.nodes[n], graph.nodes[q.n]));
    return m;
  };

  // ── 종점 후보: 같은 구간이면 구간을 따라 곧장 ───────────────────
  let best: { g: number; prev: St | null; goal: number } = { g: Infinity, prev: null, goal: -1 };
  let direct: { t0: number; t1: number; fwd: boolean } | null = null;
  if (S && G && S.idx === G.idx) {
    const fwd = G.t >= S.t;
    const c = dirCost(adj, S.edge, S.idx, fwd) * Math.abs(G.t - S.t);
    if (Number.isFinite(c)) {
      direct = { t0: Math.min(S.t, G.t), t1: Math.max(S.t, G.t), fwd };
      best = { g: c, prev: null, goal: -1 };
    }
  }

  const g = new Map<string, number>();
  const from = new Map<string, { prev: St; edge: GraphEdge }>();
  const done = new Set<string>();
  // term=true 는 가상 종점 항목이다. 꺼내면 끝난다(휴리스틱이 일관적이라 최적이다)
  const open: { s: St; f: number; term?: boolean }[] = [];
  for (const { s, g: g0 } of seeds) {
    if (g0 < (g.get(key(s)) ?? Infinity)) { g.set(key(s), g0); open.push({ s, f: g0 + h(s.n) }); }
  }
  if (direct) open.push({ s: { n: -1, via: -1 }, f: best.g, term: true });

  let finished = false;
  while (open.length) {
    open.sort((p, q) => p.f - q.f);
    const cur = open.shift()!;
    if (cur.term) {
      if (cur.f <= best.g) { finished = true; break; }
      continue;
    }
    const ck = key(cur.s);
    if (done.has(ck)) continue;
    done.add(ck);
    const base = g.get(ck) ?? Infinity;
    const back = cur.s.via >= 0 ? otherEnd(graph.edges[cur.s.via], cur.s.n) : -1;

    // 이 노드에서 도착 구간으로 들어가기
    goals.forEach((q, k) => {
      if (q.n !== cur.s.n) return;
      let ng = base + q.extra;
      if (q.guard >= 0) {
        if (cur.s.via === q.guard) return;            // 온 구간을 되돌아 들어가기 = 유턴
        if (cur.s.via >= 0 && turnBan(graph, cur.s.via, cur.s.n, q.guard) !== undefined) ng += TURN_BAN_M;
        if (cur.s.via >= 0 && isTight(graph, adj, cur.s.via, cur.s.n, q.guard)) ng += TIGHT_TURN_M;
      }
      if (ng < best.g) {
        best = { g: ng, prev: cur.s, goal: k };
        open.push({ s: cur.s, f: ng, term: true });
      }
    });

    for (const { to, cost, edge, idx } of adj.get(cur.s.n) ?? []) {
      if (to === back) continue;
      const nx: St = { n: to, via: idx };
      const nk = key(nx);
      if (done.has(nk)) continue;
      const ban = cur.s.via >= 0 && turnBan(graph, cur.s.via, cur.s.n, idx) !== undefined;
      const tight = cur.s.via >= 0 && isTight(graph, adj, cur.s.via, cur.s.n, idx);
      const ng = base + cost + (ban ? TURN_BAN_M : 0) + (tight ? TIGHT_TURN_M : 0);
      if (ng < (g.get(nk) ?? Infinity)) {
        g.set(nk, ng);
        from.set(nk, { prev: cur.s, edge });
        open.push({ s: nx, f: ng + h(to) });
      }
    }
  }
  if (!finished && !Number.isFinite(best.g)) return null;

  // ── 조각 모으기: (원본 엣지, 인덱스, 진행방향, 자를 비율) ─────────
  const index = edgeIndex(graph);
  type Piece = { e: GraphEdge; idx: number; fwd: boolean; clip: [number, number] | null };
  const pieces: Piece[] = [];
  if (best.prev === null && direct && S) {
    pieces.push({ e: S.edge, idx: S.idx, fwd: direct.fwd, clip: [direct.t0, direct.t1] });
  } else {
    const mid: Piece[] = [];
    let st = best.prev!;
    for (;;) {
      const step = from.get(key(st));
      if (!step) break;
      const idx = index.get(step.edge)!;
      mid.unshift({ e: step.edge, idx, fwd: step.edge.a === step.prev.n, clip: null });
      st = step.prev;
    }
    // 뿌리가 출발 구간 위 시작 상태면 그 부분을 앞에 붙인다
    if (S && st.via === S.idx) {
      const fwd = st.n === S.edge.b;
      pieces.push({ e: S.edge, idx: S.idx, fwd, clip: fwd ? [S.t, 1] : [0, S.t] });
    }
    pieces.push(...mid);
    const q = goals[best.goal];
    if (q && q.guard >= 0 && G) pieces.push({ e: G.edge, idx: G.idx, fwd: q.fwd, clip: [q.t0, q.t1] });
  }

  // ── RoutePlan 조립 ───────────────────────────────────────────
  const edges: GraphEdge[] = [];
  const forward: boolean[] = [];
  const coords: LngLat[] = [];
  const nodes: number[] = [];
  const byVerdict: Record<string, number> = {};
  let lengthM = 0;
  for (const p of pieces) {
    let e = p.e;
    if (p.clip) {
      const [t0, t1] = p.clip;
      const L = (e.length_m ?? geomLen(e.coords)) * (t1 - t0);
      e = { ...e, coords: clipCoords(e.coords, t0, t1), length_m: L, clip: { src: p.idx, t0, t1 } };
    }
    if (!nodes.length) nodes.push(p.fwd ? e.a : e.b);
    edges.push(e);
    forward.push(p.fwd);
    nodes.push(p.fwd ? e.b : e.a);
    const c = p.fwd ? e.coords : [...e.coords].reverse();
    for (let i = coords.length ? 1 : 0; i < c.length; i++) coords.push(c[i]);
    const L = e.length_m ?? 0;
    lengthM += L;
    byVerdict[e.verdict] = (byVerdict[e.verdict] ?? 0) + L;
  }
  if (!edges.length) {
    // 출발 = 도착(같은 노드 · 같은 점)
    const at = S?.point ?? G?.point ?? graph.nodes[seeds[0].s.n];
    coords.push(at);
    nodes.push(seeds[0].s.n);
  }

  return {
    edges, forward, nodes, coords,
    cost: best.g, lengthM, byVerdict,
    rules: routeRuleWarnings(graph, { edges, forward, nodes }, ADJ_SPEC.get(adj)),
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
      // 자른 사본(출발·도착 구간)이면 원본 비율을 사본 비율로 옮긴다
      const q = e.clip
        ? (e.clip.t1 > e.clip.t0 ? (current.progress - e.clip.t0) / (e.clip.t1 - e.clip.t0) : 0)
        : current.progress;
      const p = plan.forward[i] ? q : 1 - q;
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

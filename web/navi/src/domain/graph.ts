/**
 * domain/graph.ts — A*. 그리고 경로 계산의 **한 문**이다.
 *
 * `MASTER §20-5` 가 "하지 않았다" 고 남겨둔 자리를 닫는다.
 *
 * ── 왜 셋으로 갈랐나 (PLAN §1 #130) ─────────────────────────────
 * ★ 2026-09-25. 627줄로 길이 상한(600)을 넘었다. 한 파일이 네 가지 일을 했고 넷은
 *   서로 다른 이유로 바뀐다. 셋을 떼고 **길을 고르는 일만** 남겼다 —
 *
 *     `adjacency.ts`    인접리스트 굽기 · 차 기억 · 가까운 노드 · 방향별 비용
 *     `edgeSnap.ts`     구간 위 투영 · 형상 자르기 (§218-3)
 *     `routeDerive.ts`  다 난 경로에서 값 읽기 (주행거리 · 앞쪽 구간 · 경계 자르기)
 *
 * ★ **이름은 안 옮겼다.** 아래 재수출로 `domain/graph` 의 표면이 갈라기 전과 한 글자도
 *   같다 — 시험 여섯 파일과 화면 셋이 이 이름으로 읽는다. 새로 쓰는 쪽은 위 세 파일을
 *   직접 부르는 것이 낫다. 여기를 거치면 왜 그 함수가 있는지가 안 보인다.
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 *
 * IN    NaviGraph · Adjacency · 끝점(노드이거나 구간 위 투영점)
 * OUT   RoutePlan — 구간 목록 · 진행방향 · 좌표 · 비용 · 길이 · 판정별 길이 · 규칙 경고
 * 밖    통행 가부와 비용은 여기서 안 정한다(`adjacency.ts`). 화면·음성이 쓰는 파생값도
 *       여기 없다(`routeDerive.ts`).
 */

import { distM, angleDelta, type LngLat } from "./geo";
import { edgeIndex, routeRuleWarnings, turnBan, TURN_BAN_M } from "./rules";
import { TIGHT_TURN_M } from "./turning";
import {
  adjacencySpec, dirCost, isTight, type Adjacency,
} from "./adjacency";
import {
  clipCoords, geomLen, snapToEdge, NODE_EPS_M, type EdgeSnap,
} from "./edgeSnap";
import type { GraphEdge, NaviGraph, RoutePlan } from "./types";

// ── 갈라기 전 표면을 그대로 둔다 (위 머리말 참조) ─────────────────
export {
  adjacencySpec, buildAdjacency, dirCost, isTight, nearestNode, usableEdges,
  type Adjacency, type CostMode,
} from "./adjacency";
export {
  clipCoords, fullProgress, geomLen, snapToEdge, NODE_EPS_M, type EdgeSnap,
} from "./edgeSnap";
export {
  lookAhead, progressAlongRoute, routeUids, splitAtHybridBoundary,
} from "./routeDerive";

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
    rules: routeRuleWarnings(graph, { edges, forward, nodes }, adjacencySpec(adj)),
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
    rules: routeRuleWarnings(graph, { edges, forward, nodes }, adjacencySpec(adj)),
  };
}

export { angleDelta };

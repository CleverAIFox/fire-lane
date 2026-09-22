/**
 * test/pointRoute.test.ts — 출발·도착을 **구간에 투영**하는가 (PLAN §1 #50).
 *
 * 노드에 붙이면 구간 한가운데 선 차가 교차점으로 옮겨진다(웅토피아 DECISIONS §134 —
 * 20m 를 1,172m 로 안내). 합성 사각형으로 모양을 가르고, 실제 발행 그래프로 최적성과
 * 끝점 위치를 본다.
 */
import { FL, test, ok } from "./harness";
import {
  buildAdjacency, clipCoords, findRoute, findRouteBetween, findRouteFromPoints,
  nearestNode, progressAlongRoute, snapToEdge, type Adjacency,
} from "../src/domain/graph";
import { routeGeom } from "../src/domain/progress";
import { distM, type LngLat } from "../src/domain/geo";
import { WRONG_WAY } from "../src/domain/rules";
import type { GraphEdge, NaviGraph, RoutePlan } from "../src/domain/types";

const { spec } = FL;
const near = (a: number, b: number, eps = 1e-6) => Math.abs(a - b) <= eps;
const ids = (p: RoutePlan | null) => p?.edges.map((e) => e.seg_uid).join(",");

//   0 ──e0 100m── 1
//   │             │
//  e2 150m       e1 100m
//   │             │
//   3 ──e3 150m── 2
function square(over: Partial<Record<number, Partial<GraphEdge>>> = {}): NaviGraph {
  const nodes: [number, number][] = [[126.9, 35.15], [126.901, 35.15], [126.901, 35.149], [126.9, 35.149]];
  const mk = (i: number, a: number, b: number, L: number): GraphEdge => ({
    seg_uid: `e${i}`, verdict: "clear", width_min_m: 10, length_m: L,
    a, b, coords: [nodes[a], nodes[b]], ...over[i],
  });
  return {
    crs: "EPSG:4326", node_tol_m: 0.5, counts: { nodes: 4, edges: 4, self_loops: 0 },
    style: {}, nodes,
    edges: [mk(0, 0, 1, 100), mk(1, 1, 2, 100), mk(2, 0, 3, 150), mk(3, 3, 2, 150)],
    turns: [],
  };
}
/** 구간 i 의 형상 비율 t 지점 */
const on = (g: NaviGraph, i: number, t: number): LngLat => clipCoords(g.edges[i].coords, 0, t).at(-1)!;

test("투영 — 구간 · 비율 · 부분 길이", () => {
  const g = square();
  const s = snapToEdge(g, buildAdjacency(g, spec), on(g, 2, 0.3))!;
  ok(s.edge.seg_uid === "e2", `구간 ${s.edge.seg_uid}`);
  ok(near(s.t, 0.3, 1e-6) && near(s.toA_M, 45, 1e-4) && near(s.toB_M, 105, 1e-4), JSON.stringify(s));
  ok(s.distM < 1e-6, "구간 위 점인데 거리가 있다");
  // 신고로 뺀 구간에는 안 붙는다 — nearestNode 와 같은 기준
  const shut = buildAdjacency(g, spec, false, "safe", undefined, new Set(["e2"]));
  ok(snapToEdge(g, shut, on(g, 2, 0.3))!.edge.seg_uid !== "e2", "뺀 구간에 붙었다");
});

test("구간 한가운데 출발 — 교차점으로 옮기지 않고 부분 구간을 값에 넣는다", () => {
  const g = square();
  const adj = buildAdjacency(g, spec);
  // e2 의 0.45 지점(노드 0 이 더 가깝다) → 노드 2
  const from = on(g, 2, 0.45), to = g.nodes[2];
  const node = findRoute(g, adj, nearestNode(g, adj, from), nearestNode(g, adj, to))!;
  ok(ids(node) === "e0,e1", `노드 기준 ${ids(node)}`);     // 옛 결과: 노드 0 에서 출발한 척
  const p = findRouteFromPoints(g, adj, from, to)!;
  // 부분 e2(0.55×150) + e3 150 = 232.5 < 0.45×150 + 200 = 267.5
  ok(ids(p) === "e2,e3", `점 기준 ${ids(p)}`);
  ok(near(p.lengthM, 232.5, 1e-6) && near(p.cost, 232.5, 1e-6), `길이 ${p.lengthM} · 비용 ${p.cost}`);
  ok(p.forward.join() === "true,true", `방향 ${p.forward}`);
  ok(p.nodes.join() === "0,3,2", `노드 ${p.nodes}`);
  ok(distM(p.coords[0], from) < 0.01, "경로가 출발점에서 시작하지 않는다");
  ok(distM(p.coords.at(-1)!, to) < 0.01, "경로가 도착점에서 끝나지 않는다");
  ok(p.edges[0].clip?.src === 2 && near(p.edges[0].length_m!, 82.5, 1e-6), "첫 구간이 잘리지 않았다");
  ok(!p.edges[1].clip && p.edges[1] === g.edges[3], "중간 구간은 원본 그대로여야 한다");
  // 거리를 length_m 합으로 세는 쪽과 맞는가
  ok(near(routeGeom(p).totalM, p.lengthM, 1e-6), "routeGeom 총길이가 lengthM 과 다르다");
});

test("구간 한가운데 → 구간 한가운데 — 짧은 쪽 · 부분 두 개", () => {
  const g = square();
  const adj = buildAdjacency(g, spec);
  // e0 0.4 → e1 0.3 : 부분 60 + 부분 30 = 90. 노드 기준(0→1)은 100 이고 도착 부분을 모른다
  const p = findRouteFromPoints(g, adj, on(g, 0, 0.4), on(g, 1, 0.3))!;
  ok(ids(p) === "e0,e1" && near(p.lengthM, 90, 1e-6), `${ids(p)} ${p.lengthM}`);
  ok(p.edges.every((e) => e.clip), "두 끝 구간이 다 잘려야 한다");
  // 진행 — 스냅 progress 는 원본 구간 비율이다
  ok(near(progressAlongRoute(p, { seg_uid: "e0", progress: 0.4 })!, 0, 1e-9), "출발점 진행이 0 이 아니다");
  ok(near(progressAlongRoute(p, { seg_uid: "e0", progress: 0.7 })!, 30, 1e-9), "첫 구간 진행이 틀렸다");
  ok(near(progressAlongRoute(p, { seg_uid: "e1", progress: 0.15 })!, 75, 1e-9), "끝 구간 진행이 틀렸다");
});

test("같은 구간 안 — 구간을 따라 곧장 (양방향)", () => {
  const g = square();
  const adj = buildAdjacency(g, spec);
  const f = findRouteFromPoints(g, adj, on(g, 3, 0.2), on(g, 3, 0.7))!;
  ok(ids(f) === "e3" && f.forward[0] === true && near(f.lengthM, 75, 1e-6), `${ids(f)} ${f.forward} ${f.lengthM}`);
  ok(distM(f.coords[0], on(g, 3, 0.2)) < 0.01 && distM(f.coords.at(-1)!, on(g, 3, 0.7)) < 0.01, "끝점");
  const b = findRouteFromPoints(g, adj, on(g, 3, 0.7), on(g, 3, 0.2))!;
  ok(ids(b) === "e3" && b.forward[0] === false && near(b.lengthM, 75, 1e-6), `${ids(b)} ${b.forward} ${b.lengthM}`);
  ok(distM(b.coords[0], on(g, 3, 0.7)) < 0.01, "역방향 경로가 출발점에서 시작하지 않는다");
  ok(!b.rules.length, "양방향 구간인데 규칙 경고가 있다");
});

test("일방통행 — 출발 부분 구간에도 방향 배수가 걸린다", () => {
  // e3 은 3→2 로만. e3 의 0.9 지점에서 e2 의 0.9 지점(노드 3 근처)으로
  const from = (g: NaviGraph) => on(g, 3, 0.9), to = (g: NaviGraph) => on(g, 2, 0.9);
  const two = square();
  const p2 = findRouteFromPoints(two, buildAdjacency(two, spec), from(two), to(two))!;
  // 양방향이면 뒤로 135 + 15 = 150
  ok(ids(p2) === "e3,e2" && p2.forward.join() === "false,false" && near(p2.lengthM, 150, 1e-6),
     `양방향 ${ids(p2)} ${p2.forward} ${p2.lengthM}`);
  const one = square({ 3: { ow: 1 } });
  const p1 = findRouteFromPoints(one, buildAdjacency(one, spec), from(one), to(one))!;
  // 역주행 135×4 + 15 = 555 > 앞으로 15 + 100 + 100 + 135 = 350
  ok(ids(p1) === "e3,e1,e0,e2" && p1.forward[0] === true, `일방 ${ids(p1)} ${p1.forward}`);
  ok(near(p1.cost, 350, 1e-6) && near(p1.lengthM, 350, 1e-6), `비용 ${p1.cost} · 길이 ${p1.lengthM}`);
  ok(!p1.rules.some((w) => w.kind === "wrong_way"), "역주행하지 않는데 경고가 있다");
});

test("일방통행 · 같은 구간 — 역주행이 제일 싸면 지나며 경고한다(빼지 않는다)", () => {
  const g = square({ 3: { ow: 1 } });
  const p = findRouteFromPoints(g, buildAdjacency(g, spec), on(g, 3, 0.7), on(g, 3, 0.2))!;
  // 역주행 75×4 = 300 < 돌아가기 45 + 100 + 100 + 150 + 30 = 425
  ok(ids(p) === "e3" && p.forward[0] === false, `${ids(p)} ${p.forward}`);
  ok(near(p.cost, 75 * WRONG_WAY, 1e-6) && near(p.lengthM, 75, 1e-6), `비용 ${p.cost}`);
  ok(p.rules.some((w) => w.kind === "wrong_way"), "역주행인데 경고가 없다");
  // e3 을 길게 하면(역주행 비용 > 돌아가기) 돌아간다
  const long = square({ 3: { ow: 1, length_m: 400 } });
  const q = findRouteFromPoints(long, buildAdjacency(long, spec), on(long, 3, 0.7), on(long, 3, 0.2))!;
  ok(ids(q) === "e3,e1,e0,e2,e3", `긴 일방 ${ids(q)}`);
  ok(!q.rules.some((w) => w.kind === "wrong_way"), "돌아가는데 역주행 경고가 있다");
});

test("노드 끝점과 섞어 쓴다 — 대체 접근 지점(§214-2) 경로", () => {
  const g = square();
  const adj = buildAdjacency(g, spec);
  const s = snapToEdge(g, adj, on(g, 0, 0.5))!;
  const p = findRouteBetween(g, adj, s, { node: 2 })!;
  ok(ids(p) === "e0,e1" && near(p.lengthM, 150, 1e-6), `${ids(p)} ${p.lengthM}`);
  ok(p.nodes.at(-1) === 2 && distM(p.coords.at(-1)!, g.nodes[2]) < 0.01, "노드에서 끝나지 않는다");
  // 노드 → 노드는 findRoute 와 같다
  const n = findRouteBetween(g, adj, { node: 0 }, { node: 2 })!;
  const r = findRoute(g, adj, 0, 2)!;
  ok(ids(n) === ids(r) && near(n.cost, r.cost) && near(n.lengthM, r.lengthM), "노드 끝점이 findRoute 와 다르다");
});

// ── 실제 발행 그래프 ──────────────────────────────────────────────
test("실제 그래프 — 구간 위 점 경로가 끝점에 붙고, 노드 경로 + 부분 구간보다 비싸지 않다", () => {
  const g = FL.graph;
  const adj: Adjacency = buildAdjacency(g, spec);
  const usable = [...new Set([...adj.values()].flat().map((x) => x.idx))].sort((a, b) => a - b);
  // 결정적 표본 — 구간 24개의 0.37 지점
  const pts: { p: LngLat; idx: number }[] = [];
  for (let k = 0; k < usable.length && pts.length < 24; k += Math.max(1, Math.floor(usable.length / 24))) {
    const i = usable[k];
    pts.push({ p: on(g, i, 0.37), idx: i });
  }
  const dir = (e: GraphEdge, idx: number, fwd: boolean) =>
    adj.get(fwd ? e.a : e.b)!.find((x) => x.idx === idx && x.to === (fwd ? e.b : e.a))!.cost;

  let n = 0, shorter = 0, worse = 0;
  for (let i = 0; i < pts.length; i++) {
    for (let j = 0; j < pts.length; j++) {
      if (i === j) continue;
      const A = pts[i], B = pts[j];
      const r = findRouteFromPoints(g, adj, A.p, B.p);
      const S = snapToEdge(g, adj, A.p)!, T = snapToEdge(g, adj, B.p)!;
      // 기준: 출발 구간 끝점 X · 도착 구간 끝점 Y 네 조합의 (부분 + 노드 경로 + 부분) 최소
      let ref = Infinity;
      for (const xf of [true, false]) for (const yf of [true, false]) {
        const X = xf ? S.edge.b : S.edge.a, Y = yf ? T.edge.a : T.edge.b;
        const mid = findRoute(g, adj, X, Y);
        if (!mid) continue;
        const c = dir(S.edge, S.idx, xf) * (xf ? 1 - S.t : S.t) + mid.cost
          + dir(T.edge, T.idx, yf) * (yf ? T.t : 1 - T.t);
        ref = Math.min(ref, c);
      }
      if (!Number.isFinite(ref)) { ok(!r, "노드로 못 닿는데 점 경로가 섰다"); continue; }
      ok(r, `점 경로가 안 섰다 (${A.idx} → ${B.idx})`);
      n++;
      ok(distM(r.coords[0], A.p) < 1, `출발점에서 ${distM(r.coords[0], A.p).toFixed(2)}m 떨어져 시작한다`);
      ok(distM(r.coords.at(-1)!, B.p) < 1, `도착점에서 ${distM(r.coords.at(-1)!, B.p).toFixed(2)}m 떨어져 끝난다`);
      ok(near(routeGeom(r).totalM, r.lengthM, 1e-6), "routeGeom 총길이가 lengthM 과 다르다");
      ok(r.nodes.length === r.edges.length + 1 && r.forward.length === r.edges.length, "모양이 findRoute 와 다르다");
      // 부분 구간에서 나가는 첫 전이의 회전 금지 벌점(200m)만큼은 기준이 모른다 — 그 이상 비싸면 결함
      if (r.cost > ref + 1e-6) worse++;
      ok(r.cost <= ref + 200 + 1e-6, `점 경로 비용 ${r.cost.toFixed(1)} > 기준 ${ref.toFixed(1)}`);
      // 옛 방식(가장 가까운 노드 ↔ 노드)과 길이 비교
      const old = findRoute(g, adj, nearestNode(g, adj, A.p), nearestNode(g, adj, B.p));
      if (old && r.lengthM < old.lengthM - 1) shorter++;
    }
  }
  ok(n > 300, `비교한 쌍이 ${n} — 표본이 너무 적다`);
  ok(worse === 0, `기준보다 비싼 점 경로 ${worse}건`);
  console.info(`점 경로 ${n}쌍 · 옛 노드 경로보다 1m 넘게 짧은 것 ${shorter}쌍`);
});

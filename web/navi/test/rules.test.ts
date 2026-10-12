/**
 * test/rules.test.ts — 통행 규칙(일방통행 · 회전 금지)이 비용과 경고로 옮겨지는가.  (DECISIONS §215-1)
 *
 * 합성 사각형 하나와 실제 발행 그래프를 같이 본다. 합성만으로는 발행물에 규칙이 실렸는지
 * 모르고, 실제 그래프만으로는 금지 회전을 **피하는지** 가를 수 없다(우회가 있는지 모른다).
 */
import { FL, test, ok } from "./harness";
import { buildAdjacency, findRoute, type Adjacency } from "../src/domain/graph";
import {
  directionFactor, edgeIndex, isWrongWay, nextRule, routeRuleWarnings,
  ruleSummary, rulePhrase, turnBan, TURN_BAN_WORD,
  WRONG_WAY, ONEWAY_UNKNOWN, TURN_BAN_M,
} from "../src/domain/rules";
import type { GraphEdge, NaviGraph } from "../src/domain/types";

const { spec } = FL;

//   0 ──e0 100m── 1
//   │             │
//  e2 150m       e1 100m
//   │             │
//   3 ──e3 150m── 2
function square(over: Partial<Record<number, Partial<GraphEdge>>> = {},
                turns: NaviGraph["turns"] = []): NaviGraph {
  const nodes: [number, number][] = [[126.9, 35.15], [126.901, 35.15], [126.901, 35.149], [126.9, 35.149]];
  const mk = (i: number, a: number, b: number, L: number): GraphEdge => ({
    seg_uid: `e${i}`, verdict: "clear", width_min_m: 10, length_m: L,
    a, b, coords: [nodes[a], nodes[b]], ...over[i],
  });
  return {
    crs: "EPSG:4326", node_tol_m: 0.5, counts: { nodes: 4, edges: 4, self_loops: 0 },
    style: {}, nodes,
    edges: [mk(0, 0, 1, 100), mk(1, 1, 2, 100), mk(2, 0, 3, 150), mk(3, 3, 2, 150)],
    turns,
  };
}
const ids = (g: NaviGraph, adj: Adjacency, a: number, b: number) =>
  findRoute(g, adj, a, b)?.edges.map((e) => e.seg_uid).join(",");

test("규칙 없는 사각형 — 짧은 쪽(e0,e1)", () => {
  const g = square();
  ok(ids(g, buildAdjacency(g, spec), 0, 2) === "e0,e1", "최단을 안 골랐다");
});

test("금지 회전은 우회가 싸면 피하고, 우회가 없으면 지나며 경고한다", () => {
  const g = square({}, [[0, 1, 1, 101]]);           // e0 로 와서 1 에서 e1 로 = 좌회전 금지
  const adj = buildAdjacency(g, spec);
  ok(ids(g, adj, 0, 2) === "e2,e3", "200 + 200 > 300 인데 금지 회전을 탔다");
  // 우회로를 막으면 금지 회전으로라도 간다 — 빼지 않는다(사용자 결정)
  const shut = buildAdjacency(g, spec, false, "safe", undefined, new Set(["e2"]));
  const p = findRoute(g, shut, 0, 2);
  ok(p && p.edges.map((e) => e.seg_uid).join() === "e0,e1", "우회로가 없는데 경로를 안 냈다");
  ok(p.rules.some((w) => w.kind === "turn_ban" && w.text === "좌회전 금지"), "금지 회전을 지나는데 경고가 없다");
  ok(Math.abs(p.cost - (200 + TURN_BAN_M)) < 1e-6, `비용 ${p.cost} — 회전 벌점이 안 붙었다`);
});

test("금지 회전을 골목 유턴으로 피하지 않는다 — 발행 그래프의 금지 전부 (독립 검토 2026-09-22)", () => {
  const g = FL.graph;
  const adj = buildAdjacency(g, spec);
  for (const [i, n, o] of g.turns ?? []) {
    const ei = g.edges[i], eo = g.edges[o];
    const from = ei.a === n ? ei.b : ei.a, to = eo.a === n ? eo.b : eo.a;
    const p = findRoute(g, adj, from, to);
    if (!p) continue;
    for (let k = 1; k < p.nodes.length - 1; k++) {
      ok(p.nodes[k - 1] !== p.nodes[k + 1], `금지 [${i},${n},${o}] 경로가 노드 ${p.nodes[k]} 에서 되돌아간다`);
    }
    const uses = p.edges.some((e, k) => k > 0 && p.edges[k - 1] === ei && e === eo);
    ok(!uses || p.rules.some((w) => w.kind === "turn_ban"), "금지 회전을 지나는데 경고가 없다");
  }
});

test("반대로 지나는 회전(e1→e0)은 금지 규칙이 아니다", () => {
  const g = square({}, [[0, 1, 1, 101]]);
  const p = findRoute(g, buildAdjacency(g, spec), 2, 0)!;
  ok(p.edges.map((e) => e.seg_uid).join() === "e1,e0", "규칙은 방향이 있다 — 반대 회전까지 막았다");
  ok(!p.rules.length, "반대 회전에 경고를 냈다");
});

test("알려진 일방통행 — 정방향은 그대로, 역방향만 불리하고 경고는 역주행", () => {
  const e: GraphEdge = { seg_uid: "x", verdict: "clear", width_min_m: 10, length_m: 100, a: 0, b: 1, coords: [], ow: 1 };
  ok(directionFactor(e, true) === 1 && directionFactor(e, false) === WRONG_WAY, "배수가 방향을 안 본다");
  // e1 을 2→1 로만 갈 수 있게 — 0→2 는 e1 을 역주행해야 짧다
  const g = square({ 1: { ow: -1 } });
  const adj = buildAdjacency(g, spec);
  ok(ids(g, adj, 0, 2) === "e2,e3", "100 + 400 > 300 인데 역주행을 골랐다");
  const p = findRoute(g, adj, 2, 0)!;
  ok(p.edges[0].seg_uid === "e1" && !p.rules.length, "정방향 일방통행에 경고를 냈다");
  const shut = buildAdjacency(g, spec, false, "safe", undefined, new Set(["e3"]));
  const q = findRoute(g, shut, 0, 2)!;
  ok(q.rules.some((w) => w.kind === "wrong_way"), "역주행으로만 닿는데 경고가 없다");
});

test("방향 모름 — 양쪽 다 조금 불리하고 역주행이라 말하지 않는다", () => {
  const e: GraphEdge = { seg_uid: "x", verdict: "clear", width_min_m: 10, length_m: 100, a: 0, b: 1, coords: [], ow: 2 };
  ok(directionFactor(e, true) === ONEWAY_UNKNOWN && directionFactor(e, false) === ONEWAY_UNKNOWN, "한쪽만 불리하다");
  const g = square({ 0: { ow: 2 }, 1: { ow: 2 } });
  const p = findRoute(g, buildAdjacency(g, spec), 0, 2)!;
  // 150 + 150 = 300 = e2+e3 → 동률. 어느 쪽이든 경고는 한 번만
  if (p.edges[0].seg_uid === "e0") {
    const ws = p.rules.filter((w) => w.kind === "oneway_unknown");
    ok(ws.length === 1, `연속한 일방통행 두 구간을 ${ws.length}번 셌다`);
    ok(!rulePhrase(ws[0]).includes("역주행"), "방향을 모르는데 역주행이라 말한다");
  }
});

test("다가오는 규칙 — 지난 것은 안 보고, 먼 것은 아직 안 말한다", () => {
  const ws = [{ kind: "turn_ban" as const, atM: 100, seg_uid: "a", text: "좌회전 금지" },
              { kind: "oneway_unknown" as const, atM: 400, seg_uid: "b", text: "" }];
  ok(nextRule(ws, 0, 150)?.atM === 100, "150m 안의 규칙을 못 봤다");
  ok(nextRule(ws, 120, 150) === null, "280m 앞을 150m 안이라고 봤다");
  ok(nextRule(ws, 300, 150)?.atM === 400, "지난 규칙에 걸렸다");
  ok(ruleSummary(ws) === "일방통행 1곳(방향 미확인) · 회전 금지 1곳", `요약 ${ruleSummary(ws)}`);
  ok(ruleSummary([]) === null, "규칙이 없는데 요약을 냈다");
});

test("발행 그래프 — 일방통행 · 회전 금지가 실렸고, 경로의 경고가 경로와 맞다", () => {
  const g = FL.graph;
  const ow = g.edges.filter((e) => e.ow);
  ok(ow.length > 20, `일방통행 ${ow.length}구간 — 발행이 규칙을 안 실었다`);
  ok((g.turns ?? []).length > 0, "회전 금지가 0건 — 발행이 규칙을 안 실었다");
  for (const [i, n, o] of g.turns ?? []) {
    const ei = g.edges[i], eo = g.edges[o];
    ok(ei && eo && [ei.a, ei.b].includes(n) && [eo.a, eo.b].includes(n), `회전 금지 [${i},${n},${o}] 가 노드에 안 닿는다`);
  }
  const adj = buildAdjacency(g, spec);
  const nodes = [...adj.keys()].sort((a, b) => a - b);
  let seen = 0;
  for (let i = 0; i < nodes.length; i += 97) {
    for (let j = nodes.length - 1; j > i; j -= 131) {
      const p = findRoute(g, adj, nodes[i], nodes[j]);
      if (!p) continue;
      const again = routeRuleWarnings(g, p);
      ok(JSON.stringify(again) === JSON.stringify(p.rules), "경로가 든 경고와 다시 센 경고가 다르다");
      seen += p.rules.length;
    }
  }
  ok(seen > 0, "표본 경로 어디에도 규칙이 안 걸렸다 — 표본이 좁거나 규칙이 안 먹는다");
});


// ── 2026-10-12 (DECISIONS §482) ────────────────────────────────────
//   `navicov` 가 이 파일의 세 함수를 「시험이 이름으로도 안 부른다」로 셌다 —
//   `isWrongWay` · `turnBan` · `edgeIndex`. 셋 다 **경고가 나가는 길목**이다.

test("역주행 — 방향 모름(2)은 역주행이 아니다. 발행물 57구간 중 56이 그것이다", () => {
  const g = square({ 0: { ow: 1 }, 1: { ow: -1 }, 2: { ow: 2 } });
  const [e0, e1, e2, e3] = g.edges;
  ok(isWrongWay(e0, false) && !isWrongWay(e0, true), "ow=1 은 뒤로 갈 때만 역주행이다");
  ok(isWrongWay(e1, true) && !isWrongWay(e1, false), "ow=-1 은 앞으로 갈 때 역주행이다");
  // ★ 여기가 본체다. 모름을 역주행으로 세면 **56구간에서 화면이 소리친다** —
  //   그러면 사람이 그 경고를 끄고, 끈 경고는 진짜 1구간도 못 말한다.
  ok(!isWrongWay(e2, true) && !isWrongWay(e2, false), "방향 모름을 역주행이라고 말한다");
  ok(!isWrongWay(e3, true) && !isWrongWay(e3, false), "규칙이 없는 구간을 역주행이라 말한다");
});

test("역주행 판정과 비용 배수가 **같은 것을 말한다**", () => {
  // ★ 둘은 다른 함수이고 같은 사실을 말한다. 한쪽만 고치면 비용은 올리면서
  //   경고는 안 하거나(조용한 역주행), 그 반대가 된다.
  const g = square({ 0: { ow: 1 }, 1: { ow: -1 }, 2: { ow: 2 } });
  for (const e of g.edges) {
    for (const fwd of [true, false]) {
      ok(isWrongWay(e, fwd) === (directionFactor(e, fwd) === WRONG_WAY),
        `${e.seg_uid} forward=${fwd} — 경고와 배수가 어긋난다`);
    }
  }
  ok(directionFactor(g.edges[2], true) === ONEWAY_UNKNOWN, "모름의 배수가 틀렸다");
});

test("금지 회전 조회 — 등재된 쌍만 답하고, 그래프마다 따로 센다", () => {
  const g = square({}, [[0, 1, 1, 101]]);
  ok(turnBan(g, 0, 1, 1) === 101, "등재된 금지 회전을 못 찾는다");
  ok(turnBan(g, 1, 1, 0) === undefined, "반대 방향까지 금지라고 말한다");
  ok(turnBan(g, 0, 2, 1) === undefined, "엉뚱한 노드에서도 금지라고 말한다");
  // ★ 캐시가 그래프를 열쇠로 든다. 전역이면 **다른 그래프가 앞의 답을 받는다**
  const empty = square({}, []);
  ok(turnBan(empty, 0, 1, 1) === undefined, "회전 금지가 없는 그래프가 옆 그래프의 답을 받는다");
  ok(turnBan(g, 0, 1, 1) === 101, "두 번째 호출에서 답이 달라졌다 — 캐시가 깨졌다");
});

test("금지 회전 문구 — 발행물에 있는 TURN_TYPE 은 **전부 말을 갖는다**", () => {
  const { graph } = FL;
  const kinds = new Set((graph.turns ?? []).map(([, , , ty]) => ty));
  ok(kinds.size > 0, "발행물에 금지 회전이 없다 — 이 시험의 전제가 깨졌다");
  for (const ty of kinds) {
    ok(TURN_BAN_WORD[ty], `TURN_TYPE ${ty} 에 문구가 없다 — 화면이 빈 말을 한다`);
  }
});

test("엣지 색인 — `turns` 가 인덱스로 적혀 있어 이것이 그 다리다", () => {
  const { graph } = FL;
  const idx = edgeIndex(graph);
  ok(idx.size === graph.edges.length, `색인 ${idx.size} ≠ 엣지 ${graph.edges.length}`);
  for (const i of [0, 1, 7, graph.edges.length - 1]) {
    ok(idx.get(graph.edges[i]) === i, `엣지 ${i} 의 색인이 틀렸다`);
  }
  ok(edgeIndex(graph) === idx, "두 번째 호출이 표를 다시 만든다 — 캐시가 안 든다");
  // ★ 발행물의 금지 회전이 **그 다리를 건널 수 있는가.** 못 건너면 금지가 조용하다
  for (const [i, , o] of graph.turns ?? []) {
    ok(idx.get(graph.edges[i]) === i && idx.get(graph.edges[o]) === o,
      `금지 회전이 가리키는 엣지 ${i}·${o} 를 색인이 못 찾는다`);
  }
});

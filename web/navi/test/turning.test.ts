/**
 * test/turning.test.ts — 좁은 코너는 제원 완성 차종에게만, 막지 않고 비용 · 경고로.  (DECISIONS §218-2)
 */
import { FL, test, ok } from "./harness";
import { buildAdjacency, findRoute } from "../src/domain/graph";
import { cornerRadiusMax, deflection, tightTurn, TIGHT_TURN_M } from "../src/domain/turning";
import { routeRuleWarnings } from "../src/domain/rules";
import type { GraphEdge, NaviGraph, VehicleSpec } from "../src/domain/types";

const PUMP: VehicleSpec = { ...FL.spec, width_m: 2.5, turn_check_radius_m: 7.3 };
const NOCHK: VehicleSpec = { ...FL.spec, width_m: 2.5, turn_check_radius_m: null };

test("모형 — 90° · 폭 5m 는 펌프차가 돌고 4m 는 못 돈다", () => {
  const need = 7.3 - 2.5 / 2;
  ok(Math.abs(cornerRadiusMax(5, 2.5, 90)! - 8.536) < 0.01, "R_max(5m, 90°) 가 8.54 가 아니다");
  ok(cornerRadiusMax(5, 2.5, 90)! >= need, "5m 코너를 못 돈다고 했다");
  ok(cornerRadiusMax(4, 2.5, 90)! < need, "4m 코너를 돈다고 했다");
  ok(cornerRadiusMax(3, 2.5, 10) === Infinity, "완만한 꺾임(10°)을 코너로 봤다");
  ok(cornerRadiusMax(null, 2.5, 90) === null, "폭을 모르는데 점검했다");
});

//  0 ──e0 (폭 4m, 60m)── 1
//                         │ e1 (폭 4m, 60m)  ← 1 에서 90° 꺾임
//  3 ──e3 (폭 8m)──────── 2      0→3→2 는 폭 8m 로 돌아간다(e2 · e3)
function L(): NaviGraph {
  const nodes: [number, number][] = [[126.9, 35.15], [126.90066, 35.15], [126.90066, 35.14946], [126.9, 35.14946]];
  const mk = (i: number, a: number, b: number, w: number, len: number): GraphEdge => ({
    seg_uid: `e${i}`, verdict: "clear", width_min_m: w, length_m: len, a, b, coords: [nodes[a], nodes[b]] });
  return { crs: "EPSG:4326", node_tol_m: 0.5, counts: { nodes: 4, edges: 4, self_loops: 0 }, style: {}, nodes,
    edges: [mk(0, 0, 1, 4, 60), mk(1, 1, 2, 4, 60), mk(2, 0, 3, 8, 60), mk(3, 3, 2, 8, 120)] };
}

test("좁은 코너는 우회가 있으면 피하고, 제원 미완성 차는 그대로 간다", () => {
  const g = L();
  ok(Math.abs(deflection(g.edges[0], 1, g.edges[1])! - 90) < 1, "꺾임각이 90° 가 아니다");
  ok(tightTurn(g, PUMP, 0, 1, 1) !== null, "4m 직각 코너를 넉넉하다고 봤다");
  const p = findRoute(g, buildAdjacency(g, PUMP), 0, 2)!;
  ok(p.edges.map((e) => e.seg_uid).join() === "e2,e3", `펌프차가 좁은 코너(120m)를 탔다 — ${p.edges.map((e) => e.seg_uid)}`);
  const q = findRoute(g, buildAdjacency(g, NOCHK), 0, 2)!;
  ok(q.edges.map((e) => e.seg_uid).join() === "e0,e1", "제원 미완성 차까지 코너를 점검했다");
  ok(!q.rules.some((w) => w.kind === "tight_turn"), "점검 안 하는 차에 좁은 코너 경고를 냈다");
  // 우회를 막으면 좁은 코너로라도 간다 — 막지 않는다
  const shut = buildAdjacency(g, PUMP, false, "safe", undefined, new Set(["e3"]));
  const r = findRoute(g, shut, 0, 2)!;
  ok(r.edges.map((e) => e.seg_uid).join() === "e0,e1", "우회가 없는데 경로를 안 냈다");
  ok(r.rules.some((w) => w.kind === "tight_turn"), "좁은 코너를 지나는데 경고가 없다");
  ok(Math.abs(r.cost - (120 + TIGHT_TURN_M)) < 1e-6, `비용 ${r.cost} — 코너 벌점이 안 붙었다`);
});

test("발행 그래프 — 펌프차 · 물탱크차 경로의 경고가 경로와 맞고, 물탱크차가 더 자주 걸린다", () => {
  const g = FL.graph;
  const tank: VehicleSpec = { ...PUMP, turn_check_radius_m: 11.2 };
  let nPump = 0, nTank = 0, seen = 0;
  const adjP = buildAdjacency(g, PUMP), adjT = buildAdjacency(g, tank);
  const nodes = [...adjP.keys()].sort((a, b) => a - b);
  for (let i = 0; i < nodes.length; i += 97) {
    for (let j = nodes.length - 1; j > i; j -= 131) {
      const p = findRoute(g, adjP, nodes[i], nodes[j]);
      const t = findRoute(g, adjT, nodes[i], nodes[j]);
      if (!p || !t) continue;
      seen++;
      ok(JSON.stringify(routeRuleWarnings(g, p, PUMP)) === JSON.stringify(p.rules), "경로가 든 경고와 다시 센 경고가 다르다");
      nPump += p.rules.filter((w) => w.kind === "tight_turn").length;
      nTank += t.rules.filter((w) => w.kind === "tight_turn").length;
    }
  }
  ok(seen > 20, `표본 경로 ${seen} — 너무 적다`);
  ok(nTank >= nPump, `물탱크차(11.2m) 경고 ${nTank} < 펌프차(7.3m) ${nPump} — 반경이 클수록 코너가 좁아야 한다`);
});

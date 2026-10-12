/**
 * test/turning.test.ts — 좁은 코너는 제원 완성 차종에게만, 막지 않고 비용 · 경고로.  (DECISIONS §218-2)
 */
import { FL, test, ok } from "./harness";
import { buildAdjacency, findRoute } from "../src/domain/graph";
import {
  cornerRadiusMax, cornerWidth, deflection, MIN_DEFLECTION, tightTurn,
  TIGHT_TURN_M, turnCheckRadius,
} from "../src/domain/turning";
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


// ── 2026-10-12 (DECISIONS §483) ────────────────────────────────────
//   `navicov` 가 이 파일의 둘을 「시험이 이름으로도 안 부른다」로 셌다 —
//   `turnCheckRadius` · `cornerWidth`. 둘 다 **점검을 켜고 끄는 자리**다.

test("점검 대상인가 — 제원 완성 차종만. 실물 제원은 **아직 아니다**", () => {
  ok(turnCheckRadius(PUMP) === 7.3, "반경을 든 차의 반경을 못 읽는다");
  ok(turnCheckRadius(NOCHK) === null, "null 을 수로 바꿔 읽는다");
  // ★ 실물 `vehicle_spec.json` 에는 그 칸이 없다 — `turn_radius_verified` 가
  //   false 이고 미검증 값으로 화면이 말하지 않는다(§81 · §86-5). 그래서
  //   지금 이 점검은 **꺼져 있다.** 결함이 아니라 선언이고, 자료가 오면 켜진다.
  ok(turnCheckRadius(FL.spec) === null,
    "실물 제원에 회전반경이 들어왔다 — 그러면 이 점검이 켜지고 경로가 움직인다");
  ok(tightTurn(L(), FL.spec, 0, 1, 1) === null, "점검 대상이 아닌데 코너를 판정했다");
});

test("코너 폭 — **벽~벽**을 먼저 쓴다. 최소 폭은 모서리의 폭이 아니다", () => {
  const mk = (over: Partial<GraphEdge>) => ({
    seg_uid: "x", verdict: "clear", width_min_m: null, length_m: 10,
    a: 0, b: 1, coords: [], ...over,
  } as GraphEdge);
  ok(cornerWidth(mk({ width_max_m: 8, width_min_m: 3 })) === 8,
    "최소 폭을 썼다 — 전이 4,472 중 2,038 이 좁은 코너가 됐던 그 꼴이다");
  ok(cornerWidth(mk({ width_min_m: 3 })) === 3, "벽~벽이 없을 때 최소 폭으로 안 떨어진다");
  ok(cornerWidth(mk({})) === null, "둘 다 없는데 수를 만든다 — 모르면 말하지 않는다");
  // ★ `0` 은 **모르는 것이 아니다.** 접으면 폭 0 인 길이 폭 미지로 바뀐다
  ok(cornerWidth(mk({ width_max_m: 0, width_min_m: 3 })) === 0, "폭 0 을 모름으로 접었다");
  ok(MIN_DEFLECTION > 0 && MIN_DEFLECTION < 90, "코너 문턱이 말이 안 되는 값이다");
});

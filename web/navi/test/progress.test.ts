/**
 * test/progress.test.ts — 위치 추정 · 턴바이턴 폐루프 (DECISIONS §213-2 · §213-3).
 *
 * 입력은 **GPS 흉내**(`replay.ts`)다 — 1Hz · σ5m · 음영. 경로를 따라 걷는 정답 점
 * (`simulation.ts`)을 넣으면 추정기가 틀려도 통과하므로 그것은 안 쓴다.
 */
import { FL, test, ok, quantile } from "./harness";
import { buildAdjacency, findRoute } from "../src/domain/graph";
import { locate, predictS, pointAtM, routeGeom, type ProgressState } from "../src/domain/progress";
import { buildIncidence, extractManeuvers, nextManeuver } from "../src/domain/turn";
import { requiredWidth } from "../src/domain/vehicle";
import { createReplaySource } from "../src/infra/position/replay";
import { MX, MY } from "../src/domain/geo";
import type { GraphEdge, RoutePlan } from "../src/domain/types";

const { graph, spec } = FL;
const adj = buildAdjacency(graph, spec, false, "safe");
const inc = buildIncidence(graph);
const need = requiredWidth(spec);

/** 회전이 넷 이상인 1.2km+ 경로를 **결정적으로** 하나 고른다 */
function pickPlan(): RoutePlan {
  const nodes = [...adj.keys()].sort((a, b) => a - b);
  for (let i = 0; i < nodes.length; i += 37) {
    for (let j = nodes.length - 1; j > i; j -= 53) {
      const p = findRoute(graph, adj, nodes[i], nodes[j]);
      if (p && p.lengthM > 1200 && extractManeuvers(p, inc, need).length >= 5) return p;
    }
  }
  throw new Error("시험용 경로를 못 골랐다 — navi_graph 가 바뀌었나");
}
const plan = pickPlan();
const geom = routeGeom(plan);
const mans = extractManeuvers(plan, inc, need);
/** 선형 참값 → length_m 공간 (시험 비교용 근사) */
const truthS = (g: number, total: number) => g * (plan.lengthM / total);

interface Run { err: number[]; offs: number; jumps: { at: number; errAfter: number; sameTurn: boolean }[] }

function drive(opts: Parameters<typeof createReplaySource>[1], hooks?: (t: number, h: ReturnType<typeof createReplaySource>) => void): Run {
  const src = createReplaySource(plan, opts);
  let st: ProgressState | null = null;
  const run: Run = { err: [], offs: 0, jumps: [] };
  let now = 0;
  for (let k = 0; k < 20000 && src.truthM < src.totalM - 1; k++) {
    now += 100;
    hooks?.(now / 1000, src);
    const f = src.step(0.1, now);
    if (!f) continue;
    const r = locate(geom, { lon: f.lon, lat: f.lat, heading: f.heading, t: f.t ?? now }, st);
    st = r.state;
    const truth = truthS(src.truthM, src.totalM);
    if (!r.result.onRoute) run.offs++;
    run.err.push(Math.abs(r.result.s - truth));
    if (r.result.jumped) {
      const a = nextManeuver(mans, r.result.s).m;
      const b = nextManeuver(mans, truth).m;
      run.jumps.push({ at: truth, errAfter: Math.abs(r.result.s - truth), sameTurn: a === b });
    }
  }
  return run;
}

test("선형 길이를 length_m 공간으로 옮긴다 — 회전 지점과 같은 자", () => {
  ok(Math.abs(geom.totalM - plan.lengthM) < 0.01, `총연장 ${geom.totalM} ≠ ${plan.lengthM}`);
  const a = pointAtM(geom, 0).point;
  ok(Math.hypot((a[0] - plan.coords[0][0]) * MX, (a[1] - plan.coords[0][1]) * MY) < 0.5, "s=0 이 경로 시작이 아니다");
});

test("1Hz · σ5m — 중앙 오차 6m · 95% 15m 안, 이탈 오판 0", () => {
  const r = drive({ sigmaM: 5, shadowEverySec: 0, seed: 11 });
  ok(r.err.length > 60, `측위가 ${r.err.length}개뿐이다`);
  const med = quantile(r.err, 0.5), p95 = quantile(r.err, 0.95);
  ok(med < 6, `중앙 오차 ${med.toFixed(1)}m`);
  ok(p95 < 15, `95% 오차 ${p95.toFixed(1)}m`);
  ok(r.offs === 0, `경로 위인데 이탈로 ${r.offs}번 봤다`);
});

test("음영 8초 → 순간이동을 알아채고 새 자리의 회전을 고른다", () => {
  const r = drive({ sigmaM: 5, shadowEverySec: 25, shadowSec: 8, seed: 5 });
  ok(r.jumps.length >= 1, "음영 뒤 순간이동을 한 번도 못 알아챘다");
  for (const j of r.jumps) {
    ok(j.errAfter < 15, `이동 직후 오차 ${j.errAfter.toFixed(1)}m (참값 ${j.at.toFixed(0)}m)`);
    ok(j.sameTurn, `이동 직후 다음 회전이 참값과 다르다 (참값 ${j.at.toFixed(0)}m)`);
  }
  const p95 = quantile(r.err, 0.95);
  ok(p95 < 20, `음영 포함 95% 오차 ${p95.toFixed(1)}m`);
});

test("강제 순간이동 +250m — 한 측위 만에 따라붙는다", () => {
  let done = false;
  const r = drive({ sigmaM: 4, shadowEverySec: 0, seed: 3 }, (t, h) => {
    if (!done && t > 20 && h.truthM + 300 < h.totalM) { h.seek(h.truthM + 250); done = true; }
  });
  ok(done, "경로가 짧아 순간이동을 못 넣었다");
  ok(r.jumps.length >= 1 && r.jumps[0].errAfter < 12,
     `순간이동 뒤 오차 ${r.jumps[0]?.errAfter?.toFixed(1)}m`);
});

test("되돌아 나오는 경로 — 두 번째 통과를 첫 번째로 착각하지 않는다", () => {
  // 같은 구간을 갔다가 그대로 되돌아온다
  const e = [...graph.edges].filter((x) => (x.length_m ?? 0) > 150 && x.coords.length >= 2)
    .sort((a, b) => (b.length_m ?? 0) - (a.length_m ?? 0))[0] as GraphEdge;
  const back = [...e.coords].reverse();
  const loop: RoutePlan = {
    edges: [e, e], forward: [true, false], nodes: [e.a, e.b, e.a],
    coords: [...e.coords, ...back.slice(1)], cost: 0,
    lengthM: 2 * (e.length_m ?? 0), byVerdict: {}, rules: [],
  };
  const g = routeGeom(loop);
  const src = createReplaySource(loop, { sigmaM: 4, shadowEverySec: 0, seed: 9 });
  let st: ProgressState | null = null;
  let now = 0, worst = 0;
  const L = e.length_m ?? 0;
  while (src.truthM < src.totalM - 1) {
    now += 100;
    const f = src.step(0.1, now);
    if (!f) continue;
    const r = locate(g, { lon: f.lon, lat: f.lat, heading: f.heading, t: now }, st);
    st = r.state;
    const truth = src.truthM * (loop.lengthM / src.totalM);
    if (truth > L + 40) worst = Math.max(worst, Math.abs(r.result.s - truth));
  }
  ok(worst < 20, `돌아오는 길에서 오차 최대 ${worst.toFixed(1)}m — 첫 통과에 붙었다`);
});

test("경로에서 45m 벗어나면 두 측위째 이탈, 돌아오면 복귀", () => {
  // 옆으로 45m 밀었을 때 30m 안에 **다른 경로 선분이 없는** 자리를 찾는다
  let pick: { base: [number, number]; off: [number, number] } | null = null;
  for (let s = 100; s < plan.lengthM - 100 && !pick; s += 25) {
    const p = pointAtM(geom, s);
    const rad = (p.bearing * Math.PI) / 180;
    for (const side of [1, -1]) {
      const off: [number, number] = [p.point[0] + side * 45 * Math.cos(rad) / MX,
                                     p.point[1] - side * 45 * Math.sin(rad) / MY];
      const probe = locate(geom, { lon: off[0], lat: off[1], heading: null, t: 0 }, null).result;
      if (probe.lateralM > 35) { pick = { base: p.point, off }; break; }
    }
  }
  ok(pick, "옆으로 벗어날 자리가 경로 어디에도 없다");
  let st: ProgressState | null = null;
  const at = (q: [number, number], t: number) => {
    const r = locate(geom, { lon: q[0], lat: q[1], heading: null, t }, st);
    st = r.state; return r.result;
  };
  ok(at(pick.base, 0).onRoute, "경로 위인데 이탈");
  ok(at(pick.off, 1000).onRoute, "한 번 튄 것으로 이탈을 확정했다");
  ok(!at(pick.off, 2000).onRoute, "두 번 연속 벗어났는데 이탈이 아니다");
  ok(at(pick.base, 3000).onRoute, "돌아왔는데 복귀가 안 된다");
});

test("추측항법은 마지막 측위에서 1.5초 넘게 앞서 가지 않는다", () => {
  const st: ProgressState = { s: 100, v: 10, t: 0, offCount: 0 };
  ok(Math.abs(predictS(st, 1000, 5000) - 110) < 1e-6, "1초 뒤 110m 가 아니다");
  ok(Math.abs(predictS(st, 9000, 5000) - 115) < 1e-6, "끊긴 뒤에도 계속 달린다");
});

test("안내 문턱은 가장 안쪽을 고른다 — 준비 · 실행 안내가 나간다", async () => {
  const { gateIndex } = await import("../src/domain/turn");
  // 8m/s: 먼저 알림 96m · 준비 48m · 실행 20m
  ok(gateIndex(200, 8) === -1, "문턱 밖인데 걸렸다");
  ok(gateIndex(60, 8) === 0, "먼저 알림 자리가 아니다");
  ok(gateIndex(40, 8) === 1, "준비 자리에서 준비가 아니다 — 종전 findIndex 결함");
  ok(gateIndex(10, 8) === 2, "실행 자리에서 실행이 아니다 — 종전 findIndex 결함");
});

test("재동기화 직후 안내 문구 = 새 자리 기준", async () => {
  const { mergePhrase } = await import("../src/domain/turn");
  const k = mans.findIndex((x, i) => i > 0 && x.kind !== "arrive" && x.atM - mans[i - 1].atM > 120);
  ok(k > 0, "간격 넓은 회전 쌍이 없다");
  const s = mans[k].atM - 70;                    // 순간이동으로 떨어진 자리
  const n = nextManeuver(mans, s, 45);
  ok(n.m === mans[k], "새 자리의 다음 회전이 아니다");
  const txt = mergePhrase(n.m!, n.after, n.distM);
  ok(/^70미터 앞 /.test(txt), `문구가 새 자리 거리를 말하지 않는다: ${txt}`);
});

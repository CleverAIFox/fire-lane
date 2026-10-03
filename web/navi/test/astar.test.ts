/**
 * test/astar.test.ts — **A* 가 다익스트라와 같은 답을 내는가.** (PLAN §1 #71)
 *
 * ── 왜 생겼나 ───────────────────────────────────────────────────
 * `domain/graph.ts` 머리말이 「`edgeCost` 의 배수 최솟값은 **1.0** 이다. 따라서
 * 비용 ≥ 실거리이고 직선거리를 그대로 휴리스틱으로 써도 과대추정하지 않는다」고
 * **선언만** 하고 있었다. 강제자가 0 이었다.
 *
 * 그리고 바로 다음 줄이 스스로 경고했다 — 「`TUNING` 에 1.0 미만 배수를 넣으면
 * 이 성질이 깨진다」. 그런데 `TUNING` 은 머리말이 **「남는 사람이 회색 해법을
 * 정하면 여기만 고치면 된다」**고 선언한 자리다. **깨뜨릴 사람이 graph.ts 의
 * 머리말을 읽을 이유가 없다.**
 *
 * ★ 이 시험이 묻는 것 셋 —
 *     ① 지금 값에서 A* 와 다익스트라가 **같은 비용**을 내나 (실물 그래프)
 *     ② 배수를 1.0 아래로 내리면 **옛 휴리스틱은 깨지고 새 것은 안 깨지나**
 *     ③ `TuningKnobs` 의 모든 칸이 배수냐 아니냐로 **분류돼 있나**
 *
 * ★ 비용은 **인접리스트가 쓰는 벌점 비용**으로 센다. 실거리로 세면 벌점이
 *   붙은 경로에서 두 답이 달라도 같아 보인다 — 첫 판에서 실제로 그렇게
 *   재서 「차이 0」이 나왔고, 그것은 빈 그물이었다.
 */
import { FL, test, ok } from "./harness";
import { buildAdjacency, findRoute } from "../src/domain/graph";
import { adjacencyMinFactor, type Adjacency } from "../src/domain/adjacency";
import {
  MULTIPLIERS, minCostFactor, pressureIsSane, TUNING, type TuningKnobs,
} from "../src/domain/vehicle";
import { minDirectionFactor } from "../src/domain/rules";
import type { RoutePlan } from "../src/domain/types";

/**
 * 배수가 **아닌** 칸. 사유가 본체다 — 빠지면 ③ 이 그 칸 이름을 대며 운다.
 *
 * ★ **번들이 아니라 여기 산다.** 사유는 사람이 읽는 글이고 앱이 받을 이유가
 *   없다 — `test_layering.py` 의 `NOT_DOMAIN` 이 시험에 사는 것과 같은 자리다.
 *   (무게 때문은 아니다. 옮기기 전후 둘 다 141.61KB 였다 — 소비자 없는
 *    `Record` 는 접힌다. 재 보고 적는다.)
 * ★ 분모는 `TuningKnobs` 에서 **유도**된다. 이 표가 좁아지는 쪽으로 틀리면
 *   ③ 이 운다 — 손목록의 결함은 틀린 항목이 아니라 빠진 항목이다(§370).
 */
const NOT_A_MULTIPLIER: Record<string, string> = {
  tightMarginM: "미터다. 배수가 아니라 **문턱**이고, 이 값이 결정하는 것은 "
    + "「`tight` 배수를 걸까」지 비용의 크기가 아니다",
  parkPer1000: "더하기 계수다. `pressureFactor` 가 `1 + Σ` 를 내므로 "
    + "**음수가 아닌 동안** 그 항의 최솟값은 1 이다(`pressureIsSane`)",
  ecamPerSite: "더하기 계수다 — `parkPer1000` 과 같은 자리, 같은 사유",
  speedbumpEach: "더하기 계수다 — `parkPer1000` 과 같은 자리, 같은 사유",
  speedcamEach: "더하기 계수다 — `parkPer1000` 과 같은 자리, 같은 사유",
  zoneEach: "더하기 계수다 — `parkPer1000` 과 같은 자리, 같은 사유",
};

/** 그 인접리스트가 실제로 쓰는 벌점 비용으로 경로 값을 다시 센다. */
function planCost(adj: Adjacency, p: RoutePlan): number {
  let s = 0;
  for (let i = 0; i < p.edges.length; i++) {
    const row = adj.get(p.nodes[i]) ?? [];
    const hit = row.find((a) => a.edge === p.edges[i]);
    if (!hit) return Number.NaN;
    s += hit.cost;
  }
  return s;
}

/** 무작위 쌍을 A*(휴리스틱) 와 다익스트라(휴리스틱 0)로 풀어 비용을 댄다. */
function sweep(adj: Adjacency, seed: number, tries: number) {
  const N = FL.graph.nodes.length;
  let rnd = seed;
  const next = () => (rnd = (rnd * 1103515245 + 12345) % 2147483648) / 2147483648;
  let pairs = 0, worse = 0, unscored = 0, maxGap = 0;
  const show: string[] = [];
  for (let i = 0; i < tries; i++) {
    const a = Math.floor(next() * N), b = Math.floor(next() * N);
    if (a === b) continue;
    const ra = findRoute(FL.graph, adj, a, b, true);
    const rd = findRoute(FL.graph, adj, a, b, false);
    if (!ra || !rd) continue;
    pairs++;
    const ca = planCost(adj, ra), cd = planCost(adj, rd);
    if (!Number.isFinite(ca) || !Number.isFinite(cd)) { unscored++; continue; }
    const gap = ca - cd;
    if (gap > 1e-6) {
      worse++;
      maxGap = Math.max(maxGap, gap);
      if (show.length < 3) show.push(`${a}→${b}  A* ${ca.toFixed(1)} > D ${cd.toFixed(1)} (+${gap.toFixed(2)})`);
    }
  }
  return { pairs, worse, unscored, maxGap, show };
}

test("① 지금 값에서 A* 와 다익스트라가 같은 비용을 낸다", () => {
  const adj = buildAdjacency(FL.graph, FL.spec);
  const r = sweep(adj, 20260904, 700);
  console.log(`  노드 ${FL.graph.nodes.length} · 하한 ${adjacencyMinFactor(adj)}`
    + ` · 쌍 ${r.pairs} · 비용 못 센 것 ${r.unscored} · A* 가 더 나쁜 답 ${r.worse}`);
  r.show.forEach((s) => console.log("      " + s));
  ok(r.pairs > 50, `둘 다 경로가 있는 쌍이 ${r.pairs} — 표본이 얇다(빈 그물)`);
  ok(r.unscored === 0, `비용을 못 센 쌍이 ${r.unscored} — planCost 가 실물과 갈렸다`);
  ok(r.worse === 0,
    `A* 가 ${r.worse}개 쌍에서 더 나쁜 답을 낸다 (최대 +${r.maxGap.toFixed(2)})\n`
    + `      휴리스틱이 실제 비용을 넘고 있다 — 하한이 ${adjacencyMinFactor(adj)} 인데 배수가 더 작다`);
});

test("② 배수를 1.0 아래로 내리면 옛 휴리스틱은 깨지고 새 것은 안 깨진다", () => {
  const bad: TuningKnobs = { ...TUNING, unknown: 0.2, noWidth: 0.2, tight: 0.2 };
  const adj = buildAdjacency(FL.graph, FL.spec, false, "safe", bad);

  // ★ 새 휴리스틱 — 하한을 곱하므로 admissible 이다
  const now = sweep(adj, 777, 1200);
  console.log(`  배수 0.2 · 하한 ${adjacencyMinFactor(adj)} — 쌍 ${now.pairs}`
    + ` · A* 가 더 나쁜 답 ${now.worse}`);
  now.show.forEach((s) => console.log("      " + s));
  ok(now.pairs > 50, `표본 ${now.pairs} — 얇다`);
  ok(now.worse === 0,
    `하한을 곱했는데도 ${now.worse}개가 더 나쁘다 (최대 +${now.maxGap.toFixed(2)})`);

  // ★ **양성 대조.** 옛 꼴(하한 1)로 같은 그래프를 돌면 깨져야 한다.
  //   안 깨지면 이 시험이 지키는 것이 없다 — 빈 그물이다.
  //   `findRoute` 는 하한을 인접리스트에서 읽으므로 배율을 쥘 수 없다.
  //   그래서 `astarWith` 가 **같은 사슬**을 돌며 배율만 인자로 받는다.
  const probe = sweepWithH(adj, 777, 1200, 1);
  console.log(`  ★ 옛 휴리스틱(하한 1) — 쌍 ${probe.pairs} · 더 나쁜 답 ${probe.worse}`
    + ` · 최대 +${probe.maxGap.toFixed(2)}`);
  probe.show.forEach((s) => console.log("      " + s));
  ok(probe.worse > 0,
    "하한 1 로 되돌려도 안 깨진다 — 이 시험이 지키는 것이 없다(빈 그물).\n"
    + "      배수를 더 내리거나 표본을 늘려라");
});

/** 휴리스틱 배율을 **직접 주고** 같은 쓸기를 돈다 — 옛 꼴의 재현용. */
function sweepWithH(adj: Adjacency, seed: number, tries: number, mf: number) {
  const N = FL.graph.nodes.length;
  let rnd = seed;
  const next = () => (rnd = (rnd * 1103515245 + 12345) % 2147483648) / 2147483648;
  let pairs = 0, worse = 0, maxGap = 0;
  const show: string[] = [];
  for (let i = 0; i < tries; i++) {
    const a = Math.floor(next() * N), b = Math.floor(next() * N);
    if (a === b) continue;
    const ra = astarWith(adj, a, b, mf);
    const rd = findRoute(FL.graph, adj, a, b, false);
    if (ra === null || !rd) continue;
    const cd = planCost(adj, rd);
    if (!Number.isFinite(ra) || !Number.isFinite(cd)) continue;
    pairs++;
    const gap = ra - cd;
    if (gap > 1e-6) {
      worse++; maxGap = Math.max(maxGap, gap);
      if (show.length < 3) show.push(`${a}→${b}  A* ${ra.toFixed(1)} > D ${cd.toFixed(1)} (+${gap.toFixed(2)})`);
    }
  }
  return { pairs, worse, maxGap, show };
}

/**
 * `findRoute` 와 **같은 사슬**로 A* 를 돌되 휴리스틱 배율만 인자로 받는다.
 * 옛 코드(배율 1)가 깨지는 것을 보이려면 그 배율을 쥘 수 있어야 한다.
 */
function astarWith(adj: Adjacency, s: number, g: number, mf: number): number | null {
  const goal = FL.graph.nodes[g];
  const dist = (n: number) => {
    const a = FL.graph.nodes[n];
    const dy = (goal[1] - a[1]) * 111_320;
    const dx = (goal[0] - a[0]) * 111_320 * Math.cos((a[1] * Math.PI) / 180);
    return Math.hypot(dx, dy);
  };
  const open: { n: number; f: number; gc: number }[] = [{ n: s, f: dist(s) * mf, gc: 0 }];
  const best = new Map<number, number>([[s, 0]]);
  const done = new Set<number>();
  while (open.length) {
    open.sort((p, q) => p.f - q.f);
    const cur = open.shift()!;
    if (cur.n === g) return cur.gc;
    if (done.has(cur.n)) continue;
    done.add(cur.n);
    for (const a of adj.get(cur.n) ?? []) {
      const ng = cur.gc + a.cost;
      if (ng < (best.get(a.to) ?? Infinity)) {
        best.set(a.to, ng);
        open.push({ n: a.to, f: ng + dist(a.to) * mf, gc: ng });
      }
    }
  }
  return null;
}

test("③ TuningKnobs 의 모든 칸이 배수냐 아니냐로 분류돼 있다", () => {
  const keys = Object.keys(TUNING) as (keyof TuningKnobs)[];
  const mult = new Set<string>(MULTIPLIERS);
  const missing = keys.filter((k) => !mult.has(k) && !(k in NOT_A_MULTIPLIER));
  ok(missing.length === 0,
    `분류 안 된 조율 칸 — ${missing.join(", ")}\n`
    + "      `MULTIPLIERS` 에 넣거나 `NOT_A_MULTIPLIER` 에 **사유와 함께** 적어라.\n"
    + "      손목록의 결함은 틀린 항목이 아니라 **빠진 항목**이다(§370).");

  // ★ 양방향 — 죽은 분류는 사각지대다
  const dead = [...mult, ...Object.keys(NOT_A_MULTIPLIER)].filter(
    (k) => !(k in TUNING));
  ok(dead.length === 0, `실재하지 않는 칸을 분류한다 — ${dead.join(", ")}`);

  // ★ 사유가 짧으면 사유가 아니다
  const thin = Object.entries(NOT_A_MULTIPLIER).filter(([, v]) => v.length < 20);
  ok(thin.length === 0, `사유가 20자 미만 — ${thin.map(([k]) => k).join(", ")}`);

  console.log(`  조율 칸 ${keys.length} = 배수 ${MULTIPLIERS.length}`
    + ` + 배수 아님 ${Object.keys(NOT_A_MULTIPLIER).length}`
    + ` · 하한 ${minCostFactor(TUNING, minDirectionFactor())}`);
});

test("④ 하한 계산이 값을 따라 움직인다", () => {
  ok(minCostFactor(TUNING, minDirectionFactor()) === 1,
    "지금 값에서 하한이 1 이 아니다 — 그러면 오늘 경로가 달라진다");
  ok(minCostFactor({ ...TUNING, tight: 0.4 }, 1) === 0.4, "배수를 안 따라간다");
  ok(minCostFactor(TUNING, 0.25) === 0.25, "방향 계수를 안 따라간다");
  ok(minCostFactor({ ...TUNING, tight: 5 }, 1) === 1,
    "배수가 다 1 이상인데 하한이 1 을 넘는다 — 그러면 최적해가 깨진다");
  ok(!pressureIsSane({ ...TUNING, parkPer1000: -1 }), "음수 압력 계수를 통과시킨다");
  ok(pressureIsSane(TUNING), "지금 값을 음수로 본다");
});

test("⑤ 압력 계수가 음수면 휴리스틱을 포기한다 (다익스트라로 떨어진다)", () => {
  const adj = buildAdjacency(FL.graph, FL.spec, false, "safe",
    { ...TUNING, parkPer1000: -1 });
  ok(adjacencyMinFactor(adj) === 0,
    `음수 계수인데 하한이 ${adjacencyMinFactor(adj)} 다 — 자료 없이는 못 묶는다`);
});

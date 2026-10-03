/**
 * rulesens.test.ts — **그 배수가 경로를 얼마나 바꾸는가.** (DECISIONS §367)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `domain/rules.ts` 가 제 머리말에 이렇게 적는다 —
 *
 * > ★ 아래 배수는 **근거 없는 가정값**이다. 측정한 값이 아니다.
 * >   현장 검증 전까지 이 숫자를 근거로 인용하지 않는다.
 *
 * 그 선언은 옳고 정직하다. 그런데 **근거 없는 수를 다른 근거 없는 수로 바꾸는
 * 것은 고치는 것이 아니다.** 「4 가 맞나 3 이 맞나」는 현장 없이 답이 없다.
 *
 * 답이 **있는** 물음은 다른 것이다 — **그 수가 틀렸을 때 얼마나 아픈가.**
 * 영향이 0 이면 그 수는 고칠 가치가 없고(지금 아무 경로도 안 움직인다),
 * 영향이 크면 **현장 검증이 PLAN 위로 올라가야 한다.** 그 판단에 필요한 것이
 * 민감도이고, 민감도는 **레이크 없이 저장소 안에서 잰다** — `navi_graph.json`
 * 이 커밋돼 있다.
 *
 * ── 범위 (실측이 먼저 좁혔다) ───────────────────────────────────
 * ```
 * 엣지 1,281  ·  ow=2(방향 미확인) 56  ·  ow=1(방향 확정) 1  ·  회전금지 5
 * ```
 * **배수 셋이 닿는 자리가 62개뿐이다.** 그래서 영향의 상한도 거기서 나온다 —
 * 이 측정이 재는 것은 「그 62개를 지나는 경로가 몇이고, 배수를 흔들면 그중
 * 몇이 길을 바꾸는가」다.
 *
 * ★ **이 시험은 수를 박지 않는다.** 박으면 그래프가 바뀔 때마다 낡고,
 *   그 수의 정본은 없다(§246-2 · `countcheck`). 박는 것은 **방향**이다 —
 *     ① 배수를 **키우면** 그 구간을 지나는 경로가 **줄거나 같다**(단조)
 *     ② 배수를 1 로 내리면 **답이 갈린다**(= 이 신호가 듣는다)
 *     ③ `WRONG_WAY` 를 키워도 **「경로 없음」이 안 생긴다**(빼지 않는다 · §215-1)
 *   수는 `console.log` 로 찍어 사람이 읽는다 — 재현 명령이 머리말에 있다.
 *
 *     npx vitest run test/rulesens.test --reporter=basic
 */
import { describe, expect, it } from "vitest";

import { FL } from "./harness";
import { buildAdjacency, type Adjacency } from "../src/domain/adjacency";
import { findRouteBetween, snapToEdge } from "../src/domain/graph";
import { ONEWAY_UNKNOWN, TURN_BAN_M, WRONG_WAY, directionFactor } from "../src/domain/rules";
import { TUNING, type TuningKnobs } from "../src/domain/vehicle";
import type { GraphEdge, NaviGraph, RoutePlan } from "../src/domain/types";

const { graph, spec } = FL;

/** 배수 셋이 닿는 자리. **여기 없으면 어떤 배수도 경로를 안 바꾼다.** */
const TOUCHED = {
  owUnknown: graph.edges.filter((e) => e.ow === 2).length,
  owKnown: graph.edges.filter((e) => e.ow === 1 || e.ow === -1).length,
  turnBans: (graph.turns ?? []).length,
};

/**
 * 배수를 갈아끼운 그래프. **`rules.ts` 의 상수를 못 바꾸므로 `ow` 를 바꾼다.**
 *
 * ★ 상수를 몽키패치하지 않는다 — `directionFactor` 가 모듈 상수를 읽고,
 *   그것을 시험이 쓰면 **시험이 산 코드를 고치는** 꼴이 된다. 대신 같은
 *   효과를 **입력 쪽**에서 낸다: `ow` 를 지우면 그 구간의 배수가 1 이 된다.
 *   「배수를 1 로 내렸을 때」와 **정확히 같은 그래프**다.
 */
function withoutOneway(g: NaviGraph): NaviGraph {
  return { ...g, edges: g.edges.map((e) => (e.ow ? { ...e, ow: 0 } : e)) } as NaviGraph;
}
function withoutTurnBans(g: NaviGraph): NaviGraph {
  return { ...g, turns: [] } as NaviGraph;
}

/**
 * O/D 표본. **결정적이다** — 노드 목록을 일정 간격으로 집는다.
 *
 * ★ 난수를 안 쓴다. 쓰면 배치마다 다른 수가 나오고, 그러면 「변했다」와
 *   「표본이 달랐다」를 못 가른다(§230 과 같은 자리).
 */
function pairs(adj: Adjacency, n: number): [number, number][] {
  const nodes = [...adj.keys()].sort((a, b) => a - b);
  const out: [number, number][] = [];
  const stride = Math.max(1, Math.floor(nodes.length / n));
  for (let i = 0; i < nodes.length; i += stride) {
    const j = (i + Math.floor(nodes.length / 2)) % nodes.length;
    out.push([nodes[i], nodes[j]]);
  }
  return out;
}

const uids = (p: RoutePlan | null) => p?.edges.map((e) => e.seg_uid).join(",") ?? null;

/**
 * **원본에서** 일방통행인 구간의 이름.
 *
 * ★ 첫 판이 `off` 쪽에서도 `e.ow` 를 봤고, `withoutOneway` 가 그 칸을 0 으로
 *   만들므로 **늘 0 이 나왔다.** 「배수를 끄면 그 길을 더 쓴다」를 재는데
 *   끈 그래프에서 그 길을 **못 알아보는** 꼴이었다 — 내 시험이 먼저 빨갰다.
 *   기준은 **원본**이어야 한다.
 */
const ONEWAY_UIDS: ReadonlySet<string> = new Set(
  graph.edges.filter((e) => e.ow === 1 || e.ow === -1 || e.ow === 2)
    .map((e) => e.seg_uid));

interface Run {
  solved: number;
  routes: (string | null)[];
  lengths: number[];
  /** 배수가 닿는 구간을 지나는 경로 수 */
  touching: number;
}

function sweep(g: NaviGraph, od: [number, number][], knobs: TuningKnobs = TUNING): Run {
  const adj = buildAdjacency(g, spec, false, "safe", knobs);
  const routes: (string | null)[] = [];
  const lengths: number[] = [];
  let solved = 0;
  let touching = 0;
  for (const [a, b] of od) {
    const p = findRouteBetween(g, adj, { node: a }, { node: b });
    routes.push(uids(p));
    if (p) {
      solved++;
      lengths.push(p.lengthM);
      if (p.edges.some((e: GraphEdge) => ONEWAY_UIDS.has(e.seg_uid))) touching++;
    } else {
      lengths.push(NaN);
    }
  }
  return { solved, routes, lengths, touching };
}

describe("배수 셋이 닿는 자리 — 영향의 상한", () => {
  it("★ 0 이면 이 측정이 **빈 그물**이다", () => {
    expect(TOUCHED.owUnknown + TOUCHED.owKnown).toBeGreaterThan(0);
  });

  it("실측을 찍는다 — 수는 문서에 안 적는다", () => {
    const base = buildAdjacency(graph, spec);
    const od = pairs(base, 120);
    const on = sweep(graph, od);
    const off = sweep(withoutOneway(graph), od);
    const nb = sweep(withoutTurnBans(graph), od);
    const moved = on.routes.map((r, i) => (r !== off.routes[i] ? i : -1))
      .filter((i) => i >= 0);
    const nbMoved = on.routes.filter((r, i) => r !== nb.routes[i]).length;
    // ★ 「얼마나 돌아가나」 — 이것이 정책의 **값**이다. 배수가 틀렸을 때 내는 비용
    const extra = moved.map((i) => on.lengths[i] - off.lengths[i])
      .filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
    const mid = extra.length ? extra[Math.floor(extra.length / 2)] : NaN;
    const pct = (n: number) => `${((100 * n) / on.solved).toFixed(1)}%`;
    // ★ `no-console` 은 이 저장소에 **켜져 있지 않다.** 억제 주석을 달았다가
    //   eslint 가 「없는 규칙을 끈다」고 경고해서 지웠다 — §279-4 가 센 그 종이고,
    //   28개를 걷어낸 자리에 이 배치가 하나를 더할 뻔했다.
    console.log([
      "",
      "── 통행규칙 배수 민감도 (DECISIONS §367) ──────────────────",
      `  엣지 ${graph.edges.length} · ow=2 ${TOUCHED.owUnknown}`
      + ` · ow=±1 ${TOUCHED.owKnown} · 회전금지 ${TOUCHED.turnBans}`,
      `  상수     WRONG_WAY ${WRONG_WAY} · ONEWAY_UNKNOWN ${ONEWAY_UNKNOWN}`
      + ` · TURN_BAN_M ${TURN_BAN_M}`,
      `  O/D 표본 ${od.length} · 경로 성립 ${on.solved}`,
      "",
      `  일방통행 구간을 지나는 경로        ${on.touching}  (${pct(on.touching)})`,
      `  일방통행 배수를 1 로 → 길이 바뀜   ${moved.length}  (${pct(moved.length)})`,
      `  회전금지를 없애 → 길이 바뀜        ${nbMoved}  (${pct(nbMoved)})`,
      `  바뀐 경로가 **더 돌아간 거리** 중앙  ${Number.isFinite(mid) ? mid.toFixed(0) : "—"}m`
      + (extra.length ? `  (최소 ${extra[0].toFixed(0)} · 최대 ${extra.at(-1)!.toFixed(0)})` : ""),
      "",
      "  ★ 0 이 아니면 **장식이 아니다.** 그러나 이 수가 곧 「배수 4 가 맞다」는",
      "    뜻은 아니다 — 재는 것은 **틀렸을 때의 아픔**이고, 맞는 값은 현장이 든다.",
      "",
    ].join("\n"));
    expect(on.solved).toBeGreaterThan(0);
  });
});

describe("① 단조 — 키우면 그 길을 **덜** 쓴다", () => {
  it("일방통행 배수를 없애면 그 구간을 지나는 경로가 **늘거나 같다**", () => {
    const base = buildAdjacency(graph, spec);
    const od = pairs(base, 120);
    const on = sweep(graph, od);
    const off = sweep(withoutOneway(graph), od);
    // 배수가 없으면 그 구간이 싸지므로 **더 쓰인다**. 반대로는 안 간다.
    expect(off.touching).toBeGreaterThanOrEqual(on.touching);
  });
});

describe("② 이 신호가 듣는가 — 끄면 **답이 갈린다**", () => {
  it("★ 끄고도 모든 경로가 같으면 이 배수는 **장식**이다", () => {
    const base = buildAdjacency(graph, spec);
    const od = pairs(base, 200);
    const on = sweep(graph, od);
    const off = sweep(withoutOneway(graph), od);
    const changed = on.routes.filter((r, i) => r !== off.routes[i]).length;
    expect(changed, [
      "일방통행 배수를 1 로 내려도 **경로가 하나도 안 바뀐다.**",
      "둘 중 하나다 —",
      "  ① 표본이 그 구간을 안 지난다  → 표본을 늘려라",
      `  ② 그 배수가 장식이다        → ow=2 가 ${TOUCHED.owUnknown}개인데`,
      "     경로가 안 움직이면 `ONEWAY_UNKNOWN` 은 지금 아무 일도 안 한다.",
      "     그러면 **현장 검증의 우선순위가 내려간다** — 그것이 이 측정의 값이다.",
    ].join("\n")).toBeGreaterThan(0);
  });

  it("방향 배수는 **방향마다** 다르다 — 양쪽이 같으면 일방통행이 아니다", () => {
    const e = { ow: 1 } as GraphEdge;
    expect(directionFactor(e, true)).toBe(1);
    expect(directionFactor(e, false)).toBe(WRONG_WAY);
    const u = { ow: 2 } as GraphEdge;
    expect(directionFactor(u, true)).toBe(directionFactor(u, false));
    expect(directionFactor(u, true)).toBe(ONEWAY_UNKNOWN);
  });
});

describe("③ 빼지 않는다 — 배수를 키워도 「경로 없음」이 안 생긴다 (§215-1)", () => {
  it("★ 정책의 전부다. 빼 버리면 역주행으로만 닿는 집이 「경로 없음」이 된다", () => {
    const base = buildAdjacency(graph, spec);
    const od = pairs(base, 120);
    const on = sweep(graph, od);
    const off = sweep(withoutOneway(graph), od);
    // 배수가 있어도 **성립한 경로 수가 같다.** 비용만 오른다
    expect(on.solved).toBe(off.solved);
  });

  it("회전 금지도 같다 — 금지를 없애도 성립 수가 같다", () => {
    const base = buildAdjacency(graph, spec);
    const od = pairs(base, 120);
    expect(sweep(graph, od).solved).toBe(sweep(withoutTurnBans(graph), od).solved);
  });
});

describe("★ 측정 자체의 생사 — 합성 그래프로 민다", () => {
  /**
   * 역주행이 아니면 **훨씬 긴** 우회만 남는 그래프.
   *
   *   0 ──e0 100m(일방 0→1)── 1
   *   └──e1 100m── 2 ──e2 100m── 3 ──e3 100m── 1
   *
   * 1 → 0 은 역주행 100m × 4 = 400 대 우회 300 이다 — **우회를 택한다.**
   * 배수가 1 이면 역주행 100 이 이긴다. 그 갈림이 이 측정의 심장이다.
   */
  function synth(): NaviGraph {
    const nodes: [number, number][] = [
      [126.900, 35.150], [126.902, 35.150], [126.900, 35.149],
      [126.901, 35.149],
    ];
    const mk = (uid: string, a: number, b: number, L: number, ow = 0): GraphEdge =>
      ({ seg_uid: uid, verdict: "clear", width_min_m: 10, length_m: L,
         a, b, ow, coords: [nodes[a], nodes[b]] } as GraphEdge);
    return {
      crs: "EPSG:4326", node_tol_m: 0.5,
      counts: { nodes: 4, edges: 4, self_loops: 0 }, style: {}, nodes,
      edges: [mk("e0", 0, 1, 100, 1), mk("e1", 0, 2, 100),
              mk("e2", 2, 3, 100), mk("e3", 3, 1, 100)],
      turns: [],
    } as unknown as NaviGraph;
  }

  it("배수가 있으면 **우회**를 택한다", () => {
    const g = synth();
    const adj = buildAdjacency(g, spec);
    const p = findRouteBetween(g, adj, { node: 1 }, { node: 0 });
    expect(uids(p)).toBe("e3,e2,e1");
  });

  it("★ 배수를 1 로 내리면 **역주행**을 택한다 — 측정이 산다", () => {
    const g = withoutOneway(synth());
    const adj = buildAdjacency(g, spec);
    const p = findRouteBetween(g, adj, { node: 1 }, { node: 0 });
    expect(uids(p)).toBe("e0");
  });

  it("우회가 **더 길어도** 역주행으로 안 간다 — 배수 4 가 그 크기다", () => {
    const g = synth();
    // 우회 셋을 각 130m 로 늘리면 390 이고 역주행 400 보다 싸다
    const long = { ...g, edges: g.edges.map((e) =>
      (e.seg_uid === "e0" ? e : { ...e, length_m: 130 })) } as NaviGraph;
    const p = findRouteBetween(long, buildAdjacency(long, spec),
                               { node: 1 }, { node: 0 });
    expect(uids(p)).toBe("e3,e2,e1");
    // ★ 반대 — 우회가 **배수를 넘으면** 역주행이 이긴다. 그 선이 정책의 크기다
    const longer = { ...g, edges: g.edges.map((e) =>
      (e.seg_uid === "e0" ? e : { ...e, length_m: 140 })) } as NaviGraph;
    expect(uids(findRouteBetween(longer, buildAdjacency(longer, spec),
                                 { node: 1 }, { node: 0 }))).toBe("e0");
  });

  it("출발점을 못 붙이면 측정이 성립하지 않는다 — 전제를 적어 둔다", () => {
    const g = synth();
    expect(snapToEdge(g, buildAdjacency(g, spec), [126.901, 35.1495])).not.toBeNull();
  });
});

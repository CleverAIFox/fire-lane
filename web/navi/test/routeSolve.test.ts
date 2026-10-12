/**
 * routeSolve.test.ts — 「출발 · 도착」을 경로 한 벌로 푸는 자. (DECISIONS §482)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 센 40 중 **모듈 통째로 안 드는 것 셋** 가운데 둘째다.
 * `domain/routeSolve.ts` 는 `#129` 가 **훅에서 떼어낸** 계산이고, 뗀 이유가
 * 「브라우저 없이 부를 수 있어야 한다」였는데 **브라우저 없이 부르는 자가
 * 없었다.** 뗀 값을 아무도 안 썼다.
 *
 * ★ 이 파일이 무는 것은 그 머리말이 **적어 둔 세 약속**이다 —
 *
 *     ① 못 닿으면 **대체 접근 지점**에 댄다. 「경로 없음」으로 끝내지 않는다
 *     ② 대체 접근이면 빠른 경로도 **같은 끝점**으로 낸다 — 끝이 갈리면
 *        두 경로를 비교한 수가 거짓이 된다
 *     ③ 상태를 안 만진다 (순수) — 그래서 여기서 그냥 부를 수 있다
 *
 * ★ 실물 발행물(`navi_graph.json`)로 민다. 대체 접근은 **성분이 갈린
 *   그래프**에서만 나오고, 합성 도로로는 그 모양을 못 만든다 — 그래서
 *   전제를 **시험으로** 먼저 적는다(없어지면 운다).
 *
 * 밖    **`null` 갈래는 못 민다.** 그것은 출발 좌표가 어느 통행가능 구간에도
 *       안 붙는 경우(또는 대체 접근까지 실패)이고, 실물 발행물에는 그런
 *       좌표가 없다 — 멀리 찍어도 `snapToEdge` 가 가장 가까운 구간에 붙인다
 *       (실측: 18km 밖에서도 경로가 서고 `walkM` 이 16,414m 다). 합성
 *       그래프를 지어 그 갈래만 밀면 **그 합성이 실물과 다른 꼴**이 되므로,
 *       여기서는 **먼 곳이 null 이 아니라는 것**을 적는다 — 그것이 지금
 *       실제로 하는 일이고, 화면이 그 수를 받는다.
 */
import { describe, expect, it } from "vitest";

import { reachable } from "../src/domain/access";
import { distM, type LngLat } from "../src/domain/geo";
import { buildAdjacency, type Adjacency } from "../src/domain/graph";
import { reaches, solveRoute } from "../src/domain/routeSolve";
import { FL } from "./harness";

const { graph, spec } = FL;
const safe = buildAdjacency(graph, spec, false, "safe");
const fast = buildAdjacency(graph, spec, false, "fastest");

const NODES = [...safe.keys()].sort((a, b) => a - b);
const A: LngLat = graph.nodes[NODES[0]];
const B: LngLat = graph.nodes[NODES[NODES.length - 1]];

/** 출발점에서 닿는 노드 집합. 성분이 갈린 자리를 여기서 찾는다. */
const REACH = reachable(safe, NODES[0]);

/** 다른 성분에 있는 구간들의 **가운데 점**. 대체 접근을 부르는 좌표다. */
const OTHER: LngLat[] = graph.edges
  .filter((e) => safe.has(e.a) && !REACH.has(e.a) && !REACH.has(e.b)
    && (e.coords?.length ?? 0) >= 2)
  .map((e) => e.coords[Math.floor(e.coords.length / 2)]);

describe("① 전제 — 성분이 갈린 그래프인가", () => {
  it("★ 닿지 않는 성분이 있다", () => {
    // 이것이 깨지면 아래 ③이 **아무것도 안 민다.** 발행물이 바뀌어 그래프가
    // 하나로 이어졌으면, 그때는 대체 접근을 미는 다른 길을 찾아야 한다.
    expect(REACH.size).toBeGreaterThan(50);
    expect(REACH.size).toBeLessThan(graph.nodes.length);
    expect(OTHER.length).toBeGreaterThan(0);
  });
});

describe("② 보통 — 양쪽이 같은 성분이면 그냥 푼다", () => {
  const r = solveRoute(graph, safe, fast, A, B);

  it("경로가 서고, 대체 접근이 아니다", () => {
    expect(r).not.toBeNull();
    expect(r!.alt).toBe(false);
    expect(r!.plan.edges.length).toBeGreaterThan(0);
  });

  it("도착점이 그래프 위면 **걸어갈 거리가 없다**", () => {
    expect(r!.walkM).toBeLessThan(1);
  });

  it("빠른 경로도 같이 낸다", () => {
    expect(r!.fast).not.toBeNull();
    expect(r!.fast!.edges.length).toBeGreaterThan(0);
  });

  it("★ 빠른 인접리스트를 안 주면 **안전 경로만** 낸다 — 죽지 않는다", () => {
    const one = solveRoute(graph, safe, null, A, B);
    expect(one).not.toBeNull();
    expect(one!.fast).toBeNull();
    // 안전 경로는 빠른 쪽을 줬든 안 줬든 같아야 한다
    expect(one!.plan.edges.map((e) => e.seg_uid))
      .toEqual(r!.plan.edges.map((e) => e.seg_uid));
  });

  it("★ 상태를 안 만진다 — 두 번 불러도 같은 답이다(순수)", () => {
    const again = solveRoute(graph, safe, fast, A, B);
    expect(again!.plan.edges.map((e) => e.seg_uid))
      .toEqual(r!.plan.edges.map((e) => e.seg_uid));
    expect(again!.walkM).toBeCloseTo(r!.walkM, 9);
  });
});

describe("③ 대체 접근 — 「경로 없음」으로 끝내지 않는다", () => {
  /** 대체 접근이 **실제로 걸리는** 첫 좌표. 없으면 전제가 깨진 것이다. */
  const found = (() => {
    for (const to of OTHER) {
      const r = solveRoute(graph, safe, fast, A, to);
      if (r?.alt) return { to, r };
    }
    return null;
  })();

  it("★ 못 닿는 곳을 찍으면 **닿는 가장 가까운 곳**에 댄다", () => {
    expect(found).not.toBeNull();
    expect(found!.r.plan.edges.length).toBeGreaterThan(0);
  });

  it("댄 곳에서 **걸어갈 거리**를 같이 낸다", () => {
    const { to, r } = found!;
    expect(r.walkM).toBeGreaterThan(0);
    // 그 수는 경로 끝 → 찍은 곳 **직선** 거리다 (머리말의 정의)
    const end = r.plan.coords[r.plan.coords.length - 1];
    expect(r.walkM).toBeCloseTo(distM(end, to), 6);
  });

  it("★ 두 경로의 **끝이 같다** — 갈리면 비교한 수가 거짓이 된다", () => {
    const { r } = found!;
    if (!r.fast) return;      // 빠른 쪽이 그 성분에 못 가면 null 이다
    expect(r.fast.nodes[r.fast.nodes.length - 1])
      .toBe(r.plan.nodes[r.plan.nodes.length - 1]);
  });
});

describe("④ 아주 먼 곳 — 지금 하는 일을 적는다", () => {
  it("경로는 서고, 걸어갈 거리가 크게 나온다", () => {
    const far: LngLat = [A[0] + 0.2, A[1]];
    const r = solveRoute(graph, safe, fast, A, far);
    expect(r).not.toBeNull();
    expect(r!.walkM).toBeGreaterThan(10_000);
  });
});

describe("⑤ reaches — 경로는 버리고 **닿는가**만 묻는다", () => {
  it("같은 성분이면 닿는다", () => {
    expect(reaches(graph, safe, A, B)).toBe(true);
  });

  it("★ 못 닿는 곳도 **대체 접근이 있으면** 참이다 — 그것이 이 함수의 뜻이다", () => {
    expect(reaches(graph, safe, A, OTHER[0])).toBe(true);
  });

  it("★ 인접리스트가 비면 거짓이다 — 빈 그물에 참을 내지 않는다", () => {
    const empty: Adjacency = new Map();
    expect(reaches(graph, empty, A, B)).toBe(false);
  });
});

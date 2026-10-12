/**
 * routeDerive.test.ts — 경로에서 **끌어내는** 것들. (DECISIONS §483)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 `domain/routeDerive.ts` 의 둘을 「시험이 이름으로도
 * 안 부른다」로 셌다 — `routeUids` · `splitAtHybridBoundary`.
 *
 * ★ `splitAtHybridBoundary` 는 **하이브리드 설계의 경계**다. 폭
 *   `requiredWidth(spec)` 이상은 상용 도로망에 있고 그 아래는 없다 —
 *   그 경계로 경로를 잘라 「여기는 SDK · 여기는 우리 그래프」를 가른다.
 *   그 자가 틀리면 상용 SDK 에 **없는 길**을 넘기거나, 있는 길을 우리가 짠다.
 *
 * ★ `routeUids` 는 **집합**이다. 경로가 같은 구간을 두 번 지나도(되돌아
 *   나오는 경로가 실측 21%) 한 번이어야 한다 — 화면 강조가 두 겹이 되면
 *   같은 길이 더 진하게 칠해진다.
 *
 * 밖    **경로가 옳은가는 안 본다** — `astar.test.ts` · `reroute.test.ts` 가
 *       그 축을 든다. 여기가 드는 것은 **끌어내는 꼴**이다.
 */
import { describe, expect, it } from "vitest";

import { routeUids, splitAtHybridBoundary } from "../src/domain/routeDerive";
import { requiredWidth } from "../src/domain/vehicle";
import type { GraphEdge, RoutePlan } from "../src/domain/types";
import { FL } from "./harness";

const { spec } = FL;
const NEED = requiredWidth(spec);

function edge(uid: string, widthM: number | null): GraphEdge {
  return {
    seg_uid: uid, verdict: "clear", width_min_m: widthM, length_m: 100,
    a: 0, b: 1, coords: [],
  } as GraphEdge;
}

const plan = (edges: GraphEdge[]) => ({ edges } as unknown as RoutePlan);

describe("① 지나는 구간 이름", () => {
  it("구간 이름을 모은다", () => {
    const got = routeUids(plan([edge("A", 5), edge("B", 5)]));
    expect([...got].sort()).toEqual(["A", "B"]);
  });

  it("★ 같은 구간을 두 번 지나면 **한 번**이다 — 되돌아 나오는 경로가 21% 다", () => {
    const got = routeUids(plan([edge("A", 5), edge("B", 5), edge("A", 5)]));
    expect(got.size).toBe(2);
  });

  it("빈 경로는 빈 집합이다", () => {
    expect(routeUids(plan([])).size).toBe(0);
  });
});

describe("② 하이브리드 경계", () => {
  it("★ 경계값을 발명하지 않았다 — `requiredWidth` 와 같은 수다", () => {
    // 이 전제가 깨지면 아래 시험들이 **다른 경계**를 미는 것이 된다.
    expect(NEED).toBeGreaterThan(0);
  });

  it("전부 넓으면 SDK 한 덩이다", () => {
    const got = splitAtHybridBoundary(plan([edge("A", NEED), edge("B", NEED + 2)]), spec);
    expect(got.sdk).toHaveLength(1);
    expect(got.sdk[0].map((e) => e.seg_uid)).toEqual(["A", "B"]);
    expect(got.own).toHaveLength(0);
  });

  it("전부 좁으면 우리 그래프 한 덩이다", () => {
    const got = splitAtHybridBoundary(plan([edge("A", NEED - 0.1), edge("B", 1)]), spec);
    expect(got.own).toHaveLength(1);
    expect(got.sdk).toHaveLength(0);
  });

  it("★ 번갈아 나오면 **덩이가 갈린다** — 한 덩이로 묶으면 SDK 에 없는 길이 섞인다", () => {
    const got = splitAtHybridBoundary(plan([
      edge("A", NEED + 1), edge("B", 1), edge("C", NEED + 1), edge("D", 1),
    ]), spec);
    expect(got.sdk.map((r) => r.map((e) => e.seg_uid))).toEqual([["A"], ["C"]]);
    expect(got.own.map((r) => r.map((e) => e.seg_uid))).toEqual([["B"], ["D"]]);
  });

  it("★ 마지막 덩이를 **흘리지 않는다**", () => {
    const got = splitAtHybridBoundary(plan([edge("A", 1), edge("B", NEED + 1)]), spec);
    const all = [...got.sdk.flat(), ...got.own.flat()].map((e) => e.seg_uid).sort();
    expect(all).toEqual(["A", "B"]);
  });

  it("★ 폭이 **모르는** 구간은 좁은 쪽이다 — 모르는 길을 상용에 넘기지 않는다", () => {
    const got = splitAtHybridBoundary(plan([edge("A", null)]), spec);
    expect(got.own).toHaveLength(1);
    expect(got.sdk).toHaveLength(0);
  });

  it("경계값 **그 자체**는 넓은 쪽이다 (포함)", () => {
    expect(splitAtHybridBoundary(plan([edge("A", NEED)]), spec).sdk).toHaveLength(1);
    expect(splitAtHybridBoundary(plan([edge("A", NEED - 1e-9)]), spec).own).toHaveLength(1);
  });

  it("빈 경로는 둘 다 빈다 — 빈 덩이를 만들지 않는다", () => {
    const got = splitAtHybridBoundary(plan([]), spec);
    expect(got.sdk).toHaveLength(0);
    expect(got.own).toHaveLength(0);
  });

  it("★ 모든 구간이 **정확히 한 덩이**에 든다 — 잃지도 겹치지도 않는다", () => {
    const edges = [edge("A", 9), edge("B", 1), edge("C", 1), edge("D", 9), edge("E", 9)];
    const got = splitAtHybridBoundary(plan(edges), spec);
    const seen = [...got.sdk.flat(), ...got.own.flat()].map((e) => e.seg_uid);
    expect(seen.sort()).toEqual(["A", "B", "C", "D", "E"]);
    expect(new Set(seen).size).toBe(seen.length);
  });
});

/**
 * adjacency.test.ts — 인접리스트가 **무엇을 기억하는가.** (DECISIONS §483)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 `domain/adjacency.ts` 의 세 함수를 「시험이 이름으로도
 * 안 부른다」로 셌다 — `adjacencySpec` · `usableEdges` · `isTight`. 셋은
 * 전부 **인접리스트에 딸린 기억**이고, 그 기억이 갈리면 §449(조율값을 다시
 * 읽어 휴리스틱이 과대추정) 와 같은 족의 사고가 난다.
 *
 * ★ 셋 다 `WeakMap` 이다. 그래서 묻는 것이 둘이다 —
 *     ① 구운 것을 **그대로** 돌려주는가
 *     ② **그 인접리스트에만** 딸리는가 (전역이면 옆 것이 앞의 답을 받는다)
 *
 * 밖    **비용이 옳은가는 안 본다** — `pressure.test.ts` · `rulesens.test.ts` ·
 *       `astar.test.ts` 가 그 축을 든다. 여기가 드는 것은 **딸린 기억** 하나다.
 */
import { describe, expect, it } from "vitest";

import {
  adjacencySpec, buildAdjacency, isTight, usableEdges,
} from "../src/domain/adjacency";
import type { VehicleSpec } from "../src/domain/types";
import { FL } from "./harness";

const { graph, spec } = FL;
const safe = buildAdjacency(graph, spec, false, "safe");

describe("① 구운 차를 기억한다", () => {
  it("구울 때 준 그 객체를 돌려준다", () => {
    expect(adjacencySpec(safe)).toBe(spec);
  });

  it("★ 다른 차로 구운 것은 **그 차**를 돌려준다 — 전역이면 섞인다", () => {
    const wide = { ...spec, width_m: 9.9 } as VehicleSpec;
    const other = buildAdjacency(graph, wide, false, "safe");
    expect(adjacencySpec(other)).toBe(wide);
    expect(adjacencySpec(safe)).toBe(spec);      // 앞의 것이 안 덮였다
  });

  it("★ 구운 것이 아닌 표에는 **모른다고 답한다**", () => {
    expect(adjacencySpec(new Map())).toBeUndefined();
  });
});

describe("② 실린 구간", () => {
  const u = usableEdges(safe);

  it("오름차순 · 중복 없음 · 그래프 안의 번호다", () => {
    expect(u.length).toBeGreaterThan(0);
    expect(new Set(u).size).toBe(u.length);
    for (let i = 1; i < u.length; i++) expect(u[i]).toBeGreaterThan(u[i - 1]);
    expect(u[u.length - 1]).toBeLessThan(graph.edges.length);
  });

  it("★ 통행 가능한 것만 실린다 — 전부 실리면 이 함수가 아무 말도 안 한다", () => {
    expect(u.length).toBeLessThan(graph.edges.length);
  });

  it("같은 배열을 돌려준다 — 매 틱 다시 만들면 그것이 병목이다", () => {
    expect(usableEdges(safe)).toBe(u);
  });

  it("★ 좁은 차로 구우면 **덜 실린다**", () => {
    const wide = { ...spec, width_m: 9.9 } as VehicleSpec;
    const few = usableEdges(buildAdjacency(graph, wide, false, "safe"));
    expect(few.length).toBeLessThan(u.length);
    expect(usableEdges(safe)).toBe(u);           // 앞의 것이 안 덮였다
  });
});

describe("③ 좁은 코너 — **지금은 꺼져 있다**", () => {
  /** 전이 쌍을 훑어 좁은 코너 수를 센다. 두 인접리스트를 같은 자로 잰다. */
  function count(adj: ReturnType<typeof buildAdjacency>) {
    let tight = 0;
    let seen = 0;
    for (const n of [...adj.keys()].slice(0, 400)) {
      const list = adj.get(n) ?? [];
      for (const x of list) {
        for (const y of list) {
          if (x.idx === y.idx) continue;
          seen++;
          if (isTight(graph, adj, x.idx, n, y.idx)) tight++;
        }
      }
    }
    return { tight, seen };
  }

  it("★ 실물 차 제원에는 회전반경 칸이 없어 **언제나 거짓**이다", () => {
    // 이것은 결함이 아니라 선언이다 — `vehicle_spec.json` 의
    // `turn_radius_verified` 가 false 이고, 미검증 값으로 화면이 말하지
    // 않는다(§81 · §86-5). 그래서 이 자는 **자료가 오면** 켜진다.
    expect((spec as unknown as Record<string, unknown>).turn_check_radius_m)
      .toBeUndefined();
    const { tight, seen } = count(safe);
    expect(seen).toBeGreaterThan(0);             // 전이를 실제로 훑었다
    expect(tight).toBe(0);
  });

  it("★ 반경을 주면 **켜진다** — 빈 그물이 아니다", () => {
    const withR = { ...spec, turn_check_radius_m: 12 } as unknown as VehicleSpec;
    const adj = buildAdjacency(graph, withR, false, "safe");
    const { tight, seen } = count(adj);
    expect(tight).toBeGreaterThan(0);
    // 전부 좁다고 하면 그것도 죽은 자다
    expect(tight).toBeLessThan(seen);
  });

  it("두 번 물어도 같은 답이다 — 캐시가 답을 바꾸지 않는다", () => {
    const withR = { ...spec, turn_check_radius_m: 12 } as unknown as VehicleSpec;
    const adj = buildAdjacency(graph, withR, false, "safe");
    const n = [...adj.keys()][0];
    const list = adj.get(n) ?? [];
    if (list.length < 2) return;
    const [x, y] = list;
    const first = isTight(graph, adj, x.idx, n, y.idx);
    expect(isTight(graph, adj, x.idx, n, y.idx)).toBe(first);
    // ★ 같은 전이를 **반경 없는** 인접리스트에 물으면 거짓이다 — 캐시가
    //   인접리스트에 딸려 있다는 뜻이고, 전역이면 여기가 참을 받는다
    expect(isTight(graph, safe, x.idx, n, y.idx)).toBe(false);
  });
});

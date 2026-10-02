/**
 * reroute.test.ts — **영상이 경로를 다시 내게 하는 규율.** (DECISIONS §366)
 *
 * ★ 이 파일이 지키는 것은 다섯 문장이다 —
 *     ① 영상이 없으면 **오늘과 한 글자도 다르지 않다**
 *     ② 좁아져도 지나면 재탐색이 **아니다**
 *     ③ 지나온 구간은 재탐색이 **아니다**
 *     ④ 같은 구간은 **더 좁아질 때만** 다시 쏜다
 *     ⑤ 발밑은 재탐색이 아니라 **정지·후진**이다
 *   다섯 다 **반대 방향까지** 민다 — 한 방향만 보면 「항상 null 인 함수」가
 *   전부 통과한다(§17-0 의 빈 그물).
 */
import { describe, expect, it } from "vitest";

import { fold, type CvReading } from "../src/domain/cv";
import {
  RETRIGGER_DROP_M, cvAhead, pruneReroute, rememberReroute, reroutePhrase,
  rerouteSignal, type RerouteMemory,
} from "../src/domain/reroute";
import { buildAdjacency } from "../src/domain/adjacency";
import type { GraphEdge, NaviGraph, RoutePlan, VehicleSpec } from "../src/domain/types";

const NOW = 1_800_000_000_000;
const NEED = 3.0;

function edge(uid: string, widthM: number | null, lenM = 100): GraphEdge {
  return { seg_uid: uid, a: 0, b: 1, length_m: lenM, width_min_m: widthM,
           verdict: "clear", ow: 0 } as GraphEdge;
}

/**
 * `A(100m) → B(100m) → C(100m)` 세 구간 경로.
 *
 * ★ `as unknown as RoutePlan` 이다. `reroute.ts` 가 읽는 것은 `edges` 하나이고
 *   `cost` · `byVerdict` · `rules` 를 합성으로 채우면 **그것들이 판단에 쓰이는
 *   것처럼 읽힌다.** 안 쓰는 칸은 안 채우고, 그 사실을 여기 적는다.
 */
function plan(...es: GraphEdge[]): RoutePlan {
  const lengthM = es.reduce((s, e) => s + (e.length_m ?? 0), 0);
  return { edges: es, forward: es.map(() => true), nodes: es.map((_, i) => i),
           coords: [], lengthM } as unknown as RoutePlan;
}

const P = plan(edge("A", 4.0), edge("B", 4.0), edge("C", 4.0));

function cvOf(...rs: Partial<CvReading>[]) {
  return fold(rs.map((x) => ({
    t: "cv" as const, seg: "B", passM: 2.1, at: NOW, cam: "C1", conf: 0.9, ...x,
  })), NOW);
}

describe("① 영상이 없으면 아무 일도 없다", () => {
  it("영상이 null 이면 null 이다", () => {
    expect(rerouteSignal({ plan: P, cv: null, requiredM: NEED, driven: 0 })).toBeNull();
  });
  it("빈 묶음이면 null 이다", () => {
    expect(rerouteSignal({ plan: P, cv: new Map(), requiredM: NEED, driven: 0 })).toBeNull();
  });
  it("경로가 없으면 null 이다", () => {
    expect(rerouteSignal({ plan: null, cv: cvOf({}), requiredM: NEED, driven: 0 })).toBeNull();
  });
  it("★ 그런데 영상이 **있으면** 쏜다 — 위 셋이 「항상 null」이 아님을 이 줄이 증명한다", () => {
    const s = rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 0 });
    expect(s?.seg_uid).toBe("B");
    expect(s?.kind).toBe("ahead");
  });
});

describe("② 막힘만 센다", () => {
  it("좁아져도 지나면 재탐색이 아니다", () => {
    expect(rerouteSignal({ plan: P, cv: cvOf({ passM: 3.4 }), requiredM: NEED, driven: 0 }))
      .toBeNull();
  });
  it("★ 원래 못 지나던 길은 **새로 막힌 것이 아니다**", () => {
    const Q = plan(edge("A", 4.0), edge("B", 2.0), edge("C", 4.0));
    expect(rerouteSignal({ plan: Q, cv: cvOf({ passM: 1.5 }), requiredM: NEED, driven: 0 }))
      .toBeNull();
  });
  it("정적 폭을 모르는 구간은 영상 하나로 막지 않는다 — 열지도 막지도 않는다", () => {
    const Q = plan(edge("A", 4.0), edge("B", null), edge("C", 4.0));
    expect(rerouteSignal({ plan: Q, cv: cvOf({}), requiredM: NEED, driven: 0 })).toBeNull();
  });
  it("경로를 바꿀 자격이 없는 측정(aging · 저신뢰 · 못 쟴)은 안 쏜다", () => {
    for (const x of [{ at: NOW - 200_000 }, { conf: 0.3 }, { passM: null }]) {
      expect(rerouteSignal({ plan: P, cv: cvOf(x), requiredM: NEED, driven: 0 })).toBeNull();
    }
  });
  it("차가 작으면 같은 측정이 막지 않는다 — 필요폭이 판단의 분모다", () => {
    expect(rerouteSignal({ plan: P, cv: cvOf({}), requiredM: 2.0, driven: 0 })).toBeNull();
  });
});

describe("③ 앞만 본다", () => {
  it("아직 안 간 구간은 쏜다", () => {
    expect(rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 50 })?.atM).toBe(100);
  });
  it("★ 이미 지난 구간은 **안 쏜다** — 지나온 길이 좁아진 것은 우리 일이 아니다", () => {
    expect(rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 250 })).toBeNull();
  });
  it("주행거리를 모르면(이탈) 다 본다 — 못 잰 것을 「지났다」로 치지 않는다", () => {
    expect(rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: null })?.seg_uid)
      .toBe("B");
  });
  it("막힌 것이 둘이면 **가까운 쪽**이다", () => {
    const cv = fold([
      { t: "cv", seg: "B", passM: 2.1, at: NOW, cam: "C1", conf: 0.9 },
      { t: "cv", seg: "C", passM: 1.2, at: NOW, cam: "C2", conf: 0.9 },
    ], NOW);
    const s = rerouteSignal({ plan: P, cv, requiredM: NEED, driven: 0 });
    expect(s?.seg_uid).toBe("B");
    // ★ 반대 방향 — 가까운 쪽이 풀리면 먼 쪽이 나온다. 「늘 B」가 아니다
    const cv2 = fold([
      { t: "cv", seg: "B", passM: 3.5, at: NOW, cam: "C1", conf: 0.9 },
      { t: "cv", seg: "C", passM: 1.2, at: NOW, cam: "C2", conf: 0.9 },
    ], NOW);
    expect(rerouteSignal({ plan: P, cv: cv2, requiredM: NEED, driven: 0 })?.seg_uid).toBe("C");
  });
});

describe("④ 이력 — 깜빡임이 재탐색이 되면 안 된다", () => {
  it("쏜 뒤 같은 값이 또 와도 **다시 안 쏜다**", () => {
    const mem: RerouteMemory = new Map();
    const s = rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 0, mem })!;
    rememberReroute(mem, s);
    expect(rerouteSignal({ plan: P, cv: cvOf({ at: NOW - 1000 }), requiredM: NEED, driven: 0, mem }))
      .toBeNull();
  });
  it("★ **더 좁아지면** 다시 쏜다 — 2.1m 와 0.8m 는 같은 사실이 아니다", () => {
    const mem: RerouteMemory = new Map();
    rememberReroute(mem, rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 0, mem })!);
    const again = rerouteSignal({
      plan: P, cv: cvOf({ passM: 2.1 - RETRIGGER_DROP_M - 0.01 }), requiredM: NEED, driven: 0, mem });
    expect(again?.passM).toBeCloseTo(1.79, 2);
  });
  it("잡음만큼(문턱 안) 좁아진 것으로는 안 쏜다", () => {
    const mem: RerouteMemory = new Map();
    rememberReroute(mem, rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 0, mem })!);
    expect(rerouteSignal({
      plan: P, cv: cvOf({ passM: 2.1 - RETRIGGER_DROP_M + 0.01 }), requiredM: NEED, driven: 0, mem }))
      .toBeNull();
  });
  it("★ 보기만 해서는 **기억에 안 남는다** — 판단과 기록이 갈려 있다", () => {
    const mem: RerouteMemory = new Map();
    expect(rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 0, mem })).not.toBeNull();
    expect(rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 0, mem })).not.toBeNull();
    expect(mem.size).toBe(0);
  });
  it("경로가 바뀌면 **경로 밖만** 비운다 — 다 비우면 재탐색이 무한히 돈다", () => {
    const mem: RerouteMemory = new Map([["B", 2.1], ["Z", 1.0]]);
    pruneReroute(mem, P);
    expect([...mem.keys()]).toEqual(["B"]);
    pruneReroute(mem, null);
    expect(mem.size).toBe(0);
  });
});

describe("⑤ 발밑과 앞은 처방이 다르다", () => {
  it("밟고 있는 구간이 막히면 `underfoot` 이다", () => {
    const s = rerouteSignal({
      plan: P, cv: cvOf({}), requiredM: NEED, driven: 150, currentUid: "B" });
    expect(s?.kind).toBe("underfoot");
  });
  it("★ 발밑은 **이미 지나도** 산다 — 앞만 보는 규율의 예외다", () => {
    const s = rerouteSignal({
      plan: P, cv: cvOf({}), requiredM: NEED, driven: 999, currentUid: "B" });
    expect(s?.kind).toBe("underfoot");
  });
  it("발밑과 앞이 같이 막히면 **발밑이 먼저다** — 앞은 돌아갈 수 있다", () => {
    const cv = fold([
      { t: "cv", seg: "B", passM: 2.1, at: NOW, cam: "C1", conf: 0.9 },
      { t: "cv", seg: "C", passM: 1.2, at: NOW, cam: "C2", conf: 0.9 },
    ], NOW);
    expect(rerouteSignal({ plan: P, cv, requiredM: NEED, driven: 0, currentUid: "C" })?.kind)
      .toBe("underfoot");
  });
  it("문구가 처방까지 말한다 — 「다시 찾습니다」와 「후진하십시오」", () => {
    const ahead = rerouteSignal({ plan: P, cv: cvOf({}), requiredM: NEED, driven: 0 })!;
    expect(reroutePhrase(ahead)).toContain("경로를 다시 찾습니다");
    const under = rerouteSignal({
      plan: P, cv: cvOf({}), requiredM: NEED, driven: 0, currentUid: "B" })!;
    expect(reroutePhrase(under)).toContain("후진");
    expect(reroutePhrase(under)).toContain("2.1미터");
  });
});

// ── 비용 쪽 — 같은 문으로 들어가는가 ──────────────────────────────
describe("영상 폭이 **인접리스트**에 들어간다", () => {
  // ★ 필요폭은 `vehicle.requiredWidth` 가 **전폭 + 여유**로 센다 — 상수가 아니다.
  //   처음에 `required_width_m: 3.0` 이라는 **없는 키**를 줬고 `clearance_m` 이
  //   빠져 요구폭이 `NaN` 이 됐다. `2.1 < NaN` 은 거짓이라 **셋이 조용히 통과했다.**
  const spec = { width_m: 2.5, clearance_m: 0.5 } as VehicleSpec;
  const graph = {
    nodes: [[126.9, 35.1], [126.901, 35.1], [126.902, 35.1]],
    edges: [
      { seg_uid: "A", a: 0, b: 1, length_m: 100, width_min_m: 4.0, verdict: "clear", ow: 0 },
      { seg_uid: "B", a: 1, b: 2, length_m: 100, width_min_m: 4.0, verdict: "clear", ow: 0 },
    ],
    turns: [],
  } as unknown as NaviGraph;

  const uids = (adj: ReturnType<typeof buildAdjacency>) => {
    const s = new Set<string>();
    for (const l of adj.values()) for (const x of l) s.add(x.edge.seg_uid);
    return [...s].sort();
  };

  it("영상이 없으면 둘 다 실린다 — 퇴행이 무손실이다", () => {
    expect(uids(buildAdjacency(graph, spec))).toEqual(["A", "B"]);
  });
  it("★ 영상이 필요폭 아래로 좁히면 그 구간이 **빠진다**", () => {
    const cv = fold([{ t: "cv", seg: "B", passM: 2.1, at: NOW, cam: "C1", conf: 0.9 }], NOW);
    expect(uids(buildAdjacency(graph, spec, false, "safe", undefined, undefined, null, cv)))
      .toEqual(["A"]);
  });
  it("좁히되 아직 지나면 **안 빠진다**", () => {
    const cv = fold([{ t: "cv", seg: "B", passM: 3.4, at: NOW, cam: "C1", conf: 0.9 }], NOW);
    expect(uids(buildAdjacency(graph, spec, false, "safe", undefined, undefined, null, cv)))
      .toEqual(["A", "B"]);
  });
  it("★ 영상이 **넓게** 재도 원래 좁은 구간은 안 열린다", () => {
    const narrow = {
      ...graph,
      edges: [graph.edges[0], { ...graph.edges[1], width_min_m: 2.0 }],
    } as NaviGraph;
    const cv = fold([{ t: "cv", seg: "B", passM: 9.9, at: NOW, cam: "C1", conf: 0.9 }], NOW);
    expect(uids(buildAdjacency(narrow, spec, false, "safe", undefined, undefined, null, cv)))
      .toEqual(["A"]);
  });
  it("「빠른 경로」에도 똑같이 건다 — 못 지나는 길은 빠른 길이 아니다", () => {
    const cv = fold([{ t: "cv", seg: "B", passM: 2.1, at: NOW, cam: "C1", conf: 0.9 }], NOW);
    expect(uids(buildAdjacency(graph, spec, false, "fastest", undefined, undefined, null, cv)))
      .toEqual(["A"]);
  });
});

// ── 말할 거리를 고르는 자리 ───────────────────────────────────────
describe("앞 구간 소견 — 말은 막히지 않은 것도 한다", () => {
  it("영상이 없으면 null 이다", () => {
    expect(cvAhead(P, null, 0, 400, NEED)).toBeNull();
    expect(cvAhead(null, cvOf({}), 0, 400, NEED)).toBeNull();
  });
  it("★ 막히지 않아도 **말할 것이 있다** — 재탐색과 다른 물음이다", () => {
    const got = cvAhead(P, cvOf({ passM: 3.4 }), 0, 400, NEED);
    expect(got?.view.sayM).toBe(3.4);
    expect(got?.blocked).toBe(false);
  });
  it("막혔으면 막혔다고 든다", () => {
    expect(cvAhead(P, cvOf({}), 0, 400, NEED)?.blocked).toBe(true);
  });
  it("창 밖이면 안 든다 — 400m 앞 폭을 지금 말하면 도착할 때 잊는다", () => {
    expect(cvAhead(P, cvOf({}), 0, 50, NEED)).toBeNull();
  });
  it("이미 지난 구간은 안 든다", () => {
    expect(cvAhead(P, cvOf({}), 250, 400, NEED)).toBeNull();
  });
  it("★ aging 측정은 **말은 하고** 경로는 안 바꾼다 — 두 함수가 갈린다", () => {
    const old = cvOf({ at: NOW - 100_000 });
    expect(cvAhead(P, old, 0, 400, NEED)?.view.sayM).toBe(2.1);
    expect(cvAhead(P, old, 0, 400, NEED)?.blocked).toBe(false);
    expect(rerouteSignal({ plan: P, cv: old, requiredM: NEED, driven: 0 })).toBeNull();
  });
  it("못 쟀으면(null) 말할 것이 없다", () => {
    expect(cvAhead(P, cvOf({ passM: null }), 0, 400, NEED)).toBeNull();
  });
});

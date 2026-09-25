/**
 * test/pressure.test.ts — 점유 압력 배선이 **경로를 안 바꾸면서** 사는가.
 *
 * ── 무엇을 보는가 ───────────────────────────────────────────────
 *   ① 계수가 0 이면 배수가 **정확히 1** 이다 — 즉 지금 경로가 안 움직인다
 *   ② **결측을 0 으로 접지 않는다** — `null` · `undefined` 는 `0` 과 다르게 센다
 *   ③ 계수를 켜면 **실제로 는다** — 빈 그물이 아니다(0 이라 항상 통과하는 시험 방지)
 *   ④ `countText` 가 「모름」 과 「0건」 을 가른다 — 종전 결함의 회귀 시험
 *   ⑤ 실제 발행물에서 `park` · `ecam` 이 0 을 **빼지 않고** 싣는다
 *   ⑥ 인접리스트 비용이 압력 배선 전후로 같다(계수 0 일 때)
 *
 * ★ ③ 이 요점이다. 계수가 0 이라 ①②만 보면 **아무것도 안 하는 코드도 통과한다.**
 *   배선이 죽었는지 살았는지는 켜 봐야 안다.
 */
import { FL, ok, test } from "./harness";
import {
  buildHazardIndex, countText, pressureFactor, pressureIsInert, pressureParts,
} from "../src/domain/pressure";
import { TUNING } from "../src/domain/vehicle";
import { buildAdjacency, dirCost } from "../src/domain/adjacency";
import type { GraphEdge } from "../src/domain/types";

const HZ = { speedbump: 3, speedcam: 2, child_zone: 1, senior_zone: 1 };

function edge(over: Partial<GraphEdge> = {}): GraphEdge {
  return {
    seg_uid: "T-0", verdict: "clear", width_min_m: 5, length_m: 100,
    a: 0, b: 1, coords: [[126.92, 35.14], [126.921, 35.141]], ...over,
  };
}

test("압력 계수가 전부 0 이다 — 근거 없는 값을 새로 만들지 않았다", () => {
  ok(pressureIsInert(TUNING), "TUNING 의 압력 계수가 0 이 아니다. "
    + "값을 넣으려면 PLAN §1-27 측정 대장에 행을 먼저 세운다(가드 6)");
});

test("계수 0 이면 배수가 정확히 1 — 경로가 한 치도 안 움직인다", () => {
  for (const e of [edge(), edge({ park: 9999 }), edge({ park: 0, ecam: 7 })]) {
    const f = pressureFactor(e, HZ, TUNING);
    ok(f === 1, `배수가 1 이 아니다 — ${f}`);
  }
});

test("결측을 0 으로 접지 않는다", () => {
  ok(pressureParts(edge({ park: 0, ecam: 0 }), HZ).unknown === 0, "세어진 0 을 모름으로 센다");
  ok(pressureParts(edge({ park: null, ecam: 0 }), HZ).unknown === 1, "null 을 안 센다");
  ok(pressureParts(edge({ park: 0, ecam: 0 }), undefined).unknown === 1, "주변 사정 결측을 안 센다");
  // 옛 발행물 — 칸이 아예 없다. 0 이 아니라 모름이다.
  const old = pressureParts(edge(), undefined);
  ok(old.unknown === 3 && old.park === null, `옛 발행물을 0 으로 읽는다 — ${JSON.stringify(old)}`);
});

test("계수를 켜면 는다 — 배선이 살아 있다(빈 그물 방지)", () => {
  const on = { ...TUNING, parkPer1000: 1, ecamPerSite: 1, speedbumpEach: 1, speedcamEach: 1, zoneEach: 1 };
  ok(!pressureIsInert(on), "켠 계수를 0 으로 본다");
  // 단속 2,000건(=2.0) + 카메라 3 + 방지턱 3 + 카메라 2 + 보호구역 2 → 1 + 12
  const f = pressureFactor(edge({ park: 2000, ecam: 3 }), HZ, on);
  ok(Math.abs(f - 13) < 1e-9, `증거가 비용에 안 닿는다 — ${f}`);
  // 결측은 켜도 아무것도 더하지 않는다. 벌하지도 깎지도 않는다.
  ok(pressureFactor(edge({ park: null, ecam: null }), undefined, on) === 1,
    "모르는 증거로 벌을 준다");
});

test("countText 가 모름과 0 을 가른다 — 종전 결함의 회귀", () => {
  ok(countText(null, "건") === "모름", "null 을 0 처럼 찍는다");
  ok(countText(undefined, "건") === "모름", "undefined 를 0 처럼 찍는다");
  ok(countText(0, "건") === "0건", "세어진 0 을 「없음」 으로 접는다");
  ok(countText(1234, "건") === "1,234건", `천단위가 안 붙는다 — ${countText(1234, "건")}`);
});

test("발행물이 park · ecam 의 0 을 빼지 않고 싣는다", () => {
  const miss = FL.graph.edges.filter((e) => e.park === undefined || e.ecam === undefined);
  ok(miss.length === 0, `칸이 빠진 구간 ${miss.length}개 — 0 을 빼면 결측과 같은 모습이 된다`);
  const zero = FL.graph.edges.filter((e) => e.park === 0).length;
  ok(zero > 0, "0 인 구간이 하나도 없다 — 0 을 빼서 발행하던 때로 돌아갔나");
  // 0 의 강도를 발행물이 스스로 든다.
  ok((FL.graph.counts.ecam_unplaced_sites ?? 0) > 0,
    "못 붙은 카메라 지점 수가 없다 — 0 을 「없다」로 읽게 된다");
});

test("압력 배선이 지금 인접리스트 비용을 안 바꾼다", () => {
  const idx = buildHazardIndex(FL.graph, null);
  const withHz = buildAdjacency(FL.graph, FL.spec, false, "safe", TUNING, undefined, idx);
  const without = buildAdjacency(FL.graph, FL.spec, false, "safe", TUNING, undefined, null);
  let n = 0;
  FL.graph.edges.forEach((e, i) => {
    for (const fwd of [true, false]) {
      const a = dirCost(withHz, e, i, fwd), b = dirCost(without, e, i, fwd);
      ok(a === b || (!Number.isFinite(a) && !Number.isFinite(b)), `${e.seg_uid} 비용이 갈렸다 ${a} ≠ ${b}`);
      n++;
    }
  });
  ok(n > 1000, `대조한 방향이 ${n}개뿐이다`);
});

test("주변 사정 색인이 구간에 붙는다 — 붙을 것이 있으면 붙는다", () => {
  const empty = buildHazardIndex(FL.graph, null);
  ok(empty.size === 0, "자료가 없는데 색인이 찼다 — 결측이 「하나도 없다」로 바뀐다");
  // 실제 구간 하나 위에 점 하나를 놓고 붙는지 본다. 합성이라 발행물에 안 기댄다.
  const e = FL.graph.edges.find((x) => x.coords.length >= 2)!;
  const ctx = {
    type: "FeatureCollection" as const,
    features: [{
      type: "Feature" as const, properties: { kind: "speedbump" },
      geometry: { type: "Point" as const, coordinates: e.coords[0] },
    }],
  };
  const idx = buildHazardIndex(FL.graph, ctx as never);
  ok(idx.get(e.seg_uid)!.speedbump >= 1, "구간 좌표 위의 과속방지턱이 안 붙는다");
  ok(idx.size === FL.graph.edges.length, "색인이 구간 전부를 안 든다");
});

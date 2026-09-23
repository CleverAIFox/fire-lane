/**
 * test/clearance.test.ts — 여유폭 · 사유 문장 · 「같은 경로」 표기.  (DECISIONS §219 → §220)
 *
 * ★ 여기서 무는 것은 **화면이 말하는 수가 경로가 내는 가부와 같은가** 다. 여유폭이
 *   음수인데 경로가 그리로 안내하면(또는 그 반대면) 관제사가 색을 못 믿는다 —
 *   그 대조를 실제 발행물(`navi_graph.json` · `fleet.json`) 전 구간에 돌린다.
 */
import { FL, test, ok } from "./harness";
import fleetJson from "../../data/fleet.json";
import {
  CLEARANCE_BAND_ORDER, CLEARANCE_WIDE_M, clearanceBand, clearanceCounts, clearanceM,
  edgeClearance, fmtClearance,
} from "../src/domain/clearance";
import { TUNING, edgeCost, requiredWidth } from "../src/domain/vehicle";
import { CLEARANCE_SCALE, segmentReason, widthLine } from "../src/ui/clearanceMeaning";
import { GRAY_REASON } from "../src/ui/verdictMeaning";
import {
  SAME_ROUTE_TITLE, compareKind, routeStats, sameRoute,
} from "../src/domain/compare";
import { buildAdjacency, findRoute } from "../src/domain/graph";
import type { Fleet, GraphEdge, VehicleSpec } from "../src/domain/types";

const { graph, spec } = FL;
const fleet = fleetJson as unknown as Fleet;

/** 편성 한 대의 제원 — `useFleet` 이 만드는 것과 같은 모양 */
function specOf(id: string): VehicleSpec {
  const v = fleet.vehicles.find((x) => x.id === id)!;
  return { ...spec, kind: v.label, width_m: v.width_m, clearance_m: v.clearance_m };
}

// ── 1. 뺄셈 ────────────────────────────────────────────────────────

test("여유폭 = 최소 유효폭 − 요구폭(전폭 + 필요 여유) — 편성 전 차종", () => {
  ok(fleet.vehicles.length >= 3, "편성이 너무 적다 — 시험 전제가 깨졌다");
  for (const v of fleet.vehicles) {
    const s = specOf(v.id);
    const need = requiredWidth(s);
    // 발행물이 이미 낸 요구폭과 화면의 뺄셈이 같은 수를 쓰는가
    ok(Math.abs(need - v.required_width_m) < 1e-9,
       `${v.id} 요구폭 ${need} vs 발행 ${v.required_width_m}`);
    ok(Math.abs(need - (v.width_m + v.clearance_m)) < 1e-9, `${v.id} 요구폭이 전폭+여유가 아니다`);
    ok(Math.abs(clearanceM(s, 4.0)! - (4.0 - need)) < 1e-9, `${v.id} 여유폭 뺄셈이 틀렸다`);
  }
});

test("폭을 모르면 여유폭도 없다 — 0 으로 떨어뜨리지 않는다", () => {
  const s = specOf(fleet.default);
  ok(clearanceM(s, null) === null, "폭 null 인데 수를 냈다");
  ok(clearanceM(s, undefined) === null, "폭 undefined 인데 수를 냈다");
  const c = edgeClearance({ width_min_m: null }, s);
  ok(c.m === null && c.band === "unknown", `폭 미상이 ${c.band}`);
  ok(fmtClearance(null) === "—", "폭 미상을 0.0m 로 적었다");
  ok(CLEARANCE_SCALE.unknown.color !== CLEARANCE_SCALE.neg.color, "폭 미상과 음수가 같은 색이다");
});

test("여유폭 4단 — 경계는 0 · TUNING.tightMarginM · CLEARANCE_WIDE_M", () => {
  const t = TUNING.tightMarginM;
  ok(clearanceBand(-0.01) === "neg", "-0.01 이 음수가 아니다");
  ok(clearanceBand(-3) === "neg", "-3 이 음수가 아니다");
  ok(clearanceBand(0) === "tight", "0 이 서행 구간이 아니다");
  ok(clearanceBand(t - 0.01) === "tight", `${t} 바로 아래가 서행이 아니다`);
  ok(clearanceBand(t) === "mid", `${t} 가 서행에 남았다`);
  ok(clearanceBand(CLEARANCE_WIDE_M - 0.01) === "mid", "1m 바로 아래가 중간이 아니다");
  ok(clearanceBand(CLEARANCE_WIDE_M) === "wide", "1m 가 넉넉이 아니다");
  ok(clearanceBand(null) === "unknown", "null 이 폭 미상이 아니다");
  // 범례가 도는 순서에 빠진 구간이 없다
  for (const k of ["neg", "tight", "mid", "wide", "unknown"] as const) {
    ok(CLEARANCE_BAND_ORDER.includes(k), `범례 순서에 ${k} 가 없다`);
    ok(CLEARANCE_SCALE[k].color.startsWith("#"), `${k} 색이 없다`);
  }
});

test("부호를 반드시 보인다 — 음수가 요지다", () => {
  ok(fmtClearance(-0.6) === "-0.6m", fmtClearance(-0.6));
  ok(fmtClearance(0) === "+0.0m", fmtClearance(0));
  ok(fmtClearance(1.25) === "+1.3m", fmtClearance(1.25));
});

// ── 2. 화면의 수 ↔ 경로의 가부 ────────────────────────────────────

test("여유폭이 음수인 구간이 실제로 있고, 그 구간으로는 경로가 안 선다", () => {
  const s = specOf(fleet.default);
  let neg = 0;
  for (const e of graph.edges) {
    const c = edgeClearance(e, s);
    if (c.m == null) continue;
    const cost = edgeCost(s, e.length_m, e.width_min_m, e.verdict, null, false);
    if (c.m < 0) {
      neg++;
      ok(!Number.isFinite(cost),
         `여유폭 ${fmtClearance(c.m)} 인데 경로가 쓴다 — ${e.seg_uid} ${e.seg_label ?? ""}`);
    } else if (e.verdict !== "blocked" && (e.length_m ?? 0) > 0) {
      ok(Number.isFinite(cost),
         `여유폭 ${fmtClearance(c.m)} 인데 경로가 막는다 — ${e.seg_uid} ${e.seg_label ?? ""}`);
    }
  }
  ok(neg > 0, "여유폭 음수 구간이 하나도 없다 — 음수 표기를 시험할 데이터가 없다");
});

test("구간별 개수의 합이 전 구간이다 — 범례가 빠뜨리는 구간이 없다", () => {
  const s = specOf(fleet.default);
  const c = clearanceCounts(graph.edges, s);
  const sum = CLEARANCE_BAND_ORDER.reduce((a, k) => a + c[k], 0);
  ok(sum === graph.edges.length, `합 ${sum} vs 구간 ${graph.edges.length}`);
  ok(c.neg > 0 && c.wide > 0, `한쪽으로 쏠렸다 — ${JSON.stringify(c)}`);
});

// ── 3. 사유 문장 ──────────────────────────────────────────────────

const S = specOf("pump-js");
const NEED = requiredWidth(S);

function reason(e: Partial<GraphEdge> & Pick<GraphEdge, "verdict">) {
  return segmentReason({ width_min_m: null, unknown_reason: null, ...e }, S);
}

test("사유 — 빨강은 어느 폭이 얼마나 모자란지 적는다", () => {
  const r = reason({ verdict: "blocked", width_min_m: 2.4 })!;
  ok(r != null, "통행 불가인데 사유가 없다");
  ok(r.head.includes("통행 불가") && r.head.includes("폭"), r.head);
  ok(r.detail.includes("최소 유효폭 2.4m"), r.detail);
  ok(r.detail.includes(`요구폭 ${NEED.toFixed(1)}m`), r.detail);
  ok(r.detail.includes(`${S.width_m}`) && r.detail.includes(`${S.clearance_m}`), r.detail);
  ok(r.detail.includes("여유폭 -0.6m"), r.detail);
  ok(!!r.action, "관제사가 취할 조치가 비었다");
});

test("사유 — 폭을 못 낸 빨강은 폭 미상이라고 말한다", () => {
  const r = reason({ verdict: "blocked", width_min_m: null })!;
  ok(r.head.includes("폭 미상"), r.head);
  ok(!r.detail.includes("NaN") && !r.detail.includes("null"), r.detail);
  ok(!!r.action, "폭 미상인데 조치가 없다");
});

test("사유 — 회색은 `unknown_reason` 넷을 그대로 말한다", () => {
  for (const k of Object.keys(GRAY_REASON)) {
    const r = reason({ verdict: "unknown", width_min_m: 3.2, unknown_reason: k })!;
    ok(r.head.includes(GRAY_REASON[k].short), `${k}: ${r.head}`);
    ok(r.head.includes("영상판정 불가"), `${k}: ${r.head}`);
    ok(!!r.action, `${k}: 조치가 없다`);
  }
  // 모르는 사유가 와도 그 문자열을 잃지 않는다
  const odd = reason({ verdict: "unknown", width_min_m: 3.2, unknown_reason: "새_사유" })!;
  ok(odd.head.includes("새_사유"), odd.head);
  // 사유가 아예 없는 회색도 말은 한다
  const bare = reason({ verdict: "unknown", width_min_m: 3.2 })!;
  ok(bare.head.includes("영상판정 불가"), bare.head);
});

test("사유 — 주황은 여유폭 부호에 따라 다른 조치를 낸다", () => {
  const tight = reason({ verdict: "needs_cv", width_min_m: NEED - 0.4 })!;
  ok(tight.head.includes("요구폭 미만"), tight.head);
  const ok0 = reason({ verdict: "needs_cv", width_min_m: NEED + 0.2 })!;
  ok(ok0.head.includes(TUNING.tightMarginM.toFixed(1)), ok0.head);
  const wide = reason({ verdict: "needs_cv", width_min_m: NEED + 4 })!;
  ok(wide.head.includes("영상판정 대상"), wide.head);
  ok(tight.action !== ok0.action && ok0.action !== wide.action, "세 경우가 같은 조치를 낸다");
});

test("사유 — 초록이고 여유가 넉넉하면 적지 않는다 (조치가 없으면 뺀다)", () => {
  ok(reason({ verdict: "clear", width_min_m: NEED + 4 }) === null, "취할 조치가 없는데 줄을 냈다");
  const tight = reason({ verdict: "clear", width_min_m: NEED + 0.2 })!;
  ok(tight != null && !!tight.action, "여유 0.5m 미만인데 아무 말이 없다");
});

test("사유 — 실제 발행물의 빨강 · 주황 · 회색은 전부 사유와 조치를 낸다", () => {
  let n = 0;
  for (const e of graph.edges) {
    if (e.verdict === "clear") continue;
    const r = segmentReason(e, S);
    ok(r != null, `${e.seg_uid} (${e.verdict}) 사유가 없다`);
    ok(r!.head.length > 0 && r!.detail.length > 0, `${e.seg_uid} 빈 사유`);
    ok(!!r!.action, `${e.seg_uid} 조치가 없다`);
    n++;
  }
  ok(n > 500, `사유를 낸 구간이 ${n}개뿐`);
});

test("어느 폭을 썼는지 말한다 — 「최소 유효폭」", () => {
  const line = widthLine({ width_min_m: 5.5 }, S);
  ok(line.includes("최소 유효폭 5.5m"), line);
  ok(line.includes("여유폭 +2.5m"), line);
  ok(widthLine({ width_min_m: null }, S).includes("값이 없다"), widthLine({ width_min_m: null }, S));
});

// ── 4. 「안전하면서 빠른 추천 경로」 ───────────────────────────────

test("경로 비교 — 같으면 same · 없으면 single · 다르면 two", () => {
  const safeAdj = buildAdjacency(graph, S, false, "safe");
  const fastAdj = buildAdjacency(graph, S, false, "fastest");
  const nodes = [...safeAdj.keys()].sort((a, b) => a - b);
  let same = 0;
  let two = 0;
  for (let i = 0; i < nodes.length && (same < 1 || two < 1); i += 7) {
    const a = findRoute(graph, safeAdj, nodes[0], nodes[i]);
    const b = findRoute(graph, fastAdj, nodes[0], nodes[i]);
    if (!a || !b) continue;
    const k = compareKind(a, b);
    ok(k === (sameRoute(a, b) ? "same" : "two"), "compareKind 가 sameRoute 와 갈렸다");
    if (k === "same") same++; else two++;
    ok(compareKind(a, a) === "same", "자기 자신과 다르다고 했다");
    ok(compareKind(a, null) === "single", "둘째 경로가 없는데 same 이라 했다");
    ok(compareKind(null, b) === "single", "첫째 경로가 없는데 same 이라 했다");
  }
  ok(same > 0, "같은 경로가 한 쌍도 안 나왔다 — 표기를 시험할 데이터가 없다");
  ok(two > 0, "다른 경로가 한 쌍도 안 나왔다");
});

test("같을 때 쓰는 이름은 멘토링이 정한 그 말이다", () => {
  ok(SAME_ROUTE_TITLE === "안전하면서 빠른 추천 경로", SAME_ROUTE_TITLE);
});

test("경로 비교 수치 — 길이 · 통행 불가 경유 · 규칙 경고", () => {
  const adj = buildAdjacency(graph, S, false, "safe");
  const nodes = [...adj.keys()].sort((a, b) => a - b);
  let checked = 0;
  for (let i = 1; i < nodes.length && checked < 12; i += 11) {
    const p = findRoute(graph, adj, nodes[0], nodes[i]);
    if (!p) continue;
    checked++;
    const st = routeStats(p);
    ok(st.lengthM === p.lengthM, "길이가 경로와 다르다");
    ok(st.ruleCount === p.rules.length, "규칙 경고 수가 경로와 다르다");
    // A* 가 `blocked` 를 막으므로 0 이어야 한다. 0 이 아니면 그 자체가 큰 사건이다
    ok(st.blockedCount === 0, `안전 경로가 통행 불가 ${st.blockedCount}곳을 지난다`);
    const unc = p.edges.filter((e) => e.verdict === "needs_cv" || e.verdict === "unknown");
    ok(st.uncertainCount === unc.length, "확인 구간 수가 안 맞는다");
    const w = p.edges.map((e) => e.width_min_m).filter((x): x is number => x != null);
    ok(st.minWidthM === (w.length ? Math.min(...w) : null), "최소 유효폭이 안 맞는다");
  }
  ok(checked > 0, "경로가 하나도 안 섰다");
});

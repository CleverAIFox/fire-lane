/**
 * domain/rules.ts — 통행 규칙(일방통행 · 회전 금지)을 비용과 경고로 바꾼다.  (DECISIONS §215-1)
 *
 * ── 정책 (사용자 결정 2026-09-22) ─────────────────────────────────
 * 소방차는 규칙을 **어길 수는 있으나 피한다.** 그래서 경로에서 빼지 않고 비용을 올린다.
 * 돌아갈 길이 있으면 그리로 가고, 규칙을 어겨야만 닿는 곳이면 어기되 화면과 음성으로
 * 알린다. 빼 버리면 역주행으로만 닿는 집이 「경로 없음」이 되고, 그대로 두면 역주행
 * 경로를 아무 말 없이 낸다 — 둘 다 현장에서 틀린다.
 *
 * ── 방향을 대부분 모른다 ─────────────────────────────────────────
 * `navi_graph.json` 의 일방통행 57구간 중 방향이 확정된 것은 1곳이다. 1:1000 중심선은
 * 일방통행 **여부**만 있고 방향이 없다(발행 `publish_navi._oneway` 참조). 모르는 곳은
 * **양쪽 다** `ONEWAY_UNKNOWN` 만큼 불리하게 본다 — 어느 쪽이 역주행인지 모르므로.
 *
 * ── ★ 아래 배수는 **근거 없는 가정값**이다 ─────────────────────────
 * 측정한 값이 아니다. 「돌아갈 길이 이만큼 길어도 규칙을 지킨다」 는 정책의 크기다.
 *   WRONG_WAY 4      역주행 100m 를 정상 400m 로 본다 — 웬만한 우회는 택한다
 *   ONEWAY_UNKNOWN 1.5  방향 모름 100m 를 150m 로 — 비슷한 길이면 피한다
 *   TURN_BAN_M 200   금지 회전 한 번을 200m 우회와 같게 본다
 * 현장 검증 전까지 이 숫자를 근거로 인용하지 않는다. 배수가 1 이상이라 A* 휴리스틱의
 * admissible 성질은 유지된다(`graph.ts findRoute`).
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 */

import type { GraphEdge, NaviGraph, RoutePlan, RuleWarning, VehicleSpec } from "./types";
import { tightTurn } from "./turning";

export type { RuleWarning };

export const WRONG_WAY = 4;
export const ONEWAY_UNKNOWN = 1.5;
export const TURN_BAN_M = 200;

/** `navi_graph.json.turns[][3]` — 표준노드링크 TURN_TYPE */
export const TURN_BAN_WORD: Record<number, string> = {
  3: "회전 금지", 101: "좌회전 금지", 102: "직진 금지", 103: "우회전 금지",
};

/** 엣지를 `forward`(a→b) 방향으로 지날 때 곱할 배수. */
export function directionFactor(e: GraphEdge, forward: boolean): number {
  switch (e.ow) {
    case 1: return forward ? 1 : WRONG_WAY;
    case -1: return forward ? WRONG_WAY : 1;
    case 2: return ONEWAY_UNKNOWN;
    default: return 1;
  }
}

/** 이 방향이 **알려진** 역주행인가. 방향 모름(2)은 역주행이 아니라 모름이다. */
export function isWrongWay(e: GraphEdge, forward: boolean): boolean {
  return (e.ow === 1 && !forward) || (e.ow === -1 && forward);
}

const TURN_CACHE = new WeakMap<NaviGraph, Map<string, number>>();

/** `(들어온 엣지, 노드, 나갈 엣지)` → TURN_TYPE. 없으면 undefined */
export function turnBan(graph: NaviGraph, inIdx: number, node: number, outIdx: number): number | undefined {
  let m = TURN_CACHE.get(graph);
  if (!m) {
    m = new Map();
    for (const [i, n, o, t] of graph.turns ?? []) m.set(`${i}|${n}|${o}`, t);
    TURN_CACHE.set(graph, m);
  }
  return m.size ? m.get(`${inIdx}|${node}|${outIdx}`) : undefined;
}

export type RuleKind = RuleWarning["kind"];

const WORD: Record<RuleKind, string> = {
  wrong_way: "역주행 구간",
  oneway_unknown: "일방통행 구간(방향 미확인)",
  turn_ban: "회전 금지",
  tight_turn: "좁은 코너",
};

/**
 * 경로가 어기거나 확인이 필요한 규칙을 순서대로.
 *
 * ★ 연속한 일방통행 구간은 **하나로** 센다. 골목 하나가 구간 셋으로 잘려 있으면
 *   「일방통행」 을 세 번 말하게 된다.
 */
export function routeRuleWarnings(
  graph: NaviGraph, plan: Pick<RoutePlan, "edges" | "forward" | "nodes">, spec?: VehicleSpec,
): RuleWarning[] {
  const index = edgeIndex(graph);
  // 출발·도착 구간은 자른 사본이라(`GraphEdge.clip`) 객체로는 못 찾는다 — 원본 인덱스를 쓴다
  const idx = { get: (e: GraphEdge) => index.get(e) ?? e.clip?.src };
  const out: RuleWarning[] = [];
  let acc = 0;
  let prevKind: RuleKind | null = null;
  for (let i = 0; i < plan.edges.length; i++) {
    const e = plan.edges[i];
    const fwd = plan.forward[i];
    if (i > 0) {
      const t = turnBan(graph, idx.get(plan.edges[i - 1]) ?? -1, plan.nodes[i], idx.get(e) ?? -1);
      if (t !== undefined) {
        out.push({ kind: "turn_ban", atM: acc, seg_uid: e.seg_uid,
                   text: TURN_BAN_WORD[t] ?? WORD.turn_ban });
      }
      // 좁은 코너(§218-2) — 차를 알 때만(제원 완성 차종). 숫자를 같이 말한다
      const tt = spec ? tightTurn(graph, spec, idx.get(plan.edges[i - 1]) ?? -1, plan.nodes[i], idx.get(e) ?? -1) : null;
      if (tt) {
        out.push({ kind: "tight_turn", atM: acc, seg_uid: e.seg_uid,
                   text: `좁은 코너 — 필요 반경 ${tt.needM.toFixed(1)}m · 코너 ${tt.haveM.toFixed(1)}m` });
      }
    }
    const k: RuleKind | null = isWrongWay(e, fwd) ? "wrong_way" : e.ow === 2 ? "oneway_unknown" : null;
    if (k && k !== prevKind) out.push({ kind: k, atM: acc, seg_uid: e.seg_uid, text: WORD[k] });
    prevKind = k;
    acc += e.length_m ?? 0;
  }
  return out;
}

/** 한 줄 요약. 없으면 null — 화면이 빈 줄을 안 그린다 */
export function ruleSummary(ws: RuleWarning[]): string | null {
  if (!ws.length) return null;
  const n = (k: RuleKind) => ws.filter((w) => w.kind === k).length;
  const parts = [
    n("wrong_way") && `역주행 ${n("wrong_way")}곳`,
    n("oneway_unknown") && `일방통행 ${n("oneway_unknown")}곳(방향 미확인)`,
    n("turn_ban") && `회전 금지 ${n("turn_ban")}곳`,
    n("tight_turn") && `좁은 코너 ${n("tight_turn")}곳`,
  ].filter(Boolean);
  return parts.join(" · ");
}

/** `driven` 뒤 `reachM` 안에서 처음 만나는 규칙. 이미 지난 것은 안 본다 */
export function nextRule(ws: readonly RuleWarning[] | undefined, driven: number, reachM: number): RuleWarning | null {
  for (const w of ws ?? []) {
    if (w.atM < driven) continue;
    return w.atM - driven <= reachM ? w : null;
  }
  return null;
}

/**
 * 음성 문구. **무엇을 하라**까지 말한다 — 「일방통행」 만 말하면 운전자가 판단을 한 번 더 해야 한다.
 * ★ 방향을 모르는 곳은 역주행이라고 말하지 않는다. 모른다고 말한다.
 */
export function rulePhrase(w: RuleWarning): string {
  switch (w.kind) {
    case "wrong_way": return "잠시 후 역주행 구간입니다. 서행하십시오.";
    case "oneway_unknown": return "잠시 후 일방통행 구간. 방향 미확인, 대향차 주의.";
    case "turn_ban": return `잠시 후 ${w.text} 교차로. 주의하십시오.`;
    case "tight_turn": return "잠시 후 좁은 코너. 크게 돌거나 전진 후진으로 도십시오.";
  }
}

const INDEX_CACHE = new WeakMap<NaviGraph, Map<GraphEdge, number>>();

/** 엣지 객체 → `graph.edges` 인덱스. `turns` 가 인덱스로 적혀 있어서 필요하다 */
export function edgeIndex(graph: NaviGraph): Map<GraphEdge, number> {
  let m = INDEX_CACHE.get(graph);
  if (!m) {
    m = new Map(graph.edges.map((e, i) => [e, i]));
    INDEX_CACHE.set(graph, m);
  }
  return m;
}

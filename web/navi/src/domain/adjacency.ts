/**
 * domain/adjacency.ts — 그래프를 A* 용 인접리스트로 굽는다.
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `domain/graph.ts` 가 627줄로 길이 상한(600)을 넘었고, 한 파일이
 *   네 가지 일을 했다 — **인접리스트 굽기** · 구간 위 투영 · A* · 경로 파생값.
 *   넷은 서로 다른 속도로 바뀐다. 굽는 규칙은 통행 가부(폭 · 막힘 · 신고 · 일방통행)가
 *   바뀔 때 손대고, A* 는 상태 정의가 바뀔 때 손댄다 — 같은 파일에 있으면 어느 쪽을
 *   고치든 나머지 셋을 읽고 지나가야 한다.
 *
 * ★ **차를 인접리스트에 묶어 둔다.** 코너 회전 점검(§218-2)이 전이마다 차를 알아야
 *   하는데 A* 는 차를 인자로 받지 않는다. 그 기억(`WeakMap`)과 그것을 읽는 함수가
 *   한자리에 있어야 「인접리스트 하나 = 차 하나」 규약이 눈에 보인다.
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 *
 * IN    NaviGraph · VehicleSpec · 조율값 · 신고로 뺀 구간 · 주변 사정 색인(`pressure.ts`)
 *       · **영상이 지금 재 준 통과폭**(`cv.fold()` · DECISIONS §366)
 * OUT   Adjacency — 노드 → 나가는 전이 목록. 비용은 방향마다 다르다
 * 밖    길을 고르는 것은 여기 일이 아니다(`graph.ts`). 여기는 **갈 수 있는가와
 *       얼마인가**만 센다. 구간 위 투영도 여기 없다(`edgeSnap.ts`).
 *       **「다시 낼 것인가」도 여기 없다**(`reroute.ts`) — 여기는 다시 낼 때
 *       쓰는 **값**만 든다.
 */

import { distM, type LngLat } from "./geo";
import {
  edgeCost, minCostFactor, pressureIsSane, type TuningKnobs, TUNING,
} from "./vehicle";
import { directionFactor, edgeIndex, minDirectionFactor } from "./rules";
import { tightTurn } from "./turning";
import { hazardsOf, pressureFactor, type HazardIndex } from "./pressure";
import { effectiveWidth, type CvView } from "./cv";
import type { GraphEdge, NaviGraph, VehicleSpec } from "./types";

/** `idx` 는 `graph.edges` 인덱스 — 회전 금지가 인덱스로 적혀 있다 */
interface Adj { to: number; cost: number; edge: GraphEdge; idx: number }
export type Adjacency = Map<number, Adj[]>;
export type CostMode = "safe" | "fastest";

/** 인접리스트를 구운 차 — 코너 회전 점검(§218-2)이 전이마다 차를 알아야 한다 */
const ADJ_SPEC = new WeakMap<Adjacency, VehicleSpec>();
/**
 * 이 인접리스트의 **비용/직선거리 하한.** A* 휴리스틱이 곱한다(PLAN §1 #71).
 *
 * ★ 조율값과 **같은 자리에서** 잰다. `findRoute` 가 `TUNING` 을 다시 읽으면
 *   인접리스트를 다른 조율로 구운 경우(시험 · 비교 모드)에 둘이 갈리고,
 *   갈리면 휴리스틱이 **과대추정**해 최적해가 깨진다. 구운 쪽이 기억한다.
 */
const ADJ_MIN_FACTOR = new WeakMap<Adjacency, number>();
const TIGHT_CACHE = new WeakMap<Adjacency, Map<string, boolean>>();

/** 이 인접리스트의 차에게 `(들어온, 노드, 나갈)` 전이가 좁은 코너인가. 캐시한다 */
export function isTight(graph: NaviGraph, adj: Adjacency, inIdx: number, node: number, outIdx: number): boolean {
  const spec = ADJ_SPEC.get(adj);
  if (!spec?.turn_check_radius_m) return false;
  let m = TIGHT_CACHE.get(adj);
  if (!m) TIGHT_CACHE.set(adj, (m = new Map()));
  const k = `${inIdx}|${node}|${outIdx}`;
  let v = m.get(k);
  if (v === undefined) m.set(k, (v = tightTurn(graph, spec, inIdx, node, outIdx) !== null));
  return v;
}

/** 인접리스트를 구운 차. 경고를 다시 셀 때 쓴다 */
export function adjacencySpec(adj: Adjacency): VehicleSpec | undefined {
  return ADJ_SPEC.get(adj);
}

/**
 * 이 인접리스트의 비용/직선거리 **하한**. 모르면 보수적으로 가장 작은 값(0)을
 * 준다 — 휴리스틱 0 은 다익스트라이고, **느린 것은 틀린 것보다 낫다.**
 */
export function adjacencyMinFactor(adj: Adjacency): number {
  return ADJ_MIN_FACTOR.get(adj) ?? 0;
}

/**
 * 그래프를 A* 용 인접리스트로 굽는다. **한 번만 호출한다.**
 *
 * @param mode "fastest" 면 통행 가부는 그대로 보되 **비용을 실거리로** 쓴다.
 *   ★ "fastest" 라도 `blocked` 와 필요폭 미만은 막는다. 소방차가 못
 *     지나가는 길은 빠른 것이 아니라 못 가는 길이다.
 * @param cv `cv.fold()` 가 접은 구간별 영상 소견. 없으면 **오늘과 한 글자도
 *   다르지 않다**(DECISIONS §366-1).
 * ★ 자기루프(a===b)는 뺀다. `seg/graph.py` 가 버리는 것과 같다.
 */
export function buildAdjacency(
  graph: NaviGraph, spec: VehicleSpec, lenient = false,
  mode: CostMode = "safe", tuning: TuningKnobs = TUNING,
  excluded?: ReadonlySet<string>,
  hazards?: HazardIndex | null,
  cv?: ReadonlyMap<string, CvView> | null,
): Adjacency {
  const adj: Adjacency = new Map();
  ADJ_SPEC.set(adj, spec);
  // ★ PLAN §1 #71. **구운 조율로** 하한을 재서 같이 들고 다닌다.
  //   `fastest` 는 비용이 실거리 그대로라 하한이 1 이다 — 방향 계수만 남는다.
  //   압력 계수가 음수면 하한을 자료 없이 못 묶으므로 0(= 다익스트라)으로 떨어뜨린다.
  ADJ_MIN_FACTOR.set(adj, !pressureIsSane(tuning) ? 0
    : mode === "fastest" ? Math.min(1, minDirectionFactor())
      : minCostFactor(tuning, minDirectionFactor()));
  const index = edgeIndex(graph);
  for (const e of graph.edges) {
    if (e.a === e.b) continue;
    // ★ 2026-09-21 (와이어프레임 16·17). 현장에서 「통행 불가」로 신고한
    //   구간은 **그래프에서 뺀다.** 비용을 올리는 것이 아니다 — 올리면 다른
    //   길이 더 비쌀 때 그 구간으로 다시 안내한다. 사람이 막혔다고 말한
    //   길을 계산이 되살리면 안 된다.
    if (excluded?.has(e.seg_uid)) continue;
    // ★ **영상 폭은 정적 폭과 같은 문으로 들어간다**(DECISIONS §366-1). 좁히는
    //   쪽만 받고(`cv.effectiveWidth`), 필요폭 미만이 되면 `edgeCost` 가
    //   `Infinity` 를 내 이 구간이 **그래프에서 빠진다** — 정적 폭이 좁을 때와
    //   같은 자리, 같은 판단이다.
    //   ★ `excluded`(현장 신고)로 안 넣은 이유 둘 —
    //     ① 신고는 사람의 **단언**이고 영상은 **삭는 측정**이다. 신고 집합에
    //        넣으면 낡은 측정이 그 길을 영원히 닫고, 그것을 되돌릴 자리가 없다
    //     ② 한 사실(「이 폭으로 못 지난다」)을 두 문이 들면 둘이 갈린다.
    //        폭 판단은 `edgeCost` 하나다(R3 · 정본 단일화)
    const seenW = effectiveWidth(e.width_min_m, cv?.get(e.seg_uid));
    const penalized = edgeCost(
      spec, e.length_m, seenW, e.verdict, null, lenient, tuning);
    if (!Number.isFinite(penalized)) continue;
    // ★ 안전 경로는 폭을 아는 확인 필요 구간을 피한다(`TuningKnobs.avoidUncertain`).
    //   연결성 우선(lenient)에서는 안 피한다 — 그 모드는 닿는 것이 먼저다.
    const avoid = mode === "safe" && !lenient && e.width_min_m != null
      && (e.verdict === "needs_cv" || e.verdict === "unknown") ? tuning.avoidUncertain : 1;
    // ★ **점유 압력** — 단속 이력 · 단속 카메라 · 주변 사정(과속방지턱 · 보호구역)을
    //   길을 고르기 **전에** 비용에 놓는다(`domain/pressure.ts` · PLAN §1 #2 · #31 · #60).
    //   종전에는 이 자료가 경로가 정해진 **뒤에** 안내로만 붙었다 — 안내는 선택이 아니다.
    // ★ **지금은 정확히 1 이다.** `TUNING` 의 압력 계수가 전부 0 이라 경로가 안 움직인다.
    //   근거 없는 배수를 하나 더 만들지 않겠다는 뜻이고, 배선은 여기 살아 있다.
    // ★ 「빠른 경로」에는 안 건다. 그 모드는 **실거리**가 정의다(아래 `mode` 분기).
    const press = mode === "safe" ? pressureFactor(e, hazardsOf(hazards, e), tuning) : 1;
    const cost = mode === "fastest" ? (e.length_m ?? penalized) : penalized * avoid * press;
    const idx = index.get(e)!;
    // ★ 2026-09-22 (§215-1). 일방통행은 **방향마다** 값이 다르다. 두 모드 다 건다 —
    //   「빠른 길」 이 역주행이면 빠른 것이 아니라 어기는 것이다. 빼지는 않는다(rules.ts).
    for (const [from, to] of [[e.a, e.b], [e.b, e.a]] as const) {
      let list = adj.get(from);
      if (!list) adj.set(from, (list = []));
      list.push({ to, cost: cost * directionFactor(e, from === e.a), edge: e, idx });
    }
  }
  return adj;
}

/** 좌표에서 가장 가까운 통행가능 노드. */
export function nearestNode(graph: NaviGraph, adj: Adjacency, p: LngLat): number {
  let best = -1;
  let bd = Infinity;
  for (const n of adj.keys()) {
    const d = distM(graph.nodes[n], p);
    if (d < bd) { bd = d; best = n; }
  }
  return best;
}

const USABLE = new WeakMap<Adjacency, number[]>();

/** 인접리스트에 실린(= nearestNode 가 통행가능으로 보는) 구간 인덱스 */
export function usableEdges(adj: Adjacency): number[] {
  let u = USABLE.get(adj);
  if (!u) {
    const s = new Set<number>();
    for (const list of adj.values()) for (const x of list) s.add(x.idx);
    USABLE.set(adj, (u = [...s].sort((p, q) => p - q)));
  }
  return u;
}

/** 인접리스트가 이 구간의 한 방향에 매긴 비용(배수 · 일방통행 포함). 없으면 Infinity */
export function dirCost(adj: Adjacency, e: GraphEdge, idx: number, forward: boolean): number {
  const [from, to] = forward ? [e.a, e.b] : [e.b, e.a];
  for (const x of adj.get(from) ?? []) if (x.idx === idx && x.to === to) return x.cost;
  return Infinity;
}

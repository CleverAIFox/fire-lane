/**
 * domain/turn.ts — 교차로 회전 판정과 안내 문구.
 *
 * ══ 회전각은 데이터가 아니라 계산이다 ══════════════════════════
 * `PLAN #1`(node_link 그래프 투입)이 ⏳ 인 것과 회전각을 못 내는 것은
 * 다른 문제다. 교차점 진입·이탈 방위각 차가 회전각이다.
 *
 * ══ 기준은 각도가 아니라 **분기 유무**다 ══════════════════════
 * 상용 내비는 길이 좌로 굽는다고 "좌회전하세요" 라고 하지 않는다.
 *
 *     갈 수 있는 길이 하나뿐   →  안내하지 않는다. **각도와 무관하다**
 *     둘 이상                  →  고른 것이 최직진인가?
 *
 * 실측에서 101° 로 꺾이는 길도 갈림길이 없으면 조용하다.
 *
 * ★ **도로명은 기준이 아니다.** 주소 체계지 도로 위상이 아니다.
 *   효과가 0 이면서 진짜 분기(`제봉로 4-120`, 폭 1.68m, road_side=1)를
 *   버릴 위험만 있었다.
 *
 * ══ ★ 진행방향은 경로가 안다 ═══════════════════════════════════
 * 2026-09-06. 엣지가 어느 쪽으로 그려졌는지를 좌표로 되짚다가 안내
 * 타이밍이 어긋났다. **`RoutePlan.forward` 가 이미 그것을 들고 있다** —
 * `findRoute` 가 좌표를 이어붙이며 기록한다. 다시 계산하지 않는다.
 *
 * ── 아직 못 하는 것 ─────────────────────────────────────────────
 * ★ 차로 안내("2차로로 진입"). `node_link` 의 `LANES` 가 대장에 있으나
 *   **골목을 안 담는다**(폭 2m 이하 링크 3%). 큰길 한정으로만 열린다.
 * ★ 회전제한(`turn_restriction` 87건). 대장에 있고 `ingest` 가 태운다.
 *   `publish_navi.py` 가 실어주면 여기서 쓴다.
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 */

import { angleDelta, bearing } from "./geo";
import type { GraphEdge, NaviGraph, RoutePlan } from "./types";

export type TurnKind =
  | "start" | "straight" | "slight_left" | "left" | "sharp_left"
  | "slight_right" | "right" | "sharp_right" | "uturn" | "arrive";

export interface Maneuver {
  /** 경로 시작점부터 이 회전 지점까지 거리(m) */
  atM: number;
  kind: TurnKind;
  /** 회전각(도). 양수 우, 음수 좌 */
  deltaDeg: number;
  /** 그 교차로의 통행가능 분기 수 */
  forks: number;
  edge: GraphEdge | null;
  roadName: string | null;
  verdict?: string;
  widthM?: number | null;
}

/** 노드에 붙은 엣지 목록. **그래프당 한 번만 만든다.** */
export type Incidence = Map<number, GraphEdge[]>;

export function buildIncidence(graph: NaviGraph): Incidence {
  const inc: Incidence = new Map();
  const push = (n: number, e: GraphEdge) => {
    let l = inc.get(n);
    if (!l) inc.set(n, (l = []));
    l.push(e);
  };
  for (const e of graph.edges) {
    if (e.a === e.b) continue;
    push(e.a, e);
    push(e.b, e);
  }
  return inc;
}

export function classify(delta: number): TurnKind {
  const a = Math.abs(delta);
  if (a < 25) return "straight";
  if (a > 160) return "uturn";
  const side = delta > 0 ? "right" : "left";
  if (a < 50) return `slight_${side}` as TurnKind;
  if (a < 120) return side as TurnKind;
  return `sharp_${side}` as TurnKind;
}

const WORD: Record<TurnKind, string> = {
  start: "출발", straight: "직진",
  slight_left: "왼쪽 방향", left: "좌회전", sharp_left: "급좌회전",
  slight_right: "오른쪽 방향", right: "우회전", sharp_right: "급우회전",
  uturn: "유턴", arrive: "도착",
};

/** `node` 쪽 끝에서 바깥으로 나가는 방위각. */
function outBearing(e: GraphEdge, node: number): number {
  const c = e.coords;
  return e.a === node
    ? bearing(c[0], c[1])
    : bearing(c[c.length - 1], c[c.length - 2]);
}

/** 통행 가능한가. 분기를 셀 때 못 가는 길은 선택지가 아니다. */
function passable(e: GraphEdge, needM: number): boolean {
  return e.verdict !== "blocked"
    && e.width_min_m != null && e.width_min_m >= needM;
}

/**
 * 경로에서 회전 지점을 뽑는다. **한 번만 계산한다.**
 *
 * ★ 진행방향을 `plan.forward` 에서 읽는다. 좌표로 되짚지 않는다 —
 *   경로가 구간을 거꾸로 지나는 경우가 21% 라 되짚으면 어긋난다.
 */
export function extractManeuvers(
  plan: RoutePlan, inc: Incidence, needM: number,
): Maneuver[] {
  const out: Maneuver[] = [];
  const n = plan.edges.length;
  if (n === 0) return out;

  let acc = 0;
  for (let i = 0; i + 1 < n; i++) {
    const cur = plan.edges[i];
    const nxt = plan.edges[i + 1];
    acc += cur.length_m ?? 0;

    // 두 엣지를 잇는 노드. `plan.nodes[i+1]` 이 그것이다.
    const end = plan.nodes[i + 1];
    // 들어올 때의 방위각 = 나가는 방위각의 반대.
    const inB = (outBearing(cur, end) + 180) % 360;
    const d = angleDelta(inB, outBearing(nxt, end));

    // ── ★ 분기를 센다. 여기가 이 함수의 핵심이다 ────────────────
    const alts: number[] = [];
    for (const e of inc.get(end) ?? []) {
      if (e.seg_uid === cur.seg_uid) continue;     // 온 길
      if (!passable(e, needM)) continue;
      const dd = angleDelta(inB, outBearing(e, end));
      if (Math.abs(dd) > 160) continue;           // 되돌아가기
      alts.push(dd);
    }

    // 선택할 것이 없으면 안내하지 않는다. **각도와 무관하다.**
    if (alts.length < 2) continue;

    // 고른 것이 최직진이고 완만하면 안내하지 않는다.
    const straightest = alts.reduce((a, b) => (Math.abs(b) < Math.abs(a) ? b : a));
    if (Math.abs(d - straightest) < 1e-6 && Math.abs(d) < 50) continue;

    const kind = classify(d);
    if (kind === "straight") continue;

    out.push({
      atM: acc, kind, deltaDeg: Math.round(d), forks: alts.length,
      edge: nxt, roadName: nxt.road_name ?? nxt.seg_label ?? null,
      verdict: nxt.verdict, widthM: nxt.width_min_m,
    });
  }

  out.push({
    atM: plan.lengthM, kind: "arrive", deltaDeg: 0, forks: 0,
    edge: null, roadName: null,
  });
  return out;
}

/**
 * 다음 회전 · 남은 거리 · **바로 뒤따르는 회전**.
 *
 * @param mergeM 다음 회전이 이 거리 안에 또 있으면 `after` 로 함께 낸다.
 *   회전 간격 21% 가 30m 미만이라 묶지 않으면 말할 시간이 없다.
 *
 * ★ 지나친 판정을 -5m 고정으로 두지 않는다. 시속 144km 시뮬레이션에서
 *   한 틱(200ms)이 8m 라 5m 여유로는 회전을 건너뛴다. `passedM` 로 받는다.
 */
export function nextManeuver(
  maneuvers: Maneuver[], drivenM: number | null,
  mergeM = 45, passedM = 12,
): { m: Maneuver | null; distM: number | null; after: Maneuver | null } {
  if (drivenM == null) {
    return { m: maneuvers[0] ?? null, distM: null, after: null };
  }
  for (let k = 0; k < maneuvers.length; k++) {
    const m = maneuvers[k];
    if (m.atM < drivenM - passedM) continue;
    const nxt = maneuvers[k + 1] ?? null;
    const after = nxt && nxt.atM - m.atM <= mergeM ? nxt : null;
    return { m, distM: Math.max(0, m.atM - drivenM), after };
  }
  return { m: null, distM: null, after: null };
}

/**
 * 안내 문구. **화면과 음성이 같은 문구를 쓴다.**
 *
 * ★ 2026-09-06. 도로명을 붙였다가 뺐다. "150미터 앞 좌회전 동명로14번길"
 *   은 읽는 데 4초가 걸리는데 **회전 간격 중앙이 64m**(시속 30km 에서
 *   7.7초)라 다음 안내를 밀어낸다. 상용도 대부분 도로명을 안 읽는다.
 *
 *   도로명은 **화면에 남긴다** — 눈은 한 번에 읽지만 귀는 순서대로 듣는다.
 */
export function phrase(m: Maneuver, distM: number | null): string {
  if (m.kind === "arrive") {
    return distM != null && distM > 40 ? `${round(distM)} 앞 목적지` : "목적지 도착";
  }
  const head = distM != null && distM > 15 ? `${round(distM)} 앞 ` : "";
  return `${head}${WORD[m.kind]}`;
}

/**
 * 연속 회전을 한 문장으로.  "60미터 앞 좌회전 후 우회전"
 * ★ 도로명을 붙이지 않는다. 회전 간격 21% 가 30m 미만이라 시속 30km 에서
 *   3.6초다 — 도로명까지 읽으면 회전이 지나간다.
 */
export function mergePhrase(
  m: Maneuver, after: Maneuver | null, distM: number | null,
): string {
  if (!after) return phrase(m, distM);
  const head = distM != null && distM > 15 ? `${round(distM)} 앞 ` : "";
  if (after.kind === "arrive") return `${head}${WORD[m.kind]} 후 목적지`;
  return `${head}${WORD[m.kind]} 후 ${WORD[after.kind]}`;
}

/** 상용 관례로 거리를 반올림한다. "187미터 앞" 은 사람이 못 쓴다. */
export function round(m: number): string {
  if (m >= 1000) return `${(m / 1000).toFixed(1)}킬로미터`;
  if (m >= 300) return `${Math.round(m / 100) * 100}미터`;
  if (m >= 100) return `${Math.round(m / 50) * 50}미터`;
  return `${Math.max(10, Math.round(m / 10) * 10)}미터`;
}

export const TURN_WORD = WORD;

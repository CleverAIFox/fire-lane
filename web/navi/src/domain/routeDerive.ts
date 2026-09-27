/**
 * domain/routeDerive.ts — 이미 나온 경로에서 값을 읽는다.
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `domain/graph.ts` 가 상한(600)을 넘었다. 여기 넷은 **경로를 내지
 *   않는다** — 다 난 경로를 읽기만 한다. 부르는 쪽도 다르다(음성 · HUD · 스냅 ·
 *   하이브리드 경계). A* 를 고치는 사람과 안내 문구를 고치는 사람이 같은 파일을
 *   열어야 할 이유가 없었다.
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 *
 * IN    RoutePlan · 현재 스냅 · 주행거리 · 차 제원
 * OUT   구간 집합 · 주행거리(m) · 앞쪽 구간 · 하이브리드 경계로 자른 묶음
 * 밖    길을 고르지 않는다. 경로가 왜 그 모양인지는 `graph.ts` 가 답한다.
 */

import { requiredWidth } from "./vehicle";
import type { GraphEdge, RoutePlan, VehicleSpec } from "./types";

/** 경로 구간 집합. 스냅이 경로를 알게 하는 데 쓴다. */
export function routeUids(plan: RoutePlan): Set<string> {
  return new Set(plan.edges.map((e) => e.seg_uid));
}

/**
 * 경로 시작점부터 현재 위치까지 실제로 온 거리(m).
 *
 * ★ **진행방향을 본다.** 경로가 구간을 거꾸로 지나면 스냅의 `progress`
 *   를 뒤집어야 한다 — 21% 가 그런 구간이고, 안 뒤집으면 주행거리가
 *   앞뒤로 튀어 안내가 늦거나 이미 지나서 나온다(2026-09-06).
 *
 * ★ 경로 밖이면 null 이다. 이탈 중에는 남은 거리를 말하지 않는다.
 */
export function progressAlongRoute(
  plan: RoutePlan, current: { seg_uid: string; progress: number } | null,
): number | null {
  if (!current) return null;
  let acc = 0;
  for (let i = 0; i < plan.edges.length; i++) {
    const e = plan.edges[i];
    const L = e.length_m ?? 0;
    if (e.seg_uid === current.seg_uid) {
      // 자른 사본(출발·도착 구간)이면 원본 비율을 사본 비율로 옮긴다
      const q = e.clip
        ? (e.clip.t1 > e.clip.t0 ? (current.progress - e.clip.t0) / (e.clip.t1 - e.clip.t0) : 0)
        : current.progress;
      const p = plan.forward[i] ? q : 1 - q;
      return acc + L * Math.max(0, Math.min(1, p));
    }
    acc += L;
  }
  return null;
}

/**
 * 현재 위치에서 `aheadM` 앞에 있는 구간.
 *
 * ★ 판정 안내를 **진입 전에** 하려고 있다. 회색 구간에 들어가 놓고
 *   "주행 중" 이라고 하면 운전자가 이미 결정을 내린 뒤라 쓸모가 없다.
 */
export function lookAhead(
  plan: RoutePlan, drivenM: number, aheadM: number,
): GraphEdge | null {
  const target = drivenM + aheadM;
  let acc = 0;
  for (const e of plan.edges) {
    const L = e.length_m ?? 0;
    if (acc + L > target) return acc > drivenM ? e : null;
    acc += L;
  }
  return null;
}

/**
 * 경로를 **하이브리드 경계**로 자른다.
 *
 * 폭 3.0m 이상 구간은 상용 도로망에 있고(1,101건 전량 대조: 89%), 그
 * 아래는 없다(23%). 경계값을 발명하지 않았다 — `requiredWidth(spec)` 과
 * 같은 숫자이고, 그것이 우연이 아니라는 것이 이 설계의 논거다.
 */
export function splitAtHybridBoundary(
  plan: RoutePlan, spec: VehicleSpec,
): { sdk: GraphEdge[][]; own: GraphEdge[][] } {
  const need = requiredWidth(spec);
  const sdk: GraphEdge[][] = [];
  const own: GraphEdge[][] = [];
  let run: GraphEdge[] = [];
  let wide: boolean | null = null;
  const flush = () => {
    if (run.length && wide !== null) (wide ? sdk : own).push(run);
    run = [];
  };
  for (const e of plan.edges) {
    const w = e.width_min_m != null && e.width_min_m >= need;
    if (wide !== null && w !== wide) flush();
    wide = w;
    run.push(e);
  }
  flush();
  return { sdk, own };
}

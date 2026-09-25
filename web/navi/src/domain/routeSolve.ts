/**
 * domain/routeSolve.ts — 「출발점 · 도착점」 을 경로 한 벌로 푼다.
 *
 * ── 왜 갈랐나 (PLAN §1 #129) ────────────────────────────────────
 * ★ 2026-09-25. `app/useNavigation.ts` 가 570줄이었고, 그 안의 `route` 는 **계산과
 *   상태 쓰기가 엉켜** 있었다 — 투영 · A* · 대체 접근 지점 · 빠른 경로를 내면서
 *   중간중간 `setPlan` · `setAccess` · `setNoRoute` 를 불렀다. 계산이 훅 안에 있으면
 *   브라우저 없이 부를 수 없고, 「경로가 없다」 를 판단하는 자리가 화면 상태와 같은
 *   문장에 있어 읽는 사람이 둘을 구분하지 못했다.
 *
 * ★ 순수하다 — 무엇도 안 고치고 **결과만** 낸다. 훅은 그 결과를 상태에 옮기기만 한다.
 *
 * ── 무엇을 푸나 ─────────────────────────────────────────────────
 * 1. 출발·도착을 가장 가까운 **통행가능 구간**에 투영한다(DECISIONS §218-3).
 *    노드에 붙이면 구간 한가운데 선 차를 교차점으로 옮겨 경로를 짠다.
 * 2. 못 닿으면 **닿는 가장 가까운 곳**(대체 접근 지점 · §214-2)에 댄다. 종전에는
 *    「경로 없음」 을 띄우고 끝났다 — 다른 접근 지점을 사람에게 넘겼다.
 * 3. 빠른 경로는 **자기 인접리스트**로 다시 투영해 낸다. 대체 접근이면 도착점은
 *    안전 경로가 찾은 그 노드다 — 두 경로의 끝이 갈리면 비교가 거짓이 된다.
 *
 * IN    NaviGraph · 인접리스트 둘(안전 · 빠른) · 출발 좌표 · 도착 좌표
 * OUT   RouteSolution, 또는 null(= 어느 접근 지점에도 못 닿는다)
 * 밖    상태를 안 만진다. 「경로 없음」 화면(와이어프레임 13)을 띄우는 것은 훅 일이다.
 */

import { distM, type LngLat } from "./geo";
import { findRouteBetween, snapToEdge, type Adjacency, type RouteEnd } from "./graph";
import { alternateAccess } from "./access";
import type { NaviGraph, RoutePlan } from "./types";

export interface RouteSolution {
  /** 채택할 안전 경로 */
  plan: RoutePlan;
  /** 같은 끝점으로 낸 빠른 경로. 인접리스트가 없거나 못 내면 null */
  fast: RoutePlan | null;
  /** 사건 지점까지 못 가서 대체 접근 지점에 댔다 */
  alt: boolean;
  /** 경로 끝 → 도착 좌표 **직선** 거리(m) */
  walkM: number;
}

export function solveRoute(
  graph: NaviGraph, safe: Adjacency, fast: Adjacency | null,
  from: LngLat, to: LngLat,
): RouteSolution | null {
  const S = snapToEdge(graph, safe, from);
  let goal: RouteEnd | null = snapToEdge(graph, safe, to);
  let r = S && goal ? findRouteBetween(graph, safe, S, goal) : null;
  let alt = false;
  if (!r && S) {
    // ★ 출발 구간의 두 끝점은 같은 성분이라 어느 쪽에서 세어도 닿는 곳이 같다.
    const acc = alternateAccess(graph, safe, S.edge.a, to);
    if (acc) {
      goal = { node: acc.node };
      r = findRouteBetween(graph, safe, S, goal);
      if (r && !r.edges.length) r = null;       // 제자리가 대체 지점이면 경로가 아니다
      alt = !!r;
    }
  }
  if (!r) return null;
  const end = r.coords[r.coords.length - 1];
  const FS = fast ? snapToEdge(graph, fast, from) : null;
  const FG = fast ? (alt ? goal : snapToEdge(graph, fast, to)) : null;
  return {
    plan: r,
    fast: fast && FS && FG ? findRouteBetween(graph, fast, FS, FG) : null,
    alt,
    walkM: end ? distM(end, to) : 0,
  };
}

/**
 * 이 인접리스트로 도착 좌표에 **닿기는 하나**. 경로 자체는 버린다.
 * ★ 우회 후보를 고를 때 쓴다 — 막아도 갈 곳이 남는 구간만 신고 시연에 올린다(§214-2).
 */
export function reaches(
  graph: NaviGraph, adj: Adjacency, from: LngLat, to: LngLat,
): boolean {
  const S = snapToEdge(graph, adj, from);
  const T = snapToEdge(graph, adj, to);
  return !!(S && T && (findRouteBetween(graph, adj, S, T)
    || alternateAccess(graph, adj, S.edge.a, to)));
}

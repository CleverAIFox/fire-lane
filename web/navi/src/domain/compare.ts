/**
 * domain/compare.ts — 경로 비교(02) — 지도 위 표지 · **두 경로가 같은가** · 비교 수치.
 *                     (와이어프레임 02 · DECISIONS §214-2 · §220)
 *
 * 와이어프레임 02 는 두 경로 위에 표지 둘을 띄운다 —
 *
 *     「공통 구간」        두 경로가 같이 가는 구간
 *     「확인 필요 45m」    빠른 경로에만 있는 확인 필요(판정 보류 · CCTV 없음) 구간
 *
 * ★ 45m 는 그림의 예시다. 여기서는 **실제로 센다** — 비교 경로에만 있는 첫 연속 확인
 *   구간의 길이 합. 그런 구간이 없으면 표지도 없다. 없는 것을 그리지 않는다.
 * ★ 와이어프레임의 주차 차량 아이콘은 쓰지 않는다. 주정차 데이터가 없다(§212-4).
 */
import type { LngLat } from "./geo";
import { cumulative, pointAlong } from "./geo";
import type { GraphEdge, RoutePlan } from "./types";

const UNCERTAIN = new Set(["needs_cv", "unknown"]);

/**
 * 두 경로가 **같은 구간을 같은 순서로** 지나는가.
 *
 * ★ 2026-09-23 (DECISIONS §220). 종전엔 `App.tsx` 안에 있었고, 같으면 둘째 카드를
 *   숨기고 「비교할 둘째 경로가 없다」 한 줄을 냈다. 멘토링(§219)이 그 자리를 짚었다 —
 *   **같으면 같다고 말해야 한다**(「안전하면서 빠른 추천 경로」). 화면이 그 말을 하려면
 *   먼저 이 술어가 화면 밖에 있어야 한다. 시험이 여기를 문다.
 * ★ 좌표가 아니라 `seg_uid` 로 비교한다. 출발·도착 구간은 투영점에서 잘린 사본이라
 *   (`GraphEdge.clip` · §218-3) 좌표는 같은 경로에서도 부동소수로 갈릴 수 있다.
 */
export function sameRoute(a: RoutePlan, b: RoutePlan): boolean {
  return a.edges.length === b.edges.length
    && a.edges.every((e, i) => e.seg_uid === b.edges[i].seg_uid);
}

/** 두 경로가 같을 때 쓰는 이름(멘토링 §219). 화면과 시험이 **같은 문자열**을 본다 */
export const SAME_ROUTE_TITLE = "안전하면서 빠른 추천 경로";

/**
 * 비교 화면이 어느 모양이어야 하는가.
 *
 *   same    같은 구간 순서 → 카드 **하나**를 「안전하면서 빠른 추천 경로」 로
 *   two     다르다 → 둘 다 두고 다른 곳을 수로 보인다
 *   single  빠른 경로가 아예 안 섰다 → 추천 하나 + 그 사실을 말한다
 *
 * ★ `same` 과 `single` 을 가르는 것이 이 함수의 요지다. 종전 화면은 둘을 같은 한 줄로
 *   처리해 「비교할 둘째 경로가 없다」 로 읽혔다 — **없는 것과 같은 것은 다른 말이다.**
 */
export type CompareKind = "same" | "two" | "single";

export function compareKind(safe: RoutePlan | null, fast: RoutePlan | null): CompareKind {
  if (!safe || !fast) return "single";
  return sameRoute(safe, fast) ? "same" : "two";
}

/** 경로 하나를 비교 가능한 수로 줄인 것. 카드가 줄마다 그대로 찍는다 */
export interface RouteStats {
  lengthM: number;
  /** 지나는 **통행 불가** 구간 수. 지금은 A* 가 막아 0 이지만 세어서 보인다 —
   *  0 이라는 사실 자체가 관제사가 보려는 것이고, 목적지 직전 예외(§219)가 들어오면
   *  이 줄이 그대로 0 이 아니게 된다 */
  blockedCount: number;
  /** 통행 규칙 경고 수(역주행 · 방향 미확인 일방통행 · 회전 금지 · 급회전) */
  ruleCount: number;
  /** 폭 기준 확인 필요(판정 보류 · 영상판정 불가) 구간 수와 실거리 */
  uncertainCount: number;
  uncertainM: number;
  /** 경로에서 가장 좁은 최소 유효폭. 폭을 아는 구간이 없으면 null */
  minWidthM: number | null;
}

export function routeStats(p: RoutePlan): RouteStats {
  const unc = p.edges.filter((e) => UNCERTAIN.has(e.verdict));
  const w = p.edges.map((e) => e.width_min_m).filter((x): x is number => x != null);
  return {
    lengthM: p.lengthM,
    blockedCount: p.edges.filter((e) => e.verdict === "blocked").length,
    ruleCount: p.rules.length,
    uncertainCount: unc.length,
    uncertainM: unc.reduce((a, e) => a + (e.length_m ?? 0), 0),
    minWidthM: w.length ? Math.min(...w) : null,
  };
}

function edgeCoords(p: RoutePlan, i: number): LngLat[] {
  const c = p.edges[i].coords;
  return p.forward[i] ? c : [...c].reverse();
}

function midOf(coords: LngLat[]): LngLat | null {
  if (coords.length < 2) return coords[0] ?? null;
  const cum = cumulative(coords);
  return pointAlong(coords, cum, cum[cum.length - 1] / 2).point;
}

export interface CompareMarks {
  /** 공통 구간(앞에서부터 같이 가는 구간)의 가운데. 없으면 null */
  commonAt: LngLat | null;
  commonM: number;
  /** 비교 경로에만 있는 첫 확인 필요 연속 구간의 가운데 */
  checkAt: LngLat | null;
  checkM: number;
}

export function compareMarks(base: RoutePlan, other: RoutePlan): CompareMarks {
  // 공통 구간 — 앞에서부터 같은 구간
  const common: LngLat[] = [];
  let commonM = 0;
  const n = Math.min(base.edges.length, other.edges.length);
  let k = 0;
  while (k < n && base.edges[k].seg_uid === other.edges[k].seg_uid) {
    const c = edgeCoords(base, k);
    common.push(...(common.length ? c.slice(1) : c));
    commonM += base.edges[k].length_m ?? 0;
    k++;
  }
  // 비교 경로에만 있는 확인 필요 구간 — 첫 연속 묶음
  const inBase = new Set(base.edges.map((e) => e.seg_uid));
  let run: LngLat[] = [];
  let runM = 0;
  for (let i = 0; i < other.edges.length; i++) {
    const e: GraphEdge = other.edges[i];
    const hit = UNCERTAIN.has(e.verdict) && !inBase.has(e.seg_uid);
    if (hit) {
      const c = edgeCoords(other, i);
      run.push(...(run.length ? c.slice(1) : c));
      runM += e.length_m ?? 0;
    } else if (run.length) break;
  }
  return {
    commonAt: commonM >= 30 ? midOf(common) : null,
    commonM,
    checkAt: run.length ? midOf(run) : null,
    checkM: Math.round(runM),
  };
}

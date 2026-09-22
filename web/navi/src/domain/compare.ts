/**
 * domain/compare.ts — 경로 비교(02) 지도 위 표지.  (와이어프레임 02 · DECISIONS §214-2)
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

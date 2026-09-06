/**
 * domain/speed.ts — 구간별 주행 속도 추정. 순수 함수.
 *
 * ── 왜 필요한가 ─────────────────────────────────────────────────
 * 2026-09-06. 시뮬레이션 속도를 29/72/144km/h 버튼으로 골랐다. 의미가
 * 없다 — **큰길과 골목을 같은 속도로 달리는 차는 없다.** 그리고 도착
 * 예정 시각과 안내 문턱이 그 고정 속도에 매달려 값이 틀렸다.
 *
 * 도로 폭에서 낸다. 폭은 우리가 이미 가진 유일한 물리량이다.
 *
 *     폭 >= 12m    50 km/h    간선. 도심 제한속도
 *     폭 >=  7m    40 km/h    2차로
 *     폭 >=  4m    30 km/h    1차로 골목
 *     그 아래      20 km/h    서행 골목
 *
 * ★ **미검증이다.** 소방차 골목 주행 속도를 잰 적이 없다. 도착 예정
 *   시각과 안내 문턱이 전부 이 표에 매달린다 — D-30 인터뷰 항목이고,
 *   `node_link` 의 `MAX_SPD` 가 발행되면 그것으로 갈아끼운다.
 *
 * ★ 긴급자동차는 제한속도를 안 받지만 **골목에서는 물리가 제한한다.**
 *   폭 2m 길을 50으로 달릴 수 없다. 그래서 법정 상한이 아니라 실주행
 *   추정이다.
 *
 * ★ 회색 구간을 여기서 느리게 잡지 않는다. `edgeCost` 의 배수가 이미
 *   그 역할을 하고, 여기서 또 곱하면 이중 계산이 된다.
 */
import type { GraphEdge, RoutePlan } from "./types";

/** 폭 문턱(m) → 속도(km/h). 큰 것부터. **미검증 표다.** */
export const SPEED_TABLE: [number, number][] = [
  [12, 50],
  [7, 40],
  [4, 30],
  [0, 20],
];

/** 구간 하나의 추정 주행 속도(m/s). */
export function speedOf(e: GraphEdge): number {
  // `width_min_m` 이 없으면 도로대장 폭(road_bt_m)으로 떨어진다.
  const w = e.width_min_m ?? e.road_bt_m ?? 0;
  for (const [minW, kmh] of SPEED_TABLE) {
    if (w >= minW) return kmh / 3.6;
  }
  return 20 / 3.6;
}

/**
 * 경로 전체의 소요 시간(초).
 *
 * ★ `edgeCost` 의 배수를 곱한다. 배수가 곧 감속이므로 "여유 0~0.5m 는
 *   ×1.8" 이 그대로 시간에 반영된다 — **별도 감속 모델을 만들지 않는다.**
 */
export function travelSeconds(plan: RoutePlan): number {
  const eff = plan.lengthM > 0 ? plan.cost / plan.lengthM : 1;
  let sec = 0;
  for (const e of plan.edges) sec += (e.length_m ?? 0) / speedOf(e);
  return sec * eff;
}

/** 남은 거리에 대한 소요 시간(초). 현재 위치 이후 구간만 센다. */
export function remainingSeconds(plan: RoutePlan, drivenM: number): number {
  const eff = plan.lengthM > 0 ? plan.cost / plan.lengthM : 1;
  let acc = 0;
  let sec = 0;
  for (const e of plan.edges) {
    const L = e.length_m ?? 0;
    const end = acc + L;
    if (end > drivenM) {
      const part = Math.min(L, end - Math.max(acc, drivenM));
      sec += part / speedOf(e);
    }
    acc = end;
  }
  return sec * eff;
}

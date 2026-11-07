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

/**
 * 지령 → 현장도착의 **고정분**(초). `travelSeconds`(주행 시간)에 더해 「지령 → 현장도착」 추정을 낸다 — 지령 → 출발과 현장 접근이 여기 든다.
 * **이 값의 정본은 여기 하나다.** 속도표(`SPEED_TABLE`)와 같은 집이고 파이썬 쪽에 사본이 없다 — `tools/cost_vs_dispatch.py` 가 이 파일을 읽는다.
 *
 * ── 근거 ────────────────────────────────────────────────────
 * ① 값 210 — 전국 화재 270,174행에서 센터 → 현장 거리 **0~1km 구간의 중앙 지령 → 현장도착**이다(DECISIONS §644 · 실측).
 *    ★ **선형회귀의 절편이 아니다** — §644 가 선형 기울기(28.1초/km = 128km/h)를 틀린 도구라고 적었다. 그 구간에는 근접 주행(약 55초/km 로 0.5km 안팎)이
 *    들어 있어 순수 고정분보다 수십 초 클 수 있다. 우리 cost 는 펌프차 기준이고(`CONFIG.fleetDefault` = pump-js) 화재 출동이 펌프차다.
 * ② 확인 — 119 신고접수의 구간 단위 실측(DECISIONS §650): 이 파일이 낸 **주행 시간만**의 계산과 실제 지령 → 도착의 치우침 중앙이 +208초
 *    [+179, +234](스냅된 65곳) · 합친 표본 106곳 +208초 [+183, +227]. 210 이 두 구간 안에 있다. 전국 집계와 동명동 구간 실측은 **서로 다른 자료**다.
 * ③ 제외 — 구급 294초(DECISIONS §645)는 구급차 값이다. 그 84초 차이는 환자 정보 확인 · 장비 점검으로 **설명된다**(추론).
 * ★ 한계 — ② 는 센터에서 1.0~1.4km 지점에서만 섰다(거리에 레버리지가 없어 속도와 고정분을 못 가른다). 속도표와 **같이** 미검증이다.
 *   바뀌면 `tools/cost_vs_dispatch.py` 가 치우침을 다시 낸다 — 0 에 가까워야 한다.
 */
export const DISPATCH_FIXED_S = 210;

/**
 * 지령 → 현장도착 추정(초) = 고정분 + 주행 시간. **관제가 지령 전에 보는 수**다.
 *
 * ★ `travelSeconds` 를 이것으로 바꾸지 않았다 — 그 함수는 **주행 시간**이고 `remainingSeconds`(출발 전이면 같다 · 시험이 문다)와 경로 간 차이(`routeOption.deltaSec` ·
 *   `slowerSec`)가 그 위에 선다. 고정분은 차이에서 지워지고 달리는 중에는 이미 지나갔다. 달리는 화면의 도착 예정 시각(`remainingSeconds`)에는 안 더한다.
 */
export function dispatchToArrivalSeconds(plan: RoutePlan): number {
  return DISPATCH_FIXED_S + travelSeconds(plan);
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

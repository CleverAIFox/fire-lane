/**
 * domain/vehicle.ts — 소방차 제원과 통행 비용.
 *
 * `seg/vehicle.py` 를 그대로 옮긴 것이다. **순수 함수만 담는다** —
 * 파일도 경로도 fetch 도 모른다. 원본이 그렇게 설계돼 있어서 이식이 쉽다.
 *
 * ── 두 언어에 같은 규칙이 사는 위험 ──────────────────────────────
 * 이것은 파이썬 원본의 **사본**이다. 원본이 바뀌면 여기도 바꿔야 하고,
 * 강제자가 없으면 조용히 갈린다(MASTER §17 이 반복해 배운 형태).
 *
 * 그래서 대조 수단을 함께 둔다 — `verifyAgainstPrecomputed()` 가
 * `route_vehicle.json` 의 파이썬 결과와 맞춰본다. 앱이 켜질 때마다 돈다.
 * **갈리면 즉시 안다.** 그것이 사전계산본을 버리지 않는 이유다.
 *
 * ── 임계값 정본 ─────────────────────────────────────────────────
 * 3.0 / 0.5 / 1.8 / 2.5 를 여기서 재선언하지 않는다. 폭·여유는
 * `vehicle_spec.json` 에서 읽고, 그 정본은 `sources.yaml` 이다.
 */

import type { RouteVehicle, GraphEdge, VehicleSpec, Verdict } from "./types";

/**
 * 내륜차 — 회전 시 앞·뒷바퀴 궤적의 폭 차이(m).
 *
 *     Δ = R − √(R² − L²)
 *
 * ★ 1차 근사 `L²/(2R)` 를 쓰지 않는다. R=8 · L=4 에서 근사 1.000 대
 *   정확 1.072 로 7cm 가 어긋나고, 그것이 3.0m 임계 근처에서 판정을
 *   가른다. 골목에 R<8m 인 코너가 실제로 있다.
 *
 * ★ **미검증 축거로는 계산하지 않는다.** 0 을 돌려주면 필요폭이 직선
 *   하한만 남는다 — 근거 없이 **막지 않는** 쪽이고 `canTurn` 과 같은
 *   선택이다(DECISIONS §81 · §86-4).
 */
export function offtracking(spec: VehicleSpec, radiusM?: number | null): number {
  if (radiusM == null || radiusM <= 0) return 0;
  if (!spec.wheelbase_verified || spec.wheelbase_m == null) return 0;
  const wb = spec.wheelbase_m;
  if (radiusM >= (wb * wb) / (2 * 0.05)) return 0;
  if (radiusM <= wb) return wb;   // 축거보다 급한 반경은 물리적으로 못 돈다
  return radiusM - Math.sqrt(radiusM * radiusM - wb * wb);
}

/**
 * 그 곡률에서 필요한 최소 노면 폭(m).
 *
 *     직선   전폭 + 여유              = 3.0m
 *     곡선   전폭 + 여유 + 내륜차
 */
export function requiredWidth(spec: VehicleSpec, radiusM?: number | null): number {
  return spec.width_m + spec.clearance_m + offtracking(spec, radiusM);
}

/**
 * 그 곡률을 이 차가 돌 수 있는가. **폭과 무관하다.**
 *
 * ★ 미검증 반경으로는 막지 않는다. `turn_radius_m: 12.0` 은 자동차규칙
 *   제9조① 의 **법정 상한**이지 성능값이 아니다. 성능으로 쓰면 R=11.2m
 *   코너를 못 돈다고 내고, 근거 없이 39구간이 막힌다.
 */
export function canTurn(spec: VehicleSpec, radiusM?: number | null): boolean {
  if (!spec.turn_radius_verified || spec.turn_radius_m == null) return true;
  return radiusM == null || radiusM >= spec.turn_radius_m;
}

/**
 * 엣지 하나의 통행 비용. `Infinity` 면 못 간다.
 *
 *     여유 충분        ×1.0
 *     여유 0~0.5m      ×1.8      서행 · 접이식 미러
 *     필요폭 미만      막힘
 *     회전 불가        막힘
 *     모름             ×2.5  (lenient 면 ×1.2)
 *
 * ── lenient ──────────────────────────────────────────────────
 * `unknown` 354 · `needs_cv` 191 은 **모른다** 는 뜻이지 못 간다는 뜻이
 * 아니다. 막으면 그래프가 끊겨 경로가 아예 안 나온다 — 측정했다.
 * strict 로 돌리면 안전센터에서 도달 가능한 구간이 **1개**가 된다.
 *
 * ★ 어느 쪽이든 `blocked` 는 막는다. 그것만은 판정이 확정이다.
 * ★ 이 플래그는 디버그가 아니라 **제품 기능**이다. UI 에
 *   "안전 경로 / 연결성 우선" 으로 노출한다.
 *
 * ★ ×2.5 · ×1.2 · ×1.8 **은 근거 없는 값이다.** 회색 구간을 회피할
 *   근거가 아직 없어서 정한 임시 계수이며, 주정차 단속 이력 기반
 *   점유위험도(β)가 이 자리를 대체할 후보다(PLAN §4-1 · #62).
 *   `TUNING` 이 이 값들을 한 자리에 모아 갈아끼울 수 있게 한다.
 */
export function edgeCost(
  spec: VehicleSpec,
  lengthM: number | null,
  widthM: number | null,
  verdict?: Verdict | null,
  radiusM?: number | null,
  lenient = false,
  t: TuningKnobs = TUNING,
): number {
  if (lengthM == null || lengthM <= 0) return Infinity;
  if (verdict === "blocked") return Infinity;
  if (!canTurn(spec, radiusM)) return Infinity;

  const need = requiredWidth(spec, radiusM);

  if (widthM == null) {
    // 폭을 모른다. 판정 어휘가 남은 정보다.
    if (verdict === "needs_cv" || verdict === "unknown") {
      return lengthM * (lenient ? t.unknownLenient : t.unknown);
    }
    return lengthM * (lenient ? t.noWidthLenient : t.noWidth);
  }

  if (widthM < need) return Infinity;
  if (widthM - need < t.tightMarginM) return lengthM * t.tight;
  return lengthM;
}

/**
 * 갈아끼울 계수.
 *
 * ★ **여기 있는 값은 전부 미검증이다.** 근거가 생기면 그 값을 바꾸고
 *   근거를 이 주석에 적는다. 근거 있는 값(전폭 2.5 · 필요폭 3.0)은
 *   여기 없다 — 그것은 `vehicle_spec.json` 과 `seg/params.py` 가 든다.
 *
 * 남는 사람이 회색 해법을 정하면 **여기만 고치면 된다.** 그것이 이
 * 객체가 존재하는 이유다.
 */
export interface TuningKnobs {
  /** 폭 미상 + 회색 판정. 근거 없음 */
  unknown: number;
  unknownLenient: number;
  /** 폭 미상 + 그 밖. 근거 없음 */
  noWidth: number;
  noWidthLenient: number;
  /** 여유가 이 값 미만이면 서행으로 본다(m). 근거 없음 */
  tightMarginM: number;
  /** 서행 배수. 근거 없음 */
  tight: number;
}

export const TUNING: TuningKnobs = {
  unknown: 2.5,
  unknownLenient: 1.2,
  noWidth: 3.0,
  noWidthLenient: 1.5,
  tightMarginM: 0.5,
  tight: 1.8,
};

/**
 * 이 구현이 파이썬과 같은 답을 내는가.
 *
 * `route_vehicle.json` 은 안전센터 2곳에서 파이썬 `edge_cost` 로 돌린
 * 결과다. 같은 조건으로 여기서 돌려 통행 가부가 맞는지 본다.
 * **어긋나면 두 언어의 규칙이 갈린 것이다.**
 *
 * ★ 이것이 사전계산본을 버리지 않는 이유다. 소비자가 없던 83KB 짜리
 *   파일이 이제 골든 테스트가 된다.
 */
export function verifyAgainstPrecomputed(
  edges: GraphEdge[], spec: VehicleSpec, ref: RouteVehicle,
): { checked: number; mismatch: string[] } {
  const mismatch: string[] = [];
  let checked = 0;
  for (const e of edges) {
    const r = ref[e.seg_uid];
    if (!r) continue;
    checked++;
    const passable = Number.isFinite(
      edgeCost(spec, e.length_m, e.width_min_m, e.verdict, null, false)) ? 1 : 0;
    if (passable !== r.passable) {
      mismatch.push(
        `${e.seg_uid} ${e.seg_label ?? ""} ts=${passable} py=${r.passable} ` +
        `(verdict=${e.verdict} w=${e.width_min_m})`);
    }
  }
  return { checked, mismatch };
}

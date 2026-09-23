/**
 * domain/clearance.ts — 여유폭.  (멘토링 2026-09-22 · DECISIONS §219 → §220)
 *
 *     여유폭 = 최소 유효폭 − 요구폭
 *     요구폭 = 전폭 + 필요 여유            (`vehicle.ts::requiredWidth`)
 *
 * ★ 2026-09-23 (DECISIONS §220). 문턱을 여기서 다시 세우지 않는다. 요구폭은
 *   `requiredWidth(spec)` 가 들고(전폭 · 필요 여유의 정본은 `vehicle_spec.json` ·
 *   `fleet.json`), 「여유 0.5m 미만은 서행」 은 `TUNING.tightMarginM` 이 이미 든다 —
 *   `edgeCost` 가 같은 값으로 ×1.8 을 건다. 이 파일이 하는 일은 **그 뺄셈과 구간
 *   나누기**뿐이고, 통행 판정은 한 글자도 바꾸지 않는다.
 *
 * ★ 쓰는 폭은 `width_min_m`(최소 유효폭) 하나다. `edgeCost` · `buildAdjacency` 가
 *   통행 가부에 쓰는 바로 그 값이라, 화면에 뜨는 수와 경로가 내는 가부가 갈리지
 *   않는다. `width_max_m` 은 표시용이고 여유폭에 안 쓴다.
 *
 * ★ 회전 여유(내륜차)는 안 더한다 — `requiredWidth(spec, null)` 로 부른다. 코너
 *   반경은 구간 단위로 주어지지 않고, 있는 것처럼 빼면 직선 구간까지 좁아 보인다
 *   (§81 · §86-4 가 「근거 없이 막지 않는다」 로 정한 자리와 같은 선택이다).
 *
 * ★ 순수하다. React · MapLibre · fetch 를 모른다.
 */
import { requiredWidth, TUNING, type TuningKnobs } from "./vehicle";
import type { GraphEdge, VehicleSpec } from "./types";

/**
 * 여유폭 구간.
 *   neg      음수 — 이 차는 못 지난다(`edgeCost` 가 Infinity 를 내는 구간과 같다)
 *   tight    0 ~ 0.5m — 서행 · 미러 접기
 *   mid      0.5 ~ 1m
 *   wide     1m 이상
 *   unknown  폭을 모른다 — 뺄셈 자체가 성립 안 한다
 */
export type ClearanceBand = "neg" | "tight" | "mid" | "wide" | "unknown";

/** 범례 · 집계가 도는 순서. 좁은 쪽부터다 */
export const CLEARANCE_BAND_ORDER: readonly ClearanceBand[] =
  ["neg", "tight", "mid", "wide", "unknown"] as const;

/**
 * 「0.5~1m」 와 「1m+」 를 가르는 값(m).
 *
 * ★ **근거 없는 표시용 구분값이다.** 0.5m 는 `TUNING.tightMarginM`(서행 문턱)이라
 *   비용 계산과 같은 수를 쓰지만, 1.0m 는 색을 네 단으로 나누려고 정한 것뿐이다.
 *   판정에도 비용에도 안 들어간다 — 바꿔도 경로는 그대로다.
 */
export const CLEARANCE_WIDE_M = 1.0;

/** 여유폭(m). 폭을 모르면 null */
export function clearanceM(
  spec: VehicleSpec, widthM: number | null | undefined, radiusM?: number | null,
): number | null {
  if (widthM == null) return null;
  return widthM - requiredWidth(spec, radiusM);
}

/** 여유폭이 어느 구간인가 */
export function clearanceBand(m: number | null, t: TuningKnobs = TUNING): ClearanceBand {
  if (m == null) return "unknown";
  if (m < 0) return "neg";
  if (m < t.tightMarginM) return "tight";
  if (m < CLEARANCE_WIDE_M) return "mid";
  return "wide";
}

export interface EdgeClearance {
  /** 여유폭(m). 폭 미상이면 null */
  m: number | null;
  band: ClearanceBand;
  /** 뺄셈에 쓴 폭 — `width_min_m` */
  widthM: number | null;
  /** 뺀 값 — 전폭 + 필요 여유 */
  requiredM: number;
}

/** 구간 하나의 여유폭. 화면이 수와 색을 같이 얻는 자리다 */
export function edgeClearance(
  e: Pick<GraphEdge, "width_min_m">, spec: VehicleSpec, t: TuningKnobs = TUNING,
): EdgeClearance {
  const widthM = e.width_min_m ?? null;
  const m = clearanceM(spec, widthM);
  return { m, band: clearanceBand(m, t), widthM, requiredM: requiredWidth(spec) };
}

/** 구간별 개수 — 관제 범례가 색마다 몇 개인지 적는다 */
export function clearanceCounts(
  edges: readonly Pick<GraphEdge, "width_min_m">[], spec: VehicleSpec, t: TuningKnobs = TUNING,
): Record<ClearanceBand, number> {
  const out: Record<ClearanceBand, number> = { neg: 0, tight: 0, mid: 0, wide: 0, unknown: 0 };
  for (const e of edges) out[edgeClearance(e, spec, t).band]++;
  return out;
}

/** `+0.6m` · `-0.6m` · `—`. 부호를 반드시 보인다 — 음수가 요지다 */
export function fmtClearance(m: number | null): string {
  if (m == null) return "—";
  return `${m >= 0 ? "+" : ""}${m.toFixed(1)}m`;
}

/**
 * app/useHudData.ts — 화면이 쓸 파생값을 만든다. **순수 함수다.**
 *
 * ★ React 훅이지만 계산은 전부 `buildHudData` 에 있다. 인자만 받고
 *   아무것도 안 만지므로 **브라우저 없이 단위 테스트가 돈다.**
 *
 * ★ 회전 안내는 `useVoice` 가 이미 계산한 것을 받는다. 같은 문구를 두
 *   곳에서 만들면 화면과 음성이 갈린다 — **둘은 같은 문구를 쓴다.**
 *
 * ★ 주행 거리를 상태로 두지 않는다. `progressAlongRoute` 가 스냅에서
 *   파생하고, 그것이 `plan.forward` 를 봐서 역방향을 뒤집는다.
 *
 * ★ 소요 시간을 **고정 속도로 나누지 않는다.** 구간 폭에서 속도를 내고
 *   남은 구간만 합산한다 — 큰길 50 · 골목 20km/h(`domain/speed.ts`).
 *   고정 속도로 냈을 때 골목 경로의 도착 시각이 크게 틀렸다(2026-09-06).
 */
import { useMemo } from "react";
import { progressAlongRoute } from "../domain/graph";
import { remainingSeconds, travelSeconds } from "../domain/speed";
import { requiredWidth } from "../domain/vehicle";
import type { Maneuver } from "../domain/turn";
import type {
  RoutePlan, SnapResult, VehicleSpec, VerdictStyle,
} from "../domain/types";
import type { HudData } from "../ui/Hud";

export interface HudInput {
  spec: VehicleSpec;
  style: Record<string, VerdictStyle>;
  plan: RoutePlan | null;
  fastPlan: RoutePlan | null;
  current: SnapResult | null;
  lenient: boolean;
  offRoute: boolean;
  /** useVoice 가 낸 다음 회전. 화면과 음성이 같은 것을 본다 */
  maneuver: Maneuver | null;
  maneuverDistM: number | null;
  maneuverText: string | null;
  now?: number;
}

export function buildHudData(i: HudInput): HudData | null {
  if (!i.plan) return null;
  const { plan, spec, style } = i;
  const need = requiredWidth(spec);

  const driven = progressAlongRoute(plan, i.current);
  const remainM = Math.max(0, plan.lengthM - (driven ?? 0));
  const remainSec = remainingSeconds(plan, driven ?? 0);
  const eta = new Date((i.now ?? Date.now()) + remainSec * 1000);

  const unc = plan.edges.filter(
    (e) => e.verdict === "needs_cv" || e.verdict === "unknown");
  const widths = plan.edges
    .map((e) => e.width_min_m).filter((x): x is number => x != null);
  const minW = widths.length ? Math.min(...widths) : null;

  return {
    vehicleKind: spec.kind ?? "소방차",
    safeMode: !i.lenient,
    offRoute: i.offRoute,

    turnKind: i.maneuver?.kind ?? null,
    turnText: i.maneuverText,
    // ★ 도로명은 **화면에만** 남긴다. 음성은 안 읽는다 — 눈은 한 번에
    //   읽지만 귀는 순서대로 듣는다(domain/turn.ts::phrase).
    nextLabel: i.maneuver?.roadName ?? null,
    nextDistM: i.maneuverDistM,

    remainM, remainSec,
    etaText: `${String(eta.getHours()).padStart(2, "0")}:`
      + `${String(eta.getMinutes()).padStart(2, "0")}`,

    currentLabel: i.current?.seg_label,
    currentVerdictLabel: i.current ? style[i.current.verdict]?.label : undefined,
    currentVerdictColor: i.current ? style[i.current.verdict]?.color : undefined,
    currentWidthM: i.current?.width_min_m ?? null,
    sdkCovered: i.current?.width_min_m != null && i.current.width_min_m >= need,

    uncertainCount: unc.length,
    uncertainM: unc.reduce((s, e) => s + (e.length_m ?? 0), 0),
    minWidthM: minW,
    requiredM: need,
    marginM: minW != null ? minW - need : null,
    slowerSec: i.fastPlan
      ? travelSeconds(plan) - travelSeconds(i.fastPlan) : null,
    fastMinWidthM: i.fastPlan
      ? Math.min(...i.fastPlan.edges.map((e) => e.width_min_m ?? Infinity)) : null,
    fastLengthM: i.fastPlan?.lengthM ?? null,
  };
}

export function useHudData(i: HudInput): HudData | null {
  return useMemo(() => buildHudData(i), [
    i.plan, i.fastPlan, i.current, i.lenient, i.offRoute,
    i.spec, i.style, i.maneuver, i.maneuverDistM, i.maneuverText,
  ]);
}

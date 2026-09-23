/**
 * ui/clearanceMeaning.ts — 여유폭의 **색과 말**.  (DECISIONS §219 → §220)
 *
 * 수는 `domain/clearance.ts` 가 낸다. 여기는 그 수에 붙이는 색 · 이름 · 사유 문장뿐이다.
 *
 * ── 왜 색을 여기서 정의하나 ──────────────────────────────────────
 * 판정 4색은 정본이 `web/config.js` 다(MASTER §10-2) — 여기서 만들지 않는다. 여유폭
 * 색은 **다른 축**이다. 판정은 파이프라인이 낸 결론이고, 여유폭은 고른 차의 전폭으로
 * 화면이 그 자리에서 빼는 수다. 차를 바꾸면 색이 바뀐다 — 발행물에 담을 수 없다.
 *
 * ★ 2026-09-23 (DECISIONS §220). 판정 4색과 **겹치지 않는 색**을 쓴다. 초록이 사라지고
 *   파랑이 나오므로 모드가 바뀐 것이 지도만 봐도 보인다. 0 을 경계로 빨강 → 파랑으로
 *   가는 네 단인데, 0 이 곧 통행 가부의 문턱이라 그 자리에서 색이 가장 크게 튄다.
 *
 * ── 사유 문장의 규칙 ─────────────────────────────────────────────
 * ★ `action` 은 **관제사가 그것으로 취할 조치가 있을 때만** 채운다. 없으면 null 이고
 *   화면은 그 줄을 빼 버린다. 「참고하세요」 같은 줄은 화면에서 자리만 먹는다.
 */
import { clearanceBand, edgeClearance, fmtClearance, type ClearanceBand } from "../domain/clearance";
import { TUNING } from "../domain/vehicle";
import type { GraphEdge, VehicleSpec } from "../domain/types";
import { GRAY_REASON } from "./verdictMeaning";

/** 화면이 「무엇을 보여주는가」 를 한 줄로 말할 때 쓰는 정의. 그대로 찍는다 */
export const CLEARANCE_FORMULA = "여유폭 = 최소 유효폭 − 요구폭(전폭 + 필요 여유)";

/** 여유폭 4단(+ 폭 미상)의 색과 이름. 범례와 지도가 같은 것을 읽는다 */
export const CLEARANCE_SCALE: Record<ClearanceBand, { short: string; label: string; color: string }> = {
  neg: { short: "음수", label: "여유폭 음수 — 이 차는 못 지난다", color: "#d73027" },
  tight: { short: "0~0.5m", label: "0 ~ 0.5m — 서행 · 미러 접기", color: "#fc8d59" },
  mid: { short: "0.5~1m", label: "0.5 ~ 1m", color: "#fee090" },
  wide: { short: "1m+", label: "1m 이상", color: "#91bfdb" },
  unknown: { short: "폭 미상", label: "폭 미상 — 뺄셈이 성립 안 한다", color: "#6b7280" },
};

export interface SegmentReason {
  /** 왜 그 색인가 — 한 줄 */
  head: string;
  /** 근거 — 어느 폭이 얼마이고 요구폭과 얼마나 차이 나는가 */
  detail: string;
  /** 관제사가 지금 취할 조치. 없으면 null — 없는 조치는 적지 않는다 */
  action: string | null;
}

/** `최소 유효폭 2.4m − 요구폭 3.0m(전폭 2.5 + 여유 0.5) = 여유폭 -0.6m` */
export function widthLine(e: Pick<GraphEdge, "width_min_m">, spec: VehicleSpec): string {
  const c = edgeClearance(e, spec);
  const req = `요구폭 ${c.requiredM.toFixed(1)}m(전폭 ${spec.width_m} + 여유 ${spec.clearance_m})`;
  if (c.widthM == null) return `최소 유효폭 값이 없다 · ${req}`;
  return `최소 유효폭 ${c.widthM.toFixed(1)}m − ${req} = 여유폭 ${fmtClearance(c.m)}`;
}

/**
 * 구간 하나의 **사유**. 「빨간 도로는 색만이 아니라 사유를 적는다」(§219)가 이 함수다.
 *
 * ★ 초록이고 여유가 넉넉하면 null 을 낸다 — 적을 사유도, 취할 조치도 없다.
 */
export function segmentReason(
  e: Pick<GraphEdge, "width_min_m" | "verdict" | "unknown_reason">, spec: VehicleSpec,
): SegmentReason | null {
  const c = edgeClearance(e, spec);
  const detail = widthLine(e, spec);
  const tightM = TUNING.tightMarginM.toFixed(1);

  if (e.verdict === "blocked") {
    if (c.widthM == null) {
      return {
        head: "통행 불가 — 폭 미상",
        detail: "도면에서 최소 유효폭을 내지 못했다",
        action: "현장 확인 전에는 진입 가부를 말할 수 없다 — 다른 진입로를 같이 잡는다",
      };
    }
    return {
      head: "통행 불가 — 폭 부족",
      detail,
      action: "이 차로는 진입 불가 — 더 좁은 차종이나 다른 진입로를 지령한다",
    };
  }

  if (e.verdict === "needs_cv") {
    if (c.band === "neg") {
      return {
        head: "판정 보류 — 도면상 요구폭 미만",
        detail,
        action: "영상판정 전까지 진입 불가로 본다 — 우회로를 같이 잡는다",
      };
    }
    return {
      head: c.band === "tight" ? `판정 보류 — 여유 ${tightM}m 미만` : "판정 보류 — 영상판정 대상",
      detail,
      action: c.band === "tight"
        ? "주차 한 대로 막힌다 — 서행 · 미러 접기, 선행 차로 확인"
        : "영상판정 전에는 유일 경로로 지령하지 않는다",
    };
  }

  if (e.verdict === "unknown") {
    const g = e.unknown_reason ? GRAY_REASON[e.unknown_reason] : null;
    return {
      head: `영상판정 불가 — ${g?.short ?? e.unknown_reason ?? "CCTV 25m 밖"}`,
      detail,
      action: c.band === "neg"
        ? "도면상 요구폭 미만 — 진입 전 현장 확인이 필요하다"
        : c.band === "tight"
          ? "주차 한 대로 막힌다 — 진입 전 선행 차로 확인"
          : "CCTV 밖이라 영상판정이 안 된다 — 현장 확인으로만 확정된다",
    };
  }

  // clear — 여유가 넉넉하면 적을 것이 없다
  if (c.band === "neg" || c.band === "tight") {
    return {
      head: `통행 가능 — 여유 ${tightM}m 미만`,
      detail,
      action: "서행 · 미러 접기 — 맞은편 교행은 안 된다",
    };
  }
  return null;
}

/** 여유폭 수 하나에 붙는 색. 지도 밖(카드 · 패널)에서 쓴다 */
export function clearanceColorOf(m: number | null): string {
  return CLEARANCE_SCALE[clearanceBand(m)].color;
}

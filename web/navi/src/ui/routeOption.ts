/**
 * ui/routeOption.ts — 경로 하나를 **비교 카드 한 장**으로 접는다.  (와이어프레임 02)
 *
 * ── 왜 갈랐나 (PLAN §1 #130) ────────────────────────────────────
 * ★ 2026-09-25. `App.tsx` 가 640줄로 길이 상한(600)을 넘었다. 이 함수는 훅도 상태도
 *   안 쓰고 **인자만 보고 문장을 만든다** — 배선 파일에 있을 이유가 없었다. 문구를
 *   고치러 오는 사람과 화면 흐름을 고치러 오는 사람은 다른 사람이다.
 *
 * ★ 2026-09-22 (§214-2). 문구를 **실제 수로** 쓴다. 종전 「확인 필요 구간 11개를
 *   지납니다」 는 비교 상대를 안 말해서 추천 이유가 안 보였다.
 *
 * IN    경로 · 요구폭 · 비교 상대 경로 · 추천인가 · 접근 지점 · 주변 사정
 * OUT   RouteOption — `ui/RouteCompare` 가 그대로 그리는 한 벌
 * 밖    둘 중 어느 것이 추천인지 고르지 않는다. 고르는 것은 `App.tsx` 다.
 */
import { routeStats } from "../domain/compare";
import { hazardSummary, routeHazards } from "../domain/context";
import { ruleSummary } from "../domain/rules";
import { travelSeconds } from "../domain/speed";
import type { RoutePlan } from "../domain/types";
import type { RouteOption } from "./RouteCompare";
import { fmtDur } from "./tokens";

export function routeOption(
  p: RoutePlan, need: number, other: RoutePlan | null, rec: boolean,
  access: { alt: boolean; walkM: number } | null,
  ctx: GeoJSON.FeatureCollection | null,
): RouteOption {
  const st = routeStats(p);
  const unc = { length: st.uncertainCount };
  const sec = travelSeconds(p);
  const deltaSec = other ? sec - travelSeconds(other) : 0;
  const otherUnc = other ? routeStats(other).uncertainCount : unc.length;
  const slower = deltaSec > 1 ? `${fmtDur(deltaSec)} 느리지만 ` : "";
  const recNote = !unc.length ? `${slower}확인 필요 구간을 우회합니다.`
    : unc.length < otherUnc ? `${slower}확인 필요 구간이 ${otherUnc - unc.length}개 적습니다.`
    : `확인 필요 구간 ${unc.length}개를 지납니다 — 피할 수 있는 경로가 없습니다.`;
  const tail = access?.alt
    ? ` 차량은 사건 지점 약 ${Math.round(access.walkM)}m(직선) 앞 대체 접근 지점까지 갑니다.` : "";
  return {
    title: rec ? "폭 기준 추천" : "빠른 경로", recommended: rec, sec, lengthM: st.lengthM,
    uncertainCount: st.uncertainCount,
    uncertainM: st.uncertainM,
    minWidthM: st.minWidthM,
    requiredM: need,
    blockedCount: st.blockedCount,
    ruleCount: st.ruleCount,
    deltaSec,
    note: (rec ? recNote : "도착은 빠르지만 폭 측정 신뢰도가 낮은 구간이 포함됩니다.") + tail,
    rules: ruleSummary(p.rules),
    around: hazardSummary(routeHazards(p, ctx)),
  };
}

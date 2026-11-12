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
import { riskList, routeStats, type RiskItem } from "../domain/compare";
import { hazardSummary, routeHazards } from "../domain/context";
import { ruleSummary } from "../domain/rules";
import { travelSeconds } from "../domain/speed";
import type { RoutePlan } from "../domain/types";
import type { RouteOption } from "./RouteCompare";
import { fmtDur } from "./tokens";

/** 카드에 올리는 경고 줄 수. 넘치면 「외 N곳」 으로 수만 말한다 — 지도를 가리는 것이 이 앱에서 제일 나쁘다 */
export const RISK_LINES_MAX = 4;

export const RISK_KIND_TEXT: Record<RiskItem["kind"], string> = {
  blocked: "통행 불가", needs_cv: "확인 필요", unknown: "폭 모름", tight: "여유 부족",
};

/** 경고 한 줄 — 거리 · 이름 · 종류 · 여유를 **실제 수로** 쓴다. **폭 모름이면 여유 수를 안 쓴다** — 모르는 수를 쓰면 보는 사람이 믿는다 */
export function riskLine(r: RiskItem): string {
  const margin = r.kind !== "unknown" && r.marginM != null ? ` · 여유 ${r.marginM >= 0 ? "+" : ""}${r.marginM.toFixed(1)}m` : "";
  return `${r.atM}m ${r.label} · ${RISK_KIND_TEXT[r.kind]}${margin}`;
}

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
    title: rec ? "안전 경로" : "빠른 경로", recommended: rec, sec, lengthM: st.lengthM,
    uncertainCount: st.uncertainCount,
    unknownCount: p.edges.filter((e) => e.verdict === "unknown").length,
    uncertainM: st.uncertainM,
    minWidthM: st.minWidthM,
    requiredM: need,
    blockedCount: st.blockedCount,
    ruleCount: st.ruleCount,
    deltaSec,
    note: (rec ? recNote : "도착은 빠르지만 폭 측정 신뢰도가 낮은 구간이 포함됩니다.") + tail,
    rules: ruleSummary(p.rules),
    around: hazardSummary(routeHazards(p, ctx)),
    risks: riskSummary(p, need, other),
  };
}

/**
 * 카드에 올릴 경고 — 줄과 넘친 수. 경로에서 `edges` 만 읽는다(그래서 시험이 가짜 경로로 문다).
 *
 * ★ **상대 경로가 있으면 이 경로에만 있는 구간을 먼저 올린다**(DECISIONS §727 · B4). 두 경로가 출발 쪽을 같이 쓰므로 각자 경로 순서로 앞 네 줄을 올리면 **같은 공통 구간이 양쪽 앞을 채워**
 *   「고르라고 펼치는 건데 같은 걸 두 번 본다」가 됐다. 갈리는 구간이 먼저고 공통 구간은 뒤(넘치면 「외 N곳」)이며 `shared` 는 **보이는 줄 중 끝에서 몇 줄이 공통인가**다(화면이 흐리게 그린다).
 */
export function riskSummary(p: Pick<RoutePlan, "edges">, need: number, other: Pick<RoutePlan, "edges"> | null = null): RouteOption["risks"] {
  const all = riskList(p, need);
  if (!other) return { lines: all.slice(0, RISK_LINES_MAX).map(riskLine), more: Math.max(0, all.length - RISK_LINES_MAX) };
  const theirs = new Set(riskList(other, need).map((r) => r.segUid));
  const ordered = [...all.filter((r) => !theirs.has(r.segUid)), ...all.filter((r) => theirs.has(r.segUid))];   // 각 묶음 안은 경로 순서 그대로
  const shown = ordered.slice(0, RISK_LINES_MAX);
  return { lines: shown.map(riskLine), more: Math.max(0, ordered.length - shown.length), shared: shown.filter((r) => theirs.has(r.segUid)).length };
}

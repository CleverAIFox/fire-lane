/**
 * domain/context.ts — 경로 **주변 사정**을 경로 위 거리로 옮긴다.  (DECISIONS §216-3)
 *
 * 과속방지턱 · 단속카메라 · 어린이 · 노인보호구역 시설은 받아 두고 아무도 안 읽던 데이터다
 * (`web/data/context.geojson` · `publish_context.py`). 판정과 무관하다 — 폭도 색도 안 바꾼다.
 * 여기서는 「경로에서 몇 m 앞에 무엇이 있나」 만 낸다. 음성 · 지도가 그것을 쓴다.
 *
 * ★ 거리 문턱은 **자료의 성격**에서 왔다(측정값 아님).
 *   과속방지턱 12m   도로 위 시설이다. 도로 폭의 반 + 좌표 오차
 *   단속카메라 25m   도로변 기둥 · 좌표가 설치 장소 기준이다
 *   보호구역 150m    **시설 점**이다. 지정 범위(시설 기준 최대 300m)를 구역으로 그리지 않는다 —
 *                    구역 선형이 자료에 없다. 「시설 부근」 으로만 말한다
 * ★ 같은 종류가 60m 안에 이어지면 하나로 센다(과속방지턱 연속 설치).
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 */
import { distM, type LngLat } from "./geo";
import type { ContextKind, RoutePlan } from "./types";

export const NEAR_M: Record<ContextKind, number> = {
  speedbump: 12, speedcam: 25, child_zone: 150, senior_zone: 150,
};
const MERGE_M = 60;

export interface Hazard {
  kind: ContextKind;
  /** 경로 시작부터(m) */
  atM: number;
  at: LngLat;
  text: string;
}

const WORD: Record<ContextKind, string> = {
  speedbump: "과속방지턱",
  speedcam: "단속카메라",
  child_zone: "어린이보호구역 시설 부근",
  senior_zone: "노인보호구역 시설 부근",
};

/**
 * 점 p 를 좌표열에 투영 — (선 위 거리, 수직거리). 짧은 선이라 선형 탐색으로 충분하다.
 *
 * ★ `domain/pressure.ts` 가 **구간 하나**에 같은 것을 쓴다(경로가 아니라 엣지에 붙인다).
 *   투영을 두 번 구현하지 않는다 — 두 벌이면 같은 점이 경로에서는 걸리고 구간에서는
 *   안 걸리는 일이 생기고, 그것은 찾기 어렵다.
 */
export function nearestOnPath(coords: LngLat[], cum: number[], p: LngLat): { s: number; d: number } {
  let best = { s: 0, d: Infinity };
  const kx = 111_320 * Math.cos((p[1] * Math.PI) / 180), ky = 110_540;
  for (let i = 0; i + 1 < coords.length; i++) {
    const a = coords[i], b = coords[i + 1];
    const ax = (a[0] - p[0]) * kx, ay = (a[1] - p[1]) * ky;
    const bx = (b[0] - p[0]) * kx, by = (b[1] - p[1]) * ky;
    const vx = bx - ax, vy = by - ay;
    const L2 = vx * vx + vy * vy;
    const t = L2 ? Math.max(0, Math.min(1, -(ax * vx + ay * vy) / L2)) : 0;
    const x = ax + vx * t, y = ay + vy * t;
    const d = Math.hypot(x, y);
    if (d < best.d) best = { s: cum[i] + Math.sqrt(L2) * t, d };
  }
  return best;
}

/** 경로 위 주변 사정, 앞에서부터 */
export function routeHazards(plan: Pick<RoutePlan, "coords">, ctx: GeoJSON.FeatureCollection | null): Hazard[] {
  if (!ctx || plan.coords.length < 2) return [];
  const cum = [0];
  for (let i = 1; i < plan.coords.length; i++) cum.push(cum[i - 1] + distM(plan.coords[i - 1], plan.coords[i]));
  const hits: Hazard[] = [];
  for (const f of ctx.features) {
    const kind = f.properties?.kind as ContextKind | undefined;
    if (!kind || !(kind in NEAR_M) || f.geometry.type !== "Point") continue;
    const at = f.geometry.coordinates as LngLat;
    const { s, d } = nearestOnPath(plan.coords, cum, at);
    if (d > NEAR_M[kind]) continue;
    const lim = kind === "speedcam" && f.properties?.limit ? ` · 제한 ${f.properties.limit}km/h` : "";
    hits.push({ kind, atM: s, at, text: WORD[kind] + lim });
  }
  hits.sort((a, b) => a.atM - b.atM);
  const out: Hazard[] = [];
  for (const h of hits) {
    const prev = [...out].reverse().find((x) => x.kind === h.kind);
    if (prev && h.atM - prev.atM < MERGE_M) continue;
    out.push(h);
  }
  return out;
}

/** 음성 — 짧게. 보호구역은 「시설 부근」 이다(구역 경계를 모른다) */
export function hazardPhrase(h: Hazard): string {
  switch (h.kind) {
    case "speedbump": return "과속방지턱.";
    case "speedcam": return `단속카메라${h.text.includes("제한") ? h.text.replace("단속카메라", "") : ""}.`;
    case "child_zone": return "어린이보호구역 시설 부근입니다. 서행.";
    case "senior_zone": return "노인보호구역 시설 부근입니다. 서행.";
  }
}

/** `driven` 뒤 `reachM` 안의 첫 주변 사정. 지난 것은 안 본다 */
export function nextHazard(hs: readonly Hazard[], driven: number, reachM: number): Hazard | null {
  for (const h of hs) {
    if (h.atM < driven) continue;
    return h.atM - driven <= reachM ? h : null;
  }
  return null;
}

/** 경로 비교 카드 한 줄. 없으면 null */
export function hazardSummary(hs: readonly Hazard[]): string | null {
  if (!hs.length) return null;
  const n = (k: ContextKind) => hs.filter((h) => h.kind === k).length;
  const parts = [
    n("speedbump") && `과속방지턱 ${n("speedbump")}`,
    n("speedcam") && `단속카메라 ${n("speedcam")}`,
    (n("child_zone") + n("senior_zone")) && `보호구역 시설 ${n("child_zone") + n("senior_zone")}`,
  ].filter(Boolean);
  return parts.join(" · ");
}

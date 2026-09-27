/**
 * domain/pressure.ts — 받아 두고 **경로 비용에 못 닿던** 자료를 엣지에 붙인다. (PLAN §1 #2 · #31 · #60)
 *
 * ── 왜 생겼나 ───────────────────────────────────────────────────
 * ★ 2026-09-25. 대장에 있고 코드가 읽는데 **경로를 못 고르던** 자료가 넷이었다.
 *   `domain/context.ts` 가 과속방지턱 · 단속카메라 · 보호구역을 **경로가 정해진 뒤**
 *   「몇 m 앞에 무엇이 있나」로 읽는다. 그것은 안내지 선택이 아니다 — A* 는 그 자료를
 *   보지 못한 채 길을 고르고, 다 고른 다음에 「거기 과속방지턱 있습니다」 라고 말한다.
 *   `park`(단속 이력)은 발행까지 됐지만 화면만 읽었다. `enforce_cam` 은 소비자가 0 이었다.
 *
 *   이 파일이 그 넷을 **고르기 전에** 놓는 자리다. `buildAdjacency` 가 비용을 만들 때
 *   부른다 — `avoidUncertain` 배수가 걸리는 바로 그 자리다.
 *
 * ── ★ 값이 없다. 칸만 섰다 ──────────────────────────────────────
 * **계수 전부가 0 이고, 그래서 이 파일은 지금 경로를 한 치도 바꾸지 않는다.**
 * `pressureFactor()` 는 정확히 `1` 을 돌려준다(항등원).
 *
 * 일부러 그렇게 뒀다. 「단속 1,000건이면 비용 몇 배」 를 정하려면 **근거가 있어야 하고
 * 그 근거는 아직 없다** — `avoidUncertain = 2.0` 이 근거 없이 들어가 PLAN §1 #2 ·
 * #70 에 「근거 없는 값」 으로 적혀 있는 것과 같은 실수를 하나 더 만들지 않는다.
 * 저장소 규율이 **「값보다 스키마가 먼저다」** 이고 이것이 그 모양이다:
 *
 *     배선 · 자료 · 결측 구분 · 시험      지금 선다
 *     계수                                근거가 서는 날 `TUNING` 한 줄
 *
 * 근거를 채우는 법은 PLAN §1 #2 가 적는다(단속이력 상습도 #31 · CCTV 없는 구간 #60).
 * 계수를 넣는 사람은 **재기 전에** PLAN §1-27 측정 대장에 행을 세워야 한다(가드 6) —
 * `tests/test_measurements.py` 가 그것을 강제하고, `tests/test_cost_inputs.py` 가
 * 「계수가 0 이 아니게 됐는데 대장 행이 없다」 를 잡는다.
 *
 * ── 결측과 0 ────────────────────────────────────────────────────
 * ★ **모르는 것을 0 으로 읽지 않는다.** `park` · `ecam` 은 `null`(도로명이 없어 못 셌다) ·
 *   `undefined`(칸이 없는 옛 발행물) · `0`(세었고 없다) 셋이 다르다. 압력에는 **세어진
 *   것만** 들어가고, 모르는 것은 `unknown` 으로 따로 센다 — 0 으로 접으면 「증거가
 *   없다」가 「위험이 없다」로 조용히 바뀐다.
 * ★ 0 의 **강도**도 다르다. `ecam: 0` 은 「카메라가 없다」가 아니라 「도로명이 붙은
 *   18지점 중에 없다」다(57지점 중 39지점은 지번 주소라 못 붙는다). 그 몫은
 *   `counts.ecam_unplaced_sites` 가 든다. 지오코딩을 지어내 0 을 메우지 않는다.
 *
 * ── 거리 문턱을 새로 만들지 않는다 ──────────────────────────────
 * 주변 사정을 구간에 붙이는 거리는 `context.ts::NEAR_M` 을 **그대로** 쓴다. 투영도
 * 그 파일의 `nearestOnPath` 하나다. 두 벌이면 같은 과속방지턱이 경로에서는 걸리고
 * 구간에서는 안 걸린다.
 *
 * ★ 순수하다. React·MapLibre·fetch 를 모른다.
 *
 * IN    NaviGraph · context.geojson · TuningKnobs
 * OUT   엣지별 압력 증거와 **배수**(지금은 항등원 1)
 * 밖    **판정을 안 본다.** 폭도 `verdict` 도 안 만지고 통행 가부에도 관여하지 않는다 —
 *       곱하기만 하므로 `verifyAgainstPrecomputed`(파이썬 대조)가 그대로 맞는다.
 *       `speedbump` 를 속도로 옮기지도 않는다(`speed.ts` 가 이중 계산을 거부한다).
 */

import { distM } from "./geo";
import { NEAR_M, nearestOnPath } from "./context";
import type { ContextKind, GraphEdge, NaviGraph } from "./types";
import type { TuningKnobs } from "./vehicle";

/** 구간 하나에 붙은 주변 사정 개수. 없는 종류는 0 이다 — 여기 0 은 **세어진** 0 이다 */
export type EdgeHazards = Record<ContextKind, number>;

/** seg_uid → 그 구간에 붙은 주변 사정 */
export type HazardIndex = Map<string, EdgeHazards>;

export const HAZARD_KINDS: readonly ContextKind[] = ["speedbump", "speedcam", "child_zone", "senior_zone"];

function empty(): EdgeHazards {
  return { speedbump: 0, speedcam: 0, child_zone: 0, senior_zone: 0 };
}

/**
 * 주변 사정 점을 **구간마다** 센다. 경로가 아니라 엣지에 붙이는 것이 요점이다 —
 * 이 색인이 있으면 A* 가 길을 고르기 **전에** 그 자료를 본다.
 *
 * ★ `ctx` 가 없으면 **빈 색인**이다. 빈 색인과 「사정이 하나도 없다」는 다르므로
 *   `hazardsOf()` 가 그 둘을 가른다(`undefined` 대 `0` 넷).
 */
export function buildHazardIndex(graph: NaviGraph, ctx: GeoJSON.FeatureCollection | null): HazardIndex {
  const out: HazardIndex = new Map();
  if (!ctx) return out;
  // 구간 좌표열의 누적거리. 투영이 요구하는 꼴이다.
  const cums = graph.edges.map((e) => {
    const cum = [0];
    for (let i = 1; i < e.coords.length; i++) cum.push(cum[i - 1] + distM(e.coords[i - 1], e.coords[i]));
    return cum;
  });
  for (const e of graph.edges) out.set(e.seg_uid, empty());
  for (const f of ctx.features) {
    const kind = f.properties?.kind as ContextKind | undefined;
    if (!kind || !(kind in NEAR_M) || f.geometry.type !== "Point") continue;
    const at = f.geometry.coordinates as [number, number];
    const near = NEAR_M[kind];
    for (let k = 0; k < graph.edges.length; k++) {
      const e = graph.edges[k];
      // 값싼 선제 기각. ★ **문턱을 새로 만들지 않는다** — 기각 한계를 증명해서 쓴다.
      //   선분 위 최근접점은 그 선분의 끝점보다 최대 「선분 길이」만큼 더 가깝다.
      //   그러므로 모든 좌표까지의 거리가 `near + 최장 선분` 을 넘으면 투영해도
      //   절대 `near` 안에 못 든다. 느슨한 배수를 고르면 조용히 놓치는 점이 생긴다.
      const cum = cums[k];
      let span = 0;
      for (let i = 1; i < cum.length; i++) span = Math.max(span, cum[i] - cum[i - 1]);
      let close = false;
      for (const c of e.coords) {
        if (distM(c, at) <= near + span) { close = true; break; }
      }
      if (!close) continue;
      if (nearestOnPath(e.coords, cums[k], at).d <= near) {
        const h = out.get(e.seg_uid)!;
        h[kind] += 1;
      }
    }
  }
  return out;
}

/**
 * 이 구간의 주변 사정. 색인에 없으면 `undefined` — **모른다**(자료를 못 받았다).
 * `empty()` 를 돌려주면 「하나도 없다」가 되고 그것은 다른 말이다.
 */
export function hazardsOf(idx: HazardIndex | null | undefined, e: GraphEdge): EdgeHazards | undefined {
  return idx?.get(e.seg_uid);
}

/** 압력의 증거 한 벌. 화면 · 도구가 **결측을 결측으로** 보이게 하려고 쓴다 */
export interface PressureParts {
  /** 세어진 단속 건수. 모르면 null */
  park: number | null;
  /** 세어진 카메라 지점 수. 모르면 null */
  ecam: number | null;
  /** 세어진 주변 사정. 모르면 null */
  hazards: EdgeHazards | null;
  /** 증거 셋 중 **모르는** 것의 수. 0 이면 다 세어졌다 */
  unknown: number;
}

/** `null` · `undefined` 를 0 으로 접지 않고 그대로 통과시킨다 */
function counted(v: number | null | undefined): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function pressureParts(e: GraphEdge, hz?: EdgeHazards): PressureParts {
  const park = counted(e.park);
  const ecam = counted(e.ecam);
  const hazards = hz ?? null;
  return { park, ecam, hazards,
           unknown: (park === null ? 1 : 0) + (ecam === null ? 1 : 0) + (hazards === null ? 1 : 0) };
}

/**
 * 이 구간의 **비용 배수.** 1 이면 아무 영향도 없다.
 *
 * ★ **지금은 항상 정확히 1 이다** — `TUNING` 의 압력 계수가 전부 0 이기 때문이다.
 *   근거 없는 배수를 하나 더 만들지 않겠다는 뜻이고, 배선은 이미 살아 있으므로
 *   근거가 서는 날 `TUNING` 한 줄로 켠다.
 *
 * ★ 모르는 증거는 **아무것도 더하지 않는다.** 벌하지도(없는 위험을 지어냄) 깎지도
 *   (모름을 안전으로 읽음) 않는다 — `offtracking` · `canTurn` 이 미검증 제원에서
 *   0 을 돌려주는 것과 같은 선택이다(DECISIONS §81 · §86-4).
 */
export function pressureFactor(e: GraphEdge, hz: EdgeHazards | undefined, t: TuningKnobs): number {
  const p = pressureParts(e, hz);
  let add = 0;
  if (p.park !== null) add += (p.park / 1000) * t.parkPer1000;
  if (p.ecam !== null) add += p.ecam * t.ecamPerSite;
  if (p.hazards !== null) {
    add += p.hazards.speedbump * t.speedbumpEach;
    add += p.hazards.speedcam * t.speedcamEach;
    add += (p.hazards.child_zone + p.hazards.senior_zone) * t.zoneEach;
  }
  return 1 + add;
}

/** 압력 계수가 **전부 0** 인가 — 즉 이 자료가 경로를 아직 안 고르는가 */
export function pressureIsInert(t: TuningKnobs): boolean {
  return t.parkPer1000 === 0 && t.ecamPerSite === 0
    && t.speedbumpEach === 0 && t.speedcamEach === 0 && t.zoneEach === 0;
}

// ── 화면 말 ────────────────────────────────────────────────────

/**
 * 「몇 건」 을 사람 말로. **`null` 과 0 을 가른다.**
 *
 * ★ 종전에 `d.park ? … : "없음"` 이었다. 그러면 모르는 구간도 「없음」 이 된다 —
 *   0 은 세었고 없는 것이고 `null` 은 안 세어진 것이다. 실측으로 지금 `park` 결측은
 *   0건이지만(구간 1,281 전부에 도로명이 있다) **그것은 자료가 그래서지 코드가
 *   그래서가 아니다.** 단속이력 파일이 빠지면 전부 `null` 이 되고, 그날 「없음」 은
 *   거짓이 된다.
 */
export function countText(v: number | null | undefined, unit: string): string {
  const n = counted(v);
  if (n === null) return "모름";
  return n === 0 ? `0${unit}` : `${n.toLocaleString()}${unit}`;
}

/** `ecam` 의 0 은 약하다 — 무엇 중의 0 인지 붙여 준다 */
export function ecamNote(graph: NaviGraph | null | undefined): string | undefined {
  const n = graph?.counts?.ecam_unplaced_sites;
  return n ? `도로명이 붙은 지점만 — ${n}지점은 지번 주소라 구간에 못 붙였다` : undefined;
}

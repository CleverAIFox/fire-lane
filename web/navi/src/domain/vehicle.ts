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
/** 내륜차를 무시하는 문턱(m).
 *
 * ★ 정본은 `src/firelane/seg/params.py::OFFTRACK_MIN` 이다. 여기 있는 것은
 *   **사본**이고, 두 언어가 같은 규칙을 각자 구현하는 자리라 어쩔 수 없다
 *   (PLAN §1 #126 이 그 이중 구현 자체를 든다). 값이 갈리면
 *   `tests/test_sources_of_truth.py` 가 운다. */
const OFFTRACK_MIN = 0.05;

export function offtracking(spec: VehicleSpec, radiusM?: number | null): number {
  if (radiusM == null || radiusM <= 0) return 0;
  if (!spec.wheelbase_verified || spec.wheelbase_m == null) return 0;
  const wb = spec.wheelbase_m;
  if (radiusM >= (wb * wb) / (2 * OFFTRACK_MIN)) return 0;
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
  /**
   * **안전 경로가 확인 필요 구간을 피하는 배수.** 폭을 아는 `needs_cv` ·
   * `unknown` 구간에만 곱한다(폭을 모르는 쪽은 이미 `unknown` 이 든다).
   * 근거 없음 — 다른 배수와 같은 미검증 값이다.
   *
   * ★ 2026-09-21 (와이어프레임 02 · DECISIONS §211). 이것이 없을 때 **안전
   *   경로와 빠른 경로가 동명동 안 목적지 211곳 전부에서 같았다**(지산센터
   *   출발 · 실측). 폭을 아는 확인 필요 구간은 비용이 길이 그대로라, 두
   *   모드가 같은 비용을 냈다. 와이어프레임 02 는 「폭 기준 추천 = 확인 구간
   *   0개 · 빠른 경로 = 확인 구간 1개」 로 두 경로를 가른다 — **제품 정의가
   *   코드에 없었다.** 배수별 실측(같은 211곳):
   *
   *       1.0   갈림   0%   늘어난 거리 중앙 0.0%   확인 구간 평균 654m → 654m
   *       1.5   갈림  65%                    0.4%                    → 477m
   *       2.0   갈림  96%                    0.8%                    → 435m
   *       3.0   갈림  98%                    3.1%                    → 418m
   *
   *   2.0 을 쓴다 — 거리를 1% 안 늘리고 확인 구간을 1/3 줄인다. 3.0 은 거리만
   *   네 배로 더 쓰고 확인 구간은 17m 더 준다.
   * ★ 통행 가부는 안 바꾼다. 곱하기만 하므로 `verifyAgainstPrecomputed`
   *   (파이썬과 통행 가부 대조)가 그대로 맞는다.
   */
  avoidUncertain: number;

  /**
   * ── 점유 압력 계수 넷. **전부 0 이고, 0 인 것이 이 값들의 요점이다.** ──────
   *
   * ★ 2026-09-25. 받아 두고 **경로 비용에 못 닿던** 자료를 엣지에 붙였다
   *   (`domain/pressure.ts` · PLAN §1 #2 · #31 · #60). 배선 · 자료 · 결측 구분 ·
   *   시험은 다 섰고 **계수만 비었다.**
   *
   *   비운 것이 미완성이 아니라 **판단**이다. 위 `avoidUncertain = 2.0` 은 근거 없이
   *   들어가 PLAN §1 #2 · #70 에 「근거 없는 값」 으로 앉아 있다. 같은 자리를 넷 더
   *   만들면 갚을 빚이 다섯이 된다. 그래서 이 저장소 규율대로 한다 —
   *   **「값보다 스키마가 먼저다」.** 0 이면 `pressureFactor()` 가 정확히 1 을 내고
   *   경로는 한 치도 안 움직인다. 근거가 서는 날 이 넷만 고치면 켜진다.
   *
   * ★ **켜려면 먼저 적어야 한다.** 재기 전에 PLAN §1-27 측정 대장에 행을 세운다
   *   (가드 6 — 기준을 재고 나서 적으면 그것은 판정이 아니라 사후 합리화다).
   *   `tests/test_cost_inputs.py` 가 「0 이 아니게 됐는데 대장 행이 없다」 를 잡는다.
   */
  /** 단속 이력 1,000건당 더할 비용 비율. **근거 없음 — 그래서 0 이다** */
  parkPer1000: number;
  /** 단속 카메라 한 지점당. **근거 없음 — 그래서 0 이다** */
  ecamPerSite: number;
  /** 과속방지턱 하나당. **근거 없음 — 그래서 0 이다** */
  speedbumpEach: number;
  /** 단속카메라(교통) 하나당. **근거 없음 — 그래서 0 이다** */
  speedcamEach: number;
  /** 보호구역 시설 하나당(어린이 · 노인 합산). **근거 없음 — 그래서 0 이다** */
  zoneEach: number;
}

/**
 * ── A* 휴리스틱 허용성의 밑동 ──────────────────────────────────
 *
 * `graph.ts` 의 A* 는 직선거리를 휴리스틱으로 쓴다. 그것이 admissible 하려면
 * **비용 ≥ 직선거리 × (최소 배율)** 이어야 하고, `graph.ts` 머리말은 그 최솟값이
 * 1.0 이라고 **선언만** 하고 있었다 — 강제자가 0 이었다(PLAN §1 #71).
 *
 * ★ 실측(2026-10-03 · `test/astar.test.ts`). 지금 값에서는 선언이 맞다 —
 *   발행 그래프 노드 1,139 에서 무작위 쌍 **255**개를 A* 와 다익스트라로 각각
 *   풀어 **벌점 비용**을 대 보니 차이 0 이었다. 그런데 `unknown`·`noWidth`·
 *   `tight` 를 0.2 로 내리고 **옛 휴리스틱**(배율 1)으로 돌리면 쌍 456 중
 *   **19개에서 A* 가 더 나쁜 답**을 냈고 최대 **+34.94** 였다. 같은 그래프를
 *   새 휴리스틱(배율 0.2)으로 돌리면 **0** 이다.
 *   즉 이 성질은 **값에 매달려 있고** 그 값은 「남는 사람이 고치는 자리」다.
 *
 * ★ 그래서 휴리스틱이 이 수를 곱한다. 지금은 1.0 이라 **한 글자도 안 달라지고**,
 *   누가 배수를 1.0 아래로 내리는 날 자동으로 느슨해져 최적해를 지킨다.
 *
 * ★ **분모를 손으로 적지 않는다.** `TuningKnobs` 의 모든 칸이 아래 둘 중
 *   하나에 들어야 하고, 안 들면 `test/astar.test.ts` 가 그 칸 이름을 대며 운다 —
 *   §370 이 `DOMAIN` ↔ `NOT_DOMAIN` 으로 세운 그 틀이다. 손목록의 결함은
 *   틀린 항목이 아니라 **빠진 항목**이다.
 */
export const MULTIPLIERS = [
  "unknown", "unknownLenient", "noWidth", "noWidthLenient", "tight", "avoidUncertain",
] as const;

/**
 * ★ **배수가 아닌 칸의 목록과 그 사유는 `test/astar.test.ts` 에 있다.**
 *   `tests/test_layering.py` 의 `NOT_DOMAIN` 이 시험에 사는 것과 같은 자리다 —
 *   사유는 사람이 읽는 글이고 앱이 받을 이유가 없다. 분류가 **빠지면** 그
 *   시험이 칸 이름을 대며 운다. 분모는 `TuningKnobs` 에서 **유도**된다.
 *
 * ★ **번들 무게 때문이 아니다.** 옮기기 전후를 재 봤고 둘 다 141.61KB 였다 —
 *   `Record` 리터럴이 소비자 없으면 접힌다. 자리를 옮긴 사유는 **소유**다.
 */
/**
 * 압력 계수가 **음수가 아닌가.** 음수면 「주차 단속이 많은 길이 더 좋다」는
 * 뜻이고, 그것은 조율이 아니라 결함이다. 그리고 음수면 압력 항의 하한을
 * 자료 없이는 못 묶으므로 휴리스틱도 못 고친다 — 여기서 거부하는 것이 맞다.
 */
export function pressureIsSane(t: TuningKnobs): boolean {
  return t.parkPer1000 >= 0 && t.ecamPerSite >= 0 && t.speedbumpEach >= 0
    && t.speedcamEach >= 0 && t.zoneEach >= 0;
}

/**
 * 비용/직선거리 의 **하한.** A* 휴리스틱에 곱한다.
 *
 * 비용 사슬은 `penalized × avoid × press × direction` 이고 각 항의 최솟값을
 * 곱한다. `press` 는 `pressureIsSane` 인 동안 1 이다.
 *
 * ★ 1 을 넘지 않는다. 배수가 전부 1 이상이면 1 을 쓰는 것이 **가장 센**
 *   admissible 휴리스틱이고, 그보다 키우면 최적해가 깨진다.
 */
export function minCostFactor(t: TuningKnobs = TUNING, dirMin = 1): number {
  const mults = MULTIPLIERS.map((k) => t[k] as number);
  return Math.min(1, ...mults, dirMin);
}

/**
 * **모르는 값은 아는 값보다 싸지 않다.** 어기면 어긴 자리를 돌려준다.
 *
 * ★ 2026-10-06 (DECISIONS §407 · PLAN #147). 라우터의 「모름」 정책이 코드에
 *   선언된 적이 없었고, 재 보니 **어기고 있었다.** §396-5 가 `verdictsim` 에서
 *   이름 붙인 규율(「모르는 값은 한 번도 유리하게 쓰이지 않는다」)이 라우터에는
 *   안 걸려 있었다.
 *
 * ★ 막는 것과 비싸게 치는 것은 다르다. 이 규율은 **순서**만 묶는다 — 모름을
 *   `Infinity` 로 만들면 그래프가 끊겨 경로가 아예 안 나온다.
 *
 * ★ 파이썬 쪽 정본은 `seg/vehicle.py` 의 `unknown_is_never_cheaper` 다.
 *   두 벌인 것이 아니라 **두 런타임에 같은 규율을 건다** — 노브 대장이
 *   양쪽에 있으므로 규율도 양쪽에 있어야 한쪽만 느슨해지지 않는다.
 */
export function unknownIsNeverCheaper(t: TuningKnobs = TUNING): string[] {
  const bad: string[] = [];
  if (t.unknownLenient < t.tight) {
    bad.push(`unknownLenient ${t.unknownLenient} < tight ${t.tight} — 모르는 구간이 잰 구간보다 싸다`);
  }
  if (t.unknown < t.tight) bad.push(`unknown ${t.unknown} < tight ${t.tight}`);
  if (t.noWidthLenient < t.unknownLenient) {
    bad.push(`noWidthLenient ${t.noWidthLenient} < unknownLenient ${t.unknownLenient} — 어휘조차 없는 쪽이 모름보다 싸다`);
  }
  if (t.noWidth < t.unknown) bad.push(`noWidth ${t.noWidth} < unknown ${t.unknown}`);
  return bad;
}

export const TUNING: TuningKnobs = {
  unknown: 2.5,
  // ★ 2026-10-06 (DECISIONS §407 · PLAN #147). 1.2 → 1.8 · 1.5 → 2.5.
  //   **모르는 값이 아는 값보다 쌌다** — `tight`(폭을 재서 여유 0.5m 미만)가
  //   1.8 인데 `unknownLenient`(폭을 아예 모름)가 1.2 였다. 연결성 모드에서
  //   라우터가 **잰 구간보다 모르는 구간을 먼저 골랐다.**
  //   바닥은 지어낸 수가 아니라 이미 표에 있는 값이다 — `unknownIsNeverCheaper`.
  unknownLenient: 1.8,
  noWidth: 3.0,
  noWidthLenient: 2.5,
  tightMarginM: 0.5,
  tight: 1.8,
  avoidUncertain: 2.0,
  // ★ 넷이 아니라 다섯이고 **전부 0** 이다. 값을 넣기 전에 PLAN §1-27 에 행을 세운다.
  parkPer1000: 0,
  ecamPerSite: 0,
  speedbumpEach: 0,
  speedcamEach: 0,
  zoneEach: 0,
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

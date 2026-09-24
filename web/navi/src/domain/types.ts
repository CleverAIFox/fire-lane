/**
 * domain/types.ts — 계층이 함께 보는 타입 한 자리.
 *
 * ★ 이 파일의 정본은 파이썬 쪽이다. `publish_navi.py` 가 내는
 *   `navi_graph.json`, `publish_web.py` 의 `vehicle_spec.json`·`view.json`,
 *   `publish_fleet.py` 의 `fleet.json` 스키마를 옮긴 것이다.
 *   **여기서 필드를 발명하지 마라.**
 *
 * ★ `verdict` 는 4종 문자열이다. 숫자로 분기하지 마라 — 임계값 3.0/7.0
 *   의 정본은 `seg/params.py` 이고 여기는 어휘만 안다(MASTER §10-2).
 */

import type { LngLat } from "./geo";

export type Verdict = "clear" | "needs_cv" | "unknown" | "blocked";

/** `web/data/vehicle_spec.json`. 기준 차량 한 대. */
export interface VehicleSpec {
  kind?: string;
  width_m: number;
  length_m?: number | null;
  /**
   * 전고(m) — **판정에 안 쓴다.** 상공 장애물 데이터가 없다(`fleet.json` note).
   * 자차를 실측 크기 상자로 놓는 데만 쓰고, 없으면 상자를 안 놓는다(§232).
   */
  height_m?: number | null;
  /** 미검증이면 null 로 발행된다. publish_web.py 가 그렇게 막는다 */
  wheelbase_m: number | null;
  turn_radius_m: number | null;
  clearance_m: number;
  wheelbase_verified?: boolean;
  turn_radius_verified?: boolean;
  /**
   * 코너 회전 점검에 쓰는 최소회전반경(m) — **제원 완성 차종만** 값이 있다(`fleet.json`
   * `turn_check_radius_m` · DECISIONS §218-2). 막지 않고 비용 · 경고에만 쓴다(`domain/turning.ts`).
   * ★ `turn_radius_m`(검증 시 막는 값)과 섞지 않는다.
   */
  turn_check_radius_m?: number | null;
}

/** `web/data/fleet.json` 의 차량 한 대. 차종 선택 화면이 읽는다. */
export interface FleetVehicle {
  id: string;
  label: string;
  station?: string | null;
  count: number;
  /** 판정에 쓰는 값 */
  width_m: number;
  clearance_m: number;
  required_width_m: number;
  /** 회전 등급 (여유 · 주의 · 미판정). `turn_radius_ref_m` 이 null 일 때 화면이 띄운다 */
  turn_grade?: string | null;
  turn_unknown: boolean;
  turn_radius_verified: boolean;
  /**
   * 제원표 최소회전반경(m) — **참고값, 판정에 안 쓴다**(DECISIONS §212).
   * 그 차의 값이라고 말할 수 없으면 null 이다(제원표 공란 · `turn_unknown`).
   * ★ `VehicleSpec.turn_radius_m`(판정용)과 이름을 일부러 달리 둔다.
   */
  turn_radius_ref_m?: number | null;
  /** 제원 다섯이 다 있고 대응이 확정 — 코너 회전을 점검한다(§218-2) */
  spec_complete?: boolean;
  turn_check_radius_m?: number | null;
  wheelbase_m?: number | null;
  /** 판정하지 않는 값. 표시용으로만 흐른다 */
  length_m?: number | null;
  height_m?: number | null;
  match?: string | null;
  note?: string | null;
}

export interface Fleet {
  default: string;
  note: string;
  source?: string;
  vehicles: FleetVehicle[];
}

/** `navi_graph.json.style` — `web/config.js` 에서 추출된 판정 표현. */
export interface VerdictStyle {
  color: string;
  lightColor: string;
  label: string;
  desc: string;
}

/** `navi_graph.json.edges[]` 한 줄. */
export interface GraphEdge {
  seg_uid: string;
  verdict: Verdict;
  width_min_m: number | null;
  width_max_m?: number | null;
  length_m: number | null;
  seg_label?: string;
  road_name?: string;
  in_emd?: number | null;

  // ── 병목 상세 패널이 읽는 것 ────────────────────────────────
  /** 폭 표본이 구간을 덮은 비율 0~1. 화면의 "측정 신뢰도" 다 */
  width_cov?: number | null;
  /** 폭 표본 수. 1이면 `verdict()` 가 통과 확정을 보류한다 */
  n_sample?: number | null;
  /** 가장 가까운 CCTV 까지 거리(m). 25m 넘으면 영상판정이 성립 안 한다 */
  cctv_dist_m?: number | null;
  /** 왜 회색인가. no_cctv_band · no_cctv_thin · no_cctv_narrow · no_cctv_single */
  unknown_reason?: string | null;
  /**
   * 도로대장 폭(m). `width_min_m` 이 없을 때 속도 추정이 이것으로 떨어진다.
   *
   * ★ **판정에는 쓰지 않는다.** 정수 90% · 2.0 에 30% 몰려 있어 폭 판정의
   *   근거가 못 된다(대장 road_link.note). 속도 표는 미검증이라 이 정도
   *   해상도로 충분하다.
   */
  road_bt_m?: number | null;

  /**
   * 일방통행. 없으면 양방향(DECISIONS §215-1).
   *   1 a→b 로만 · -1 b→a 로만 · 2 일방통행인데 **방향을 모른다**
   * 비용과 경고는 `domain/rules.ts` 가 만든다.
   */
  ow?: 0 | 1 | -1 | 2;
  /**
   * 이 구간 **도로명**의 불법주정차 단속 건수(2022-01~2025-02). 없으면 0(§216-3).
   * ★ 도로 단위다 — 같은 도로명 구간은 같은 수. 현재 주차가 아니라 위험의 대리값이다.
   */
  park?: number;

  /**
   * **경로 안에서만** 붙는다 — 출발·도착 구간을 투영점에서 자른 사본이다(DECISIONS §218-3).
   * `src` 는 원본 `graph.edges` 인덱스, `t0..t1` 은 원본 형상(a→b) 위 비율이다.
   * 자른 사본의 `coords` · `length_m` 은 자른 부분만이고 `a` · `b` · `seg_uid` 는 원본 그대로다.
   * 발행물(`navi_graph.json`)에는 없다.
   */
  clip?: { src: number; t0: number; t1: number };

  /** 접합된 노드 인덱스 */
  a: number;
  b: number;
  loop?: number;
  coords: LngLat[];
}

/** `web/data/navi_graph.json`. */
export interface NaviGraph {
  crs: string;
  node_tol_m: number;
  counts: { nodes: number; edges: number; self_loops: number;
            oneway?: number; oneway_dir_known?: number; turn_bans?: number };
  style: Record<string, VerdictStyle>;
  nodes: LngLat[];
  edges: GraphEdge[];
  /** 지형 — 정본은 `web/config.js` terrain(§217-2). 옛 그래프에는 없다 */
  terrain?: { enabled: boolean; exaggeration: number };
  /** 회전 금지 `[들어오는 엣지, 노드, 나가는 엣지, TURN_TYPE]`. 옛 그래프에는 없다 */
  turns?: [number, number, number, number][];
}

/** 경로가 어기거나 확인이 필요한 통행 규칙 하나(`domain/rules.ts`). */
export interface RuleWarning {
  kind: "wrong_way" | "oneway_unknown" | "turn_ban" | "tight_turn";
  /** 경로 시작부터 그 자리까지(m) */
  atM: number;
  seg_uid: string;
  /** 화면 · 음성에 그대로 쓰는 말 */
  text: string;
}

/** `web/data/view.json`. 시점·경계의 정본이다. */
export interface View {
  build: string;
  center?: LngLat;
  bounds?: [LngLat, LngLat];
  maxBounds?: [LngLat, LngLat];
  minZoom?: number;
  maxZoom?: number;
  orthoBounds?: [number, number, number, number];
  /** 지형 타일 범위(terrain.py). 없으면 지형을 안 켠다 */
  terrainBounds?: [number, number, number, number];
  emdBounds?: [LngLat, LngLat];
}

/** `web/data/route_vehicle.json` — 파이썬 사전계산본. 대조에 쓴다. */
export type RouteVehicle = Record<string, {
  use: number; cost: number; passable: number; reachable: number;
}>;

/** 스냅 결과. */
export interface SnapResult {
  seg_uid: string;
  verdict: Verdict;
  width_min_m: number | null;
  seg_label?: string;
  /** 구간 시작점 기준 진행률 0~1 */
  progress: number;
  /** 붙은 점까지의 수직거리(m). 크면 도로 밖이다 */
  dist_m: number;
  /** 진행방향 방위각(도, 0=북) */
  bearing: number;
  /** heading 을 받아 진행방향으로 정렬했는가 */
  bearingKnown: boolean;
  point: LngLat;
  /** 믿어도 되는가. 도로 밖이거나 후보가 팽팽하면 false */
  confident: boolean;
  /** 활성 경로 위의 구간인가. false 면 이탈 후보다 */
  onRoute: boolean;
}

/** 경로 산출 결과. */
export interface RoutePlan {
  edges: GraphEdge[];
  /**
   * 엣지별 진행방향. `true` 면 `a → b` 로 지난다.
   *
   * ★ **거리를 세는 쪽이 전부 이것을 봐야 한다.** 경로가 구간을 거꾸로
   *   지나는 경우가 21% 이고(측정: 경로 40개 1,267구간 중 263), 스냅의
   *   `progress` 는 구간 형상 시작점 기준이라 역방향에서 0.2 가 실제로는
   *   80% 지점이다. 안 뒤집으면 주행거리가 앞뒤로 튀어 안내가 늦거나
   *   이미 지나서 나온다(2026-09-06).
   */
  forward: boolean[];
  /** 지나는 노드. `nodes[i]` 가 `edges[i]` 의 시작이다. 길이는 edges+1 */
  nodes: number[];
  /** 이어붙인 좌표열. Map Matching 에 그대로 던진다 */
  coords: LngLat[];
  /** 비용 합. 배수가 곱해진 **실효 거리**다 */
  cost: number;
  lengthM: number;
  /** 판정별 실거리(m). 불확실성 리본이 읽는다 */
  byVerdict: Record<string, number>;
  /** 지나는 통행 규칙 — 역주행 · 방향 미확인 일방통행 · 회전 금지(§215-1) */
  rules: RuleWarning[];
}

/** 위치 한 점. GPS 든 시뮬레이션이든 이 모양으로 들어온다. */
export interface Fix {
  lon: number;
  lat: number;
  /** 진행 방위각(도). 모르면 null — 받는 쪽이 이동량으로 만든다 */
  heading: number | null;
  /** replay = GPS 흉내(1Hz · 잡음 · 음영). 실주행과 같은 코드를 지난다(§213-3) */
  source: "gps" | "simulation" | "manual" | "replay";
  /**
   * 수평 정확도(m · 95% 신뢰). 모르면 `null`.
   *
   * ★ 2026-09-24 (PLAN §13 W13-2). 이 칸이 **없었다.** `gps.ts` 가
   *   `coords.accuracy` 를 안 읽었고 타입에도 자리가 없어, 신호가 50m 로
   *   흔들려도 화면은 초록 「안전 경로 안내중」 이었다. 그래서 08 화면
   *   (GPS 신호 약함)이 시연 전용으로 남아 있었다 — **알 방법이 없어서**다.
   */
  accuracy?: number | null;
  /**
   * 측위 시각(ms, `performance.now()` 시계). 위치 추정이 속도 × 경과로 예측한다.
   * 비어 있으면 받는 쪽이 받은 시각으로 채운다.
   */
  t?: number;
}

/** `web/data/context.geojson` 한 점 — 경로 주변 사정(§216-3). 판정과 무관하다 */
export type ContextKind = "speedbump" | "speedcam" | "child_zone" | "senior_zone";

/** `web/data/history.geojson.summary` — 실제 출동 → 현장 도착(초) */
export interface HistorySummary {
  points: number;
  resp_median_s: number | null;
  resp_p90_s: number | null;
  resp_n: number;
  by_center: Record<string, { n: number; median_s: number | null; straight_kmh: number | null }>;
  fire_donggu: { n: number; median_s: number | null };
  note: string;
}

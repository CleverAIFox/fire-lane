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
  length_m?: number;
  /** 미검증이면 null 로 발행된다. publish_web.py 가 그렇게 막는다 */
  wheelbase_m: number | null;
  turn_radius_m: number | null;
  clearance_m: number;
  wheelbase_verified?: boolean;
  turn_radius_verified?: boolean;
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
  /**
   * 회전 등급. **숫자가 아니다** — `turn_radius_verified` 가 false 인
   * 동안 화면이 숫자를 확정처럼 띄우지 않게 하려는 것이다.
   */
  turn_grade?: string | null;
  turn_unknown: boolean;
  turn_radius_verified: boolean;
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
  counts: { nodes: number; edges: number; self_loops: number };
  style: Record<string, VerdictStyle>;
  nodes: LngLat[];
  edges: GraphEdge[];
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
}

/** 위치 한 점. GPS 든 시뮬레이션이든 이 모양으로 들어온다. */
export interface Fix {
  lon: number;
  lat: number;
  /** 진행 방위각(도). 모르면 null — 받는 쪽이 이동량으로 만든다 */
  heading: number | null;
  source: "gps" | "simulation" | "manual";
}

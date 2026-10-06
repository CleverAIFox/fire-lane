/**
 * domain/handoff.ts — **관제 지령을 읽는 한 자리.**  (DECISIONS §386)
 *
 * ── 정책 (사용자 결정 2026-10-04 · §382-1) ─────────────────────
 * 이 내비는 일반 내비가 아니다. **관제가 정한 지령을 그대로 따라간다** —
 * 승객이 부른 경로가 기사 화면에 고정되는 호출택시 내비와 같은 꼴이다.
 * 소방차 기사는 목적지를 고르지 않는다.
 *
 * 고를 수 있게 두면 지령과 화면이 갈리고, 갈린 둘 중 어느 쪽이 기록으로
 * 남는지가 불분명해진다. 출동 기록은 관제가 든다.
 *
 * ── 왜 한 자리인가 ────────────────────────────────────────────
 * 종전에는 `new URLSearchParams(location.search)` 가 `App.tsx` 안에서만
 * **네 번** 따로 불렸다(사건 · 차종 · 센터 · dev). 깃발이 늘 때마다 한 번씩
 * 더 늘고, 「지령이 왔는가」를 묻고 싶으면 그 넷을 다 봐야 했다 — 물음이
 * 어디에도 없었다는 뜻이다. 여기가 그 물음의 집이다.
 *
 * IN    location.search
 * OUT   Handoff (순수 값)
 * 밖    **화면을 안 그린다.** 무엇을 숨길지는 부르는 쪽이 정한다.
 *       그리고 **좌표가 스코프 안인지도 안 본다** — 그것은 `setDestAt` 이
 *       스냅과 함께 든다. 여기가 드는 것은 「지령이 왔는가」 하나다.
 */
import type { LngLat } from "./geo";

export type Handoff = {
  /** 관제가 사건 위치를 줬다. **참이면 기사는 목적지를 고르지 않는다.** */
  readonly inherited: boolean;
  readonly incident: LngLat | null;
  readonly label: string | null;
  readonly sub: string | null;
  readonly vehicle: string | null;
  readonly station: string | null;
  /**
   * 경로 모드. **관제가 정한다** — 기사는 못 고른다.
   *
   * ★ 지령에 없으면 `null` 이다. 그때 내비는 `safe` 로 간다 — 그러나 그것은
   *   **기본값이지 지시가 아니고**, 화면이 그렇게 적는다. 없는 지시를 있는
   *   것처럼 그리면 기사가 관제가 고른 줄 안다(회색 = NULL · §140 과 같은 자리).
   */
  readonly route: RouteMode | null;
  /** `?demo=1` — 발표용. 경로를 따라 달린다(GPS 흉내가 아니다). */
  readonly demo: boolean;
  /** `?dev=1` — 시연 막대. **켜는 쪽을 명시한다**(§W13-1). */
  readonly dev: boolean;
};

/** 경로 모드 — 둘뿐이다. 「폭 기준」은 2026-10-05 에 **안전**으로 이름이 바뀌었다. */
export type RouteMode = "safe" | "fast";

/** 지시가 없을 때 내비가 가는 쪽. **기본값이고 지시가 아니다.** */
export const ROUTE_FALLBACK: RouteMode = "safe";

const EMPTY: Handoff = {
  inherited: false, incident: null, label: null, sub: null,
  vehicle: null, station: null, route: null, demo: false, dev: false,
};

/** `lon,lat` 를 읽는다. 하나라도 수가 아니면 **없는 것**으로 본다. */
function point(v: string | null): LngLat | null {
  if (!v) return null;
  const parts = v.split(",");
  // ★ 빈 칸은 수가 아니다. `Number("")` 가 **0** 이라 `?incident=,` 가
  //   기니만 앞바다(0,0)로 들어온다 — 시험이 그 자리를 물었다.
  if (parts.length !== 2 || parts.some((s) => s.trim() === "")) return null;
  const [lon, lat] = parts.map(Number);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  // 경위도 범위 밖은 오타다. 스코프 판정이 아니라 **자릿수** 판정이다.
  if (Math.abs(lon) > 180 || Math.abs(lat) > 90) return null;
  return [lon, lat];
}

/** 질의 문자열 → 지령. 부작용이 없다. */
export function readHandoff(search: string): Handoff {
  let q: URLSearchParams;
  try {
    q = new URLSearchParams(search);
  } catch {
    return EMPTY;
  }
  const incident = point(q.get("incident"));
  return {
    inherited: incident !== null,
    incident,
    label: incident ? (q.get("label") ?? "접수 위치") : null,
    sub: incident ? q.get("sub") : null,
    vehicle: q.get("vehicle"),
    station: q.get("station"),
    // ★ 어휘 밖은 **없는 것**으로 본다. `?route=빠름` 같은 오타를 받아
    //   `fast` 로 읽으면 지령에 없는 지시가 생긴다.
    route: q.get("route") === "fast" ? "fast"
      : q.get("route") === "safe" ? "safe" : null,
    // ★ 둘 다 **켜는 쪽을 명시**한다. `!== "0"` 로 두면 인자가 없는 배포 링크가
    //   켜진 채로 나가고, 운전석에서 손이 스치면 모의 주행이 실제 GPS 를
    //   대체한다(§W13-1 이 실제로 겪은 일이다).
    demo: q.get("demo") === "1",
    dev: q.get("dev") === "1",
  };
}

/**
 * 지령이 준 경로 모드. 없으면 **기본값**이고, 그 사실을 `fromOrder` 가 든다.
 *
 * ★ 2026-10-05 (DECISIONS §400). 종전에 이 모듈에는 `canPickDestination` 과
 *   `editHands` 가 있었다 — 「기사가 **고를 수 있는 경우**」를 전제로 손을
 *   열어 두는 문이다. 사람이 그 전제를 잘랐다:
 *
 *       「내비가 스스로 고를 수 있는건 없다니깐 완전 수동적이라고」
 *
 *   카카오택시 기사는 손님도 목적지도 경로도 안 고른다. 그러면 **고르는
 *   경우가 없으므로 문도 없다.** 문을 넓히는 대신 문과 손을 같이 들어냈고,
 *   그 자리를 `tests/navi` 의 「운전석에 바꾸는 손이 0 인가」가 든다 —
 *   손이 하나라도 생기면 운다. 문보다 그쪽이 강하다.
 */
export function routeOf(h: Handoff): { mode: RouteMode; fromOrder: boolean } {
  return h.route
    ? { mode: h.route, fromOrder: true }
    : { mode: ROUTE_FALLBACK, fromOrder: false };
}

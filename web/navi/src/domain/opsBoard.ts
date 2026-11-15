/**
 * domain/opsBoard.ts — **관제 쪽 전용**: 받은 메시지를 믿는 일 · 상황판 상태를 접는 일 · 끊김 자.  (PLAN #235 · DECISIONS §797-C)
 *
 * ★ 왜 갈랐나. `opsProtocol.ts` 는 내비(진입 청크)와 관제(`OpsApp`)가 같이 읽는 한 모듈이라 번들러가 **모듈째로** 공통 청크(=내비 진입 청크)에 놓는다 —
 *   내비가 안 쓰는 이 함수들(`asNaviMsg` · `opsReduce` · `opsAck` · `unitStale` · `OPS_EMPTY`)이 첫 화면에 따라왔다(소스맵 귀속 2.1KB · 격리 사본 실험 −1,616B).
 *   여기로 옮기면 관제 청크만 읽는다. 내비가 이 파일을 import 하면 도로 따라온다 — `test/opsPinPanel.test.ts` 가 내비 쪽 소스가 안 읽음을 문다.
 *
 * IN    `opsProtocol` 의 형 · `isObj` · `isLL`
 * OUT   `asNaviMsg` · `OPS_EMPTY` · `opsReduce` · `opsAck` · `UNIT_STALE_MS` · `unitStale`
 * 밖    메시지의 형과 상수(`HB_*` · 채널)는 `opsProtocol` 이 든다 — 내비도 쓴다
 */
import type { LngLat } from "./geo";
import { isLL, isObj } from "./opsProtocol";
import type { NaviMsg, OpsState, Unit } from "./opsProtocol";

/**
 * 받은 것을 믿기 전에 모양을 본다. 같은 채널 이름을 다른 탭(옛 판 · 다른 앱)이 쓸 수 있다.
 * ★ 모르는 것은 **버린다.** 반쯤 맞는 메시지를 반쯤 쓰면 그것이 거짓 화면이다.
 */
export function asNaviMsg(x: unknown): NaviMsg | null {
  if (!isObj(x) || typeof x.unit !== "string") return null;
  if (x.t === "bye") return { t: "bye", unit: x.unit };
  if (x.t === "share") {
    if (typeof x.shareId !== "string" || typeof x.at !== "number") return null;
    if (x.kind !== "bottleneck" && x.kind !== "blocked" && x.kind !== "arrival") return null;
    return {
      t: "share", unit: x.unit, shareId: x.shareId, kind: x.kind, at: x.at,
      text: typeof x.text === "string" ? x.text : "", point: isLL(x.point) ? x.point : null,
    };
  }
  if (x.t === "state") {
    if (typeof x.at !== "number" || typeof x.routeRev !== "number") return null;
    const inc = isObj(x.incident) && isLL(x.incident.point)
      ? { point: x.incident.point, label: String(x.incident.label ?? "") } : null;
    return {
      t: "state", unit: x.unit, at: x.at,
      vehicle: String(x.vehicle ?? ""), station: typeof x.station === "string" ? x.station : null,
      incident: inc, pos: isLL(x.pos) ? x.pos : null,
      brg: typeof x.brg === "number" ? x.brg : 0,
      status: String(x.status ?? ""), title: String(x.title ?? ""),
      remainM: typeof x.remainM === "number" ? x.remainM : null,
      etaText: typeof x.etaText === "string" ? x.etaText : null,
      routeRev: x.routeRev,
      demo: x.demo === true,
      route: Array.isArray(x.route) && x.route.every(isLL) ? (x.route as LngLat[]) : undefined,
    };
  }
  return null;
}

export const OPS_EMPTY: OpsState = { units: {}, feed: [] };

/** 관제 화면이 받은 메시지를 접는다. **새 객체를 낸다** — React 가 바뀐 줄 안다 */
export function opsReduce(st: OpsState, m: NaviMsg, now: number): OpsState {
  if (m.t === "bye") {
    const units = { ...st.units };
    delete units[m.unit];
    return { ...st, units };
  }
  if (m.t === "share") {
    if (st.feed.some((f) => f.shareId === m.shareId)) return st;   // 다시 보내기는 한 줄
    return { ...st, feed: [{ ...m, ackedAt: null }, ...st.feed].slice(0, 50) };
  }
  const prev = st.units[m.unit];
  // 경로는 바뀔 때만 온다. 판 번호가 같으면 가진 것을 쓴다
  const route = m.route !== undefined ? m.route
    : prev && prev.routeRev === m.routeRev ? prev.route : null;
  return {
    ...st,
    units: { ...st.units, [m.unit]: { unit: m.unit, last: m, route, routeRev: m.routeRev, heardAt: now } },
  };
}

export function opsAck(st: OpsState, shareId: string, now: number): OpsState {
  return { ...st, feed: st.feed.map((f) => (f.shareId === shareId ? { ...f, ackedAt: now } : f)) };
}

/** 이만큼(ms) 소식이 없으면 그 차는 연결이 끊긴 것으로 본다 */
export const UNIT_STALE_MS = 5000;
export function unitStale(u: Unit, now: number): boolean {
  return now - u.heardAt > UNIT_STALE_MS;
}


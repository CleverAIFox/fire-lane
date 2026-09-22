/**
 * domain/opsProtocol.ts — **내비 ↔ 관제 화면이 주고받는 말.**  (DECISIONS §214-3)
 *
 * ══ 왜 생겼나 ═══════════════════════════════════════════════════
 * 와이어프레임 18~21 · 23 은 「관제에 공유 → 대기 → 관제 확인」 이다. 관제가 없어서
 * 타이머로 흉내 냈다(`useShare` 의 「시연」). 2026-09-22 에 관제 화면(새 GIS)을 같은
 * 앱 안에 세우면서 **진짜 상대**가 생겼다 — 내비 탭이 위치 · 경로 · 상태 · 공유를
 * 보내고, 관제 탭의 사람이 「확인」 을 누르면 그 확인이 내비로 돌아간다.
 *
 * ★ 전송은 `BroadcastChannel` 이다(`app/opsLink.ts`). **같은 브라우저의 탭끼리만** 닿는다.
 *   서버가 아니다 — 시연 한 대에서 두 창을 띄우는 구성이다. 실제 관제 시스템(119
 *   종합상황실)과 잇는 것은 이 말(메시지 모양)을 그대로 두고 전송만 갈아 끼우는 일이다.
 *   그래서 모양을 여기 **순수하게** 둔다 — 전송을 모른다.
 *
 * ★ 관제가 **없으면** 종전처럼 흉내로 돈다. 있는지 없는지는 관제의 심장박동(hb)으로 안다.
 *   흉내일 때는 화면이 「시연」 을 단다 — 그 규율은 그대로다.
 */
import type { LngLat } from "./geo";

export const OPS_CHANNEL = "fire-lane-ops";
/** 관제 심장박동 주기 · 이만큼 안 오면 관제가 없는 것이다(ms) */
export const HB_MS = 1500;
export const HB_TTL_MS = 4000;
/** 관제 확인을 이만큼 기다리고 안 오면 실패(20)다(ms). 사람이 누르는 시간이다 */
export const ACK_TIMEOUT_MS = 30000;

export type ShareKind = "bottleneck" | "blocked" | "arrival";

/** 내비가 보내는 상태. 0.5초마다, 또는 바뀔 때 */
export interface UnitState {
  t: "state";
  unit: string;            // 내비 세션 id
  at: number;              // ms epoch
  vehicle: string;         // "펌프차 (중형)"
  station: string | null;
  incident: { point: LngLat; label: string } | null;
  pos: LngLat | null;
  brg: number;
  status: string;          // StatusKey
  title: string;           // 상단바 제목(사람이 읽는 것)
  remainM: number | null;
  etaText: string | null;
  /** 경로가 바뀔 때만 좌표를 싣는다. 같으면 routeRev 만 */
  routeRev: number;
  route?: LngLat[] | null;
}

export interface ShareMsg {
  t: "share";
  unit: string;
  shareId: string;
  kind: ShareKind;
  at: number;
  text: string;
  point: LngLat | null;
}

export interface ByeMsg { t: "bye"; unit: string }

export type NaviMsg = UnitState | ShareMsg | ByeMsg;

export interface HbMsg { t: "hb"; ops: string; at: number }
export interface AckMsg { t: "ack"; shareId: string; unit: string; at: number; by: string }
export type OpsMsg = HbMsg | AckMsg;

const isObj = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null;
const isLL = (x: unknown): x is LngLat =>
  Array.isArray(x) && x.length === 2 && x.every((v) => typeof v === "number" && Number.isFinite(v));

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
      route: Array.isArray(x.route) && x.route.every(isLL) ? (x.route as LngLat[]) : undefined,
    };
  }
  return null;
}

export function asOpsMsg(x: unknown): OpsMsg | null {
  if (!isObj(x)) return null;
  if (x.t === "hb" && typeof x.ops === "string" && typeof x.at === "number") {
    return { t: "hb", ops: x.ops, at: x.at };
  }
  if (x.t === "ack" && typeof x.shareId === "string" && typeof x.unit === "string"
      && typeof x.at === "number") {
    return { t: "ack", shareId: x.shareId, unit: x.unit, at: x.at, by: String(x.by ?? "관제") };
  }
  return null;
}

// ── 관제 쪽 상태 ────────────────────────────────────────────────

export interface Unit {
  unit: string;
  last: UnitState;
  route: LngLat[] | null;
  routeRev: number;
  /** 마지막으로 들은 시각(ms). 오래되면 「연결 끊김」 */
  heardAt: number;
}

export interface FeedItem extends ShareMsg {
  ackedAt: number | null;
}

export interface OpsState {
  units: Record<string, Unit>;
  feed: FeedItem[];
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

/** 관제가 지금 듣고 있나 */
export function opsPresent(lastHbAt: number | null, now: number): boolean {
  return lastHbAt != null && now - lastHbAt <= HB_TTL_MS;
}

/** 공유 한 건의 화면 상태. 전송 → 대기 → 확인 · 시간 초과면 실패 */
export function shareState(sentAt: number, ackedAt: number | null, now: number,
                           timeoutMs = ACK_TIMEOUT_MS): "awaiting" | "acked" | "failed" {
  if (ackedAt != null) return "acked";
  return now - sentAt > timeoutMs ? "failed" : "awaiting";
}

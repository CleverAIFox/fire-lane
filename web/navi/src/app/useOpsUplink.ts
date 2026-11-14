/**
 * app/useOpsUplink.ts — 내비 쪽 관제 연결.  (DECISIONS §214-3)
 *
 *   내비 ──state(0.5초) · share──▶ 관제
 *   내비 ◀──────hb(1.5초) · ack──── 관제
 *
 * ★ 상태는 ref 로 받아 **주기적으로** 보낸다. React 가 렌더할 때마다 보내면 초당
 *   수십 번이 되고, 위치는 어차피 60fps ref(`live`)에 있다.
 * ★ 경로 좌표는 **바뀔 때만** 싣는다(`routeRev`). 0.5초마다 수백 점을 보낼 이유가 없다.
 *   관제가 늦게 켜지면 경로를 모르므로, 관제의 첫 심장박동에 한 번 더 싣는다.
 *
 * ★ 2026-11-14 (PLAN #234 — 「끝에 끊김」). 훅 안에 있던 주기 · 받기를 **React 를 모르는 `startUplink`** 로 꺼냈다 —
 *   훅 안에 있으면 가짜 타이머로 못 잰다(시험 환경에 DOM 이 없다). 같이 고친 것 셋:
 *     ① 관제를 **들은 시각을 내 시계로** 적는다. 종전에는 `hb.at`(관제 기계의 시계)을 내 `Date.now()` 와 뺐다 —
 *        두 기계의 시계가 4초 넘게 어긋나면 관제가 멀쩡히 있어도 「관제 없음(시연)」 이고, 반대로 어긋나면 떠난 관제가 남는다.
 *        탭끼리(`BroadcastChannel`)는 같은 시계라 안 보였고 **중개자로 다른 기계가 붙으면서** 생긴 결함이다.
 *     ② 소켓이 **붙는 순간** 한 통을 경로와 함께 보낸다(`openLink` 의 `onOpen`) — 다음 주기를 안 기다린다.
 *     ③ 탭이 **앞으로 돌아오는 순간** 한 통을 보낸다(`visibilitychange`) — 묶였던 타이머가 풀리기를 안 기다린다.
 *   타이머가 묶인 **동안**은 못 고친다(브라우저가 정한다) — 무엇이 얼마나 묶이는지는 `test/opsUplink.test.ts` 가 수로 든다.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  HB_MS, HB_TTL_MS, asOpsMsg, opsPresent, type ShareKind, type UnitState,
} from "../domain/opsProtocol";
import { newId, openLink, type Link } from "../infra/opsLink";
import type { LngLat } from "../domain/geo";

export type UnitSnapshot = Omit<UnitState, "t" | "unit" | "at" | "routeRev" | "route"> & {
  route: LngLat[] | null;
};

/** 상태를 보내는 주기(ms). 관제의 「끊김」 자(`UNIT_STALE_MS`)가 이 수의 배수로 넉넉해야 한다 — 시험이 문다 */
export const STATE_MS = 500;

/** `document` 에서 쓰는 것만 — 시험이 가짜를 넣는다 */
export type VisDoc = Pick<Document, "addEventListener" | "removeEventListener" | "visibilityState">;

export interface UplinkOn {
  /** 주기마다(상태가 없어도). 화면 시계 */
  tick?: (now: number) => void;
  /** 관제 심장박동을 들었다 — **내 시계**의 들은 시각 */
  hb?: (heardAt: number) => void;
  /** 내 공유를 관제가 확인했다 */
  ack?: (shareId: string, at: number) => void;
  /** 없으면 탭 가시성을 안 본다(시험 · DOM 없는 환경) */
  doc?: VisDoc | null;
}

export interface Uplink {
  readonly link: Link;
  /** 주기를 안 기다리고 지금 한 통 */
  kick(): void;
  /** 떠난다고 말한다(`pagehide`) */
  bye(): void;
  stop(): void;
}

/**
 * 연결 하나를 열고 상태를 주기로 보낸다. **React 를 모른다** — 훅은 이것을 감쌀 뿐이다.
 * @param snap 지금 상태. null 이면 그 주기는 안 보낸다
 */
export function startUplink(unit: string, snap: () => UnitSnapshot | null, on: UplinkOn = {}): Uplink {
  const rev = { route: null as LngLat[] | null, n: 0, sentN: -1 };
  let needRoute = true;
  let heardAt: number | null = null;
  // ★ 처음 보는 관제 id 의 `hb` 가 오면 경로를 다시 싣는다(DECISIONS §755 · §746 의 둘째 관제) — 첫 관제의 `hb` 가 흐르는 중에 붙은 둘째 관제는 종전 신호(`hb` 가 4초 넘게 끊김)가 안 서 경로를 못 봤다.
  const seenOps = new Set<string>();

  const send = () => {
    const s = snap();
    if (!s) return;
    if (s.route !== rev.route) { rev.route = s.route; rev.n += 1; }
    const withRoute = needRoute || rev.sentN !== rev.n;
    const { route, ...rest } = s;
    l.send({
      t: "state", unit, at: Date.now(), routeRev: rev.n, ...rest,
      ...(withRoute ? { route } : {}),
    });
    // ★ 못 나간 것(소켓이 아직 안 붙음)도 「보냈다」로 센다 — 종전과 같다. 그래서 붙는 순간 `onOpen` 이 경로를 다시 싣게 한다.
    if (withRoute) { rev.sentN = rev.n; needRoute = false; }
  };

  const l: Link = openLink((d) => {
    const m = asOpsMsg(d);
    if (!m) return;
    if (m.t === "hb") {
      const now = Date.now();
      if (!seenOps.has(m.ops)) { seenOps.add(m.ops); needRoute = true; }
      if (heardAt == null || now - heardAt > HB_TTL_MS) needRoute = true;   // 관제가 새로 켜졌다
      heardAt = now;                                                        // ★ `m.at` 이 아니다 — 남의 시계다(머리말 ①)
      on.hb?.(now);
    } else if (m.t === "ack" && m.unit === unit) {
      on.ack?.(m.shareId, m.at);
    }
    // ★ `who` 를 넘긴다 — 중개자가 관제와 차를 **다른 문으로** 받는다.
    //   어느 전송으로 갈지는 `openLink` 가 설정을 보고 고른다(§343).
  }, { kind: "unit", unit }, () => { needRoute = true; send(); });

  const tick = setInterval(() => { on.tick?.(Date.now()); send(); }, STATE_MS);
  const doc = on.doc ?? null;
  const onVis = () => { if (doc?.visibilityState === "visible") { on.tick?.(Date.now()); send(); } };
  doc?.addEventListener("visibilitychange", onVis);
  const bye = () => l.send({ t: "bye", unit });

  return {
    link: l,
    kick: send,
    bye,
    stop() { bye(); clearInterval(tick); doc?.removeEventListener("visibilitychange", onVis); l.close(); },
  };
}

export function useOpsUplink(snap: UnitSnapshot | null) {
  const unit = useRef(newId("navi")).current;
  const link = useRef<Link | null>(null);
  const snapRef = useRef(snap);
  snapRef.current = snap;
  const [lastHb, setLastHb] = useState<number | null>(null);
  const [acks, setAcks] = useState<Record<string, number>>({});
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const u = startUplink(unit, () => snapRef.current, {
      tick: setNow,
      hb: setLastHb,
      ack: (shareId, at) => setAcks((a) => ({ ...a, [shareId]: at })),
      doc: typeof document !== "undefined" ? document : null,
    });
    link.current = u.link;
    window.addEventListener("pagehide", u.bye);
    return () => { window.removeEventListener("pagehide", u.bye); u.stop(); };
  }, [unit]);

  const sendShare = useCallback((kind: ShareKind, text: string, point: LngLat | null): string => {
    const shareId = newId("sh");
    link.current?.send({ t: "share", unit, shareId, kind, at: Date.now(), text, point });
    return shareId;
  }, [unit]);

  return {
    unit,
    present: opsPresent(lastHb, now),
    available: link.current?.available ?? typeof BroadcastChannel !== "undefined",
    acks, now, sendShare,
    /** 관제 심장박동 주기 — 화면 문구용 */
    hbMs: HB_MS,
  };
}

export type OpsUplink = ReturnType<typeof useOpsUplink>;

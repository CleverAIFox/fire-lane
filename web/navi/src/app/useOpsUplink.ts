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
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  HB_MS, asOpsMsg, opsPresent, type ShareKind, type UnitState,
} from "../domain/opsProtocol";
import { newId, openLink, type Link } from "../infra/opsLink";
import type { LngLat } from "../domain/geo";

export type UnitSnapshot = Omit<UnitState, "t" | "unit" | "at" | "routeRev" | "route"> & {
  route: LngLat[] | null;
};

export function useOpsUplink(snap: UnitSnapshot | null) {
  const unit = useRef(newId("navi")).current;
  const link = useRef<Link | null>(null);
  const snapRef = useRef(snap);
  snapRef.current = snap;
  const [lastHb, setLastHb] = useState<number | null>(null);
  const [acks, setAcks] = useState<Record<string, number>>({});
  const [now, setNow] = useState(() => Date.now());
  const rev = useRef({ route: null as LngLat[] | null, n: 0, sentN: -1 });
  const needRoute = useRef(true);

  useEffect(() => {
    const l = openLink((d) => {
      const m = asOpsMsg(d);
      if (!m) return;
      if (m.t === "hb") {
        setLastHb((prev) => {
          if (prev == null || Date.now() - prev > 4000) needRoute.current = true;   // 관제가 새로 켜졌다
          return m.at;
        });
      } else if (m.t === "ack" && m.unit === unit) {
        setAcks((a) => ({ ...a, [m.shareId]: m.at }));
      }
    });
    link.current = l;
    const tick = setInterval(() => {
      setNow(Date.now());
      const s = snapRef.current;
      if (!s) return;
      const r = rev.current;
      if (s.route !== r.route) { r.route = s.route; r.n += 1; }
      const withRoute = needRoute.current || r.sentN !== r.n;
      const { route, ...rest } = s;
      l.send({
        t: "state", unit, at: Date.now(), routeRev: r.n, ...rest,
        ...(withRoute ? { route } : {}),
      });
      if (withRoute) { r.sentN = r.n; needRoute.current = false; }
    }, 500);
    const bye = () => l.send({ t: "bye", unit });
    window.addEventListener("pagehide", bye);
    return () => { bye(); clearInterval(tick); window.removeEventListener("pagehide", bye); l.close(); };
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

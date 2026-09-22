/**
 * app/useShare.ts — 관제 공유.  (와이어프레임 18 · 19 · 20 · 21 · 23)
 *
 *   idle ──공유──▶ sending ──▶ awaiting ──▶ acked
 *                                   └──────▶ failed ──다시──▶ sending
 *
 * ── ★ 2026-09-22 · 관제가 있으면 **진짜로** 보낸다 (DECISIONS §214-3) ──────
 * 같은 앱에 관제 화면(`?view=ops`)이 생겼다. 관제 탭이 열려 있으면(심장박동이 오면)
 * 공유는 관제로 가고, **관제의 사람이 「확인」 을 눌러야** 21(관제 확인)이 된다.
 * 30초 안에 확인이 없으면 20(실패)이다.
 *
 * 관제가 **없으면** 종전처럼 타이머로 흉내 내고 `simulated: true` — 상태칩이 「시연」
 * 을 단다. 흉내인 줄 모르고 보면 그것이 거짓 화면이다(`domain/status.ts` 주입 표지와
 * 같은 규율).
 *
 * ★ `failNext` 는 두 경우 다 먹는다 — 20(실패)을 검수하는 단추다.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { shareState, type ShareKind } from "../domain/opsProtocol";
import type { OpsUplink } from "./useOpsUplink";
import type { LngLat } from "../domain/geo";

export type ShareState = "idle" | "sending" | "awaiting" | "acked" | "failed";
export type { ShareKind };

export interface ShareInfo {
  state: ShareState;
  kind: ShareKind | null;
  /** 관제 확인 시각(HH:MM) */
  ackedAt: string | null;
  /** 관제가 없어 흉내 냈다 */
  simulated: boolean;
}

/** 흉내 지연(ms). 실제 관제 응답 시간을 잰 적이 없다 — 시연용 값이다 */
const SEND_MS = 1200;
const ACK_MS = 2600;

function hhmm(d = new Date()): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function useShare(up?: OpsUplink) {
  const [info, setInfo] = useState<ShareInfo>({
    state: "idle", kind: null, ackedAt: null, simulated: true,
  });
  const [failNext, setFailNext] = useState(false);
  const timers = useRef<number[]>([]);
  const failRef = useRef(failNext);
  failRef.current = failNext;
  /** 진짜 전송 중인 건 */
  const live = useRef<{ id: string; kind: ShareKind; at: number } | null>(null);

  const clear = () => { timers.current.forEach((t) => clearTimeout(t)); timers.current = []; };
  useEffect(() => clear, []);

  // ── 진짜 전송: 관제 확인 · 시간 초과를 본다 ───────────────────
  useEffect(() => {
    const l = live.current;
    if (!l || !up) return;
    const st = shareState(l.at, up.acks[l.id] ?? null, up.now);
    if (st === "acked") {
      live.current = null;
      setInfo({ state: "acked", kind: l.kind, ackedAt: hhmm(new Date(up.acks[l.id])), simulated: false });
    } else if (st === "failed") {
      live.current = null;
      setInfo({ state: "failed", kind: l.kind, ackedAt: null, simulated: false });
    }
  }, [up?.acks, up?.now]); // eslint-disable-line react-hooks/exhaustive-deps

  const share = useCallback((kind: ShareKind, text = "", point: LngLat | null = null) => {
    clear();
    live.current = null;
    const real = !!up?.present;
    setInfo({ state: "sending", kind, ackedAt: null, simulated: !real });
    if (real && up) {
      if (failRef.current) {
        setFailNext(false);
        timers.current.push(window.setTimeout(
          () => setInfo({ state: "failed", kind, ackedAt: null, simulated: false }), SEND_MS));
        return;
      }
      const id = up.sendShare(kind, text, point);
      live.current = { id, kind, at: Date.now() };
      timers.current.push(window.setTimeout(
        () => setInfo((i) => (i.state === "sending" ? { ...i, state: "awaiting" } : i)), 400));
      return;
    }
    timers.current.push(window.setTimeout(() => {
      if (failRef.current) {
        setFailNext(false);
        setInfo({ state: "failed", kind, ackedAt: null, simulated: true });
        return;
      }
      setInfo({ state: "awaiting", kind, ackedAt: null, simulated: true });
      timers.current.push(window.setTimeout(() => {
        setInfo({ state: "acked", kind, ackedAt: hhmm(), simulated: true });
      }, ACK_MS));
    }, SEND_MS));
  }, [up]);

  /** 시연 막대가 상태를 직접 넣는다(검수용) */
  const force = useCallback((state: ShareState, kind: ShareKind = "bottleneck") => {
    clear();
    live.current = null;
    setInfo({ state, kind: state === "idle" ? null : kind,
              ackedAt: state === "acked" ? hhmm() : null, simulated: true });
  }, []);

  const reset = useCallback(() => { clear(); force("idle"); }, [force]);

  return { info, share, force, reset, failNext, setFailNext };
}

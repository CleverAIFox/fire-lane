/**
 * app/useShare.ts — 관제 공유.  (와이어프레임 18 · 19 · 20 · 21 · 23)
 *
 *   idle ──공유──▶ sending ──▶ awaiting ──▶ acked
 *                                   └──────▶ failed ──다시──▶ sending
 *
 * ★ **서버가 없다.** 관제 시스템과 잇는 곳이 아직 없으므로 이 훅은 전송을
 *   흉내 낸다 — 타이머로 상태를 넘긴다. 그 사실을 화면이 말해야 한다:
 *   `simulated: true` 이면 상태칩이 「시연」 표지를 단다. 흉내인 줄 모르고
 *   보면 그것이 거짓 화면이다(`domain/status.ts` 의 주입 표지와 같은 규율).
 *
 * ★ 실패 경로(20)도 흉내 낼 수 있어야 검수가 된다 — `failNext` 를 켜면
 *   다음 전송이 실패로 끝난다.
 *
 * ★ 와이어프레임 18 · 19 · 20 세 장은 2026-09-21 현재 **같은 그림**이다
 *   (파일 크기까지 같다). 공유 상태를 어디에 띄울지는 아직 안 정해졌다 —
 *   여기서는 상단바 오른쪽 아래 상태칩으로 둔다. 지혜님 확인 사항이다.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export type ShareState = "idle" | "sending" | "awaiting" | "acked" | "failed";

/** 무엇을 공유했나 — 병목 · 통행 불가 · 도착 보고 */
export type ShareKind = "bottleneck" | "blocked" | "arrival";

export interface ShareInfo {
  state: ShareState;
  kind: ShareKind | null;
  /** 관제 확인 시각(HH:MM) */
  ackedAt: string | null;
  simulated: true;
}

/** 흉내 지연(ms). 실제 관제 응답 시간을 잰 적이 없다 — 시연용 값이다 */
const SEND_MS = 1200;
const ACK_MS = 2600;

function hhmm(d = new Date()): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function useShare() {
  const [info, setInfo] = useState<ShareInfo>({
    state: "idle", kind: null, ackedAt: null, simulated: true,
  });
  const [failNext, setFailNext] = useState(false);
  const timers = useRef<number[]>([]);
  const failRef = useRef(failNext);
  failRef.current = failNext;

  const clear = () => { timers.current.forEach((t) => clearTimeout(t)); timers.current = []; };
  useEffect(() => clear, []);

  const share = useCallback((kind: ShareKind) => {
    clear();
    setInfo({ state: "sending", kind, ackedAt: null, simulated: true });
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
  }, []);

  /** 시연 막대가 상태를 직접 넣는다(검수용) */
  const force = useCallback((state: ShareState, kind: ShareKind = "bottleneck") => {
    clear();
    setInfo({ state, kind: state === "idle" ? null : kind,
              ackedAt: state === "acked" ? hhmm() : null, simulated: true });
  }, []);

  const reset = useCallback(() => { clear(); force("idle"); }, [force]);

  return { info, share, force, reset, failNext, setFailNext };
}

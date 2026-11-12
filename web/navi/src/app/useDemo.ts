/**
 * app/useDemo.ts — 시연 모드의 상태 · 켜기 규칙.  (DECISIONS §713 · ⓲C)
 *
 * ★ 시연은 위치원 선택이 아니라 **모드**다 — GPS 와 무관하다. 켜진 동안 `usePositionSource` 는 GPS 를 아예 안 구독한다.
 * ★ 실주행 중(주행 단계 · 구역 안 측위가 오는 중)에는 켜기를 거절한다(`canStartDemo`). 끄면 시연 차가 선다.
 * ★ 주행 중에 켜면 곧바로 배속 1 로 달린다 — 주행 전이면 `start()` 가 `demoRef` 를 보고 달린다.
 *
 * IN    단계 · 배속 설정자 · 알림 설정자
 * OUT   demo · gpsState · setGpsState(위치원이 알린다) · setDemo · demoRef
 * 밖    시연을 돌리는 일(위치원)은 안 한다 — `usePositionSource`.
 */
import { useCallback, useRef, useState } from "react";
import { canStartDemo, type GpsState } from "../domain/demo";
import type { Phase } from "../domain/types";

export function useDemo(phase: Phase, setSimSpeed: (v: number) => void, setNotice: (m: string | null) => void) {
  const [demo, setDemoState] = useState(false);
  const [gpsState, setGpsState] = useState<GpsState>("idle");
  const demoRef = useRef(false);
  const setDemo = useCallback((on: boolean): boolean => {
    if (on && !canStartDemo(phase, gpsState, demoRef.current)) return false;
    demoRef.current = on; setDemoState(on); setNotice(null);
    setSimSpeed(on && phase === "guiding" ? 1 : 0);
    return true;
  }, [phase, gpsState, setSimSpeed, setNotice]);
  return { demo, demoRef, gpsState, setGpsState, setDemo };
}

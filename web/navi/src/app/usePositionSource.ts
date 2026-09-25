/**
 * app/usePositionSource.ts — 측위가 **어디서 오나**. 셋 중 하나를 골라 잇는다.
 *
 *   실주행        `infra/position/gps`         실제 geolocation
 *   GPS 흉내      `infra/position/replay`      1Hz · σ5m · 40초마다 8초 음영
 *   경로 따라가기 `infra/position/simulation`  60fps 정답 점
 *
 * ── 왜 갈랐나 (PLAN §1 #129) ────────────────────────────────────
 * ★ 2026-09-25. `useNavigation` 이 570줄로 넷을 들었다. 위치원 배선은 그 중 **바깥
 *   세계와 붙는 유일한 자리**다 — 시작 · 정지 · 갈아타기 · 멈춘 자리 기억이 한 덩어리로
 *   묶여 있어야 새 위치원을 더할 때 읽을 곳이 하나다.
 *
 * ★ 폐루프 검수는 gpsSim 으로 한다. 경로 따라가기는 추정이 틀려도 맞아 보인다(§213-3).
 *
 * ★ 2026-09-21. 배속을 바꾸면 시뮬레이션이 **처음부터 다시** 돌았다 — 소스를 새로
 *   만들면서 진행 거리를 버렸기 때문이다. 같은 경로면 멈춘 자리에서 이어 간다.
 *   경로가 바뀌면(우회·재탐색) 새 경로는 현위치에서 시작하므로 0 이 맞다.
 *
 * IN    단계 · 재생 배속 · 경로 · 위치원 선택 · 측위 받는 함수 · 끝 알림 · 알림 쓰기
 * OUT   teleport(시연) · forget(멈춘 자리를 잊는다)
 * 밖    측위를 해석하지 않는다. 경로 위 어디인지는 `domain/progress` 가 답하고, 그것을
 *       상태로 옮기는 것은 `useNavigation` 의 `onFix` 다.
 */
import { useCallback, useEffect, useRef } from "react";
import { createGpsSource } from "../infra/position/gps";
import { createSimulationSource } from "../infra/position/simulation";
import { createReplaySource } from "../infra/position/replay";
import type { Fix, Phase, PosMode, RoutePlan } from "../domain/types";

/** 위치원이 공통으로 내주는 손잡이 — 앞으로 감기와 지금까지 온 거리 */
interface Source {
  seek(m: number): void;
  readonly alongM?: number;
  readonly truthM?: number;
}

export function usePositionSource(a: {
  phase: Phase;
  simSpeed: number;
  plan: RoutePlan | null;
  posMode: PosMode;
  onFix: (f: Fix) => void;
  /** 시뮬레이션이 경로 끝에 닿았다 */
  onEnd: () => void;
  onNotice: (m: string | null) => void;
}) {
  const { phase, simSpeed, plan, posMode, onFix, onEnd, onNotice } = a;
  const srcRef = useRef<Source | null>(null);
  const simAt = useRef<{ plan: RoutePlan | null; along: number }>({ plan: null, along: 0 });

  useEffect(() => {
    // ★ 2026-09-21. 주행 전(00 · 01 · 02)에는 위치를 안 받는다. 출발지가
    //   안전센터라 현위치가 쓰이지 않고, 받으면 「위치 없음」 알림만 뜬다.
    if (phase !== "guiding") return;
    if (simSpeed > 0 && plan) {
      // 속도는 구간에서 읽는다. simSpeed 는 **재생 배속**이다.
      if (posMode === "gpsSim") {
        // ★ GPS 흉내 — 1Hz · σ5m · 40초마다 8초 음영. 마커는 추정기가 낸 자리다
        const src = createReplaySource(plan, { rate: simSpeed }, onEnd);
        if (simAt.current.plan === plan) src.seek(simAt.current.along);
        srcRef.current = src;
        const stop = src.start(onFix);
        return () => { simAt.current = { plan, along: src.truthM }; srcRef.current = null; stop(); };
      }
      const src = createSimulationSource(plan, simSpeed, onEnd);
      if (simAt.current.plan === plan) src.seek(simAt.current.along);
      srcRef.current = src;
      const stop = src.start(onFix);
      return () => { simAt.current = { plan, along: src.alongM }; srcRef.current = null; stop(); };
    }
    // ★ 실제 GPS 가 없는 기기(데스크톱 · 거부)에서 「위치 없음 (User denied…)」 이 주행
    //   화면을 덮었다. 무엇을 하면 되는지를 말한다.
    return createGpsSource().start(onFix, (m) => onNotice(
      m.startsWith("위치 없음") ? "실제 GPS 신호가 없다 — 시연은 아래 ▶ 로 주행한다" : m));
  }, [phase, simSpeed, plan, onFix, posMode]); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * 시연 — 차를 앞으로 순간이동시킨다. GPS 가 음영에서 튀어 돌아온 상황이다.
   * ★ 화면이 따라붙는지(마커 · 안내 · 남은 거리)를 보는 단추다. 위치원만 옮기고
   *   추정기에는 아무것도 알리지 않는다 — 알아채는 것이 추정기의 일이다.
   */
  const teleport = useCallback((m: number) => {
    const s = srcRef.current;
    if (!s) return;
    const at = s.truthM ?? s.alongM ?? 0;
    s.seek(at + m);
  }, []);

  /** 멈춘 자리를 잊는다. 출동을 처음부터 다시 할 때 부른다 */
  const forget = useCallback(() => { simAt.current = { plan: null, along: 0 }; }, []);

  return { teleport, forget };
}

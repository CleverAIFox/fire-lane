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
import { noGpsNotice, type GpsState } from "../domain/demo";
import { outsideNotice, outsideServiceArea, metresOutside } from "../domain/serviceArea";
import type { LngLat } from "../domain/geo";
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
  /** `view.json` 의 `maxBounds`. 없으면 범위 판정을 **안 한다**(§275) */
  area?: readonly [LngLat, LngLat];
  /**
   * 시연이 켜져 있다(DECISIONS §713) — **GPS 를 아예 안 받는다.** 시연이 멈춰 있어도(■) 실제 GPS 로 안 돌아간다 —
   * 구역 밖에서 서울 측위가 카메라를 서울로 끌고 가던 길이 이것이었다.
   */
  demo: boolean;
  /** 측위 상태가 바뀌었다 — ① 없음 · ② 구역 밖 · ③ 실주행(`domain/demo.ts`). 안내 문구와 단추는 위에서 같은 규칙으로 낸다 */
  onGpsState: (g: GpsState) => void;
}) {
  const { phase, simSpeed, plan, posMode, onFix, onEnd, onNotice, area, demo, onGpsState } = a;
  const srcRef = useRef<Source | null>(null);
  /** 범위 밖 알림은 **한 번만.** 1Hz 로 뜨면 그것이 화면을 덮는다 */
  const saidOut = useRef(false);
  const simAt = useRef<{ plan: RoutePlan | null; along: number }>({ plan: null, along: 0 });
  // ★ 2026-11-12 (DECISIONS §708). 시연 차가 **섰다**(■) = 속도 0 인 측위 하나. 위치원이 조용히 사라지면 마지막 속도가 「달리는 중」으로 남아 병목 「자세히」 의 잠금이
  //   영영 안 풀린다(음영과 구별되지 않는다 — `domain/motion.ts` `silenceStops`). 실제 GPS 로 돌아갈 때는 안 낸다 — 그 정지는 GPS 가 말한다.
  const lastSim = useRef<Fix | null>(null);

  useEffect(() => {
    // ★ 2026-09-21. 주행 전(00 · 01 · 02)에는 위치를 안 받는다. 출발지가
    //   안전센터라 현위치가 쓰이지 않고, 받으면 「위치 없음」 알림만 뜬다.
    if (phase !== "guiding") return;
    if (!(simSpeed > 0 && plan) && lastSim.current) {
      onFix({ ...lastSim.current, speedMps: 0 });       // 시연 차가 섰다
      lastSim.current = null;
    }
    if (simSpeed > 0 && plan) {
      const track = (f: Fix) => { lastSim.current = f; onFix(f); };
      // 속도는 구간에서 읽는다. simSpeed 는 **재생 배속**이다.
      if (posMode === "gpsSim") {
        // ★ GPS 흉내 — 1Hz · σ5m · 40초마다 8초 음영. 마커는 추정기가 낸 자리다
        const src = createReplaySource(plan, { rate: simSpeed }, onEnd);
        if (simAt.current.plan === plan) src.seek(simAt.current.along);
        srcRef.current = src;
        const stop = src.start(track);
        return () => { simAt.current = { plan, along: src.truthM }; srcRef.current = null; stop(); };
      }
      const src = createSimulationSource(plan, simSpeed, onEnd);
      if (simAt.current.plan === plan) src.seek(simAt.current.along);
      srcRef.current = src;
      const stop = src.start(track);
      return () => { simAt.current = { plan, along: src.alongM }; srcRef.current = null; stop(); };
    }
    // ★ 실제 GPS 가 없는 기기(데스크톱 · 거부)에서 「위치 없음 (User denied…)」 이 주행
    //   화면을 덮었다. 무엇을 하면 되는지를 말한다.
    //
    // ★ 2026-09-27 (§275). **잡히는데 엉뚱한 데서 잡히는 경우**가 구멍이었다.
    //   서울에서 열면 GPS 가 정상으로 서울 좌표를 준다 — 에러가 아니므로 위
    //   안내가 안 뜨고, 경로는 동명동인데 현위치는 200km 밖이다. 맵매칭이
    //   조용히 실패한다. 범위 밖 측위는 **쓰지 않고 말한다** — 시연은 사람이 켠다(`domain/demo.ts`).
    if (demo) return;              // ★ 시연은 GPS 와 무관한 축이다 — 멈춰 있어도(simSpeed 0) 실제 GPS 로 안 돌아간다
    // ★ 측위 상태를 여기서 `idle` 로 안 되돌린다 — 재탐색이 `plan` 을 바꿔 이 효과가 다시 돌 때 **실주행 중에 시연 단추가 깜빡 뜬다.** 되돌리는 곳은 처음부터(`reset`) 하나다.
    const guard = (f: Fix) => {
      const p: LngLat = [f.lon, f.lat];
      if (outsideServiceArea(p, area)) {
        // ★ **구역 밖 측위는 하나도 안 쓴다**(종전에는 첫 하나만 막고 이후는 통과 → 카메라가 서울로 갔다). 말은 한 번만 한다.
        onGpsState("outside");
        if (!saidOut.current) { saidOut.current = true; onNotice(outsideNotice(metresOutside(p, area))); }
        return;
      }
      onGpsState("live");
      onFix(f);
    };
    return createGpsSource().start(guard, (m) => {
      if (m.startsWith("위치 없음")) { onGpsState("none"); onNotice(noGpsNotice()); } else onNotice(m);
    });
  }, [phase, simSpeed, plan, onFix, posMode, demo]); // eslint-disable-line react-hooks/exhaustive-deps

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

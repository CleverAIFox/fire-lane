/**
 * app/useDeadReckoning.ts — 측위 사이를 **60fps 로 메운다**.
 *
 * ── 왜 갈랐나 (PLAN §1 #129) ────────────────────────────────────
 * ★ 2026-09-25. `useNavigation` 이 570줄로 넷을 들었다. 이것은 그 중 **React 가 모르는
 *   일**이다 — 상태를 하나도 안 만들고 매 프레임 ref 만 고친다. 상태 기계와 같은 파일에
 *   있으면 「왜 여기서는 setState 를 안 하나」 를 매번 다시 설명해야 한다.
 *
 * ── 세 속도 중 가장 빠른 것 ─────────────────────────────────────
 *   위치  60fps      `live` (ref). 카메라만 읽는다. React 가 모른다  ← 여기
 *   스냅  5Hz        2.2ms 브루트포스라 매 프레임은 낭비다
 *   UI    구간 변경   setState
 *
 * ★ **드문 측위에서만** 앞으로 민다(GPS · 흉내는 1Hz). 60fps 위치원은 이미 프레임마다
 *   오므로 예측을 겹치면 두 번 움직인다.
 * ★ 경로 위에 있을 때만 민다. 이탈 중에는 예측할 선형이 없다 — 그때 마커는 GPS 그대로다.
 * ★ 1.5초 넘게 앞서 가지 않는다(`predictS`). 음영이 길어지면 차가 혼자 달려간다.
 *
 * IN    단계 · 경로 선형 · 추정 상태(ref) · 드문 측위인가(ref) · 경로 위인가(ref) · live(ref)
 * OUT   (없음 — `live.current` 를 고친다)
 * 밖    추정하지 않는다. 예측식은 `domain/progress::predictS` 에 있다.
 */
import { useEffect } from "react";
import { pointAtM, predictS, type ProgressState, type RouteGeom } from "../domain/progress";
import type { LiveFix, Phase } from "../domain/types";

export function useDeadReckoning(a: {
  phase: Phase;
  geom: RouteGeom | null;
  prog: { current: ProgressState | null };
  sparse: { current: boolean };
  onRoute: { current: boolean };
  live: { current: LiveFix };
}): void {
  const { phase, geom, prog, sparse, onRoute, live } = a;
  useEffect(() => {
    if (phase !== "guiding" || !geom) return;
    let raf = 0;
    const tick = () => {
      const st = prog.current;
      if (st && sparse.current && onRoute.current) {
        const q = pointAtM(geom, predictS(st, performance.now(), geom.totalM));
        live.current = { lon: q.point[0], lat: q.point[1], brg: q.bearing, on: true };
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [phase, geom]); // eslint-disable-line react-hooks/exhaustive-deps
}

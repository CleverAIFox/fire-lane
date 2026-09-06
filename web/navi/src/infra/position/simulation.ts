/**
 * infra/position/simulation.ts — 경로를 따라 걷는다.
 *
 * ── 개발 편의가 아니다 ──────────────────────────────────────────
 * 발표에서 실제로 차를 몰 수 없다. 경로를 따라 움직이는 점이 있어야
 * 재탐색도 음성도 보여줄 수 있다.
 *
 * ★ **진짜 스냅 경로를 그대로 태운다.** GPS 와 같은 `Fix` 를 내므로
 *   실주행과 같은 코드를 지난다. 별도 경로를 파면 시뮬만 되고 실주행은
 *   안 되는 상태를 못 알아챈다.
 *
 * ── ★ 속도를 구간에서 읽는다 ────────────────────────────────────
 * 2026-09-06. 29/72/144km/h 버튼으로 골랐다가 뺐다. **큰길과 골목을
 * 같은 속도로 달리는 차는 없다.** `domain/speed.ts` 가 폭에서 속도를
 * 내고, 시뮬레이션은 지금 밟고 있는 구간의 속도로 달린다.
 *
 *     간선 12m+   50km/h        골목 4m 미만  20km/h
 *
 * 배속은 남긴다 — 시연에서 2분짜리 경로를 다 볼 수 없다. 다만 그것은
 * **재생 배속**이지 주행 속도가 아니다. 안내 문턱은 실제 속도를 본다.
 *
 * ★ dt 를 0.1초로 자른다. 탭이 백그라운드에 갔다 오면 dt 가 커져서
 *   차가 순간이동한다.
 */
import { cumulative, pointAlong, type LngLat } from "../../domain/geo";
import { speedOf } from "../../domain/speed";
import type { RoutePlan } from "../../domain/types";
import type { PositionSource } from "./types";

export interface SimulationHandle extends PositionSource {
  /** 진행 거리(m) */
  readonly alongM: number;
  readonly totalM: number;
  /** 재생 배속. 1이면 실시간 */
  setRate(x: number): void;
  seek(m: number): void;
}

export function createSimulationSource(
  plan: RoutePlan, rate = 1, onEnd?: () => void,
): SimulationHandle {
  const coords: LngLat[] = plan.coords;
  const cum = cumulative(coords);
  const total = cum[cum.length - 1];

  // 경로상 위치 → 그 지점 구간의 속도. 미리 구간 경계를 만들어 둔다.
  const bounds: { end: number; mps: number }[] = [];
  {
    let acc = 0;
    for (const e of plan.edges) {
      acc += e.length_m ?? 0;
      bounds.push({ end: acc, mps: speedOf(e) });
    }
  }
  const mpsAt = (m: number) => {
    for (const b of bounds) if (m <= b.end) return b.mps;
    return bounds.length ? bounds[bounds.length - 1].mps : 8;
  };

  let along = 0;
  let mul = rate;

  return {
    kind: "simulation",
    get alongM() { return along; },
    get totalM() { return total; },
    setRate(x) { mul = Math.max(0, x); },
    seek(m) { along = Math.max(0, Math.min(total, m)); },

    start(onFix) {
      if (coords.length < 2) return () => {};
      let raf = 0;
      let last = performance.now();
      const tick = (t: number) => {
        const dt = Math.min(0.1, (t - last) / 1000);
        last = t;
        along = Math.min(total, along + mpsAt(along) * mul * dt);
        const { point, heading } = pointAlong(coords, cum, along);
        onFix({ lon: point[0], lat: point[1], heading, source: "simulation" });
        if (along >= total) { onEnd?.(); return; }
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    },
  };
}

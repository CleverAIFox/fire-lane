/**
 * infra/position/replay.ts — **GPS 흉내.** 경로를 달리는 가상의 차를 1Hz GPS 로 본다.
 *
 * ══ 왜 생겼나 (2026-09-22 · DECISIONS §213-3) ═══════════════════
 * `simulation.ts` 는 60fps 로 **경로 위의 정확한 점**을 낸다. 그러면 위치 추정이
 * 틀려도 화면이 맞아 보인다 — 입력이 이미 정답이기 때문이다. 턴바이턴이
 * 「차가 이렇게 갈 거다」 를 가정만 하는 것처럼 보인 이유가 이것이다.
 *
 * 실제 GPS 는 이렇다 —
 *
 *     1초에 한 번           측위 사이는 추정이 메운다
 *     수 m 잡음             σ ≈ 5m (도심 차량 단말 통상치. 우리가 잰 값이 아니다)
 *     저속 방향 없음        2m/s 미만이면 heading 이 null
 *     음영                  고가 · 빌딩 숲에서 수 초 끊긴다 → 다시 잡히면 **순간이동**
 *
 * 이 넷을 그대로 낸다. 받는 쪽은 `gps.ts` 와 같은 `Fix` 를 받으므로 **실주행과
 * 같은 코드를 지난다.**
 *
 * ★ 차는 보이지 않는다. 화면의 마커는 추정기가 낸 자리다 — 가상의 차가 어디
 *   있는지 그리면 다시 정답을 보여주는 것이다. 참값은 `truthM` 으로만 꺼낸다(시험용).
 *
 * ★ 잡음은 시드 난수다. 같은 시드면 같은 주행이 나와 시험이 흔들리지 않는다.
 */
import { cumulative, pointAlong, MX, MY, type LngLat } from "../../domain/geo";
import { speedOf } from "../../domain/speed";
import type { Fix, RoutePlan } from "../../domain/types";
import type { PositionSource } from "./types";

export interface ReplayOpts {
  /** 재생 배속. 1 이면 실시간 */
  rate?: number;
  /** 측위 잡음 표준편차(m) */
  sigmaM?: number;
  /** 측위 간격(초, 주행 시간 기준) */
  everySec?: number;
  /** 음영이 이만큼(주행 초)마다 한 번 온다. 0 이면 없다 */
  shadowEverySec?: number;
  /** 음영 길이(주행 초) */
  shadowSec?: number;
  seed?: number;
}

export interface ReplayHandle extends PositionSource {
  /** 가상의 차가 실제로 있는 곳(m, 선형). **시험 전용** — 화면에 그리지 않는다 */
  readonly truthM: number;
  readonly totalM: number;
  setRate(x: number): void;
  seek(m: number): void;
  /** 지금부터 이만큼 GPS 없이 달린다(주행 초). 다음 측위가 순간이동이 된다 */
  shadow(sec: number): void;
  /**
   * 한 걸음 진행시키고 측위가 나오면 돌려준다. `start` 가 rAF 로 부르는 것과 같다.
   * ★ 시험이 브라우저 없이 이것을 직접 부른다.
   */
  step(dtSec: number, nowMs: number): Fix | null;
}

/** 시드 난수 (mulberry32) */
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function createReplaySource(
  plan: RoutePlan, o: ReplayOpts = {}, onEnd?: () => void,
): ReplayHandle {
  const coords: LngLat[] = plan.coords;
  const cum = cumulative(coords);
  const total = cum[cum.length - 1];
  const sigma = o.sigmaM ?? 5;
  const every = o.everySec ?? 1;
  const shadowEvery = o.shadowEverySec ?? 40;
  const shadowLen = o.shadowSec ?? 8;
  const rnd = rng(o.seed ?? 7);
  const gauss = () => {
    const u = Math.max(1e-9, rnd());
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rnd());
  };

  // 선형 위치 → 그 지점 구간 속도(엣지 length_m 합은 선형과 약간 다르다 — 속도만 빌린다)
  const bounds: { end: number; mps: number }[] = [];
  {
    let acc = 0;
    const scale = total / Math.max(1, plan.lengthM);
    for (const e of plan.edges) {
      acc += (e.length_m ?? 0) * scale;
      bounds.push({ end: acc, mps: speedOf(e) });
    }
  }
  const mpsAt = (m: number) => {
    for (const b of bounds) if (m <= b.end) return b.mps;
    return bounds.length ? bounds[bounds.length - 1].mps : 8;
  };

  let along = 0;
  let mul = o.rate ?? 1;
  let driveT = 0;           // 주행 시간(초)
  let nextFixAt = 0;        // 다음 측위 주행 시각
  let shadowUntil = -1;
  let nextShadowAt = shadowEvery > 0 ? shadowEvery : Infinity;

  const h: ReplayHandle = {
    kind: "replay",
    get truthM() { return along; },
    get totalM() { return total; },
    setRate(x) { mul = Math.max(0, x); },
    seek(m) { along = Math.max(0, Math.min(total, m)); },
    shadow(sec) { shadowUntil = driveT + sec; },

    step(dtSec, nowMs) {
      const dt = dtSec * mul;
      driveT += dt;
      along = Math.min(total, along + mpsAt(along) * dt);
      if (driveT >= nextShadowAt) { shadowUntil = driveT + shadowLen; nextShadowAt += shadowEvery; }
      if (driveT < nextFixAt) return null;
      nextFixAt = driveT + every;
      if (driveT < shadowUntil) return null;     // 음영 — 측위 없음
      const { point, heading } = pointAlong(coords, cum, along);
      const ex = gauss() * sigma;
      const ey = gauss() * sigma;
      const v = mpsAt(along);
      return {
        lon: point[0] + ex / MX,
        lat: point[1] + ey / MY,
        heading: v >= 2 ? (heading + gauss() * 8 + 360) % 360 : null,
        source: "replay",
        t: nowMs,
      };
    },

    start(onFix) {
      if (coords.length < 2) return () => {};
      let raf = 0;
      let last = performance.now();
      const tick = (t: number) => {
        const dt = Math.min(0.1, (t - last) / 1000);
        last = t;
        const f = h.step(dt, t);
        if (f) onFix(f);
        if (along >= total) { onEnd?.(); return; }
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    },
  };
  return h;
}

/**
 * simulation.test.ts — 경로를 따라 걷는 점. **개발 편의가 아니다.** (DECISIONS §483)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 센 마지막 다섯 중 하나다. 발표에서 실제로 차를 몰
 * 수 없으므로 이 자가 **재탐색도 음성도 보여주는 유일한 길**인데, 미는
 * 시험이 없었다. 시연 날 안 돌면 보여줄 것이 없다.
 *
 * ★ 머리말이 적은 두 규율을 문다 —
 *     ① **진짜 스냅 경로를 그대로 태운다** — 속도를 구간에서 읽는다
 *        (`domain/speed.ts`). 별도 경로를 파면 시뮬만 되고 실주행은 안 된다
 *     ② **dt 를 0.1초로 자른다** — 탭이 백그라운드에 갔다 오면 dt 가 커져
 *        차가 **순간이동한다.** 그 자름이 사라지면 시연 중에 점이 날아간다
 *
 * ★ `requestAnimationFrame` 을 가짜로 세운다. 진짜 프레임을 기다리면 시험이
 *   시각에 매이고, 매인 시험은 이따금 빨개진다(`opsLink.test.ts` 와 같은 사유).
 *
 * 밖    **화면을 안 본다** — 점을 그리는 것은 `NaviMap` 소관이다.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { cumulative, LAT0, LON0, MY, type LngLat } from "../src/domain/geo";
import { speedOf } from "../src/domain/speed";
import { createSimulationSource } from "../src/infra/position/simulation";
import type { GraphEdge, RoutePlan } from "../src/domain/types";

const DLAT = 1 / MY;

/** 북으로 100m(폭 12m · 50km/h) 뒤 100m(폭 3m · 20km/h). */
function plan(): RoutePlan {
  const coords: LngLat[] = [
    [LON0, LAT0], [LON0, LAT0 + 100 * DLAT], [LON0, LAT0 + 200 * DLAT],
  ];
  const mk = (w: number): GraphEdge => ({
    seg_uid: `w${w}`, verdict: "clear", width_min_m: w, length_m: 100,
    a: 0, b: 1, coords: [],
  } as GraphEdge);
  return { coords, edges: [mk(12), mk(3)] } as unknown as RoutePlan;
}

/**
 * 가짜 프레임. `step(ms)` 로 시험이 손으로 시각을 민다.
 *
 * ★ 콜백을 **쌓아 두고** 부른다 — `tick` 이 다음 프레임을 예약하므로
 *   곧바로 부르면 재귀로 끝없이 돈다.
 */
function frames() {
  let now = 0;
  let next: ((t: number) => void) | null = null;
  const cancelled: number[] = [];
  vi.stubGlobal("performance", { now: () => now });
  vi.stubGlobal("requestAnimationFrame", (cb: (t: number) => void) => {
    next = cb;
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", (h: number) => cancelled.push(h));
  return {
    step(ms: number) {
      now += ms;
      const cb = next;
      next = null;
      cb?.(now);
    },
    get pending() { return next !== null; },
    cancelled,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("① 재지 않고도 아는 것", () => {
  it("전체 길이가 좌표열의 누적과 같다", () => {
    const p = plan();
    const cum = cumulative(p.coords);
    const sim = createSimulationSource(p);
    expect(sim.totalM).toBeCloseTo(cum[cum.length - 1], 6);
    expect(sim.alongM).toBe(0);
    expect(sim.kind).toBe("simulation");
  });

  it("★ 자리를 옮기면 **길 안으로 잘린다**", () => {
    const sim = createSimulationSource(plan());
    sim.seek(50);
    expect(sim.alongM).toBeCloseTo(50, 6);
    sim.seek(-900);
    expect(sim.alongM).toBe(0);
    sim.seek(99_999);
    expect(sim.alongM).toBeCloseTo(sim.totalM, 6);
  });

  it("★ 배속은 음수가 안 된다 — 뒤로 가는 시연은 없다", () => {
    const f = frames();
    const sim = createSimulationSource(plan());
    sim.setRate(-5);
    const stop = sim.start(() => {});
    f.step(1000);
    expect(sim.alongM).toBe(0);
    stop();
  });
});

describe("② 걷는다", () => {
  it("★ 구간 속도로 간다 — 별도 속도표를 두지 않는다", () => {
    const f = frames();
    const p = plan();
    const sim = createSimulationSource(p);
    const fixes: { lon: number; lat: number }[] = [];
    const stop = sim.start((fx) => fixes.push(fx));
    // 100ms 한 틱 — 첫 구간(50km/h = 13.89m/s)에서 1.389m
    f.step(100);
    expect(fixes).toHaveLength(1);
    expect(sim.alongM).toBeCloseTo(speedOf(p.edges[0]) * 0.1, 6);
    stop();
  });

  it("★ **dt 를 0.1초로 자른다** — 탭이 돌아왔을 때 점이 날아가지 않는다", () => {
    const f = frames();
    const p = plan();
    const sim = createSimulationSource(p);
    const stop = sim.start(() => {});
    // 10초를 한 틱에 준다(백그라운드에서 돌아온 꼴)
    f.step(10_000);
    const cap = speedOf(p.edges[0]) * 0.1;
    expect(sim.alongM).toBeCloseTo(cap, 6);
    // 자름이 없으면 139m 를 날아가 **구간 하나를 통째로 건너뛴다**
    expect(sim.alongM).toBeLessThan(5);
    stop();
  });

  it("두 번째 구간에 들면 **느려진다**", () => {
    const f = frames();
    const p = plan();
    const sim = createSimulationSource(p);
    sim.seek(150);
    const stop = sim.start(() => {});
    f.step(100);
    expect(sim.alongM - 150).toBeCloseTo(speedOf(p.edges[1]) * 0.1, 6);
    expect(speedOf(p.edges[1])).toBeLessThan(speedOf(p.edges[0]));
    stop();
  });

  it("★ 끝에 닿으면 **멈추고 알린다** — 프레임을 더 예약하지 않는다", () => {
    const f = frames();
    let ended = 0;
    const sim = createSimulationSource(plan(), 1, () => ended++);
    sim.seek(sim.totalM - 0.5);
    const stop = sim.start(() => {});
    f.step(100);
    expect(sim.alongM).toBeCloseTo(sim.totalM, 6);
    expect(ended).toBe(1);
    expect(f.pending).toBe(false);
    stop();
  });

  it("★ 좌표가 둘 미만이면 **아무것도 안 한다** — 빈 경로에서 죽지 않는다", () => {
    frames();
    const one = { coords: [[LON0, LAT0]], edges: [] } as unknown as RoutePlan;
    const sim = createSimulationSource(one);
    let n = 0;
    const stop = sim.start(() => n++);
    expect(n).toBe(0);
    expect(() => stop()).not.toThrow();
  });

  it("멈추면 예약을 **거둔다**", () => {
    const f = frames();
    const sim = createSimulationSource(plan());
    const stop = sim.start(() => {});
    f.step(100);
    stop();
    expect(f.cancelled.length).toBe(1);
  });
});

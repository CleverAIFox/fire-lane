/**
 * gps.test.ts — 위치가 **어느 시계로** 들어오는가.  (PLAN W13-5 · DECISIONS §328)
 *
 * ── 왜 이 파일이 생겼나 (2026-09-30) ────────────────────────────
 * `infra/position/gps.ts` 는 60줄이고 **시험이 하나도 없었다.** 그 60줄 안에
 * 이 앱에서 제일 조용한 결함 자리가 있다 —
 *
 *     `GeolocationPosition.timestamp` 는 **에포크 ms** 다.
 *     `Fix.t` 를 읽는 쪽은 `performance.now()` 시계로 읽는다.
 *
 * 그대로 넣으면 첫 `dt` 가 **수십억 ms** 가 되고 순간속도가 0 으로 죽는다.
 * 화면은 멀쩡히 뜨고 차만 안 움직인다 — 출동 중에 그것이 무슨 뜻인지는
 * 운전자가 알 수 없다. 코드는 이미 옳게 짜여 있었고 **그것을 붙드는 것이 없었다.**
 *
 * ★ 잠그는 것은 **정책**이다. 진짜 GPS 는 안 쓴다 — `navigator.geolocation` 을
 *   가짜로 세우고 「무엇을 어떤 값으로 넘겼는가」만 본다. 데스크톱에도 WSL 에도
 *   GPS 가 없고, 있어도 시험이 창밖 하늘에 기대면 안 된다.
 *
 * ★ 밖 — **정확도가 좋은가는 안 본다.** 그것은 기기가 정하는 값이고, 여기가
 *   드는 것은 「못 믿을 값을 `null` 로 넘기는가」다. 회색(모름)은 0 이 아니다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createGpsSource } from "../src/infra/position/gps";
import type { Fix } from "../src/domain/types";

/** 가짜 측위기. 넘긴 콜백을 쥐고 있다가 시험이 부른다. */
function fakeGeo() {
  let onOk: ((p: unknown) => void) | null = null;
  let onErr: ((e: { message: string }) => void) | null = null;
  const cleared: number[] = [];
  const opts: unknown[] = [];
  const geo = {
    watchPosition(ok: (p: unknown) => void, err: (e: { message: string }) => void, o: unknown) {
      onOk = ok; onErr = err; opts.push(o);
      return 7;
    },
    clearWatch(id: number) { cleared.push(id); },
  };
  return {
    geo, cleared, opts,
    /** 측위 하나를 흘려 넣는다. `timestamp` 는 **에포크 ms** 다 — 실물과 같게. */
    emit(coords: Record<string, unknown>, timestamp: number) {
      onOk?.({ coords, timestamp });
    },
    fail(message: string) { onErr?.({ message }); },
  };
}

let G: ReturnType<typeof fakeGeo>;
let fixes: Fix[];

/** 에포크 기준. `timeOrigin` 이 이 값이면 에포크 t 는 `t - ORIGIN` 이 된다. */
const ORIGIN = 1_700_000_000_000;

beforeEach(() => {
  G = fakeGeo();
  fixes = [];
  vi.stubGlobal("navigator", { geolocation: G.geo });
  vi.stubGlobal("performance", { timeOrigin: ORIGIN, now: () => 10_000 });
});

const start = () => createGpsSource().start((f) => { fixes.push(f); }, undefined);

const GOOD = { longitude: 126.9, latitude: 35.15, heading: 90, accuracy: 8 };

describe("시계", () => {
  it("에포크를 performance 시계로 옮긴다", () => {
    start();
    G.emit(GOOD, ORIGIN + 5_000);
    expect(fixes).toHaveLength(1);
    // ★ **에포크를 그대로 넘기면 여기가 1.7e12 다.** 그것이 이 파일의 이유다.
    expect(fixes[0].t).toBe(5_000);
  });

  it("미래 측위는 안 쓴다 — 받는 쪽이 채운다", () => {
    start();
    G.emit(GOOD, ORIGIN + 10_000 + 5_000);   // now()+1000 보다 뒤다
    expect(fixes[0].t).toBeUndefined();
  });

  it("과거로 어긋난 시계도 안 쓴다", () => {
    start();
    G.emit(GOOD, ORIGIN - 1);                // 음수가 된다
    expect(fixes[0].t).toBeUndefined();
  });

  it("시각이 숫자가 아니면 안 쓴다", () => {
    start();
    G.emit(GOOD, Number.NaN);
    expect(fixes[0].t).toBeUndefined();
    // ★ 그래도 **좌표는 넘어간다.** 시각 하나 때문에 측위를 버리면 안 된다.
    expect(fixes[0].lon).toBe(126.9);
  });

  it("timeOrigin 을 못 읽는 기계에서도 죽지 않는다", () => {
    vi.stubGlobal("performance", { timeOrigin: Number.NaN, now: () => 10_000 });
    start();
    G.emit(GOOD, ORIGIN + 5_000);
    expect(fixes[0].t).toBeUndefined();
  });
});

describe("모르는 값은 null 이다", () => {
  it("저속에서 방위가 없으면 null — 0 이 아니다", () => {
    start();
    G.emit({ ...GOOD, heading: null }, ORIGIN + 1);
    // ★ 0 으로 채우면 **정북을 보고 있다**는 뜻이 된다. 회색은 NULL 이다.
    expect(fixes[0].heading).toBeNull();
  });

  it("정확도가 없으면 null — 신호 품질 화면의 근거가 사라지는 것이 맞다", () => {
    start();
    G.emit({ ...GOOD, accuracy: undefined }, ORIGIN + 1);
    expect(fixes[0].accuracy).toBeNull();
  });

  it("방위 0 은 값이다 — null 로 뭉개지 않는다", () => {
    start();
    G.emit({ ...GOOD, heading: 0 }, ORIGIN + 1);
    expect(fixes[0].heading).toBe(0);
  });
});

describe("없어도 앱이 돈다", () => {
  it("위치 기능이 없는 브라우저에서 던지지 않고 사유를 넘긴다", () => {
    vi.stubGlobal("navigator", {});
    const errs: string[] = [];
    const stop = createGpsSource().start(() => {}, (m) => errs.push(m));
    expect(errs).toHaveLength(1);
    // ★ **해지 함수는 그래도 나온다.** 없으면 부르는 쪽이 터진다.
    expect(() => stop()).not.toThrow();
  });

  it("측위 실패는 사유와 함께 올라간다", () => {
    const errs: string[] = [];
    createGpsSource().start(() => {}, (m) => errs.push(m));
    G.fail("User denied Geolocation");
    expect(errs[0]).toContain("User denied Geolocation");
  });

  it("해지하면 그 watch 를 끈다", () => {
    const stop = start();
    stop();
    expect(G.cleared).toEqual([7]);
  });

  it("묵은 캐시를 받을 수 있게 열어 두고, 그래서 시각을 같이 받는다", () => {
    start();
    const o = G.opts[0] as { maximumAge: number; enableHighAccuracy: boolean };
    // ★ 이 둘은 한 쌍이다. `maximumAge` 가 0 이 아니면 **받은 시각으로 덮으면 안 된다** —
    //   그 결합이 깨지면 위 「시계」 묶음이 지키는 것이 무의미해진다.
    expect(o.maximumAge).toBeGreaterThan(0);
    expect(o.enableHighAccuracy).toBe(true);
  });
});

/**
 * edgeSnap.test.ts — 자른 사본과 원본 사이를 **오가는** 둘. (DECISIONS §483)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 `domain/edgeSnap.ts` 의 둘을 「시험이 이름으로도 안
 * 부른다」로 셌다 — `geomLen` · `fullProgress`.
 *
 * ★ `fullProgress` 가 요점이다. 출발·도착 구간은 투영점에서 **잘린 사본**이고
 *   (§218-3), 스냅의 `progress` 는 **원본 형상** 기준이다. 둘을 오가는 자가
 *   이 함수 하나다 — 틀리면 「구간의 몇 %를 지났나」가 어긋나고, 그 수로
 *   회전 안내와 남은 거리가 선다.
 *
 * 밖    **투영이 옳은가는 안 본다** — `snapToEdge` 는 `snap.test.ts` ·
 *       `pointRoute.test.ts` 가 든다.
 */
import { describe, expect, it } from "vitest";

import { fullProgress, geomLen, NODE_EPS_M } from "../src/domain/edgeSnap";
import { cumulative, LAT0, LON0, MX, MY, type LngLat } from "../src/domain/geo";
import type { GraphEdge } from "../src/domain/types";

const DLAT = 1 / MY;
const DLON = 1 / MX;

describe("① 형상 길이", () => {
  it("꺾인 선의 길이를 더한다", () => {
    const line: LngLat[] = [
      [LON0, LAT0], [LON0, LAT0 + 30 * DLAT], [LON0 + 40 * DLON, LAT0 + 30 * DLAT],
    ];
    expect(geomLen(line)).toBeCloseTo(70, 6);
  });

  it("★ `geo.cumulative` 의 마지막 값과 같다 — 길이를 두 벌로 세지 않는다", () => {
    const line: LngLat[] = [
      [LON0, LAT0], [LON0 + 11 * DLON, LAT0 + 7 * DLAT], [LON0 + 3 * DLON, LAT0 + 19 * DLAT],
    ];
    const cum = cumulative(line);
    expect(geomLen(line)).toBeCloseTo(cum[cum.length - 1], 9);
  });

  it("점 하나 · 빈 것은 0 이다 — 던지지 않는다", () => {
    expect(geomLen([[LON0, LAT0]])).toBe(0);
    expect(geomLen([])).toBe(0);
  });

  it("같은 점이 겹친 형상도 0 이다", () => {
    expect(geomLen([[LON0, LAT0], [LON0, LAT0]])).toBe(0);
  });

  it("노드 붙임 문턱이 **길이보다 작다** — 안 그러면 모든 구간이 한 점이다", () => {
    expect(NODE_EPS_M).toBeGreaterThan(0);
    expect(NODE_EPS_M).toBeLessThan(1);
  });
});

describe("② 자른 사본 ↔ 원본 비율", () => {
  const whole = { seg_uid: "W" } as GraphEdge;
  const clipped = { seg_uid: "C", clip: { src: 7, t0: 0.2, t1: 0.6 } } as GraphEdge;

  it("자르지 않은 구간은 **그대로**다", () => {
    for (const f of [0, 0.25, 0.5, 1]) expect(fullProgress(whole, f)).toBe(f);
  });

  it("자른 사본의 양 끝이 원본의 `t0` · `t1` 이다", () => {
    expect(fullProgress(clipped, 0)).toBeCloseTo(0.2, 9);
    expect(fullProgress(clipped, 1)).toBeCloseTo(0.6, 9);
  });

  it("★ 가운데가 비례로 간다 — 선형이 아니면 남은 거리가 튄다", () => {
    expect(fullProgress(clipped, 0.5)).toBeCloseTo(0.4, 9);
    expect(fullProgress(clipped, 0.25)).toBeCloseTo(0.3, 9);
  });

  it("★ 단조증가다", () => {
    let prev = -1;
    for (let f = 0; f <= 1.0001; f += 0.05) {
      const v = fullProgress(clipped, Math.min(1, f));
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });

  it("★ 뒤집힌 자름(`t0` > `t1`)도 양 끝을 지킨다 — 거꾸로 지나는 경로가 있다", () => {
    const back = { seg_uid: "B", clip: { src: 7, t0: 0.9, t1: 0.3 } } as GraphEdge;
    expect(fullProgress(back, 0)).toBeCloseTo(0.9, 9);
    expect(fullProgress(back, 1)).toBeCloseTo(0.3, 9);
    expect(fullProgress(back, 0.5)).toBeCloseTo(0.6, 9);
  });
});

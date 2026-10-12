/**
 * context.test.ts — 주변 사정이 **경로 위 어디에** 있는가. (DECISIONS §483)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 `domain/context.ts` 의 둘을 「시험이 이름으로도 안
 * 부른다」로 셌다 — `nearestOnPath` · `nextHazard`.
 *
 * ★ `nearestOnPath` 는 §473 이 **상수를 고친 자리**다. 여기 `ky` 를 110,540
 *   으로 들고 있었고(정본 110,943), 그 한 벌이 네 벌 중 하나였다. 고친 뒤로
 *   그 함수를 미는 자가 없었다 — 고친 것이 맞는지 아무도 안 물었다.
 *
 * ★ `nextHazard` 는 **다음 하나**만 본다. 창 밖이면 `null` 이고 **더 뒤를
 *   안 찾는다** — 그 꼴이 의도인지 결함인지가 읽는 사람에게 안 보였다.
 *   의도다(「다음」을 말하는 자리이고, 창 밖의 사정은 아직 말할 때가 아니다).
 *   시험으로 적어 둔다.
 *
 * 밖    **어떤 사정을 말할 것인가는 안 본다** — 문구와 묶음은
 *       `hazardPhrase` · `hazardSummary` 소관이고 `voice.test.ts` 가 든다.
 */
import { describe, expect, it } from "vitest";

import { nearestOnPath, nextHazard, type Hazard } from "../src/domain/context";
import { cumulative, distM, LAT0, LON0, MX, MY, type LngLat } from "../src/domain/geo";

const DLAT = 1 / MY;
const DLON = 1 / MX;

/** 남으로 100m 뒤 동으로 100m 꺾이는 길. */
const LINE: LngLat[] = [
  [LON0, LAT0],
  [LON0, LAT0 + 100 * DLAT],
  [LON0 + 100 * DLON, LAT0 + 100 * DLAT],
];
const CUM = cumulative(LINE);

describe("① 경로 위 가장 가까운 점", () => {
  it("길 위의 점은 거리가 0 이고 자리가 그 자리다", () => {
    const got = nearestOnPath(LINE, CUM, [LON0, LAT0 + 40 * DLAT]);
    expect(got.d).toBeCloseTo(0, 6);
    expect(got.s).toBeCloseTo(40, 6);
  });

  it("옆으로 비낀 점은 **수선 거리**와 그 발의 자리를 낸다", () => {
    const got = nearestOnPath(LINE, CUM, [LON0 + 7 * DLON, LAT0 + 40 * DLAT]);
    expect(got.d).toBeCloseTo(7, 6);
    expect(got.s).toBeCloseTo(40, 6);
  });

  it("★ 꺾인 뒤의 구간도 본다 — 첫 구간만 보면 모서리에 다 붙는다", () => {
    const got = nearestOnPath(LINE, CUM, [LON0 + 60 * DLON, LAT0 + 105 * DLAT]);
    expect(got.d).toBeCloseTo(5, 6);
    expect(got.s).toBeCloseTo(160, 6);
  });

  it("길 앞/뒤로 벗어난 점은 **끝으로 잘린다**", () => {
    const before = nearestOnPath(LINE, CUM, [LON0, LAT0 - 30 * DLAT]);
    expect(before.s).toBeCloseTo(0, 6);
    expect(before.d).toBeCloseTo(30, 6);
    const after = nearestOnPath(LINE, CUM, [LON0 + 130 * DLON, LAT0 + 100 * DLAT]);
    expect(after.s).toBeCloseTo(200, 6);
    expect(after.d).toBeCloseTo(30, 6);
  });

  it("★ 길이 0 인 구간에 0 으로 나누지 않는다", () => {
    const dup: LngLat[] = [[LON0, LAT0], [LON0, LAT0]];
    const got = nearestOnPath(dup, [0, 0], [LON0 + 5 * DLON, LAT0]);
    expect(Number.isFinite(got.d)).toBe(true);
    expect(got.d).toBeCloseTo(5, 6);
  });

  it("★ 쟀다 — 수선 거리가 `distM` 과 같은 자다(§473 이 고친 그 상수)", () => {
    // 상수가 한 벌이면 두 함수가 같은 수를 낸다. 갈리면 여기가 운다.
    const p: LngLat = [LON0 + 13 * DLON, LAT0 + 50 * DLAT];
    const foot: LngLat = [LON0, LAT0 + 50 * DLAT];
    expect(nearestOnPath(LINE, CUM, p).d).toBeCloseTo(distM(p, foot), 6);
  });
});

describe("② 다음 사정", () => {
  const HS: Hazard[] = [
    { kind: "speedbump", atM: 50, at: LINE[0], text: "과속방지턱" },
    { kind: "speedcam", atM: 120, at: LINE[0], text: "단속카메라" },
    { kind: "child_zone", atM: 400, at: LINE[0], text: "어린이보호구역" },
  ];

  it("창 안의 첫 사정을 낸다", () => {
    expect(nextHazard(HS, 0, 100)?.atM).toBe(50);
    expect(nextHazard(HS, 60, 100)?.atM).toBe(120);
  });

  it("지난 것은 안 센다", () => {
    expect(nextHazard(HS, 130, 500)?.atM).toBe(400);
  });

  it("★ 창 밖이면 `null` 이고 **더 뒤를 안 찾는다** — 「다음」을 말하는 자리다", () => {
    expect(nextHazard(HS, 0, 10)).toBeNull();
    // 50 은 창 밖이고 120 은 더 밖이다. 「아무것도 없다」가 옳다
    expect(nextHazard(HS, 0, 40)).toBeNull();
  });

  it("빈 목록은 `null` 이다", () => {
    expect(nextHazard([], 0, 1000)).toBeNull();
  });

  it("경로를 다 지났으면 `null` 이다", () => {
    expect(nextHazard(HS, 999, 1000)).toBeNull();
  });
});

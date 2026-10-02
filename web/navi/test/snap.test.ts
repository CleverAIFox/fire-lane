/**
 * snap.test.ts — GPS 좌표를 구간에 붙이는 **네 신호.** (DECISIONS §156 · §119)
 *
 * ── 왜 이 파일이 생겼나 (2026-10-03 · DECISIONS §364) ────────────
 * `domain/snap.ts` 는 **내비의 나머지 전부가 그 위에 선다.** 그런데 전용 시험이
 * 없었다. §156 이 강제자로 `tests/test_contract.py` 를 들고 있었는데 그 파일은
 * `snap` 이라는 글자를 한 번도 안 쓴다 — **죽은 강제자 참조**였고, 문서 도장이
 * 그것을 꺼냈다(§363 과 같은 배치).
 *
 * ★ 적중률 70 → 79 → 91% 는 **재현 못 한다**(GPS σ=4m · n=300 실험). 여기서
 *   재는 것은 그 수가 아니라 **네 신호가 각각 답을 바꾸는가**다 — 하나가 죽어도
 *   나머지로 그럴듯한 답이 나오므로, 섞은 것은 **찢어서** 물어야 한다
 *   (`test_shardseal.py::test_each_cell_tears_the_seal` 과 같은 꼴).
 *
 * ★ 좌표는 동명동 근처의 **합성**이다. 실물 `segments.geojson` 을 읽으면 그
 *   파일이 바뀔 때마다 이 시험이 흔들리고, 흔들리는 시험은 꺼진다.
 */
import { describe, expect, it } from "vitest";

import {
  SNAP_KNOBS, createTracker, prepare, snap, type SnapSegment,
} from "../src/domain/snap";

/** 동명동 한가운데. 여기서 남북·동서로 두 길을 긋는다. */
const LON0 = 126.925;
const LAT0 = 35.151;
/** 위도 1도 ≈ 111km · 이 위도에서 경도 1도 ≈ 91km (localgeo 와 같은 근사) */
const DLAT = 1 / 111_000;
const DLON = 1 / 91_000;

function seg(uid: string, coords: [number, number][]): SnapSegment {
  return { seg_uid: uid, verdict: "clear", width_min_m: 5, coords } as SnapSegment;
}

/** 남북으로 뻗은 길(북행) 과 그 20m 동쪽의 평행한 길. */
const NS = seg("NS", [[LON0, LAT0 - 60 * DLAT], [LON0, LAT0 + 60 * DLAT]]);
const NS_EAST = seg("NS_EAST",
  [[LON0 + 20 * DLON, LAT0 - 60 * DLAT], [LON0 + 20 * DLON, LAT0 + 60 * DLAT]]);
/** 같은 자리를 **동서로** 지나는 길. 거리로는 비기고 방위각이 가른다. */
const EW = seg("EW", [[LON0 - 60 * DLON, LAT0], [LON0 + 60 * DLON, LAT0]]);

describe("① 거리 — 가장 가까운 길에 붙는다", () => {
  const P = prepare([NS, NS_EAST]);
  it("바로 위에 서면 그 길이다", () => {
    expect(snap(LON0, LAT0, P)?.seg_uid).toBe("NS");
  });
  it("동쪽으로 가면 동쪽 길로 넘어간다", () => {
    expect(snap(LON0 + 18 * DLON, LAT0, P)?.seg_uid).toBe("NS_EAST");
  });
  it("도로에서 멀면 **아무 데도 안 붙는다** — 억지로 붙이지 않는다", () => {
    const far = snap(LON0 + 400 * DLON, LAT0, P);
    expect(far === null || far.confident === false).toBe(true);
  });
});

describe("② 방위각 — 거리가 비기면 가는 쪽이 가른다", () => {
  const P = prepare([NS, EW]);
  const cross = { lon: LON0 + 0.4 * DLON, lat: LAT0 + 0.4 * DLAT };

  it("북으로 가면 남북 길이다", () => {
    expect(snap(cross.lon, cross.lat, P, { heading: 0 })?.seg_uid).toBe("NS");
  });
  it("동으로 가면 동서 길이다", () => {
    expect(snap(cross.lon, cross.lat, P, { heading: 90 })?.seg_uid).toBe("EW");
  });
  it("★ 신호를 끄면 **답이 갈린다** — 끄고도 같으면 이 신호는 안 듣는 것이다", () => {
    const off = { ...SNAP_KNOBS, bearingW: 0 };
    const n = snap(cross.lon, cross.lat, P, { heading: 0, knobs: off })?.seg_uid;
    const e = snap(cross.lon, cross.lat, P, { heading: 90, knobs: off })?.seg_uid;
    expect(n).toBe(e);
  });
  it("남으로 가도 남북 길이다 — **형상 방향이 아니라 진행방향**이다", () => {
    expect(snap(cross.lon, cross.lat, P, { heading: 180 })?.seg_uid).toBe("NS");
  });
});

describe("③ 직전 스냅 — 붙어 있던 길에 머무른다", () => {
  const P = prepare([NS, NS_EAST]);
  /** 두 길 사이 한가운데보다 **동쪽으로 살짝** — 거리만 보면 동쪽 길이다 */
  const mid = LON0 + 11 * DLON;

  it("직전이 없으면 가까운 쪽이다", () => {
    expect(snap(mid, LAT0, P)?.seg_uid).toBe("NS_EAST");
  });
  it("직전이 서쪽 길이면 **머무른다**", () => {
    expect(snap(mid, LAT0, P, { prevUid: "NS" })?.seg_uid).toBe("NS");
  });
  it("★ 그래도 충분히 멀어지면 **떨어진다** — 하드 제한이 아니다", () => {
    expect(snap(LON0 + 19 * DLON, LAT0, P, { prevUid: "NS" })?.seg_uid).toBe("NS_EAST");
  });
  it("신호를 끄면 머무르지 않는다", () => {
    const off = { ...SNAP_KNOBS, stickyM: 0 };
    expect(snap(mid, LAT0, P, { prevUid: "NS", knobs: off })?.seg_uid).toBe("NS_EAST");
  });
});

describe("④ 활성 경로 — 경로 위를 달리면 옆 골목에 안 붙는다 (§119)", () => {
  const P = prepare([NS, NS_EAST]);
  const mid = LON0 + 12 * DLON;

  it("경로를 모르면 가까운 쪽이다", () => {
    expect(snap(mid, LAT0, P)?.seg_uid).toBe("NS_EAST");
  });
  it("경로가 서쪽 길이면 거기 붙는다", () => {
    expect(snap(mid, LAT0, P, { onRoute: new Set(["NS"]) })?.seg_uid).toBe("NS");
  });
  it("★ **진짜로 벗어나면 할인을 이긴다** — 아니면 이탈을 영영 못 본다", () => {
    const off = snap(LON0 + 60 * DLON, LAT0, P, { onRoute: new Set(["NS"]) });
    expect(off?.seg_uid).not.toBe("NS");
  });
  it("신호를 끄면 경로를 안 본다", () => {
    const k = { ...SNAP_KNOBS, routeM: 0 };
    expect(snap(mid, LAT0, P, { onRoute: new Set(["NS"]), knobs: k })?.seg_uid)
      .toBe("NS_EAST");
  });
});

describe("확신 — 비기면 안 믿는다", () => {
  it("두 길이 같은 거리면 `confident` 가 아니다", () => {
    const P = prepare([NS, NS_EAST]);
    const r = snap(LON0 + 10 * DLON, LAT0, P);
    expect(r?.confident).toBe(false);
  });
  it("한 길만 가까우면 믿는다", () => {
    const P = prepare([NS, NS_EAST]);
    expect(snap(LON0, LAT0, P)?.confident).toBe(true);
  });
});

describe("추적기 — heading 이 없으면 **이동량으로 만든다**", () => {
  it("GPS heading 이 null 이어도 두 점이면 방향이 선다", () => {
    const t = createTracker(prepare([NS, EW]));
    t.update(LON0, LAT0 - 10 * DLAT, null);          // 첫 점 — 방향 없음
    const r = t.update(LON0 + 0.4 * DLON, LAT0, null);  // 북으로 10m
    expect(r?.seg_uid).toBe("NS");
  });

  it("★ 2m 를 못 움직이면 방향을 **안 만든다** — 정지 중 GPS 잡음이 방향이 된다", () => {
    // 교차점에 **확신 있게** 올라선 뒤 0.5m 만 동쪽으로 흔든다.
    // 그 흔들림이 heading 90 으로 합성되면 EW 가 이긴다 — 그러면 안 된다.
    const t = createTracker(prepare([NS, EW]));
    t.update(LON0, LAT0 - 10 * DLAT, null);     // 남쪽 10m — NS 에 확신
    t.update(LON0, LAT0 - 0.4 * DLAT, null);    // 북으로 10m — heading 0 합성
    expect(t.current).toBe("NS");
    const r = t.update(LON0 + 0.5 * DLON, LAT0 - 0.4 * DLAT, null);
    expect(r?.seg_uid).toBe("NS");

    // ★ 반대 방향. **진짜 방향이 주어지면** EW 로 넘어간다 — 위가 「붙박이」가
    //   아니라 「방향을 안 만든 것」임을 이 줄이 증명한다.
    const t2 = createTracker(prepare([NS, EW]));
    t2.update(LON0, LAT0 - 10 * DLAT, null);
    t2.update(LON0, LAT0 - 0.4 * DLAT, null);
    expect(t2.update(LON0 + 0.5 * DLON, LAT0 - 0.4 * DLAT, 90)?.seg_uid).toBe("EW");
  });

  it("확신 없는 스냅은 **기억에 안 남는다**", () => {
    const t = createTracker(prepare([NS, NS_EAST]));
    t.update(LON0 + 10 * DLON, LAT0, 0);             // 비긴다
    expect(t.current).toBeNull();
  });

  it("`reset` 이 경로와 직전을 같이 지운다", () => {
    const t = createTracker(prepare([NS, NS_EAST]));
    t.setRoute(new Set(["NS"]));
    t.update(LON0, LAT0, 0);
    expect(t.current).toBe("NS");
    t.reset();
    expect(t.current).toBeNull();
    expect(t.update(LON0 + 12 * DLON, LAT0, 0)?.seg_uid).toBe("NS_EAST");
  });
});

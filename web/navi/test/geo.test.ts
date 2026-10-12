/**
 * geo.test.ts — 번들 **전부가 그 위에 서는** 다섯 함수. (DECISIONS §482)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 번들의 순수 함수 149 중 **40** 을 시험이 이름으로도
 * 안 부른다고 셌고, 그중 **일곱이 `domain/geo.ts`** 였다 — 번들에서 가장
 * 아래 깔린 모듈이다. `distM` 과 `bearing` 만 다섯 시험이 **곁눈으로** 들고
 * 있었고(거리를 쓰는 다른 주제의 시험들), 각도 · 누적 · 수선은 아무도 안
 * 들었다.
 *
 * ★ 이 자리는 **이미 한 번 크게 틀렸다**(§473). `MX` · `MY` 가 틀린 채
 *   3.3km 에서 11.09m 를 냈고, 그때 `egobox.test.ts` 는 **제 상수를 들고**
 *   있어서 두 오차가 서로 지워 초록이었다. 정본을 들어야 그 사고가 안 난다 —
 *   이 파일은 `geo` 에서 상수까지 **가져와** 민다.
 *
 * ★ 각도 둘은 **다른 일감**이다. 섞어 쓰면 조용히 틀린다 —
 *
 *       angleDelta   부호 있는 최단 회전(-180~180).  **회전 방향**이 필요한 쪽
 *       foldedDiff   0~90 으로 접는다.               **같은 도로인가**를 묻는 쪽
 *
 *   역주행은 회전으로는 180° 고 도로 매칭에서는 **0°** 다. 한쪽 자를 다른
 *   쪽에 쓰면 맞물린 차선이 서로 다른 도로가 되거나, 유턴이 직진이 된다.
 */
import { describe, expect, it } from "vitest";

import {
  LAT0, LON0, MX, MY, angleDelta, bearing, cumulative, distM, foldedDiff,
  pointAlong, projectOnSegment, type LngLat,
} from "../src/domain/geo";

/** 1m 에 해당하는 위도·경도. **정본 상수에서 낸다** — 손으로 적지 않는다. */
const DLAT = 1 / MY;
const DLON = 1 / MX;

const C: LngLat = [LON0, LAT0];

describe("① 상수 — 정본과 같은 수인가", () => {
  it("1도 거리가 곧 상수다", () => {
    // ★ `distM` 이 어떤 상수를 쓰는지를 **밖에서** 못박는다. 다른 수로
    //   갈아끼우면 여기가 운다 — §473 이 그렇게 넷을 찾았다.
    expect(distM([LON0, LAT0], [LON0, LAT0 + 1])).toBeCloseTo(MY, 6);
    expect(distM([LON0, LAT0], [LON0 + 1, LAT0])).toBeCloseTo(MX, 6);
  });

  it("미터 환산이 실제로 미터다", () => {
    expect(distM(C, [LON0, LAT0 + 100 * DLAT])).toBeCloseTo(100, 6);
    expect(distM(C, [LON0 + 100 * DLON, LAT0])).toBeCloseTo(100, 6);
  });
});

describe("② 방위각 — 북이 0 이고 시계방향이다", () => {
  it("네 방향", () => {
    expect(bearing(C, [LON0, LAT0 + DLAT])).toBeCloseTo(0, 6);
    expect(bearing(C, [LON0 + DLON, LAT0])).toBeCloseTo(90, 6);
    expect(bearing(C, [LON0, LAT0 - DLAT])).toBeCloseTo(180, 6);
    expect(bearing(C, [LON0 - DLON, LAT0])).toBeCloseTo(270, 6);
  });

  it("★ 같은 점끼리는 0 을 낸다 — **없다고 말하지 않는다**", () => {
    // 머리말에 없던 성질이라 적어 둔다. `atan2(0,0)` 이 0 이라 **북**이 된다.
    // 모르는 것을 북으로 말하는 셈인데, 부르는 쪽(`pointAlong`)이 길이 0 인
    // 구간을 안 만들어서 지금은 안 터진다. 꼴을 바꾸면 여기가 운다.
    expect(bearing(C, C)).toBe(0);
  });
});

describe("③ angleDelta — 부호 있는 최단 회전", () => {
  it("359→1 을 358 로 세지 않는다", () => {
    expect(angleDelta(350, 10)).toBeCloseTo(20, 9);
    expect(angleDelta(10, 350)).toBeCloseTo(-20, 9);
  });

  it("우가 양수 · 좌가 음수다", () => {
    expect(angleDelta(0, 90)).toBeCloseTo(90, 9);
    expect(angleDelta(90, 0)).toBeCloseTo(-90, 9);
  });

  it("반 바퀴는 180 이다", () => {
    expect(Math.abs(angleDelta(0, 180))).toBeCloseTo(180, 9);
  });

  it("★ 치역을 넘지 않는다 — 1도 단위로 한 바퀴 다 민다", () => {
    for (let a = 0; a < 360; a += 1) {
      for (const b of [0, 37, 180, 181, 359]) {
        const d = angleDelta(a, b);
        expect(Math.abs(d)).toBeLessThanOrEqual(180 + 1e-9);
        // 돌아온 각이 원래 각을 가리켜야 한다 (360 모듈로)
        expect(((a + d - b) % 360 + 360) % 360).toBeCloseTo(0, 9);
      }
    }
  });
});

describe("④ foldedDiff — 역주행도 같은 도로다", () => {
  it("반대 방향은 0 이다", () => {
    expect(foldedDiff(0, 180)).toBeCloseTo(0, 9);
    expect(foldedDiff(270, 90)).toBeCloseTo(0, 9);
  });

  it("직각은 90 이다 — 접기의 천장", () => {
    expect(foldedDiff(0, 90)).toBeCloseTo(90, 9);
    expect(foldedDiff(0, 91)).toBeCloseTo(89, 9);
  });

  it("★ 0~90 을 벗어나지 않고, 대칭이다", () => {
    for (let a = 0; a < 360; a += 7) {
      for (let b = 0; b < 360; b += 11) {
        const d = foldedDiff(a, b);
        expect(d).toBeGreaterThanOrEqual(0);
        expect(d).toBeLessThanOrEqual(90 + 1e-9);
        expect(foldedDiff(b, a)).toBeCloseTo(d, 9);
      }
    }
  });

  it("★ 두 자를 섞으면 안 되는 이유 — 역주행에서 둘이 갈린다", () => {
    expect(Math.abs(angleDelta(0, 180))).toBeCloseTo(180, 9);
    expect(foldedDiff(0, 180)).toBeCloseTo(0, 9);
  });
});

describe("⑤ cumulative — 좌표열의 누적 거리", () => {
  const line: LngLat[] = [
    C, [LON0, LAT0 + 30 * DLAT], [LON0 + 40 * DLON, LAT0 + 30 * DLAT],
  ];

  it("첫 원소가 0 이고 길이가 좌표 수와 같다", () => {
    const cum = cumulative(line);
    expect(cum[0]).toBe(0);
    expect(cum).toHaveLength(line.length);
  });

  it("30m 뒤 40m 면 70m 다", () => {
    const cum = cumulative(line);
    expect(cum[1]).toBeCloseTo(30, 6);
    expect(cum[2]).toBeCloseTo(70, 6);
  });

  it("단조증가한다", () => {
    const cum = cumulative(line);
    for (let i = 1; i < cum.length; i++) expect(cum[i]).toBeGreaterThanOrEqual(cum[i - 1]);
  });

  it("점 하나면 [0] 이다 — 빈 그물 쪽", () => {
    expect(cumulative([C])).toEqual([0]);
  });
});

describe("⑥ pointAlong — 좌표열 위를 걷는다", () => {
  const line: LngLat[] = [
    C, [LON0, LAT0 + 100 * DLAT], [LON0 + 100 * DLON, LAT0 + 100 * DLAT],
  ];
  const cum = cumulative(line);

  it("0 이면 첫 점 · 전체 길이면 끝 점", () => {
    expect(pointAlong(line, cum, 0).point[1]).toBeCloseTo(LAT0, 9);
    const end = pointAlong(line, cum, cum[2]).point;
    expect(distM(end, line[2])).toBeLessThan(1e-6);
  });

  it("중간이면 그 구간을 비례로 나눈다", () => {
    const got = pointAlong(line, cum, 25);
    expect(distM(got.point, C)).toBeCloseTo(25, 6);
    expect(got.heading).toBeCloseTo(0, 6);     // 첫 구간은 북행
  });

  it("두 번째 구간에 들어가면 진행방향이 바뀐다", () => {
    expect(pointAlong(line, cum, 150).heading).toBeCloseTo(90, 6);
  });

  it("★ 바깥 값은 **끝으로 자른다** — 던지지 않는다", () => {
    const before = pointAlong(line, cum, -500);
    const after = pointAlong(line, cum, 99_999);
    expect(distM(before.point, line[0])).toBeLessThan(1e-6);
    expect(distM(after.point, line[2])).toBeLessThan(1e-6);
  });

  it("★ 걸은 거리가 요청한 거리와 같다 — 1m 눈금으로 전 구간", () => {
    for (let d = 0; d <= cum[2]; d += 1) {
      const p = pointAlong(line, cum, d).point;
      // 꺾인 선이라 직선거리가 아니라 **누적으로** 되짚는다
      const walked = d <= 100 ? distM(p, line[0]) : 100 + distM(p, line[1]);
      expect(walked).toBeCloseTo(d, 6);
    }
  });
});

describe("⑦ projectOnSegment — 스냅의 최소 단위", () => {
  it("선분 가운데로 내린다", () => {
    const r = projectOnSegment(5, 3, 0, 0, 10, 0);
    expect(r.t).toBeCloseTo(0.5, 9);
    expect(r.cx).toBeCloseTo(5, 9);
    expect(r.cy).toBeCloseTo(0, 9);
    expect(r.dist).toBeCloseTo(3, 9);
  });

  it("★ 선분 **밖으로 안 나간다** — 끝점으로 자른다", () => {
    const before = projectOnSegment(-7, 0, 0, 0, 10, 0);
    expect(before.t).toBe(0);
    expect(before.dist).toBeCloseTo(7, 9);
    const after = projectOnSegment(17, 0, 0, 0, 10, 0);
    expect(after.t).toBe(1);
    expect(after.dist).toBeCloseTo(7, 9);
  });

  it("★ 길이 0 인 선분에 0 으로 나누지 않는다", () => {
    const r = projectOnSegment(3, 4, 1, 1, 1, 1);
    expect(r.t).toBe(0);
    expect(Number.isFinite(r.dist)).toBe(true);
    expect(r.dist).toBeCloseTo(Math.hypot(2, 3), 9);
  });

  it("선분 위의 점은 거리가 0 이다", () => {
    expect(projectOnSegment(4, 4, 0, 0, 10, 10).dist).toBeCloseTo(0, 9);
  });
});

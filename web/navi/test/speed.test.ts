/**
 * speed.test.ts — **도착 예정 시각이 전부 그 위에 선다.** (DECISIONS §482)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 센 40 중 **모듈 통째로 안 드는 것이 셋**이었고
 * `domain/speed.ts` 가 그중 하나다 — 내보낸 함수 셋 전부 시험이 이름을 안
 * 불렀다. 그 파일 머리말이 제 표를 **「미검증이다」**라고 적어 두고 있다.
 * 미검증인 표를 **고치는 날**에 무엇이 깨지는지 아무도 안 들고 있었다.
 *
 * ★ 여기가 미는 것은 **표의 값이 옳은가가 아니다.** 소방차 골목 속도는
 *   아직 아무도 안 쟀고(D-30 인터뷰 항목), `node_link` 의 `MAX_SPD` 가
 *   발행되면 갈아끼운다. 미는 것은 **표를 읽는 꼴**이다 —
 *
 *       문턱이 포함인가 (폭 12m 가 50 인가 40 인가)
 *       바닥이 덮이는가 (아무 폭이나 값을 받는가)
 *       대장 폭으로 **떨어지는가** (`width_min_m` 이 없을 때)
 *       배수가 시간에 **한 번만** 곱해지는가
 *       남은 시간이 전체 시간보다 **크지 않은가**
 *
 *   표를 갈아끼울 때 이 다섯은 그대로여야 한다. 그래서 값이 아니라 꼴을 문다.
 *
 * ★ 회전 판정 둘(`classify` · `round`)도 같이 든다 — 같은 40 안에 있었고,
 *   둘 다 **문턱이 박힌 순수 함수**라 미는 자가 없으면 문턱이 조용히 움직인다.
 */
import { describe, expect, it } from "vitest";

import { SPEED_TABLE, remainingSeconds, speedOf, travelSeconds } from "../src/domain/speed";
import { classify, round } from "../src/domain/turn";
import type { GraphEdge, RoutePlan } from "../src/domain/types";

/** 폭과 길이만 있는 구간. 속도 추정이 읽는 것은 그 둘이다. */
function edge(widthM: number | null, lengthM: number, roadBt?: number | null): GraphEdge {
  return {
    seg_uid: `W${widthM}`, verdict: "clear", width_min_m: widthM,
    length_m: lengthM, road_bt_m: roadBt, a: 0, b: 1, coords: [],
  } as GraphEdge;
}

/**
 * 경로 하나. ★ `as unknown as` — `speed.ts` 가 읽는 것은 `edges` · `cost` ·
 * `lengthM` 셋이고, 나머지 칸을 채우면 **무엇을 읽는지가 안 보인다.**
 */
function plan(edges: GraphEdge[], cost?: number): RoutePlan {
  const lengthM = edges.reduce((s, e) => s + (e.length_m ?? 0), 0);
  return { edges, lengthM, cost: cost ?? lengthM } as unknown as RoutePlan;
}

const KMH = (v: number) => v / 3.6;

describe("① 표를 읽는 꼴", () => {
  it("★ 바닥이 덮인다 — 표의 마지막 문턱이 0 이다", () => {
    // 이것이 깨지면 `speedOf` 가 표를 다 지나쳐 **뒤에 적힌 되돌림**으로
    // 떨어진다. 그 되돌림은 지금 닿지 않는 줄이고, 닿는 날은 표가 바닥을
    // 잃은 날이다.
    expect(SPEED_TABLE[SPEED_TABLE.length - 1][0]).toBe(0);
  });

  it("★ 문턱이 큰 것부터다 — 섞이면 좁은 길이 간선 속도를 받는다", () => {
    for (let i = 1; i < SPEED_TABLE.length; i++) {
      expect(SPEED_TABLE[i][0]).toBeLessThan(SPEED_TABLE[i - 1][0]);
      expect(SPEED_TABLE[i][1]).toBeLessThan(SPEED_TABLE[i - 1][1]);
    }
  });

  it("문턱은 **포함**이다", () => {
    for (const [w, kmh] of SPEED_TABLE) {
      expect(speedOf(edge(w, 10))).toBeCloseTo(KMH(kmh), 9);
    }
  });

  it("문턱 바로 아래는 한 칸 느리다", () => {
    for (let i = 0; i < SPEED_TABLE.length - 1; i++) {
      const [w] = SPEED_TABLE[i];
      expect(speedOf(edge(w - 0.01, 10))).toBeCloseTo(KMH(SPEED_TABLE[i + 1][1]), 9);
    }
  });

  it("★ 어떤 폭에도 **0 보다 큰** 속도를 낸다 — 0 이면 시간이 무한이 된다", () => {
    for (const w of [null, -3, 0, 0.5, 3.99, 4, 6.9, 7, 11.9, 12, 100]) {
      const v = speedOf(edge(w, 10));
      expect(v).toBeGreaterThan(0);
      expect(Number.isFinite(v)).toBe(true);
    }
  });

  it("폭이 없으면 **대장 폭으로 떨어진다**", () => {
    expect(speedOf(edge(null, 10, 12))).toBeCloseTo(KMH(50), 9);
    expect(speedOf(edge(null, 10, 2))).toBeCloseTo(KMH(20), 9);
    // 측정 폭이 있으면 대장 폭을 안 본다 — 순서가 뒤집히면 판정 폭이 밀린다
    expect(speedOf(edge(4, 10, 12))).toBeCloseTo(KMH(30), 9);
  });

  it("둘 다 없으면 가장 느린 칸이다 — 모르는 길을 빠르다고 하지 않는다", () => {
    expect(speedOf(edge(null, 10, null))).toBeCloseTo(KMH(20), 9);
  });
});

describe("② 소요 시간", () => {
  const P = plan([edge(12, 500), edge(4, 300)]);

  it("구간별 속도로 더한다", () => {
    expect(travelSeconds(P)).toBeCloseTo(500 / KMH(50) + 300 / KMH(30), 6);
  });

  it("★ 배수가 곱해진다 — 여유 없는 길은 느리다", () => {
    const tight = plan(P.edges, P.lengthM * 1.8);
    expect(travelSeconds(tight)).toBeCloseTo(travelSeconds(P) * 1.8, 6);
  });

  it("★ 길이 0 인 경로에 0 으로 나누지 않는다", () => {
    const z = plan([], 0);
    expect(travelSeconds(z)).toBe(0);
    expect(Number.isFinite(travelSeconds(z))).toBe(true);
  });

  it("길이가 없는 구간은 시간을 안 보탠다", () => {
    const e = { ...edge(4, 0), length_m: null } as GraphEdge;
    expect(travelSeconds(plan([e], 1))).toBe(0);
  });
});

describe("③ 남은 시간", () => {
  const P = plan([edge(12, 500), edge(4, 300)]);

  it("출발 전이면 전체와 같다", () => {
    expect(remainingSeconds(P, 0)).toBeCloseTo(travelSeconds(P), 6);
  });

  it("도착했으면 0 이다", () => {
    expect(remainingSeconds(P, P.lengthM)).toBeCloseTo(0, 9);
    expect(remainingSeconds(P, P.lengthM + 999)).toBeCloseTo(0, 9);
  });

  it("★ 단조감소다 — 달리는데 남은 시간이 늘면 화면이 뒤로 간다", () => {
    let prev = Infinity;
    for (let d = 0; d <= P.lengthM; d += 25) {
      const s = remainingSeconds(P, d);
      expect(s).toBeLessThanOrEqual(prev + 1e-9);
      prev = s;
    }
  });

  it("구간 가운데서는 **그 구간의 남은 몫만** 센다", () => {
    // 첫 구간 500m 중 200m 를 달렸다 → 첫 구간 300m + 둘째 구간 300m
    expect(remainingSeconds(P, 200))
      .toBeCloseTo(300 / KMH(50) + 300 / KMH(30), 6);
  });

  it("★ 둘째 구간에 들어가면 첫 구간을 안 센다", () => {
    expect(remainingSeconds(P, 500)).toBeCloseTo(300 / KMH(30), 6);
    expect(remainingSeconds(P, 650)).toBeCloseTo(150 / KMH(30), 6);
  });

  it("배수는 남은 시간에도 같은 배로 든다", () => {
    const tight = plan(P.edges, P.lengthM * 1.8);
    expect(remainingSeconds(tight, 200)).toBeCloseTo(remainingSeconds(P, 200) * 1.8, 6);
  });
});

describe("④ classify — 회전 문턱 25 · 50 · 120 · 160", () => {
  it("문턱 **안쪽**이 직진이다", () => {
    expect(classify(0)).toBe("straight");
    expect(classify(24.9)).toBe("straight");
    expect(classify(-24.9)).toBe("straight");
  });

  it("25 부터 꺾인 것이다 — 경계가 포함이 아니다", () => {
    expect(classify(25)).toBe("slight_right");
    expect(classify(-25)).toBe("slight_left");
  });

  it("50 부터 좌·우회전", () => {
    expect(classify(49.9)).toBe("slight_right");
    expect(classify(50)).toBe("right");
    expect(classify(-50)).toBe("left");
  });

  it("120 부터 급회전", () => {
    expect(classify(119.9)).toBe("right");
    expect(classify(120)).toBe("sharp_right");
    expect(classify(-120)).toBe("sharp_left");
  });

  it("160 **넘으면** 유턴이다", () => {
    expect(classify(160)).toBe("sharp_right");
    expect(classify(160.1)).toBe("uturn");
    expect(classify(-180)).toBe("uturn");
  });

  it("★ 부호가 좌우를 가른다 — 뒤집히면 안내가 반대로 나간다", () => {
    for (const a of [30, 60, 90, 130, 150]) {
      expect(classify(a)).toContain("right");
      expect(classify(-a)).toContain("left");
    }
  });

  it("★ 치역 밖을 내지 않는다 — 1도 단위로 두 바퀴", () => {
    const kinds = new Set(["straight", "slight_left", "left", "sharp_left",
      "slight_right", "right", "sharp_right", "uturn"]);
    for (let d = -360; d <= 360; d += 1) expect(kinds.has(classify(d))).toBe(true);
  });
});

describe("⑤ round — 사람이 쓰는 거리", () => {
  it("1km 넘으면 킬로미터다", () => {
    expect(round(1000)).toBe("1.0킬로미터");
    expect(round(2350)).toBe("2.4킬로미터");
  });

  it("300m 넘으면 100m 단위", () => {
    expect(round(300)).toBe("300미터");
    expect(round(487)).toBe("500미터");
  });

  it("100m 넘으면 50m 단위 — \"187미터 앞\" 은 사람이 못 쓴다", () => {
    expect(round(187)).toBe("200미터");
    expect(round(120)).toBe("100미터");
  });

  it("그 아래는 10m 단위", () => {
    expect(round(64)).toBe("60미터");
    expect(round(66)).toBe("70미터");
  });

  it("★ **0미터 앞** 이라고 말하지 않는다", () => {
    expect(round(0)).toBe("10미터");
    expect(round(3)).toBe("10미터");
  });

  it("★ 단조다 — 멀어지는데 수가 줄면 화면이 뒤로 간다", () => {
    let prev = -1;
    for (let m = 0; m <= 3000; m += 1) {
      const t = round(m);
      const v = t.endsWith("킬로미터") ? parseFloat(t) * 1000 : parseFloat(t);
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });
});

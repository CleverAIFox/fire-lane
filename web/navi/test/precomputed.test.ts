/**
 * precomputed.test.ts — 파이썬 대조를 **CI 로 끌어온다.** (DECISIONS §483)
 *
 * ── 왜 이 파일이 생겼나 ─────────────────────────────────────────
 * `tools/navicov.py` 가 `vehicle.verifyAgainstPrecomputed` 를 「시험이
 * 이름으로도 안 부른다」로 셌다. 소비자를 찾아보니 **`app/useBundle.ts`
 * 하나**였고, 그것은 브라우저가 묶음을 받은 뒤 `console.error` 와 화면
 * 알림을 낸다 — 즉 **사람이 내비를 열어 콘솔을 봐야** 아는 대조였다.
 *
 * `domain/vehicle.ts` 머리말은 그 함수를 두고 「소비자가 없던 83KB 짜리
 * 파일이 이제 **골든 테스트**가 된다」고 적는다. 골든 테스트는 CI 에서
 * 도는 것이고, 이것은 안 돌고 있었다 — 선언과 실물이 갈린 자리다.
 *
 * ★ `tests/test_vehicle_parity.py` 와 **다른 축**이다. 저쪽은 경계값 격자
 *   18,228칸으로 **식**을 견주고(결측 · 0 · 음수 · 검증 플래그), 여기는
 *   **실제 발행물의 통행 가부**를 본다(`radius_m=null` 고정 · 불리언 하나).
 *   저쪽 그물에 안 걸리는 것이 「발행된 폭 분포에서 두 판이 갈리는가」다.
 *
 * 밖    **식을 안 본다**(위 참조). **경로도 안 본다** — 통행 가부 하나다.
 */
import { describe, expect, it } from "vitest";

import { verifyAgainstPrecomputed } from "../src/domain/vehicle";
import type { GraphEdge, RouteVehicle, VehicleSpec } from "../src/domain/types";
import { FL } from "./harness";
import ref from "../../data/route_vehicle.json";

const { graph, spec } = FL;
const REF = ref as unknown as RouteVehicle;

describe("발행물 통행 가부 — 두 판이 같은 답을 내는가", () => {
  const got = verifyAgainstPrecomputed(graph.edges, spec, REF);

  it("★ 전제 — 셀 것이 있다. 0구간이면 이 시험은 빈 그물이다", () => {
    expect(got.checked).toBeGreaterThan(100);
  });

  it("★ 전량 일치한다 — 어긋나면 **두 언어의 규칙이 갈린 것**이다", () => {
    expect(got.mismatch).toEqual([]);
  });

  it("사전계산본이 그래프의 상당 부분을 덮는다", () => {
    // 덮임이 얕으면 「전량 일치」가 적은 표본의 일치다
    expect(got.checked).toBeGreaterThan(graph.edges.length * 0.5);
  });

  it("★ 음성 대조 — 차를 넓히면 **어긋난다**. 안 그러면 자가 죽었다", () => {
    const huge = { ...spec, width_m: 99 } as VehicleSpec;
    const bad = verifyAgainstPrecomputed(graph.edges, huge, REF);
    expect(bad.checked).toBe(got.checked);
    expect(bad.mismatch.length).toBeGreaterThan(0);
    // 어긋난 줄이 **무엇이 갈렸는지** 말한다 — 수만 세면 고칠 수가 없다
    expect(bad.mismatch[0]).toMatch(/ts=\d py=\d/);
  });

  it("사전계산본에 없는 구간은 **안 센다** — 모르는 것을 틀렸다고 하지 않는다", () => {
    const ghost = {
      seg_uid: "없는구간", verdict: "clear", width_min_m: 0.1,
      length_m: 10, a: 0, b: 1, coords: [],
    } as GraphEdge;
    const one = verifyAgainstPrecomputed([ghost], spec, REF);
    expect(one.checked).toBe(0);
    expect(one.mismatch).toEqual([]);
  });

  it("빈 입력에서 던지지 않는다", () => {
    expect(verifyAgainstPrecomputed([], spec, REF)).toEqual({ checked: 0, mismatch: [] });
  });
});

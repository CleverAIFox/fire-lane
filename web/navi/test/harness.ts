/**
 * test/harness.ts — 시험이 먹는 실제 발행물과 단언 하나.
 *
 * ★ 2026-09-22 (DECISIONS §217-5) — 러너를 **vitest** 로 바꿨다. 종전엔 esbuild 로
 *   한 파일씩 묶어 node 로 도는 수제 러너(`scripts/test.mjs` · 50줄)였다. 이유는
 *   「의존성을 늘리면 dependabot PR 이 는다」(§213-3)였는데, 사용자 원칙은 반대다 —
 *   **가능한 한 모든 것을 의존성에 맡긴다.** vitest 는 vite 설정을 그대로 먹고
 *   (같은 번들러 · 같은 변환), 병렬 · 감시 · 필터 · 실패 차이 출력을 공짜로 준다.
 *   수제 러너가 못 하던 것 — 한 시험만 골라 돌리기(`npx vitest -t 회전`)도 된다.
 *
 * ★ 시험은 `web/data` 의 **실제 발행물**(navi_graph.json)을 먹는다. 합성 도로만으로
 *   맞추면 실제 교차로 · 되돌아 나오는 경로에서 틀려도 모른다.
 */
import { test as vt } from "vitest";
import graph from "../../data/navi_graph.json";
import spec from "../../data/vehicle_spec.json";
import type { NaviGraph, VehicleSpec } from "../src/domain/types";

export const FL = {
  graph: graph as unknown as NaviGraph,
  spec: spec as unknown as VehicleSpec,
};

export const test = (name: string, fn: () => void | Promise<void>) => vt(name, fn);

export function ok(c: unknown, msg: string): asserts c {
  if (!c) throw new Error(msg);
}

export function quantile(xs: number[], q: number): number {
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(q * s.length))];
}

/**
 * test/harness.ts — 러너(`scripts/test.mjs`)가 넘긴 것을 받는다.
 * ★ node 타입을 안 쓴다. 파일은 러너가 읽어 `globalThis.__FL__` 로 넘긴다.
 */
import type { NaviGraph, VehicleSpec } from "../src/domain/types";

interface FL {
  graph: NaviGraph;
  spec: VehicleSpec;
  test(name: string, fn: () => void | Promise<void>): void;
}

export const FL = (globalThis as unknown as { __FL__: FL }).__FL__;
export const test = (name: string, fn: () => void | Promise<void>) => FL.test(name, fn);

export function ok(c: unknown, msg: string): asserts c {
  if (!c) throw new Error(msg);
}

export function quantile(xs: number[], q: number): number {
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(q * s.length))];
}

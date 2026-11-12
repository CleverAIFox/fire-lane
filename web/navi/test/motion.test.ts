/**
 * test/motion.test.ts — **차가 달리고 있는가**(`domain/motion.ts` · DECISIONS §704). 「자세히」 의 속도 잠금이 이것을 본다.
 */
import { ok, test } from "./harness";
import { fixSpeed, MOVING_MPS, nextMoving, STOPPED_MPS } from "../src/domain/motion";
import type { Fix } from "../src/domain/types";

const fix = (over: Partial<Fix> = {}): Fix => ({ lon: 126.9, lat: 35.15, heading: null, source: "gps", ...over });
const M_PER_DEG_LAT = 111_320;

test("속도가 실려 오면 그것을 쓴다(도플러) — 위치 차분보다 정지 근처에서 정확하다", () => {
  ok(fixSpeed({ lon: 126.9, lat: 35.15, t: 0 }, fix({ speedMps: 0.2 }), 1000) === 0.2, "실린 속도를 안 썼다");
  ok(fixSpeed(null, fix({ speedMps: 9 }), 1000) === 9, "앞 측위가 없어도 실린 속도는 쓴다");
});

test("속도가 없고 앞 측위도 없으면 모른다(null) — 모르는 속도로 풀지 않는다", () => {
  ok(fixSpeed(null, fix(), 1000) === null, "앞 측위 없이 속도를 만들었다");
});

test("차분 속도 — 측위 오차 안의 움직임은 정지다(정지한 GPS 가 흔들려도 달리는 것이 아니다)", () => {
  const prev = { lon: 126.9, lat: 35.15, t: 0 };
  const jitter = fix({ lat: 35.15 + 3 / M_PER_DEG_LAT, accuracy: 8 });           // 3m 흔들림 · 오차 8m
  ok(fixSpeed(prev, jitter, 1000) === 0, "오차 안의 흔들림이 속도가 됐다");
  const real = fix({ lat: 35.15 + 40 / M_PER_DEG_LAT, accuracy: 8 });            // 1초에 40m
  const v = fixSpeed(prev, real, 1000);
  ok(v !== null && Math.abs(v - 40) < 1, `실제 이동이 안 잡힌다: ${v}`);
});

test("차분 속도 — 간격이 너무 짧거나 길면 믿지 않는다", () => {
  const prev = { lon: 126.9, lat: 35.15, t: 0 }, far = fix({ lat: 35.15 + 100 / M_PER_DEG_LAT });
  ok(fixSpeed(prev, far, 100) === null && fixSpeed(prev, far, 9000) === null, "믿을 수 없는 간격에서 속도를 냈다");
});

test("히스테리시스 — 달리다가는 0.5 m/s 미만이 돼야 서고, 서 있다가는 1.0 m/s 이상이 돼야 달린다", () => {
  ok(nextMoving(true, STOPPED_MPS + 0.1) === true, "문턱 사이에서 서 버렸다(깜박임)");
  ok(nextMoving(false, MOVING_MPS - 0.1) === false, "문턱 사이에서 달려 버렸다(깜박임)");
  ok(nextMoving(true, STOPPED_MPS - 0.1) === false && nextMoving(false, MOVING_MPS) === true, "문턱을 넘었는데 안 바뀐다");
  ok(nextMoving(true, null) === true && nextMoving(false, null) === false, "모르는 속도가 상태를 바꿨다");
});

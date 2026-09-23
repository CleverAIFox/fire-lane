/**
 * test/egobox.test.ts — 자차 상자가 **실측 크기인가.**  (DECISIONS §232)
 *
 * ★ 이 화면의 존재 이유가 「이 차가 이 골목에 들어가나」이므로, 차 크기가
 *   틀리면 화면 전체가 거짓말이 된다. 종전 DOM 마커는 **화면 픽셀**이라
 *   줌마다 비율이 달라졌고, 그래서 눈으로 가늠할 수 없었다.
 *
 * ★ 여기서 무는 것 넷 —
 *     ① 상자의 실제 치수가 `fleet.json` 제원과 같은가 (미터로 되짚는다)
 *     ② 방위를 돌리면 그만큼 돌아가는가
 *     ③ 제원이 없으면 **상자를 안 놓는가** (없는 숫자를 그림으로 주장하지 않는다)
 *     ④ 상자 폭이 **전폭**이지 필요폭(전폭+여유)이 아닌가
 */
import { test, ok } from "./harness";
import fleetJson from "../../data/fleet.json";
import { egoBox, egoFeature } from "../src/domain/egobox";
import { requiredWidth } from "../src/domain/vehicle";
import type { Fleet, VehicleSpec } from "../src/domain/types";

const fleet = fleetJson as unknown as Fleet;
const pump = fleet.vehicles.find((v) => v.id === "pump-js")!;

const SPEC: VehicleSpec = {
  kind: pump.label, width_m: pump.width_m, clearance_m: pump.clearance_m,
  length_m: pump.length_m, height_m: pump.height_m,
  wheelbase_m: null, turn_radius_m: null,
};

const LON = 126.9266, LAT = 35.1512;
const R = 6378137;
const M_LAT = (Math.PI * R) / 180;
const M_LON = M_LAT * Math.cos((LAT * Math.PI) / 180);

/** 두 꼭짓점 사이 거리(m). 국소 평면 — 차 한 대 크기라 충분하다. */
function dist(a: [number, number], b: [number, number]): number {
  const dx = (a[0] - b[0]) * M_LON, dy = (a[1] - b[1]) * M_LAT;
  return Math.hypot(dx, dy);
}

test("제원이 fleet.json 에 실제로 있다 — 없으면 이 시험이 빈 그물이다", () => {
  ok(pump.length_m != null && pump.height_m != null,
     `pump-js 전장·전고가 없다: ${pump.length_m} · ${pump.height_m}`);
  ok(pump.width_m > 0, "전폭이 없다");
});

test("상자 치수가 제원과 같다 (전폭 × 전장)", () => {
  const b = egoBox(SPEC, LON, LAT, 0)!;
  ok(b != null, "상자가 안 나왔다");
  ok(b.ring.length === 5, `꼭짓점이 ${b.ring.length} — 닫힌 사각형이 아니다`);
  const w = dist(b.ring[0], b.ring[1]);   // 앞변 = 전폭
  const l = dist(b.ring[1], b.ring[2]);   // 옆변 = 전장
  ok(Math.abs(w - pump.width_m!) < 0.02, `전폭 ${w.toFixed(3)} ≠ ${pump.width_m}`);
  ok(Math.abs(l - pump.length_m!) < 0.02, `전장 ${l.toFixed(3)} ≠ ${pump.length_m}`);
  ok(b.heightM === pump.height_m, `전고 ${b.heightM} ≠ ${pump.height_m}`);
});

test("상자 폭은 **전폭**이다 — 필요폭(전폭+여유)이 아니다", () => {
  const b = egoBox(SPEC, LON, LAT, 0)!;
  const w = dist(b.ring[0], b.ring[1]);
  const need = requiredWidth(SPEC);
  ok(need > pump.width_m!, "이 시험의 전제가 깨졌다 — 필요폭이 전폭보다 커야 한다");
  ok(Math.abs(w - need) > 0.3,
     `상자가 필요폭 ${need} 로 그려졌다 — 차를 실제보다 넓게 주장한다`);
});

test("방위 0 은 북쪽을 향한다 — 앞 중점이 북에 있다", () => {
  const b = egoBox(SPEC, LON, LAT, 0)!;
  const frontY = (b.ring[0][1] + b.ring[1][1]) / 2;
  const backY = (b.ring[2][1] + b.ring[3][1]) / 2;
  ok(frontY > backY, "방위 0 인데 앞이 북쪽이 아니다");
  ok(Math.abs((frontY - backY) * M_LAT - pump.length_m!) < 0.02, "전장이 안 맞는다");
});

test("방위 90 은 동쪽을 향한다", () => {
  const b = egoBox(SPEC, LON, LAT, 90)!;
  const frontX = (b.ring[0][0] + b.ring[1][0]) / 2;
  const backX = (b.ring[2][0] + b.ring[3][0]) / 2;
  ok(frontX > backX, "방위 90 인데 앞이 동쪽이 아니다");
  ok(Math.abs((frontX - backX) * M_LON - pump.length_m!) < 0.02, "전장이 안 맞는다");
});

test("방위를 돌려도 치수는 안 변한다", () => {
  for (const brg of [0, 37, 90, 180, 271, 359]) {
    const b = egoBox(SPEC, LON, LAT, brg)!;
    const w = dist(b.ring[0], b.ring[1]), l = dist(b.ring[1], b.ring[2]);
    ok(Math.abs(w - pump.width_m!) < 0.02, `${brg}° 에서 전폭 ${w.toFixed(3)}`);
    ok(Math.abs(l - pump.length_m!) < 0.02, `${brg}° 에서 전장 ${l.toFixed(3)}`);
  }
});

test("제원이 없으면 상자를 안 놓는다 — 없는 숫자를 그림으로 주장하지 않는다", () => {
  const noLen = { ...SPEC, length_m: null };
  const noHgt = { ...SPEC, height_m: null };
  ok(egoBox(noLen, LON, LAT, 0) === null, "전장 없이 상자가 나왔다");
  ok(egoBox(noHgt, LON, LAT, 0) === null, "전고 없이 상자가 나왔다");
  ok(egoBox(null, LON, LAT, 0) === null, "제원 없이 상자가 나왔다");
  ok(egoFeature(null).features.length === 0, "빈 상자가 피처를 낸다");
});

test("fleet.json 에서 상자가 나오는 차와 안 나오는 차가 둘 다 있다", () => {
  const made = fleet.vehicles.filter((v) => egoBox(
    { ...SPEC, width_m: v.width_m, length_m: v.length_m ?? null,
      height_m: v.height_m ?? null }, LON, LAT, 0) !== null);
  ok(made.length > 0, "상자가 나오는 차가 하나도 없다 — 판정기가 죽었다");
  ok(made.length < fleet.vehicles.length,
     "전부 상자가 나온다 — 제원 없는 차를 거르는 갈래가 안 돈다");
});

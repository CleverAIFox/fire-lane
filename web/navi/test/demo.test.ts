/**
 * test/demo.test.ts — 시연은 GPS 와 무관한 축이다.  (DECISIONS §713 · ⓲C)
 * 세 상태(없음 · 구역 밖 · 실주행) × 모든 단계를 **표로** 민다.
 */
import { ok, test } from "./harness";
import { DEMO_BADGE, DEMO_START, canStartDemo, noGpsNotice, type GpsState } from "../src/domain/demo";
import { demoUi } from "../src/ui/DemoStrip";
import { outsideNotice } from "../src/domain/serviceArea";
import type { Phase } from "../src/domain/types";

const PHASES: Phase[] = ["loading", "idle", "picked", "preview", "guiding", "arrived"];
const GPS: GpsState[] = ["idle", "none", "outside", "live"];

test("시연이 켜져 있으면 어느 단계 · 어느 측위에서든 표가 나고 끝내기가 있다", () => {
  for (const ph of PHASES) for (const g of GPS) {
    const u = demoUi(ph, g, true);
    ok(u.badge && u.button === "end", `${ph}/${g}: ${JSON.stringify(u)}`);
  }
});

test("실주행 중(주행 단계 + 구역 안 측위가 오는 중)에는 못 켠다 · 단추도 없다", () => {
  ok(!canStartDemo("guiding", "live", false), "실주행 중에 켜졌다");
  ok(demoUi("guiding", "live", false).button === null, "실주행 중에 단추가 있다");
  // 그 밖에는 켤 수 있다 — 서울(구역 밖) · GPS 없음 · 주행 전
  for (const g of ["idle", "none", "outside"] as GpsState[]) ok(canStartDemo("guiding", g, false), `guiding/${g}`);
  for (const ph of ["idle", "picked", "preview"] as Phase[]) ok(canStartDemo(ph, "live", false), `${ph}/live — 주행 전이다`);
});

test("안내 문구가 가리키는 단추는 **반드시 화면에 있다** — 문구가 뜨는 모든 조건에서 `start` 단추", () => {
  // 문구가 뜨는 조건: 주행 단계 · 시연 꺼짐 · 측위가 없음/구역 밖
  for (const g of ["none", "outside"] as GpsState[]) ok(demoUi("guiding", g, false).button === "start", `${g}`);
  for (const t of [noGpsNotice(), outsideNotice(265_000)]) ok(t.includes(`「${DEMO_START}」`), `문구가 단추 이름을 안 부른다: ${t}`);
  ok(!noGpsNotice().includes("▶"), "문구가 ▶ 를 가리킨다 — ▶ 는 `?dev=1` 에만 있다");
  ok(!outsideNotice(10).includes("▶"), "구역 밖 문구가 ▶ 를 가리킨다");
});

test("주행 전에는 켜기 단추 · 도착 · 로딩에는 없다", () => {
  for (const ph of ["idle", "picked", "preview"] as Phase[]) ok(demoUi(ph, "idle", false).button === "on", ph);
  for (const ph of ["loading", "arrived"] as Phase[]) ok(demoUi(ph, "idle", false).button === null && !demoUi(ph, "idle", false).badge, ph);
});

test("띠는 「시연」을 말하고 단추 이름은 안내 문구가 부르는 그것이다", () => {
  ok(DEMO_BADGE.includes("시연"), DEMO_BADGE);
  ok(noGpsNotice().includes(DEMO_START), "문구가 단추 이름을 안 부른다");
});

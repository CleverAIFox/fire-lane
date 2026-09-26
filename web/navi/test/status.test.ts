/**
 * test/status.test.ts — 화면 상태가 **신호대로 갈리는가.**  (DECISIONS §242)
 *
 * ★ 2026-09-24. `domain/status.ts::deriveStatus` 한 줄이 18장의 화면을 가르는데
 *   **시험이 한 줄도 없었다.** 감사가 React·infra 층 전체에 시험이 없다고 냈고
 *   그중 이것이 제일 위다 — 순수 함수라 지금 바로 물 수 있는데 안 물고 있었다.
 *
 * ★ 이 배치가 고친 둘을 특히 문다 —
 *     ① GPS 약함(08)이 **주입이 아니라 신호**다. 종전에는 정확도를 받을
 *        타입조차 없어 50m 로 흔들려도 초록 「안전 경로 안내중」 이었다.
 *     ② 우선순위. 도착보다 아래, 나머지보다 위다 — 위치를 못 믿는데
 *        「재탐색」 이나 회전 안내를 띄우면 그것이 거짓 화면이다.
 */
import { test, ok } from "./harness";
import { deriveStatus, GPS_WEAK_M, STATUS, type StatusSignals } from "../src/domain/status";

const base: StatusSignals = {
  phase: "guiding", choice: "safe", rerouting: false, noRoute: false,
  blockedPending: false, detourFresh: false, arrivalAcked: false,
  remainM: 800, onUnverified: false, injected: null,
};
const S = (o: Partial<StatusSignals>) => deriveStatus({ ...base, ...o });

test("평소에는 선택한 경로 어휘가 뜬다", () => {
  ok(S({}) === "safe", S({}));
  ok(S({ choice: "fast" }) === "fast", S({ choice: "fast" }));
});

test("GPS 정확도가 임계를 넘으면 08 로 내려간다 — **신호**다", () => {
  ok(S({ gpsAccM: GPS_WEAK_M + 1 }) === "gpsWeak", S({ gpsAccM: GPS_WEAK_M + 1 }));
  ok(S({ gpsAccM: GPS_WEAK_M }) === "safe", "임계 그 자체는 넘은 것이 아니다");
  ok(S({ gpsAccM: 3 }) === "safe", "좋은 신호가 08 을 띄우면 안 된다");
});

test("정확도를 **모르면** 08 을 안 띄운다 — 모르는 것과 나쁜 것은 다르다", () => {
  ok(S({ gpsAccM: null }) === "safe", "null 이 08 을 띄운다");
  ok(S({}) === "safe", "칸이 없으면 08 을 띄운다");
});

test("도착은 GPS 가 나빠도 도착이다 — 우선순위가 위다", () => {
  ok(S({ phase: "arrived", gpsAccM: 99 }) === "arrived", "도착보다 08 이 이긴다");
  ok(S({ phase: "arrived", arrivalAcked: true, gpsAccM: 99 }) === "reported",
     "신고 완료가 08 에 밀린다");
});

test("위치를 못 믿으면 재탐색 · 경로없음 · 골목경고보다 08 이 앞선다", () => {
  ok(S({ rerouting: true, gpsAccM: 99 }) === "gpsWeak", "재탐색이 08 을 이긴다");
  ok(S({ noRoute: true, gpsAccM: 99 }) === "gpsWeak", "경로없음이 08 을 이긴다");
  ok(S({ onUnverified: true, gpsAccM: 99 }) === "gpsWeak", "골목경고가 08 을 이긴다");
  ok(S({ remainM: 10, gpsAccM: 99 }) === "gpsWeak", "최종접근이 08 을 이긴다");
});

test("주입은 무엇이든 이긴다 — 시연 막대의 계약이다", () => {
  ok(S({ injected: "noRoute", gpsAccM: 99 }) === "noRoute", "주입이 08 에 밀린다");
  ok(S({ injected: "arrived", phase: "guiding" }) === "arrived", "주입이 단계에 밀린다");
});

test("★ 08 이 더는 **주입 전용**이 아니다", () => {
  ok(!STATUS.gpsWeak.injected,
     "gpsWeak 에 injected 표식이 남아 있다 — 이제 신호다");
  // 서버가 없어 아직 주입뿐인 것들은 그대로여야 한다
  for (const k of ["offline", "restored", "dataDelayed", "serviceError"] as const) {
    ok(STATUS[k].injected === true, `${k} 는 아직 주입이다`);
  }
});

test("18장 전부가 표에 있고 와이어프레임 번호를 든다 — 빈 그물 방지", () => {
  const keys = Object.keys(STATUS);
  ok(keys.length >= 15, `상태가 ${keys.length}개뿐이다`);
  for (const k of keys) {
    ok(STATUS[k as keyof typeof STATUS].wf.length > 0, `${k} 에 wf 번호가 없다`);
  }
});

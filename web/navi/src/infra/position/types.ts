/**
 * infra/position/types.ts — 위치가 어디서 오든 같은 모양으로 온다.
 *
 * ── 왜 인터페이스로 빼나 ────────────────────────────────────────
 * 2026-09-05. GPS 와 시뮬레이션이 **다른 코드 경로로 같은 일**을 하고
 * 있었다. 하나를 고치면 다른 쪽이 조용히 어긋나고, 실제 차량 텔레메트리가
 * 오면 세 번째 경로가 생긴다. OCP 위반이다.
 *
 * 소스를 인터페이스 뒤로 밀면 `NavigationContext` 는 **어느 소스인지
 * 모른다.** 소스만 갈아끼운다.
 *
 *   GpsSource          navigator.geolocation
 *   SimulationSource   경로를 따라 걷는다. 발표에서 차를 못 모니 필수다
 *   TelemetrySource    나중. 차량 단말
 *
 * ★ 부수 효과가 값어치 있다 — 시뮬레이션이 그대로 **테스트 더블**이다.
 *   좌표열을 넣고 스냅 결과를 검증하는 단위 테스트가 브라우저 없이 돈다.
 */
import type { Fix } from "../../domain/types";

export interface PositionSource {
  /** 무엇으로 위치를 내는가. 화면이 "시뮬레이션 중" 을 알리는 데 쓴다 */
  readonly kind: Fix["source"];
  /** 구독을 시작한다. 반환값을 부르면 멈춘다 */
  start(onFix: (f: Fix) => void, onError?: (msg: string) => void): () => void;
}

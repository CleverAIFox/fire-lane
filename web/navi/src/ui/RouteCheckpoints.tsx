/**
 * ui/RouteCheckpoints.tsx — 관제 경로 카드의 「소화전 N · CCTV N」 (PLAN #72).
 *
 * ★ **접어서 붙인다.** 기본은 접힌 상태이고 펼쳐야 보인다 — 카드의 첫 시선(예측 시간 · 확인 필요 · 폭 모름 · 여유폭)을 안 흐린다.
 * ★ **관제 화면에만** 붙는다. 내비는 진입 청크 여유가 137B 라 못 넣는다(이 파일은 `OpsApp` 만 부른다).
 * ★ 말은 경로 카드와 같다 — 모르면 「모름」(「폭 모름」과 같은 낱말)이고 0 이라고 쓰지 않는다(`domain/checkpoints.ts`).
 */
import { routeCheckpoints } from "../domain/checkpoints";
import type { GraphEdge } from "../domain/types";
import { D } from "./opsTheme";

const n = (v: number | null) => (v == null ? "모름" : String(v));

export function RouteCheckpoints({ edges }: { edges: readonly Pick<GraphEdge, "hyd" | "cctv">[] }) {
  const c = routeCheckpoints(edges);
  return (
    <details style={{ marginTop: 4 }}>
      <summary style={{ cursor: "pointer", color: D.sub }}>체크포인트</summary>
      소화전 {n(c.hyd)} · CCTV {n(c.cctv)}
    </details>
  );
}

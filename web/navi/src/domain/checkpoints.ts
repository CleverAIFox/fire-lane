/**
 * domain/checkpoints.ts — 경로 위의 소화전 · CCTV 지점 수 (PLAN #72).
 *
 * `src/firelane/publish_checkpoints.py::route_checkpoints` 와 **같은 규칙**이다 —
 *   · 수는 엣지 번호 목록의 **합집합 크기**다(같은 지점이 두 엣지에 붙어도 한 번 센다)
 *   · 경로의 엣지 하나라도 그 칸이 없거나 `null` 이면 수는 `null`(모른다) — 아는 엣지만 세어 「적어도 N」을 「N」이라 말하지 않는다
 *   · 빈 경로는 0 이 아니라 `null`
 */
import type { GraphEdge } from "./types";

export interface RouteCheckpoints { hyd: number | null; cctv: number | null }

function countUnion(edges: readonly Pick<GraphEdge, "hyd" | "cctv">[], kind: "hyd" | "cctv"): number | null {
  if (edges.length === 0) return null;
  const ids = new Set<number>();
  for (const e of edges) {
    const v = e[kind];
    if (v == null) return null;
    for (const id of v) ids.add(id);
  }
  return ids.size;
}

export function routeCheckpoints(edges: readonly Pick<GraphEdge, "hyd" | "cctv">[]): RouteCheckpoints {
  return { hyd: countUnion(edges, "hyd"), cctv: countUnion(edges, "cctv") };
}

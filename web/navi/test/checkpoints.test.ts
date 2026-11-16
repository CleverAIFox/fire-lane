/** domain/checkpoints.ts — `route_checkpoints`(Python · `publish_checkpoints.py`)와 같은 규칙인가 (PLAN #72). */
import { FL, ok, test } from "./harness";
import { routeCheckpoints } from "../src/domain/checkpoints";

test("같은 지점이 두 엣지에 붙어도 한 번 센다 — 수는 합집합이다", () => {
  const c = routeCheckpoints([{ hyd: [1, 2], cctv: [7] }, { hyd: [2, 3], cctv: [7] }]);
  ok(c.hyd === 3 && c.cctv === 1, `합집합이 아니다: ${JSON.stringify(c)}`);
});

test("한 엣지라도 칸이 없거나 null 이면 모른다(null) — 아는 것만 세어 「적어도 N」을 N 이라 안 한다", () => {
  ok(routeCheckpoints([{ hyd: [1] }, { hyd: null }]).hyd === null, "null 엣지가 섞였는데 수를 냈다");
  ok(routeCheckpoints([{ hyd: [1] }, {}]).hyd === null, "칸이 없는 엣지가 섞였는데 수를 냈다");
  ok(routeCheckpoints([{ hyd: [] }]).hyd === 0, "빈 목록은 0 이다(모름이 아니다)");
});

test("빈 경로는 0 이 아니라 null 이다", () => {
  const c = routeCheckpoints([]);
  ok(c.hyd === null && c.cctv === null, "빈 경로에 수를 냈다");
});

test("발행 그래프의 실제 엣지 칸이 이 함수가 읽는 모양이다(빈 그물 방지)", () => {
  const withHyd = FL.graph.edges.filter((e) => (e.hyd?.length ?? 0) > 0);
  ok(withHyd.length > 0, "소화전이 붙은 엣지가 0 이다 — 칸이 비었다");
  const c = routeCheckpoints(withHyd.slice(0, 5));
  const sum = withHyd.slice(0, 5).reduce((s, e) => s + (e.hyd?.length ?? 0), 0);
  ok(c.hyd !== null && c.hyd > 0 && c.hyd <= sum, `합집합 ${c.hyd} 이 합 ${sum} 보다 크거나 0 이다`);
});

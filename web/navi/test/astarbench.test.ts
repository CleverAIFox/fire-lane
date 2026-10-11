/**
 * test/astarbench.test.ts — **A* 가 어디서 이득이고 어디서 아닌가.** (PLAN §1 #71)
 *
 * ── 왜 생겼나 ───────────────────────────────────────────────────
 * `#71` 은 「A* 대 다익스트라 실행시간 비교 그래프 한 장」을 들고 있었고, 그 행이
 * 스스로 적은 사유가 **「A* 를 쓰는 이유는 속도가 아니다」**였다. 그런데 그 말을
 * 뒷받침하는 수가 어디에도 없었다 — `findRoute` 에 `heuristic` 인자가 있는데
 * (§373 이 그 비교축을 꺼냈다) **무엇이 달라지나를 세는 자리가 없었다.**
 *
 * ★ **벽시계로 안 잰다.** 같은 입력에 같은 수가 나와야 그림이 되고, 밀리초는
 *   그 기계의 부하를 탄다. 세는 것은 `RouteStats.expanded` — 확정한 상태 수다.
 *   정렬이 거기 붙으므로 복잡도를 지배하는 수이기도 하다.
 *
 * ★ 묻는 것 둘 —
 *     ① 1→1 (내비)            A* 가 **덜 연다.** 이것이 A* 를 쓰는 이유다
 *     ② 1→전 노드 (현재 산출)  다익스트라는 **한 번에** 전부 푼다. A* 는 목표마다
 *                              다시 열어야 하므로 **이득이 없다** — 그 수를 댄다
 *
 * ★ 재고 **장부에 적는다**(`data/golden/astar.json`). 그림을 그리는 쪽은
 *   파이썬이고 그 기계에 node 가 없을 수 있다 — 수를 커밋해 두면 `render_figures`
 *   가 어디서든 돈다. 그리고 이 시험이 그 장부를 **매 실행 대조한다**:
 *   어긋나면 운다. 받아적은 수가 아니라 **재서 적은 수**다.
 */
import { FL, test, ok } from "./harness";
import { buildAdjacency, findRoute, type RouteStats } from "../src/domain/graph";
import type { Adjacency } from "../src/domain/adjacency";
import LEDGER from "../../../data/golden/astar.json";

/** 장부 꼴. 적는 쪽과 읽는 쪽이 **같은 모양**을 본다. */
type Bench = {
  nodes: number;
  pairs: number;
  one_to_one: { astar: number; dijkstra: number };
  one_to_all: { astar_sum: number; dijkstra_sweep: number; goals: number };
};

const BOOK = LEDGER as unknown as Bench;

/** 씨를 박은 난수 — 같은 쌍을 매번 고른다. 표본이 흔들리면 수가 흔들린다. */
function rnd(seed: number): () => number {
  let r = seed;
  return () => (r = (r * 1103515245 + 12345) % 2147483648) / 2147483648;
}

/** 그 탐색이 연 상태 수. 경로가 없으면 `null` — 0 과 다른 사실이다. */
function expanded(adj: Adjacency, a: number, b: number, h: boolean): number | null {
  const st: RouteStats = { expanded: 0 };
  const plan = findRoute(FL.graph, adj, a, b, h, st);
  return plan ? st.expanded : null;
}

/** 전 노드를 **한 번에** 쓸었을 때의 전개 수. 닿지 못하는 목표를 쓴다. */
function sweep(adj: Adjacency, src: number, unreachable: number): number {
  const st: RouteStats = { expanded: 0 };
  findRoute(FL.graph, adj, src, unreachable, false, st);   // null 로 끝난다
  return st.expanded;
}

/** `src` 에서 **닿지 못하는** 노드. 쓸기의 목표로 쓴다. 없으면 `null`. */
function findUnreachable(adj: Adjacency, src: number): number | null {
  const N = FL.graph.nodes.length;
  for (let n = 0; n < N; n++) {
    if (n !== src && findRoute(FL.graph, adj, src, n, false) === null) return n;
  }
  return null;
}

test("① 1→1 에서 A* 가 다익스트라보다 덜 연다", () => {
  const adj = buildAdjacency(FL.graph, FL.spec);
  const N = FL.graph.nodes.length;
  const next = rnd(20261011);
  let a1 = 0, d1 = 0, pairs = 0;
  for (let i = 0; i < 600 && pairs < BOOK.pairs; i++) {
    const a = Math.floor(next() * N), b = Math.floor(next() * N);
    if (a === b) continue;
    const ea = expanded(adj, a, b, true), ed = expanded(adj, a, b, false);
    if (ea === null || ed === null) continue;
    pairs++; a1 += ea; d1 += ed;
  }
  console.log(`  1→1  쌍 ${pairs} · A* ${a1} · 다익스트라 ${d1}`
    + ` · 몫 ${(a1 / d1).toFixed(3)}`);
  ok(pairs === BOOK.pairs,
    `쌍 ${pairs} ≠ 장부 ${BOOK.pairs} — 표본이 달라졌다. 발행 그래프가 바뀌었으면`
    + " 장부를 다시 적어라(이 시험이 낸 수를 `data/golden/astar.json` 에)");
  ok(a1 < d1, `A* 가 더 많이 열었다 — A* ${a1} · 다익스트라 ${d1}`);
  ok(a1 === BOOK.one_to_one.astar && d1 === BOOK.one_to_one.dijkstra,
    `장부와 어긋난다 — 실측 A* ${a1} · D ${d1},`
    + ` 장부 A* ${BOOK.one_to_one.astar} · D ${BOOK.one_to_one.dijkstra}`);
});

test("② 1→전 노드에서는 A* 가 이득이 없다 — 다익스트라는 한 번에 푼다", () => {
  const adj = buildAdjacency(FL.graph, FL.spec);
  const N = FL.graph.nodes.length;
  // ★ 출발은 **고정**이다. 무작위로 고르면 수가 매 실행 흔들려 그림이 못 된다.
  const src = 0;
  const far = findUnreachable(adj, src);
  ok(far !== null,
    "닿지 못하는 노드가 없다 — 그러면 한 번의 쓸기를 끝까지 못 돌린다."
    + " 발행 그래프가 완전연결이 됐으면 이 측정의 기준을 다시 정해야 한다");
  const one = sweep(adj, src, far);

  let sum = 0, goals = 0;
  for (let n = 0; n < N; n++) {
    if (n === src) continue;
    const e = expanded(adj, src, n, true);
    if (e === null) continue;
    sum += e; goals++;
  }
  console.log(`  1→전노드  목표 ${goals} · A* 합 ${sum} · 다익스트라 쓸기 ${one}`
    + ` · 배수 ${(sum / one).toFixed(1)}`);
  ok(sum > one * 10,
    `A* 합 ${sum} 이 쓸기 ${one} 의 열 배도 안 된다 — 「이득이 없다」는 주장의`
    + " 근거가 약해졌다. 다시 재고 `#71` 의 결론을 다시 적어라");
  ok(goals === BOOK.one_to_all.goals && sum === BOOK.one_to_all.astar_sum
    && one === BOOK.one_to_all.dijkstra_sweep,
    `장부와 어긋난다 — 실측 목표 ${goals} · A* ${sum} · 쓸기 ${one},`
    + ` 장부 목표 ${BOOK.one_to_all.goals} · A* ${BOOK.one_to_all.astar_sum}`
    + ` · 쓸기 ${BOOK.one_to_all.dijkstra_sweep}`);
});

test("③ 장부의 노드 수가 발행 그래프와 같다", () => {
  // ★ 분모가 갈리면 위 두 수가 무엇의 수인지 모른다. **빈 그물의 반대쪽**이다.
  ok(BOOK.nodes === FL.graph.nodes.length,
    `장부 노드 ${BOOK.nodes} ≠ 발행 ${FL.graph.nodes.length} — 장부가 낡았다`);
  ok(BOOK.pairs > 50, `쌍 ${BOOK.pairs} — 표본이 얇다`);
});

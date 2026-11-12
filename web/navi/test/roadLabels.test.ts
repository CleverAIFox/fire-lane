/**
 * test/roadLabels.test.ts — 도로명 글자를 **화면 기준으로 이름마다 한 점**, 가로로, 아이콘 밑에.  (PLAN #73 · DECISIONS §711)
 * 순수 함수(`pickRoadLabels` · `clipPolyline`)와 층 선언을 문다. 지도 엔진의 충돌은 `scripts` 의 실측이 든다(브라우저).
 */
import { ok, test } from "./harness";
import { CHAR_PX, LABEL_MARGIN_PX, MIN_PIECE_PX, ROAD_LABEL_SRC, attachRoadLabels, clipPolyline, labelCollection, pickRoadLabels, roadLabelLayers, type RoadPiece } from "../src/components/roadLabels";

const W = 1000, H = 700;
const line = (name: string, ...px: [number, number][]): RoadPiece => ({ name, px });

test("clipPolyline — 상자 밖은 자르고 이어지는 조각마다 한 줄", () => {
  const out = clipPolyline([[-100, 50], [500, 50]], [0, 0, 400, 100]);
  ok(out.length === 1 && Math.abs(out[0][0][0]) < 1e-6 && Math.abs(out[0][1][0] - 400) < 1e-6, JSON.stringify(out));
  ok(clipPolyline([[-50, -50], [-10, -10]], [0, 0, 100, 100]).length === 0, "상자 밖 선이 남았다");
  const two = clipPolyline([[10, 50], [500, 50], [500, 80], [10, 80]], [0, 0, 100, 100]);
  ok(two.length === 2, `나갔다 들어오면 조각이 둘이다: ${two.length}`);
});

test("같은 이름은 한 점만 — 가장 긴 조각을 쓴다(동명로가 넷 뜨던 것)", () => {
  const picks = pickRoadLabels([
    line("동명로", [100, 100], [160, 100]),                 // 짧다
    line("동명로", [100, 300], [700, 300]),                 // 가장 길다
    line("동명로", [100, 500], [300, 500]),
    line("밤실로4번길", [200, 600], [500, 600]),
  ], W, H);
  ok(picks.length === 2 && picks.filter((p) => p.name === "동명로").length === 1, JSON.stringify(picks));
  const d = picks.find((p) => p.name === "동명로")!;
  ok(Math.abs(d.y - 300) < 1e-6 && Math.abs(d.len - 600) < 1e-6, "가장 긴 조각을 안 골랐다");
});

test("글자 상자가 화면 안에 통째로 드는 점만 — 가장자리에서 반만 나오는 글자가 없다", () => {
  // 화면 오른쪽 끝에 걸친 긴 선: 안쪽 상자로 잘려 글자가 상자 안에 앉는다
  const picks = pickRoadLabels([line("지호로86번길", [300, 350], [1400, 350])], W, H);
  ok(picks.length === 1, "걸친 선에 글자가 안 앉았다");
  const w = [..."지호로86번길"].length * CHAR_PX, p = picks[0];
  ok(p.x - w / 2 >= 4 && p.x + w / 2 <= W - 4 && p.y >= 9 && p.y <= H - 9, `글자 상자가 화면 밖이다: ${JSON.stringify(p)}`);
  ok(p.x <= W - LABEL_MARGIN_PX, "안쪽 상자 밖에 앉았다");
  // 상자 안쪽에 드는 길이가 글자보다 한참 짧으면 안 얹는다
  ok(pickRoadLabels([line("지호로86번길", [W - 30, 350], [W + 400, 350])], W, H).length === 0, "가장자리에 겨우 걸친 선에 글자가 앉았다");
});

test("글자보다 한참 짧은 조각에는 안 얹는다", () => {
  ok(pickRoadLabels([line("동명로", [300, 300], [300 + MIN_PIECE_PX - 8, 300])], W, H).length === 0, "너무 짧은 조각에 얹었다");
  ok(pickRoadLabels([line("지호로100번길", [300, 300], [300 + 60, 300])], W, H).length === 0, "글자(8자 ≈ 92px)보다 한참 짧은데 얹었다");
});

test("결정적이다 — 입력 순서가 달라도 같은 점 · 긴 길이 먼저", () => {
  const a = [line("가로", [100, 100], [600, 100]), line("나로", [100, 200], [800, 200]), line("다로", [100, 300], [450, 300])];
  const x = JSON.stringify(pickRoadLabels(a, W, H)), y = JSON.stringify(pickRoadLabels([...a].reverse(), W, H));
  ok(x === y, "입력 순서에 결과가 흔들린다");
  ok(pickRoadLabels(a, W, H).map((p) => p.name).join() === "나로,가로,다로", "긴 길이 먼저가 아니다");
});

test("labelCollection — 점 · 이름 · 길이를 싣는다", () => {
  const fc = labelCollection([{ name: "동명로", x: 10, y: 20, len: 300.4 }], (x, y) => [x / 100, y / 100]);
  ok(fc.features.length === 1 && fc.features[0].geometry.type === "Point" && fc.features[0].properties?.len === 300, JSON.stringify(fc));
});

test("층 선언 — 도로명은 점 · 가로 · 소스는 점 소스", () => {
  const road = roadLabelLayers()[0] as { id: string; source?: string; layout?: Record<string, unknown> };
  ok(road.id === "lbl-road" && road.source === ROAD_LABEL_SRC, "소스가 점 소스가 아니다");
  ok(road.layout?.["symbol-placement"] === "point", "길을 따라 눕히는 배치가 남았다 — 남북 길에서 한글이 세로로 눕는다");
  ok(road.layout?.["text-rotation-alignment"] === "viewport", "글자가 화면 기준 가로가 아니다");
});

test("붙일 때 도로명 층을 아이콘 층(소화전) **앞에** 넣는다 — 아이콘이 먼저 자리를 잡고 글자가 비켜난다", () => {
  const calls: { id: string; before?: string }[] = [];
  const sources: string[] = [];
  const fake = {
    addSource: (id: string) => { sources.push(id); },
    addLayer: (l: { id: string }, before?: string) => { calls.push({ id: l.id, before }); },
    getLayer: (id: string) => (id === "hydrant" ? {} : undefined),
    on: () => {}, off: () => {}, getSource: () => undefined,
  };
  const off = attachRoadLabels(fake as never, 16);
  off();
  ok(sources.includes(ROAD_LABEL_SRC), "점 소스를 안 더했다");
  ok(calls.length === 1 && calls[0].id === "lbl-road" && calls[0].before === "hydrant", `아이콘 층 앞이 아니다: ${JSON.stringify(calls)}`);
});

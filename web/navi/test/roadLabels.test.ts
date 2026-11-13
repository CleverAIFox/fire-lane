/**
 * test/roadLabels.test.ts — 도로명 글자를 **화면 기준으로 이름마다 한 점**, 가로로, 아이콘 밑에.  (PLAN #73 · DECISIONS §711)
 * 순수 함수(`pickRoadLabels` · `clipPolyline`)와 층 선언을 문다. 지도 엔진의 충돌은 `scripts` 의 실측이 든다(브라우저).
 */
import { ok, test } from "./harness";
import { CHAR_PX, LABEL_MARGIN_PX, MIN_PIECE_PX, ROAD_LABEL_SRC, SETTLE_MS, UPDATE_MS, attachRoadLabels, clipPolyline, labelCollection, makeScheduler, pickRoadLabels, roadLabelLayers, type RoadPiece, type Timers } from "../src/components/roadLabels";

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


// ── 갱신 빈도 (DECISIONS §723 · A2 렉) — 주행 중 프레임마다 전 타일을 훑던 것 ──────────────────────
/** 가짜 시계 — 시험이 시간을 직접 민다 */
function fakeClock(): Timers & { advance(ms: number): void; now(): number } {
  let t = 0, id = 0;
  const q = new Map<number, { at: number; f: () => void }>();
  return {
    set(f, ms) { q.set(++id, { at: t + ms, f }); return id; },
    clear(h) { q.delete(h as number); },
    now: () => t,
    advance(ms) {
      const end = t + ms;
      for (;;) {
        const due = [...q.entries()].filter(([, v]) => v.at <= end).sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
        if (!due) break;
        q.delete(due[0]); t = due[1].at; due[1].f();
      }
      t = end;
    },
  };
}

test("스케줄러 — touch 가 천 번 와도 스로틀 안에서 run 은 한 번이다", () => {
  const c = fakeClock(); let runs = 0;
  const got = () => runs;               // `ok` 가 단언 함수라 변수를 읽으면 타입이 좁혀진다
  const s = makeScheduler(() => { runs++; }, 700, 150, c);
  for (let i = 0; i < 1000; i++) s.touch();
  ok(got() === 0, "touch 가 바로 run 을 불렀다");
  c.advance(SETTLE_MS - 1); ok(got() === 0, `멈추기 전에 run ${runs}`);
  c.advance(2); ok(got() === 1, `멈춘 뒤 run ${runs} — 천 번 touch 에 한 번이어야 한다(두 타이머가 둘 다 돌았거나 touch 마다 돌았다)`);
  c.advance(5000); ok(got() === 1, `대기 타이머가 남아 한 번 더 돌았다: ${runs}`);
});

test("스케줄러 — 3초 동안 16ms 마다 touch(추종 루프)해도 run 은 스로틀 한계(≤ 5)이고 멈추면 한 번 더 돈다", () => {
  const c = fakeClock(); let runs = 0 as number;
  const s = makeScheduler(() => { runs++; }, UPDATE_MS, SETTLE_MS, c);
  for (let t = 0; t < 3000; t += 16) { s.touch(); c.advance(16); }
  ok(runs >= 3 && runs <= 5, `3초에 run ${runs} — 프레임마다(약 190) 돌면 안 된다`);
  const before = runs;
  c.advance(SETTLE_MS + 1);
  ok(runs === before + 1, `멈춘 뒤 마지막 한 번이 없다(${before} → ${runs}) — 라벨이 옛 자리에 남는다`);
});

test("스케줄러 — cancel 하면 아무것도 안 돈다", () => {
  const c = fakeClock(); let runs = 0 as number;
  const s = makeScheduler(() => { runs++; }, 700, 150, c);
  s.touch(); s.cancel(); c.advance(5000);
  ok(runs === 0, `cancel 뒤에 run ${runs}`);
});

/** 가짜 지도 — `attachRoadLabels` 가 부르는 것만 든다. 카메라는 호출마다 움직일 수 있다 */
function fakeMap(features: unknown[] = []) {
  const on = new Map<string, Array<() => void>>(); const calls = { qsf: 0, setData: 0 };
  let lng = 126.92; const src = { setData() { calls.setData++; } };
  const m = {
    addSource() {}, addLayer() {}, getLayer: () => ({}),
    on(e: string, f: () => void) { (on.get(e) ?? on.set(e, []).get(e)!).push(f); },
    off(e: string, f: () => void) { on.set(e, (on.get(e) ?? []).filter((x) => x !== f)); },
    getSource: () => src, getCanvas: () => ({ clientWidth: 1000, clientHeight: 700 }),
    getCenter: () => ({ lng, lat: 35.15 }), getZoom: () => 17, getBearing: () => 0, getPitch: () => 60,
    querySourceFeatures() { calls.qsf++; return features; }, project: (p: number[]) => ({ x: (p[0] - lng) * 1e6, y: (p[1] - 35.15) * 1e6 }), unproject: (p: number[]) => ({ lng: p[0] / 1e6 + lng, lat: p[1] / 1e6 + 35.15 }),   // 카메라 중심 기준 px — 실제 지도처럼 카메라가 움직이면 같은 점의 화면 자리가 움직인다
  };
  return { m, calls, move(dx = 0.00004) { lng += dx; for (const f of on.get("move") ?? []) f(); for (const f of on.get("moveend") ?? []) f(); }, on };
}

test("주행 시뮬 — 3초 동안 프레임마다 jumpTo(move + moveend)해도 라벨 갱신은 스로틀 한계 안이다", () => {
  const c = fakeClock(); const fm = fakeMap();
  const off = attachRoadLabels(fm.m as never, 16, c);
  const frames = 190;                                  // 3초 · 16ms
  for (let i = 0; i < frames; i++) { fm.move(); c.advance(16); }
  ok(fm.calls.qsf >= 3 && fm.calls.qsf <= 6, `프레임 ${frames}번에 querySourceFeatures ${fm.calls.qsf}번 — 프레임마다 돌면 주행이 막힌다(종전 프레임당 1~2번)`);
  c.advance(SETTLE_MS + 1); const n = fm.calls.qsf;
  c.advance(5000); ok(fm.calls.qsf === n, `움직임이 없는데 계속 돈다: ${n} → ${fm.calls.qsf}`);
  off();
});

test("카메라도 데이터도 안 바뀌었으면 다시 안 고른다 — moveend 가 겹쳐 와도 한 번이다", () => {
  const c = fakeClock(); const fm = fakeMap();
  const off = attachRoadLabels(fm.m as never, 16, c);
  c.advance(UPDATE_MS + 1);                            // 처음 한 번
  const first = fm.calls.qsf; ok(first === 1, `처음 ${first}번`);
  for (const f of fm.on.get("moveend") ?? []) f();     // 안 움직였는데 moveend
  c.advance(5000);
  ok(fm.calls.qsf === first, `안 움직였는데 다시 골랐다: ${first} → ${fm.calls.qsf}`);
  off();
});

test("느리게 흘러가는 카메라(80px 미만)는 다시 안 고른다 — 한 프레임의 움직임은 몇 px 이다", () => {
  const c = fakeClock(); const fm = fakeMap();
  const off = attachRoadLabels(fm.m as never, 16, c);
  c.advance(UPDATE_MS + 1); const first = fm.calls.qsf;                       // 처음 한 번
  for (let i = 0; i < 60; i++) { fm.move(0.000001); c.advance(16); }          // 프레임당 1px · 60px — 문턱(80) 아래
  c.advance(5000);
  ok(fm.calls.qsf === first, `60px 흘렀는데 다시 골랐다: ${first} → ${fm.calls.qsf}`);
  fm.move(0.00005); c.advance(UPDATE_MS + SETTLE_MS + 5);                    // 50px 더 → 합 110px — 문턱을 넘는다
  ok(fm.calls.qsf === first + 1, `문턱을 넘었는데 안 골랐다: ${first} → ${fm.calls.qsf}`);
  off();
});

test("다시 골라도 이름 묶음이 같고 옛 점이 화면 안이면 setData 를 안 한다 — 워커 재타일링을 안 부른다", () => {
  const road = { type: "Feature", properties: { seg_uid: "a", road_name: "동명로" },
                 geometry: { type: "LineString", coordinates: [[126.9196, 35.15035], [126.9204, 35.15035]] } };   // 가로 800px · y 350px
  const c = fakeClock(); const fm = fakeMap([road]);
  const off = attachRoadLabels(fm.m as never, 16, c);
  c.advance(UPDATE_MS + 1);
  ok(fm.calls.setData >= 1 && fm.calls.qsf === 1, `처음 ${fm.calls.qsf}번 고르고 setData ${fm.calls.setData}번`);
  const sd: number = fm.calls.setData, q1: number = fm.calls.qsf;
  fm.move(0.0001); c.advance(UPDATE_MS + SETTLE_MS + 5);                     // 100px — 문턱을 넘어 다시 고른다
  ok(fm.calls.qsf === q1 + 1, `문턱을 넘었는데 안 골랐다: ${q1} → ${fm.calls.qsf}`);
  ok(fm.calls.setData === sd, `같은 이름 하나인데 setData 를 또 했다: ${sd} → ${fm.calls.setData}`);
  off();
});

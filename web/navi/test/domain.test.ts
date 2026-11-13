/**
 * test/domain.test.ts — 대체 접근 지점 · 경로 비교 표지 · 차종 이름 · 관제 말 (DECISIONS §214).
 */
import { FL, test, ok } from "./harness";
import { buildAdjacency, findRoute } from "../src/domain/graph";
import { alternateAccess, reachable, reachableEdges, MAX_WALK_M } from "../src/domain/access";
import { compareMarks } from "../src/domain/compare";
import { displayName, shortStation, vehicleClass } from "../src/domain/fleetName";
import {
  asNaviMsg, asOpsMsg, opsAck, opsReduce, OPS_EMPTY, shareState, opsPresent, HB_TTL_MS,
  unitStale, UNIT_STALE_MS, type Unit,
} from "../src/domain/opsProtocol";
import { distM } from "../src/domain/geo";
import opsAppSrc from "../src/OpsApp.tsx?raw";
import { liveCounts, sortUnits, unitRank, unitStatus } from "../src/domain/unitBoard";
import { choOf, isChoQuery, preparePois, searchPois, type Poi } from "../src/domain/search";

const { graph, spec } = FL;
const safe = buildAdjacency(graph, spec, false, "safe");
const fast = buildAdjacency(graph, spec, false, "fastest");

test("대체 접근 지점 — 닿는 노드 중 사건 지점에 가장 가깝고, 그리로 경로가 선다", () => {
  const nodes = [...safe.keys()].sort((a, b) => a - b);
  const from = nodes[0];
  const reach = reachable(safe, from);
  ok(reach.size > 50, `출발점에서 닿는 노드가 ${reach.size}개뿐`);
  // 닿지 **않는** 노드 하나를 사건 지점으로 삼는다
  const unreach = graph.nodes.map((_, i) => i).find((i) => !reach.has(i) && graph.nodes[i]);
  ok(unreach != null, "닿지 않는 노드가 없다 — 시험 전제가 깨졌다");
  const target = graph.nodes[unreach!];
  const a = alternateAccess(graph, safe, from, target, 5000, reach);
  ok(a, "5km 안에서도 대체 접근 지점을 못 찾았다");
  ok(reach.has(a.node), "고른 노드가 닿는 노드가 아니다");
  for (const n of reach.keys()) {
    ok(distM(graph.nodes[n], target) >= a.walkM - 1e-6, "더 가까운 닿는 노드가 있다");
  }
  ok(findRoute(graph, safe, from, a.node), "대체 접근 지점으로 경로가 안 선다");
  ok(MAX_WALK_M > 0, "도보 상한이 없다");
});

test("대체 접근 지점 — 도보 상한 밖이면 없다고 말한다", () => {
  const nodes = [...safe.keys()].sort((a, b) => a - b);
  const far: [number, number] = [graph.nodes[nodes[0]][0] + 0.2, graph.nodes[nodes[0]][1]];
  ok(alternateAccess(graph, safe, nodes[0], far, 300) === null, "20km 밖인데 접근 지점을 냈다");
});

test("도달 가능 구간은 인접리스트의 구간만 담는다", () => {
  const nodes = [...safe.keys()].sort((a, b) => a - b);
  const r = reachableEdges(graph, safe, nodes[0]);
  const blocked = graph.edges.filter((e) => e.verdict === "blocked").map((e) => e.seg_uid);
  ok(r.size > 50, `닿는 구간 ${r.size}`);
  ok(blocked.every((u) => !r.has(u)), "통행 불가 구간이 도달 가능에 들어갔다");
});

test("경로 비교 표지 — 공통 구간 · 비교 경로에만 있는 확인 구간을 실제로 센다", () => {
  const nodes = [...safe.keys()].sort((a, b) => a - b);
  let found = 0;
  for (let i = 0; i < nodes.length && found < 3; i += 41) {
    for (let j = nodes.length - 1; j > i && found < 3; j -= 67) {
      const a = findRoute(graph, safe, nodes[i], nodes[j]);
      const b = findRoute(graph, fast, nodes[i], nodes[j]);
      if (!a || !b || a.edges.map((e) => e.seg_uid).join() === b.edges.map((e) => e.seg_uid).join()) continue;
      const m = compareMarks(a, b);
      const inA = new Set(a.edges.map((e) => e.seg_uid));
      const want = b.edges.some((e) => (e.verdict === "needs_cv" || e.verdict === "unknown") && !inA.has(e.seg_uid));
      ok(!!m.checkAt === want, `확인 필요 표지 유무가 경로와 다르다 (표지 ${!!m.checkAt}, 실제 ${want})`);
      if (m.checkAt) ok(m.checkM > 0, "확인 필요 길이가 0");
      if (m.commonAt) ok(a.edges[0].seg_uid === b.edges[0].seg_uid, "첫 구간이 다른데 공통 구간을 냈다");
      found++;
    }
  }
  ok(found > 0, "갈리는 경로 쌍을 하나도 못 찾았다");
});

test("차종 이름 · 그림 종류", () => {
  ok(displayName("펌프차 (중형)") === "중형 펌프차", displayName("펌프차 (중형)"));
  ok(displayName("구급차") === "구급차", "괄호 없는 이름을 바꿨다");
  ok(vehicleClass("굴절형 사다리차 27m") === "articulated", "굴절");
  ok(vehicleClass("직진형 사다리차 53m") === "ladder", "사다리");
  ok(vehicleClass("물탱크차 (대형)") === "tanker", "물탱크");
  ok(vehicleClass("구급차") === "ambulance", "구급");
  ok(vehicleClass("구조차") === "rescue", "구조");
  ok(vehicleClass("조연차") === "light", "조연");
  ok(vehicleClass("화학차") === "chem", "화학");
  ok(vehicleClass("펌프차 (중형)") === "pump", "펌프");
});

test("관제 말 — 모양이 틀린 메시지는 버리고, 공유는 확인을 눌러야 확인이다", () => {
  ok(asNaviMsg({ t: "share", unit: "u" }) === null, "필드 빠진 공유를 받았다");
  ok(asNaviMsg({ t: "zzz", unit: "u" }) === null, "모르는 종류를 받았다");
  ok(asOpsMsg({ t: "ack", shareId: "s" }) === null, "unit 없는 확인을 받았다");
  const st1 = asNaviMsg({ t: "state", unit: "u1", at: 1, routeRev: 1, route: [[1, 2], [3, 4]],
                          vehicle: "펌프차", status: "safe", title: "안내" })!;
  let s = opsReduce(OPS_EMPTY, st1, 100);
  ok(s.units.u1.route?.length === 2, "경로를 못 받았다");
  const st2 = asNaviMsg({ t: "state", unit: "u1", at: 2, routeRev: 1, vehicle: "펌프차" })!;
  s = opsReduce(s, st2, 200);
  ok(s.units.u1.route?.length === 2, "같은 판 번호인데 경로를 잃었다");
  const sh = asNaviMsg({ t: "share", unit: "u1", shareId: "s1", kind: "bottleneck", at: 5, text: "x" })!;
  s = opsReduce(s, sh, 300);
  s = opsReduce(s, sh, 301);
  ok(s.feed.length === 1, "같은 공유가 두 줄이 됐다");
  ok(shareState(0, null, 1000) === "awaiting", "확인 전인데 대기가 아니다");
  s = opsAck(s, "s1", 400);
  ok(s.feed[0].ackedAt === 400, "확인이 안 박혔다");
  ok(shareState(0, 400, 1000) === "acked", "확인 뒤인데 확인이 아니다");
  ok(shareState(0, null, 10 ** 6) === "failed", "시간이 지났는데 실패가 아니다");
  ok(opsPresent(1000, 1000 + HB_TTL_MS - 1) && !opsPresent(1000, 1000 + HB_TTL_MS + 1), "심장박동 판정");
  s = opsReduce(s, { t: "bye", unit: "u1" }, 500);
  ok(!s.units.u1, "떠난 차가 남았다");
});

test("회색 사유 — 발행 그래프의 회색 구간은 전부 사람 말 사유를 갖는다 (§215-2)", async () => {
  const { GRAY_REASON, grayReason } = await import("../src/ui/verdictMeaning");
  const gray = graph.edges.filter((e) => e.verdict === "unknown");
  ok(gray.length > 0, "회색 구간이 0 — 시험 전제가 깨졌다");
  for (const e of gray) {
    const r = grayReason(e);
    ok(r && e.unknown_reason && GRAY_REASON[e.unknown_reason], `${e.seg_uid} 사유 ${e.unknown_reason} 에 문구가 없다`);
    ok(!/\d\.\dm/.test(r.long), "폭 문턱 숫자를 박았다 — 정본은 seg/params.py");
  }
  ok(grayReason({ verdict: "clear", unknown_reason: "no_cctv_band" }) === null, "회색이 아닌데 사유를 냈다");
});

test("건물은 땅에서 선다 — 지형을 안 켠 지도에서 해발고(z)를 밑면으로 쓰지 않는다 (§216-2)", async () => {
  const { baseLayers } = await import("../src/components/layers");
  const ls = baseLayers(graph.style);
  const ext = ls.filter((l) => l.type === "fill-extrusion");
  ok(ext.length === 1, `압출 레이어 ${ext.length}개 — 같은 건물을 두 번 압출하면 그리기가 두 배다`);
  const paint = JSON.stringify((ext[0] as { paint?: unknown }).paint);
  ok(!paint.includes('"z"'), "건물 압출이 z(해발 지반고)를 쓴다 — 지형이 없으면 건물이 16m 뜬다");
});

test("경로 주변 사정 — 경로 위 거리 순 · 종류별 문턱 안 · 연속 과속방지턱은 하나로 (§216-3)", async () => {
  const { routeHazards, hazardSummary, NEAR_M } = await import("../src/domain/context");
  const { distM: d } = await import("../src/domain/geo");
  const mk = (kind: string, at: [number, number]) =>
    ({ type: "Feature", properties: { kind }, geometry: { type: "Point", coordinates: at } }) as GeoJSON.Feature;
  // 동서 직선 200m 경로
  const a: [number, number] = [126.925, 35.15], b: [number, number] = [126.9272, 35.15];
  const plan = { coords: [a, b] };
  ok(Math.abs(d(a, b) - 200) < 5, "시험 전제 — 경로 길이");
  const off = (m: number) => m / 110_540;             // 북쪽으로 m
  const ctx = { type: "FeatureCollection", features: [
    mk("speedbump", [126.9255, 35.15 + off(5)]),       // 경로 위
    mk("speedbump", [126.9257, 35.15 + off(3)]),       // 18m 뒤 — 하나로 센다
    mk("speedbump", [126.9265, 35.15 + off(40)]),      // 40m 밖 — 안 센다
    mk("speedcam", [126.9268, 35.15 + off(20)]),
    mk("child_zone", [126.926, 35.15 + off(120)]),
  ] } as GeoJSON.FeatureCollection;
  const hs = routeHazards(plan, ctx);
  ok(hs.map((h) => h.kind).join() === "speedbump,child_zone,speedcam", `순서 ${hs.map((h) => h.kind).join()}`);
  ok(hs.every((h, i) => i === 0 || hs[i - 1].atM <= h.atM), "경로 위 거리 순이 아니다");
  ok(NEAR_M.speedbump < NEAR_M.child_zone, "문턱 전제");
  ok(hazardSummary(hs) === "과속방지턱 1 · 단속카메라 1 · 보호구역 시설 1", `요약 ${hazardSummary(hs)}`);
  ok(routeHazards(plan, null).length === 0, "주변 사정 파일이 없는데 무언가를 냈다");
});

// ── 초성 검색 (DECISIONS §224-5) ─────────────────────────────
// ★ 관제요원은 신고자 말을 받아치면서 지도를 본다. `ㄷㅁㄷㅎㅈㅂㅈㅅㅌ` 가
//   `동명동행정복지센터` 로 가야 한다. **인스턴스가 아니라 경계를 본다** —
//   넓히면 `ㄱ` 한 자가 색인 전체를 물어와 잘 되던 검색이 나빠진다.
test("초성으로 찾는다 — 전부 초성일 때만", () => {
  const mk = (name: string, over: Partial<Poi> = {}): Poi => ({
    name, cat: "", sub: "", addr: "", alt: "", src: "store",
    point: [0, 0], cho: choOf(name), ...over,
  });
  const pois: Poi[] = [
    mk("동명동행정복지센터", { src: "civil", cat: "읍면동" }),
    mk("광주서석초등학교", { src: "civil", cat: "초등학교" }),
    mk("그레이스 원룸", { src: "build", sub: "주택" }),
    mk("동명동 김밥천국"),
  ];

  ok(choOf("동명동행정복지센터") === "ㄷㅁㄷㅎㅈㅂㅈㅅㅌ", `초성 ${choOf("동명동행정복지센터")}`);
  ok(choOf("GS25 편의점") === "GS25 ㅍㅇㅈ", "한글 아닌 글자는 그대로 둬야 한다");

  ok(isChoQuery("ㄷㅁㄷ"), "전부 초성인데 아니라고 한다");
  ok(!isChoQuery("동ㅁㄷ"), "완성 음절이 섞였는데 초성 질의로 본다");
  ok(!isChoQuery("gs25"), "영문은 초성 질의가 아니다");

  const a = searchPois(pois, "ㄷㅁㄷㅎㅈ");
  ok(a.length === 1 && a[0].name === "동명동행정복지센터", `초성 검색 실패: ${a.map((h) => h.name).join(",")}`);

  // 공백이 섞인 이름도 — norm 이 공백을 지운다
  ok(searchPois(pois, "ㄱㄹㅇㅅㅇㄹ")[0]?.name === "그레이스 원룸", "공백 든 이름을 초성으로 못 찾는다");

  // ★ 경계 — 완성 음절 질의는 종전 그대로 동작해야 한다(회귀 방지)
  const b = searchPois(pois, "동명동");
  ok(b.length === 2, `완성 음절 검색이 달라졌다: ${b.length}`);
  ok(b[0].src === "civil", "같은 점수면 관공서가 앞서야 한다");

  // ★ 초성 질의가 **이름 말고 다른 칸**을 훑지 않는가. `ㅇㅁㄷ`(읍면동)은
  //   유형 칸에만 있으므로 아무것도 안 나와야 한다 — 문이 넓어지면 여기가 운다.
  ok(searchPois(pois, "ㅇㅁㄷ").length === 0, "초성 질의가 이름 밖을 훑는다");
});


// ── 2026-10-12 (DECISIONS §483) ────────────────────────────────────
//   `navicov` 가 센 넷을 여기 붙인다 — 이 파일이 이미 그 세 모듈의 **옆
//   함수들**을 들고 있어서, 새 파일을 세우면 같은 주제가 두 군데로 갈린다.

test("안전센터 이름 줄이기 — 발행물 세 이름이 다 줄고, 빈 이름이 안 나온다", () => {
  ok(shortStation("동부소방서_광주-지산-119 안전센터") === "지산119안전센터",
    `줄인 꼴이 틀렸다 — ${shortStation("동부소방서_광주-지산-119 안전센터")}`);
  // ★ 꼴이 안 맞는 이름은 **그대로 둔다.** 빈 글자를 내면 화면에 이름이 사라진다
  ok(shortStation("동부소방서") === "동부소방서", "꼴이 다른 이름을 지웠다");
  ok(shortStation("") === "", "빈 이름에서 던진다");
  for (const raw of ["동부소방서_광주-지산-119 안전센터", "동부소방서_광주-대인-119 안전센터",
    "동부소방서"]) {
    const got = shortStation(raw);
    ok(got.length > 0, `${raw} 가 빈 글자가 됐다`);
    ok(!/[-\s]/.test(got), `${raw} → ${got} 에 구분자가 남았다`);
  }
});

test("관제 — 소식이 끊긴 차를 **문턱으로** 가른다", () => {
  const u = { unit: "U1", heardAt: 1_000 } as Unit;
  ok(!unitStale(u, 1_000), "방금 들은 차를 끊겼다고 한다");
  ok(!unitStale(u, 1_000 + UNIT_STALE_MS), "문턱 그 자리에서 끊겼다고 한다 — 경계가 포함이다");
  ok(unitStale(u, 1_000 + UNIT_STALE_MS + 1), "문턱을 넘었는데 살아 있다고 한다");
  // ★ 시계가 뒤로 갔을 때(음수 경과) 끊겼다고 하지 않는다 — 화면이 깜빡인다
  ok(!unitStale(u, 500), "시계가 뒤로 가자 끊겼다고 한다");
  ok(UNIT_STALE_MS > HB_TTL_MS / 10, "문턱이 심장소리보다 터무니없이 짧다");
});

test("POI 준비 — 점이 아니거나 이름이 없는 것은 **안 싣는다**", () => {
  const fc = {
    type: "FeatureCollection",
    features: [
      { type: "Feature", properties: { name: "가게", cat: "상점", src: "store" },
        geometry: { type: "Point", coordinates: [126.9, 35.15] } },
      // 이름이 없다 — 검색창에 빈 줄이 뜬다
      { type: "Feature", properties: { cat: "상점" },
        geometry: { type: "Point", coordinates: [126.9, 35.15] } },
      // 점이 아니다 — 좌표를 점으로 읽으면 엉뚱한 자리로 간다
      { type: "Feature", properties: { name: "길" },
        geometry: { type: "LineString", coordinates: [[126.9, 35.15], [126.91, 35.15]] } },
      // 모르는 출처는 기본값으로 접는다
      { type: "Feature", properties: { name: "청사", src: "엉뚱" },
        geometry: { type: "Point", coordinates: [126.9, 35.15] } },
    ],
  } as unknown as GeoJSON.FeatureCollection;
  const got = preparePois(fc);
  ok(got.length === 2, `${got.length}건을 실었다 — 기대 2`);
  ok(got.map((p) => p.name).sort().join() === "가게,청사", "실은 것이 다르다");
  ok(got.every((p) => ["store", "civil", "build"].includes(p.src)),
    "선언에 없는 출처가 실렸다");
  // ★ 빈 자료에서 던지지 않는다
  ok(preparePois({ type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection)
    .length === 0, "빈 자료에서 무언가를 만든다");
});

test("회색 사유 — GRAY_REASON 과 web/config.js 의 reason 키 집합이 같다 (감사 N1)", async () => {
  const { GRAY_REASON } = await import("../src/ui/verdictMeaning");
  // ★ `node:fs` 를 안 쓴다 — vite 가 빌드 시각에 문자열로 준다(dataBase.test 와 같은 이유).
  const files = import.meta.glob("../../config.js", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
  const src = Object.values(files)[0] ?? "";
  const blk = src.slice(src.indexOf("reason: {") + "reason: {".length);
  const body = blk.slice(0, blk.indexOf("\n  },"));
  // 옛 키(`no_cctv`)는 재발행 전 산출물용으로 config.js 만 남긴다 — 정본 집합이 아니다
  const LEGACY = new Set(["no_cctv"]);
  const cfg = [...body.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/^\s*([a-z_]+)\s*:/gm)]
    .map((m) => m[1]).filter((k) => !LEGACY.has(k)).sort();
  const gr = Object.keys(GRAY_REASON).sort();
  ok(cfg.length > 5, `config.js 에서 사유 키를 못 읽었다 — ${cfg.join(",")}`);
  ok(JSON.stringify(cfg) === JSON.stringify(gr),
    `사유 키 집합이 어긋난다 — config.js ${cfg.join(",")} / GRAY_REASON ${gr.join(",")}`);
});


// ── 관제 상황판 순서 (DECISIONS §726 · B3) ─────────────────────────────────────────────────
/** 합성 차량 — `ago` 초 전에 마지막으로 들었고(5초 넘으면 끊김) `remainM` 이 있으면 나가 있는 차 */
const NOW = 1_000_000;
const unit = (name: string, ago: number, remainM: number | null, demo = false): Unit => ({
  unit: name, heardAt: NOW - ago * 1000, route: null, routeRev: 0,
  last: { t: "state", unit: name, at: NOW, vehicle: name, station: null, incident: null, pos: null, brg: 0, status: "safe", title: "", remainM, etaText: null, routeRev: 0, demo },
});

test("상황판 — 연결된 순서가 끊김 · 출동 중 · 대기여도 출동 중이 맨 위다(끊김은 색이 할 일이지 순서가 아니다)", () => {
  const lostIdle = unit("A-끊김", 30, null), live = unit("B-출동", 1, 1800), idle = unit("C-대기", 1, null);
  const board = sortUnits([lostIdle, live, idle], NOW);
  ok(board.map((u) => u.unit).join() === "B-출동,C-대기,A-끊김", `순서 ${board.map((u) => u.unit).join()}`);
});

test("상황판 — 끊겼지만 나가 있던 차는 대기보다 위다(길을 잃었을 수 있다) · 나가 있지 않던 끊김은 맨 아래다", () => {
  const lostWas = unit("A", 30, 900), lostIdle = unit("B", 30, null), idle = unit("C", 1, null), live = unit("D", 1, 500);
  ok([lostWas, lostIdle, idle, live].map((u) => unitRank(u, NOW)).join() === "1,3,2,0", "순위표가 다르다");
  ok(sortUnits([lostIdle, idle, lostWas, live], NOW).map((u) => u.unit).join() === "D,A,C,B", "정렬이 순위표와 다르다");
});

test("상황판 — 같은 순위 안은 이름순이라 남은 거리가 변해도 행이 안 뒤바뀐다", () => {
  const a = unit("Z", 1, 100), b = unit("A", 1, 9000);
  ok(sortUnits([a, b], NOW).map((u) => u.unit).join() === "A,Z", "이름순이 아니다");
  const a2 = unit("Z", 1, 9999), b2 = unit("A", 1, 50);         // 남은 거리가 뒤집혀도
  ok(sortUnits([a2, b2], NOW).map((u) => u.unit).join() === "A,Z", "거리에 따라 행이 뒤바뀐다 — 누를 수가 없다");
});

test("상황판 — 입력을 안 바꾼다 · 끊김 판정은 시계에 따른다", () => {
  const xs = [unit("A", 30, null), unit("B", 1, 1)]; const before = xs.map((u) => u.unit).join();
  sortUnits(xs, NOW); ok(xs.map((u) => u.unit).join() === before, "입력 배열이 바뀌었다");
  ok(unitStatus(xs[1], NOW) === "dispatching" && unitStatus(xs[1], NOW + UNIT_STALE_MS + 1000) === "lost", "시계가 흘러도 끊김이 안 된다");
});

test("상황판 배선 — 차량 목록은 정렬된 board 로 그린다(되돌리면 연결 순서로 돌아가 끊김이 맨 위가 된다)", () => {
  ok(/const board = useMemo\(\(\) => sortUnits\(units, now\)/.test(opsAppSrc), "OpsApp 이 sortUnits 로 board 를 안 만든다");
  ok(/\{board\.map\(\(u\) => \{/.test(opsAppSrc), "상황판이 board 가 아니라 정렬 안 된 목록을 그린다");
  ok(!/\{units\.map\(\(u\) => \{\s*const stale = unitStale/.test(opsAppSrc), "상황판 행이 옛 목록(units)으로 돌아갔다");
});

test("사건 검색 — 자료가 실렸는데 검색어에 맞는 것이 없으면 「결과 없음」 을 말한다(침묵이 아니라 · B5)", () => {
  const m = /\{data && q\.trim\(\) && hits\.length === 0 && <div[^>]*>결과 없음<\/div>\}/.exec(opsAppSrc);
  ok(m != null, "OpsApp 에 빈 결과 줄이 없다 — 검색어를 쳤는데 아무 말이 없다");
  ok(/hits: PoiHit\[\] = useMemo\(\(\) => \(q\.trim\(\)\.length >= 1 \? searchPois/.test(opsAppSrc), "hits 의 정의가 바뀌어 빈 결과 줄의 조건과 어긋날 수 있다");
  const pois = preparePois({ type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection);
  ok(searchPois(pois, "존재하지않는이름").length === 0, "색인이 비었는데 결과가 났다");
});


// ── 시연 / 실제 (DECISIONS §745 · ⓲I-C2 · 안전 결함) ───────────────────────────────────────
const stateMsg = (extra: Record<string, unknown>) => ({ t: "state", unit: "u", at: 1, routeRev: 0, ...extra });

test("시연 — 메시지가 시연 여부를 싣고 받는 쪽이 읽는다 · 칸이 없으면 실제로 읽는다", () => {
  const on = asNaviMsg(stateMsg({ demo: true })), off = asNaviMsg(stateMsg({ demo: false })), none = asNaviMsg(stateMsg({}));
  ok(on?.t === "state" && on.demo === true, "demo:true 를 못 읽었다");
  ok(off?.t === "state" && off.demo === false, "demo:false 를 못 읽었다");
  ok(none?.t === "state" && none.demo === false, "칸이 없으면 false 여야 한다");
  ok(asNaviMsg(stateMsg({ demo: "true" }))?.t === "state" && (asNaviMsg(stateMsg({ demo: "true" })) as { demo: boolean }).demo === false, "문자열 true 를 시연으로 믿었다 — 엄격히 불리언 true 만");
});

test("시연 — 관제의 「출동 중 N대」 에 시연 차량이 안 센다 · 따로 센다", () => {
  const us = [unit("실제1", 1, 1000), unit("시연1", 1, 800, true), unit("시연끊김", 30, 800, true), unit("실제대기", 1, null)];
  const c = liveCounts(us, NOW);
  ok(c.real === 2 && c.demo === 1, `실제 ${c.real} · 시연 ${c.demo} (끊긴 시연은 안 센다)`);
});

test("시연 — 상황판에서 시연 차량은 실제 뒤에 온다(출동 중이어도)", () => {
  const b = sortUnits([unit("A-시연출동", 1, 500, true), unit("B-실제대기", 1, null), unit("C-실제끊김", 30, null)], NOW);
  ok(b.map((u) => u.unit).join() === "B-실제대기,C-실제끊김,A-시연출동", `순서 ${b.map((u) => u.unit).join()}`);
});

test("시연 — 관제 화면이 시연을 호박색으로 그리고 합계에서 뺀다(소스 계약)", () => {
  ok(/liveCounts\(units, now\)/.test(opsAppSrc), "OpsApp 이 liveCounts 로 센다 — 시연이 합산될 수 있다");
  ok(/u\.last\.demo && !stale/.test(opsAppSrc) && /D\.warn/.test(opsAppSrc), "상황판 행이 시연을 호박색으로 안 가른다");
  ok(!/units\.filter\(\(u\) => !unitStale\(u, now\)\)\.length/.test(opsAppSrc), "옛 합산(시연 포함)이 돌아왔다");
});

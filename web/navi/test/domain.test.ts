/**
 * test/domain.test.ts — 대체 접근 지점 · 경로 비교 표지 · 차종 이름 · 관제 말 (DECISIONS §214).
 */
import { FL, test, ok } from "./harness";
import { buildAdjacency, findRoute } from "../src/domain/graph";
import { alternateAccess, reachable, reachableEdges, MAX_WALK_M } from "../src/domain/access";
import { compareMarks } from "../src/domain/compare";
import { displayName, vehicleClass } from "../src/domain/fleetName";
import {
  asNaviMsg, asOpsMsg, opsAck, opsReduce, OPS_EMPTY, shareState, opsPresent, HB_TTL_MS,
} from "../src/domain/opsProtocol";
import { distM } from "../src/domain/geo";

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

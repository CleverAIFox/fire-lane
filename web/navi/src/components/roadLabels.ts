/**
 * components/roadLabels.ts — **도로명 글자를 화면 기준으로 한 번씩만 얹는다.**  (PLAN #73 · DECISIONS §711)
 *
 * IN    `segments` 소스의 도로명 선(`querySourceFeatures`) · 화면 크기 · 지도의 투영
 * OUT   `road_labels` 소스(점 · 도로명 · 화면 길이) — `lbl-road` 층이 그린다
 * PARAM `LABEL_MARGIN_PX` · `CHAR_PX` · `MIN_PIECE_PX` · `UPDATE_MS`
 * 밖    **글자끼리 · 아이콘과의 충돌은 안 가린다** — 그것은 지도 엔진(`lbl-road` 의 충돌 규칙)이 한다. 여기가 정하는 것은 「어느 도로명을 **어디에 한 번** 얹는가」 하나다.
 *       **HTML 마커(출발 · 사건 핀)와는 못 피한다** — 엔진의 충돌 색인 밖이다.
 *
 * ── 왜 선을 따라 쓰지 않나 ───────────────────────────────────
 * `symbol-placement: "line"` 은 글자를 **길을 따라 눕힌다**(`text-rotation-alignment` 기본이 지도 기준). 남북으로 뻗은 길에는 한글이 **90도 누워 세로로** 읽힌다 —
 * 차량 화면에서 못 읽는다(관제 줌 셋 실측 · 오른쪽 · DECISIONS §711). 점 배치(`point`)는 늘 가로다.
 * 또 한 도로가 여러 구간 · 여러 타일로 쪼개져 **구간마다** 글자가 얹혀 같은 이름이 한 화면에 둘 · 셋 떴다(동명로 넷). 그리고 가장자리에서는 엔진이 화면 밖 100px 까지를
 * 허용해 글자가 **반만** 나왔다. 셋 다 「화면 기준으로 이름마다 한 점을 고른다」로 풀린다 — 이 파일이 그 고르기다.
 */
import type { GeoJSONSource, LayerSpecification, Map as MapLibreMap } from "maplibre-gl";
import { MAP } from "../ui/tokens";
import { FONT, Z } from "./layers";

export const ROAD_LABEL_SRC = "road_labels";
/** 화면 가장자리에서 이만큼(px) 안쪽의 상자 안에서만 고른다 — 글자가 가장자리에 걸려 반만 나오지 않게. */
export const LABEL_MARGIN_PX = 24;
/** 글자 한 자의 폭 근사(px · 11px 글자 — 한글은 한 자가 거의 한 칸이다). */
export const CHAR_PX = 11.5;
/** 이 화면 길이(px) 아래의 도로 조각에는 글자를 안 얹는다 — 글자가 길보다 길면 어느 길의 이름인지 못 읽는다. */
export const MIN_PIECE_PX = 32;
/** …그리고 조각 길이가 글자 폭의 이 비율 아래면 안 얹는다. ★ 2026-11-13(DECISIONS §751): 48px · 0.7 → 32px · 0.5 — 줌 16 에서 폰 42% · 관제 31% 가 빠지던 것을 31% · 19% 로 줄인다(번길의 짧은 조각). 더 낮추면 글자가 길보다 훨씬 길어져 어느 길의 이름인지 못 읽는다. */
export const MIN_PIECE_RATIO = 0.5;
/** 움직임이 멎은 뒤 다시 고르는 간격(ms). 주행 중 카메라가 계속 움직여도 이 간격으로만 고른다. */
export const UPDATE_MS = 700;
/** 움직임이 멈춘 뒤 마지막 한 번까지의 간격(ms) */
export const SETTLE_MS = 150;
/** 카메라가 이만큼(화면 px) · 줌 0.25 · 방위 20° · 기울기 10° 움직여야 다시 고른다 — 조금 움직인 것은 옛 점이 그대로 맞다 */
export const MOVE_PX = 80;

/**
 * `lbl-road` 층 — **점 · 가로 · 아이콘 층 밑.** (DECISIONS §711 · PLAN #73)
 *  · 층 순서가 곧 자리 잡는 순서다 — 위 층이 먼저 잡는다. 도로명이 소화전 · CCTV 위에 있었을 때 글자가 먼저 잡혀 아이콘이 그 위에 겹쳤다. 이제 아이콘 층(`allow-overlap` 이어도
 *    충돌 색인에는 들어간다)이 먼저 잡고 글자는 **비켜난다**(`attachRoadLabels` 가 이 층을 `hydrant` **앞에** 넣는다) — 소화전 · CCTV 는 위치가 뜻이고 도로명은 다른 글자로 대체된다(사람이 정했다).
 *  · `symbol-placement: "line"` 을 버렸다 — 길을 따라 눕히면 남북 길에서 한글이 세로로 누웠다. 점 + 가로(`viewport`)다.
 *  · `symbol-sort-key` — 화면에서 **긴 길이 먼저** 자리를 잡는다(`k` = −길이).
 * 이 층은 **지연 청크**(이 파일)에 산다 — 진입 청크 래칫(`naviweight` `ENTRY_KB`)이 첫 화면에 안 필요한 바이트를 못 받는다. `tools/uicheck.py` 는 이 파일도 층 명세로 읽는다(`LAYER_FILES`).
 */
export function roadLabelLayers(): LayerSpecification[] {
  return [
    { id: "lbl-road", type: "symbol", source: ROAD_LABEL_SRC, minzoom: Z.road,
      layout: {
        "symbol-placement": "point", "text-field": ["get", "name"],
        "text-font": FONT, "text-size": 11, "text-rotation-alignment": "viewport",
        "symbol-sort-key": ["get", "k"] as never,
      },
      paint: { "text-color": MAP.roadLabel, "text-halo-color": MAP.roadLabelHalo, "text-halo-width": 1.6 } },
  ];
}

export type Pt = [number, number];
export interface RoadPiece { name: string; px: Pt[] }
export interface RoadLabelPick { name: string; x: number; y: number; len: number }

/** 선분 하나를 상자로 자른다(Liang–Barsky). 안 걸치면 null. */
function clipSeg(a: Pt, b: Pt, x0: number, y0: number, x1: number, y1: number): [Pt, Pt] | null {
  let t0 = 0, t1 = 1;
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const p = [-dx, dx, -dy, dy], q = [a[0] - x0, x1 - a[0], a[1] - y0, y1 - a[1]];
  for (let i = 0; i < 4; i++) {
    if (p[i] === 0) { if (q[i] < 0) return null; continue; }
    const r = q[i] / p[i];
    if (p[i] < 0) { if (r > t1) return null; if (r > t0) t0 = r; }
    else { if (r < t0) return null; if (r < t1) t1 = r; }
  }
  return [[a[0] + t0 * dx, a[1] + t0 * dy], [a[0] + t1 * dx, a[1] + t1 * dy]];
}

/** 꺾은선을 상자로 자른다 — 이어지는 조각마다 한 줄. 순수. */
export function clipPolyline(px: Pt[], box: [number, number, number, number]): Pt[][] {
  const out: Pt[][] = [];
  let cur: Pt[] = [];
  for (let i = 0; i + 1 < px.length; i++) {
    const s = clipSeg(px[i], px[i + 1], box[0], box[1], box[2], box[3]);
    if (!s) { if (cur.length) { out.push(cur); cur = []; } continue; }
    if (!cur.length) cur.push(s[0]);
    else if (Math.hypot(cur[cur.length - 1][0] - s[0][0], cur[cur.length - 1][1] - s[0][1]) > 0.5) { out.push(cur); cur = [s[0]]; }
    cur.push(s[1]);
    if (s[1][0] !== px[i + 1][0] || s[1][1] !== px[i + 1][1]) { out.push(cur); cur = []; }
  }
  if (cur.length) out.push(cur);
  return out;
}

const lenOf = (l: Pt[]) => l.reduce((a, p, i) => (i ? a + Math.hypot(p[0] - l[i - 1][0], p[1] - l[i - 1][1]) : 0), 0);

/** 선 위에서 시작점으로부터 `d`px 떨어진 점. */
function pointAt(l: Pt[], d: number): Pt {
  let acc = 0;
  for (let i = 1; i < l.length; i++) {
    const s = Math.hypot(l[i][0] - l[i - 1][0], l[i][1] - l[i - 1][1]);
    if (acc + s >= d && s > 0) { const t = (d - acc) / s; return [l[i - 1][0] + t * (l[i][0] - l[i - 1][0]), l[i - 1][1] + t * (l[i][1] - l[i - 1][1])]; }
    acc += s;
  }
  return l[l.length - 1];
}

/**
 * 도로명마다 **한 점**을 고른다. 순수 함수.
 *  - 이름이 같은 조각은 하나로 본다 — 안쪽 상자 안에서 **화면 길이가 가장 긴** 조각을 쓴다(중복 없음).
 *  - 글자 상자(가로 `이름 길이 × CHAR_PX`)가 **화면 안**(4px 여유)에 통째로 드는 점만 쓴다(반만 나오는 글자 없음).
 *  - 조각이 글자보다 많이 짧으면(`MIN_PIECE_PX` · 글자 폭의 `MIN_PIECE_RATIO`) 안 얹는다.
 * 결과는 길이 큰 순 · 같으면 이름순 — 결정적이다.
 */
export function pickRoadLabels(pieces: RoadPiece[], W: number, H: number, margin = LABEL_MARGIN_PX): RoadLabelPick[] {
  const box: [number, number, number, number] = [margin, margin, W - margin, H - margin];
  const best = new Map<string, { piece: Pt[]; len: number }>();
  for (const pc of pieces) {
    if (!pc.name || pc.px.length < 2) continue;
    for (const c of clipPolyline(pc.px, box)) {
      const len = lenOf(c);
      const cur = best.get(pc.name);
      if (!cur || len > cur.len) best.set(pc.name, { piece: c, len });
    }
  }
  const out: RoadLabelPick[] = [];
  for (const [name, { piece, len }] of best) {
    const w = [...name].length * CHAR_PX;
    if (len < Math.max(MIN_PIECE_PX, w * MIN_PIECE_RATIO)) continue;
    for (const f of [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8]) {
      const [x, y] = pointAt(piece, len * f);
      if (x - w / 2 >= 4 && x + w / 2 <= W - 4 && y - 9 >= 4 && y + 9 <= H - 4) { out.push({ name, x, y, len }); break; }
    }
  }
  return out.sort((a, b) => b.len - a.len || (a.name < b.name ? -1 : 1));
}

export function labelCollection(picks: RoadLabelPick[], unproject: (x: number, y: number) => [number, number]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: picks.map((p) => ({ type: "Feature", properties: { name: p.name, len: Math.round(p.len), k: -Math.round(p.len) },
                                  geometry: { type: "Point", coordinates: unproject(p.x, p.y) } })),
  };
}

/** 타이머 쌍 — 시험이 가짜를 꽂는다 */
export interface Timers { set(f: () => void, ms: number): unknown; clear(h: unknown): void }
const REAL: Timers = { set: (f, ms) => setTimeout(f, ms), clear: (h) => clearTimeout(h as ReturnType<typeof setTimeout>) };

/**
 * 갱신 스케줄러 — **움직이는 동안 `throttleMs` 에 한 번 + 멈춘 뒤 `settleMs` 에 한 번.** 순수하다(타이머를 꽂는다). (DECISIONS §723 · A2 렉)
 *
 * ★ 종전에는 `moveend` 가 `update` 를 **바로** 불렀다. MapLibre 의 `jumpTo` 는 호출마다 `moveend` 를 동기로 내고 내비의 카메라 추종 루프가 매 프레임 `jumpTo` 를 부르므로
 *   **매 프레임** 전 타일 `querySourceFeatures` + 투영이 돌았다(프레임 두 배 — 대기 타이머도 안 지웠다). 이벤트는 전부 `touch()` 로 오고, 갱신은 여기서만 정해진다.
 * ★ `touch` 가 몇 번 오든 `throttleMs` 안에 `run` 은 한 번이다(첫 `touch` 가 시계를 건다 — 이후 `touch` 가 시계를 안 민다). 멈추면(`settleMs` 동안 `touch` 없음) 마지막 자리로 한 번 더 돈다.
 */
export function makeScheduler(run: () => void, throttleMs: number, settleMs: number, t: Timers = REAL) {
  let a: unknown, b: unknown;
  const fire = () => {
    if (a !== undefined) { t.clear(a); a = undefined; }
    if (b !== undefined) { t.clear(b); b = undefined; }
    run();
  };
  return {
    touch() { if (a === undefined) a = t.set(fire, throttleMs); if (b !== undefined) t.clear(b); b = t.set(fire, settleMs); },
    now: fire,
    cancel() { if (a !== undefined) t.clear(a); if (b !== undefined) t.clear(b); a = b = undefined; },
  };
}

/** 지도에 붙인다 — 소스와 `lbl-road` 층을 **아이콘 층 앞에** 넣고, 움직임이 있을 때마다(`UPDATE_MS` 간격으로) 다시 고른다. 떼는 함수를 돌려준다. 아이콘 층이 이미 올라 있어야 한다. */
export function attachRoadLabels(m: MapLibreMap, minZoom: number, timers: Timers = REAL): () => void {
  const empty: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
  m.addSource(ROAD_LABEL_SRC, { type: "geojson", data: empty });
  for (const L of roadLabelLayers()) m.addLayer(L, m.getLayer("hydrant") ? "hydrant" : undefined);   // 아이콘 층 **앞** — 아이콘이 먼저 자리를 잡는다
  // ★ 다시 고르는 것은 **비싸다**(전 타일 `querySourceFeatures` + 투영 + `setData` 가 워커 재타일링과 심볼 재배치를 부른다 — DECISIONS §723). 그래서 셋을 건너뛴다:
  //   ① 카메라가 `MOVE_PX` · 줌 0.25 · 방위 20° · 기울기 10° 를 안 넘었고 데이터(구간 타일)가 안 늘었으면 안 고른다 — 주행 중 한 프레임의 움직임은 몇 px 이다
  //   ② 골라 보니 이름 묶음이 전과 같고 옛 점이 아직 화면 안이면 `setData` 를 안 한다(옛 점이 지리 좌표라 그대로 맞다)
  let dirty = true, last: { c: [number, number]; px: [number, number]; z: number; b: number; p: number; w: number; h: number } | undefined;
  let prev: GeoJSON.Feature<GeoJSON.Point>[] = [];
  const moved = () => {
    if (dirty || !last) return true;
    const cv = m.getCanvas(), q = m.project(last.c);
    const db = Math.abs(((m.getBearing() - last.b + 540) % 360) - 180);       // 방위 차(0~180°) — 360° 를 건너는 것도 맞다
    return Math.hypot(q.x - last.px[0], q.y - last.px[1]) >= MOVE_PX || Math.abs(m.getZoom() - last.z) >= 0.25
      || db >= 20 || Math.abs(m.getPitch() - last.p) >= 10 || cv.clientWidth !== last.w || cv.clientHeight !== last.h;
  };
  const update = () => {
    const src = m.getSource(ROAD_LABEL_SRC) as GeoJSONSource | undefined;
    if (!src) return;
    if (!moved()) return;
    const cc = m.getCenter(), cp = m.project([cc.lng, cc.lat]), cv = m.getCanvas();
    last = { c: [cc.lng, cc.lat], px: [cp.x, cp.y], z: m.getZoom(), b: m.getBearing(), p: m.getPitch(), w: cv.clientWidth, h: cv.clientHeight };
    dirty = false;
    if (m.getZoom() < minZoom) { if (prev.length) { src.setData(empty); prev = []; } return; }
    const c = cv;
    const seen = new Set<string>();
    const pieces: RoadPiece[] = [];
    for (const f of m.querySourceFeatures("segments", { filter: ["has", "road_name"] })) {
      const g = f.geometry;
      const lines = g.type === "LineString" ? [g.coordinates] : g.type === "MultiLineString" ? g.coordinates : [];
      for (const ln of lines) {
        const key = `${f.properties?.seg_uid}|${ln[0]}|${ln[ln.length - 1]}`;
        if (seen.has(key)) continue;                     // 타일 경계에서 같은 선이 두 번 온다
        seen.add(key);
        pieces.push({ name: String(f.properties?.road_name), px: ln.map((p) => { const q = m.project(p as [number, number]); return [q.x, q.y] as Pt; }) });
      }
    }
    const fc = labelCollection(pickRoadLabels(pieces, c.clientWidth, c.clientHeight), (x, y) => { const l = m.unproject([x, y]); return [l.lng, l.lat]; });
    const feats = fc.features as GeoJSON.Feature<GeoJSON.Point>[];
    // ② 이름 묶음이 같고 옛 점이 전부 화면 안이면 그대로 둔다
    const names = (a: GeoJSON.Feature[]) => a.map((f) => String(f.properties?.name)).sort().join("|");
    const inView = prev.every((f) => { const q = m.project(f.geometry.coordinates as [number, number]); return q.x >= 4 && q.x <= c.clientWidth - 4 && q.y >= 9 && q.y <= c.clientHeight - 9; });
    if (prev.length === feats.length && names(prev) === names(feats) && inView) return;
    prev = feats;
    src.setData(fc);
  };
  const sch = makeScheduler(update, UPDATE_MS, SETTLE_MS, timers);
  const onData = (e: { sourceId?: string; isSourceLoaded?: boolean }) => { if (e.sourceId === "segments" && e.isSourceLoaded) { dirty = true; sch.touch(); } };
  // ★ `moveend` 를 `update` 에 **바로** 안 건다 — 추종 루프의 `jumpTo` 는 호출마다 `moveend` 를 낸다(매 프레임). 전부 스케줄러로 간다.
  m.on("move", sch.touch);
  m.on("moveend", sch.touch);
  m.on("sourcedata", onData);
  sch.touch();
  return () => { m.off("move", sch.touch); m.off("moveend", sch.touch); m.off("sourcedata", onData); sch.cancel(); };
}

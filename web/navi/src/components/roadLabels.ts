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
import type { GeoJSONSource, Map as MapLibreMap } from "maplibre-gl";

export const ROAD_LABEL_SRC = "road_labels";
/** 화면 가장자리에서 이만큼(px) 안쪽의 상자 안에서만 고른다 — 글자가 가장자리에 걸려 반만 나오지 않게. */
export const LABEL_MARGIN_PX = 24;
/** 글자 한 자의 폭 근사(px · 11px 글자 — 한글은 한 자가 거의 한 칸이다). */
export const CHAR_PX = 11.5;
/** 이 화면 길이(px) 아래의 도로 조각에는 글자를 안 얹는다 — 글자가 길보다 길면 어느 길의 이름인지 못 읽는다. */
export const MIN_PIECE_PX = 48;
/** 움직임이 멎은 뒤 다시 고르는 간격(ms). 주행 중 카메라가 계속 움직여도 이 간격으로만 고른다. */
export const UPDATE_MS = 700;

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
 *  - 조각이 글자보다 많이 짧으면(`MIN_PIECE_PX` · 글자 폭의 70%) 안 얹는다.
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
    if (len < Math.max(MIN_PIECE_PX, w * 0.7)) continue;
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
    features: picks.map((p) => ({ type: "Feature", properties: { name: p.name, len: Math.round(p.len) },
                                  geometry: { type: "Point", coordinates: unproject(p.x, p.y) } })),
  };
}

/** 지도에 붙인다 — 움직임이 있을 때마다(`UPDATE_MS` 간격으로) 다시 고른다. 떼는 함수를 돌려준다. `lbl-road` 층의 소스가 이미 있어야 한다(`layers.ts::sources`). */
export function attachRoadLabels(m: MapLibreMap, minZoom: number): () => void {
  let timer: number | undefined;
  const empty: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
  const update = () => {
    timer = undefined;
    const src = m.getSource(ROAD_LABEL_SRC) as GeoJSONSource | undefined;
    if (!src) return;
    if (m.getZoom() < minZoom) { src.setData(empty); return; }
    const c = m.getCanvas();
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
    src.setData(labelCollection(pickRoadLabels(pieces, c.clientWidth, c.clientHeight),
                                (x, y) => { const l = m.unproject([x, y]); return [l.lng, l.lat]; }));
  };
  const sched = () => { if (timer === undefined) timer = window.setTimeout(update, UPDATE_MS); };
  const onData = (e: { sourceId?: string; isSourceLoaded?: boolean }) => { if (e.sourceId === "segments" && e.isSourceLoaded) sched(); };
  m.on("move", sched);
  m.on("moveend", update);
  m.on("sourcedata", onData);
  sched();
  return () => { m.off("move", sched); m.off("moveend", update); m.off("sourcedata", onData); if (timer !== undefined) window.clearTimeout(timer); };
}

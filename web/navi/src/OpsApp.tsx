/**
 * OpsApp.tsx — **관제 화면(새 GIS).**  `…/navi/?view=ops`   (DECISIONS §214-4)
 *
 * ══ 왜 여기 있나 ════════════════════════════════════════════════
 * 판정 지도(GIS)는 `web/index.html` + `web/js/**` 로 따로 살았다 — 바닐라 JS · MapLibre 5
 * · 자기 검색 · 자기 차종 선택. 내비(React · MapLibre 6)와 **같은 데이터를 다른 코드로**
 * 읽었고, 서로 말을 못 했다. 관제사가 신고를 받고 → 차를 고르고 → 내비로 보내고 →
 * 차가 어디 있는지 보는 흐름이 **두 앱 사이에서 끊겼다.**
 *
 * 그래서 관제를 내비와 **같은 앱 · 같은 코드**로 세운다 —
 *
 *     사건 접수     검색(`domain/search`) · 지도 찍기
 *     출동 지령     센터 · 차종(`useFleet`) → 미리보기 경로(`domain/graph` · `access`)
 *                   → 「내비로 출동」 이 내비 탭을 연다(URL 에 사건 · 차종 · 센터)
 *     판정 지도     4색 원색 · 폭 비례 굵기 · 색별 거르기 · 구간 상세
 *     도달 가능     고른 센터 · 차종에서 닿는 구간(`reachableEdges`) — 못 닿는 곳은 사선
 *     정사영상      로컬 25cm 타일 — 키 불필요
 *     실시간        내비 탭이 보내는 위치 · 경로 · 상태 · 공유(`opsProtocol`)
 *                   공유에 「확인」 을 누르면 그 내비가 21(관제 확인)로 바뀐다
 *
 * ★ 옛 지도(`web/js`)는 이번에 지우지 않았다. 시험 열다섯 · CI 셋 · 배포 · config.js 정규식
 *   파싱이 물려 있다 — 철거는 핀 목록과 함께 다음 배치다(DECISIONS §214-5).
 * ★ 연결은 **같은 브라우저 탭끼리**다(BroadcastChannel). 서버가 아니다.
 *
 * ══ 관제실 초안 (2026-09-22 · DECISIONS §216-4) ═══════════════════
 * 사용자 지적 — 「관제는 출동자 시점이 아니라 **관제 센터에서 보는 느낌**이어야 한다」.
 * 종전 화면은 내비와 같은 밝은 바탕 · 비스듬한 3D · 왼쪽 긴 패널이라 운전석을 옮겨 놓은
 * 모양이었다. 상황실 벽 화면의 문법으로 바꾼다 —
 *     상단 상황판   시계 · 접수 · 출동 중 · 미확인 공유 · **실측 도착 중앙값**(119 이력)
 *     좌           접수 · 지령(차종 목록 = 요구폭)
 *     중앙          북쪽 위 **평면** 지도 · 어두운 바탕에 판정 4색 · 범례와 레이어는 지도 위
 *     우           차량 상태판 · 현장 공유 · 구간 정보 · 출동 이력 요약
 * ★ 와이어프레임이 아니다. 지혜님이 깊게 파기 전의 **초안**이다 — 구조와 데이터 배선을 먼저
 *   세우고, 모양은 와이어프레임이 오면 따른다.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { OpsMap, type OpsLayers } from "./components/OpsMap";
import { useFleet } from "./app/useFleet";
import { loadAll, loadHistory, type Bundle } from "./infra/dataSource";
import { openLink, newId, type Link } from "./infra/opsLink";
import {
  HB_MS, OPS_EMPTY, asNaviMsg, opsAck, opsReduce, unitStale, type OpsState,
} from "./domain/opsProtocol";
import { buildAdjacency, findRouteBetween, nearestNode, snapToEdge } from "./domain/graph";
import { ruleSummary } from "./domain/rules";
import { alternateAccess, reachableEdges, MAX_WALK_M } from "./domain/access";
import { preparePois, searchPois, type PoiHit } from "./domain/search";
import { travelSeconds } from "./domain/speed";
import { requiredWidth } from "./domain/vehicle";
import {
  CLEARANCE_BAND_ORDER, clearanceCounts, edgeClearance, fmtClearance,
} from "./domain/clearance";
import { snap as snapOnce, prepare } from "./domain/snap";
import { distM, type LngLat } from "./domain/geo";
import type { GraphEdge, HistorySummary, VehicleSpec } from "./domain/types";
import { F, fmtDur } from "./ui/tokens";
import { GRAY_REASON, grayReason, VERDICT_MEANING, VERDICT_ORDER } from "./ui/verdictMeaning";
import { CLEARANCE_FORMULA, CLEARANCE_SCALE, segmentReason } from "./ui/clearanceMeaning";
import { VehicleArt } from "./ui/VehicleArt";
import { displayName, vehicleClass } from "./domain/fleetName";

interface Incident { point: LngLat; label: string; at: Date }

export default function OpsApp() {
  const [data, setData] = useState<Bundle | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const fleet = useFleet();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [picking, setPicking] = useState(false);
  const [stationId, setStationId] = useState<string>("0");
  const [layers, setLayers] = useState<OpsLayers>({
    ortho: false, reach: true, cctvCov: false, bldg: false, history: false, context: false, terrain: true,
  });
  const [history, setHistory] = useState<{ summary?: HistorySummary } | null>(null);
  const [hidden, setHidden] = useState<ReadonlySet<string>>(() => new Set());
  // ★ 2026-09-23 (DECISIONS §220). 구간 색의 기준. **판정 4색이 기본이다** — 여유폭은
  //   고른 차로 그 자리에서 빼는 수라 파이프라인 판정을 덮어쓰지 않는다.
  const [colorMode, setColorMode] = useState<"verdict" | "clearance">("verdict");
  const [hiddenBands, setHiddenBands] = useState<ReadonlySet<string>>(() => new Set());
  const [seg, setSeg] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [ops, setOps] = useState<OpsState>(OPS_EMPTY);
  const [now, setNow] = useState(() => Date.now());
  const [focus, setFocus] = useState<{ n: number; at: LngLat; zoom?: number } | null>(null);
  const link = useRef<Link | null>(null);
  const opsId = useRef(newId("ops")).current;

  useEffect(() => { loadAll().then(setData).catch((e) => setFatal(String(e))); }, []);
  useEffect(() => { loadHistory().then((h) => setHistory(h as { summary?: HistorySummary } | null)); }, []);

  // ── 내비와 잇는다 ─────────────────────────────────────────────
  useEffect(() => {
    const l = openLink((d) => {
      const m = asNaviMsg(d);
      if (m) setOps((s) => opsReduce(s, m, Date.now()));
    });
    link.current = l;
    const hb = () => l.send({ t: "hb", ops: opsId, at: Date.now() });
    hb();
    const t = setInterval(hb, HB_MS);
    // ★ 상황판 시계는 1초마다. 끊김 판정(`unitStale`)도 이 시각을 쓴다
    const c = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(t); clearInterval(c); l.close(); };
  }, [opsId]);

  const ack = useCallback((shareId: string, unit: string) => {
    link.current?.send({ t: "ack", shareId, unit, at: Date.now(), by: "관제" });
    setOps((s) => opsAck(s, shareId, Date.now()));
  }, []);

  // ── 센터 ──────────────────────────────────────────────────────
  const stations = useMemo(() => {
    const fc = data?.stations;
    if (!fc) return [];
    return fc.features
      .filter((f) => f.properties?.kind === "center" && f.geometry.type === "Point")
      .map((f, i) => ({
        id: String(i),
        name: shortStation(String(f.properties?.["소방서 및 안전센터명"] ?? "안전센터")),
        point: (f.geometry as GeoJSON.Point).coordinates as LngLat,
      }));
  }, [data]);
  const station = stations.find((s) => s.id === stationId) ?? stations[0] ?? null;

  // ── 검색 ──────────────────────────────────────────────────────
  const pois = useMemo(() => (data ? preparePois(data.dest) : []), [data]);
  const hits: PoiHit[] = useMemo(() => (q.trim().length >= 1 ? searchPois(pois, q).slice(0, 8) : []), [pois, q]);
  const prepared = useMemo(() => (data ? prepare(data.graph.edges.map((e) => ({
    seg_uid: e.seg_uid, verdict: e.verdict, width_min_m: e.width_min_m,
    seg_label: e.seg_label, coords: e.coords,
  }))) : null), [data]);

  /**
   * 좌표 → **도로 위 점**. 내비(`useNavigation.snapAt`)와 같은 순서다.
   * ★ 2026-09-22 검수. 센터 건물 좌표에서 곧장 가장 가까운 노드를 잡았더니 차고 뒤
   *   **끊긴 골목 조각**의 노드가 걸려 어디로도 경로가 안 났다(「300m 안에 접근 지점 없음」).
   *   내비는 먼저 도로에 붙이므로 멀쩡했다 — 같은 순서를 따른다.
   */
  const onRoad = useCallback((pt: LngLat): LngLat => {
    const r = prepared ? snapOnce(pt[0], pt[1], prepared, {}) : null;
    return r && r.dist_m <= 60 ? r.point : pt;
  }, [prepared]);

  // ── 도달 가능 · 출동 미리보기 (고른 차종의 제원으로) ────────────
  const spec = fleet.spec ?? data?.spec ?? null;
  const adj = useMemo(() => (data && spec ? buildAdjacency(data.graph, spec, false, "safe") : null),
                      [data, spec]);
  const fromNode = useMemo(() => (data && adj && station ? nearestNode(data.graph, adj, onRoad(station.point)) : -1),
                           [data, adj, station, onRoad]);
  const reach = useMemo(() => (data && adj && fromNode >= 0 ? reachableEdges(data.graph, adj, fromNode) : null),
                        [data, adj, fromNode]);
  const plan = useMemo(() => {
    if (!data || !adj || fromNode < 0 || !incident) return null;
    // 출발·도착을 구간에 투영한다(DECISIONS §218-3) — 노드에 붙이면 교차점으로 옮겨진다
    const S = station ? snapToEdge(data.graph, adj, onRoad(station.point)) : null;
    const T = snapToEdge(data.graph, adj, onRoad(incident.point));
    let p = S && T ? findRouteBetween(data.graph, adj, S, T) : null;
    let alt = false;
    if (!p && S) {
      const a = alternateAccess(data.graph, adj, fromNode, incident.point);
      if (a) { p = findRouteBetween(data.graph, adj, S, { node: a.node }); alt = !!p; }
    }
    if (!p) return { plan: null, alt: false, walkM: 0 };
    const end = p.coords[p.coords.length - 1];
    return { plan: p, alt, walkM: end ? distM(end, incident.point) : 0 };
  }, [data, adj, fromNode, station, incident, onRoad]);

  const onPick = useCallback((lon: number, lat: number) => {
    if (!picking || !prepared) return;
    const r = snapOnce(lon, lat, prepared, {});
    setIncident({ point: [lon, lat], label: r?.seg_label ?? "지도에서 고른 지점", at: new Date() });
    setPicking(false);
  }, [picking, prepared]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of data?.graph.edges ?? []) c[e.verdict] = (c[e.verdict] ?? 0) + 1;
    return c;
  }, [data]);
  const grayCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of data?.graph.edges ?? []) {
      if (e.verdict === "unknown") c[e.unknown_reason ?? "width"] = (c[e.unknown_reason ?? "width"] ?? 0) + 1;
    }
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  }, [data]);
  /** 여유폭 구간별 개수 — 고른 차가 바뀌면 다시 센다(§220) */
  const bandCounts = useMemo(
    () => (data && spec ? clearanceCounts(data.graph.edges, spec)
                        : { neg: 0, tight: 0, mid: 0, wide: 0, unknown: 0 }),
    [data, spec]);
  const edgeByUid = useMemo(() => new Map((data?.graph.edges ?? []).map((e) => [e.seg_uid, e])), [data]);
  const selEdge: GraphEdge | null = seg ? edgeByUid.get(seg) ?? null : null;

  const units = useMemo(() => Object.values(ops.units), [ops.units]);
  const need = spec ? requiredWidth(spec) : 3;

  if (fatal) return <Center>★ {fatal}</Center>;
  if (!data) return <Center>불러오는 중…</Center>;
  const style = data.graph.style;
  const vehicle = fleet.current;

  const dispatchUrl = incident && vehicle && station
    ? `./?incident=${incident.point[0].toFixed(6)},${incident.point[1].toFixed(6)}`
      + `&label=${encodeURIComponent(incident.label)}&vehicle=${encodeURIComponent(vehicle.id)}`
      + `&station=${encodeURIComponent(station.name)}`
    : null;

  const waiting = ops.feed.filter((f) => !f.ackedAt).length;
  const live = units.filter((u) => !unitStale(u, now)).length;
  const hs = history?.summary;
  const myCenter = station ? hs?.by_center[`${station.name.replace(/119안전센터$/, "")}119안전센터`] : undefined;

  return (
    <div style={shell}>
      {/* ══ 상단 상황판 ══════════════════════════════════════════ */}
      <header style={top}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, minWidth: 0 }}>
          <b style={{ fontSize: 18, letterSpacing: -.3 }}>FireLane 종합상황실</b>
          <span style={{ fontSize: 12, color: D.sub, whiteSpace: "nowrap" }}>동부소방서 관할 · 동명동 · 도면 기반 1차 판정</span>
        </div>
        <div style={{ flex: 1 }} />
        <Tile k="접수" v={incident ? "1건" : "0건"} tone={incident ? "danger" : undefined} />
        <Tile k="출동 중" v={`${live}대`} tone={live ? "ok" : undefined} />
        <Tile k="미확인 공유" v={`${waiting}건`} tone={waiting ? "warn" : undefined} />
        <Tile k={`실측 도착 중앙값${myCenter ? ` · ${station?.name.replace(/119안전센터$/, "")}` : ""}`}
              v={fmtSec(myCenter?.median_s ?? hs?.resp_median_s ?? null)}
              sub={myCenter ? `${myCenter.n}건` : hs ? `${hs.resp_n}건` : "이력 없음"} />
        <div style={clock}>{clockText(now)}</div>
      </header>

      <div style={body}>
        {/* ══ 좌 — 접수 · 지령 ═════════════════════════════════════ */}
        <aside style={colL}>
          <Sec title="사건 접수">
            <div style={{ display: "flex", gap: 6 }}>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="상호 · 주소 · 건물 · 도로명"
                     style={input} />
              <button onClick={() => setPicking((x) => !x)}
                      style={{ ...btnSm, background: picking ? D.accent : "transparent", color: picking ? "#0b1220" : D.accent }}>
                {picking ? "지도를 누르세요" : "지도에서"}
              </button>
            </div>
            {hits.length > 0 && (
              <div style={list}>
                {hits.map((h, i) => (
                  <button key={`${h.name}-${i}`} style={listItem} onClick={() => {
                    setIncident({ point: h.point, label: h.name, at: new Date() });
                    setQ(""); setFocus({ n: Date.now(), at: h.point, zoom: 17 });
                  }}>
                    <b>{h.name}</b>
                    <span style={{ display: "block", fontSize: 11, color: D.sub }}>{h.addr || h.cat}</span>
                  </button>
                ))}
              </div>
            )}
            {incident ? (
              <div style={{ ...card, borderColor: D.danger }}>
                <div style={{ fontSize: 11, color: D.danger, fontWeight: 800, letterSpacing: .4 }}>화재 · 접수 {hhmm(incident.at)}</div>
                <div style={{ fontSize: 16, fontWeight: 800, marginTop: 2 }}>{incident.label}</div>
                <button onClick={() => setIncident(null)} style={{ ...linkBtn, marginTop: 4 }}>접수 해제</button>
              </div>
            ) : (
              <div style={{ fontSize: 12, color: D.sub, marginTop: 8 }}>검색하거나 「지도에서」 로 지점을 찍는다.</div>
            )}
          </Sec>

          <Sec title="출동 지령">
            <label style={lab}>출발 센터</label>
            <select value={station?.id ?? ""} onChange={(e) => setStationId(e.target.value)} style={input}>
              {stations.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <label style={lab}>차량 — 요구폭</label>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 250, overflowY: "auto" }}>
              {(fleet.fleet?.vehicles ?? []).map((v) => {
                const on = v.id === vehicle?.id;
                return (
                  <button key={v.id} onClick={() => fleet.select(v.id)}
                          style={{ ...vehRow, borderColor: on ? D.accent : D.line, background: on ? "#0c2a3f" : "transparent" }}>
                    <VehicleArt kind={vehicleClass(v.label, v.id)} w={40} />
                    <span style={{ flex: 1, textAlign: "left" }}>
                      <b style={{ fontSize: 13 }}>{displayName(v.label)}</b>
                      <span style={{ display: "block", fontSize: 10, color: D.sub }}>{(v.station ?? "").replace(/119안전센터|119구조대/, "")}</span>
                    </span>
                    <b style={{ fontSize: 12, color: on ? D.accent : D.sub }}>{v.required_width_m.toFixed(1)}m</b>
                  </button>
                );
              })}
            </div>
            {incident && plan && (
              <div style={{ ...card, borderColor: plan.plan ? (plan.alt ? D.warn : D.ok) : D.danger }}>
                {plan.plan ? (
                  <>
                    <div style={{ fontWeight: 800, fontSize: 18 }}>
                      {fmtDur(travelSeconds(plan.plan))} <span style={{ fontSize: 13, color: D.sub }}>· {(plan.plan.lengthM / 1000).toFixed(1)}km · 내비 예측</span>
                    </div>
                    {myCenter?.median_s != null && (
                      <div style={{ fontSize: 11, color: D.sub, marginTop: 2 }}>
                        같은 센터 실제 출동→도착 중앙값 {fmtSec(myCenter.median_s)} — 내비 속도표는 미검증이다
                      </div>
                    )}
                    {/* ★ §220 — 경로의 **가장 좁은 곳의 여유폭**. 관제가 지령 전에 보는 수다 */}
                    <div style={{ fontSize: 12, color: D.sub, marginTop: 4 }}>
                      확인 필요 {plan.plan.edges.filter((e) => e.verdict === "needs_cv" || e.verdict === "unknown").length}개 ·
                      최소폭 {Math.min(...plan.plan.edges.map((e) => e.width_min_m ?? 99)).toFixed(1)}m / 요구 {need.toFixed(1)}m ·
                      여유폭 <b style={{ color: D.ink }}>
                        {fmtClearance(Math.min(...plan.plan.edges.map((e) => e.width_min_m ?? 99)) - need)}
                      </b>
                    </div>
                    {ruleSummary(plan.plan.rules) && (
                      <div style={{ fontSize: 12, color: D.warn, fontWeight: 800, marginTop: 4 }}>
                        통행 규칙 — {ruleSummary(plan.plan.rules)}
                      </div>
                    )}
                    {plan.alt && (
                      <div style={{ fontSize: 12, color: D.warn, fontWeight: 800, marginTop: 4 }}>
                        차량 경로 없음 → 대체 접근 지점 + 도보 약 {Math.round(plan.walkM)}m(직선)
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ fontWeight: 800, color: D.danger }}>
                    이 차종으로 {MAX_WALK_M}m 안에 닿는 접근 지점이 없다 — 다른 차종 · 센터
                  </div>
                )}
              </div>
            )}
            <button disabled={!dispatchUrl || !plan?.plan}
                    onClick={() => dispatchUrl && window.open(dispatchUrl, "_blank")}
                    style={{ ...cta, opacity: dispatchUrl && plan?.plan ? 1 : .35 }}>
              출동 지령 — 내비 열기 »
            </button>
            <div style={{ fontSize: 10.5, color: D.sub, marginTop: 6, lineHeight: 1.5 }}>
              새 탭에 내비가 사건 · 차종 · 센터를 채운 채 열린다. 위치 · 공유가 이 화면으로 온다(같은 브라우저 탭끼리 — 서버 아님).
            </div>
          </Sec>
        </aside>

        {/* ══ 중앙 — 지도(북쪽 위 · 평면) ═══════════════════════════ */}
        <main style={mapBox}>
          <OpsMap view={data.view} terrain={data.graph.terrain} style={style} layers={layers} hidden={hidden}
                  colorMode={colorMode} requiredM={need} hiddenBands={hiddenBands}
                  reachable={reach} incident={incident?.point ?? null}
                  preview={plan?.plan?.coords ?? null}
                  previewWalk={plan?.plan && incident ? [plan.plan.coords[plan.plan.coords.length - 1], incident.point] : null}
                  units={units} feed={ops.feed} selectedSeg={seg} focus={focus}
                  onPick={onPick} onSeg={(u) => { if (!picking) setSeg(u); }} />
          {/* 범례 · 레이어 — 지도 위 왼쪽 아래 */}
          <div style={legendBox}>
            {/* ══ 구간 색 기준 — 판정 4색(기본) ↔ 여유폭 (§220) ══════════
                ★ 어느 모드인지가 **범례 자체**로 보여야 한다. 단추를 누르면 아래 줄이
                  통째로 바뀌고 머리글이 지금 칠해지는 것이 무엇인지 말한다. */}
            <div style={{ display: "flex", gap: 4, marginBottom: 6 }}>
              {([["verdict", "판정 4색"], ["clearance", "여유폭"]] as const).map(([k, t]) => (
                <button key={k} onClick={() => setColorMode(k)}
                        style={{ ...modeBtn, background: colorMode === k ? D.accent : "transparent",
                                 color: colorMode === k ? "#0b1220" : D.sub,
                                 borderColor: colorMode === k ? D.accent : D.line }}>
                  {t}
                </button>
              ))}
            </div>
            {colorMode === "verdict" ? (
              <>
                <div style={{ fontSize: 11, fontWeight: 800, color: D.sub, marginBottom: 4 }}>판정 (CV = 영상판정) · 눌러서 숨기기</div>
                {VERDICT_ORDER.filter((k) => style[k]).map((k) => {
                  const off = hidden.has(k);
                  return (
                    <button key={k} style={{ ...legendRow, opacity: off ? .35 : 1 }} title={VERDICT_MEANING[k]}
                            onClick={() => setHidden((h) => { const n = new Set(h); if (n.has(k)) n.delete(k); else n.add(k); return n; })}>
                      <i style={{ ...dot, background: style[k].color }} />
                      <span style={{ flex: 1, textAlign: "left" }}>{style[k].label}</span>
                      <b>{counts[k] ?? 0}</b>
                    </button>
                  );
                })}
                {grayCounts.length > 0 && !hidden.has("unknown") && (
                  <div style={{ margin: "0 0 4px 20px", fontSize: 10.5, color: D.sub, lineHeight: 1.55 }}>
                    {grayCounts.map(([k, n]) => (
                      <div key={k} style={{ display: "flex" }}><span style={{ flex: 1 }}>└ {GRAY_REASON[k]?.short ?? k}</span><b>{n}</b></div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <div style={{ fontSize: 11, fontWeight: 800, color: D.accent, marginBottom: 1 }}>
                  여유폭 · {displayName(vehicle?.label ?? "기준 차량")} · 눌러서 숨기기
                </div>
                <div style={{ fontSize: 10.5, color: D.sub, marginBottom: 4 }}>
                  {CLEARANCE_FORMULA} = {need.toFixed(1)}m
                </div>
                {CLEARANCE_BAND_ORDER.map((k) => {
                  const off = hiddenBands.has(k);
                  return (
                    <button key={k} style={{ ...legendRow, opacity: off ? .35 : 1 }} title={CLEARANCE_SCALE[k].label}
                            onClick={() => setHiddenBands((h) => { const n = new Set(h); if (n.has(k)) n.delete(k); else n.add(k); return n; })}>
                      <i style={{ ...dot, background: CLEARANCE_SCALE[k].color }} />
                      <span style={{ flex: 1, textAlign: "left" }}>{CLEARANCE_SCALE[k].label}</span>
                      <b>{bandCounts[k]}</b>
                    </button>
                  );
                })}
                <div style={{ fontSize: 10.5, color: D.sub, marginTop: 2, lineHeight: 1.5 }}>
                  판정은 안 바뀐다 — 같은 구간을 고른 차의 폭으로 다시 칠한 것뿐이다.
                </div>
              </>
            )}
            <div style={{ borderTop: `1px solid ${D.line}`, margin: "6px 0 4px" }} />
            {([
              ["reach", `도달 불가 사선 · ${displayName(vehicle?.label ?? "기준 차량")}`],
              ["history", "출동 이력 · 실제 도착 시간"],
              ["context", "과속방지턱 · 카메라 · 보호구역"],
              ["cctvCov", "CCTV 영상판정 반경 25m"],
              ["ortho", "항공정사영상 25cm"],
              ["bldg", "3D 건물(비스듬히)"],
              ["terrain", "지형(음영 · 3D 에서 지면 휨)"],
            ] as [keyof OpsLayers, string][]).map(([k, t]) => (
              <label key={k} style={toggleRow}>
                <input type="checkbox" checked={layers[k]} onChange={() => setLayers((L) => ({ ...L, [k]: !L[k] }))} />
                {t}
              </label>
            ))}
            {layers.history && (
              <div style={{ fontSize: 10.5, color: D.sub, marginTop: 4, lineHeight: 1.5 }}>
                점 색 = 실제 출동→도착 <b style={{ color: D.ok }}>~5분</b> · <b style={{ color: D.warn }}>~8분</b> · <b style={{ color: D.danger }}>8분+</b> (경계는 표시용 가정값)
              </div>
            )}
            <div style={{ fontSize: 10.5, color: D.sub, marginTop: 4 }}>
              닿는 구간 {reach?.size ?? 0} / {data.graph.edges.length} · 굵기 = 최소 유효폭 · 전 구간 현장 미검증
            </div>
          </div>
        </main>

        {/* ══ 우 — 차량 상태판 · 현장 공유 · 구간 ═══════════════════ */}
        <aside style={colR}>
          <Sec title={`차량 상태판 · 연결 ${units.length}`}>
            {link.current?.available === false && (
              <div style={{ fontSize: 12, color: D.warn }}>이 브라우저는 탭 연결을 못 한다</div>
            )}
            {units.length === 0 && (
              <div style={{ fontSize: 12, color: D.sub }}>연결된 내비가 없다 — 「출동 지령」 으로 연다.</div>
            )}
            {units.map((u) => {
              const stale = unitStale(u, now);
              const st = stale ? "끊김" : u.last.remainM != null ? "출동 중" : "대기";
              const tone = stale ? D.danger : u.last.remainM != null ? D.ok : D.sub;
              return (
                <button key={u.unit} style={unitRow}
                        onClick={() => u.last.pos && setFocus({ n: Date.now(), at: u.last.pos, zoom: 17.2 })}>
                  <span style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
                    <b style={{ flex: 1 }}>{u.last.vehicle}</b>
                    <span style={{ ...chip, color: tone, borderColor: tone }}>{st}</span>
                  </span>
                  <span style={{ fontSize: 12 }}>{u.last.title}</span>
                  <span style={{ fontSize: 11, color: D.sub }}>
                    {u.last.remainM != null ? `남은 ${(u.last.remainM / 1000).toFixed(1)}km · 도착 ${u.last.etaText ?? "—"}` : "—"}
                    {u.last.incident ? ` · ${u.last.incident.label}` : ""}
                  </span>
                </button>
              );
            })}
          </Sec>
          <Sec title={`현장 공유${waiting ? ` · 미확인 ${waiting}` : ""}`}>
            {ops.feed.length === 0 && <div style={{ fontSize: 12, color: D.sub }}>아직 없다.</div>}
            <div style={{ maxHeight: 260, overflowY: "auto" }}>
              {ops.feed.map((f) => (
                <div key={f.shareId} style={feedRow}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 800, color: f.kind === "blocked" ? D.danger : f.kind === "arrival" ? D.accent : D.warn }}>
                      {f.kind === "blocked" ? "통행 불가 신고" : f.kind === "arrival" ? "도착 보고" : "병목 공유"} · {hhmm(new Date(f.at))}
                    </div>
                    <div style={{ fontSize: 12 }}>{f.text}</div>
                  </div>
                  {f.ackedAt
                    ? <span style={{ fontSize: 12, color: D.ok, fontWeight: 800 }}>확인 {hhmm(new Date(f.ackedAt))}</span>
                    : <button style={ackBtn} onClick={() => { ack(f.shareId, f.unit); if (f.point) setFocus({ n: Date.now(), at: f.point, zoom: 17.5 }); }}>확인</button>}
                </div>
              ))}
            </div>
          </Sec>
          {selEdge && spec ? (
            <SegCard e={selEdge} style={style} spec={spec} reachable={reach?.has(selEdge.seg_uid) ?? null}
                     vehicle={displayName(vehicle?.label ?? "기준 차량")} onClose={() => setSeg(null)} />
          ) : (
            <Sec title="구간 정보">
              <div style={{ fontSize: 12, color: D.sub }}>지도에서 도로를 누르면 여유폭 · 사유 · 판정 근거 · 단속 이력이 뜬다.</div>
            </Sec>
          )}
          {hs && (
            <Sec title="출동 이력 요약 (실측)">
              {Object.entries(hs.by_center).filter(([, v]) => v.n >= 5).map(([k, v]) => (
                <Row key={k} k={`${k.replace(/119안전센터|119구조대/, (m) => (m.includes("구조") ? " 구조대" : ""))} · ${v.n}건`}
                     v={`${fmtSec(v.median_s)}${v.straight_kmh ? ` · 직선 ${v.straight_kmh}km/h` : ""}`} />
              ))}
              <Row k={`동구 화재 · ${hs.fire_donggu.n}건`} v={fmtSec(hs.fire_donggu.median_s)} />
              <div style={{ fontSize: 10.5, color: D.sub, marginTop: 6, lineHeight: 1.5 }}>
                출동 지령 → 현장 도착. 직선 km/h 는 센터~지점 직선거리 ÷ 시간(실제 주행 속도의 하한).
              </div>
            </Sec>
          )}
        </aside>
      </div>
    </div>
  );
}

/**
 * 구간 카드.
 *
 * ★ 2026-09-23 (DECISIONS §220). 두 가지가 들어왔다 — **여유폭을 수로**(색과 같은 4단
 *   색을 글자에 입힌다) 와 **사유 한 줄**. 사유는 빨강만이 아니라 판정마다 낸다.
 *   초록이고 여유가 넉넉하면 `segmentReason` 이 null 을 내고 그 칸이 통째로 빠진다 —
 *   관제사가 그것으로 취할 조치가 없으면 화면에서도 뺀다.
 */
function SegCard({ e, style, spec, reachable, vehicle, onClose }: {
  e: GraphEdge; style: Bundle["graph"]["style"]; spec: VehicleSpec; reachable: boolean | null;
  vehicle: string; onClose: () => void;
}) {
  const s = style[e.verdict];
  const c = edgeClearance(e, spec);
  const why = segmentReason(e, spec);
  const cctvOk = e.cctv_dist_m != null && e.cctv_dist_m <= 25;
  const gray = grayReason(e);
  return (
    <div style={{ ...secBox }}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <b style={{ fontSize: 15, flex: 1 }}>{e.seg_label ?? e.road_name ?? e.seg_uid}</b>
        <button onClick={onClose} style={{ border: "none", background: "none", fontSize: 18, cursor: "pointer", color: D.sub }}>✕</button>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
        <i style={{ ...dot, background: s?.color }} />
        <b>{s?.label ?? e.verdict}</b>
        <span style={{ fontSize: 11, color: D.sub }}>{VERDICT_MEANING[e.verdict]}</span>
      </div>
      {why && (
        <div style={{ ...whyBox, borderColor: CLEARANCE_SCALE[c.band].color }}>
          <b style={{ color: CLEARANCE_SCALE[c.band].color }}>{why.head}</b>
          <div style={{ color: D.ink, marginTop: 2 }}>{why.detail}</div>
          {why.action && <div style={{ color: D.sub, marginTop: 2 }}>→ {why.action}</div>}
        </div>
      )}
      <Row k="최소 · 최대 유효폭" v={`${e.width_min_m?.toFixed(1) ?? "—"} · ${e.width_max_m?.toFixed(1) ?? "—"}m`} />
      <Row k={`${vehicle} 요구폭 (전폭 + 여유)`} v={`${c.requiredM.toFixed(1)}m`} />
      {/* ★ 멘토링 §219 — 「여유폭을 색과 수로」. 이 한 줄이 그 수다 */}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, padding: "4px 0",
                    borderBottom: `1px solid ${D.line}` }}>
        <span style={{ color: D.sub }}>여유폭 = 최소 유효폭 − 요구폭</span>
        <b style={{ color: CLEARANCE_SCALE[c.band].color, textAlign: "right" }}>
          {fmtClearance(c.m)} <span style={{ fontWeight: 600, color: D.sub }}>{CLEARANCE_SCALE[c.band].short}</span>
        </b>
      </div>
      <Row k="측정 신뢰도 · 폭 표본" v={`${e.width_cov != null ? Math.round(e.width_cov * 100) + "%" : "—"} · ${e.n_sample ?? "—"}개`} />
      <Row k="가까운 CCTV" v={e.cctv_dist_m != null ? `${Math.round(e.cctv_dist_m)}m ${cctvOk ? "(영상판정 가능)" : "(25m 밖)"}` : "—"} />
      {gray && (
        <div style={{ fontSize: 12, background: "#0f172a", border: `1px solid ${D.line}`, borderRadius: 8, padding: "7px 9px", marginTop: 6, lineHeight: 1.5 }}>
          <b>회색 사유 — {gray.short}</b><br />{gray.long}
        </div>
      )}
      <Row k="불법주정차 단속(도로명 · 3년)" v={e.park ? `${e.park.toLocaleString()}건` : "없음"} warn={(e.park ?? 0) >= 200} />
      {e.ow ? (
        <Row k="일방통행" v={e.ow === 2 ? "방향 미확인" : "방향 확정"} warn={e.ow === 2} />
      ) : null}
      <Row k="길이" v={e.length_m != null ? `${Math.round(e.length_m)}m` : "—"} />
      <Row k="선택 센터에서" v={reachable == null ? "—" : reachable ? "도달 가능" : "도달 불가"} warn={reachable === false} />
      <div style={{ fontSize: 11, color: D.sub, marginTop: 8, lineHeight: 1.5 }}>
        폭은 도면 기반 미검증 값이다. 실시간 주정차 · 공사 · 회전 · 높이는 반영하지 않는다.
      </div>
    </div>
  );
}

function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12, padding: "4px 0",
                  borderBottom: `1px solid ${D.line}` }}>
      <span style={{ color: D.sub }}>{k}</span>
      <b style={{ color: warn ? D.danger : D.ink, textAlign: "right" }}>{v}</b>
    </div>
  );
}
function Sec({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={secBox}>
      <div style={{ fontSize: 11, fontWeight: 800, color: D.sub, letterSpacing: .6, marginBottom: 8 }}>{title}</div>
      {children}
    </section>
  );
}
function Tile({ k, v, sub, tone }: { k: string; v: string; sub?: string; tone?: "ok" | "warn" | "danger" }) {
  const c = tone === "ok" ? D.ok : tone === "warn" ? D.warn : tone === "danger" ? D.danger : D.ink;
  return (
    <div style={tile}>
      <div style={{ fontSize: 10.5, color: D.sub, whiteSpace: "nowrap" }}>{k}</div>
      <div style={{ fontSize: 18, fontWeight: 800, color: c, lineHeight: 1.15 }}>
        {v}{sub && <span style={{ fontSize: 10.5, color: D.sub, fontWeight: 600 }}> {sub}</span>}
      </div>
    </div>
  );
}
function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ ...shell, display: "grid", placeItems: "center" }}>{children}</div>;
}
function hhmm(d: Date): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function clockText(t: number): string {
  const d = new Date(t);
  return `${hhmm(d)}:${String(d.getSeconds()).padStart(2, "0")}`;
}
function fmtSec(s: number | null | undefined): string {
  if (s == null) return "—";
  return `${Math.floor(s / 60)}분 ${String(Math.round(s % 60)).padStart(2, "0")}초`;
}
function shortStation(raw: string): string {
  const m = raw.match(/광주-(.+)$/);
  return (m ? m[1] : raw).replace(/[-\s]/g, "");
}

// ── 관제실 톤 (§216-4) ─────────────────────────────────────────────
// ★ 판정 4색은 여기 없다(정본 `style`). 틀 · 글자 · 상태 색만이다.
const D = {
  bg: "#0b1220", panel: "#0f172a", card: "#111c2f", line: "#23324a", ink: "#e5e7eb", sub: "#94a3b8",
  accent: "#38bdf8", ok: "#22c55e", warn: "#f59e0b", danger: "#ef4444",
};
const shell: React.CSSProperties = {
  position: "fixed", inset: 0, background: D.bg, fontFamily: F.family, color: D.ink,
  display: "flex", flexDirection: "column",
};
const top: React.CSSProperties = {
  height: 58, flex: "0 0 auto", display: "flex", alignItems: "center", gap: 10, padding: "0 14px",
  borderBottom: `1px solid ${D.line}`, background: "#070d18",
};
const tile: React.CSSProperties = {
  border: `1px solid ${D.line}`, borderRadius: 8, padding: "4px 10px", background: D.panel, minWidth: 74,
};
const clock: React.CSSProperties = {
  fontSize: 22, fontWeight: 800, fontVariantNumeric: "tabular-nums", marginLeft: 6, color: D.accent,
};
const body: React.CSSProperties = {
  flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "340px 1fr 360px",
};
const colL: React.CSSProperties = {
  borderRight: `1px solid ${D.line}`, overflowY: "auto", padding: 10, display: "flex", flexDirection: "column", gap: 10,
  background: D.panel,
};
const colR: React.CSSProperties = { ...colL, borderRight: "none", borderLeft: `1px solid ${D.line}` };
const mapBox: React.CSSProperties = { position: "relative", minWidth: 0 };
const secBox: React.CSSProperties = {
  background: D.card, border: `1px solid ${D.line}`, borderRadius: 10, padding: "10px 12px",
};
const whyBox: React.CSSProperties = {
  fontSize: 11.5, background: "#0f172a", border: "1.5px solid", borderRadius: 8,
  padding: "7px 9px", margin: "8px 0 2px", lineHeight: 1.5,
};
const legendBox: React.CSSProperties = {
  position: "absolute", left: 10, bottom: 10, width: 270, zIndex: 3, background: "rgba(11,18,32,.9)",
  border: `1px solid ${D.line}`, borderRadius: 10, padding: "8px 10px", fontSize: 12,
};
const input: React.CSSProperties = {
  flex: 1, width: "100%", boxSizing: "border-box", border: `1px solid ${D.line}`, borderRadius: 8,
  padding: "8px 10px", fontSize: 13, fontFamily: F.family, background: D.panel, color: D.ink,
};
const btnSm: React.CSSProperties = {
  border: `1px solid ${D.accent}`, borderRadius: 8, padding: "0 10px", fontWeight: 800, fontSize: 12,
  cursor: "pointer", fontFamily: F.family, whiteSpace: "nowrap",
};
const linkBtn: React.CSSProperties = {
  border: "none", background: "none", color: D.sub, fontSize: 11, cursor: "pointer", padding: 0,
  fontFamily: F.family, textDecoration: "underline",
};
const list: React.CSSProperties = { border: `1px solid ${D.line}`, borderRadius: 8, marginTop: 6, overflow: "hidden" };
const listItem: React.CSSProperties = {
  display: "block", width: "100%", textAlign: "left", border: "none", borderBottom: `1px solid ${D.line}`,
  background: D.panel, color: D.ink, padding: "7px 10px", cursor: "pointer", fontFamily: F.family, fontSize: 13,
};
const card: React.CSSProperties = {
  marginTop: 8, border: `1.5px solid ${D.line}`, borderRadius: 10, padding: "9px 11px", background: D.panel,
};
const lab: React.CSSProperties = { display: "block", fontSize: 11, color: D.sub, margin: "8px 0 4px" };
const vehRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, border: "1px solid", borderRadius: 8, padding: "4px 8px",
  cursor: "pointer", fontFamily: F.family, color: D.ink,
};
const cta: React.CSSProperties = {
  width: "100%", marginTop: 10, border: "none", borderRadius: 10, padding: "12px 0",
  background: "linear-gradient(90deg,#dc2626,#ef4444)", color: "#fff", fontWeight: 800, fontSize: 15,
  cursor: "pointer", fontFamily: F.family, letterSpacing: .3,
};
const modeBtn: React.CSSProperties = {
  flex: 1, border: "1px solid", borderRadius: 7, padding: "4px 0", fontSize: 11.5, fontWeight: 800,
  cursor: "pointer", fontFamily: F.family,
};
const legendRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, width: "100%", border: "none", background: "none",
  padding: "3px 0", cursor: "pointer", fontFamily: F.family, color: D.ink, fontSize: 12,
};
const dot: React.CSSProperties = { width: 12, height: 12, borderRadius: 6, flex: "0 0 auto", border: "2px solid rgba(255,255,255,.25)" };
const toggleRow: React.CSSProperties = { display: "flex", alignItems: "center", gap: 7, fontSize: 12, padding: "2px 0" };
const chip: React.CSSProperties = { border: "1px solid", borderRadius: 999, padding: "1px 8px", fontSize: 11, fontWeight: 800 };
const unitRow: React.CSSProperties = {
  display: "flex", flexDirection: "column", alignItems: "flex-start", width: "100%", gap: 2, marginTop: 6,
  border: `1px solid ${D.line}`, borderRadius: 8, padding: "7px 9px", background: D.panel,
  cursor: "pointer", fontFamily: F.family, color: D.ink, textAlign: "left",
};
const feedRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, padding: "7px 0", borderBottom: `1px solid ${D.line}`,
};
const ackBtn: React.CSSProperties = {
  border: "none", background: D.accent, color: "#0b1220", borderRadius: 7, padding: "6px 11px",
  fontWeight: 800, cursor: "pointer", fontFamily: F.family,
};

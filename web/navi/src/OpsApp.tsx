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
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { OpsMap, type OpsLayers } from "./components/OpsMap";
import { useFleet } from "./app/useFleet";
import { loadAll, type Bundle } from "./infra/dataSource";
import { openLink, newId, type Link } from "./infra/opsLink";
import {
  HB_MS, OPS_EMPTY, asNaviMsg, opsAck, opsReduce, unitStale, type OpsState,
} from "./domain/opsProtocol";
import { buildAdjacency, findRoute, nearestNode } from "./domain/graph";
import { alternateAccess, reachableEdges, MAX_WALK_M } from "./domain/access";
import { preparePois, searchPois, type PoiHit } from "./domain/search";
import { travelSeconds } from "./domain/speed";
import { requiredWidth } from "./domain/vehicle";
import { snap as snapOnce, prepare } from "./domain/snap";
import { distM, type LngLat } from "./domain/geo";
import type { GraphEdge } from "./domain/types";
import { C, F, fmtDur } from "./ui/tokens";
import { VERDICT_MEANING, VERDICT_ORDER } from "./ui/verdictMeaning";
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
  const [layers, setLayers] = useState<OpsLayers>({ ortho: false, reach: true, cctvCov: false, bldg: true });
  const [hidden, setHidden] = useState<ReadonlySet<string>>(() => new Set());
  const [seg, setSeg] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [ops, setOps] = useState<OpsState>(OPS_EMPTY);
  const [now, setNow] = useState(() => Date.now());
  const [focus, setFocus] = useState<{ n: number; at: LngLat; zoom?: number } | null>(null);
  const link = useRef<Link | null>(null);
  const opsId = useRef(newId("ops")).current;

  useEffect(() => { loadAll().then(setData).catch((e) => setFatal(String(e))); }, []);

  // ── 내비와 잇는다 ─────────────────────────────────────────────
  useEffect(() => {
    const l = openLink((d) => {
      const m = asNaviMsg(d);
      if (m) setOps((s) => opsReduce(s, m, Date.now()));
    });
    link.current = l;
    const hb = () => l.send({ t: "hb", ops: opsId, at: Date.now() });
    hb();
    const t = setInterval(() => { hb(); setNow(Date.now()); }, HB_MS);
    return () => { clearInterval(t); l.close(); };
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
    const to = nearestNode(data.graph, adj, onRoad(incident.point));
    let p = findRoute(data.graph, adj, fromNode, to);
    let alt = false;
    if (!p) {
      const a = alternateAccess(data.graph, adj, fromNode, incident.point);
      if (a) { p = findRoute(data.graph, adj, fromNode, a.node); alt = !!p; }
    }
    if (!p) return { plan: null, alt: false, walkM: 0 };
    const end = p.coords[p.coords.length - 1];
    return { plan: p, alt, walkM: end ? distM(end, incident.point) : 0 };
  }, [data, adj, fromNode, incident, onRoad]);

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

  return (
    <div style={shell}>
      <OpsMap view={data.view} style={style} layers={layers} hidden={hidden}
              reachable={reach} incident={incident?.point ?? null}
              preview={plan?.plan?.coords ?? null}
              previewWalk={plan?.plan && incident ? [plan.plan.coords[plan.plan.coords.length - 1], incident.point] : null}
              units={units} feed={ops.feed} selectedSeg={seg} focus={focus}
              onPick={onPick} onSeg={(u) => { if (!picking) setSeg(u); }} />

      {/* ══ 좌측 — 접수 · 지령 · 판정 · 레이어 ═══════════════════ */}
      <aside style={panel}>
        <div style={head}>
          <div style={{ fontSize: 20, fontWeight: 800 }}>FireLane 관제</div>
          <div style={{ fontSize: 12, opacity: .7 }}>전남광주통합특별시 동구 동명동 · 도면 기반 1차 판정</div>
        </div>
        <div style={{ padding: "12px 16px 18px", overflowY: "auto", flex: 1 }}>
          <H>사건 접수</H>
          <div style={{ display: "flex", gap: 6 }}>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="상호 · 주소 · 건물 · 도로명"
                   style={input} />
            <button onClick={() => setPicking((x) => !x)}
                    style={{ ...btnSm, background: picking ? C.cta : "#fff", color: picking ? "#fff" : C.cta }}>
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
                  <span style={{ display: "block", fontSize: 11, color: C.panelSub }}>{h.addr || h.cat}</span>
                </button>
              ))}
            </div>
          )}
          {incident && (
            <div style={card}>
              <div style={{ fontSize: 12, color: C.danger, fontWeight: 800 }}>화재 · 접수 {hhmm(incident.at)}</div>
              <div style={{ fontSize: 16, fontWeight: 800, marginTop: 2 }}>{incident.label}</div>
            </div>
          )}

          <H>출동 지령</H>
          <label style={lab}>출발 센터</label>
          <select value={station?.id ?? ""} onChange={(e) => setStationId(e.target.value)} style={input}>
            {stations.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <label style={lab}>차량</label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {(fleet.fleet?.vehicles ?? []).map((v) => {
              const on = v.id === vehicle?.id;
              return (
                <button key={v.id} onClick={() => fleet.select(v.id)}
                        style={{ ...vehBtn, borderColor: on ? C.cta : C.sheetLine, background: on ? C.softBlue : "#fff" }}>
                  <VehicleArt kind={vehicleClass(v.label, v.id)} w={52} />
                  <span style={{ fontSize: 12, fontWeight: 800 }}>{displayName(v.label)}</span>
                  <span style={{ fontSize: 10, color: C.panelSub }}>{(v.station ?? "").replace(/119안전센터|119구조대/, "")} · 요구 {v.required_width_m.toFixed(1)}m</span>
                </button>
              );
            })}
          </div>
          {incident && plan && (
            <div style={{ ...card, borderColor: plan.plan ? (plan.alt ? C.warn : C.safe) : C.danger }}>
              {plan.plan ? (
                <>
                  <div style={{ fontWeight: 800, fontSize: 15 }}>
                    {fmtDur(travelSeconds(plan.plan))} · {(plan.plan.lengthM / 1000).toFixed(1)}km
                  </div>
                  <div style={{ fontSize: 12, color: C.panelSub, marginTop: 2 }}>
                    확인 필요 {plan.plan.edges.filter((e) => e.verdict === "needs_cv" || e.verdict === "unknown").length}개 ·
                    최소폭 {Math.min(...plan.plan.edges.map((e) => e.width_min_m ?? 99)).toFixed(1)}m / 요구 {need.toFixed(1)}m
                  </div>
                  {plan.alt && (
                    <div style={{ fontSize: 12, color: C.warnInk, fontWeight: 800, marginTop: 4 }}>
                      사건 지점까지 차량 경로 없음 → 대체 접근 지점, 이후 도보 약 {Math.round(plan.walkM)}m(직선)
                    </div>
                  )}
                </>
              ) : (
                <div style={{ fontWeight: 800, color: C.danger }}>
                  이 차종으로 {MAX_WALK_M}m 안에 닿는 접근 지점이 없다 — 다른 차종 · 센터
                </div>
              )}
            </div>
          )}
          <button disabled={!dispatchUrl || !plan?.plan}
                  onClick={() => dispatchUrl && window.open(dispatchUrl, "_blank")}
                  style={{ ...cta, opacity: dispatchUrl && plan?.plan ? 1 : .45 }}>
            내비로 출동 지령 »
          </button>
          <div style={{ fontSize: 11, color: C.panelSub, marginTop: 6, lineHeight: 1.5 }}>
            새 탭에 내비가 사건 · 차종 · 센터를 채운 채 열린다. 그 내비의 위치 · 공유가 이 화면으로 온다
            (같은 브라우저 탭끼리 — 서버 아님).
          </div>

          <H>판정 (영상판정 = CV)</H>
          {VERDICT_ORDER.filter((k) => style[k]).map((k) => {
            const off = hidden.has(k);
            return (
              <button key={k} style={{ ...legendRow, opacity: off ? .4 : 1 }}
                      onClick={() => setHidden((h) => { const n = new Set(h); if (n.has(k)) n.delete(k); else n.add(k); return n; })}>
                <i style={{ ...dot, background: style[k].color }} />
                <span style={{ flex: 1, textAlign: "left" }}>
                  <b>{style[k].label}</b>
                  <span style={{ display: "block", fontSize: 11, color: C.panelSub }}>{VERDICT_MEANING[k]}</span>
                </span>
                <b style={{ fontSize: 13 }}>{counts[k] ?? 0}</b>
              </button>
            );
          })}
          <div style={{ fontSize: 11, color: C.panelSub, marginTop: 4 }}>
            눌러서 숨기기 · 굵기는 최소 유효폭 비례 · 전 구간 현장 미검증
          </div>

          <H>레이어</H>
          {([
            ["reach", `도달 불가 사선 (${displayName(vehicle?.label ?? "기준 차량")} · ${station?.name ?? ""})`],
            ["cctvCov", "CCTV 영상판정 반경 25m"],
            ["ortho", "항공정사영상 25cm"],
            ["bldg", "건물 3D"],
          ] as [keyof OpsLayers, string][]).map(([k, t]) => (
            <label key={k} style={toggleRow}>
              <input type="checkbox" checked={layers[k]} onChange={() => setLayers((L) => ({ ...L, [k]: !L[k] }))} />
              {t}
            </label>
          ))}
          <div style={{ fontSize: 11, color: C.panelSub, marginTop: 6 }}>
            닿는 구간 {reach?.size ?? 0} / {data.graph.edges.length} · 옛 지도는 <a href="../" style={{ color: C.cta }}>여기</a>
          </div>
        </div>
      </aside>

      {/* ══ 우측 — 출동 중 · 공유 ════════════════════════════════ */}
      <div style={right}>
        <div style={liveCard}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <b style={{ fontSize: 15 }}>출동 중</b>
            <span style={{ fontSize: 11, color: C.panelSub }}>
              {link.current?.available === false ? "이 브라우저는 탭 연결을 못 한다" : `내비 ${units.length}대 연결`}
            </span>
          </div>
          {units.length === 0 && (
            <div style={{ fontSize: 12, color: C.panelSub, marginTop: 6 }}>
              연결된 내비가 없다 — 「내비로 출동 지령」 으로 연다.
            </div>
          )}
          {units.map((u) => {
            const stale = unitStale(u, now);
            return (
              <button key={u.unit} style={unitRow}
                      onClick={() => u.last.pos && setFocus({ n: Date.now(), at: u.last.pos, zoom: 17.2 })}>
                <span style={{ fontWeight: 800 }}>{u.last.vehicle}</span>
                <span style={{ fontSize: 12 }}>{u.last.title}</span>
                <span style={{ fontSize: 11, color: stale ? C.danger : C.panelSub }}>
                  {stale ? "연결 끊김" : u.last.remainM != null ? `남은 ${(u.last.remainM / 1000).toFixed(1)}km · 도착 ${u.last.etaText ?? "—"}` : "대기"}
                  {u.last.incident ? ` · ${u.last.incident.label}` : ""}
                </span>
              </button>
            );
          })}
        </div>
        {ops.feed.length > 0 && (
          <div style={{ ...liveCard, marginTop: 10, maxHeight: 320, overflowY: "auto" }}>
            <b style={{ fontSize: 15 }}>현장 공유</b>
            {ops.feed.map((f) => (
              <div key={f.shareId} style={feedRow}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 800, color: f.kind === "blocked" ? "#991b1b" : f.kind === "arrival" ? C.cta : C.warnInk }}>
                    {f.kind === "blocked" ? "통행 불가 신고" : f.kind === "arrival" ? "도착 보고" : "병목 공유"} · {hhmm(new Date(f.at))}
                  </div>
                  <div style={{ fontSize: 12 }}>{f.text}</div>
                </div>
                {f.ackedAt
                  ? <span style={{ fontSize: 12, color: C.safeInk, fontWeight: 800 }}>확인 {hhmm(new Date(f.ackedAt))}</span>
                  : <button style={ackBtn} onClick={() => { ack(f.shareId, f.unit); if (f.point) setFocus({ n: Date.now(), at: f.point, zoom: 17.5 }); }}>확인</button>}
              </div>
            ))}
          </div>
        )}
        {selEdge && (
          <SegCard e={selEdge} style={style} need={need} reachable={reach?.has(selEdge.seg_uid) ?? null}
                   vehicle={displayName(vehicle?.label ?? "기준 차량")} onClose={() => setSeg(null)} />
        )}
      </div>
    </div>
  );
}

function SegCard({ e, style, need, reachable, vehicle, onClose }: {
  e: GraphEdge; style: Bundle["graph"]["style"]; need: number; reachable: boolean | null;
  vehicle: string; onClose: () => void;
}) {
  const s = style[e.verdict];
  const margin = e.width_min_m != null ? e.width_min_m - need : null;
  const cctvOk = e.cctv_dist_m != null && e.cctv_dist_m <= 25;
  return (
    <div style={{ ...liveCard, marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <b style={{ fontSize: 15, flex: 1 }}>{e.seg_label ?? e.road_name ?? e.seg_uid}</b>
        <button onClick={onClose} style={{ border: "none", background: "none", fontSize: 18, cursor: "pointer" }}>✕</button>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
        <i style={{ ...dot, background: s?.color }} />
        <b>{s?.label ?? e.verdict}</b>
        <span style={{ fontSize: 11, color: C.panelSub }}>{VERDICT_MEANING[e.verdict]}</span>
      </div>
      <Row k="최소 · 최대 유효폭" v={`${e.width_min_m?.toFixed(1) ?? "—"} · ${e.width_max_m?.toFixed(1) ?? "—"}m`} />
      <Row k={`${vehicle} 요구폭 · 여유`} v={`${need.toFixed(1)}m · ${margin != null ? `${margin >= 0 ? "+" : ""}${margin.toFixed(1)}m` : "—"}`}
           warn={margin != null && margin < 0.5} />
      <Row k="측정 신뢰도 · 폭 표본" v={`${e.width_cov != null ? Math.round(e.width_cov * 100) + "%" : "—"} · ${e.n_sample ?? "—"}개`} />
      <Row k="가까운 CCTV" v={e.cctv_dist_m != null ? `${Math.round(e.cctv_dist_m)}m ${cctvOk ? "(영상판정 가능)" : "(25m 밖)"}` : "—"} />
      <Row k="길이" v={e.length_m != null ? `${Math.round(e.length_m)}m` : "—"} />
      <Row k="선택 센터에서" v={reachable == null ? "—" : reachable ? "도달 가능" : "도달 불가"} warn={reachable === false} />
      <div style={{ fontSize: 11, color: C.panelSub, marginTop: 8, lineHeight: 1.5 }}>
        폭은 도면 기반 미검증 값이다. 실시간 주정차 · 공사 · 회전 · 높이는 반영하지 않는다.
      </div>
    </div>
  );
}

function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0",
                  borderBottom: `1px solid ${C.sheetLine}` }}>
      <span style={{ color: C.panelSub }}>{k}</span>
      <b style={{ color: warn ? C.danger : C.panelInk }}>{v}</b>
    </div>
  );
}
function H({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 13, fontWeight: 800, margin: "16px 0 8px", color: C.panelInk }}>{children}</div>;
}
function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ ...shell, display: "grid", placeItems: "center" }}>{children}</div>;
}
function hhmm(d: Date): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function shortStation(raw: string): string {
  const m = raw.match(/광주-(.+)$/);
  return (m ? m[1] : raw).replace(/[-\s]/g, "");
}

const shell: React.CSSProperties = { position: "fixed", inset: 0, background: "#e8e4da", fontFamily: F.family, color: C.panelInk };
const panel: React.CSSProperties = {
  position: "absolute", top: 0, left: 0, bottom: 0, width: 400, background: "#fff", zIndex: 5,
  display: "flex", flexDirection: "column", boxShadow: "4px 0 18px rgba(0,0,0,.18)",
};
const head: React.CSSProperties = { background: "#0b1220", color: "#fff", padding: "14px 16px" };
const input: React.CSSProperties = {
  flex: 1, width: "100%", boxSizing: "border-box", border: `1.5px solid ${C.sheetLine}`, borderRadius: 10,
  padding: "9px 11px", fontSize: 14, fontFamily: F.family,
};
const btnSm: React.CSSProperties = {
  border: `1.5px solid ${C.cta}`, borderRadius: 10, padding: "0 10px", fontWeight: 800, fontSize: 12,
  cursor: "pointer", fontFamily: F.family, whiteSpace: "nowrap",
};
const list: React.CSSProperties = { border: `1px solid ${C.sheetLine}`, borderRadius: 10, marginTop: 6, overflow: "hidden" };
const listItem: React.CSSProperties = {
  display: "block", width: "100%", textAlign: "left", border: "none", borderBottom: `1px solid ${C.sheetLine}`,
  background: "#fff", padding: "8px 10px", cursor: "pointer", fontFamily: F.family, fontSize: 13,
};
const card: React.CSSProperties = {
  marginTop: 8, border: `2px solid ${C.sheetLine}`, borderRadius: 12, padding: "10px 12px", background: "#fff",
};
const lab: React.CSSProperties = { display: "block", fontSize: 11, color: C.panelSub, margin: "8px 0 4px" };
const vehBtn: React.CSSProperties = {
  display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2, border: "1.5px solid",
  borderRadius: 10, padding: "6px 8px", cursor: "pointer", fontFamily: F.family, color: C.panelInk,
};
const cta: React.CSSProperties = {
  width: "100%", marginTop: 10, border: "none", borderRadius: 12, padding: "13px 0",
  background: "linear-gradient(90deg,#1e7cf2,#3aa0ff)", color: "#fff", fontWeight: 800, fontSize: 16,
  cursor: "pointer", fontFamily: F.family,
};
const legendRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 10, width: "100%", border: "none", background: "none",
  padding: "5px 2px", cursor: "pointer", fontFamily: F.family, color: C.panelInk,
};
const dot: React.CSSProperties = { width: 14, height: 14, borderRadius: 7, flex: "0 0 auto", border: "2px solid rgba(0,0,0,.15)" };
const toggleRow: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, fontSize: 13, padding: "3px 0" };
const right: React.CSSProperties = { position: "absolute", top: 14, right: 14, width: 340, zIndex: 5 };
const liveCard: React.CSSProperties = {
  background: "#fff", borderRadius: 16, padding: "12px 14px", boxShadow: "0 8px 24px rgba(0,0,0,.2)",
};
const unitRow: React.CSSProperties = {
  display: "flex", flexDirection: "column", alignItems: "flex-start", width: "100%", gap: 2, marginTop: 8,
  border: `1px solid ${C.sheetLine}`, borderRadius: 10, padding: "8px 10px", background: "#f8fafc",
  cursor: "pointer", fontFamily: F.family, color: C.panelInk, textAlign: "left",
};
const feedRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8, padding: "8px 0", borderBottom: `1px solid ${C.sheetLine}`,
};
const ackBtn: React.CSSProperties = {
  border: "none", background: C.cta, color: "#fff", borderRadius: 8, padding: "7px 12px",
  fontWeight: 800, cursor: "pointer", fontFamily: F.family,
};

#!/usr/bin/env python3
"""
segments.py — 도로구간을 노딩해 통과판정 세그먼트 그래프를 만든다.

전제
  ingest.py 가 먼저 돌아야 한다. data/processed 의 road_link / road_rw /
  building / building_entrance / boundary_emd 를 입력으로 쓴다.

원칙
  1. 계산은 EPSG:5186. 표출만 4326. (ingest.py 와 동일)
  2. 동 경계로 clip 하지 않는다. clip 하면 그래프가 깨진다(연결요소 70개/최대 34%).
     buffer(GRAPH_BUFFER) 로 원본 형상을 유지한 채 넉넉히 담는다.
  3. 노딩은 unary_union 만으로 부족하다. T자 접합(끝점이 본선 '중간'에 접함)이
     밀리미터 단위로 벌어져 있어 위상이 안 생긴다. 끝점 투영 스냅이 필수.
       원본 40개 요소 / 93.3%  →  끝점투영 0.5m  6개 / 99.8%
  4. 폭 파라미터는 원본 도로구간(평균 76m)이 아니라 노딩 세그먼트(중앙 37m)
     기준으로 잡아야 한다. 절대값 필터를 그대로 옮기면 짧은 세그먼트가 전멸한다.

산출
  segments.geojson / segments_5186.gpkg / segments.schema.json
"""
from __future__ import annotations
import json, hashlib
from collections import Counter
from pathlib import Path

import geopandas as gpd, numpy as np, networkx as nx, shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
OUT  = ROOT / "data" / "processed"
CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"

EMD_CD        = "12210108"   # 동명동
GRAPH_BUFFER  = 1500.0       # 안전센터(대인 1.0km / 지산 1.2km)까지 포함
KEEP_BUFFER   = 50.0         # 산출물에 남길 범위
SNAP_TOL      = 0.5          # 끝점 투영 반경. T자 접합 해소
XSEC_EXCL     = 5.0          # 교차로 노드 제외 반경. blob 폭 폭발 방지
WMAX_CAP      = 40.0         # 담~담 상한. 15m로 잡으면 대로가 전멸한다
MIN_SEG_LEN   = 3.0          # 이하는 교차로 파편. 폭 미산출 후 인접 상속
TRUCK, PARK   = 3.0, 2.0     # 소방펌프차 전폭(사이드미러 포함) / 주차 1대 노면점유
STATIONS = {                 # 출동은 소방서가 아니라 119안전센터에서 나간다
    "대인119안전센터": (126.914765, 35.154579),
    "지산119안전센터": (126.938531, 35.149963),
}


def load(key):
    return gpd.read_file(OUT / f"{key}_5186.gpkg").to_crs(CRS_M)


def endpoint_snap(lines, tol=SNAP_TOL):
    tree, out = STRtree(lines), []
    for i, ln in enumerate(lines):
        c = list(ln.coords)
        for idx in (0, -1):
            p, best, bd = Point(c[idx]), None, tol
            for j in tree.query(p.buffer(tol)):
                if j == i:
                    continue
                d = lines[j].distance(p)
                if 0 < d < bd:
                    bd, best = d, lines[j]
            if best is not None:
                q = nearest_points(best, p)[0]
                c[idx] = (q.x, q.y)
        out.append(LineString(c))
    return out


def main():
    emd = load("boundary_emd")
    poly = shapely.make_valid(emd.loc[emd.EMD_CD == EMD_CD, "geometry"].iloc[0])
    road = load("road_link")
    rw   = load("road_rw")
    bld  = load("building")
    ent  = load("building_entrance")

    raw = [g for g in road[road.intersects(poly.buffer(GRAPH_BUFFER))].geometry
           if g is not None and "Line" in g.geom_type]
    G = nx.Graph()
    for s in unary_union(endpoint_snap(raw)).geoms:
        c = list(s.coords)
        a, b = tuple(round(v, 3) for v in c[0]), tuple(round(v, 3) for v in c[-1])
        if a != b:
            G.add_edge(a, b, length=s.length, geom=s)
    G = G.subgraph(max(nx.connected_components(G),
        key=lambda c: sum(d["length"] for _, _, d in G.subgraph(c).edges(data=True)))).copy()

    nodes = list(G.nodes); npts = np.array(nodes)
    snapn = lambda x, y: nodes[int(np.argmin((npts[:, 0]-x)**2 + (npts[:, 1]-y)**2))]
    tgts = {snapn(g.x, g.y) for g in ent[ent.within(poly)].geometry}
    use = Counter()
    for lon, lat in STATIONS.values():
        p0 = gpd.GeoSeries([Point(lon, lat)], crs=CRS_W).to_crs(CRS_M).iloc[0]
        pa = nx.single_source_dijkstra_path(G, snapn(p0.x, p0.y), weight="length")
        for t in tgts:
            if t in pa:
                pp = pa[t]
                for a, b in zip(pp, pp[1:]):
                    use[frozenset((a, b))] += 1

    # 접근 회랑: 최단경로 중 동 밖 구간. 표출 스코프 산정에 쓴다.
    corr = []
    for k, v in use.items():
        a, b = tuple(k)
        if not (poly.contains(Point(a)) and poly.contains(Point(b))):
            e = G.edges[a, b]
            corr.append({"usage": v, "geometry": e["geom"]})
    if corr:
        gpd.GeoDataFrame(corr, crs=CRS_M).to_file(OUT/"corridor_5186.gpkg", driver="GPKG", layer="corridor")
        print(f"접근 회랑 {len(corr)}엣지 / {sum(c['geometry'].length for c in corr):,.0f}m")

    rw_u  = unary_union([shapely.make_valid(g) for g in rw[rw.intersects(poly.buffer(80))].geometry])
    bld_u = unary_union([shapely.make_valid(g) for g in bld[bld.intersects(poly.buffer(80))].geometry])
    deg = Counter()
    for a, b in G.edges():
        deg[a] += 1; deg[b] += 1
    xn = unary_union([Point(p) for p, d in deg.items() if d >= 3])

    def measure(s, t):
        p = s.interpolate(t)
        a, b = s.interpolate(max(t-.5, 0)), s.interpolate(min(t+.5, s.length))
        dx, dy = b.x-a.x, b.y-a.y; L = np.hypot(dx, dy)
        if L == 0:
            return None, None
        ux, uy = -dy/L, dx/L
        r = LineString([(p.x-ux*60, p.y-uy*60), (p.x+ux*60, p.y+uy*60)])
        A = B = None
        sg = r.intersection(rw_u)                      # 노면폭 = 하한
        if not sg.is_empty:
            pr = [sg] if sg.geom_type == "LineString" else [q for q in sg.geoms if q.geom_type == "LineString"]
            v = max((q.length for q in pr if q.distance(p) < 0.6), default=None)
            if v and 0.3 < v < 30:
                A = v
        sg = r.intersection(bld_u)                     # 담~담 = 상한
        if not sg.is_empty:
            pr = [sg] if sg.geom_type == "LineString" else [q for q in sg.geoms if q.geom_type == "LineString"]
            s1 = min((q.distance(p) for q in pr if (q.centroid.x-p.x)*ux + (q.centroid.y-p.y)*uy < 0), default=None)
            s2 = min((q.distance(p) for q in pr if (q.centroid.x-p.x)*ux + (q.centroid.y-p.y)*uy > 0), default=None)
            if s1 is not None and s2 is not None and 0.3 < s1+s2 < WMAX_CAP:
                B = s1 + s2
        return A, B

    def widths(s):
        A, B, fb = [], [], False
        for t in np.arange(1.0, max(s.length-1.0, 1.5), 2.0):
            if xn.distance(s.interpolate(t)) < XSEC_EXCL:
                continue
            a, b = measure(s, t)
            if a: A.append(a)
            if b: B.append(b)
        if not A or not B:                              # 짧은 세그먼트 폴백
            fb = True
            for t in (s.length/2, s.length*.35, s.length*.65):
                a, b = measure(s, t)
                if a and not A: A.append(a)
                if b and not B: B.append(b)
        return (round(min(A), 2) if A else None, round(min(B), 2) if B else None, fb)

    def verdict(wmin, wmax):
        # 노면폭만으로 결론 나면 담~담은 불필요 (대로는 건물이 멀어 wmax가 null)
        if wmin is not None and wmin >= TRUCK + 2*PARK: return "clear"
        if wmax is not None and wmax < TRUCK:           return "blocked"
        if wmin is None or wmax is None:                return "unknown"
        if wmin >= TRUCK + PARK:                        return "likely_clear"
        return "needs_cv"

    rec = {}
    for i, (a, b, d) in enumerate(G.edges(data=True)):
        g = d["geom"]
        if not g.intersects(poly.buffer(KEEP_BUFFER)):
            continue
        sid = f"DM{i:05d}"
        short = g.length < MIN_SEG_LEN
        wmin, wmax, fb = (None, None, False) if short else widths(g)
        rec[sid] = dict(seg_id=sid, width_min_m=wmin, width_max_m=wmax,
                        verdict="fragment" if short else verdict(wmin, wmax),
                        width_verified=False, midpoint_fallback=fb, inherited=False,
                        route_usage=use.get(frozenset((a, b)), 0),
                        length_m=round(g.length, 1), _n=(a, b), geometry=g)

    bynode = {}
    for sid, r in rec.items():
        for n in r["_n"]:
            bynode.setdefault(n, []).append(sid)
    for sid, r in rec.items():                          # 파편은 인접 최솟값 상속(보수적)
        if r["verdict"] != "fragment":
            continue
        nb = [rec[s] for n in r["_n"] for s in bynode[n]
              if s != sid and rec[s]["width_min_m"] is not None]
        if nb:
            r["width_min_m"] = round(min(x["width_min_m"] for x in nb), 2)
            mx = [x["width_max_m"] for x in nb if x["width_max_m"] is not None]
            r["width_max_m"] = round(min(mx), 2) if mx else None
            r["verdict"] = verdict(r["width_min_m"], r["width_max_m"])
            r["inherited"] = True
    for r in rec.values():
        r.pop("_n")

    g = gpd.GeoDataFrame(list(rec.values()), crs=CRS_M)
    g.to_file(OUT / "segments_5186.gpkg", driver="GPKG", layer="segments")
    g.to_crs(CRS_W).to_file(OUT / "segments.geojson", driver="GeoJSON")
    h = hashlib.sha256((OUT / "segments.geojson").read_bytes()).hexdigest()
    (OUT / "segments.schema.json").write_text(json.dumps({
        "crs": CRS_W, "sha256": h, "count": len(g), "width_verified": False,
        "note": "width_* 는 D-25 레이저 실측 전 미검증 값. verdict 문자열만 참조하고 임계값을 하드코딩하지 말 것.",
        "fields": {
            "seg_id": "str, 불변 키",
            "width_min_m": "float|null 노면폭(하한). road_rw 트랜섹트",
            "width_max_m": "float|null 담~담(상한). building 트랜섹트. 대로는 null(건물이 40m 밖)",
            "verdict": "clear|likely_clear|needs_cv|blocked|unknown",
            "width_verified": "bool",
            "midpoint_fallback": "bool 교차로 제외로 샘플 0 → 중점 측정",
            "inherited": "bool 3m 미만 파편 → 인접 세그먼트 최솟값 상속",
            "route_usage": "int 안전센터 2곳 → 건물출입구 최단경로 사용횟수",
            "length_m": "float"},
        "params": {"truck_width_m": TRUCK, "park_occupancy_m": PARK,
                   "intersection_exclusion_m": XSEC_EXCL, "wmax_cap_m": WMAX_CAP,
                   "min_seg_len_m": MIN_SEG_LEN, "snap_tol_m": SNAP_TOL},
        "verdict_rule": ["wmin >= 7.0 -> clear (담~담 불요)", "wmax < 3.0 -> blocked",
                         "wmin or wmax null -> unknown", "wmin >= 5.0 -> likely_clear",
                         "else -> needs_cv"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(g.verdict.value_counts().to_string())
    print(f"\n→ segments {len(g)} · 경로사용 {(g.route_usage>0).sum()} · sha {h[:16]}")


if __name__ == "__main__":
    main()

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
# 소방청 「2025 화재현장 골든타임 확보 종합대책」 기준
#   진입불가  폭 2m 이하, 또는 이동불가 장애물로 진입 불가한 구간이 100m 이상
#   진입곤란  폭 3m 이상 도로 중 장애물·상습주차로 상시 장애, 구간 100m 이상
#   기준 차량 중형펌프차량 폭 2.5m
# 임의 임계값이 아니라 국가 기준이다. 바꾸지 말 것.
TRUCK      = 2.5     # 중형펌프차량 전폭
PARK       = 2.0     # 주차 1대 노면점유
NFA_RUN_M  = 100.0   # 소방청 지정 최소 연속 구간장

# CCTV 유효 범위. 이 거리를 넘으면 호모그래피 오차가 급격히 커진다.
# → 영상판정이 성립하지 않는다. CCTV가 없는 것과 같다.
# 25m 는 잠정값이다. D-25 실측으로 검증 대상.
CCTV_RANGE = 25.0
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

    # CCTV 유효 범위. needs_cv 구간이 이 안에 없으면 영상판정 자체가 불가능하다.
    cctv = gpd.read_file(OUT/"cctv_5186.gpkg").to_crs(CRS_M)
    cctv_u = unary_union(list(cctv.geometry))

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
        """소방청 기준 판정 4종.

            blocked   wmax <  2.5   중형펌프차 폭 미달. 장애물이 없어도 못 지나간다
            clear     wmin >= 4.5   주차 1대가 있어도 통과. 영상판정 불필요
            unknown   폭 산출 불가
            needs_cv  나머지        상습주차 여부로 갈린다. 영상판정 대상
        """
        if wmax is not None and wmax < TRUCK:         return "blocked"
        if wmin is not None and wmin >= TRUCK + PARK: return "clear"
        if wmin is None or wmax is None:              return "unknown"
        return "needs_cv"

    rec = {}
    for i, (a, b, d) in enumerate(G.edges(data=True)):
        g = d["geom"]
        if not g.intersects(poly.buffer(KEEP_BUFFER)):
            continue
        sid = f"DM{i:05d}"
        short = g.length < MIN_SEG_LEN
        wmin, wmax, fb = (None, None, False) if short else widths(g)
        v = "fragment" if short else verdict(wmin, wmax)

        # 영상판정 가능성. 구간에서 가장 가까운 CCTV 까지의 거리로 판단한다.
        d_cctv = round(g.distance(cctv_u), 1)
        cv_ok = d_cctv <= CCTV_RANGE

        # needs_cv 인데 CCTV 사각이면 영상판정이 성립하지 않는다.
        # 도면으로도 확정 못 하고 영상으로도 확정 못 하므로 unknown 이다.
        # blocked / clear 는 도면만으로 확정되므로 CCTV 와 무관하다.
        reason = None
        if v == "needs_cv" and not cv_ok:
            v, reason = "unknown", "no_cctv"
        elif v == "unknown":
            reason = "width"

        rec[sid] = dict(seg_id=sid, width_min_m=wmin, width_max_m=wmax,
                        verdict=v, unknown_reason=reason,
                        cctv_dist_m=d_cctv, cv_feasible=bool(cv_ok),
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
            v2 = verdict(r["width_min_m"], r["width_max_m"])
            if v2 == "needs_cv" and not r["cv_feasible"]:
                v2, r["unknown_reason"] = "unknown", "no_cctv"
            elif v2 == "unknown":
                r["unknown_reason"] = "width"
            r["verdict"] = v2
            r["inherited"] = True
    # 소방청 지정 기준의 "구간 100m 이상"은 세그먼트 단위가 아니라 연속 구간 단위다.
    # 같은 판정을 가진 인접 세그먼트를 이어붙여 연속 길이를 잰다.
    import networkx as _nx
    for target in ("blocked", "needs_cv"):
        sub = _nx.Graph()
        for sid, r in rec.items():
            if r["verdict"] == target:
                sub.add_edge(*r["_n"], sid=sid, length=r["length_m"])
        for comp in _nx.connected_components(sub):
            g2 = sub.subgraph(comp)
            run = sum(d["length"] for _, _, d in g2.edges(data=True))
            for _, _, d in g2.edges(data=True):
                rec[d["sid"]]["run_length_m"] = round(run, 1)
                rec[d["sid"]]["nfa_designated"] = bool(run >= NFA_RUN_M)
    for r in rec.values():
        r.setdefault("run_length_m", None)
        r.setdefault("nfa_designated", False)
        r.pop("_n")

    g = gpd.GeoDataFrame(list(rec.values()), crs=CRS_M)

    # ── 소방서 지정 구간 대조 ────────────────────────────────
    # 동부소방서 소방통로확보대상 지역 현황(2025-07-31)의 폭과 비교한다.
    # 좌표가 없어 도로명 단위로만 매칭되므로 참고값이다.
    # 소방서가 지정한 것은 그 도로명 중 가장 좁은 구간이므로,
    # 우리 값도 최솟값 쪽으로 비교하는 것이 타당하다.
    fa = ROOT/"data"/"raw"/"safety"/"safety_fire_access_gj_dong_20250731.csv"
    if fa.exists():
        import csv, re
        rows = list(csv.DictReader(fa.open(encoding="cp949")))
        road = gpd.read_file(OUT/"road_link_5186.gpkg").to_crs(CRS_M)
        print("\n[소방서 지정 구간 대조]")
        for r in rows:
            for rn in set(re.findall(r"[가-힣]+로\d*번?길", r["지역명"])):
                sel = road[road.RN == rn]
                if not len(sel):
                    continue
                ru = unary_union(list(sel.geometry))
                hit = g[g.geometry.buffer(1).intersects(ru)].dropna(subset=["width_min_m"])
                if not len(hit):
                    continue
                w_nfa = r["폭(m)"]
                try:
                    wf = float(str(w_nfa).split("~")[0])
                except ValueError:
                    continue
                # 소방서 기록폭은 구간 대표폭으로 보인다. 최솟값이 아니라 중앙값과 비교한다.
                # (하위10% 로 비교하면 교차로 근처 극협소 지점을 잡아 -3~-7m 로 벌어진다)
                med = hit.width_min_m.median()
                print(f"  {rn:14s} 소방서 {w_nfa:>7s}m │ 우리 중앙 {med:5.2f}m "
                      f"({med - wf:+.2f}) │ 세그 {len(hit):3d} │ "
                      + " ".join(f"{k}:{v}" for k, v in hit.verdict.value_counts().items()))
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
            "verdict": "clear|needs_cv|blocked|unknown",
            "width_verified": "bool",
            "midpoint_fallback": "bool 교차로 제외로 샘플 0 → 중점 측정",
            "inherited": "bool 3m 미만 파편 → 인접 세그먼트 최솟값 상속",
            "route_usage": "int 안전센터 2곳 → 건물출입구 최단경로 사용횟수",
            "length_m": "float 이 구간의 길이(m)",
            "run_length_m": "float|null 같은 판정이 이어지는 연속 구간장(m)",
            "nfa_designated": "bool 소방청 지정 기준(연속 100m 이상) 충족",
            "cctv_dist_m": "float 가장 가까운 CCTV 까지의 거리(m)",
            "cv_feasible": "bool CCTV 유효범위(25m) 안. 영상판정 성립 여부",
            "unknown_reason": "null|width|no_cctv unknown 이 된 이유"},
        "standard": "소방청 2025 화재현장 골든타임 확보 종합대책 (중형펌프차 2.5m, 구간 100m)",
        "params": {"truck_width_m": TRUCK, "park_occupancy_m": PARK, "nfa_run_m": NFA_RUN_M, "cctv_range_m": CCTV_RANGE,
                   "intersection_exclusion_m": XSEC_EXCL, "wmax_cap_m": WMAX_CAP,
                   "min_seg_len_m": MIN_SEG_LEN, "snap_tol_m": SNAP_TOL},
        "verdict_rule": ["wmax <  2.5 -> blocked (중형펌프차 폭 미달)",
                         "wmin >= 4.5 -> clear (주차 1대가 있어도 통과)",
                         "wmin or wmax null -> unknown (reason=width)",
                         "needs_cv 인데 CCTV 25m 밖 -> unknown (reason=no_cctv). 영상판정 불가",
                         "else -> needs_cv (상습주차 여부로 갈림. 영상판정 대상)"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(g.verdict.value_counts().to_string())
    print(f"\n→ segments {len(g)} · 경로사용 {(g.route_usage>0).sum()} · sha {h[:16]}")


if __name__ == "__main__":
    main()

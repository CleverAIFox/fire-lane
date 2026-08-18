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

import geopandas as gpd
import pandas as pd, numpy as np, networkx as nx, shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW, PROCESSED, WEB  # noqa: E402
from segkey import attach_seg_uid, uid_retention, save_uid_map  # noqa: E402
OUT = PROCESSED

CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"

# 진단 스위치. 재현성 있게 저장소에 남긴다.
#   FIRE_LANE_NO_MERGE=1        산출단위 병합을 끈다. 병합 전 기준값을 뽑을 때
#   FIRE_LANE_DEBUG_SEG=DM03223 해당 단위의 표본을 전부 덤프한다
#   FIRE_LANE_DEBUG_XY=192837,284314   좌표 최근접 단위를 덤프한다
#                               seg_id 는 실행 간 유지되지 않는다. XY 를 쓸 것
#   FIRE_LANE_MIX_SRC=1         구간 폭을 표본 혼합 집합의 최솟값으로 되돌린다(종전).
#   FIRE_LANE_OLD_SNAP=1        snap 을 소스별이 아닌 종전 방식으로 되돌린다.
#                               소스별 snap 도입 전후를 한 바이너리로 비교할 때
import os as _os
NO_MERGE  = _os.environ.get("FIRE_LANE_NO_MERGE") == "1"
DEBUG_SEG = [x.strip() for x in
             _os.environ.get("FIRE_LANE_DEBUG_SEG", "").split(",") if x.strip()]
DEBUG_XY  = _os.environ.get("FIRE_LANE_DEBUG_XY", "").strip()
OLD_SNAP  = _os.environ.get("FIRE_LANE_OLD_SNAP") == "1"
MIX_SRC   = _os.environ.get("FIRE_LANE_MIX_SRC") == "1"
_DBG = {"on": False}

EMD_CD        = "12210108"   # 동명동
GRAPH_BUFFER  = 1500.0       # 안전센터(대인 1.0km / 지산 1.2km)까지 포함
KEEP_BUFFER   = 50.0         # 산출물에 남길 범위
SNAP_TOL      = 0.5          # 끝점 투영 반경. T자 접합 해소
SNAP_MAX      = 6.0          # 측정지점을 노면 안으로 끌어오는 최대 거리
NODE_TOL      = 0.5          # 노드 동일시 반경. SNAP_TOL 과 같은 값을 쓴다.
                             # mm 반올림으로 노드를 식별하면 4cm 떨어진 두 점이
                             # 별개 노드가 되고 그 사이에 길이 0.04m 엣지가 남는다.
                             # 피처로서 의미가 없고 폭도 잴 수 없다(51개).
XSEC_EXCL     = 5.0          # 교차로 노드 제외 반경. blob 폭 폭발 방지
WMAX_CAP      = 60.0         # 담~담 상한. 15m로 잡으면 대로가 전멸한다
SNAP_TRUST    = 2.0          # 이보다 많이 끌어온 표본은 폭 산출에서 뺀다.
COV_MIN       = 0.5          # 채택 자격. 구간의 절반 미만을 잰 소스는 대표시키지 않는다.
#   소스 우선순위(결정 63)를 바꾸는 것이 아니라 자격 미달을 거르는 것이다.
#   자격 미달로 탈락하면 다음 순위 소스가 자동으로 올라간다.
#   근거: 정상 구간(<=15m)의 채택소스 커버율은 중앙 1.0 · p10 0.667 인데
#   width_min>30m 이상값 43건은 0.038~0.286 이다. 두 무리가 겹치지 않는다.
#   준법로(DM01608)는 ngii 가 26표본 중 1개(cov 0.038)를 쟀고 그 값이 53.2m 로
#   구간 폭이 됐다. 나머지 23개는 silpok 1.30m 였다.
#   snap 은 측정점을 도로면 안으로 끌어온 거리다. 크다는 것은 그 지점에
#   그 소스의 도로면이 없다는 뜻이고, 끌어온 만큼 옆 도로를 잰 값이 된다.
#   준법로(DM01609)는 표본 26개 중 23개가 silpok 1.30m 였는데,
#   ngii 3개(snap 1.18/3.18/5.18)가 우선순위로 채택돼 wmin 이 53.1m 로 나갔다.
#   width_min>30m 47구간이 전부 clear 로 판정되던 원인이다(미탐 방향).
#   SNAP_MAX(6.0)는 측정 시도 한계이고 이 값은 신뢰 한계다. 별개다.
MIN_SEG_LEN   = 3.0          # 이하는 교차로 파편. 폭 미산출 후 인접 상속
# 소방청 「2025 화재현장 골든타임 확보 종합대책」 기준
#   진입불가  폭 2m 이하, 또는 이동불가 장애물로 진입 불가한 구간이 100m 이상
#   진입곤란  폭 3m 이상 도로 중 장애물·상습주차로 상시 장애, 구간 100m 이상
#   기준 차량 중형펌프차량 폭 2.5m
# 임의 임계값이 아니라 국가 기준이다. 바꾸지 말 것.
# 소방청 기준의 2.5m 는 "차량 전폭"이다. 실제 통과에는 사이드미러와 조향 여유가
# 필요하고, 2026-08-06 현장 답사에서 3.0m 를 안정적 통과 하한으로 판단했다.
# 국가 기준보다 보수적인 방향이므로 규정과 충돌하지 않는다.
TRUCK      = 3.0     # 통과 하한 (차량 전폭 2.5m + 사이드미러·조향 여유)
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
    # 가로등. 지번 단위 회로 대표점이라 개별 폴 위치가 아니다.
    # 마커 표현은 streetlight.py 가 담당한다(group-by + count, 반경 50m 원).
    # 여기서는 구간 피처 light_count 로만 쓴다. MASTER §6 (2026-08-14 개정)
    # ★ 정본은 processed 다. RAW 를 직접 읽지 않는다.
    #   RAW 를 읽으면 ingest(1786, 스코프 필터 후)와 여기(3805, 전체)가
    #   서로 다른 값을 쓰게 된다. 실제로 그랬다. (2026-08-14)
    _lp = [str(OUT / "streetlight_5186.gpkg")] if (OUT / "streetlight_5186.gpkg").exists() else []
    _light = None
    if _lp:
        _light = gpd.read_file(_lp[0]).to_crs(CRS_M)
        print(f"  가로등 {len(_light)}등 (processed 정본)")
    else:
        # ★ 조용히 넘기지 않는다. 없으면 light_count 가 전 구간 0 이 되는데
        #   파이프라인은 OK 를 찍는다. 2026-08-14 에 실제로 겪었다.
        print("  ! streetlight_5186.gpkg 없음 — light_count 가 전부 0 이 된다")

    ngii = load("ngii_road")
    # 1:1,000 수치지형도 도로경계(도엽 20장 병합). 폭 산출 주 소스.
    try:
        ngii1k = load("ngii1k")
    except Exception:
        ngii1k = None
        print("  ! ngii1k_5186.gpkg 없음 — 1:5,000 으로 대체")       # 결정 63: 폭 주 소스(수치지도 도로경계면)
    bld  = load("building")
    ent  = load("building_entrance")

    raw = [g for g in road[road.intersects(poly.buffer(GRAPH_BUFFER))].geometry
           if g is not None and "Line" in g.geom_type]
    _E = []
    for s in unary_union(endpoint_snap(raw)).geoms:
        c = list(s.coords)
        _E.append((c[0], c[-1], s))

    # 노드 접합. 끝점을 NODE_TOL 안에서 union-find 로 묶고 무게중심을 대표점으로 쓴다.
    # 접합 후 양 끝이 같은 노드가 된 엣지는 자기루프이므로 버린다. 이것이 §4 의
    # 마이크로 엣지(길이 0.0~0.5m)다. 잘라낸 것이 아니라 애초에 노드가 하나였다.
    _pts = [Point(q) for e in _E for q in (e[0], e[1])]
    _tree = STRtree(_pts)
    _par = list(range(len(_pts)))

    def _find(i):
        while _par[i] != i:
            _par[i] = _par[_par[i]]
            i = _par[i]
        return i

    for i, pt in enumerate(_pts):
        for j in _tree.query(pt.buffer(NODE_TOL)):
            j = int(j)
            if j != i and _pts[i].distance(_pts[j]) <= NODE_TOL:
                ri, rj = _find(i), _find(j)
                if ri != rj:
                    _par[ri] = rj
    _grp = {}
    for i in range(len(_pts)):
        _grp.setdefault(_find(i), []).append(i)
    _key, _dmax = {}, 0.0
    for _, mem in _grp.items():
        cx = sum(_pts[m].x for m in mem) / len(mem)
        cy = sum(_pts[m].y for m in mem) / len(mem)
        k = (round(cx, 3), round(cy, 3))
        for m in mem:
            _key[m] = k
            _dmax = max(_dmax, np.hypot(_pts[m].x - cx, _pts[m].y - cy))

    G = nx.Graph()
    _loop, _dups = 0, []
    for i, (_, _, s) in enumerate(_E):
        a, b = _key[2*i], _key[2*i+1]
        if a == b:
            _loop += 1
            continue
        if G.has_edge(a, b):
            # 같은 노드쌍에 두 형상. nx.Graph 는 하나만 담으므로 하나는 버려진다.
            # 무엇을 버렸는지 남긴다. 길이비가 1.0 에 가까우면 같은 도로가 두 번
            # 그려진 중복이고 무해하다. 크게 벌어지면 별개 경로(우회로·측도)를
            # 지운 것이므로 그래프 결함이다.
            _o = G.edges[a, b]["geom"]
            _kept, _lost = (_o, s) if _o.length <= s.length else (s, _o)
            _dups.append((_kept.length, _lost.length, _lost.centroid))
            if s.length >= _o.length:
                continue           # 짧은 쪽만 남긴다(보수적)
        G.add_edge(a, b, length=s.length, geom=s)
    print(f"  노드접합 {NODE_TOL}m · 엣지 {len(_E)} → {G.number_of_edges()}"
          f" (자기루프 {_loop} · 병렬 {len(_dups)}) · 노드 최대이동 {_dmax:.3f}m")
    # 최대 컴포넌트만 남긴다. 나머지는 스코프 경계에서 잘린 자투리다.
    # ★ 몇 개를 버리는지 찍는다. 안 찍으면 그 구역이 판정에서 통째로 빠져도
    #   아무도 모른다. light_count 가 0 인 채 OK 를 찍던 것과 같은 종류다.
    _ncomp = nx.number_connected_components(G)
    _n0, _e0 = G.number_of_nodes(), G.number_of_edges()
    G = G.subgraph(max(nx.connected_components(G),
        key=lambda c: sum(d["length"] for _, _, d in G.subgraph(c).edges(data=True)))).copy()
    print(f"  최대성분 채택: 컴포넌트 {_ncomp} → 1 · "
          f"노드 {_n0}→{G.number_of_nodes()} · 엣지 {_e0}→{G.number_of_edges()}")

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

    keep = poly.buffer(KEEP_BUFFER)
    if corr:
        keep = keep.union(unary_union([c["geometry"] for c in corr]).buffer(70))

    # 결정 63 — 폭 주 소스 = 수치지도 도로경계면(NF_A_A01000), 폴백 = 실폭도로.
    # 두 소스는 경쟁이 아니라 상보 관계다. 수치지도는 넓은 길을 정확히 그리지만
    # 보행자 통로급 최협소 골목을 도로면으로 아예 그리지 않는다(표본 100 중 커버 70).
    # 나머지를 실폭도로가 메운다.
    _clip = keep.buffer(20)      # 세그먼트 스코프(동명동+회랑)와 일치시킨다
    def _seal(polys):
        """도로 폴리곤을 하나로 합친다.

        원본은 도로별·블록별로 쪼개져 있고 좌표가 mm 단위로 어긋나 있다.
        unary_union 만으로는 인접면이 안 붙어 얇은 틈이 경계선으로 남고,
        법선이 그 경계에서 끊겨 폭이 0.5m 로 나온다(중앙로 실측 사례).
        노딩에서 겪은 것과 같은 문제다(§3-2 T자 접합).
        살짝 부풀렸다 되돌려 틈을 닫는다.
        """
        u = unary_union([shapely.make_valid(g) for g in polys])
        return u.buffer(0.15, join_style=2).buffer(-0.15, join_style=2)

    ngii1k_u = (_seal(ngii1k[ngii1k.intersects(_clip)].geometry)
                if ngii1k is not None and len(ngii1k) else None)
    ngii_u = _seal(ngii[ngii.intersects(_clip)].geometry)
    rw_u   = _seal(rw[rw.intersects(_clip)].geometry)
    bld_u = unary_union([shapely.make_valid(g) for g in bld[bld.intersects(poly.buffer(80))].geometry])
    deg = Counter()
    for a, b in G.edges():
        deg[a] += 1; deg[b] += 1
    xn = unary_union([Point(p) for p, d in deg.items() if d >= 3])

    # ── 교차부 형상 (A0080000 평면교차점) ─────────────────────
    # 종전에는 노드에서 XSEC_EXCL(5.0m) 이내를 일괄 제외했다. 눈대중 반경이라
    # 양쪽으로 틀렸다 — 실제 교차부 등가반경은 중앙 3.2m · p90 7.5m 라
    # 작은 교차부에서는 과하게 도려내 표본을 죽이고, 큰 교차부에서는 부족해
    # 오염이 샜다. 동명로25번길 t=29·31(끝에서 5.1m)이 후자다.
    # NGII 가 실제 교차부 폴리곤을 준다(스코프 내 696건, 구간의 79%를 덮는다).
    # 폴리곤이 없는 교차로는 기존 반경 방식으로 폴백한다.
    _xp = OUT / "ngii1k_xsec_5186.gpkg"
    xsec_poly = None
    if _xp.exists():
        try:
            _xg = gpd.read_file(_xp, layer="ngii1k_xsec").to_crs(CRS_M)
            xsec_poly = unary_union(_xg.geometry.buffer(0))
            print(f"  교차부 폴리곤 {len(_xg)}건 적용")
        except Exception as _e:
            print(f"  ! 교차부 폴리곤 로드 실패 — 반경 {XSEC_EXCL}m 폴백: {_e}")
    else:
        # 조용히 넘기지 않는다. 없으면 판정 기준이 달라진다.
        print(f"  ! ngii1k_xsec_5186.gpkg 없음 — 반경 {XSEC_EXCL}m 폴백")

    def measure(s, t):
        p0 = s.interpolate(t)
        a, b = s.interpolate(max(t-.5, 0)), s.interpolate(min(t+.5, s.length))
        dx, dy = b.x-a.x, b.y-a.y; L = np.hypot(dx, dy)
        if L == 0:
            return None, None, None, (None, None, None), "L0", {}
        ux, uy = -dy/L, dx/L

        def _pt_for(u):
            """이 소스 기준으로 잴 지점. 소스마다 독립으로 판정한다.

            종전에는 세 소스 중 하나라도 p 를 덮으면 snap 을 통째로 건너뛰었다.
            실폭도로의 1.8m 조각이 p 를 덮고 있으면 주 소스인 1:1,000 이
            p 를 안 덮어도 아무 조치가 없었고, 그 소스는 no_run 으로 조용히
            빠졌다(한 구간 30표본 중 20표본). 결정 63 의 주 소스가 무력화된다.

            중심선이 노면 밖이면 법선이 도로면과 안 만나 폭이 안 나온다.
            도로명주소 중심선은 위상용이라 실측 노면과 어긋난다.
            재는 지점만 가장 가까운 노면 안으로 끌어온다(최대 SNAP_MAX).
            """
            if u is None or u.is_empty:
                return None, None
            if u.covers(p0):
                return p0, 0.0
            d = u.distance(p0)
            if d > SNAP_MAX:
                return None, None
            q = nearest_points(u, p0)[0]
            if d > 1e-9:
                # 경계선 위가 아니라 노면 안쪽으로 들여놔야 한다.
                # interpolate(length+0.2) 는 shapely 가 끝점으로 잘라 경계에 얹히고,
                # 거기서 법선을 그으면 접선이 되어 폭이 안 나온다. 방향벡터로 민다.
                _ux2, _uy2 = (q.x - p0.x) / d, (q.y - p0.y) / d
                for _push in (0.3, 0.8, 1.5):
                    _c = Point(q.x + _ux2 * _push, q.y + _uy2 * _push)
                    if u.covers(_c):
                        return _c, round(d, 2)
            return q, round(d, 2)

        def _span(poly_u, p):
            """법선을 도로면으로 자른 조각들을 이어붙이고 좌우 거리를 잰다.

            실폭도로 폴리곤은 도로 중심선을 따라 좌/우로 쪼개져 있고
            그 경계에 십수 cm 짜리 틈이 남는다(중앙로 실측 0.081m).
            폴리곤을 buffer 로 부풀려 닫으려 하면 좁은 골목이 뭉개지므로
            법선 위에서 좌표로만 이어붙인다. 폭 자체는 손대지 않는다.

            교차로에서는 법선이 교차하는 길을 따라 빠져나가 한쪽이 수십 m 가
            된다. 그 표본은 폭이 아니므로 버린다.
            """
            r = LineString([(p.x-ux*60, p.y-uy*60), (p.x+ux*60, p.y+uy*60)])
            sg = r.intersection(poly_u)
            if sg.is_empty:
                return None, "empty"          # 법선이 이 소스와 아예 안 만난다
            # 교차 결과는 LineString 만이 아니다. 법선이 폴리곤 모서리를 스치면
            # Point 가, 여러 형태가 섞이면 GeometryCollection 이 나온다.
            # geoms 접근을 무조건 하면 Point 에서 AttributeError 로 죽는다.
            if sg.geom_type == "LineString":
                pcs = [sg]
            elif hasattr(sg, "geoms"):
                pcs = [q for q in sg.geoms if q.geom_type == "LineString"]
            else:
                return None, "tangent"        # 점 교차. 법선이 경계에 접함
            if not pcs:
                return None, "tangent"

            # 각 조각을 법선 방향 1차원 구간으로 바꾼다. p 가 원점.
            iv = []
            for q in pcs:
                c = list(q.coords)
                ss = [(x - p.x) * ux + (y - p.y) * uy for x, y in c]
                iv.append((min(ss), max(ss)))
            iv.sort()

            # 0.5m 이내로 벌어진 구간은 같은 노면으로 본다(폴리곤 분할 틈).
            merged = [list(iv[0])]
            for lo, hi in iv[1:]:
                if lo - merged[-1][1] <= 0.5:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])

            run = next((m for m in merged if m[0] <= 0.0 <= m[1]), None)
            if run is None:
                return None, "no_run"         # p 가 이 폴리곤 밖 (snap 실패)
            left, right = -run[0], run[1]
            if left > WMAX_CAP or right > WMAX_CAP:   # 교차로에서 길을 따라 나갔다
                return None, "cap"
            v = left + right
            if not (0.3 < v < WMAX_CAP):
                return None, "range"          # 0.3m 이하 조각
            return v, None

        # ── 측정 지점 결정 ──────────────────────────────────
        _srcs3 = ((ngii1k_u, "ngii1k"), (ngii_u, "ngii"), (rw_u, "silpok"))
        if OLD_SNAP:
            # 종전 방식. 소스 하나라도 덮으면 snap 없음, 아니면 최근접 하나로 전부 이동.
            _live = [u for u, _ in _srcs3 if u is not None and not u.is_empty]
            _pp = p0
            if _live and not any(u.covers(p0) for u in _live):
                _near = min(_live, key=lambda u: u.distance(p0))
                _d = _near.distance(p0)
                if _d <= SNAP_MAX:
                    _q = nearest_points(_near, p0)[0]
                    _pp = _q
                    if _d > 1e-9:
                        _u2, _v2 = (_q.x-p0.x)/_d, (_q.y-p0.y)/_d
                        for _push in (0.3, 0.8, 1.5):
                            _c = Point(_q.x+_u2*_push, _q.y+_v2*_push)
                            if _near.covers(_c):
                                _pp = _c
                                break
            _pts = {nm: (_pp, 0.0) for _, nm in _srcs3}
        else:
            _pts = {nm: _pt_for(u) for u, nm in _srcs3}

        res = {}
        for u, nm in _srcs3:
            pt, sn = _pts[nm][0], _pts[nm][1]
            if u is None or u.is_empty:
                res[nm] = (None, "absent", None, None); continue
            if pt is None:
                res[nm] = (None, "far", None, None); continue
            v, c = _span(u, pt)
            # 자기일관성 검사. 폭 v 인 도로에 속한 점이라면 그 밖으로 벗어난
            # 거리가 반폭을 넘을 수 없다. 4.3m 를 밀어 넣어 1.26m 폭을 쟀다면
            # 원래 점은 그 조각 바깥 4.3m 에 있었던 것이고 1.26m 도로의 점일 수
            # 없다. 다른 폴리곤 조각에 억지로 들어가 그 조각의 좁은 데를 잰 것이다.
            # 45.9m 구간이 이런 표본 하나로 1.26m 판정을 받고 있었다.
            # 측정값 자신으로 검증하므로 임계값을 새로 만들지 않는다.
            if (not OLD_SNAP) and v is not None and sn is not None and sn > v / 2.0:
                v, c = None, f"snap{sn:.1f}>w/2"
            res[nm] = (v, c, pt, sn)

        # 세 소스를 다 재고 신뢰도 순으로 채택한다. 좁은 쪽을 고르지 않는다.
        # 실폭도로는 실측 11.8m 인 동계천로에 1.30m 짜리 측구 조각을 그려 놓았고
        # min() 은 그것을 무조건 채택했다. 틀린 값은 보수적인 게 아니라 틀린 것이다.
        A, src, P = None, None, p0
        for nm in ("ngii1k", "ngii", "silpok"):
            if res[nm][0] is not None:
                A, src, P = res[nm][0], nm, res[nm][2]
                break

        # 담~담(상한)은 폭을 채택한 지점과 같은 곳에서 잰다. 다른 지점에서 재면
        # wmin 과 wmax 가 서로 다른 단면을 기술하게 된다.
        rb = LineString([(P.x-ux*60, P.y-uy*60), (P.x+ux*60, P.y+uy*60)])
        B = None
        sg = rb.intersection(bld_u)                    # 담~담 = 상한
        if not sg.is_empty:
            if sg.geom_type == "LineString":
                pr = [sg]
            elif hasattr(sg, "geoms"):
                pr = [q for q in sg.geoms if q.geom_type == "LineString"]
            else:
                pr = []
            s1 = min((q.distance(P) for q in pr
                      if (q.centroid.x-P.x)*ux + (q.centroid.y-P.y)*uy < 0), default=None)
            s2 = min((q.distance(P) for q in pr
                      if (q.centroid.x-P.x)*ux + (q.centroid.y-P.y)*uy > 0), default=None)
            if s1 is not None and s2 is not None and 0.3 < s1+s2 < WMAX_CAP:
                B = s1 + s2
        # 벽 사이 폭은 도로 폭보다 좁을 수 없다. 상한(WMAX_CAP)에 걸려 잘린 경우
        # 역전이 생기므로 도로 폭으로 끌어올린다.
        if A is not None and B is not None and B < A:
            B = A

        a_1k, a_ngii, a_rw = res["ngii1k"][0], res["ngii"][0], res["silpok"][0]
        if _DBG["on"]:
            print("      " + "  ".join(
                f"{nm}={res[nm][0] if res[nm][0] is not None else res[nm][1]}"
                f"(snap{res[nm][3] if res[nm][3] is not None else '-'})"
                for nm in ("ngii1k", "ngii", "silpok"))
                + f" → A={A} src={src} B={B}")
        why = None
        if A is None:
            why = "|".join(f"{k}:{res[n][1]}" for k, n in
                           (("1k", "ngii1k"), ("ng", "ngii"), ("rw", "silpok")))
        return A, B, src, (a_1k, a_ngii, a_rw), why, res

    def widths(s):
        A, B, fb = [], [], False
        S, D = [], []
        # 교차로 파편(길이 < MIN_SEG_LEN)은 정의상 전 구간이 교차로 안이다.
        # XSEC_EXCL 을 그대로 적용하면 표본이 0 개가 되어 폭이 안 나온다.
        # 짧은 조각은 교차로 제외를 풀고 중점 한 점이라도 잰다.
        _short = s.length < MIN_SEG_LEN
        _lo = min(1.0, s.length*0.25)
        _ts = list(np.arange(_lo, max(s.length-_lo, s.length*0.5+1e-9), 2.0))
        if not _ts:
            _ts = [s.length/2]
        _nc, _nx_skip, _whys = 0, 0, []
        _cov = {"ngii1k": 0, "ngii": 0, "silpok": 0}
        _by  = {"ngii1k": [], "ngii": [], "silpok": []}
        _n_try = 0

        def _covr():
            """소스별 커버율. 정규 표본 중 그 소스가 값을 낸 비율.

            표본마다 다른 소스가 채택되면 wmin=min(A) 이 소스 혼합 집합에서
            최솟값을 뽑는다. 소스 축에서 폐기한 min() 이 표본 축으로 부활한 것이다.
            구간 단위 채택으로 바꾸기 위한 관측값이다. (STEP 5-1)
            """
            return ({k: (round(v/_n_try, 3) if _n_try else None)
                     for k, v in _cov.items()}, _n_try)
        for t in _ts:
            _nc += 1
            _pt = s.interpolate(t)
            if xsec_poly is not None:
                # ★ 폴리곤이 근처에 있으면 폴리곤만 믿는다.
                #   or 로 반경 폴백을 항상 같이 걸면 폴리곤이 무의미해진다.
                #   작은 교차부(등가반경 중앙 3.2m)는 여전히 5m 씩 도려내지고,
                #   큰 교차부(p90 7.5m)는 폴리곤 밖 오염이 그대로 남는다.
                #   폴리곤이 아예 없는 교차로에서만 반경으로 폴백한다.
                if xsec_poly.distance(_pt) < XSEC_EXCL * 2:
                    _inx = xsec_poly.intersects(_pt)
                else:
                    _inx = xn.distance(_pt) < XSEC_EXCL
            else:
                _inx = xn.distance(_pt) < XSEC_EXCL
            # ★ 짧은 조각도 교차부 폴리곤 안이면 제외한다.
            #   종전에는 _short 면 교차부 제외를 통째로 건너뛰고 중점 한 점을
            #   쟀는데, 그 한 점이 교차로 한복판이라 길이 1m 조각에서 55m 가
            #   나왔다. 표본 0 을 피하려다 쓰레기 값을 만든 것이다.
            #   MIN_SEG_LEN 주석이 이미 '폭 미산출 후 인접 상속'이라고 적고 있다.
            #   상속 경로가 원래 설계에 있는데 억지 값 때문에 안 쓰이고 있었다.
            #   교차부 폴리곤이 없을 때만 종전 동작(짧으면 재기)을 유지한다.
            _skip = _inx if (xsec_poly is not None and not _short) else _inx
            if _short and xsec_poly is not None:
                _skip = xsec_poly.intersects(_pt)
            elif _short:
                _skip = False
            if _skip:
                _nx_skip += 1
                if _DBG["on"]:
                    _how = "폴리곤" if (xsec_poly is not None
                                       and xsec_poly.intersects(_pt)) else "반경"
                    print(f"    t={t:7.1f}  교차로 {xn.distance(_pt):.1f}m ({_how}) — 제외")
                continue
            if _DBG["on"]:
                _pp = s.interpolate(t)
                print(f"    t={t:7.1f}  ({_pp.x:.1f},{_pp.y:.1f})")
            a, b, sc, pr, _why, _res = measure(s, t)
            _n_try += 1

            def _trusted(_nm):
                """이 지점에서 그 소스의 표본을 믿을 수 있는가."""
                _r = _res.get(_nm)
                if _r is None or _r[0] is None:
                    return False
                _sn = _r[3]
                return _sn is None or _sn <= SNAP_TRUST

            for _nm in ("ngii1k", "ngii", "silpok"):
                if _trusted(_nm):
                    _cov[_nm] += 1
            if _why: _whys.append(_why)
            # 채택된 소스의 snap 이 크면 그 표본 자체를 버린다.
            if a and (sc is None or _trusted(sc)):
                A.append(a); S.append(sc); D.append(pr)
            for _nm, _vv in zip(("ngii1k", "ngii", "silpok"), pr):
                if _vv is not None and _trusted(_nm):
                    _by[_nm].append(_vv)
            if b: B.append(b)
        if A:
            _rsn = None
        elif _nc == 0:
            _rsn = "ts_empty"
        elif _nx_skip == _nc:
            _rsn = "all_xsec"            # 표본 전부 교차로 5m 안. 잰 적이 없다
        else:
            _rsn = Counter(_whys).most_common(1)[0][0] if _whys else "unknown"
        # 폴백을 두지 않는다. 정규 샘플(2m 간격)로 한 점도 안 잡히면
        # 중심선이 도로면을 벗어난 것이고, 그때 억지로 낸 값은 근거가 없다.
        # 33m·63m 구간이 표본 1개로 1.3m 판정을 받고 있었다.
        _n_reg = len(A)

        # ── 구간 단위 소스 채택 (STEP 5-1) ──────────────────
        # 종전에는 wmin = min(A) 였는데 A 는 표본마다 다른 소스가 채택된
        # 혼합 집합이다. 표본1 은 1:1,000 의 3.2m, 표본2 는 실폭도로의 1.8m
        # 인데 그 둘의 최솟값을 구간 폭이라고 불렀다. 소스 축에서 폐기한
        # min() 이 표본 축에 그대로 남아 있었던 것이다(1k 부분커버 302 구간).
        #
        # 값을 낸 최우선 소스 하나로 고정하고 그 소스의 표본만으로 최솟값을 낸다.
        # 커버율이 높은 소스를 고르지 않는다 — 실폭도로가 0.955 로 가장 높은데
        # 그것을 채택하면 결정 63(수치지도 주 소스)을 정면으로 뒤집는다.
        # 부분커버 구간은 그 소스가 못 잰 구간을 모르는 채로 판정하는 것이므로
        # width_cov 로 노출해 D-25 실측 우선순위에 쓴다.
        _pick = None
        if not MIX_SRC:
            # 커버율은 소스를 '고르는' 기준이 아니라 '자격'이다.
            # 커버율로 고르면 실폭도로(0.955)가 항상 이겨 결정 63 이 뒤집힌다.
            _covnow = _covr()[0]
            for _nm in ("ngii1k", "ngii", "silpok"):
                if not _by[_nm]:
                    continue
                _cv = _covnow.get(_nm)
                if _cv is not None and _cv < COV_MIN and _n_reg >= 3:
                    continue          # 자격 미달. 다음 순위로 넘긴다
                _pick = _nm
                break
            # 전부 자격 미달이면 우선순위대로 하나는 쓴다(폭을 못 내는 것보다 낫다).
            if _pick is None:
                for _nm in ("ngii1k", "ngii", "silpok"):
                    if _by[_nm]:
                        _pick = _nm
                        break
        wmin = None
        if _pick is not None:
            wmin = round(min(_by[_pick]), 2)
        elif A:
            wmin = round(min(A), 2)
        wmax = round(min(B), 2) if B else None
        # 벽 사이 폭이 도로 폭보다 좁을 수는 없다. 샘플별로는 맞아도
        # 각각 최솟값을 취하면 역전이 생긴다(대로에서 WMAX_CAP 에 걸린 경우).
        if wmin is not None and wmax is not None and wmax < wmin:
            wmax = wmin
        # 폴백 표본만으로 나온 값은 신뢰할 수 없다. 긴 구간에서 정규 샘플이
        # 하나도 안 잡혔다는 것은 중심선이 도로면을 벗어났다는 뜻이다.
        # 그 값으로 판정하면 대로가 1.4m 로 나간다(DM02856 63m 구간).
        if _n_reg == 0 and s.length >= MIN_SEG_LEN * 2:
            return None, None, True, None, None, _rsn, _covr()

        # 채택된 소스를 기록한다(결정 64). 구간 단위 단일 소스다.
        if _pick is not None:
            wsrc = _pick
            _i = A.index(min(A)) if A else None
        else:
            _i = A.index(min(A)) if A else None
            wsrc = S[_i] if _i is not None else None
        # 두 공공 소스가 같은 지점을 얼마나 다르게 기술하는가.
        # 이 값이 큰 순서가 곧 D-25 실측 우선순위다(§7-2 관측점 선정).
        wdis = None
        if _i is not None:
            _vals = [v for v in D[_i] if v is not None]
            if len(_vals) >= 2:
                wdis = round(max(_vals) - min(_vals), 2)
        return wmin, wmax, fb, wsrc, wdis, _rsn, _covr()

    def verdict(wmin, wmax, nreg=None):
        """소방청 기준 판정 4종.

            blocked   wmax <  3.0   통과 하한 미달. 장애물이 없어도 못 지나간다
            clear     wmin >= 7.0   양쪽에 주차가 있어도 통과. 영상판정 불필요
            unknown   폭 산출 불가
            needs_cv  나머지        상습주차 여부로 갈린다. 영상판정 대상
        """
        # ★ 표본 1개로는 clear 를 주지 않는다.
        #   DM02825(동계천로95번길, 길이 2.7m)는 표본 하나가 교차로를 대각선으로
        #   가로질러 42.1m 가 나왔고 그것이 곧 wmin 이 되어 clear 로 판정됐다.
        #   실제로는 사거리 한복판이다(네이버 거리뷰 확인, 2026-08-14).
        #   표본이 하나면 커버율이 자동으로 1.0 이 되어 COV_MIN 검사도 통과한다.
        #   clear 는 '영상판정조차 필요 없다'는 가장 강한 주장이라 근거가 필요하다.
        #   blocked 는 막는 쪽이라 표본 1개여도 유지한다(미탐:오탐 = 100:1).
        #   ※ widths() 에서 None 을 반환하면 3m 미만 구간이 fragment 로 떨어져
        #     44개 구간이 산출물에서 사라진다. 그래서 판정 단계에서 막는다.
        if wmax is not None and wmax < TRUCK:           return "blocked"
        if wmin is not None and wmin >= TRUCK + 2*PARK:
            if nreg is not None and nreg <= 1:
                return "needs_cv"
            return "clear"
        # 도로폭이 있으면 판정한다. wmax(담~담) 가 없는 것은 실패가 아니다.
        # 대로는 건물이 WMAX_CAP(40m) 밖이라 벽 사이를 잴 수 없고,
        # 그런 구간은 도로폭만으로 이미 판정이 끝난다.
        # 이 줄이 없어서 필문대로·밤실로 같은 대로 392구간이 회색으로 떨어졌다.
        if wmin is not None:                            return "needs_cv"
        return "unknown"

    # 표출 범위 = 동명동 + 접근 회랑. 회랑도 판정 색상을 가져야
    # "안전센터에서 오는 길이 어떤 상태인가"가 보인다.

    # 폭 소스(rw_u / bld_u)는 poly.buffer(80) 으로 클립돼 있다.
    # 그 밖의 회랑 구간은 "폭을 못 잰 것"이 아니라 "잴 대상이 아닌 것"이다.
    # 둘을 같은 이름으로 부르면 화면이 "골목의 44%를 모른다"로 오독된다.
    # 도로명. 노딩하면 원본 속성이 끊기므로 중점 최근접으로 되붙인다.
    # seg_id(DM00001)만 보이면 사람이 어느 골목인지 알 수 없다.
    _rn = road[road["RN"].notna()].copy()
    _rn_geo = list(_rn.geometry)
    _rn_nm = list(_rn["RN"])
    # RDS_DPN_SE 0=주도로 1=부속(측도·측면도로).
    # 중앙로(본선 25m) 옆에 붙은 폭 1.3m 통로가 같은 도로명을 갖는다.
    # 이름만 보면 대로인데 폭이 1m 로 나와 오산출로 오해하기 쉽다.
    _rn_dpn = list(_rn["RDS_DPN_SE"].astype(str))
    _rn_bt = list(_rn["ROAD_BT"])
    _rn_tree = STRtree(_rn_geo)

    def road_name(g):
        """겹침 길이가 가장 긴 도로선의 RN.

        세그먼트는 road_link 를 교차점에서 자른 조각이므로 원본 선 위에
        그대로 놓여 있다. 추정할 필요가 없다.
        중점 최근접 방식은 교차로에서 옆 도로를 집는다.
        """
        band = g.buffer(0.5)
        best, best_len, best_k = None, 0.0, None
        for k in _rn_tree.query(band):
            ov = _rn_geo[k].intersection(band)
            if ov.is_empty:
                continue
            if ov.length > best_len:
                best, best_len, best_k = _rn_nm[k], ov.length, k
        if best is None or best_len < g.length * 0.5:
            return None, None, None
        return best, _rn_dpn[best_k], _rn_bt[best_k]

    if _dups:
        print(f"\n[병렬 엣지 {len(_dups)}] 같은 노드쌍에 두 형상 — 긴 쪽을 버렸다")
        print("  남긴길이  버린길이   비  위치도로")
        _bad = 0
        for _kl, _ll, _c in sorted(_dups, key=lambda x: -x[1]/max(x[0], 1e-9)):
            _r = _kl and _ll / _kl or 0
            _q = _rn_tree.query(_c.buffer(15.0))
            _nm = min(((_rn_geo[k].distance(_c), _rn_nm[k]) for k in _q),
                      default=(None, None))[1]
            if _r > 1.5:
                _bad += 1
            print(f"  {_kl:8.1f}  {_ll:8.1f}  {_r:5.2f}  {_nm or '(미매칭)'}"
                  + ("   ← 별개 경로 의심" if _r > 1.5 else ""))
        print(f"  길이비 1.5 초과 {_bad}건" +
              ("  ★ 병렬 처리 방식 재검토 필요" if _bad else "  — 중복 형상. 무해"))

    # ── 산출 단위 구성 (B2) ──────────────────────────────────
    # 그래프 G 는 라우팅·교차로 노드(xn) 정본이므로 손대지 않는다.
    # 산출 단위만 묶는다. 도로 B 는 교차로 노드에 그대로 붙어 있고
    # 연결성·최단경로가 변하지 않는다.
    #
    # 교차로 안에만 존재하는 조각은 제자리에서 폭을 잴 수 없다. 기하학적으로
    # 정의되지 않는다 — 법선이 교차하는 도로를 따라 길이 방향으로 달려서
    # 폭이 아니라 "옆 도로가 얼마나 뻗어 있나"를 잰다(제봉로 3.3m 구간에서 55m).
    # 그래서 값을 빌려오는 대신 독립 피처로 두지 않는다. 동일선상 이웃과
    # 하나의 산출 단위로 묶고, 그 단위 위에서 XSEC_EXCL 을 유지한 채 정규 측정한다.
    # wmin 이 표본 최솟값인 것은 나머지 세그먼트도 마찬가지다. 파편만 예외였다.
    COLLIN_DEG  = 30.0     # 동일선상 판정. 이 각을 넘으면 다른 도로다
    MERGE_PASS  = 4        # 짧은 것끼리 연쇄로 붙는 경우 대비

    units, node2u = {}, {}
    for i, (a, b, d) in enumerate(G.edges(data=True)):
        units[i] = {"geom": d["geom"], "ends": [a, b], "n": 1,
                    "why": None, "usage": use.get(frozenset((a, b)), 0)}
        node2u.setdefault(a, set()).add(i)
        node2u.setdefault(b, set()).add(i)
    # 산출 범위 밖 단위는 재지 않는다. 병합 상대로만 쓰이고, 흡수되면 재측정된다.
    _ink = {uid for uid, u in units.items() if u["geom"].intersects(keep)}
    W = {uid: widths(units[uid]["geom"]) for uid in _ink}
    _fail0 = sum(1 for v in W.values() if v[0] is None)
    print(f"  산출범위 단위 {len(_ink)} / 전체 {len(units)} · 폭 미산출 {_fail0}")

    def _dirv(geom, node, back=3.0):
        """node 쪽 끝에서 형상 안쪽을 향하는 단위벡터."""
        c = list(geom.coords)
        nd = Point(node)
        if Point(c[0]).distance(nd) <= Point(c[-1]).distance(nd):
            base, tgt = Point(c[0]), geom.interpolate(min(back, geom.length))
        else:
            base, tgt = Point(c[-1]), geom.interpolate(max(geom.length-back, 0.0))
        dx, dy = tgt.x-base.x, tgt.y-base.y
        L = np.hypot(dx, dy)
        return (dx/L, dy/L) if L > 0 else None

    def _join(g1, g2):
        """접합점에서 두 형상을 용접한다.

        노드 접합으로 두 형상의 끝점이 최대 NODE_TOL 만큼 어긋나 있어
        linemerge 가 실패한다. 중점으로 용접해 틈을 없앤다.
        """
        c1, c2 = list(g1.coords), list(g2.coords)
        best = None
        for i1, e1 in ((0, c1[0]), (-1, c1[-1])):
            for i2, e2 in ((0, c2[0]), (-1, c2[-1])):
                dd = np.hypot(e1[0]-e2[0], e1[1]-e2[1])
                if best is None or dd < best[0]:
                    best = (dd, i1, i2)
        dd, i1, i2 = best
        if dd > NODE_TOL * 2:
            return None
        A = c1 if i1 == -1 else c1[::-1]
        B = c2 if i2 == 0 else c2[::-1]
        mid = ((A[-1][0]+B[0][0])/2.0, (A[-1][1]+B[0][1])/2.0)
        return LineString(A[:-1] + [mid] + B[1:])

    _cos_lim = -np.cos(np.radians(COLLIN_DEG))
    _mrg = []
    for _pass in range(0 if NO_MERGE else MERGE_PASS):
        _todo = [uid for uid in list(units)
                 if uid in W and W[uid][0] is None]
        if not _todo:
            break
        _n_moved = 0
        for uid in _todo:
            if uid not in units:
                continue
            u = units[uid]
            best = None
            for nd in list(u["ends"]):
                du = _dirv(u["geom"], nd)
                if du is None:
                    continue
                for vid in list(node2u.get(nd, ())):
                    if vid == uid or vid not in units or nd not in units[vid]["ends"]:
                        continue
                    dv = _dirv(units[vid]["geom"], nd)
                    if dv is None:
                        continue
                    dot = du[0]*dv[0] + du[1]*dv[1]
                    if dot <= _cos_lim and (best is None or dot < best[0]):
                        best = (dot, vid, nd)
            if best is None:
                continue                      # 동일선상 이웃 없음. 병합하지 않는다
            _dot, vid, nd = best
            v = units[vid]
            gj = _join(u["geom"], v["geom"])
            if gj is None:
                continue
            ends = [e for e in u["ends"] + v["ends"] if e != nd]
            if len(ends) != 2:
                continue                      # 고리. 건드리지 않는다
            for n2 in set(u["ends"] + v["ends"]):
                node2u.get(n2, set()).discard(uid)
                node2u.get(n2, set()).discard(vid)
            for n2 in ends:
                node2u.setdefault(n2, set()).add(uid)
            _mrg.append((uid, W[uid][5], round(u["geom"].length, 1),
                         round(v["geom"].length, 1), round(np.degrees(np.arccos(
                             max(-1.0, min(1.0, -_dot))))), 1))
            u.update(geom=gj, ends=ends, n=u["n"]+v["n"],
                     why=u["why"] or W[uid][5],
                     usage=max(u["usage"], v["usage"]))
            del units[vid]; W.pop(vid, None)
            W[uid] = widths(gj)
            _n_moved += 1
        print(f"  병합 pass{_pass+1} · 대상 {len(_todo)} · 병합 {_n_moved}"
              f" · 남은 미산출 {sum(1 for x in W.values() if x[0] is None)}")
        if _n_moved == 0:
            break
    print(f"  산출단위 {G.number_of_edges()} → {len(units)}"
          f" · 폭 미산출 {_fail0} → {sum(1 for x in W.values() if x[0] is None)}")
    if _mrg:
        _ml = sorted(((units[u]['geom'].length, units[u]['n'], u)
                      for u, *_ in _mrg if u in units), reverse=True)[:10]
        print("  병합 후 최장 단위:",
              " ".join(f"{l:.0f}m({n})" for l, n, _ in _ml))

    rec = {}
    for i, (uid, u) in enumerate(sorted(units.items())):
        g, (a, b) = u["geom"], u["ends"]
        if not g.intersects(keep):
            continue
        sid = f"DM{i:05d}"
        short = g.length < MIN_SEG_LEN
        if uid not in W:
            W[uid] = widths(g)          # 병합으로 범위 안에 들어온 단위
        wmin, wmax, fb, wsrc, wdis, wfail, (wcov, wnt) = W[uid]
        _road_nm, _road_side, _road_bt = road_name(g)
        v = verdict(wmin, wmax, wnt)
        if short and wmin is None:
            v = "fragment"

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
            # 폭을 못 잰 것과 잴 만한 도로가 아닌 것은 다르다.
            # 도로대장 명목폭(ROAD_BT)이 TRUCK 미만이면 소방차 진입 불가가
            # 명백하다. 그런 구간을 "CCTV 없어 판정 보류" 회색으로 두면
            # 영상판정으로 메울 수 있다는 뜻이 되는데, 카메라를 갖다 대도
            # 못 들어간다. 도면으로 이미 확정된 것이다.
            # 폭 미산출 구간에 한해서만 적용한다 — ROAD_BT 는 도로명 단위
            # 대표값이라 실측값이 있으면 그쪽이 항상 우선한다.
            if _road_bt is not None and _road_bt < TRUCK:
                v, reason = "blocked", None

        rec[sid] = dict(seg_id=sid, width_min_m=wmin, width_max_m=wmax,
                        verdict=v, unknown_reason=reason,
                        cctv_dist_m=d_cctv, cv_feasible=bool(cv_ok),
                        width_verified=False, midpoint_fallback=fb, inherited=False,
                        width_src=wsrc,
                        width_disagree_m=wdis,
                        width_fail=wfail,          # ★ 진단용. 저장 전 drop
                        road_name=_road_nm, road_side=_road_side, road_bt_m=_road_bt,
                        light_count=(int(_light.intersects(g.buffer(50)).sum())
                                     if _light is not None else None),
                        in_emd=bool(g.intersects(poly)),
                        route_usage=u["usage"],
                        merged_n=u["n"], merge_why=u["why"],
                        cov_ngii1k=wcov["ngii1k"], cov_ngii=wcov["ngii"],
                        cov_silpok=wcov["silpok"], n_sample=wnt,
                        width_cov=(wcov.get(wsrc) if wsrc else None),
                        length_m=round(g.length, 1), _n=(a, b), geometry=g)

    bynode = {}
    for sid, r in rec.items():
        for n in r["_n"]:
            bynode.setdefault(n, []).append(sid)
    # 인접 상속은 하지 않는다. 교차로 파편의 이웃은 사방이라 어느 값을
    # 물려받아도 근거가 없다. 편차가 이웃 자체의 두 배였다(-2.00 vs -1.00).
    # 못 잰 것은 못 잰 것으로 둔다.

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
    # 인접에 폭 있는 세그먼트가 없어 상속에 실패한 파편은 unknown 으로 떨어뜨린다.
    # verdict 어휘에 fragment 는 없다.
    for r in rec.values():
        if r["verdict"] == "fragment":
            r["verdict"] = "unknown"
            r["unknown_reason"] = "width"
    for r in rec.values():
        r.setdefault("run_length_m", None)
        r.setdefault("nfa_designated", False)
        r.pop("_n")

    g = gpd.GeoDataFrame(list(rec.values()), crs=CRS_M)
    # ── seg_uid ──────────────────────────────────────────────
    # seg_id 는 실행 간 유지되지 않는다. 노딩 규칙이 바뀌면서 1266 → 1087 이
    # 되었을 때 번호가 전부 밀렸다. 실측값·관측점·영상판정 반환값·향후 DB PK 는
    # 전부 seg_uid 에 붙는다. seg_id 는 콘솔·디버그 표시용으로만 남긴다.
    g = attach_seg_uid(g)
    _ret = uid_retention(OUT / "seg_uid_map.csv", g)
    print(f"  seg_uid {g.seg_uid.nunique()}개 · 직전 실행 대비 유지율 {_ret:.1%}")
    if _ret < 0.90:
        print("  ! 유지율 90% 미만 — segkey 규칙 재검토 필요")
    save_uid_map(g, OUT / "seg_uid_map.csv")

    # ── 소방서 지정 구간 대조 ────────────────────────────────
    # 동부소방서 소방통로확보대상 지역 현황(2025-07-31)의 폭과 비교한다.
    # 좌표가 없어 도로명 단위로만 매칭되므로 참고값이다.
    # 소방서가 지정한 것은 그 도로명 중 가장 좁은 구간이므로,
    # 우리 값도 최솟값 쪽으로 비교하는 것이 타당하다.
    # ★ RAW 는 $FIRE_LANE_RAW 다. ROOT/"data"/"raw" 로 박아두면 exists() 가
    #   항상 거짓이라 이 블록이 통째로 죽는다. 실제로 한 번도 실행된 적이 없었다.
    #   소방서 지정 구간은 우리 폭에 대한 유일한 외부 대조 수단이다.
    fa = RAW/"safety"/"safety_fire_access_gj_dong_20250731.csv"
    if fa.exists():
        import csv, re
        rows = list(csv.DictReader(fa.open(encoding="cp949")))
        road = gpd.read_file(OUT/"road_link_5186.gpkg").to_crs(CRS_M)
        print("\n[소방서 지정 구간 대조]")
        # ★ 2026-08-18. print 만 하던 것을 파일로도 남긴다.
        #   이 대조는 우리 폭에 대한 유일한 외부 대조 수단인데 두 번 소실됐다.
        #   경로 오류로 죽어 있던 것이 8/13, 터미널에만 있던 것이 8/17 이다.
        #   8/17 봉인 때 7.24m 를 문서에서 손으로 옮겨 적어야 했다.
        _nfa_rows = []
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
                _nfa_rows.append({
                    "road": rn,
                    "nfa_m": wf,
                    "nfa_raw": str(w_nfa),
                    "ours_median_m": round(float(med), 2),
                    "dev_m": round(float(med) - wf, 2),
                    "n_seg": int(len(hit)),
                    "verdict": {k: int(v) for k, v in hit.verdict.value_counts().items()},
                })

        if _nfa_rows:
            import json as _json
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            _abs = round(sum(abs(x["dev_m"]) for x in _nfa_rows), 2)
            _out = {
                "as_of": _dt.now(_tz(_td(hours=9))).isoformat(timespec="seconds"),
                "source": str(fa.name),
                "ref": "동부소방서 소방통로확보대상 지역 현황 (20구간 7,120m)",
                "match_by": "도로명. 소방서 자료에 좌표가 없다",
                "compare": "구간 대표폭이므로 중앙값과 비교. 최솟값이면 -3~-7m 로 벌어진다",
                "caveat": ("★ 이것은 검증이 아니라 적합(fit)일 수 있다. 12.6 → 7.24 로 "
                           "줄이는 과정에서 이 표를 게이트로 썼다. 게이트로 쓴 자료는 "
                           "그 순간부터 외부 검증 수단이 아니다. MASTER 4절 참조."),
                "abs_dev_sum_m": _abs,
                "n_road": len(_nfa_rows),
                "rows": sorted(_nfa_rows, key=lambda x: abs(x["dev_m"])),
            }
            (OUT / "nfa_compare.json").write_text(
                _json.dumps(_out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  절대편차 합 {_abs}m · {len(_nfa_rows)}구간"
                  f"  → {(OUT / 'nfa_compare.json').name}")
        else:
            # 없으면 소리를 낸다. 조용한 결측을 만들지 않는다.
            print("  ★ 매칭 0구간. 도로명 매칭이 깨졌다 — RN 컬럼과 지역명 형식 확인")
    # ── 소스별 커버율 ────────────────────────────────────────
    # 표본 축 소스 혼합이 어디서 얼마나 일어나는지. 채택 규칙(STEP 5-1) 근거.
    _gv = g[g.n_sample > 0]
    print(f"\n[소스 커버율] 표본 있는 단위 {len(_gv)}"
          f" · 소스별 snap {'OFF(종전)' if OLD_SNAP else 'ON'}")
    print(_gv[["cov_ngii1k", "cov_ngii", "cov_silpok"]]
          .describe(percentiles=[.25, .5, .75]).round(3).to_string())
    _mix = _gv[(_gv.cov_ngii1k > 0) & (_gv.cov_ngii1k < 1)]
    print(f"  1k 부분커버(0<cov<1) {len(_mix)} · 그중 채택소스가 1k 아닌 것 "
          f"{int((_mix.width_src != 'ngii1k').sum())}")
    print("  채택 소스 분포:",
          dict(g.width_src.value_counts(dropna=False).items()))
    _wc = g.width_cov.dropna()
    print(f"  채택소스 커버율 — 1.0 인 구간 {int((_wc >= 1.0).sum())}"
          f" · 0.5 미만 {int((_wc < 0.5).sum())} · 평균 {_wc.mean():.3f}")
    _thin = g[(g.width_cov.notna()) & (g.width_cov < 0.5)]
    if len(_thin):
        print("  커버율 0.5 미만 상위 (실측 우선순위)")
        print(_thin.nsmallest(10, "width_cov")[
            ["seg_id", "road_name", "length_m", "width_min_m",
             "width_src", "width_cov", "n_sample"]].to_string(index=False))

    # ── 폭 미산출 진단 ───────────────────────────────────────
    # STEP 4-1. 사유별 분포를 보고 원인을 특정한다. 추정 금지.
    _w = g[g.unknown_reason == "width"]
    print(f"\n[폭 미산출 진단] {len(_w)}구간")
    if len(_w):
        print(_w.width_fail.fillna("(none)").value_counts().to_string())
        print("\n사유별 길이")
        print(_w.groupby(_w.width_fail.fillna("(none)")).length_m
              .agg(["count", "median", "max"]).round(1).to_string())
        print("\n전체 목록")
        print(_w[["seg_id", "road_name", "length_m", "in_emd", "width_fail"]]
              .sort_values(["width_fail", "length_m"]).to_string(index=False))
    _mg = g[g.merged_n > 1]
    print(f"\n[병합 단위] {len(_mg)}개 · 흡수된 엣지 합 {int(_mg.merged_n.sum())}")
    if len(_mg):
        print(_mg.groupby(_mg.merge_why.fillna("(none)")).agg(
            n=("seg_id", "size"), 길이중앙=("length_m", "median"),
            길이최대=("length_m", "max")).round(1).to_string())
        print(_mg.verdict.value_counts().to_string())
        print("\n  병합으로 blocked 이 된 단위 — run_length 부풀림 점검")
        _mb = _mg[_mg.verdict == "blocked"]
        print(_mb[["seg_id", "road_name", "road_side", "length_m", "merged_n",
                   "width_min_m", "width_max_m", "width_src", "road_bt_m",
                   "run_length_m"]].to_string(index=False)
              if len(_mb) else "  없음")
    _susp = g[(g.verdict == "blocked") & (g.length_m > 30)]
    print(f"\n[blocked 의심] 길이 30m 초과인데 통행불가 {len(_susp)}구간")
    if len(_susp):
        print(_susp[["seg_id", "road_name", "road_side", "length_m", "merged_n",
                     "width_min_m", "width_max_m", "width_src", "road_bt_m"]]
              .sort_values("length_m", ascending=False).to_string(index=False))
    print(f"\n[연속구간장] nfa_designated {int(g.nfa_designated.sum())}구간"
          f" · 최대 run {g.run_length_m.max()}m")
    print(f"[길이분포] 중앙 {g.length_m.median():.1f}m · 최대 {g.length_m.max():.1f}m"
          f" · 100m초과 {(g.length_m > 100).sum()}")

    _dbg_ids = list(DEBUG_SEG)
    if DEBUG_XY:
        _x, _y = (float(v) for v in DEBUG_XY.split(",")[:2])
        _near = g.iloc[g.distance(Point(_x, _y)).values.argmin()]
        print(f"\n[덤프대상] ({_x:.0f},{_y:.0f}) 최근접 = {_near.seg_id} "
              f"{_near.road_name} {_near.length_m}m")
        _dbg_ids.append(_near.seg_id)
    for _sid in _dbg_ids:
        _row = g[g.seg_id == _sid]
        if not len(_row):
            print(f"\n[덤프] {_sid} 없음")
            continue
        _gg = _row.geometry.iloc[0]
        print(f"\n[덤프] {_sid} {_row.road_name.iloc[0]} "
              f"len={_row.length_m.iloc[0]}m merged={_row.merged_n.iloc[0]} "
              f"side={_row.road_side.iloc[0]} bt={_row.road_bt_m.iloc[0]}")
        _DBG["on"] = True
        _r = widths(_gg)
        _DBG["on"] = False
        print(f"  → wmin={_r[0]} wmax={_r[1]} src={_r[3]} fail={_r[5]} cov={_r[6]}")

    # 진단 컬럼은 산출물에 넣지 않는다. 스키마·sha 를 바꾸면 안 된다.
    g = g.drop(columns=["width_fail"])

    g.to_file(OUT / "segments_5186.gpkg", driver="GPKG", layer="segments")
    g.to_crs(CRS_W).to_file(OUT / "segments.geojson", driver="GeoJSON")
    h = hashlib.sha256((OUT / "segments.geojson").read_bytes()).hexdigest()
    (OUT / "segments.schema.json").write_text(json.dumps({
        "crs": CRS_W, "sha256": h, "count": len(g), "width_verified": False,
        "note": "width_* 는 D-25 레이저 실측 전 미검증 값. verdict 문자열만 참조하고 임계값을 하드코딩하지 말 것.",
        "fields": {
            "seg_uid": "str, 실행 간 유지되는 키. {지역}-{중점X}-{중점Y}-{도로명해시}. 실측·관측점·영상판정·DB PK 는 전부 이 키를 쓴다",
            "seg_id": "str, 실행 내 표시용 일련번호. ★불변이 아니다. 노딩 규칙이 바뀌면 번호가 전부 밀린다. 외부 참조 금지",
            "width_min_m": "float|null 노면폭(하한). 트랜섹트 최솟값",
            "width_src": "null|ngii|silpok 채택된 폭 소스 (결정 63/64)",
            "width_disagree_m": "float|null 두 폭 소스의 차이. 실측 우선순위",
            "road_name": "str|null 도로명. 겹침길이 최대 매칭",
            "road_side": "0=주도로 1=부속(측도). 같은 도로명이라도 폭이 다르다",
            "road_bt_m": "float|null 도로대장 명목폭. 참고용. 판정에는 쓰지 않는다",
            "in_emd": "bool 동명동 안인가. false 는 접근 회랑",
            "light_count": "int|null 반경 50m 가로등 수. 지번 단위 집계라 근사다",
            "width_max_m": "float|null 담~담(상한). building 트랜섹트. 대로는 null(건물이 40m 밖)",
            "verdict": "clear|needs_cv|blocked|unknown",
            "width_verified": "bool",
            "midpoint_fallback": "bool 교차로 제외로 샘플 0 → 중점 측정",
            "inherited": "bool 사용하지 않는다. 항상 false",
            "merged_n": "int 이 산출단위가 묶은 그래프 엣지 수. 1 이면 병합 없음",
            "cov_ngii1k": "float|null 정규표본 중 1:1,000 이 값을 낸 비율",
            "cov_ngii": "float|null 정규표본 중 1:5,000 이 값을 낸 비율",
            "cov_silpok": "float|null 정규표본 중 실폭도로가 값을 낸 비율",
            "n_sample": "int 정규표본 수(교차로 제외 후)",
            "width_cov": "float|null 채택 소스가 이 구간 표본을 덮은 비율. "
                         "1 미만이면 못 잰 구간이 있다. D-25 실측 우선순위",
            "merge_why": "str|null 병합을 유발한 최초 폭 미산출 사유",
            "route_usage": "int 안전센터 2곳 → 건물출입구 최단경로 사용횟수",
            "length_m": "float 이 구간의 수평거리(m). 경사 보정 전이다. 동명동 평균경사 1.8도 기준 실주행거리는 약 0.05% 길고 최대 9도 구간에서 1.2% 길다. 보정에는 5m DEM 이 필요하다",
            "run_length_m": "float|null 같은 판정이 이어지는 연속 구간장(m)",
            "nfa_designated": "bool 소방청 지정 기준(연속 100m 이상) 충족",
            "cctv_dist_m": "float 가장 가까운 CCTV 까지의 거리(m)",
            "cv_feasible": "bool CCTV 유효범위(25m) 안. 영상판정 성립 여부",
            "unknown_reason": "null|width|no_cctv 회색이 된 이유"},
        "standard": "소방청 2025 화재현장 골든타임 확보 종합대책 (구간 100m) + 2026-08-06 현장 답사 (통과 하한 3.0m)",
        "params": {"truck_width_m": TRUCK, "park_occupancy_m": PARK, "nfa_run_m": NFA_RUN_M, "cctv_range_m": CCTV_RANGE,
                   "intersection_exclusion_m": XSEC_EXCL, "wmax_cap_m": WMAX_CAP,
                   "min_seg_len_m": MIN_SEG_LEN, "snap_tol_m": SNAP_TOL},
        "verdict_rule": ["폭 미산출 + ROAD_BT < 3.0 -> blocked (명목폭 진입 불가)",
                         "wmax <  3.0 -> blocked (통과 하한 미달)",
                         "wmin >= 7.0 -> clear (양쪽 주차해도 통과)",
                         "wmin or wmax null -> unknown (reason=width)",
                         "needs_cv 인데 CCTV 25m 밖 -> unknown (reason=no_cctv). 영상판정 불가",
                         "else -> needs_cv (상습주차 여부로 갈림. 영상판정 대상)"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(g.verdict.value_counts().to_string())
    print(f"\n→ segments {len(g)} · 경로사용 {(g.route_usage>0).sum()} · sha {h[:16]}")


if __name__ == "__main__":
    main()

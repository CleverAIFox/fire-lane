#!/usr/bin/env python3
"""
seg/graph.py — 노딩과 접근 회랑.

도로 중심선을 교차점에서 잘라 그래프로 만든다. 이 파일의 결과가 `seg_uid` 의
뿌리다 — 노드가 흔들리면 구간 경계가 흔들리고, 실측값이 미아가 된다.

★ NODE_TOL 로 끝점을 묶는 이유
  mm 반올림으로 노드를 식별하면 4cm 떨어진 두 점이 별개 노드가 되고 그 사이에
  길이 0.04m 엣지가 남는다. 피처로서 의미가 없고 폭도 잴 수 없다(51개).

2026-08-18 Stage 4 에서 `segments.py` 의 `main()` 밖으로 꺼냈다.
로직은 한 글자도 바꾸지 않았다. `tools/golden.py` 로 산출물 동일을 증명한다.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
from shapely.geometry import Point
from shapely.ops import unary_union

from firelane.seg import geom
from firelane.seg.params import GRAPH_BUFFER, NODE_TOL, STATIONS

CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"


def build_graph(road, poly, endpoint_snap):
    """도로 중심선 → 노드 접합 → 최대 연결성분 그래프.

    반환 (G, dups). dups 는 같은 노드쌍에 두 형상이 온 경우다 — 진단용.
    """
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
    # ★ 2026-09-25 (PLAN §1 #125 · DECISIONS §252). 같은 15줄이 `_write_route` 에도
    #   있었다. 합집합 방향만 달랐고 집합 분할은 같다 — 판정 재실행으로 확인하고 합쳤다.
    _rep = geom.snap_groups(_pts, NODE_TOL)
    _grp = {}
    for i, r in enumerate(_rep):
        _grp.setdefault(r, []).append(i)
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
    return G, _dups


def _connector_ends(conn) -> dict:
    """`ENT_MAN_NO` → 접속선(`TL_SPOT_CNTC`)의 두 끝점 `[(x, y), (x, y)]`.

    접속선은 출입구에서 도로까지 이은 선이다. 어느 끝이 출입구인지는 호출자가
    출입구 점과 대 보고 가른다(원천이 끝점 순서를 약속하지 않는다).
    """
    out = {}
    for k, g in zip(conn["ENT_MAN_NO"].astype(str), conn.geometry, strict=True):
        c = list(g.coords)
        out[k] = (c[0][:2], c[-1][:2])
    return out


def access_targets(G, ent, poly, conn=None) -> set:
    """소방차 목적지 노드 집합 — 동명동 안 출입구를 그래프 노드에 붙인 것.

    ★ **붙이는 길이 둘이다 — 혼합이다.** 다음 사람이 「왜 둘이냐」를 묻는다.

      · **접속선이 있는 출입구**(`conn` 에 `ENT_MAN_NO` 가 있는 것 — 오늘은 주출입구
        `RM` 1,313 전부) → 접속선의 **도로 쪽 끝점**에서 가장 가까운 노드.
        접속선은 원천(`juso_bldg_geom` 의 `TL_SPOT_CNTC`)이 「이 출입구는 도로의 여기로
        닿는다」고 **선언한** 것이다.
      · **접속선이 없는 출입구**(오늘은 보조출입구 `RS` 100 전부 — 원천이 안 준다) →
        지금까지처럼 출입구 점에서 **직선 최근접 노드**(`np.argmin`).

    ★ 왜 바꿨나(PLAN #58 · DECISIONS §616). 직선 최근접은 출입구를 **다른 도로의 노드에**
      붙일 수 있다 — 접속선과 비교하면 1,313 중 244(19%)가 다른 노드였다(노드 간 거리 중앙값
      31.7m · 최대 147.1m). `conn=None` 이면 전부 직선 최근접이다(종전 동작 그대로).
    ★ 규칙은 **「접속선이 있으면」** 이지 「`RM` 이면」이 아니다 — 원천이 `RS` 에 접속선을
      주기 시작하면 코드를 안 고쳐도 따라간다. 오늘의 `RM`/`RS` 대응은 데이터의 성질이다.
    """
    nodes = list(G.nodes); npts = np.array(nodes)
    snapn = lambda x, y: nodes[int(np.argmin((npts[:, 0]-x)**2 + (npts[:, 1]-y)**2))]
    ends = _connector_ends(conn) if conn is not None else {}
    tg = set()
    for key, g in zip(ent["ENT_MAN_NO"].astype(str), ent.geometry, strict=True):
        if not poly.contains(g):
            continue
        e = ends.get(key)
        if e is None:
            tg.add(snapn(g.x, g.y))
            continue
        # 도로 쪽 끝 = 출입구 점에서 먼 끝
        far = max(e, key=lambda q: (q[0]-g.x)**2 + (q[1]-g.y)**2)
        tg.add(snapn(far[0], far[1]))
    return tg


def access_corridor(G, ent, poly, out_dir: Path | None = None, conn=None):
    """안전센터 → 건물 출입구 최단경로의 합집합.

    출동은 소방서가 아니라 119안전센터에서 나간다. 회랑도 판정 색상을 가져야
    "안전센터에서 오는 길이 어떤 상태인가" 가 보인다.

    `conn` — 건물 접속선(`access_targets` 가 목적지 노드를 고를 때 쓴다). 없으면 종전대로다.
    반환 (corr, use).
    """
    nodes = list(G.nodes); npts = np.array(nodes)
    snapn = lambda x, y: nodes[int(np.argmin((npts[:, 0]-x)**2 + (npts[:, 1]-y)**2))]
    tgts = access_targets(G, ent, poly, conn)
    use = Counter()
    for lon, lat in STATIONS.values():
        p0 = gpd.GeoSeries([Point(lon, lat)], crs=CRS_W).to_crs(CRS_M).iloc[0]
        pa = nx.single_source_dijkstra_path(G, snapn(p0.x, p0.y), weight="length")
        for t in tgts:
            if t in pa:
                pp = pa[t]
                # 경로의 인접쌍. pp[1:] 가 하나 짧은 것이 정상이므로
                # strict=False 를 명시한다(기본값이지만 의도를 적는다).
                for a, b in zip(pp, pp[1:], strict=False):
                    use[frozenset((a, b))] += 1

    # 접근 회랑: 최단경로 중 동 밖 구간. 표출 스코프 산정에 쓴다.
    corr = []
    for k, v in use.items():
        a, b = tuple(k)
        if not (poly.contains(Point(a)) and poly.contains(Point(b))):
            e = G.edges[a, b]
            corr.append({"usage": v, "geometry": e["geom"]})
    # ★ 2026-08-21. 종전에는 모듈 최상단에서 `from paths import PROCESSED`
    #   하고 `OUT = PROCESSED` 를 잡았다. 순수 그래프 모듈이 인프라 경로를
    #   아는 구조라 (1) 단위테스트가 경로 환경변수에 걸리고
    #   (2) 다른 출력 위치로 못 부르고 (3) 계층 방향이 거꾸로였다.
    #   쓸 곳은 호출자가 정한다. 안 주면 안 쓴다.
    if corr and out_dir is not None:
        gpd.GeoDataFrame(corr, crs=CRS_M).to_file(
            out_dir / "corridor_5186.gpkg", driver="GPKG", layer="corridor")
        print(f"접근 회랑 {len(corr)}엣지 / {sum(c['geometry'].length for c in corr):,.0f}m")
    return corr, use


def station_node(pt, ends, meta, rep):
    """119안전센터가 붙을 노드 — **가장 가까운 통행 가능 구간의 가까운 끝**이다. (PLAN #120 · DECISIONS §622-2 · §623)

    ★ 최근접 노드는 막다른 골목 끝일 수 있다. 센터가 닿아야 하는 것은 노드가 아니라 **통행 가능한 길**이다.
      지산은 센터에서 12.6m 의 간선(폭 6.9m · 통과)이 있었는데 그 끝점이 30m · 112m 라서 24m 의 골목 끝에 져, 도달 노드 3 의
      컴포넌트에 갇힌 것으로 셌다. 그것은 우리 스냅의 값이었다.

    ends  [(행, 시작 좌표, 끝 좌표)] · meta  seg_id → {"blocked": bool} · rep  끝점마다의 노드 번호(`snap_groups`)

    ★ **통행 가능한 구간이 하나도 없으면 `None`** 이다(예외가 아니다). 센터가 닿을 길이 없다는 것은 오류가 아니라 **사실**이다 — 그 센터는
      도달 가능 0 으로 센다(부르는 쪽이 건너뛰고 말한다). 예외로 올리면 판정 범위(scope)를 바꾸는 순간 파이프라인 전체가 죽고, 아무 노드나
      돌려주면 「닿는다」는 거짓이 된다 — 두 길 모두 `unknown` 을 회색으로 남기는 규칙(막힌 길을 빼고 돈다 · `segments._write_route`)과 어긋난다.
    """
    from shapely.geometry import Point
    cand = [(r.geometry.distance(pt), k) for k, (r, _a, _b) in enumerate(ends)
            if not meta.get(r.seg_id, {"blocked": True})["blocked"]]
    if not cand:
        return None
    k = min(cand)[1]
    near_a = Point(ends[k][1]).distance(pt) <= Point(ends[k][2]).distance(pt)
    return rep[2 * k] if near_a else rep[2 * k + 1]

#!/usr/bin/env python3
"""
tools/route_probe.py — 소방차가 실제로 갈 수 있는 길로 경로를 낸다

    uv run python tools/route_probe.py              전체 대조
    uv run python tools/route_probe.py --lenient    모르는 곳도 통과로 본다
    uv run python tools/route_probe.py --save       data/processed/route_*.gpkg

════════════════════════════════════════════════════════════════
★ 판정을 안 바꾼다. `segments.geojson` 도 안 건드린다.
  읽고 표를 내거나 gpkg 를 따로 만든다. golden 지문은 그대로다.

── 왜 만들었나 ─────────────────────────────────────────────────
경로 탐색은 **이미 있었다.** `graph.access_corridor()` 가 119안전센터
2곳에서 건물 출입구까지 Dijkstra 를 돌리고 `route_usage` 를 낸다(579구간).

★ 2026-09-01. 아래 서술은 낡았다. `segments.py::_write_route()` 가
  이미 `edge_cost` 로 2차 경로를 내고 `route_vehicle.csv` 로 쓴다(MASTER §20-2).
  이 도구는 두 방식의 **차이를 보는** 용도로만 남는다.

**없던 것은 비용 함수다.** `weight="length"` 라 거리만 봤다.
`blocked` 159구간도 최단이면 지나갔다. 그러면 "소방차가 갈 수 있는 길" 이
아니라 **"제일 짧은 선"** 이다.

`firelane/seg/vehicle.py` 가 그 비용을 낸다 — 폭·내륜차·회전반경.

── 두 가지를 비교한다 ──────────────────────────────────────────
    현재     weight="length"          거리만
    제안     vehicle.edge_cost()      폭 · 내륜차 · 판정

차이가 나는 곳이 **"지금 지도가 잘못 안내하는 구간"** 이다.

── lenient 를 왜 두나 ──────────────────────────────────────────
`unknown` 352(32%) + `needs_cv` 190(17%) = **절반이 "모른다"** 다.
그것을 전부 막으면 그래프가 끊겨 경로가 아예 안 나온다.

    기본        모르는 곳은 비싸다 (×2.5). 보수적
    --lenient   모르는 곳도 거의 통과 (×1.2). 연결성 확인용

**어느 쪽이든 `blocked` 는 막는다.** 그것만은 판정이 확정이다.

IN    data/processed/segments_5186.gpkg
      data/processed/building_entrance_5186.gpkg (있으면)
OUT   없음. --save 를 주면 route_compare.gpkg
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import Counter

import geopandas as gpd
import networkx as nx
import numpy as np
from shapely.geometry import Point

from firelane.paths import PROCESSED
from firelane.seg import vehicle as V

# 119안전센터. graph.py 의 STATIONS 와 같은 정본을 쓴다.
from firelane.seg.graph import STATIONS

CRS_M = 5186
NODE_TOL = 0.5

C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m",
     "c": "\033[36m", "d": "\033[90m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def curvature(geom) -> float | None:
    """구간의 최소 곡률반경(m). 없으면 None(직선).

    ★ 짧은 변 사이의 각은 도로 곡률이 아니라 정점 배치 노이즈다.
      2026-08-23 에 필터 없이 쟀다가 `R=0.2m` 가 나왔다 — 노딩(0.5m 접합)이
      만든 꺾임이었다. 양쪽 변이 5m 이상일 때만 본다.
    """
    co = list(geom.coords) if geom.geom_type == "LineString" \
        else list(max(geom.geoms, key=lambda q: q.length).coords)
    best = None
    for i in range(1, len(co) - 1):
        (x0, y0), (x1, y1), (x2, y2) = co[i-1], co[i], co[i+1]
        a = math.dist((x0, y0), (x1, y1))
        b = math.dist((x1, y1), (x2, y2))
        if a < 5.0 or b < 5.0:
            continue
        c = math.dist((x0, y0), (x2, y2))
        s = abs((x1-x0)*(y2-y0) - (x2-x0)*(y1-y0)) / 2
        if s < 1e-9:
            continue
        r = a * b * c / (4 * s)
        best = r if best is None else min(best, r)
    return best


def build(seg: gpd.GeoDataFrame, lenient: bool) -> tuple[nx.Graph, dict]:
    """구간 그래프. 엣지에 두 가지 비용을 같이 단다."""
    G = nx.Graph()
    meta = {}
    for r in seg.itertuples():
        co = list(r.geometry.coords) if r.geometry.geom_type == "LineString" \
            else list(max(r.geometry.geoms, key=lambda q: q.length).coords)
        a = (round(co[0][0] / NODE_TOL), round(co[0][1] / NODE_TOL))
        b = (round(co[-1][0] / NODE_TOL), round(co[-1][1] / NODE_TOL))
        if a == b:
            continue
        rad = curvature(r.geometry)
        w = getattr(r, "width_min_m", None)
        w = None if (w is None or (isinstance(w, float) and np.isnan(w))) else float(w)
        cost = V.edge_cost(float(r.length_m), w, r.verdict, rad, lenient=lenient)
        # ★ inf 는 networkx 가 못 다룬다. 아주 큰 유한값으로 바꾸되
        #   실제 거리의 총합보다 크게 잡아 "쓰이면 반드시 티가 나게" 한다.
        big = 1e7
        prev = G.get_edge_data(a, b)
        d = {"length": float(r.length_m),
             "cost": big if cost == math.inf else cost,
             "blocked": cost == math.inf,
             "seg_uid": r.seg_uid, "verdict": r.verdict,
             "radius": rad, "geom": r.geometry}
        if prev is None or d["cost"] < prev["cost"]:
            G.add_edge(a, b, **d)
        meta[r.seg_uid] = d
    return G, meta


def run(G, weight: str) -> Counter:
    """안전센터 → 모든 노드 최단경로. 엣지 사용 횟수를 센다."""
    nodes = list(G.nodes)
    if not nodes:
        return Counter()
    npts = np.array(nodes, dtype=float)

    def snap(x, y):
        i = int(np.argmin((npts[:, 0] - x / NODE_TOL) ** 2
                          + (npts[:, 1] - y / NODE_TOL) ** 2))
        return nodes[i]

    use = Counter()
    for lon, lat in STATIONS.values():
        p = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(CRS_M).iloc[0]
        s = snap(p.x, p.y)
        if s not in G:
            continue
        paths = nx.single_source_dijkstra_path(G, s, weight=weight)
        for pp in paths.values():
            for u, v in zip(pp, pp[1:], strict=False):
                use[G.edges[u, v]["seg_uid"]] += 1
    return use


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lenient", action="store_true",
                    help="모르는 곳도 통과로 본다 (연결성 확인용)")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()

    p = PROCESSED / "segments_5186.gpkg"
    if not p.exists():
        print(col(f"{p} 가 없다. uv run fire-lane 를 먼저 돌려라.", "r"))
        return 1
    seg = gpd.read_file(p).to_crs(CRS_M)
    print(f"구간 {len(seg):,}\n")

    print(col("① 차량 제원", "c"))
    _s0 = V.spec()
    print(f"   {_s0.get('kind','?')} · 소방청 KFS-1-0073-2025-00 §3.3")
    print(f"   전폭 {V.WIDTH}m · 전장 {V.LENGTH}m · 축거 {V.WHEELBASE}m "
          f"· 최소회전반경 {V.TURN_R}m")
    print(f"   직선 필요폭 {V.required_width():.2f}m "
          f"· R={V.TURN_R}m 에서 {V.required_width(V.TURN_R):.2f}m "
          f"(내륜차 {V.offtracking(V.TURN_R):.2f}m)")
    s = V.spec()
    if not s.get("verified"):
        print(col("   ★ 미검증 제원이다 (sources.yaml vehicle_spec · "
                  "verified: false)", "y"))
        print(col("     인용 가능한 출처가 없다. D-30 동부소방서 인터뷰에서", "y"))
        print(col("     보유 차종과 실제 제원으로 바꿔야 한다.", "y"))
        print(col("     지금 결과는 참고값이지 판정이 아니다.", "y"))

    G, meta = build(seg, a.lenient)
    nblk = sum(1 for d in meta.values() if d["blocked"])
    print(f"\n{col('② 그래프', 'c')}  노드 {G.number_of_nodes():,} · "
          f"엣지 {G.number_of_edges():,}")
    print(f"   통행 불가로 본 엣지 {nblk:,}"
          + (col("  (lenient)", "d") if a.lenient else ""))
    comp = list(nx.connected_components(G))
    print(f"   연결성분 {len(comp)} · 최대 {max(len(c) for c in comp):,}노드")

    # 통행 가능한 것만으로 다시 — 그래프가 끊기는지 본다
    H = G.copy()
    H.remove_edges_from([(u, v) for u, v, d in G.edges(data=True) if d["blocked"]])
    H.remove_nodes_from(list(nx.isolates(H)))
    if H.number_of_nodes():
        ch = list(nx.connected_components(H))
        print(f"   막힌 것 제외 → 성분 {len(ch)} · "
              f"최대 {max(len(c) for c in ch):,}노드")
        print(col("   ★ 성분이 여럿이면 소방차가 못 가는 섬이 있다는 뜻이다", "d"))

    use_len = run(G, "length")
    use_veh = run(G, "cost")
    print(f"\n{col('③ 경로 비교', 'c')}  거리만 vs 차량 비용")
    print(f"   거리만 쓰는 구간   {len(use_len):,}")
    print(f"   차량 비용 쓰는 구간 {len(use_veh):,}")

    bad = [u for u in use_len if meta.get(u, {}).get("blocked")]
    print(f"\n   {col('★ 거리만 쓰면 지나가는 통행 불가 구간', 'y')} {len(bad)}")
    if bad:
        s = seg[seg.seg_uid.isin(bad)]
        cols = [c for c in ("seg_label", "verdict", "width_min_m", "length_m")
                if c in s.columns]
        print(s.sort_values("length_m", ascending=False)[cols]
              .head(12).to_string(index=False))

    tight = [(u, d) for u, d in meta.items()
             if d["radius"] and not V.can_turn(d["radius"])]
    print(f"\n{col('④ 회전 불가', 'c')} {len(tight)}구간 — "
          f"폭과 무관하게 최소회전반경 {V.TURN_R}m 미만")
    for u, d in sorted(tight, key=lambda t: t[1]["radius"])[:8]:
        r = seg[seg.seg_uid == u]
        lb = r.seg_label.iloc[0] if len(r) and "seg_label" in r else u
        print(f"   {str(lb)[:24]:26}{d['verdict']:10}R={d['radius']:6.1f}m "
              f"필요폭 {V.required_width(d['radius']):.2f}m")

    if a.save:
        seg2 = seg.copy()
        seg2["cost"] = seg2.seg_uid.map(lambda u: meta.get(u, {}).get("cost"))
        seg2["radius_m"] = seg2.seg_uid.map(lambda u: meta.get(u, {}).get("radius"))
        seg2["need_w_m"] = seg2.radius_m.map(V.required_width)
        seg2["use_len"] = seg2.seg_uid.map(lambda u: use_len.get(u, 0))
        seg2["use_veh"] = seg2.seg_uid.map(lambda u: use_veh.get(u, 0))
        dst = PROCESSED / "route_compare.gpkg"
        seg2.to_file(dst, layer="route", driver="GPKG")
        print(f"\n{col('→', 'g')} {dst}")

    print(col("\n★ 판정에 반영하지 않았다. segments.geojson 은 그대로다.", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
probe.py — 데이터를 파이프라인에 넣기 전 통과시키는 진단기.

    python src/etl/probe.py crs  data/raw/xxx.shp [--kr]
        .prj를 무시하고 좌표값만으로 실제 좌표계를 역추정한다.
        "좌표계 통일했는데 어긋난다"의 원인을 30초 만에 특정한다.

    python src/etl/probe.py topo data/processed/road_link.geojson
        선형이 교차로에서 실제로 끊겨 있는지 검사한다.
        미분할 접점 > 0 이면 다익스트라가 "경로 없음"을 뱉는다. 코드 문제가 아니다.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).parent))
from krgis.crs import CRS_METRIC, GWANGJU_BBOX, KOREA_BBOX, probe_crs  # noqa: E402

SNAP_TOL_M = 0.5


def cmd_crs(path: str, nationwide: bool = False):
    try:
        gdf = gpd.read_file(path, encoding="cp949", rows=200)
    except Exception:
        gdf = gpd.read_file(path, rows=200)
    declared = gdf.crs.to_string() if gdf.crs else "없음(.prj 부재)"
    pt = gdf.geometry.iloc[0].representative_point()
    bbox = KOREA_BBOX if nationwide else GWANGJU_BBOX

    print(f"파일       : {path}")
    print(f".prj 선언  : {declared}")
    print(f"대표 좌표  : ({pt.x:,.2f}, {pt.y:,.2f})")
    print(f"판정 범위  : {'전국' if nationwide else '광주'}\n")

    hits = probe_crs(pt.x, pt.y, bbox=bbox)
    matched = [h for h in hits if h.inside_target]
    for h in hits[:6]:
        print(" ", h)
    print()

    if not matched:
        print("✗ 어떤 후보도 대상 지역에 안 떨어진다.")
        print("  → --kr 로 전국 범위 재시도하거나 KATEC 등 비표준 좌표계를 의심하라.")
    elif len(matched) > 1:
        print(f"⚠ 후보 {len(matched)}개: {[m.epsg for m in matched]}")
        print("  → 배경지도 위에 올려 눈으로 확정하라. 5174/5181은 약 300m 차이라")
        print("    둘 다 '대충 맞아 보인다'. 어긋남의 최다 원인이다.")
    else:
        m = matched[0]
        print(f"✓ 실제 좌표계 = {m.epsg}")
        if declared != "없음(.prj 부재)" and m.epsg not in declared:
            print(f"✗ .prj({declared})가 거짓말을 하고 있다. sources.yaml에 실제값을 적어라.")


def cmd_topo(path: str):
    gdf = gpd.read_file(path).to_crs(CRS_METRIC)
    gdf = gdf[gdf.geom_type.isin(["LineString", "MultiLineString"])].explode(index_parts=False)

    ends = Counter()
    for g in gdf.geometry:
        for p in (g.coords[0], g.coords[-1]):
            ends[(round(p[0] / SNAP_TOL_M), round(p[1] / SNAP_TOL_M))] += 1
    dangles = [k for k, v in ends.items() if v == 1]
    junctions = [k for k, v in ends.items() if v >= 3]

    sindex = gdf.sindex
    unsplit = 0
    for i, g in enumerate(gdf.geometry):
        for c in (g.coords[0], g.coords[-1]):
            pt = Point(c)
            for j in sindex.query(pt.buffer(SNAP_TOL_M)):
                if j == i:
                    continue
                o = gdf.geometry.iloc[j]
                d = o.project(pt)
                if SNAP_TOL_M < d < o.length - SNAP_TOL_M and o.distance(pt) < SNAP_TOL_M:
                    unsplit += 1
                    break

    print(f"세그먼트     : {len(gdf):,}")
    print(f"고유 끝점    : {len(ends):,}")
    print(f"교차 노드(3+): {len(junctions):,}")
    print(f"단절 끝점    : {len(dangles):,}  ← 막다른 골목 + 클립 경계 + 진짜 오류")
    print(f"미분할 접점  : {unsplit:,}  ← 0이 아니면 그래프가 끊긴다\n")

    if unsplit:
        print("✗ 교차하는데 분할되지 않은 지점이 있다.")
        print("  → shapely.ops.unary_union(lines)로 노딩 후 재검사하라.")
    else:
        print("✓ 위상 정상. 그래프 구축 진행 가능.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    mode, target = sys.argv[1], sys.argv[2]
    if mode == "crs":
        cmd_crs(target, nationwide="--kr" in sys.argv)
    elif mode == "topo":
        cmd_topo(target)
    else:
        print(__doc__)

#!/usr/bin/env python3
"""
publish_basemap.py — 내비 바탕 지도의 **면**을 낸다. 도로면 · 보도.

IN    data/processed/ngii1k_5186.gpkg (수치지형도 1:1,000 도로경계 면)
      data/processed/road_rw_5186.gpkg (도로명주소 실폭도로 면)
      data/processed/ngii1k_walk_5186.gpkg (보도 면)
      web/data/view.json (maxBounds — 자르는 틀)
OUT   web/data/road_area.geojson · web/data/sidewalk.geojson
PARAM 단순화 SIMPLIFY_M · 좌표 자릿수 PREC · 크기 상한 SIZE_MAX

── 왜 생겼나 (2026-09-22 · DECISIONS §213-4) ─────────────────────
「대비가 없다」. 내비가 도로를 **판정 구간의 중심선**(1,281개)으로만 그렸다.
흰 선 위에 흰 건물이라 길과 블록이 안 갈렸고, 스코프 밖 길은 아예 없었다.
와이어프레임 09-21 은 짙은 아스팔트 면 위에 밝은 건물이다.

면 데이터는 **이미 있었다** — 폭 판정이 쓰는 수치지형도 도로경계 면과, 그것이
못 그리는 최협소 골목을 메우는 실폭도로 면(sources.yaml `road_rw.note`). 판정에만
쓰고 화면에 안 올렸을 뿐이다. 새로 들이는 데이터는 없다.

★ **판정과 무관하다.** 여기서 내는 면은 색칠용이다. 폭은 여전히
  `segments.geojson` 의 `width_min_m` 이 말한다. 면의 모양으로 폭을 읽게 하지 않는다
  — 두 소스가 합쳐지고 0.4m 단순화된 면이다.

★ 두 소스를 **합친다(union).** 도엽 경계에서 겹치고, 실폭도로가 수치지도 위에
  반쯤 겹친다. 합치지 않으면 반투명일 때 겹친 자리가 짙게 보이고 파일이 두 배다.

★ 결정적이어야 한다. `커밋된 web/data 가 최신인가` 가 재실행과 바이트 대조를
  한다 — 좌표를 자릿수로 자르고 조각을 면적 · 중심으로 정렬한다.
"""
from __future__ import annotations

import json

import geopandas as gpd
from shapely.geometry import box, mapping

from firelane.paths import ROOT

P = ROOT / "data" / "processed"
W = ROOT / "web" / "data"

#: 단순화(m). 0.4m 면 골목 모서리가 살고 파일이 1/3 이 된다
SIMPLIFY_M = 0.4
#: 좌표 자릿수. publish_web · publish_navi 와 같은 6자리(약 11cm)
PREC = 6
#: 산출 상한(두 파일 합). web/data 40MB 예산 안에서 이 몫을 못박는다
SIZE_MAX = 2 * 1024 * 1024

SOURCES = {
    "road_area": ["ngii1k_5186.gpkg", "road_rw_5186.gpkg"],
    "sidewalk": ["ngii1k_walk_5186.gpkg"],
}


def _frame() -> object:
    v = json.loads((W / "view.json").read_text(encoding="utf-8"))
    (x0, y0), (x1, y1) = v["maxBounds"]
    return gpd.GeoSeries([box(x0, y0, x1, y1)], crs=4326).to_crs(5186).iloc[0]


def _round(obj):
    if isinstance(obj, float):
        return round(obj, PREC)
    if isinstance(obj, (list, tuple)):
        return [_round(x) for x in obj]
    return obj


def build(name: str, frame) -> dict:
    parts = []
    for f in SOURCES[name]:
        path = P / f
        if not path.exists():
            raise SystemExit(f"★ {path} 가 없다 — ingest 를 먼저 돌려라. 빈 바탕을 조용히 내지 않는다")
        g = gpd.read_file(path)
        g = g[g.intersects(frame)]
        parts.extend(g.geometry.make_valid().intersection(frame))
    u = gpd.GeoSeries(parts, crs=5186).union_all().simplify(SIMPLIFY_M)
    polys = gpd.GeoSeries([u], crs=5186).explode(index_parts=False)
    polys = polys[polys.geom_type == "Polygon"]
    polys = polys[polys.area >= 1.0]                 # 1㎡ 미만 부스러기는 버린다
    key = sorted(polys, key=lambda p: (-round(p.area, 1), round(p.centroid.x, 1), round(p.centroid.y, 1)))
    out = gpd.GeoSeries(key, crs=5186).to_crs(4326)
    return {
        "type": "FeatureCollection",
        "name": name,
        "features": [
            {"type": "Feature", "properties": {},
             "geometry": _round(mapping(p))}
            for p in out
        ],
    }


def main() -> None:
    frame = _frame()
    total = 0
    for name in SOURCES:
        fc = build(name, frame)
        txt = json.dumps(fc, ensure_ascii=False, separators=(",", ":"))
        total += len(txt.encode())
        (W / f"{name}.geojson").write_text(txt, encoding="utf-8")
        print(f"  {name}.geojson  면 {len(fc['features'])} · {len(txt.encode()) / 1024:.0f}KB")
    if total > SIZE_MAX:
        raise SystemExit(f"★ 바탕 면이 {total / 1e6:.1f}MB — 상한 {SIZE_MAX / 1e6:.1f}MB 를 넘었다")


if __name__ == "__main__":
    main()

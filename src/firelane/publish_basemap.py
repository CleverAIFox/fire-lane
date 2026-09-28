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
import shapely
from shapely.geometry import MultiPolygon, box, mapping
from shapely.geometry.polygon import orient

from firelane.cli import no_args
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


def union(name: str, frame):
    """`SOURCES[name]` 를 틀 안에서 합친 면(5186 · 단순화 전). 건물 발행도 이것을 쓴다(§217-3)."""
    parts = []
    for f in SOURCES[name]:
        path = P / f
        if not path.exists():
            raise SystemExit(f"★ {path} 가 없다 — ingest 를 먼저 돌려라. 빈 바탕을 조용히 내지 않는다")
        g = gpd.read_file(path)
        g = g[g.intersects(frame)]
        parts.extend(g.geometry.make_valid().intersection(frame))
    return gpd.GeoSeries(parts, crs=5186).union_all()


def _polys(geom):
    """어떤 기하에서든 **폴리곤만** 재귀로 꺼낸다.

    ★ 2026-09-26 (§260). `GeoSeries.explode()` 는 **한 겹만** 푼다.
      `make_valid` 가 내는 `GeometryCollection` 안에 `MultiPolygon` 이 들어 있으면
      한 번 풀어도 `MultiPolygon` 이 남고, `geom_type == "Polygon"` 거름망이
      그것을 **통째로 버린다.** 실제로 그렇게 도로면 1.22km² 가 0.03km² 가 됐다 —
      고치려던 자리에서 더 큰 것을 깨뜨렸다.
    """
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if hasattr(geom, "geoms"):
        return [q for g in geom.geoms for q in _polys(g)]
    return []                                        # 선·점은 면이 아니다


def _order(polys):
    """발행 순서. **바이트 안정성**이 목적이라 면적·중심으로 못박는다."""
    return sorted(polys, key=lambda p: (-round(p.area, 9),
                                        round(p.centroid.x, 9), round(p.centroid.y, 9)))


def rfc7946(p):
    """RFC 7946 §3.1.6 — 외곽은 반시계, 구멍은 시계. (§260-4)

    ★ 지금 쓰는 렌더러는 감김을 안 본다. 그래서 **화면으로는 안 드러나는** 위반이고,
      드러나지 않는 위반은 다음 소비자가 생길 때까지 조용하다. 벡터 타일러나
      다른 파서가 붙는 날 알아차리는 것보다 지금 한 줄이 싸다.

    ★ 건물은 `MultiPolygon` 이 섞여 온다 — `orient` 는 `Polygon` 만 받으므로 편다.
    """
    if p.geom_type == "MultiPolygon":
        return MultiPolygon([orient(q, sign=1.0) for q in p.geoms])
    return orient(p, sign=1.0) if p.geom_type == "Polygon" else p


def snap_orient(g, prec: int = PREC):
    """격자 스냅 → 유효화 → RFC 7946 감김. 폴리곤이 안 남으면 None. (§260-4)

    ★ **쓰기 직전에 이 순서로** 한다. 반올림은 기하를 깨뜨리므로 반올림보다 먼저
      고치면 소용이 없다 — §260 의 결함이 정확히 그것이었다. `publish_web` 이
      `COORDINATE_PRECISION=6` 으로 드라이버에게 반올림을 맡기는데, 그 반올림이
      shapely 가 맞춰 놓은 감김을 여섯 건 도로 뒤집었다. 여기서 격자에 먼저
      앉히면 드라이버의 반올림은 이미 격자 위인 수를 다시 쓸 뿐이다.

    ★ 두 발행기가 **같은 문**으로 이것을 한다. 두 벌이면 한 쪽만 고쳐진다.
    """
    ps = _polys(shapely.make_valid(shapely.set_precision(g, 10 ** -prec)))
    if not ps:
        return None
    return rfc7946(ps[0] if len(ps) == 1 else MultiPolygon(ps))


def build(name: str, frame) -> dict:
    polys = [g for g in _polys(union(name, frame).simplify(SIMPLIFY_M)) if g.area >= 1.0]
    out = gpd.GeoSeries(_order(polys), crs=5186).to_crs(4326)

    # ★ 2026-09-26 (§260). **반올림을 기하로 한다 — 좌표를 글자로 깎지 않는다.**
    #   `_round` 가 6자리(약 11cm)로 깎는데, 그 안쪽의 두 점이 같은 점이 되면
    #   작은 고리가 점 셋 이하로 찌그러지고 폴리곤 전체가
    #   `Too few points in geometry component` 로 무효가 된다. 실제로
    #   `road_area` 가 그랬다 — 외곽 1 + 구멍 826 중 하나가 찌그러져 전체가
    #   무효였고, 렌더러가 구멍 파기를 포기해 **외곽 4.2km² 가 통째로 칠해졌다.**
    #   화면에 도로망 대신 회색 슬래브가 떴다.
    #   격자에 먼저 스냅하면 `_round` 는 이미 격자 위인 수를 다시 쓸 뿐이다.
    #
    #   하중재는 `set_precision` 이다 — 그 한 줄을 빼면 아래 관문이 운다.
    #   `make_valid` 는 스냅이 고리를 무너뜨릴 때를 위한 안전벨트고, 이 데이터로는
    #   빼도 초록이다. 단순화 **직후**에도 한 번 걸어 뒀었는데 빼도 초록이라
    #   걷어냈다 — 첫 오진(「단순화가 범인」)의 잔해였다.
    # ★ 조각마다 따로 스냅하면 안 된다. 그렇게 했더니 이웃한 두 조각의 공유 경계가
    #   따로 움직여 3.9e-12 만큼 **겹쳤고**, 건물 몫을 도로면마다 더하는 아래 검사가
    #   같은 자리를 두 번 셌다(`test_road_polygons_do_not_overlap_each_other`).
    #   통째로 넘기면 GEOS 가 전체를 한 번에 노딩해 겹침 없는 결과를 보장한다.
    snapped = _order(_polys(snap_orient(shapely.union_all(list(out)))))

    # ★ 무효면 **조용히 내보내지 않는다.** 화면이 도로망 대신 슬래브를 그리는
    #   것이 정확히 그 대가였다. 이 관문이 없어서 결함이 커밋까지 갔다.
    if (bad := sum(0 if q.is_valid else 1 for q in snapped)):
        raise SystemExit(f"★ {name}: 무효 기하 {bad}건 — 조용히 발행하지 않는다")
    return {
        "type": "FeatureCollection",
        "name": name,
        "features": [
            {"type": "Feature", "properties": {},
             "geometry": _round(mapping(p))}
            for p in snapped
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
    no_args(__doc__)          # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
    main()

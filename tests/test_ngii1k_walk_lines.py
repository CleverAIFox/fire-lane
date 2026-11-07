"""NGI 판 보도 선을 **면으로** 싣는다 — 가까운 도로 중심선의 **반대쪽**으로 폭만큼.  (Zm48 · DECISIONS §587)

IN    src/firelane/ngii1k.py (`lines_to_areas` · `build`)
OUT   없음 (검사)
밖    **실물에서 그 복원이 SHP 면과 얼마나 맞는가는 안 본다**(겹치는 도엽 45장에서 IoU 0.396 · 피복률 0.65 — §587 이 잰 값이다). 여기는 합성 도로로 **방향 · 건수 · 선언**을 민다.

★ 왜 중심 buffer 가 아닌가 — NGI 선은 보도의 **한쪽 가장자리**다(선 길이의 88.7% 가 SHP 면 경계 0.3m 안). 폭/2 로 가운데에 buffer 하면 띠가 선 양쪽으로 반씩 퍼져
  **노면 쪽으로 폭/2 가 더 깎인다.** 가장자리 선에서 띠는 한쪽으로만 난다 — 어느 쪽인지는 선의 방향이 정하지 않으므로(왼쪽 504 · 오른쪽 484) 도로 중심선에서 먼 쪽으로 정한다.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Point, Polygon

from firelane import ngii1k

ROAD = LineString([(0, 0), (100, 0)])               # 도로 중심선 y=0
SQ = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])


def _ngi(line: LineString, w: float | None) -> tuple:
    return (line, {"폭": w, "__ngi": True})


def test_the_band_lies_away_from_the_road_centerline() -> None:
    above = _ngi(LineString([(10, 3), (30, 3)]), 2.0)      # 중심선 위쪽 3m 에 있는 선
    below = _ngi(LineString([(10, -3), (30, -3)]), 2.0)
    out, st = ngii1k.lines_to_areas([above, below], [(ROAD, {})])
    assert st["converted"] == 2 and len(out) == 2
    a, b = (g for g, _ in out)
    assert a.geom_type == "Polygon" and b.geom_type == "Polygon"
    assert a.bounds == pytest.approx((10, 3, 30, 5)), a.bounds       # y 3~5 — 노면(y<3) 쪽으로 번지지 않는다
    assert b.bounds == pytest.approx((10, -5, 30, -3)), b.bounds
    assert a.area == pytest.approx(40.0) and b.area == pytest.approx(40.0)


def test_the_centered_buffer_would_have_eaten_the_carriageway() -> None:
    """카나리아 — 같은 입력에서 **중심 buffer** 는 노면 쪽(y<3)을 덮는다. 띠는 그러면 안 된다."""
    line = LineString([(10, 3), (30, 3)])
    centered = line.buffer(1.0, cap_style="flat")
    assert centered.covers(Point(20, 2.5)), "중심 buffer 가 노면 쪽을 안 덮는다 — 이 시험의 전제가 깨졌다"
    out, _ = ngii1k.lines_to_areas([_ngi(line, 2.0)], [(ROAD, {})])
    assert not out[0][0].covers(Point(20, 2.5)), "띠가 노면 쪽으로 번졌다"
    assert out[0][0].covers(Point(20, 4.0))


def test_lines_without_a_usable_width_stay_lines_and_are_counted() -> None:
    items = [_ngi(LineString([(0, 3), (9, 3)]), None), _ngi(LineString([(0, 4), (9, 4)]), 0.0), _ngi(LineString([(0, 5), (9, 5)]), -1.0)]
    out, st = ngii1k.lines_to_areas(items, [(ROAD, {})])
    assert st["converted"] == 0 and st["no_width"] == 3
    assert [g.geom_type for g, _ in out] == ["LineString"] * 3


def test_shp_lines_and_polygons_are_left_alone() -> None:
    shp_line = (LineString([(0, 3), (9, 3)]), {"폭": 2.0})                # `__ngi` 없음 — SHP 선은 면으로 안 바꾼다
    poly = (SQ, {"폭": 2.0, "__ngi": True})
    out, st = ngii1k.lines_to_areas([shp_line, poly], [(ROAD, {})])
    assert st["converted"] == 0 and st["not_ngi"] == 1
    assert [g.geom_type for g, _ in out] == ["LineString", "Polygon"]


def test_converted_items_are_marked_and_survive_build_as_polygons() -> None:
    items = [(SQ, {"폭": 2.0})] + [_ngi(LineString([(10, 3), (30, 3)]), 2.0)] * 3 + [_ngi(LineString([(0, 9), (5, 9)]), None)]
    items, _ = ngii1k.lines_to_areas(items, [(ROAD, {})])
    g = ngii1k.build("A0033320", items)
    assert len(g) == 4, "면 하나와 변환된 띠 셋이 남아야 한다 — 선이 섞여 들어와도 조용히 버려지면 안 된다"
    assert g.attrs["dropped"] == {"LineString": 1}, g.attrs["dropped"]       # 폭 없는 선만 센 채 선언된 버림
    assert sorted(g["form"]) == ["ngi_line_band"] * 3 + ["polygon"]


def test_without_any_centerline_the_side_cannot_be_chosen_so_it_raises() -> None:
    with pytest.raises(ValueError, match="중심선"):
        ngii1k.lines_to_areas([_ngi(LineString([(10, 3), (30, 3)]), 2.0)], [])

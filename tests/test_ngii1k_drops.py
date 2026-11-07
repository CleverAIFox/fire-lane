"""`ngii1k.build()` 가 **한 건이라도** 선언 없이 버리면 운다.  (Zm48 · DECISIONS §587)

IN    src/firelane/ngii1k.py
OUT   없음 (검사)
밖    **실물 원천에서 무엇이 버려지는가는 안 센다** — 그것은 `tools` 쪽 조사가 든다. 여기는 합성 입력으로 **센다 · 운다 · 선언한다** 셋이다.

★ 왜 생겼나 — `build()` 는 기하 종류가 `GEOM_OF` 와 다른 피처를 **조용히 버렸고 전부 사라질 때만 울었다.** NGI 판 보도(3,300건)가 전부 LineString 이라
  북부 12도엽의 선 1,001건이 버려져도 SHP 면 1,455건이 남아 있어 아무도 몰랐다(§577-1 · §587). 「전부 사라질 때만」은 「한 건이라도」가 아니다.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Point, Polygon

from firelane import ngii1k

SQ = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
LN = LineString([(0, 0), (5, 5)])


def test_one_undeclared_geometry_among_many_raises() -> None:
    """교차점(`A0080000` · 면)에 선 한 건이 섞여 들어오면 — 선언이 없으므로 — 건수를 대고 운다."""
    items = [(SQ, {})] * 5 + [(LN, {})]
    with pytest.raises(ValueError, match=r"1건"):
        ngii1k.build("A0080000", items)


def test_a_declared_drop_is_counted_not_silent() -> None:
    """도로경계의 선은 선언돼 있다 — 안 운다. 대신 **센다**(`g.attrs["dropped"]`)."""
    g = ngii1k.build("A0010000", [(SQ, {})] * 3 + [(LN, {})] * 2)
    assert g is not None and len(g) == 3
    assert g.attrs["dropped"] == {"LineString": 2}, g.attrs.get("dropped")


def test_nothing_dropped_means_an_empty_count() -> None:
    g = ngii1k.build("A0080000", [(SQ, {})] * 2)
    assert g.attrs["dropped"] == {}


def test_every_declared_drop_names_a_real_layer_a_real_geometry_and_a_reason() -> None:
    keys = {v[0] for v in ngii1k.LAYERS.values()}
    for key, decl in ngii1k.DROP_OK.items():
        assert key in keys, f"{key} 는 레이어가 아니다"
        for geom, why in decl.items():
            assert geom in {"Point", "LineString", "Polygon", "MultiPolygon", "MultiLineString"}, geom
            assert geom != ngii1k.GEOM_OF[key], f"{key}: 기대 기하 {geom} 는 버려지지 않는다"
            assert len(why) >= 30, f"{key}/{geom}: 사유가 너무 짧다 — 사유가 본체다"


def test_the_drop_judge_bites_the_other_way_too() -> None:
    """카나리아 — 판별식(`drops`)이 늘 빈 답이 아닌지 합성 결함으로 민다."""
    assert ngii1k.drops("A0080000", [(SQ, {})] * 4) == {}
    assert ngii1k.drops("A0080000", [(SQ, {}), (LN, {}), (Point(0, 0), {})]) == {"LineString": 1, "Point": 1}

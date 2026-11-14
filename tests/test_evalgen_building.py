"""
test_evalgen_building.py — E-1 분모가 **건물**인가.  (PLAN §13 W13-30 · DECISIONS §543-3)

`tests/test_evalgen.py` 가 700줄 상한에 닿아 따로 둔다. 합성 트리 · 헬퍼는 그쪽 것을 쓴다.

IN    tools/evalgen.py · 합성 트리(tmp_path)
OUT   없음 (검사)
PARAM 합성 건물 넷(`_put_buildings` — 1 · 2 안 · 3 범위 밖 · 4 출입구 없음)
밖    **지표값이 옳은지는 안 본다** — 분모가 건물인가 · 결손이 항으로 남는가 · 판정 산출물에 안 쓰는가.
"""
from __future__ import annotations

import hashlib

import evalgen as ev
import pytest
from test_evalgen import (
    LAT0,
    _build,
    _east,
    _ent,
    _north,
    _poly,
    _put_buildings,
    _three,
    _write_tree,
)


@pytest.fixture
def tree(tmp_path):
    """`test_evalgen.py` 의 같은 이름 픽스처와 같은 정상 합성 트리."""
    return _write_tree(tmp_path, _three(200.0, pinch_cv=True, with_detour=True))


# ── E-1 분모는 건물이다 (W13-30 · DECISIONS §543-3) ──────────────
def test_e1_denominator_is_building_and_unresolved_is_gone(tree):
    e = _build(tree)[0]["E1"]
    assert e["denominator"] == "building"
    assert "unresolved" not in e, "분모를 구현했는데 「구현 전」 서술이 남았다"
    assert e["buildings"] == 2 and e["buildings_outside_scope"] == 1


def test_e1_pairs_are_buildings_not_nodes(tree):
    """합성 그래프는 노드 셋(A · B · C)이다. 노드 분모면 쌍이 안전센터당 둘이다.
    건물 분모에서는 **건물 수**가 쌍을 센다 — 건물 하나가 노드 둘을 만들지 않고,
    같은 노드 옆 건물 둘이면 쌍도 둘이다."""
    e = _build(tree)[0]["E1"]
    stations = len(ev.STATIONS)
    assert e["pairs"] <= e["buildings"] * stations
    extra = tree / "processed"
    _put_buildings(extra, ents=[_ent(1, "RM", _east(100), LAT0), _ent(9, "RM", _east(99), LAT0),
                                _ent(2, "RM", _east(50), _north(40))],
                   polys=[_poly(1, _east(100), LAT0), _poly(9, _east(99), LAT0), _poly(2, _east(50), _north(40)),
                          _poly(3, _east(5000), LAT0), _poly(4, _east(95), _north(5))])   # 출입구는 기하로 붙는다 — 건물 9 의 면이 있어야 건물이다
    e2 = _build(tree)[0]["E1"]
    assert e2["buildings"] == e["buildings"] + 1, "노드는 같은데 건물이 늘었다 — 건물을 안 센다"
    assert 0 < e2["pairs"] - e["pairs"] <= stations, (e["pairs"], e2["pairs"])


def test_building_without_entrance_is_a_gap_not_subtracted(tree):
    """출입구 기록이 없는 범위 안 건물(4)은 분모에 안 들고 `_gaps` 에 적힌다."""
    e = _build(tree)[0]["E1"]
    g = [x for x in e["gaps"] if "building_ids" in x]
    assert g and g[0]["building_ids"] == [4], e["gaps"]


def test_the_gap_item_is_silent_without_a_missing_entrance_and_cries_with_one():
    """같은 `_gaps` 를 둘로 민다 — 결손이 없으면 조용하고, 출입구 없는 건물이 있으면 항이 선다."""
    clean = {"no_entrance": 0, "no_entrance_ids": [], "in_scope": 3}
    assert not ev._gaps({}, clean), "결손이 없는데 항이 섰다"
    assert ev._gaps({}, {"no_entrance": 1, "no_entrance_ids": [4], "in_scope": 3})[0]["building_ids"] == [4]


def test_buildings_missing_cries_instead_of_a_zero_denominator(tree):
    (tree / "processed" / "building_entrance.geojson").unlink()
    doc, why = _build(tree)
    assert why and "건물" in why[0], why
    assert set(doc) == {"gate"}


def test_the_nearest_of_several_entrances_is_the_building_node(tree):
    """한 건물에 출입구가 여럿이면 구간에 **가까운 것**이 노드를 정한다. RS 는 RM 이 없을 때만."""
    bl = ev.load_buildings(tree / "processed")
    assert isinstance(bl, tuple)
    p = tree / "processed"
    wide = _poly(1, (_east(100) + _east(50)) / 2, (LAT0 + _north(40)) / 2, d=4e-4)     # 두 출입구를 다 품는 한 건물(약 ±40m)
    _put_buildings(p, ents=[_ent(1, "RS", _east(100), LAT0), _ent(1, "RM", _east(50), _north(40))], polys=[wide])
    ents, _, stray = ev.load_buildings(p)
    assert stray == 0
    assert ents[1] == [(_east(50), _north(40))], "RM 이 있는데 RS 를 썼다"


def test_an_entrance_joins_its_building_by_geometry_and_a_far_one_is_counted_not_forced(tree):
    """★ 조인은 **기하**다(DECISIONS §320 · §781) — 지역 번호 칸이 없어도 붙고, 건물 면에서 `ENTRANCE_SNAP_M` 넘게 떨어진 출입구는 억지로 안 붙이고 센다."""
    p = tree / "processed"
    far = _ent(0, "RM", _east(100 + 3 * ev.ENTRANCE_SNAP_M), LAT0)
    _put_buildings(p, ents=[_ent(0, "RM", _east(100), LAT0), far], polys=[_poly(1, _east(100), LAT0)])
    ents, _, stray = ev.load_buildings(p)
    assert ents == {1: [(_east(100), LAT0)]} and stray == 1
    assert not ev._gaps({}, {"no_entrance": 0, "entrances_unattached": 0}), "못 붙인 것이 없는데 항이 섰다"
    assert "안 붙였다" in ev._gaps({}, {"no_entrance": 0, "entrances_unattached": stray})[0]["what"]


def test_building_denominator_leaves_judgment_files_untouched(tree):
    """평가는 읽기만 한다 — 판정 산출물은 바이트 동일."""
    names = ("segments.geojson", "route_vehicle.csv", "_manifest.json")
    h = lambda: [hashlib.sha256((tree / "processed" / n).read_bytes()).hexdigest() for n in names]  # noqa: E731 — 두 번 부르는 한 줄 헬퍼다
    before = h()
    _build(tree)
    assert h() == before


def test_a_station_snaps_to_the_passable_road_in_front_not_to_the_nearest_alley_end(monkeypatch):
    """★ 지산119안전센터가 「통행 가능 그래프에서 3 노드만 닿는다」로 나오던 원인(DECISIONS §622-2 · §782). 센터 앞 12m 에 통행 가능한
    간선이 있는데 그 끝점은 멀고, 3m 옆에 막힌 골목의 끝이 있다 — 최근접 **노드**는 골목이고 붙어야 하는 것은 간선이다."""
    def line(a, b):
        return {"type": "Feature", "properties": {"length_m": 100.0}, "geometry": {"type": "LineString", "coordinates": [list(a), list(b)]}}
    feats = [line((_east(-100), _north(12)), (_east(60), _north(12))),      # 0 간선 — 통행 가능 · 센터에서 12m · 끝점은 60m · 100m
             line((_east(2), _north(-3)), (_east(2), _north(-40)))]         # 1 골목 — 막힘 · 끝점이 센터에서 3.6m
    monkeypatch.setattr(ev, "STATIONS", {"센터": (_east(0), LAT0)})
    nid, pos = ev.build_nodes(feats)
    graph = ev.build_graph(feats, nid, None)
    alley_end, _ = ev._snap(pos, graph, _east(0), LAT0)
    assert alley_end == nid[2], "전제 — 최근접 노드는 골목 끝이다"
    at = ev.station_nodes(feats, nid, ok={0})
    assert at["센터"] == nid[1] != alley_end, "센터가 통행 가능한 간선이 아니라 골목 끝에 붙었다"
    assert ev.station_nodes(feats, nid, ok=set())["센터"] is None, "통행 가능한 길이 없는데 아무 노드나 돌려줬다"

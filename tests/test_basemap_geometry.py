#!/usr/bin/env python3
"""
test_basemap_geometry.py — **격자 · 유효화 · 감김의 순서.** (§495)

── 왜 생겼나 ───────────────────────────────────────────────────
`snap_orient` 는 발행물의 모든 폴리곤이 지나는 **한 문**이다(도로면 ·
보도 · 건물 — 두 발행기가 같이 부른다). §260 이 그 순서를 정했고,
`tools/srccov.py` 가 「시험이 이름으로도 안 부른다」로 셌다(§493).

★ 밀어 보니 **터졌다.** `shapely.set_precision` 은 **유효한 기하만** 받는다 —
  자기교차 폴리곤(8자)을 주면 `TopologyException: side location conflict` 다.
  지적·수치지도 원본에 자기교차는 흔하고(`tools/jijeok_probe.py` 는 그래서
  `buffer(0)` 을 먼저 한다), **한 건만 있어도 발행이 멈추고 어느 피처인지도
  안 말한다.** 격자 앞에 유효화를 하나 더 넣었다(§495).

★ 그 수선이 **발행물을 안 바꾼다**는 것도 여기서 든다 — 유효한 기하에
  `make_valid` 는 **글자 그대로 같은 것**을 돌려준다.

IN    없음 (합성 폴리곤)
OUT   없음 (검사)
PARAM 없음
밖    **좌표 자릿수가 몇이어야 하는가는 안 본다** — `PREC` 는 발행 예산과
      묶인 선언이고 `tests/test_contract.py` 가 발행물 쪽에서 든다.
      **면적이 맞는가도 안 본다** — 그것은 `tests/test_bbox_single_source.py`
      와 레이크 쪽 일이다. 여기가 드는 것은 **순서** 하나다.
"""
from __future__ import annotations

import shapely
from shapely.geometry import MultiPolygon, Polygon

from firelane.publish_basemap import PREC, rfc7946, snap_orient

#: 시계 방향 사각형. RFC 7946 은 외곽을 **반시계**로 요구한다.
CW = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
#: 자기교차(8자). **유효하지 않다** — 격자 스냅이 이것을 받으면 터진다.
BOWTIE = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
#: 구멍 있는 사각형. 구멍은 **시계**여야 한다.
HOLED = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)],
                [[(2, 2), (2, 4), (4, 4), (4, 2)]])


def test_valid_geometry_passes_through_make_valid_byte_for_byte():
    """★ §495 수선의 전제. 유효하면 `make_valid` 가 **같은 글자**를 낸다.

    이것이 거짓이면 격자 앞에 유효화를 넣는 것만으로 **발행물이 바뀐다.**
    """
    for g in (CW, HOLED, MultiPolygon([CW, Polygon([(5, 5), (5, 6), (6, 6)])])):
        assert shapely.make_valid(g).wkt == g.wkt, g.wkt[:40]


def test_a_self_intersecting_polygon_is_repaired_not_fatal():
    """★ 본체. 8자가 **터지지 않고** 유효한 폴리곤 둘로 갈린다.

    터지면 발행이 멈추고, 멈춘 자리가 어느 피처인지 아무도 모른다.
    """
    assert not BOWTIE.is_valid, "전제 — 이 입력은 유효하지 않다"
    got = snap_orient(BOWTIE)
    assert got is not None, "고치지 못하고 버렸다"
    assert got.is_valid, got.wkt[:60]
    assert got.geom_type == "MultiPolygon", got.geom_type
    assert len(got.geoms) == 2


def test_the_winding_follows_rfc7946_outside_and_inside():
    """외곽은 반시계 · 구멍은 시계. 렌더러는 안 보지만 다음 파서는 본다."""
    got = snap_orient(CW)
    assert shapely.is_ccw(got.exterior), "외곽이 시계다"
    h = snap_orient(HOLED)
    assert shapely.is_ccw(h.exterior) and not shapely.is_ccw(h.interiors[0]), (
        "구멍 감김이 외곽과 같다 — RFC 7946 위반이다")


def test_every_coordinate_sits_on_the_grid():
    """★ 격자에 **먼저** 앉힌다 — 드라이버의 반올림이 감김을 되뒤집지 않게.

    (§260 의 결함이 그것이었다: 드라이버가 여섯 건의 감김을 도로 뒤집었다.)
    """
    g = Polygon([(0.123456789, 0.987654321), (0, 1), (1, 1)])
    for x, y in snap_orient(g).exterior.coords:
        assert round(x, PREC) == x and round(y, PREC) == y, (x, y)


def test_something_smaller_than_the_grid_becomes_none():
    """★ 격자보다 작으면 **None** 이다 — 빈 폴리곤을 발행물에 안 넣는다."""
    tiny = Polygon([(0, 0), (0, 1e-9), (1e-9, 1e-9), (1e-9, 0)])
    assert snap_orient(tiny) is None


def test_a_zero_area_spike_is_dropped_not_published_as_a_line():
    """★ 면적 0 인 바늘은 `make_valid` 가 **선**으로 만든다 → 폴리곤이 안 남는다.

    선이 폴리곤 레이어에 실리면 화면에서 안 보이고 면적 집계만 흔든다.
    """
    spike = Polygon([(0, 0), (1, 0), (0, 0)])
    assert snap_orient(spike) is None


def test_the_single_and_multi_cases_come_back_in_their_own_shape():
    """하나면 `Polygon` · 여럿이면 `MultiPolygon`. 늘 감싸면 소비자가 둘을 본다."""
    assert snap_orient(CW).geom_type == "Polygon"
    two = MultiPolygon([CW, Polygon([(5, 5), (5, 6), (6, 6)])])
    assert snap_orient(two).geom_type == "MultiPolygon"


def test_the_winding_door_leaves_non_polygons_alone():
    """★ `rfc7946` 은 폴리곤만 돌린다 — 선·점을 받으면 그대로 돌려준다."""
    from shapely.geometry import LineString

    ln = LineString([(0, 0), (1, 1)])
    assert rfc7946(ln) is ln


def test_a_valid_polygon_is_byte_stable_through_the_door():
    """★ 유효한 입력은 **글자까지** 그대로 다시 나온다.

    발행물 안정성이 거기 걸린다 — 같은 원본에서 두 번 발행하면 바이트가
    같아야 하고, 아니면 `tests/test_write_stable.py` 가 매번 「달라졌다」로
    열차를 세운다. 실물 입력(gpkg 폴리곤)은 **유효한 쪽**이다.
    """
    for g in (CW, HOLED):
        once = snap_orient(g)
        assert snap_orient(once).wkt == once.wkt, g.wkt[:40]


def test_a_repaired_polygon_is_the_same_shape_but_not_the_same_string():
    """★ **고친 것은 글자가 돌 수 있다** — 적어 둔다. 기하는 같다.

    `orient` 가 고리의 시작 꼭짓점을 다시 고르므로, 수선된 기하를 한 번 더
    통과시키면 WKT 가 **회전**한다. 실제 발행은 원본에서 **한 번만** 지나가니
    문제가 아니지만, 「멱등이다」로 적어 두면 다음 사람이 그 말을 믿고
    수선 결과를 다시 넣는다. 그래서 **기하 동일**까지만 약속한다.
    """
    once = snap_orient(BOWTIE)
    twice = snap_orient(once)
    assert twice.equals(once), "기하가 달라졌다 — 그건 결함이다"
    assert twice.wkt != once.wkt, (
        "글자까지 같아졌다 — `orient` 의 시작점 선택이 바뀌었으면 위 설명을 고쳐라")

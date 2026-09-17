"""안전센터 출발 도로가 판정망 필터에서 빠지지 않는지 검증한다."""
import pytest
from shapely.geometry import LineString, Point, box

from firelane.seg.scope import display_scope, judgment_scope


@pytest.fixture
def scope_inputs():
    return box(0, 0, 100, 100), [LineString([(100, 50), (600, 50)])], [Point(1000, 1000)]


def test_station_roads_are_judged_without_a_corridor(scope_inputs):
    boundary, _, stations = scope_inputs
    keep = judgment_scope(boundary, [], stations)
    assert LineString([(1200, 1000), (1299, 1000)]).intersects(keep)
    assert not LineString([(1301, 1000), (1320, 1000)]).intersects(keep)


def test_boundary_crossing_short_connector_is_kept_whole(scope_inputs):
    keep = judgment_scope(*scope_inputs)
    connector = LineString([(1299, 1000), (1301, 1000)])
    assert connector.intersects(keep)
    assert not keep.covers(connector)
    # 최종 필터는 intersects. 짧은 연결부도 경계에서 절단하거나 제거하지 않는다.
    assert [g for g in [connector] if g.intersects(keep)] == [connector]


def test_existing_boundary_and_corridor_remain_in_scope(scope_inputs):
    keep = judgment_scope(*scope_inputs)
    assert keep.covers(Point(-49, 50))
    assert keep.covers(Point(400, 119))
    assert not keep.covers(Point(400, 121))


def test_display_scope_covers_judgment_scope(scope_inputs):
    keep = judgment_scope(*scope_inputs)
    display = display_scope(*scope_inputs)
    # ★ 2026-09-17 (§182-7). 닫힘 · 외곽선 재구성으로 경계 좌표가 부동소수 수준에서 달라져 `covers` 가
    #   경계 위 점 하나로 거짓이 된다. 뜻은 "판정 범위가 표출 범위 밖으로 삐져나오지 않는다" — 면적으로 본다.
    assert keep.difference(display).area < 1e-6
    assert display.covers(Point(-59, 50))
    assert not keep.covers(Point(-59, 50))


def test_duplicate_station_points_do_not_expand_scope(scope_inputs):
    boundary, corridors, stations = scope_inputs
    assert judgment_scope(boundary, corridors, stations).equals(
        judgment_scope(boundary, corridors, stations + stations)
    )


def test_missing_stations_fail_explicitly(scope_inputs):
    boundary, corridors, _ = scope_inputs
    with pytest.raises(ValueError, match="안전센터"):
        judgment_scope(boundary, corridors, [])


def test_ingest_bounds_cover_station_circles_and_width_context():
    """판정 범위를 늘려도 입력 추출 BBOX가 먼저 잘라내면 도로가 다시 누락된다."""
    from pathlib import Path

    import yaml
    from shapely.ops import transform

    pyproj = pytest.importorskip("pyproj")
    from firelane.seg.params import STATION_RADIUS, STATIONS, WMAX_CAP

    root = Path(__file__).resolve().parents[1]
    bounds = yaml.safe_load((root / "sources.yaml").read_text(encoding="utf-8"))["bbox_4326"]
    to_metric = pyproj.Transformer.from_crs(4326, 5186, always_xy=True).transform
    to_wgs = pyproj.Transformer.from_crs(5186, 4326, always_xy=True).transform
    for name, coords in STATIONS.items():
        needed = transform(to_metric, Point(coords)).buffer(STATION_RADIUS + WMAX_CAP)
        assert box(*bounds).covers(transform(to_wgs, needed)), name


def test_display_scope_has_no_notches_or_holes():
    """§182-7 — 표출 범위에 안쪽 구멍 · 좁은 틈이 없다. 판정 범위는 그대로다."""
    boundary = box(0, 0, 400, 400)
    ring = [LineString([(400, 200), (1000, 200), (1000, 800), (200, 800), (200, 400)])]   # 동을 감아 도는 회랑
    station = [Point(1000, 200)]
    keep = judgment_scope(boundary, ring, station)
    display = display_scope(boundary, ring, station)
    assert keep.difference(display).area < 1e-6
    parts = display.geoms if hasattr(display, "geoms") else [display]
    assert all(len(p.interiors) == 0 for p in parts), "안쪽 구멍이 마스크 섬으로 남는다"
    assert display.covers(Point(600, 500)), "회랑이 둘러싼 블록이 까맣게 덮인다"
    assert not keep.covers(Point(600, 500)), "프로브 — 판정 범위는 넓히지 않는다"
    far = display_scope(boundary, [], [Point(5000, 5000)])
    assert not far.covers(Point(2500, 2500)), "닫힘이 떨어진 조각 사이를 잇는다 — 반경이 과하다"

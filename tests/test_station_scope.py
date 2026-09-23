"""안전센터 출발 도로가 판정망 필터에서 빠지지 않는지 검증한다."""
import pytest
from shapely.geometry import LineString, Point, box

# ★ 2026-09-23 (PLAN §13 W3-6). `display_scope` 는 판정 지문 밖(`firelane/display_scope.py`)
#   으로 옮겼다. 판정 범위는 `seg/scope.py` 에 그대로다 — 여기서 둘을 같이 본다.
from firelane.display_scope import display_scope
from firelane.seg.scope import judgment_scope


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


# ── 표출 범위는 **자기 단계**다 (2026-09-23 · PLAN §13 W3-6) ───────────────────
def _pipeline():
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("pipeline", root / "src/firelane/pipeline.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["pipeline"] = m        # @dataclass 가 sys.modules 를 되짚는다
    spec.loader.exec_module(m)
    return m


def test_scope_step_is_declared_between_segments_and_its_readers():
    """`scope` 단계가 선언돼 있고 순방향인가.

    ★ 표출 계산이 `segments` 안에 있으면 표출 상수가 판정 지문 안이다(W3-6). 꺼내되
      **순서는 그대로여야 한다** — 회랑을 내는 segments 뒤, 스코프를 읽는 ortho·publish 앞.
      한 칸만 밀려도 ortho 가 지난 실행의 스코프로 정사영상을 굽는다(2026-09-04 에 고친 그 병).
    """
    m = _pipeline()
    names = [s.name for s in m.STEPS]
    assert "scope" in names, "표출 범위 단계가 STEPS 에 없다 — `--from scope` 도 못 쓴다"
    step = next(s for s in m.STEPS if s.name == "scope")
    assert step.module == "display_scope"
    assert names.index("segments") < names.index("scope")
    for reader in ("ortho", "publish"):
        assert names.index("scope") < names.index(reader), f"{reader} 가 스코프를 먼저 읽는다"

    P = m.PROCESSED
    assert step.writes == (P / "scope_5186.gpkg",) and not step.mutates
    assert set(step.reads) == {P / "boundary_emd_5186.gpkg", P / "corridor_5186.gpkg",
                               P / "fire_station.geojson"}
    seg = next(s for s in m.STEPS if s.name == "segments")
    assert P / "scope_5186.gpkg" not in seg.produces, (
        "segments 가 아직 스코프를 낸다 — 두 단계가 같은 파일을 쓰면 순서가 결과를 바꾼다")
    assert P / "corridor_5186.gpkg" in seg.writes, "회랑은 segments 가 낸다(scope 의 입력)"


def test_scope_step_invalidates_its_readers():
    """`--only scope` 로 돌리면 하류(ortho · publish)가 낡는다고 말하는가."""
    m = _pipeline()
    assert {s.name for s in m.downstream({"scope"})} >= {"ortho", "publish"}
    # 반대 방향 — segments 만 돌려도 scope 가 낡는다(회랑이 바뀐다)
    assert "scope" in {s.name for s in m.downstream({"segments"})}


def test_scope_step_module_does_not_import_judgment_stage():
    """표출 단계가 `segments` 를 import 하면 지문 계산이 거꾸로 선다."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    src = (root / "src/firelane/display_scope.py").read_text(encoding="utf-8")
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
    assert "firelane.segments" not in mods
    assert "firelane.seg.scope" in mods, "판정 범위 규칙의 정본은 seg/scope.py 하나다"

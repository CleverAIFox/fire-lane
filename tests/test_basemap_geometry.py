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

from pathlib import Path

import geopandas as gpd
import pytest
import shapely
from shapely.geometry import MultiPolygon, Polygon, box

import firelane.publish_basemap as PB
from firelane.ledger import load_sources
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


# ── PLAN 행 144(닫힘) — 토지이용 면: 읽는 코드가 **진짜로 그 키를 읽는다** ─────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[1]


def _landuse_gpkg(tmp_path: Path, rows: list[tuple[str, Polygon]]) -> Path:
    """`vworld_uq153_5186.gpkg` 꼴 — 5186 · `DGM_NM` 한 칸."""
    g = gpd.GeoDataFrame({"DGM_NM": [n for n, _ in rows]}, geometry=[p for _, p in rows], crs=5186)
    g.to_file(tmp_path / PB.LANDUSE_FILE, driver="GPKG")
    return tmp_path


def test_landuse_class_is_green_only_when_the_name_says_so() -> None:
    assert [PB.landuse_class(n) for n in ("근린공원", "소공원", "완충녹지", "유원지", "기타 공원시설")] == ["green"] * 5
    assert [PB.landuse_class(n) for n in ("공공공지", "광장", "", None, 3)] == ["plaza"] * 5, "낱말이 없는데 녹지로 칠했다"


def _uq164_gpkg(tmp_path: Path, rows: list[tuple[str, Polygon]]) -> None:
    """`vworld_uq164_5186.gpkg` 꼴 — 5186 · `MNUM`(분류 코드 `UQVnn` 가 안에 든다) 한 칸."""
    g = gpd.GeoDataFrame({"MNUM": [f"64600001211020130350UQV{c}00086000" for c, _ in rows]}, geometry=[p for _, p in rows], crs=5186)
    g.to_file(tmp_path / f"{PB.INST_STEM}_5186.gpkg", driver="GPKG")


def _jijeok_gpkg(tmp_path: Path, rows: list[tuple[str, Polygon]]) -> None:
    """`jijeok_5186.gpkg` 꼴 — 5186 · `A5`(지번 + 지목 끝 글자)."""
    g = gpd.GeoDataFrame({"A5": [n for n, _ in rows]}, geometry=[p for _, p in rows], crs=5186)
    g.to_file(tmp_path / f"{PB.PARCEL_STEM}_5186.gpkg", driver="GPKG")


def _sq(x: float, y: float, w: float) -> Polygon:
    return Polygon([(x, y), (x, y + w), (x + w, y + w), (x + w, y)])                  # 시계(CW) 로 준다


def test_build_landuse_keeps_the_class_clips_to_the_frame_and_is_valid_and_deterministic(tmp_path, monkeypatch) -> None:
    _landuse_gpkg(tmp_path, [("근린공원", _sq(0, 0, 40)), ("공공공지", _sq(100, 0, 30)), ("소공원", _sq(900, 900, 40))])
    _uq164_gpkg(tmp_path, [("32", _sq(0, 100, 20))])
    _jijeok_gpkg(tmp_path, [("1-1 임", _sq(0, 150, 20))])
    monkeypatch.setattr(PB, "P", tmp_path)
    frame = box(-10, -10, 200, 200)                                   # 셋째 면은 틀 밖이다
    fc = PB.build_landuse(frame)
    got = sorted(f["properties"]["cls"] for f in fc["features"])
    assert got == ["green", "inst", "jm_forest", "plaza"], f"틀 밖 면이 남았거나 갈래를 잃었다: {got}"
    assert all(set(f["properties"]) == {"cls"} for f in fc["features"]), "속성이 갈래 하나가 아니다(원천 칸을 새로 흘렸다)"
    assert PB.build_landuse(frame) == fc, "같은 입력이 다른 출력을 냈다 — 바이트 안정성이 깨졌다"
    for f in fc["features"]:
        ring = f["geometry"]["coordinates"][0]
        area2 = sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))
        assert area2 > 0, "외곽이 시계방향이다 — RFC 7946 위반"


def test_a_university_and_a_face_over_ten_percent_of_the_frame_are_lines_not_fills(tmp_path, monkeypatch) -> None:
    """★ DECISIONS §768. 대학(UQV35)과 틀의 10% 넘는 면은 **칠하지 않고 경계선만** — 캠퍼스 안에 길이 있다. 작은 학교(UQV32)는 칠한다."""
    _landuse_gpkg(tmp_path, [("근린공원", _sq(0, 0, 10))])
    _uq164_gpkg(tmp_path, [("35", _sq(0, 20, 30)), ("32", _sq(0, 60, 20)), ("80", _sq(100, 20, 120))])    # 대학 · 학교 · 틀 10% 넘는 체육
    _jijeok_gpkg(tmp_path, [("1-1 임", _sq(0, 150, 10))])
    monkeypatch.setattr(PB, "P", tmp_path)
    frame = box(0, 0, 200, 200)                                       # 면적 40,000 — 120×120(14,400 · 36%) 은 10% 를 넘는다
    fc = PB.build_landuse(frame)
    kinds = sorted((f["properties"]["cls"], f["geometry"]["type"]) for f in fc["features"])
    assert ("campus", "LineString") in kinds and kinds.count(("campus", "LineString")) + kinds.count(("campus", "MultiLineString")) >= 2, kinds
    assert not any(c == "inst" and t != "Polygon" for c, t in kinds)
    assert sum(1 for c, _ in kinds if c == "inst") == 1, f"칠하는 학교 면이 하나(UQV32)여야 한다: {kinds}"


def test_parcels_are_dissolved_by_land_category_and_roads_and_lots_are_left_out(tmp_path, monkeypatch) -> None:
    """★ 필지마다가 아니라 **지목별로 합친다**(모자이크 · 경계선 467km 를 피한다). 도로(`도`)는 뺀다(도로면이 따로 그려진다) · 대지(`대`)는 `daeji` 가 든다."""
    _landuse_gpkg(tmp_path, [("근린공원", _sq(0, 0, 10))])
    _uq164_gpkg(tmp_path, [("32", _sq(0, 20, 10))])
    # 임야 필지 둘이 맞닿는다 → 한 덩어리로 합쳐진다 · 도로 · 대지는 landuse 에 안 든다
    _jijeok_gpkg(tmp_path, [("1-1 임", _sq(0, 100, 20)), ("1-2임", _sq(20, 100, 20)), ("2-1 도", _sq(0, 130, 20)), ("3-1 대", _sq(0, 160, 20))])
    monkeypatch.setattr(PB, "P", tmp_path)
    frame = box(-10, -10, 200, 200)
    fc = PB.build_landuse(frame)
    jm = [f for f in fc["features"] if f["properties"]["cls"].startswith("jm_")]
    assert [f["properties"]["cls"] for f in jm] == ["jm_forest"], "도로 · 대지가 landuse 에 들었거나 합치지 않았다"
    assert len(jm[0]["geometry"]["coordinates"]) == 1, "맞닿은 두 필지가 한 면으로 합쳐지지 않았다(안쪽 경계가 남는다)"
    dj = PB.build_daeji(frame)
    assert [f["properties"]["cls"] for f in dj["features"]] == ["daeji"], "대지가 daeji 에 안 들었다"


def test_land_category_buckets() -> None:
    assert PB._jm_bucket("도") is None and PB._jm_bucket("대") is None and PB._jm_bucket(None) is None
    assert PB._jm_bucket("임") == "forest" and PB._jm_bucket("학") == "inst" and PB._jm_bucket("차") == "paved" and PB._jm_bucket("공") == "green"


def test_build_landuse_dies_without_its_source_instead_of_publishing_an_empty_layer(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(PB, "P", tmp_path)
    with pytest.raises(SystemExit, match="조용히 내지 않는다"):
        PB.build_landuse(box(0, 0, 1, 1))


def test_the_ledger_names_publish_basemap_as_the_consumer_and_the_code_really_reads_that_key() -> None:
    """★ 집계를 이기는 길을 막는다 — 대장 `feeds` 에 파일 이름만 적고 코드가 그 키를 안 읽으면 `unused` 가 줄어 보이기만 한다."""
    ledger = load_sources()["datasets"][PB.LANDUSE_STEM]
    assert "src/firelane/publish_basemap.py" in ledger["feeds"], "대장이 소비처를 안 적었다"
    assert ledger["kind"] == "shp_zip", "적재가 안 되는 종류(raw_only)다 — 읽을 파일이 안 나온다"
    src = (ROOT / "src/firelane/publish_basemap.py").read_text(encoding="utf-8")
    assert f'LANDUSE_STEM = "{PB.LANDUSE_STEM}"' in src and "gpd.read_file(path)" in src and "build_landuse" in src.split("def main")[1], \
        "발행기가 대장이 적은 키를 실제로 읽어 내지 않는다 — 이름만 적은 소비처다"


def test_the_published_land_cover_files_are_under_their_caps_and_carry_the_agreed_classes() -> None:
    """★ DECISIONS §768. 커밋된 `landuse.geojson` · `daeji.geojson` — 상한 아래 · 갈래는 약속한 것만 · 대학 경계선이 있다 · 도로 지목(`jm_`)이 칠로 안 들었다."""
    import json as _json
    lu_p, dj_p = PB.W / "landuse.geojson", PB.W / "daeji.geojson"
    assert lu_p.stat().st_size <= PB.LANDUSE_SIZE_MAX and dj_p.stat().st_size <= PB.DAEJI_SIZE_MAX
    lu = _json.loads(lu_p.read_text(encoding="utf-8"))["features"]
    ok = {"green", "plaza", "inst", "campus", "jm_forest", "jm_farm", "jm_water", "jm_inst", "jm_green", "jm_paved"}
    assert {f["properties"]["cls"] for f in lu} <= ok, "약속 밖 갈래(도로 · 대지가 landuse 에 들었나)"
    assert any(f["properties"]["cls"] == "campus" and f["geometry"]["type"].endswith("LineString") for f in lu), "대학 경계선이 없다"
    assert not any(f["properties"]["cls"] == "inst" and f["geometry"]["type"] != "Polygon" for f in lu)
    dj = _json.loads(dj_p.read_text(encoding="utf-8"))["features"]
    assert dj and {f["properties"]["cls"] for f in dj} == {"daeji"}

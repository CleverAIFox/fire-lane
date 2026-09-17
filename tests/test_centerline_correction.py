"""승인 중심선 보정이 위치만 고치고 접속 위상을 보존하는지 검증한다."""
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
import pytest
from shapely.geometry import LineString, box

from firelane.seg.centerline_correction import (
    PILMUN_289,
    BranchTrim,
    CorrectionSpec,
    RoadKey,
    apply_approved_centerline_corrections,
    apply_centerline_correction,
    centerline_id,
    geometry_sha256,
)
from firelane.seg.graph import build_graph
from firelane.segments import endpoint_snap


def _center_id(geometry, width=4.0):
    row = pd.Series(
        {
            "도로명": "테스트길",
            "도로폭": width,
            "차로수": 1.0,
            "포장재질": "아스팔트",
            "일방통행": "양방통행",
            "geometry": geometry,
        }
    )
    return centerline_id(row)


def _inputs():
    anchor = LineString([(-5, 0), (5, 0)])
    old = LineString([(0, 0), (2, 2), (6, 2)])
    branch_a = LineString([(3, 2), (3, -2)])
    branch_b = LineString([(5, 2), (5, -2)])
    untouched = LineString([(-4, 0), (-4, 3)])
    road = gpd.GeoDataFrame(
        [
            ("1", 10, "R", "테스트길", anchor),
            ("1", 11, "R", "테스트길", old),
            ("1", 12, "R", "테스트길", branch_a),
            ("1", 13, "R", "테스트길", branch_b),
            ("1", 14, "R", "테스트길", untouched),
        ],
        columns=["SIG_CD", "RDS_MAN_NO", "RN_CD", "RN", "geometry"],
        crs=5186,
    )
    center_geometries = [
        LineString([(0.1, 0), (3, 1)]),
        LineString([(3, 1), (5, 1), (6, 2.1)]),
    ]
    centers = gpd.GeoDataFrame(
        [
            ("테스트길", 4.0, 1.0, "아스팔트", "양방통행", geometry)
            for geometry in center_geometries
        ],
        columns=["도로명", "도로폭", "차로수", "포장재질", "일방통행", "geometry"],
        crs=5186,
    )
    merged_length = sum(geometry.length for geometry in center_geometries)
    spec = CorrectionSpec(
        correction_id="test",
        target=RoadKey("1", 11, "R", "테스트길"),
        source_geometry_sha256=geometry_sha256(old),
        centerline_ids=tuple(_center_id(geometry) for geometry in center_geometries),
        branches=(
            BranchTrim(RoadKey("1", 12, "R", "테스트길"), geometry_sha256(branch_a), 1.0),
            BranchTrim(RoadKey("1", 13, "R", "테스트길"), geometry_sha256(branch_b), 1.0),
        ),
        anchor=RoadKey("1", 10, "R", "테스트길"),
        expected_length_m=merged_length,
        max_start_shift_m=0.5,
        max_end_shift_m=0.5,
    )
    return road, centers, spec


def test_correction_replaces_target_and_trims_branches_only():
    road, centers, spec = _inputs()
    before = road.copy()
    corrected, report = apply_centerline_correction(road, centers, spec)

    assert road.geometry.equals(before.geometry), "입력 GeoDataFrame을 직접 바꾸면 안 된다"
    assert report.target_rds_man_no == 11
    assert tuple(rds for rds, _ in report.trimmed_branches_m) == (12, 13)
    assert tuple(length for _, length in report.trimmed_branches_m) == pytest.approx((1.0, 1.0))
    assert corrected.loc[corrected.RDS_MAN_NO == 11].geometry.iloc[0].length == pytest.approx(
        spec.expected_length_m
    )
    assert corrected.loc[corrected.RDS_MAN_NO == 12].geometry.iloc[0].coords[0] == pytest.approx(
        (3, 1)
    )
    assert corrected.loc[corrected.RDS_MAN_NO == 13].geometry.iloc[0].coords[0] == pytest.approx(
        (5, 1)
    )
    for rds in (10, 14):
        assert corrected.loc[corrected.RDS_MAN_NO == rds].geometry.iloc[0].equals(
            before.loc[before.RDS_MAN_NO == rds].geometry.iloc[0]
        )
    assert corrected.drop(columns="geometry").equals(before.drop(columns="geometry"))


def test_correction_preserves_graph_node_and_edge_counts():
    road, centers, spec = _inputs()
    corrected, _ = apply_centerline_correction(road, centers, spec)
    scope = box(-10, -10, 10, 10)
    old_graph, _ = build_graph(road, scope, endpoint_snap)
    new_graph, _ = build_graph(corrected, scope, endpoint_snap)
    assert (new_graph.number_of_nodes(), new_graph.number_of_edges()) == (
        old_graph.number_of_nodes(),
        old_graph.number_of_edges(),
    )
    expected_degrees = {(0.1, 0): 3, (3, 1): 3, (5, 1): 3, (6, 2.1): 1}
    for point, degree in expected_degrees.items():
        node = min(new_graph.nodes, key=lambda value: (value[0] - point[0]) ** 2 + (value[1] - point[1]) ** 2)
        assert nx.degree(new_graph, node) == degree


def test_changed_source_geometry_fails_loudly():
    road, centers, spec = _inputs()
    road.loc[road.RDS_MAN_NO == 11, "geometry"] = LineString([(0, 0), (6, 2)])
    with pytest.raises(ValueError, match="원본 geometry"):
        apply_centerline_correction(road, centers, spec)


def test_missing_approved_centerline_fails_loudly():
    road, centers, spec = _inputs()
    with pytest.raises(ValueError, match="승인한 NGII"):
        apply_centerline_correction(road, centers.iloc[:1].copy(), spec)


def test_pilmun_289_real_data_preserves_approved_topology():
    """로컬에 실제 processed 입력이 있으면 승인 대상 3행과 위상을 함께 고정한다."""
    processed = Path(__file__).resolve().parents[1] / "data" / "processed"
    paths = {
        "road": processed / "road_link_5186.gpkg",
        "center": processed / "ngii1k_center_5186.gpkg",
        "boundary": processed / "boundary_emd_5186.gpkg",
    }
    if not all(path.exists() for path in paths.values()):
        pytest.skip("processed GIS 입력이 없는 CI에서는 런타임 가드가 같은 계약을 검사한다")

    road = gpd.read_file(paths["road"]).to_crs(5186)
    centers = gpd.read_file(paths["center"]).to_crs(5186)
    boundary = gpd.read_file(paths["boundary"]).to_crs(5186)
    corrected, reports = apply_approved_centerline_corrections(road, centers)

    changed = {
        int(road.at[idx, "RDS_MAN_NO"])
        for idx in road.index
        if not road.at[idx, "geometry"].equals(corrected.at[idx, "geometry"])
    }
    assert changed == {1109, 2888, 2889}
    assert road.drop(columns="geometry").equals(corrected.drop(columns="geometry"))
    assert reports[0].corrected_length_m == pytest.approx(95.7800073)
    assert "NC-F8B3DA6F96C8" not in PILMUN_289.centerline_ids

    poly = boundary.loc[boundary.EMD_CD == "12210108", "geometry"].iloc[0]
    old_graph, _ = build_graph(road, poly, endpoint_snap)
    new_graph, _ = build_graph(corrected, poly, endpoint_snap)
    assert (old_graph.number_of_nodes(), old_graph.number_of_edges()) == (2877, 3470)
    assert (new_graph.number_of_nodes(), new_graph.number_of_edges()) == (2877, 3470)

    expected_degrees = {
        (193386.167, 283289.110): 3,
        (193429.979, 283276.166): 3,
        (193437.261, 283289.736): 3,
        (193445.332, 283304.935): 1,
    }
    for point, degree in expected_degrees.items():
        node = min(
            new_graph.nodes,
            key=lambda value: (value[0] - point[0]) ** 2 + (value[1] - point[1]) ** 2,
        )
        assert (node[0] - point[0]) ** 2 + (node[1] - point[1]) ** 2 < 0.1**2
        assert new_graph.degree[node] == degree


def test_fingerprint_ignores_trailing_bits_across_machines():
    """★ 2026-09-16. 재투영 말단 비트가 다른 같은 선은 같은 지문이어야 한다(DECISIONS §170-2).

    원판은 WKB 를 그대로 해시해 라이브러리 판 · 원본이 같은데도 기계가 다르면 승인 지문 셋이 전부
    어긋났다. 1e-9m 흔들림은 부동소수 말단이지 위치 변경이 아니다.
    """
    base = LineString([(193386.29295753533, 283289.24531015434), (193400.1234567, 283300.7654321)])
    jitter = LineString([(x + 3e-10, y - 4e-10) for x, y in base.coords])
    assert base.wkb != jitter.wkb
    assert geometry_sha256(base) == geometry_sha256(jitter)


def test_fingerprint_still_pins_the_position():
    """반대쪽 — 격자가 너무 무르면 옮겨진 선에 승인된 보정이 붙는다. 2mm 옮기면 달라야 한다."""
    base = LineString([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)])
    moved = LineString([(0.0, 0.0), (10.0, 0.002), (10.0, 5.0)])
    assert geometry_sha256(base) != geometry_sha256(moved)

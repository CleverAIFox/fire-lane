"""R1 — 하이브리드 뼈대와 대조의 순수 함수. 합성 기하(EPSG:5186 미터). (DECISIONS §184)"""
from __future__ import annotations

import geopandas as gpd
import shapely
from shapely.geometry import LineString, Polygon, box

from firelane import skeleton as S


def gdf(lines, **cols):
    return gpd.GeoDataFrame(cols, geometry=lines, crs=5186)


def test_degree2_chain_merges_into_one_edge():
    parts = [LineString([(0, 0), (10, 0)]), LineString([(10, 0), (20, 0)]), LineString([(20, 0), (30, 0)])]
    out = S.merge_degree2(parts)
    assert len(out) == 1 and abs(out[0].length - 30) < 1e-6


def test_crossing_splits_at_node():
    out = S.merge_degree2([LineString([(0, 0), (20, 0)]), LineString([(10, -10), (10, 10)])])
    assert len(out) == 4, "교차점에서 끊겨야 한다"


def test_connector_only_within_gap_and_not_when_touching():
    a = LineString([(0, 0), (10, 0)])
    near = LineString([(11.5, -5), (11.5, 5)])      # a 끝에서 1.5m
    far = LineString([(13.0, -5), (13.0, 5)])       # 3m
    assert len(S.connectors([a], [near])) == 1
    assert S.connectors([a], [far]) == []
    touching = LineString([(10, 0), (10, 10)])
    assert S.connectors([a, touching], []) == [], "이미 닿은 끝(차수 2)을 잇는다"


def test_fallback_keeps_only_parts_ngii_does_not_cover():
    ngii = [LineString([(0, 0), (50, 0)])]
    rl = [LineString([(0, 2), (50, 2)]), LineString([(0, 40), (50, 40)])]
    fb = S.fallback(rl, ngii)
    assert len(fb) == 1 and fb[0].coords[0][1] == 40, "NGII 5m 안의 road_link 가 남았다"


def test_match_accepts_offset_parallel_rejects_far_or_crossing():
    edges = [LineString([(0, 0), (100, 0)])]
    tree = shapely.STRtree(edges)
    j, share, off = S.match(LineString([(10, 3), (60, 3)]), edges, tree)
    assert j == 0 and share == 1.0 and off == 3.0
    assert S.match(LineString([(10, 12), (60, 12)]), edges, tree)[0] is None, "8m 밖을 매칭했다"
    assert S.match(LineString([(50, -20), (50, 20)]), edges, tree)[1] < S.MATCH_SHARE, "직교 선을 매칭했다"


def test_parallel_pairs_flags_dual_carriageway_only_when_wide():
    # ★ 2026-09-18 (§189-2). 이름 조건이 붙었다 — 같은 도로명끼리만 쌍선이다.
    e = gdf([LineString([(0, 0), (100, 0)]), LineString([(0, 10), (100, 10)]), LineString([(0, 60), (100, 60)])],
            도로폭=[8.0, 8.0, 8.0], 도로명=["가길", "가길", "가길"])
    assert S.parallel_pairs(e) == [True, True, False]
    e["도로폭"] = [4.0, 4.0, 4.0]
    assert S.parallel_pairs(e) == [False, False, False]


def test_build_tags_sources_and_compare_flags_suspects():
    keep = box(-10, -60, 210, 60)
    ngii = gdf([LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])],
               도로폭=[3.0, 3.0], 도로명=["가길", "가길"], 분리대유무=["무", "무"])
    rl = gdf([LineString([(0, 1), (200, 1)]), LineString([(50, 40), (150, 40)])])
    edges = S.build(ngii, rl, keep)
    assert set(edges["src"]) == {"ngii", "fallback"}
    assert (edges.loc[edges.src == "ngii", "length_m"] == 200.0).all(), "차수 2 병합이 안 됐다"
    segs = gdf([LineString([(10, 1), (90, 1)]), LineString([(60, 40), (140, 40)]), LineString([(20, -30), (80, -30)])],
               seg_uid=["A", "B", "C"], verdict=["blocked", "clear", "unknown"], width_min_m=[0.8, 5.0, 2.0])
    bldg = gpd.GeoDataFrame(geometry=[Polygon([(30, 0.5), (50, 0.5), (50, 5), (30, 5)])], crs=5186)
    t = S.compare(segs, edges, ngii_bldg=bldg).set_index("seg_uid")
    assert t.loc["A", "edge_src"] == "ngii" and "폭불일치" in t.loc["A", "suspect"] and "건물관통" in t.loc["A", "suspect"]
    # B 는 fallback 위 · NGII 40m 밖 — 판 2 는 「멀리」 가 아니라 「측량밖」(D) 이다
    assert t.loc["B", "edge_src"] == "fallback" and t.loc["B", "dist_class"] == "D" and t.loc["B", "suspect"] == "측량밖"
    assert t.loc["A", "dist_class"] == "A" and t.loc["A", "ngii_w"] == 3.0 and not t.loc["A", "same_name"]
    assert "짝없음" in t.loc["C", "suspect"]


def test_tool_reads_nested_vworld_building_layer(tmp_path, monkeypatch):
    """V-WORLD 묶음은 바깥 zip → 도엽 zip → N1A_B0010000.shp 다(2026-09-17 실측 74도엽 중 72). 판정 범위 안만 모은다."""
    import importlib.util
    import io
    import zipfile
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("r1_tool", root / "tools" / "skeleton_compare.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    gpd.GeoDataFrame({"UFID": ["a", "b"]},
                     geometry=[box(0, 0, 10, 10), box(1000, 1000, 1010, 1010)], crs=5186).to_file(shp_dir / "N1A_B0010000.shp")
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        for f in shp_dir.iterdir():
            z.write(f, f.name)
    outer = tmp_path / "vworld_map1k_jngj-donggu_20260307.zip"
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("356161406.zip", inner.getvalue())
        z.writestr("356161407.zip", _empty_zip())
    monkeypatch.setattr(m.ledger, "paths_of", lambda e, r: [outer])
    monkeypatch.setattr(m, "WORK", tmp_path / "work")
    got = m.ngii_buildings(box(-5, -5, 50, 50))
    assert len(got) == 1 and got.iloc[0]["UFID"] == "a"


def _empty_zip() -> bytes:
    import io
    import zipfile
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("N1L_A0020000.txt", "x")
    return b.getvalue()


def test_far_offset_is_flagged_before_width_gap():
    """동계천로형 — 현행 선이 측량 도로에서 3m 넘게 떨어져 있으면 `멀리` 가 붙고 폭 차이보다 앞에 선다."""
    row = {"share": 0.9, "cover": 0.9, "ngii_med": 10.1, "ngii_w": 5.0, "edge_width": 13.9, "width_min_m": 0.97,
           "bldg_ngii_m": 2.7, "edge_bldg_ngii_m": 0.0}
    t = S.suspect(row)
    assert "멀리" in t and "폭불일치" in t and "건물관통" in t
    assert S.priority(t) > S.priority("폭불일치") > S.priority("")
    assert "멀리" not in S.suspect({**row, "ngii_med": 0.4})
    assert "멀리" not in S.suspect({**row, "offset_m": 6.2, "ngii_med": 0.4}), "판 1 의 offset_m 을 아직 본다"


def test_far_threshold_grows_with_ngii_width():
    """넓은 간선은 차로 안에서도 중심선과 몇 m 벌어진다 — 문턱은 max(3m, NGII 도로폭/2)."""
    base = {"cover": 1.0}
    assert "멀리" in S.suspect({**base, "ngii_med": 4.0, "ngii_w": 4.0})
    assert "멀리" not in S.suspect({**base, "ngii_med": 4.0, "ngii_w": 25.5}), "25.5m 간선 차로 안 4m 를 멀리로 쳤다"
    assert "멀리" in S.suspect({**base, "ngii_med": 13.0, "ngii_w": 25.5})
    assert "멀리" not in S.suspect({**base, "ngii_med": 2.9, "ngii_w": None})
    assert S.suspect({**base, "ngii_med": 16.0, "ngii_w": 3.0}) == "측량밖", "15m 넘는 곳을 멀리로 쳤다"


def test_dist_class_edges_are_inclusive_upper():
    assert [S.dist_class(x) for x in (0.0, 1.5, 1.51, 5.0, 5.01, 15.0, 15.01)] == ["A", "A", "B", "B", "C", "C", "D"]
    assert S.dist_class(None) is None


def test_canary_segment_on_fallback_is_classed_c_and_far():
    """판 1 이 못 잡은 형태 — NGII 에서 8m 옆 road_link 위에 선 구간. 하이브리드는 그 road_link 를 fallback 으로
    메우므로 매칭 거리(offset_m)가 0 이다. 판 2 는 NGII 선만 재서 C · 멀리를 단다(§184-4)."""
    keep = box(-10, -60, 110, 60)
    ngii = gdf([LineString([(0, 0), (100, 0)])], 도로폭=[4.0], 도로명=["가길"], 분리대유무=["무"])
    rl = gdf([LineString([(0, 8), (100, 8)])])
    edges = S.build(ngii, rl, keep)
    assert "fallback" in set(edges.src), "전제 — road_link 가 fallback 으로 들어가야 한다"
    segs = gdf([LineString([(20, 8), (80, 8)])], seg_uid=["F"], verdict=["needs_cv"], width_min_m=[2.0], road_name=["가길"])
    r = S.compare(segs, edges).set_index("seg_uid").loc["F"]
    assert r.edge_src == "fallback" and r.offset_m == 0.0, "전제 — 판 1 의 거리는 0 이다"
    assert r.dist_class == "C" and abs(r.ngii_med - 8.0) < 1e-6 and "멀리" in r.suspect and bool(r.same_name)


def test_split_at_node_is_not_unpaired():
    """교차점에서 끊긴 두 엣지로 표가 갈려도 짝없음이 아니다 — 판 1 짝없음 168 중 160 이 이 모양이었다."""
    keep = box(-10, -60, 110, 60)
    ngii = gdf([LineString([(0, 0), (50, 0)]), LineString([(50, 0), (100, 0)]), LineString([(50, 0), (50, 40)])],
               도로폭=[3.0] * 3, 도로명=["가길"] * 3, 분리대유무=["무"] * 3)
    edges = S.build(ngii, gdf([]), keep)
    assert len(edges) == 3, "전제 — T 교차점에서 세 엣지"
    segs = gdf([LineString([(25, 1), (75, 1)])], seg_uid=["T"], verdict=["clear"], width_min_m=[3.0])
    r = S.compare(segs, edges).set_index("seg_uid").loc["T"]
    assert r.share < S.MATCH_SHARE, "전제 — 한 엣지 share 는 60% 미만"
    assert r.cover >= S.MATCH_SHARE and "짝없음" not in r.suspect


def test_ngii_distance_uses_nine_points_including_ends():
    """ngii_distance.csv(2026-09-17 미리보기)와 같은 정의 — 양끝 포함 9점 · 방향 무관 · 폭·이름은 가운데 점 기준."""
    ng = gdf([LineString([(0, 0), (80, 0)]), LineString([(0, 30), (80, 30)])], 도로폭=[4.0, 9.0], 도로명=["가", "나"])
    seg = LineString([(0, 0), (80, 8)])            # 끝으로 갈수록 0 → 8m 로 벌어진다
    d = S.ngii_distance(seg, shapely.union_all(list(ng.geometry)), ng, shapely.STRtree(list(ng.geometry)))
    assert abs(d["ngii_max"] - 8.0) < 1e-9 and abs(d["ngii_med"] - 4.0) < 1e-9
    assert d["ngii_w"] == 4.0 and d["ngii_name"] == "가"


def test_r1_does_not_touch_judgment_fingerprint_files():
    """폭 · 판정 규칙 쪽은 뼈대를 모른다.

    ★ 2026-09-18 (§188 · R3a). `segments.py` 를 목록에서 뺐다 — 거기가 **뼈대를 갈아 끼우는 자리**이고
      R3a 가 스위치로 배선했다. 스위치가 기본 꺼짐인지는 `tests/test_r3.py` 가 따로 든다.
      나머지 셋은 그대로다: 폭 엔진 · 보고 · 상수가 뼈대 모듈을 알면 지문이 뼈대 변경에 딸려 흔들린다.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in ("src/firelane/seg/width.py", "src/firelane/seg/report.py", "src/firelane/seg/params.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "skeleton" not in src, f"{rel} 가 skeleton 을 참조한다 — R3 전에는 배선하지 않는다(§184)"

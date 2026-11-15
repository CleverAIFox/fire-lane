"""`tools/bldg_buried.py` — 경사면에서 건물이 지형에 묻히는 정도를 건물마다 잰다. 합성 지형 · 합성 면으로 문다 (DECISIONS §796-A).

묻는 것: ① 쌍선형 표고가 타일 안에서 정확한가(평면 · 기울기) · 타일 밖은 NaN 이다 ② 발자국 아래 최저 · 최고 · 중심을 맞게 내는가
③ 평평한 땅에서는 묻힘 0 · 기운 땅에서는 최고 − 중심 만큼 묻히는가 ④ 통째 묻힘(묻힘 ≥ 높이)을 센다 ⑤ 후보 비용 표가 칸을 더한다(희소는 전부보다 작다).
밖    실물 타일 · 실물 건물의 값은 안 문다(합성만) · MapLibre 가 실제로 어떻게 그리는지는 안 문다(헤드리스 실측)
"""
from __future__ import annotations

import bldg_buried as B
import numpy as np
from shapely.geometry import box


def _flat_dem(h: float = 100.0, tx: int = 55870, ty: int = 25922) -> B.Dem:
    return B.Dem({(tx, ty): np.full((B.TILE, B.TILE), h)})


def _ramp_dem(slope_per_px: float, tx: int = 55870, ty: int = 25922) -> B.Dem:
    col = np.arange(B.TILE) * slope_per_px                      # 동쪽으로 오른다
    return B.Dem({(tx, ty): np.tile(col, (B.TILE, 1)) + 100.0})


def _tile_center_lonlat(tx: int, ty: int):
    n = B.TILE * 2 ** B.ZOOM
    import math
    x, y = (tx + 0.5) * B.TILE, (ty + 0.5) * B.TILE
    return x / n * 360.0 - 180.0, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))


def test_bilinear_is_exact_on_a_plane_and_nan_outside_the_tile():
    d = _ramp_dem(0.5)
    px = np.array([B.TILE * 55870 + 10.5, B.TILE * 55870 + 11.0])
    py = np.array([B.TILE * 25922 + 40.5] * 2)
    assert np.allclose(d.at(px, py), [100.0 + 10 * 0.5, 100.0 + 10.5 * 0.5])
    assert np.isnan(d.at(np.array([B.TILE * 55870 - 50.0]), np.array([B.TILE * 25922 + 5.0]))[0])


def test_flat_ground_has_no_burial_and_a_slope_buries_the_uphill_side():
    lon, lat = _tile_center_lonlat(55870, 25922)
    foot = box(lon - 0.00004, lat - 0.00003, lon + 0.00004, lat + 0.00003)      # 폭 ≈ 7m · 깊이 ≈ 6.6m
    flat = B.stats(_flat_dem(), foot)
    assert flat["ok"] and flat["hi"] - flat["center"] < 1e-9 and flat["center"] - flat["lo"] < 1e-9
    ramp = B.stats(_ramp_dem(0.5), foot)
    assert ramp["ok"] and ramp["hi"] > ramp["center"] > ramp["lo"]
    assert abs((ramp["hi"] - ramp["center"]) - (ramp["center"] - ramp["lo"])) < 0.3          # 대칭 비탈 — 오르막 · 내리막이 같다
    assert 1.0 < ramp["hi"] - ramp["lo"] < 3.0                                              # 7m 폭 × 0.5/px(약 0.2/m)


def test_a_face_outside_every_tile_is_not_measured():
    far = box(127.5, 36.0, 127.5001, 36.0001)
    assert not B.stats(_flat_dem(), far)["ok"]


def test_the_table_counts_burial_whole_burial_and_float_separately():
    rows = [{"ok": True, "center": 100.0, "lo": 99.0, "hi": 104.0, "h": 3.0},     # 묻힘 4 · 높이 3 → 통째
            {"ok": True, "center": 100.0, "lo": 100.0, "hi": 101.5, "h": 10.0},   # 묻힘 1.5
            {"ok": True, "center": 100.0, "lo": 96.0, "hi": 100.0, "h": 6.0},     # 뜸 4
            {"ok": False, "h": 5.0}]
    t = "\n".join(B.table(rows))
    assert "지형을 잰 것 3동(타일 밖 1)" in t
    assert "1m 초과 2 · 3m 초과 1 · **통째(높이 이하) 1**" in t
    assert "뜸(중심 − 최저)   : 1m 초과 1 · 3m 초과 1" in t     # 뜸 1.0 은 '초과'가 아니다


def test_sparse_candidates_cost_less_than_all_and_set_a_column_only_where_it_is_needed():
    feats = [{"type": "Feature", "properties": {"h": 6.6}, "geometry": {"type": "Point", "coordinates": [0, 0]}} for _ in range(40)]
    rows = [{"ok": True, "center": 100.0, "lo": 99.9, "hi": 100.1, "h": 6.6} for _ in range(39)]
    rows.append({"ok": True, "center": 100.0, "lo": 96.0, "hi": 104.0, "h": 6.6})   # 하나만 크게 기운 건물
    out = B.costs(feats, rows)
    assert len(out) == 6
    a_all = int(out[2].split()[-2].replace(",", "")); a_sparse = int(out[3].split()[-2].replace(",", ""))
    assert out[2].split()[-3] == "40" and out[3].split()[-3] == "1"      # 전부 40동 · 희소 1동
    assert 0 < a_sparse < a_all

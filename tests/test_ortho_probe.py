"""
test_ortho_probe.py — `tools/ortho_probe.py`(정사영상 판독 가능성 조사)의 **순수 함수**.  (DECISIONS §654)

① 세계 좌표 → 도엽 영상 좌표(북서 모서리 · 행이 아래로 증가) ② 구간 방향으로 돌려 오리는 격자(길 방향이 가로 · 법선이 세로) ③ 도엽 가장자리를 건너뛰는 규칙
④ 오차 부호와 분포(읽은 값이 없는 지점은 오차를 안 만든다) ⑤ 판독용 이미지는 **구간 벡터의 가장자리를 안 그린다**(판독이 벡터에 끌리지 않게)

IN    합성 Affine · 합성 선 · 합성 이미지
OUT   통과/실패
밖    실제 정사영상 · 실제 판독. 실측 결과는 DECISIONS §654 가 든다.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from rasterio.transform import Affine
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ortho_probe", ROOT / "tools/ortho_probe.py")
assert _spec and _spec.loader
tool = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = tool
_spec.loader.exec_module(tool)

ORIGIN = Affine(0.25, 0, 1000.0, 0, -0.25, 2000.0)           # 북서 모서리 (1000, 2000)


def test_world_to_pixel_counts_columns_east_and_rows_south_from_the_north_west_corner():
    assert tool.world_to_pixel(1000.0, 2000.0, ORIGIN) == (0.0, 0.0)
    assert tool.world_to_pixel(1010.0, 1990.0, ORIGIN) == (40.0, 40.0), "동쪽 10m = 40열 · 남쪽 10m = 40행(GSD 0.25)"


def test_tangent_is_a_unit_vector_along_the_line_and_survives_the_ends():
    L = LineString([(0, 0), (100, 0), (100, 100)])
    assert tool.tangent_at(L, 20.0) == pytest.approx((1.0, 0.0))
    tx, ty = tool.tangent_at(L, 0.0)
    assert math.hypot(tx, ty) == pytest.approx(1.0) and tx == pytest.approx(1.0)
    assert tool.tangent_at(L, L.length) == pytest.approx((0.0, 1.0)), "끝에서도 접선이 선다(앞뒤 3m 가 잘린다)"


def test_sample_grid_puts_the_road_direction_along_columns_and_the_normal_up():
    X, Y = tool.sample_grid(100.0, 200.0, 1.0, 0.0, half_u=2.0, half_v=1.0, step=0.5)       # 접선 = 동쪽
    assert X.shape == Y.shape == (4, 8)
    assert np.allclose(np.diff(X, axis=1), 0.5) and np.allclose(np.diff(Y, axis=1), 0.0), "열이 늘면 길 방향(동)으로 간다"
    assert Y[0, 0] > Y[-1, 0], "첫 행이 법선 쪽(접선을 반시계로 90° = 북) — 위가 +"
    X2, Y2 = tool.sample_grid(0.0, 0.0, 0.0, 1.0, half_u=1.0, half_v=1.0, step=0.5)         # 접선 = 북이면 법선 = 서
    assert X2[0, 0] < X2[-1, 0], "접선이 북이면 법선은 서쪽이고 위쪽 행의 x 가 더 작다"


def test_which_sheet_skips_points_near_the_image_edge_with_a_margin():
    sizes, origins = {"A": (1000, 1000)}, {"A": ORIGIN}
    assert tool.which_sheet(1100.0, 1900.0, origins, sizes) == "A"
    assert tool.which_sheet(1002.0, 1900.0, origins, sizes) is None, "가장자리 20m 안 — 영상이 잘리면 판독이 거짓이다"
    assert tool.which_sheet(5000.0, 1900.0, origins, sizes) is None


def test_overlay_draws_a_grid_and_a_scale_bar_but_leaves_a_blank_image_recognisable():
    img = Image.new("RGB", (560, 360), (10, 10, 10))
    out = tool.draw_overlay(img)
    a = np.asarray(out)
    assert out.size == (560, 360) and a.max() > 100, "격자 · 눈금 · 막대가 얹혔다"
    assert a[180, 5:60].max() > 100, "세로 0m 선(가운데 행)이 그려진다 — 눈금의 기준이다"


def test_montage_pastes_tiles_in_reading_order_and_sizes_the_sheet():
    tiles = [(f"{i}", Image.new("RGB", (30, 20), (i * 40, 0, 0))) for i in range(5)]
    m = tool.montage(tiles, cols=2)
    assert m.size == (60, 60), "5장 · 2열 → 3행"
    assert m.getpixel((55, 18))[0] == 40 and m.getpixel((5, 38))[0] == 80, "둘째 타일은 오른쪽 위 · 셋째는 둘째 줄 왼쪽(읽는 순서) — 라벨 칸을 피한 점으로 본다"


def test_width_error_is_reading_minus_reference_with_sign():
    assert tool.width_error(7.8, 26.5) == pytest.approx(-18.7), "읽은 값이 좁으면 음수"
    assert tool.width_error(3.0, 2.5) == pytest.approx(0.5)


def test_summarize_errors_reports_the_distribution_and_refuses_to_summarise_fewer_than_three():
    assert tool.summarize_errors([0.1, -0.2]) == {"n": 2}, "둘로는 분포를 말하지 않는다 — 이 조사가 실제로 만난 상황이다"
    s = tool.summarize_errors([-1.0, -0.5, 0.0, 0.5, 1.0])
    assert s["n"] == 5 and s["median"] == 0.0 and s["abs_median"] == 0.5 and s["abs_max"] == 1.0
    assert s["neg_share"] == pytest.approx(0.4) and s["within_050"] == pytest.approx(0.6) and s["within_100"] == 1.0

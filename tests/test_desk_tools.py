#!/usr/bin/env python3
"""
test_desk_tools.py — `desk_check` · `wmax_audit` 의 좌표 · 분류 · 고르기.  (PLAN §1 #12)

── 왜 생겼나 ───────────────────────────────────────────────────
PLAN §1 #12 가 한 줄로 적고 있었다 — **「좌표 변환이 틀려도 아무도 모른다」.**
`desk_check` 는 경위도를 z19 타일 픽셀로 바꿔 정사영상을 이어 붙이고, 그 위에
구간을 그려 사람이 눈으로 폭을 대조하는 도구다. 변환이 1타일 어긋나면 **엉뚱한
골목 사진**을 보고 「우리 폭이 맞다」고 판정하게 된다. 그림은 그럴듯하게 나온다.

2026-09-20 에 실제로 `Z` 가 18 이어서 원본 해상도의 절반을 버리고 있었다(W9-2).
그 상수 하나가 틀린 것을 **사람이 눈으로** 찾았다.

── 무엇을 보는가 ───────────────────────────────────────────────
    ① 웹 메르카토르 변환이 알려진 값과 맞는가 (적도 · 본초자오선 · 동명동)
    ② z 가 하나 오르면 픽셀이 정확히 두 배인가
    ③ 미터/픽셀이 위도에 따라 줄어드는가 · z19 가 원본 GSD(0.25m) 근방인가
    ④ `pick` 세 갈래가 **서로 다른 것**을 고르고, 모르는 갈래는 죽는가
    ⑤ `wmax_audit.label` 이 경계값을 어느 칸에 넣는가 (구간 끝 포함 규칙)
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_{name}", ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def desk():
    return _load("desk_check")


@pytest.fixture(scope="module")
def wmax():
    return _load("wmax_audit")


# ── ① · ② 좌표 변환 ─────────────────────────────────────────
def test_origin_is_the_top_left_of_the_world(desk):
    """웹 메르카토르 원점 — (-180, 85.0511) 이 픽셀 (0, 0) 이다."""
    x, y = desk.deg2px(-180.0, 85.05112878, 0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def test_null_island_is_the_centre(desk):
    """적도 · 본초자오선은 세계 지도 한가운데다."""
    for z in (0, 10, 19):
        n = 2.0 ** z * desk.TILE
        x, y = desk.deg2px(0.0, 0.0, z)
        assert x == pytest.approx(n / 2)
        assert y == pytest.approx(n / 2)


def test_zoom_doubles_the_pixels(desk):
    """z 가 하나 오르면 같은 점의 픽셀 좌표가 정확히 두 배다."""
    lo, la = 126.9187, 35.1536          # 동명동
    a = desk.deg2px(lo, la, 17)
    b = desk.deg2px(lo, la, 18)
    assert b[0] == pytest.approx(a[0] * 2)
    assert b[1] == pytest.approx(a[1] * 2)


def test_dongmyeong_lands_in_the_northern_east_quadrant(desk):
    """동명동(동경 126.9 · 북위 35.2)은 지도의 오른쪽 위 사분면이다."""
    z = 19
    n = 2.0 ** z * desk.TILE
    x, y = desk.deg2px(126.9187, 35.1536, z)
    assert x > n / 2, "동경인데 왼쪽에 놓였다"
    assert y < n / 2, "북위인데 아래에 놓였다"


# ── ③ 미터/픽셀 ────────────────────────────────────────────
def test_metres_per_pixel_shrinks_with_latitude(desk):
    """같은 z 에서 고위도일수록 1픽셀이 덮는 실거리가 짧다."""
    assert desk.mpp(60.0, 19) < desk.mpp(35.0, 19) < desk.mpp(0.0, 19)


def test_z19_matches_the_source_gsd(desk):
    """z19 가 원본 GSD 0.25m/px 근방이다 — **W9-2 가 고친 그 상수다.**

    z18 이면 0.49m/px 라 원본 해상도의 절반을 버린다. 그 상태로도 그림은 나온다.
    """
    assert desk.Z == 19, "Z 가 19 가 아니다 — 원본 해상도를 버린다(W9-2 재발)"
    assert desk.mpp(35.1536, desk.Z) == pytest.approx(0.25, abs=0.02)


def test_mpp_halves_per_zoom(desk):
    assert desk.mpp(35.0, 18) == pytest.approx(desk.mpp(35.0, 19) * 2)


# ── ④ 고르기 ───────────────────────────────────────────────
def _f(**p):
    base = {"width_disagree_m": 0, "width_max_m": 1.0, "width_min_m": 9.0,
            "road_bt_m": 9.0, "verdict": "clear", "cctv_dist_m": 9e9,
            "length_m": 10.0, "route_usage": 0}
    base.update(p)
    return {"properties": base, "geometry": {"coordinates": [[0, 0], [1, 1]]}}


def test_pick_disagree_takes_the_widest_gap_first(desk):
    P = [_f(width_disagree_m=6), _f(width_disagree_m=9), _f(width_disagree_m=4)]
    got = desk.pick(P, "disagree")
    assert [f["properties"]["width_disagree_m"] for f in got] == [9, 6], \
        "5m 이하를 넣었거나 정렬이 틀렸다"


def test_pick_wmax_skips_what_road_bt_already_saved(desk):
    """`road_bt_m` 이 3m 미만이면 ROAD_BT 로 이미 건진 것이라 대상이 아니다."""
    target = _f(width_max_m=None, width_min_m=1.0, road_bt_m=9.0, length_m=50)
    saved = _f(width_max_m=None, width_min_m=1.0, road_bt_m=2.0, length_m=90)
    got = desk.pick([target, saved], "wmax")
    assert got == [target], "ROAD_BT 가 건진 것을 다시 고른다"


def test_pick_shoot_needs_all_three_conditions(desk):
    ok = _f(verdict="needs_cv", cctv_dist_m=20, length_m=30, route_usage=5)
    far = _f(verdict="needs_cv", cctv_dist_m=40, length_m=30)
    short = _f(verdict="needs_cv", cctv_dist_m=20, length_m=10)
    other = _f(verdict="clear", cctv_dist_m=20, length_m=30)
    assert desk.pick([ok, far, short, other], "shoot") == [ok]


def test_pick_caps_at_six(desk):
    assert len(desk.pick([_f(width_disagree_m=6 + i) for i in range(20)], "disagree")) == 6


def test_pick_dies_on_an_unknown_track(desk):
    """모르는 갈래를 **조용히 빈 목록**으로 돌려주지 않는다."""
    with pytest.raises(SystemExit):
        desk.pick([], "없는갈래")


# ── ⑤ 폭 구간 분류 ─────────────────────────────────────────
def test_label_puts_the_boundary_in_the_upper_bin(wmax):
    """경계는 **위 칸**이다 — `lo <= v < hi`. 3.0 은 `3–5m` 다."""
    assert wmax.label(2.99) == "0–3m"
    assert wmax.label(3.0) == "3–5m"
    assert wmax.label(4.99) == "3–5m"
    assert wmax.label(5.0) == "5–7m"
    assert wmax.label(7.0) == "7–10m"


def test_label_has_an_open_top_bin(wmax):
    assert wmax.label(10.0) == "10m+"
    assert wmax.label(1e8) == "10m+"


def test_label_says_it_does_not_know(wmax):
    """음수는 칸이 없다 — 0 칸에 밀어 넣지 않는다."""
    assert wmax.label(-1.0) == "?"


def test_bins_tile_the_line_without_gaps(wmax):
    """칸이 끊기거나 겹치지 않는가 — 경계마다 정확히 한 칸이 받는다."""
    for lo, hi in wmax.BINS:
        assert wmax.label(lo) != "?", f"{lo} 를 받는 칸이 없다"
        if hi < 1e9:
            assert wmax.label(hi - 1e-9) == wmax.label(lo), f"{lo}~{hi} 가 두 칸에 걸린다"
    los = [lo for lo, _ in wmax.BINS]
    his = [hi for _, hi in wmax.BINS]
    assert los[1:] == his[:-1], "칸 사이에 틈이 있다"


def test_stitch_counts_missing_tiles(desk, tmp_path, monkeypatch):
    """타일이 없으면 **몇 장 없는지 센다** — 검은 캔버스를 성공으로 읽지 않는다."""
    monkeypatch.setattr(desk, "ORTHO", tmp_path / "ortho")
    canvas, px, py, miss = desk.stitch(126.9187, 35.1536, 126.9190, 35.1539)
    assert miss > 0, "타일이 하나도 없는데 결손 0 이다"
    assert canvas.size[0] % desk.TILE == 0 and canvas.size[1] % desk.TILE == 0
    assert math.isfinite(px) and math.isfinite(py)

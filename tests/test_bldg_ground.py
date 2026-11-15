"""`src/firelane/bldg_ground.py` — 경사면 건물에 음수 `base`(`zb`)와 지붕까지의 높이를 싣는다. 합성 지형 · 합성 면 · 발행물로 문다 (PLAN #239 · DECISIONS §797-A).

묻는 것: ① 평지는 아무것도 안 단다(희소 = 0.5m 이상만) ② 비탈은 `zb` = 최저 − 중심(음수) · `h` = 높이 + 묻힘 ③ 타일 밖은 건드리지 않는다
         ④ 파일에서 빈 `zb` · 빈 `BULD_NM` 을 뺀다 ⑤ 발행물의 `zb` 는 0 이하이고 달린 건물은 전체의 한 자릿수 %이다(희소)
밖    MapLibre 가 음수 `base` 를 실제로 어떻게 그리는지는 안 본다(헤드리스 실측 — DECISIONS §796-A) · 실제 지형 타일의 값은 안 본다(합성 타일) · 판정은 안 읽는다
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import box

from firelane import bldg_ground as G

ROOT = Path(__file__).resolve().parent.parent
TX, TY = 55900, 25500


def _dem(slope: float) -> G.Dem:
    """동쪽으로 갈수록 `slope`(m/px) 높아지는 타일 하나."""
    col = np.arange(G.TILE) * slope + 100.0
    return G.Dem({(TX, TY): np.tile(col, (G.TILE, 1))})


def _foot(px_w: float = 20.0):
    """타일 가운데의 발자국(경위도) — 가로 `px_w` 픽셀."""
    n = G.TILE * 2 ** G.ZOOM

    def ll(px, py):
        import math
        lon = px / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * py / n))))
        return lon, lat
    x0, y0 = TX * G.TILE + 118, TY * G.TILE + 118
    (a, b), (c, d) = ll(x0, y0), ll(x0 + px_w, y0 + 20)
    return box(min(a, c), min(b, d), max(a, c), max(b, d))


def test_flat_ground_gets_nothing():
    assert G.ground(_dem(0.0), _foot(), 6.6) is None


def test_slope_gets_negative_base_and_a_taller_roof():
    r = G.ground(_dem(0.1), _foot(), 6.6)    # 20px 폭 · 픽셀당 0.1m → 오르막 쪽이 중심보다 약 1m 높다
    assert r is not None
    zb, h = r
    assert -1.2 < zb < -0.8, zb               # 내리막 쪽 아래를 메운다 — 최저 − 중심
    assert 7.4 < h < 7.8, h                   # 지붕 = 최고 지반 + 6.6


def test_below_the_threshold_is_left_alone():
    assert G.ground(_dem(0.02), _foot(), 6.6) is None   # 비탈 0.2m


def test_outside_the_tiles_is_left_alone():
    far = box(127.0, 35.0, 127.0001, 35.0001)
    assert G.ground(_dem(0.1), far, 6.6) is None


def test_strip_null_cells_only_drops_empty_cells(tmp_path):
    p = tmp_path / "b.geojson"
    p.write_text('{ "properties": { "BUL_MAN_NO": 1, "BULD_NM": null, "flo": 2.0, "h": 6.6, "zb": null }, "x": { "BULD_NM": "가", "h": 3.0, "zb": -1.2 } }', encoding="utf-8")
    G.strip_null_cells(p)
    s = p.read_text(encoding="utf-8")
    assert "null" not in s and '"zb": -1.2' in s and '"BULD_NM": "가"' in s   # 값이 있는 칸은 남는다


def test_published_buildings_carry_zb_only_where_it_matters():
    p = ROOT / "web" / "data" / "buildings.geojson"
    feats = json.loads(p.read_text(encoding="utf-8"))["features"]
    zbs = [f["properties"]["zb"] for f in feats if "zb" in f["properties"]]
    assert 500 < len(zbs) < 0.1 * len(feats), f"{len(zbs)}동 — 희소가 아니거나 안 실렸다"
    assert all(z <= 0 for z in zbs), "zb 는 최저 − 중심이라 0 이하다"
    assert all(f["properties"]["zb"] is not None for f in feats if "zb" in f["properties"]), "빈 zb 가 파일에 남았다"

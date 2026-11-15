"""`tools/bldg_overlap.py` — 얹은 면이 기존 면 · 다른 얹은 면과 겹치는 것을 센다. 합성 도형으로 문다 (DECISIONS §792-H).

밖    발행물 실물의 겹침 수는 안 문다(합성 도형만) · 어느 면이 정말 어긋났는가는 안 가린다
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import bldg_overlap as O  # noqa: E402 — `sys.path` 를 먼저 깔아야 import 가 된다

ID0 = 100_000


def drop_gap(b):
    return b[b["BUL_MAN_NO"] < ID0]


def _b():
    geoms = [box(0, 0, 10, 10),                  # 기존
             box(20, 0, 30, 10),                 # 얹은 1 — 기존과 안 겹침
             box(0, 0, 10, 5),                   # 얹은 2 — 기존 위(절반)
             box(40, 0, 50, 10), box(40, 0, 50, 10)]   # 얹은 3 · 4 — 서로 똑같다(원천 중복)
    ids = [1, ID0, ID0 + 1, ID0 + 2, ID0 + 3]
    return gpd.GeoDataFrame({"BUL_MAN_NO": ids}, geometry=geoms, crs=5186)


def test_split_by_number():
    base, added = O.split(_b(), drop_gap)
    assert len(base) == 1 and len(added) == 4


def test_overlap_ratios_are_per_face_and_by_source():
    base, added = O.split(_b(), drop_gap)
    r = O.overlaps(base, added)
    assert r[0]["ratio"] == 0.0 and r[0]["n_base"] == 0
    assert abs(r[1]["ratio_base"] - 1.0) < 1e-9 and r[1]["n_base"] == 1       # 기존 면 안에 통째로
    assert r[2]["ratio_added"] == 1.0 and r[3]["ratio_added"] == 1.0 and r[2]["n_added"] == 1   # 서로 겹친다
    assert r[2]["ratio_base"] == 0.0


def test_table_counts_by_threshold_and_top_orders_by_ratio():
    base, added = O.split(_b(), drop_gap)
    rows = O.overlaps(base, added)
    t = O.table(rows)
    assert t[0].startswith("얹은 면 4면")
    assert any(" 3 " in ln for ln in t[2:3]), t           # >0.1% 에 세 면(얹은 2 · 3 · 4)
    for r in rows:
        r["lon"] = r["lat"] = 0.0
    lines = O.top(rows, 2)
    assert len(lines) == 2 + 2 and lines[2].split()[1] == "100.0%"

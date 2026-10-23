#!/usr/bin/env python3
"""
test_occ_pressure.py — 점유압력 β 는 **순서만 만든다.** 판정선을 못 넘고, null 과 0 을 섞지 않는다.

── 왜 이 시험인가 ──────────────────────────────────────────────
① **판정선.** `src/firelane/seg/classify.py` 가 `occ_pressure` 또는 `occ_pressure_rank` 를 읽으면 이 시험이 실패한다.
   사유 — 점유율 p 의 실측 중앙값이 0.07~0.14 다. 물리 환산(유효폭 = wmin − occ)을 시도했으나 분기가 걸리지 않아 규칙이
   wmin ≥ 5.0 으로 축소됐고, 그래서 기존 clear 103 / blocked 38 이 100% 재현됐다. **그 100% 는 대조가 통과한 것이 아니라
   대조가 아무것도 재지 않은 것이다.** 수요에 거주 세대만 잡히고 상업 유입이 잡히지 않는다(단속 141,556건이 그 유입의
   증거). 그래서 이 칸은 **상대 순위로만** 산다.
② **null 대 0.** `in_emd == False` 구간은 `occ_pressure` 가 **null** 이다 — 건축물대장이 동명동뿐이라 잴 수 없다.
   0 으로 적으면 「압력 없음 = 안전」으로 읽힌다. 판정 둘레에서 가장 위험한 혼동이다.
③ **길이 기준 · `cap_style=2`.** 둥근 끝이면 짧은 구간의 값이 부풀려진다(길이 기준에서만 일이 된다).
④ **밴드 안 순위.** 전체 순위는 폭 순위를 되풀이한다.

IN    firelane.occ · src/firelane/seg/classify.py
OUT   없음 (검사)
PARAM 없음
밖    **β 가 맞는 값인가는 안 본다** — 계산이 정의대로인가만 본다. 상업 유입·동명동 밖은 못 잰다.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from firelane.occ import occ_columns

ROOT = Path(__file__).resolve().parent.parent


def _seg(rows):
    """rows: (seg_uid, x0, x1, in_emd, wmin). EPSG:5179 한 줄짜리 구간. length_m 은 선 길이."""
    g = gpd.GeoDataFrame(
        {"seg_uid": [r[0] for r in rows], "in_emd": [r[3] for r in rows],
         "width_min_m": [r[4] for r in rows], "length_m": [float(abs(r[2] - r[1])) for r in rows]},
        geometry=[LineString([(r[1], 0.0), (r[2], 0.0)]) for r in rows], crs=5179)
    return g


def test_classify_never_reads_the_pressure_columns():
    src = (ROOT / "src" / "firelane" / "seg" / "classify.py").read_text(encoding="utf-8")
    for name in ("occ_pressure", "occ_pressure_rank"):
        assert name not in src, f"classify.py 가 {name} 를 읽는다 — 이 칸은 판정선을 못 넘는다(머리말 사유)"


def test_outside_the_district_is_null_not_zero():
    seg = _seg([("A", 0, 100, True, 2.0), ("B", 0, 100, False, 2.0)])
    demand = pd.DataFrame({"x": [50.0], "y": [0.0], "units": [10]})
    occ, rank = occ_columns(seg, demand)
    assert occ.iloc[1] is None and rank.iloc[1] is None, "동명동 밖이 null 이 아니다 — 0 이면 「압력 없음 = 안전」으로 읽힌다"
    assert occ.iloc[0] == 10.0, f"길이 기준(10 단위 / 100m × 100)이어야 한다 — {occ.iloc[0]}"


def test_zero_inside_is_zero_and_has_no_rank():
    seg = _seg([("A", 0, 100, True, 2.0)])
    demand = pd.DataFrame({"x": [5000.0], "y": [5000.0], "units": [10]})       # 멀다
    occ, rank = occ_columns(seg, demand)
    assert occ.iloc[0] == 0.0 and rank.iloc[0] is None


def test_missing_demand_is_all_null():
    seg = _seg([("A", 0, 100, True, 2.0)])
    occ, rank = occ_columns(seg, None)
    assert occ.iloc[0] is None and rank.iloc[0] is None


def test_flat_cap_does_not_swallow_the_far_point_of_a_short_segment():
    """길이 5m 구간 + 끝에서 10m 떨어진 점: 둥근 끝이면 먹고 평평한 끝이면 안 먹는다. 이 시험이 평평한 끝을 지킨다."""
    seg = _seg([("A", 0, 5, True, 2.0)])
    demand = pd.DataFrame({"x": [15.0], "y": [0.0], "units": [10]})
    occ, _ = occ_columns(seg, demand)
    assert occ.iloc[0] == 0.0, f"끝에서 10m 밖 점을 셌다 — 둥근 끝이다: {occ.iloc[0]}"


def test_rank_is_inside_the_width_band_and_ties_go_by_seg_uid():
    seg = _seg([("b", 0, 100, True, 2.0), ("a", 200, 300, True, 2.5),      # 같은 밴드 (0,3]
                ("c", 400, 500, True, 5.5)])                                  # 다른 밴드 (5,6]
    demand = pd.DataFrame({"x": [50.0, 250.0, 450.0, 450.0], "y": [0.0] * 4, "units": [4, 4, 1, 1]})
    occ, rank = occ_columns(seg, demand)
    assert list(occ) == [4.0, 4.0, 2.0]
    assert list(rank) == [2, 1, 1], f"동률은 seg_uid 사전순(a 가 먼저), 밴드가 다르면 따로 센다 — {list(rank)}"

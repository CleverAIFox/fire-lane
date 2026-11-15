"""`tools/xsec_leak.py` — 교차부 제외가 폴리곤 밖에 남기는 오염을 재는 조사 도구. 합성 도형으로 문다 (DECISIONS §791).

묻는 것: ① 표본점이 구간선 위 `s_m` 지점으로 되살아나는가 ② 발행 최소폭과 안 맞는 구간은 빠지는가
③ 경계 밖 거리 구간 수가 합과 맞는가 ④ 정적 재거름이 버퍼를 키울수록 단조로 늘고 표본 0 이 잡히는가.
밖    조사 도구의 **판정 수는 안 문다**(후보 판정은 격리 사본에서 따로 돌린다) · 실물 산출물의 값은 안 문다(합성 도형만)
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import xsec_leak as X  # noqa: E402


def _fixture():
    # 구간 하나: x 축 0~20m. 폴리곤은 x∈[0,4] 의 상자(구간 시작을 덮는다)
    seg = gpd.GeoDataFrame({"seg_uid": ["U1"], "width_min_m": [2.0], "road_name": ["가길"],
                            "geometry": [LineString([(0, 0), (20, 0)])]}, crs=5186).set_index("seg_uid")
    smp = pd.DataFrame({"seg_uid": "U1", "seg_id": "S1", "s_m": [1.0, 3.0, 5.0, 7.0, 9.0],
                        "w_m": [9.0, 8.0, 2.0, 6.0, 7.0]})
    poly = box(0, -3, 4, 3)
    return seg, smp, [poly], poly


def test_min_point_is_the_sample_on_the_line():
    seg, smp, polys, union = _fixture()
    M = X.min_points(seg, smp, union)
    assert len(M) == 1
    r = M.iloc[0]
    assert (r.x, r.y, r.s_m) == (5.0, 0.0, 5.0)
    assert abs(r.out_m - 1.0) < 1e-9          # 폴리곤 경계(x=4)에서 1m 밖


def test_segment_whose_min_disagrees_with_published_is_skipped():
    seg, smp, polys, union = _fixture()
    seg["width_min_m"] = 2.5                   # 중심선 가름이 다시 잰 구간 — 표본 최소(2.0)와 안 맞는다
    assert X.min_points(seg, smp, union).empty


def test_distance_bins_sum_to_the_count():
    M = pd.DataFrame({"out_m": [0.2, 0.7, 1.5, 2.5, 4.0, 7.0, 30.0]})
    lines = X.part3(M)
    counts = [int(x.split()[-1]) for x in lines[1:-1]]
    assert sum(counts) == len(M)
    assert "오염 의심(밖 0~5m) 5구간" in lines[-1]


def test_grid_counts_changed_min_and_zero_sample_segments():
    seg, smp, polys, union = _fixture()
    rows = X.grid(None, smp, seg, polys, [0, 1, 6])
    parse = [tuple(int(v) for v in r.split()[1:]) for r in rows[2:]]
    assert parse[0] == (0, 0)      # b=0: 폴리곤 안 표본(x≤4)만 빠진다 — 최솟값(x=5)은 남아 폭이 안 바뀐다
    assert parse[1] == (1, 0)      # b=1: x=5 가 경계 1m 이내라 빠진다 → 최솟값이 2.0 에서 6.0 으로 바뀐다
    assert parse[2] == (0, 1)      # b=6: 남는 표본이 없다 — 엔진이면 폭을 못 내는 구간

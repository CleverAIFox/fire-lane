"""`tools/park_forecast.py` — 단속이력 가중치 예보. 합성 그래프로 문다 (DECISIONS §794).

묻는 것: ① 가중치 0 이면 경로가 안 바뀌고 크면 단속이 많은 직선을 피해 도는가 ② 늘어난 길이를 맞게 재는가
③ 영상판정 불가 구간 중 단속 도로 가중치를 받는 수를 센다 · 단속 수가 없는 것은 안 센다.
밖    실물 그래프의 값은 안 문다(합성 도형만) · 실제 `edge_cost` 와 같은지는 안 문다
"""
from __future__ import annotations

import park_forecast as F


def _tri(park_direct):
    return [{"a": 0, "b": 1, "length_m": 100, "park": park_direct},
            {"a": 0, "b": 2, "length_m": 60, "park": 0},
            {"a": 2, "b": 1, "length_m": 70, "park": 0}]


def test_zero_weight_never_changes_the_route_and_a_big_one_goes_around():
    r = F.forecast(_tri(3000), [0], (0.0, 1.0), n_dest=5)
    assert r[0]["changed"] == 0
    assert r[1]["changed"] == 1 and abs(r[1]["extra_med"] - 30.0) < 1e-9


def test_no_enforcement_means_no_detour_at_any_weight():
    r = F.forecast(_tri(0), [0], (1.0, 10.0), n_dest=5)
    assert not r[0]["changed"] and not r[1]["changed"]


def test_grounding_counts_unknown_segments_with_a_positive_road_count():
    props = [{"seg_uid": "A", "verdict": "unknown", "unknown_reason": "no_cctv_band"},
             {"seg_uid": "B", "verdict": "unknown", "unknown_reason": "needs_survey"},
             {"seg_uid": "C", "verdict": "clear", "unknown_reason": None}]
    by = {"A": {"park": 500}, "B": {"park": 0}, "C": {"park": 900}}
    g = F.grounding(by, props)
    assert g["unknown"] == 2 and g["unknown_no_cctv"] == 1
    assert g["unknown_park_pos"] == 1 and g["unknown_park_strong"] == 1 and g["no_cctv_park_pos"] == 1


def test_the_selftest_passes():
    assert F.selftest() == 0

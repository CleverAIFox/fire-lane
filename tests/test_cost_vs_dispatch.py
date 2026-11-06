"""
test_cost_vs_dispatch.py — `tools/cost_vs_dispatch.py`(cost 대 119 실측 대조)의 **순수 함수**.  (DECISIONS §650)

① 속도표를 `speed.ts` 에서 **읽는다**(사본 없음) · 실제 파일과 맞는다 ② 접기 — 한 사건의 여러 신고접수는 하나로, 같은 곳의 다른 날 출동은 따로
③ 스냅 분류가 `seg/params.py` 의 두 상수를 쓴다 ④ 계산 소요가 `travelSeconds` 식(Σ 길이/속도 × cost/길이)이다 ⑤ 통계 요약.

IN    합성 표 · `web/navi/src/domain/speed.ts`
OUT   통과/실패
밖    실제 레이크 · 산출물. 실물 결과는 DECISIONS §650 이 든다.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from firelane.seg.params import SNAP_MAX, SNAP_TRUST

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("cost_vs_dispatch", ROOT / "tools/cost_vs_dispatch.py")
assert _spec and _spec.loader
tool = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = tool
_spec.loader.exec_module(tool)

TABLE = [(12.0, 50.0), (7.0, 40.0), (4.0, 30.0), (0.0, 20.0)]


# ── ① 속도표 ──
def test_the_speed_table_is_read_from_the_ts_source_and_matches_it():
    t = tool.parse_speed_table((ROOT / "web/navi/src/domain/speed.ts").read_text(encoding="utf-8"))
    assert t == sorted(t, reverse=True) and t[-1][0] == 0, "큰 문턱부터 · 맨 아래 칸이 문턱 0"
    assert all(kmh > 0 for _, kmh in t)


@pytest.mark.parametrize("bad", ["const X = 1;", "export const SPEED_TABLE: [number, number][] = [[0, 20], [12, 50]];"])
def test_a_missing_or_unsorted_table_stops(bad):
    with pytest.raises(ValueError):
        tool.parse_speed_table(bad)


def test_speed_falls_back_from_width_to_road_width_to_the_bottom_row():
    def mps(k):  # km/h → m/s
        return k / 3.6

    assert tool.speed_mps(12.0, None, TABLE) == pytest.approx(mps(50)), "문턱은 닫힌 구간"
    assert tool.speed_mps(6.9, 99, TABLE) == pytest.approx(mps(30)), "폭이 있으면 도로대장 폭은 안 본다"
    assert tool.speed_mps(None, 8.0, TABLE) == pytest.approx(mps(40)) and tool.speed_mps(float("nan"), 8.0, TABLE) == pytest.approx(mps(40))
    assert tool.speed_mps(None, None, TABLE) == pytest.approx(mps(20)), "둘 다 없으면 0 으로 보고 맨 아래 칸"


# ── 응답 시간 ──
def test_response_seconds_needs_both_stamps_and_a_forward_interval():
    assert tool.response_seconds("20240101120000", "20240101120500") == 300
    assert tool.response_seconds("20240101120000", "              ") is None, "2024 이후의 공백 문자열"
    assert tool.response_seconds("", "20240101120500") is None
    assert tool.response_seconds("20240101120500", "20240101120000") is None, "도착이 지령보다 앞서면 못 쓴다"


# ── ② 접기 ──
def _rows(*r):
    return pd.DataFrame(r, columns=["cntr", "lon", "lat", "dspt", "arrv", "resp"])


def test_fold_merges_calls_of_one_dispatch_but_not_repeat_visits_and_drops_missing_coords():
    A = ("지산", 126.9, 35.1)
    f = tool.fold(_rows(
        (*A, "20240101120000", "20240101120400", 240),     # 같은 출동에 신고 둘
        (*A, "20240101120000", "20240101120400", 240),
        (*A, "20240301090000", "20240301090800", 480),     # 같은 곳 다른 날 — 다른 관측
        ("지산", 126.95, 35.12, "20240201100000", "              ", None),   # 도착 시각 없음
        ("지산", float("nan"), float("nan"), "20240201100000", "20240201100300", 180),   # 좌표 없음
        ("지산", 0.0, 0.0, "20240201100000", "20240201100300", 180)))                    # 0 센티널
    assert (f["rows"], f["coord_rows"], f["events"], f["locations"]) == (6, 4, 3, 2)
    t = f["table"].set_index("lat")
    assert t.loc[35.1, "n_events"] == 2 and t.loc[35.1, "n_rows"] == 3 and t.loc[35.1, "resp_s"] == pytest.approx(360.0), "위치 안에서 중앙값(240 · 480)"
    assert math.isnan(t.loc[35.12, "resp_s"]) and t.loc[35.12, "n_resp"] == 0


def test_the_same_place_under_two_centers_is_two_locations():
    f = tool.fold(_rows(("지산", 126.9, 35.1, "a", "b", 100), ("대인", 126.9, 35.1, "a", "b", 100)))
    assert f["locations"] == 2 and f["places"] == 1


# ── ③ 스냅 ──
def test_snap_classes_use_the_two_width_constants_with_closed_bounds():
    assert tool.classify_snap(0.0) == "trust" and tool.classify_snap(SNAP_TRUST) == "trust"
    assert tool.classify_snap(SNAP_TRUST + 1e-9) == "snap" and tool.classify_snap(SNAP_MAX) == "snap"
    assert tool.classify_snap(SNAP_MAX + 1e-9) == "fail"


# ── ④ 계산 소요 ──
def _line_graph():
    """a -100m(50km/h · cost×1)- b -100m(20km/h · cost×2.5)- c"""
    P = nx.Graph()
    P.add_edge("a", "b", cost=100.0, length=100.0, sec=100 / (50 / 3.6), seg_id="s1")
    P.add_edge("b", "c", cost=250.0, length=100.0, sec=100 / (20 / 3.6), seg_id="s2")
    meta = {"s1": {"blocked": False, "a": "a", "b": "b", "cost": 100.0, "length": 100.0, "sec": 100 / (50 / 3.6)},
            "s2": {"blocked": False, "a": "b", "b": "c", "cost": 250.0, "length": 100.0, "sec": 100 / (20 / 3.6)},
            "sx": {"blocked": True, "a": "c", "b": "c", "cost": 1e7, "length": 10.0, "sec": 1.0}}
    dist, paths = nx.single_source_dijkstra(P, "a", weight="cost")
    return P, meta, dist, paths


def test_predict_is_the_travel_seconds_formula_sum_of_length_over_speed_times_cost_per_length():
    P, meta, dist, paths = _line_graph()
    sec, ln, cost = tool.predict(P, "a", meta, "s2", 0.5, paths, dist)      # b 에서 절반 들어간 점
    raw = 100 / (50 / 3.6) + 0.5 * 100 / (20 / 3.6)
    assert (ln, cost) == (150.0, 100.0 + 0.5 * 250.0)
    assert sec == pytest.approx(raw * (cost / ln)), "배수(cost/길이)가 그대로 시간에 곱해진다"


def test_predict_picks_the_cheaper_end_and_refuses_blocked_or_unknown_segments():
    P, meta, dist, paths = _line_graph()
    near_c = tool.predict(P, "a", meta, "s2", 0.9, paths, dist)             # c 쪽에서 들어가는 쪽이 더 싸지 않다 — b 쪽(a 방향)이 싸다
    assert near_c[2] == pytest.approx(100.0 + 0.9 * 250.0)
    assert tool.predict(P, "a", meta, "sx", 0.5, paths, dist) is None, "막힌 구간 위 — 못 간다"
    assert tool.predict(P, "a", meta, "nope", 0.5, paths, dist) is None, "그래프에 없는 구간"


def test_predict_to_end_stops_at_the_reachable_mouth_of_a_blocked_segment():
    P, meta, dist, paths = _line_graph()
    meta["sb"] = {"blocked": True, "a": "c", "b": "z", "cost": 1e7, "length": 30.0, "sec": 5.0}      # 끝 c 는 닿고 z 는 안 닿는다
    sec, ln, cost = tool.predict_to_end(P, meta, "sb", paths, dist)
    raw = 100 / (50 / 3.6) + 100 / (20 / 3.6)
    assert (ln, cost) == (200.0, 350.0) and sec == pytest.approx(raw * (350.0 / 200.0)), "구간 안쪽은 더하지 않는다"
    meta["far"] = {"blocked": True, "a": "y", "b": "z", "cost": 1e7, "length": 10.0, "sec": 1.0}
    assert tool.predict_to_end(P, meta, "far", paths, dist) is None, "두 끝 다 안 닿는다"
    assert tool.predict_to_end(P, meta, "none", paths, dist) is None
    meta["at_src"] = {"blocked": True, "a": "a", "b": "z", "cost": 1e7, "length": 10.0, "sec": 1.0}
    assert tool.predict_to_end(P, meta, "at_src", paths, dist) is None, "센터 노드 자신은 거리 0 이라 쓰지 않는다"


# ── ⑤ 통계 ──
def test_spearman_and_ols_on_known_shapes():
    assert tool.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert tool.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert math.isnan(tool.spearman([1, 2], [1, 2])), "둘뿐이면 정하지 않는다"
    a, b = tool.ols([0, 1, 2, 3], [5, 7, 9, 11])
    assert (round(a, 6), round(b, 6)) == (5.0, 2.0), "절편 = 고정분 · 기울기"


def test_summarize_reports_a_constant_offset_as_bias_without_correlation_loss():
    pred = np.arange(100.0, 200.0)
    s = tool.summarize(pred, pred + 200.0, boot=200, seed=1)
    assert s["n"] == 100 and s["bias_med"] == pytest.approx(200.0) and s["rho"] == pytest.approx(1.0)
    assert s["fit_fixed_s"] == pytest.approx(200.0) and s["fit_slope"] == pytest.approx(1.0) and s["actual_gt_pred"] == 1.0
    assert s["bias_ci"][0] <= 200.0 <= s["bias_ci"][1]
    assert tool.summarize([1.0, 2.0], [1.0, 2.0]) == {"n": 2}, "셋 미만은 요약하지 않는다"

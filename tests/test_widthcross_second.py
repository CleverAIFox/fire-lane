#!/usr/bin/env python3
"""
test_widthcross_second.py — 폭 교차대조 **2판**(Zm17 · DECISIONS §562)의 판별식. 데이터 없이 문다.

── 이 시험이 무는 것 ───────────────────────────────────
① **문턱은 분포에서 나온다** — 울타리(`fences`)가 사분위에서 계산되고 상수로 박히지 않는다.
② **모순 분류**(`triage`)가 이름 · 표본 수로만 가른다 — 새로 재지 않는다.
③ **매칭 진단**(`widthmatch`)의 사유 분류와 채택 조건(p · 최소 겹침)이 양방향으로 문다.

IN    tools/widthcross.py · tools/widthmatch.py
OUT   없음 (검사)
PARAM 없음
밖    **실제 수가 옳은가는 안 본다**(산출물이 있어야 안다 — `verify.sh` 의 「폭 교차대조」). 어느 규칙이 옳은가도 안 본다.
"""
from __future__ import annotations

import widthcross as W
import widthmatch as M


def test_fences_come_from_the_quartiles_not_from_a_constant():
    f = W.fences([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    assert f["lo"] == f["q25"] - W.TUKEY_K * f["iqr"] and f["hi"] == f["q75"] + W.TUKEY_K * f["iqr"]
    wide = W.fences([0.0, 10.0, 20.0, 30.0])
    assert wide["hi"] - wide["lo"] > f["hi"] - f["lo"]            # 분포가 넓으면 울타리도 넓다
    assert W.fences([]) is None


def test_outside_counts_both_sides_separately():
    rows = [{"seg_uid": "A", "wmin": 20.0, "survey": 5.0}, {"seg_uid": "B", "wmin": 0.0, "survey": 5.0},
            {"seg_uid": "C", "wmin": 5.0, "survey": 5.0}, {"seg_uid": "D", "wmin": None, "survey": 5.0}]
    assert W.outside(rows, {"lo": -1.0, "hi": 1.0}) == {"아래(우리가 더 좁다)": 1, "위(우리가 더 넓다)": 1}


def test_official_gap_is_the_spread_between_the_two_official_sources():
    q = W.official_gap([{"survey": 5.0, "ledger": 6.0}, {"survey": 8.0, "ledger": 8.0}, {"survey": None, "ledger": 4.0}])
    assert q["n"] == 2 and q["max"] == 1.0 and q["min"] == 0.0
    assert W.official_gap([]) is None


def test_triage_uses_only_the_evidence():
    t = W.triage
    assert t({"road_name": "A", "survey_name": "B", "n_sample": 9})[0] == "접합 인공물"
    assert t({"road_name": "A", "survey_name": None, "n_sample": 9})[0] == "이름 미상"
    assert t({"road_name": "A", "survey_name": "A", "n_sample": 2}) == ("표본 부족", ["n_sample≤2"])
    assert t({"road_name": "A", "survey_name": "A", "n_sample": 3}) == ("실결함 후보", [])
    assert t({"road_name": "A", "survey_name": "B", "n_sample": 1}) == ("접합 인공물", ["n_sample≤2"])   # 약점은 따로 표시한다
    assert t({"road_name": "A", "survey_name": "A", "n_sample": None})[0] == "표본 부족"                 # 결측은 0 이 아니라 약점이다


def test_overclaim_profile_counts_the_ledger_values_and_the_thin_ones():
    over = [{"증거": {"ledger": 6.0, "wmin": 7.5, "n_sample": 2}}, {"증거": {"ledger": 6.0, "wmin": 9.0, "n_sample": 8}},
            {"증거": {"ledger": 2.0, "wmin": 8.0, "n_sample": 1}}]
    p = W.overclaim_profile(over)
    assert p["건수"] == 3 and p["대장 명목폭별"] == {"2.0": 1, "6.0": 2} and p["n_sample≤2"] == 2


def test_reason_of_is_ordered_and_splits_at_the_matcher_band():
    assert M.reason_of(False, False, 0.1, True) == "우리 wmin 없음"
    assert "결측" in M.reason_of(True, True, 0.1, True)
    assert "50m" in M.reason_of(True, False, None, None)
    assert "0.5m 안" in M.reason_of(True, False, 0.5, True) and "0.5~2m" in M.reason_of(True, False, 0.6, True)
    assert "10~50m" in M.reason_of(True, False, 30.0, False) and "이름 다름" in M.reason_of(True, False, 30.0, False)


def test_adopt_requires_the_same_distribution_and_the_current_overlap_floor():
    base = {"band": 0.5, "min": 0.5, "n": 10, "p": None}
    rows = [base, {"band": 2, "min": 0.5, "n": 20, "p": 0.5}, {"band": 5, "min": 0.5, "n": 30, "p": 0.01},
            {"band": 1, "min": 0.3, "n": 99, "p": 0.9}]
    assert M.adopt(rows)["band"] == 2                            # p 가 낮은 것(5)과 최소 겹침이 다른 것(0.3)은 안 뽑힌다
    assert M.adopt([base]) is None

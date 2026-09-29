#!/usr/bin/env python3
"""
test_widthcross.py — 폭 교차대조의 **판별식**이 맞는가. 데이터 없이 문다.

── 왜 생겼나 (2026-09-28 · DECISIONS §289) ─────────────────────
우리 폭에 대한 외부 대조가 `nfa_compare` 하나였고 그것은 **오염돼 있다** —
절대편차를 12.6 → 7.24 로 줄이는 데 게이트로 썼다(MASTER §4-1).

그런데 **방법이 독립인 증인이 이미 대장에 있었다.** `ngii1k.py` 주석이
「A0020000 도로폭은 측량 성과다. 우리 기하 계산과 독립이라 **대조 검증에
쓴다**」고 적어 두고 **뽑아만 놓았다.** `road_bt_m` 은 구간마다 붙어 있는데
스키마가 「참고용. 판정에는 안 쓴다」고 적고 끝이다.

★ 대조는 **한 번 손으로 이미 했다.** `segments.py:413` 주석에 결과까지
  남아 있다(「64구간 중 36구간이 셋 다 3m 미만인데 blocked 에서 빠졌다 —
  미탐 쪽이다」). 값이 큰 실측이었는데 **산문으로만 남아 상설이 못 됐다.**

IN    tools/widthcross.py
OUT   없음 (검사)
PARAM 없음
밖    **실제 숫자가 옳은가는 안 본다.** 그것은 산출물이 있어야 알고
      `verify.sh` 의 「폭 교차대조」 단계가 잰다. 여기가 드는 것은
      「판별식이 맞는 것을 맞다 하고 틀린 것을 틀리다 하는가」다.
      **어느 원천이 진실인가도 안 본다** — 측량폭도 사람이 잰 값이다.
"""
from __future__ import annotations

from pathlib import Path

import widthcross as W

ROOT = Path(__file__).resolve().parents[1]


# ── ① 모순 판별 — 문턱이 없다 ──────────────────────────────────
def test_a_consistent_segment_is_not_a_contradiction():
    assert not W.contradictions({"wmin": 2.0, "wmax": 5.0, "survey": 5.0})


def test_a_minimum_above_the_nominal_width_is_a_contradiction():
    """★ 우리 **최솟값**이 명목폭을 넘으면 길 어디서도 그만큼 안 좁다는 뜻이다."""
    v = W.contradictions({"wmin": 7.0, "survey": 5.0})
    assert v and "명목폭을 넘는다" in v[0]


def test_walls_narrower_than_the_road_is_a_contradiction():
    """벽은 노면 밖에 있다. 담~담이 노면보다 좁을 수 없다."""
    v = W.contradictions({"wmin": 5.0, "wmax": 2.0})
    assert v and "노면보다 좁다" in v[0]


def test_rounding_is_not_a_contradiction():
    """★ 측량폭은 0.1m 단위 · 대장폭은 정수다. 표기 차이로 울면 안 된다."""
    assert not W.contradictions({"wmin": 5.3, "survey": 5.0})


def test_missing_values_are_not_contradictions():
    for row in ({}, {"wmin": None, "survey": None}, {"survey": 5.0},
                {"wmin": ""}, {"wmin": float("nan"), "survey": 5.0}):
        assert not W.contradictions(row), row


def test_zero_is_a_number_not_a_blank():
    """★ 0 을 결측으로 읽으면 「폭 0」 이라는 이상 신호가 사라진다."""
    assert W._num(0) == 0.0
    assert W._num(0.0) == 0.0
    assert W._num(None) is None and W._num("") is None


# ── ② 분포 ─────────────────────────────────────────────────────
def test_quartiles():
    q = W.quartiles([1.0, 2.0, 3.0, 4.0])
    assert (q["n"], q["min"], q["median"], q["max"]) == (4, 1.0, 2.5, 4.0)
    assert q["q25"] == 1.75 and q["q75"] == 3.25


def test_quartiles_of_one_and_of_none():
    assert W.quartiles([7.0])["median"] == 7.0
    assert W.quartiles([]) == {}


def test_cross_collects_pairs_and_contradictions():
    r = W.cross([{"seg_uid": "A", "wmin": 7.0, "survey": 5.0},
                 {"seg_uid": "B", "wmin": 3.0, "survey": 5.0}])
    assert r["구간"] == 2
    assert [b["seg"] for b in r["모순"]] == ["A"]
    assert r["차이 분포"]["wmin-survey"]["n"] == 2
    assert r["원천별 값 있음"]["survey"] == 2
    assert r["원천별 값 있음"]["ledger"] == 0


# ── ③ 이 도구의 이유가 선언에 남아 있는가 ──────────────────────
def test_at_least_two_sources_are_declared_independent():
    """★ 독립 원천이 없으면 이 도구는 `width_disagree_m` 와 같은 것이 된다.

    지금 있는 `width_disagree_m` 는 `ngii1k` · `ngii` · `silpok` 셋을 대는데
    **셋 다 같은 방법**(폴리곤에 법선 긋기)이다. 같은 자로 세 번 잰 것이라
    서로 맞아도 그 방법이 옳다는 증거가 못 된다. 이 도구의 존재 이유가
    「방법이 다른 증인」이므로 그 선언이 사라지면 안 된다.
    """
    indep = [k for k, (_w, i) in W.SOURCES.items() if i]
    assert len(indep) >= 2, f"독립 원천이 {indep} 뿐이다"
    assert "survey" in indep and "ledger" in indep


def test_no_threshold_constant_sneaks_in():
    """★ 1판은 **문턱을 발명하지 않는다.** 분포를 먼저 보고 다음에 정한다.

    `ROUNDING_M` 은 문턱이 아니라 **표기 단위**다(측량 0.1m · 대장 정수).
    그 밖의 배수·여유값이 들어오면 근거 없는 수가 판정에 끼는 것이다.
    """
    src = (ROOT / "tools" / "widthcross.py").read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]          # 머리말 밖만 본다
    for banned in ("WALL_K", "RATIO", "TOL_M", "MAX_DIFF"):
        assert banned not in body, f"문턱 상수 `{banned}` 가 생겼다"


def test_the_comparison_stays_outside_the_judgment_closure():
    """★ `nfa_compare` 가 §247 에서 나간 것과 같은 자리다.

    대조가 판정 지문 안으로 들어오면 대조 도구를 고칠 때마다 golden 이 울고,
    정당하지 않은 빨간불이 반복되면 사람이 `--allow-stale` 을 습관으로 만든다.
    """
    from firelane.shardseal import code_closure
    closure = {Path(p).name for p in code_closure("firelane.segments")}
    assert "widthcross.py" not in closure


def test_selftest_is_not_an_empty_net():
    assert W.selftest() == 0


# ── 축 ③ · `clear` 가 대장과 서로를 부정하는가 (§299) ───────────


def _clear(ledger, **kw):
    return {"seg_uid": "A", "verdict": "clear", "ledger": ledger, **kw}


def test_대장이_넉넉하면_과대주장이_아니다():
    assert not W.overclaim([_clear(8.0)], W.TRUCK)
    assert not W.overclaim([_clear(7.0)], W.CLEAR_M)


def test_대장이_소방차_하한_미만인데_clear_면_모순이다():
    """★ 실측 9건. 대장이 「소방차가 물리적으로 못 들어간다」고 적은 길이다."""
    got = W.overclaim([_clear(2.0)], W.TRUCK)
    assert len(got) == 1
    assert "clear 인데" in got[0]["why"]


def test_clear_가_아닌_판정은_안_센다():
    """그 구간은 강한 주장을 **안 했다.** 안 한 주장을 모순이라 하면 안 된다."""
    for v in ("needs_cv", "blocked", "unknown"):
        assert not W.overclaim([{"seg_uid": "A", "verdict": v, "ledger": 2.0}],
                               W.TRUCK)


def test_대장이_결측이면_모순이_아니다():
    """회색은 모순이 아니다 — 잴 것이 없는 것과 어긋난 것은 다르다."""
    assert not W.overclaim([_clear(None)], W.TRUCK)


def test_두_층이_갈려_있다():
    """★ 한 수로 세면 「대장 6.0 대 wmin 7.0」이 「대장 2.0 대 29.91」을 묻는다."""
    six = [_clear(6.0)]
    assert not W.overclaim(six, W.TRUCK), "딱딱한 층이 경계 사례를 잡는다"
    assert W.overclaim(six, W.CLEAR_M), "부드러운 층이 경계 사례를 안 잡는다"


def test_부드러운_층이_딱딱한_층을_덮는다():
    """층이 뒤집히면 딱딱한 건이 부드러운 집계에서 사라진다."""
    assert W.CLEAR_M > W.TRUCK
    two = [_clear(2.0)]
    assert W.overclaim(two, W.TRUCK) and W.overclaim(two, W.CLEAR_M)


def test_문턱을_발명하지_않았다():
    """`clear` 의 문턱은 **판정기가 정본이다.** 도구가 수를 적으면 두 집에 산다."""
    from firelane.seg.params import PARK, TRUCK
    assert W.CLEAR_M == TRUCK + 2 * PARK
    src = (Path(__file__).resolve().parents[1] / "tools/widthcross.py").read_text(
        encoding="utf-8")
    assert "CLEAR_M = TRUCK + 2 * PARK" in src, "문턱을 수로 박았다"


def test_전수_집계가_두_층을_따로_낸다():
    rows = [_clear(2.0), {"seg_uid": "B", "verdict": "clear", "ledger": 6.0},
            {"seg_uid": "C", "verdict": "clear", "ledger": 9.0}]
    r = W.cross(rows)
    assert len(r["과대주장 딱딱"]) == 1
    assert len(r["과대주장 부드러움"]) == 2


def test_래칫이_선언돼_있다():
    """래칫이 없으면 수가 조용히 는다."""
    assert isinstance(W.OVERCLAIM_HARD, int) and W.OVERCLAIM_HARD >= 0
    assert isinstance(W.OVERCLAIM_SOFT, int)
    assert W.OVERCLAIM_SOFT >= W.OVERCLAIM_HARD, "부드러운 층이 딱딱한 층보다 작다"


def test_모순에_근거가_붙는다():
    """★ 근거 없는 모순 보고는 조사를 사람에게 미룬다(§290-2 와 같은 병)."""
    r = W.cross([{"seg_uid": "A", "wmin": 7.0, "survey": 5.0,
                  "road_name": "가로", "survey_name": "나로", "n_sample": 3}])
    assert len(r["모순"]) == 1
    e = r["모순"][0]["증거"]
    assert e["road_name"] == "가로" and e["survey_name"] == "나로"
    assert e["n_sample"] == 3

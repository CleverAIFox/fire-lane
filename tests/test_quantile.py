#!/usr/bin/env python3
"""
test_quantile.py — 분위수 정본이 **남이 재는 수와 같은가.** (DECISIONS §471)

── 왜 생겼나 ───────────────────────────────────────────────────
`src/firelane/quantile.py` 는 공식을 안 짜고 `numpy.quantile` 을 부른다.
그러면 드는 것은 「공식이 맞나」가 아니라 **「우리가 고른 정의가 저장소가
이미 쓰던 정의와 같나」**다 — `tools/skeleton_compare.py` 와
`tools/corner_probe.py` 가 `pandas.Series.quantile` 로 같은 이름(p90)을
찍고 있고, 그 둘이 어긋나면 **같은 이름의 두 수**가 문서에 같이 선다.

★ 그래서 이 파일은 **pandas 를 기준으로** 든다. 손으로 계산한 기댓값을
  적지 않는다 — 그러면 그 기댓값이 셋째 정의가 된다(§471 이 고친 병이다).

★ 그리고 **옛 손 색인이 틀렸다는 것**을 수로 든다. 「n ≤ 10 이면 p90 이
  최댓값」은 산문이 아니라 판별식이어야 한다 — 안 그러면 누군가 그 색인을
  「원래 그랬다」며 되돌린다.

IN    없음
OUT   없음 (검사)
PARAM 없음
밖    가중 분위수 · 보간 방식 선택은 안 본다 — 정본이 하나만 든다.
"""
from __future__ import annotations

import random

import pandas as pd
import pytest

from firelane.quantile import P90, p90, quantile


#: 옛 손 색인 둘. **시험 안에만 산다** — 저장소 코드에서는 금지다
#: (`tests/test_handrolled.py::분위수 손 색인`). 여기 두는 이유는 둘이다 —
#: ① 그것이 틀렸다는 것을 수로 들고 ② **판별식에 심어 우는 것을 본다**.
def _old_a(v: list[float], q: float = P90) -> float:
    s = sorted(v)
    return s[int(len(s) * q)]


def _old_b(v: list[float], q: float = P90) -> float:
    s = sorted(v)
    return s[int(q * (len(s) - 1))]


def pandas_faults(fn, trials: int = 300, seed: int = 471) -> list[tuple]:
    """`fn(v, q)` 이 `pandas.Series.quantile` 과 어긋난 자리. **비면 산다.**

    ★ 순수 함수로 뺀 이유 — 아래 카나리아가 **옛 손 색인을 심어** 이 자가
      실제로 우는지 본다. 자를 심어 보지 않으면 「전부 초록」이 제가 보고
      있다는 것을 증명하지 못한다(§445).
    """
    rnd = random.Random(seed)
    bad: list[tuple] = []
    for _ in range(trials):
        n = rnd.randint(1, 80)
        v = [round(rnd.uniform(-50, 500), 4) for _ in range(n)]
        for q in (0.0, 0.1, 0.25, 0.5, 0.75, P90, 0.95, 1.0):
            b = float(pd.Series(v).quantile(q))
            try:
                a = fn(v, q)
            except Exception as e:                      # noqa: BLE001  심은 자도 받는다
                bad.append((n, q, repr(e), b))
                continue
            if abs(a - b) > 1e-9:
                bad.append((n, q, a, b))
    return bad


def test_the_canon_equals_pandas():
    """★ 본체. 무작위 표본에서 `pandas.quantile` 과 **전부** 같다."""
    assert not pandas_faults(quantile), \
        f"pandas 와 어긋난다 — 처음 셋 {pandas_faults(quantile)[:3]}"


def test_the_judge_bites_the_old_hand_index():
    """★ **카나리아.** 옛 손 색인 둘을 심으면 그 자가 **운다.**"""
    assert pandas_faults(_old_a, trials=40), "n×q 색인을 안 댄다 — 자가 죽었다"
    assert pandas_faults(_old_b, trials=40), "q×(n−1) 색인을 안 댄다"


def test_one_point_is_itself():
    """`statistics.quantiles` 는 n=1 에 운다 — 한 점짜리 표본은 실재한다."""
    assert p90([7.5]) == 7.5
    assert quantile([7.5], 0.0) == quantile([7.5], 1.0) == 7.5


def test_the_old_hand_index_said_p90_was_the_maximum():
    """★ **옛 색인이 틀렸다는 것을 수로 든다.** n ≤ 10 에서 「p90」 이 최댓값이다."""
    for n in range(2, 11):
        v = [float(i) for i in range(1, n + 1)]
        assert _old_a(v) == max(v), f"n={n} 에서 옛 색인이 최댓값이 아니다"
        assert p90(v) < max(v), f"n={n} 에서 정본이 최댓값을 낸다"
    # 그리고 다른 쪽 손 색인은 n = 2 에서 **최솟값**이었다
    assert _old_b([1.0, 9.0]) == 1.0
    assert p90([1.0, 9.0]) == pytest.approx(8.2)


def test_an_empty_sample_cries():
    """빈 표본에 0 이나 None 을 내면 「없다」와 「0 이다」가 섞인다(§467 족)."""
    with pytest.raises(ValueError):
        quantile([], P90)
    with pytest.raises(ValueError):
        p90([])


@pytest.mark.parametrize("q", [-0.1, 1.1, 90])
def test_a_q_outside_zero_to_one_cries(q: float):
    """`0.9` 와 `90` 을 섞어 쓰는 사고를 막는다 — 백분율이 아니라 비율이다."""
    with pytest.raises(ValueError):
        quantile([1.0, 2.0, 3.0], q)


def test_unsorted_input_is_sorted_for_you():
    """부르는 쪽이 정렬을 기억해야 한다면 그것은 언젠가 안 정렬된다."""
    assert quantile([5, 1, 3], P90) == quantile([1, 3, 5], P90)

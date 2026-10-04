#!/usr/bin/env python3
"""
test_colorsim.py — 색각 변환이 **알려진 사실**을 내는가.

── 왜 생겼나 (2026-10-04 · DECISIONS §383) ─────────────────────
`web/config.js` 가 네 색을 고른 근거로 적은 수는 **바탕 대비**다. 지면에서
떠 보이는가를 쟀고 **집합 안에서 서로 갈리는가**는 안 쟀다. 둘은 다른 축이고,
네 색이 전부 배경에서 잘 떠도 서로 비슷하면 지도는 한 색이 된다.

★ 그리고 축이 **둘**이다 — 색상(ΔE)과 밝기(휘도비). 실측하니 색상은 최소
  ΔE 14.7 로 넉넉한데 `blocked ↔ unknown` 의 휘도비가 **정상 시각에서도
  1.00** 이다. 지도선은 얇고 멀어서 밝기로 먼저 읽힌다.

IN    tools/colorsim.py · web/config.js
OUT   없음 (검사)
PARAM 없음
밖    **어떤 색이어야 하는지는 안 본다.** 드는 것은 ① 변환이 적록·청황
      붕괴를 재현하는가 ② 선언한 래칫이 실측과 같은가 둘이다.
"""
from __future__ import annotations

import colorsim as C

RED, GREEN, BLUE = (255, 0, 0), (0, 255, 0), (0, 0, 255)


def test_normal_vision_is_the_identity():
    """★ 왕복(RGB→LMS→RGB)의 오차까지 포함해서 본다. 행렬 둘이 서로의
    역이 아니면 정상 시각부터 색이 밀리고, 그러면 아래 수가 전부 거짓이 된다.
    """
    for c in (RED, GREEN, BLUE, (110, 120, 138)):
        assert C.delta_e(C.simulate(c, "normal"), c) < 0.01, c


def test_red_and_green_collapse_under_deuteranopia():
    """★ 이 도구의 존재 이유다. 재현이 안 되면 나머지 수가 다 거짓이다."""
    norm = C.delta_e(C.simulate(RED, "normal"), C.simulate(GREEN, "normal"))
    deut = C.delta_e(C.simulate(RED, "deutan"), C.simulate(GREEN, "deutan"))
    assert deut < norm / 2


def test_blue_and_green_collapse_under_tritanopia():
    """청황 이상은 **파랑과 초록**을 붙인다. 파랑 자체는 그 혼동축의 정점이라
    거의 안 움직인다 — 「파랑이 옮겨지는가」로 물으면 멀쩡한 변환을 틀렸다 한다."""
    norm = C.delta_e(C.simulate(BLUE, "normal"), C.simulate(GREEN, "normal"))
    trit = C.delta_e(C.simulate(BLUE, "tritan"), C.simulate(GREEN, "tritan"))
    assert trit < norm / 2


def test_red_green_blindness_leaves_blue_alone():
    assert C.delta_e(C.simulate(BLUE, "normal"), C.simulate(BLUE, "deutan")) < 25


def test_the_lightness_axis_never_dies():
    """어느 시각에서도 흑백은 갈린다. 안 갈리면 변환이 깨진 것이다."""
    for v in C.VISION:
        assert C.delta_e(C.simulate((255, 255, 255), v),
                         C.simulate((0, 0, 0), v)) > 90


def test_identical_colors_have_no_difference():
    assert C.delta_e((10, 20, 30), (10, 20, 30)) == 0
    assert C.lum_ratio((10, 20, 30), (10, 20, 30)) == 1.0


def test_luminance_ratio_is_symmetric_and_at_least_one():
    a, b = (255, 255, 255), (0, 0, 0)
    assert C.lum_ratio(a, b) == C.lum_ratio(b, a)
    assert C.lum_ratio(a, b) > 20


# ── 실물 ─────────────────────────────────────────────────────
def test_the_four_verdict_colors_are_read_from_config():
    cs = C.colors()
    assert set(cs) == {"blocked", "needs_cv", "clear", "unknown"}
    for k, v in cs.items():
        assert len(v) == 3 and all(0 <= c <= 255 for c in v), k


def test_the_declared_ratchets_match_what_the_colors_actually_say():
    got = C.ratchet_values()
    assert got["COLOR_MIN_DE"] == C.COLOR_MIN_DE
    assert got["COLOR_MIN_LUM"] == C.COLOR_MIN_LUM


def test_two_verdicts_still_share_the_same_lightness():
    """★ 음성 대조. `blocked` 와 `unknown` 의 휘도비가 **정상 시각에서 1.00**
    이다 — 색상은 다른데 밝기가 같다. 누가 색을 고쳐 이 칸이 벌어지면 이
    시험이 울고, 그때 §383 을 다시 읽고 지운다. 고쳐지는 것이 목적이다.
    """
    m = C.matrix(C.colors())
    worst = min(m, key=lambda r: r["lum"])
    assert worst["lum"] < 1.05, f"밝기가 벌어졌다 — {worst}"
    assert worst["vision"] == "normal", "색각 이상이 아니라 정상 시각의 일이다"


def test_the_tool_passes_its_own_selftest():
    assert C.selftest() == 0

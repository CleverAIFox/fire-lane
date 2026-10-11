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


# ── ★ 2026-10-12 (DECISIONS §480-1). **카나리아** ────────────────
#   `tools/canary.py` 가 이 파일을 「합성 결함을 넣어 우는 것을 본 자리가
#   없다」로 들고 있었고 **그 지적이 맞았다** — 위 시험들은 변환의 성질을
#   재지만 **판정**을 한 번도 안 민다(판정이 `show()` 의 찍는 루프 안에
#   있어서 부를 수가 없었다). `faults()` 로 빼고 양방향으로 민다.
def test_the_real_four_colors_pass_the_judge():
    """실물 넷은 **조용하다.** 여기가 빨간불이면 색을 고쳐야 한다는 뜻이다."""
    assert not C.faults(C.matrix(C.colors())), (
        "실물 판정 색이 래칫 아래다 — 색을 바꿨으면 래칫을 같이 보라\n  "
        + "\n  ".join(C.faults(C.matrix(C.colors()))))


def test_the_judge_bites_two_identical_colors():
    """★ **같은 색 둘**을 심으면 운다. ΔE 0 이고 휘도비 1.00 이다."""
    same = {"a": (26, 150, 96), "b": (26, 150, 96),
            "c": (224, 53, 38), "d": (110, 120, 138)}
    bad = C.faults(C.matrix(same))
    assert bad, "같은 색 둘을 심어도 조용하다 — 자가 죽었다"
    assert any("a ↔ b" in m for m in bad), f"심은 쌍을 안 짚는다 — {bad[:3]}"


def test_the_lightness_axis_can_actually_cry():
    """★ **밝기 축이 살아 있는가.** (DECISIONS §480-2)

    휘도비는 정의상 **≥ 1** 이므로, 래칫을 `× 100` 으로 적으면 실측 1.0021 이
    `int()` 로 **100** 이 되고 그 수는 **이 양의 바닥**이다 — 내려갈 자리가
    없으니 영원히 안 운다. 만분율로 올려 그 축을 살렸다.

    ★ 여기서 드는 것은 「지금 색이 좋은가」가 아니라 **「그 자가 울 수
      있는가」**다. 바닥에 앉은 래칫은 초록을 주지만 아무것도 안 지킨다.
    """
    # ① 바닥이 아니다 — 실측값이 단위의 최솟값보다 크다
    assert C.COLOR_MIN_LUM > C.LUM_SCALE, (
        f"래칫 {C.COLOR_MIN_LUM} 이 바닥({C.LUM_SCALE}) 이다 —"
        " 내려갈 자리가 없으면 안 운다")
    # ② 조금 나빠진 쌍을 심으면 **운다**
    worse = [{"pair": "a ↔ b", "vision": "normal", "de": 99.0,
              "lum": (C.COLOR_MIN_LUM - 5) / C.LUM_SCALE}]
    bad = C.faults(worse)
    assert any("휘도비" in m for m in bad), (
        f"래칫보다 낮은 휘도비를 안 짚는다 — {bad}. 종전 `× 100` 단위에서는"
        " 이 차이가 정수로 사라져 **영원히 조용했다**")
    # ③ 그리고 ΔE 는 멀쩡하므로 **색상 축으로는 안 운다** — 두 축이 따로다
    assert not any("ΔE" in m for m in bad), f"색상 축이 끼어든다 — {bad}"

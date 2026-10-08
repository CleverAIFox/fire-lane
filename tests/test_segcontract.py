#!/usr/bin/env python3
"""
test_segcontract.py — 발행 판정 계약의 판별식 셋이 **양방향으로** 무는가.

── 왜 생겼나 (2026-10-08 · DECISIONS §435 · PLAN #104) ─────────
`#104` 가 계약 셋을 적었다 — 폭 상한 · 도로명 규칙 위반 · 조용한 결측.
실측하면 앞 둘이 **0** 이고 셋째가 2 다. 분모가 0 인 관문은 **판별식이 죽어도
초록**이라, 셋이 합성 위반에서 우는지를 여기서 묻는다.

★ 셋째가 제일 중요하다. 앞 둘은 「값이 틀렸다」를 말하고 셋째는 「왜인지를
  읽는 사람이 알 수 없다」를 말한다. 파이프라인은 사유를 **안다**(`all_xsec`)
  그런데 표준출력에만 찍고 산출물에 안 넣는다.

IN    tools/segcontract.py
OUT   없음 (검사)
PARAM 없음
밖    **값이 옳은가는 안 본다.** 어느 폭이 맞는지는 `widthcross` 가 들고,
      어느 판정이 맞는지는 `golden` 이 든다.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import segcontract as S

ROOT = Path(__file__).resolve().parents[1]
CAP = 60.0


# ── ① 폭이 상한 밖이거나 뒤집혔다 ──────────────────────────────
def _w(**p) -> list[str]:
    return S.width_out_of_range([{"seg_id": "X", **p}], CAP)


def test_a_width_inside_the_cap_is_fine():
    assert not _w(width_min_m=3.0, width_max_m=7.0)


def test_a_width_above_the_cap_is_caught():
    assert _w(width_min_m=3.0, width_max_m=CAP + 1)


def test_a_zero_or_negative_width_is_caught():
    """0 은 결측이 아니라 **틀린 값**이다. 결측은 `None` 으로 온다."""
    assert _w(width_min_m=0.0, width_max_m=5.0)
    assert _w(width_min_m=-1.0, width_max_m=5.0)


def test_an_inverted_width_is_caught():
    assert _w(width_min_m=9.0, width_max_m=4.0)


def test_a_missing_width_is_not_a_range_defect():
    """★ 결측은 ③ 의 물음이다. 여기서 같이 울면 같은 구간이 두 번 센다."""
    assert not _w(width_min_m=None, width_max_m=None)


# ── ② 도로명이 꼴 밖이다 ──────────────────────────────────────
@pytest.mark.parametrize("name", ["필문대로", "필문대로205번길", "지호로86번길",
                                  "2순환로", "제봉로", "동계천로43번길", "금남로"])
def test_real_published_road_names_pass(name):
    """★ 발행된 107개 고유 이름에서 유도한 꼴이다 — 멀쩡한 것이 빨개지면 안 된다."""
    assert not S.roadname_off_rule([{"road_name": name}])


@pytest.mark.parametrize("name", ["엉뚱한것", "로123", "길", "필문대로205번"])
def test_an_off_rule_road_name_is_caught(name):
    assert S.roadname_off_rule([{"road_name": name}])


def test_a_blank_road_name_is_caught():
    """이름 없는 구간은 **찾을 수가 없다.** 결측도 위반으로 센다."""
    assert S.roadname_off_rule([{"road_name": None}])
    assert S.roadname_off_rule([{"road_name": "   "}])


def test_the_same_off_rule_name_counts_once():
    """★ **고유 이름**을 센다. 한 이름이 틀리면 그 이름의 구간 전부가 같은
    결함이고 고칠 것은 이름 하나다 — 구간으로 세면 수가 결함의 크기를 속인다."""
    got = S.roadname_off_rule([{"road_name": "엉뚱한것"}] * 9)
    assert len(got) == 1 and "구간 9" in got[0]


# ── ③ 조용한 결측 ────────────────────────────────────────────
def test_a_present_value_is_not_missing():
    assert not S.silent_missing([{"seg_id": "A", "width_min_m": 3.0}])


def test_a_missing_value_with_a_written_reason_is_not_silent():
    assert not S.silent_missing(
        [{"seg_id": "A", "width_min_m": None, "unknown_reason": "no_cctv_band"}])


def test_whitespace_is_not_a_reason():
    """**침묵에는 값을 안 치른다.** 공백 사유는 사유가 아니다."""
    assert S.silent_missing([{"seg_id": "A", "width_min_m": None,
                              "unknown_reason": "   "}])


def test_a_missing_value_with_no_reason_at_all_is_silent():
    assert S.silent_missing([{"seg_id": "A", "width_min_m": None}])


# ── 선언 ↔ 실측 ──────────────────────────────────────────────
def test_the_declared_ratchets_match_the_published_judgment():
    """래칫 셋이 **실물과 같은가.** 늘면 결함이고 줄면 기록을 조여야 한다."""
    got = S.ratchet_values()
    want = {k: getattr(S, k) for k in S.RATCHETS}
    assert got == want, (
        f"래칫이 실측과 다르다 — 실측 {got} · 선언 {want}\n"
        "  늘었으면 이 배치가 계약을 깼다. 줄었으면 선언을 그 수로 내려라.")


def test_the_two_silent_segments_are_the_transect_shutouts():
    """★ 조용한 결측 2 의 **정체**를 못박는다.

    둘 다 `blocked` 이고 표본을 한 발도 못 쏜 구간이다(`all_xsec`). 사유를
    담을 칸이 `unknown_reason` 뿐이고 그것은 `unknown` 전용이라 비어 있다.
    수가 2 에서 움직이면 **다른 것이 섞인 것**이므로 여기서 묻는다.
    """
    f = S.findings()
    assert len(f["silent"]) == S.SILENT_MISSING
    assert all("verdict=blocked" in x for x in f["silent"]), (
        f"조용한 결측에 `blocked` 가 아닌 것이 섞였다 — {f['silent']}\n"
        "  새 꼴이면 `NEEDS_REASON` 과 이 시험을 같이 고쳐라.")


def test_the_tool_passes_its_own_selftest():
    assert S.selftest() == 0

"""
test_canary.py — 강제자가 **합성 결함으로 울어 본 적 있는가**를 세는 자리.
  (DECISIONS §445 · PLAN #56 ① 닫힘)

★ 이 시험이 제 검사 대상이기도 하다. `tools/canary.py` 가 「카나리아 없는
  강제자」를 세는 강제자이므로, **그 자신에게 카나리아가 있어야** 한다 —
  없으면 세는 자가 저만 면제받는 꼴이고 그것이 이 저장소가 §398-6 ·
  §443-6 에서 두 번 배운 자리다.

★ 도구의 자기검사와 **같은 판별식을 두 곳에서** 민다. 자기검사는 합성 입력으로
  그물이 비었나를 보고(`selftests.py` 가 돌린다), 이쪽은 **실물 트리**에서 본다.

밖    **카나리아가 옳은가는 안 본다** — 합성 입력이 실물과 같은 꼴인지는
      사람이 본다(§436-6). 여기는 **쌍이 있는가**만 본다.
      **면제가 옳은가도 안 본다** — `EXEMPT` 의 사유는 리뷰가 든다.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools")]

import canary as C  # noqa: E402 — `sys.path` 를 먼저 깔아야 import 가 된다


def test_the_real_tree_matches_the_ratchet():
    """실물 — 카나리아 없는 강제자가 선언과 같은가. **양방향**이다."""
    n, denom = len(C.rows()), C.denominator()
    assert not C.faults(n, denom=denom), (
        f"카나리아 없는 강제자 {n} ≠ 래칫 {C.NO_CANARY} (분모 {denom})\n"
        "  늘었으면 그 강제자에 카나리아를 붙이고, 줄었으면 `NO_CANARY` 를 내려라.")


def test_the_axis_bites_when_a_naked_enforcer_lands():
    """합성 결함 — 하나 늘면 운다. **이것이 이 도구 자신의 카나리아다.**"""
    assert C.faults(C.NO_CANARY + 1, denom=99), "늘었는데 안 운다"


def test_a_loose_ratchet_is_also_a_fault():
    """줄어도 운다. 느슨한 래칫은 상한이 아니라 **지난 기록**이다(§436-8)."""
    assert C.faults(C.NO_CANARY - 1, denom=99), "줄었는데 안 운다"


def test_an_empty_net_is_a_fault():
    """★ 빈 그물 금지 — 분모가 0 이면 모든 강제자가 「카나리아 있음」이 된다."""
    assert C.faults(0, limit=0, denom=0), "분모 0 에서 조용하다"
    assert C.denominator() > 50, (
        f"실물 분모가 {C.denominator()} 다 — 수집기를 의심하라")


def test_it_counts_by_grammar_not_by_name():
    """★ 이름(`*_is_alive`)으로 세지 않는다. 낱말로 세면 §444-1 과 같은 병이다 —
    규약에 없는 이름을 쓴 카나리아가 영영 0건으로 세진다."""
    named = ast.parse("def t_is_alive():\n    assert f(1)\n")
    assert not C.has_canary(named), "이름만 보고 카나리아로 센다"
    pair = ast.parse("def a():\n    assert not f(1)\ndef b():\n    assert len(f(2)) == 1\n")
    assert C.has_canary(pair), "이름이 없으면 쌍을 못 본다"


def test_the_ratchet_declares_its_direction():
    """래칫이 **내려가는 쪽**으로 선언돼 있는가. 빚은 늘 수 없다."""
    assert C.RATCHETS == {"NO_CANARY": "down"}, C.RATCHETS
    assert C.ratchet_values()["NO_CANARY"] == len(C.rows())


def test_every_exemption_names_a_reason():
    """면제마다 사유가 있다. 사유 없는 면제는 다음 사람이 못 지운다(§69)."""
    for k, why in C.EXEMPT.items():
        assert len(why.strip()) >= 15, f"`{k}` 의 사유가 너무 짧다"

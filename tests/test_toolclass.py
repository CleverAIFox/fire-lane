#!/usr/bin/env python3
"""
test_toolclass.py — **도구 부류의 가름이 살아 있는가.**  (DECISIONS §398)

밖    **부류가 옳은가는 안 본다** — `fl.sh` 를 「생산」이라 적어도 통과한다.
      여기가 드는 것은 ①어휘가 하나인가 ②도출이 죽지 않았는가
      ③도출과 선언이 어긋나면 우는가 셋이다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("_tc", ROOT / "tools/toolclass.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


T = _mod()


def test_selftest_is_green():
    assert T.selftest() == 0


def test_the_tree_is_fully_classified():
    """★ 선언 없는 비관문이 0 이다 — 래칫이 그것을 잠근다."""
    bad, none = T.judge(T.classify())
    assert not bad, "도출과 선언이 어긋난다:\n" + "\n".join(bad)
    assert not none, "부류가 없는 비관문:\n" + "\n".join(none)
    assert T.ratchet_values()["UNDECLARED"] == T.UNDECLARED


def test_gates_are_derived_not_declared():
    """관문은 **묻는 자리가 있다** — 손으로 적지 않는다(§285-2 · §286)."""
    rows = T.classify()
    gates = [r for r in rows.values() if r["부류"] == "관문"]
    assert len(gates) > 50, f"관문을 {len(gates)}개만 도출했다 — 부르는 자리를 못 읽는다"
    assert all(g["선언"] is None for g in gates), "관문이 부류를 적었다 — 도출로 족하다"


def test_the_procedure_class_touches_no_output():
    """★ 사람이 물은 축 — 「우리 일하는 방식 때문에 있는 것」이 세어지는가."""
    rows = T.classify()
    proc = sorted(k for k, r in rows.items() if r["부류"] == "절차")
    assert proc, "절차가 0 이다 — 가름이 죽었다"
    for want in ("tools/fl.sh", "tools/inbox_fl.sh", "tools/merge_batch.sh"):
        assert want in proc, f"{want} 가 절차가 아니다"


def test_an_indented_line_is_not_a_declaration():
    """★ 들여쓴 줄을 선언으로 읽어 **이 파일의 어휘 설명**이 제 관문에 걸렸다."""
    assert T._DECL.search("    부류  조사   설명이다\n") is None
    assert T._DECL.match("부류  조사\n")
    assert T._DECL.search("# 부류  절차\n"), "셸의 주석 선언을 못 읽는다"

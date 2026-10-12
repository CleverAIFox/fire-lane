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


# ── 분모가 진입점인가 (2026-10-08 · DECISIONS §437 · PLAN #162) ────
def test_the_denominator_is_entry_points_not_every_file():
    """★ **몸통은 분모 밖이다.** 부를 수 없는 파일에 부류를 묻는 것이 틀렸다.

    종전 분모는 `tools/*` 전부였고 그 안에 몸통 열셋이 있었다. `UNDECLARED = 0`
    래칫이 그 열셋에 **낱말을 적게 만들었고**, 그 낱말은 뜻이 없었다 — 열셋이
    전부 「생산」인데 둘은 바로 아랫줄에서 「검사가 아니다」라고 적는다.
    """
    rows = T.classify()
    bodies = {k for k, r in rows.items() if not r["진입점"]}
    assert bodies, "몸통이 하나도 없다 — 도출이 늘 참이면 좁힌 것이 아니다"
    assert all(rows[k]["선언"] == "몸통" for k in bodies), (
        "몸통인데 다른 낱말을 적은 것 "
        f"{sorted(k for k in bodies if rows[k]['선언'] != '몸통')}")
    # ★ 분모가 **전부**가 되면 좁힌 뜻이 사라진다
    assert len(bodies) < len(rows), "전부 몸통이다 — 진입점 도출이 늘 거짓이다"


def test_an_entry_point_may_not_call_itself_a_body():
    """양방향 — 좁히는 쪽만 넣으면 좁힌 다음날 선언이 다시 썩는다."""
    rows = T.classify()
    liars = [k for k, r in rows.items() if r["진입점"] and r["선언"] == "몸통"]
    assert not liars, f"진입점인데 「몸통」이라 적었다 — {liars}"


def test_every_body_names_why_it_is_not_an_entry_point():
    """진입점은 **근거**를 든다. 부정은 근거 없이 적으면 검증이 안 된다."""
    rows = T.classify()
    ent = {k: r for k, r in rows.items() if r["진입점"]}
    assert ent, "진입점이 하나도 없다"
    naked = [k for k, r in ent.items() if not r["근거"]]
    assert not naked, f"진입점인데 근거가 비었다 — {naked}"


# ── 2026-10-12 (DECISIONS §489) ────────────────────────────────────
#   §487 이 분모를 바로잡은 뒤 이 파일이 빚에 남았다. `judge()` 를 **실물로**
#   부르고 「조용하다」만 보고 있었다 — 그 함수에 갈래가 **일곱**인데 어느
#   갈래도 우는 것을 본 자리가 없었다. 실물이 깨끗하면 일곱이 다 죽어도 초록이다.

def _row(*, 선언=None, 도출=False, 진입점=True, 근거="main()"):
    return {"부류": 선언 or ("관문" if 도출 else "?"), "선언": 선언,
            "도출": 도출, "진입점": 진입점, "근거": 근거}


def test_a_well_formed_row_is_silent():
    """★ 음성. 멀쩡한 줄에서 울면 실물이 영원히 빨갛다."""
    bad, none = T.judge({"tools/a.py": _row(선언="생산")})
    assert bad == [], bad
    assert none == [], none
    # 관문은 선언이 없는 것이 옳다 — 도출이 든다
    bad, none = T.judge({"tools/b.py": _row(도출=True)})
    assert bad == [] and none == [], (bad, none)
    # 몸통은 진입점이 아니어야 한다
    bad, none = T.judge({"tools/c.py": _row(선언="몸통", 진입점=False)})
    assert bad == [] and none == [], (bad, none)


def test_a_word_outside_the_vocabulary_is_caught():
    bad, _ = T.judge({"tools/a.py": _row(선언="아무말")})
    assert any("어휘 밖" in b for b in bad), bad
    # 어휘 전부를 말해 준다 — 안 말하면 다음 사람이 또 지어낸다
    assert any(next(iter(T.VOCAB)) in b for b in bad), bad


def test_a_gate_that_calls_itself_something_else_is_caught():
    """★ **도출이 이긴다.** verify · CI 가 부르면 그것은 관문이다."""
    bad, _ = T.judge({"tools/a.py": _row(선언="조사", 도출=True)})
    assert any("도출이 이기지 않는다" in b for b in bad), bad


def test_calling_yourself_a_gate_without_a_caller_is_caught():
    """★ 반대쪽 — 적어 놓고 아무도 안 부르면 **죽은 관문**이다."""
    bad, _ = T.judge({"tools/a.py": _row(선언="관문")})
    assert any("어디서도 안 부른다" in b for b in bad), bad


def test_an_entry_point_calling_itself_a_body_is_caught():
    """★ §437 이 닫은 자리 — 분모를 진입점으로 좁히면 몸통에 남은 옛 선언이
    조용해진다. 그 침묵을 이 갈래가 깬다."""
    bad, _ = T.judge({"tools/a.py": _row(선언="몸통", 근거="경로 호출")})
    assert any("진입점이다" in b and "경로 호출" in b for b in bad), bad


def test_a_non_entry_point_may_only_call_itself_a_body():
    bad, _ = T.judge({"tools/a.py": _row(선언="생산", 진입점=False)})
    assert any("물려받는다" in b for b in bad), bad


def test_a_non_entry_point_without_a_declaration_is_caught():
    bad, _ = T.judge({"tools/a.py": _row(진입점=False)})
    assert any("선언이 없다" in b for b in bad), bad


def test_an_undeclared_non_gate_goes_to_the_ratchet_not_to_the_red_list():
    """★ 그 둘이 **다른 통**이다. 섞으면 래칫이 빨간불과 같이 움직인다."""
    bad, none = T.judge({"tools/a.py": _row()})
    assert bad == [], bad
    assert none == ["tools/a.py"], none


def test_the_judge_is_not_an_empty_net():
    """★ 빈 입력에서 조용한 것은 옳다 — 그러나 실물 분모가 비면 터져야 한다.
    그 터짐은 `ratchet_values()` 가 든다(0 을 내지 않는다)."""
    assert T.judge({}) == ([], [])

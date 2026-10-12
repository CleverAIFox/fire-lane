"""
test_logic_print.py — 로직 지문기 **둘이 같은 물음에 같은 답**을 내는가.
  (DECISIONS §451 · PLAN #164 닫힘)

★ 지문기가 둘인 것 자체는 결함이 아니다 — `golden.logic_text` 는 토큰열이고
  `shardseal.logic_print` 는 `ast.dump` 다. **표현을 합치면 봉인이 찢어진다.**
  결함은 표현이 둘인 것이 아니라 **판별이 둘**이었던 것이다.

★ 그래서 이 자리가 보는 것은 「두 지문이 같은가」가 아니라 **「두 지문이 같다
  / 다르다에 합의하는가」**다. 지문 값은 서로 비교할 수 있는 것이 아니다.

밖    **어느 쪽이 옳은 판별인가는 안 본다** — 넷(모듈 · 클래스 · 함수 ·
      비동기 함수)으로 좁힌 사유는 DECISIONS §451 이 든다. 여기는 **둘이
      같은 자리를 보는가**만 본다.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

import golden as G  # noqa: E402 — `sys.path` 를 먼저 깔아야 import 가 된다

from firelane.shardseal import DOC_OWNERS, logic_print  # noqa: E402 — 위와 같은 사유

#: 둘 다 **안 봐야 하는** 손질. 로직을 한 글자도 안 건드린다.
NUDGES = {
    "머리말 주석": lambda s: "# 2026-10-10\n" + s,
    "빈 줄": lambda s: "\n\n" + s + "\n\n",
    "줄 안 공백": lambda s: s.replace(" = ", "  =  "),
    "모듈 docstring": lambda s: '"""붙인 머리말."""\n' + s,
}

#: 종전 판별 — 몸통을 가진 **모든** 노드의 첫 문자열을 docstring 으로 봤다.
#: 이 시험의 카나리아가 이것으로 합성 결함을 만든다.
WIDE = "넓은 쪽(모든 몸통)"


def tracked() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT,
                         capture_output=True, text=True, check=True, timeout=60)
    return [ROOT / x for x in out.stdout.split() if (ROOT / x).is_file()]


def _dump(src: str, *, wide: bool = False) -> str:
    """`logic_print` 과 같은 일을 **글**에서 한다. `wide` 면 종전 판별로 돈다."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        if wide:
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(getattr(body[0], "value", None), ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]
        elif isinstance(node, DOC_OWNERS) and ast.get_docstring(node) is not None:
            body = body[1:]
        node.body = body or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def agree(a: str, b: str, *, wide: bool = False) -> bool:
    """두 지문기가 「a 와 b 가 같은 로직인가」에 합의하나."""
    return (G.logic_text(a) == G.logic_text(b)) == (_dump(a, wide=wide) == _dump(b, wide=wide))


def test_the_two_fingerprinters_agree_on_every_tracked_file():
    """실물 전수 — 추적 `.py` 전부에 손질 넷을 넣고 둘의 답이 같은가."""
    split = [f"  {p.relative_to(ROOT).as_posix()}  [{why}]"
             for p in tracked() for why, f in NUDGES.items()
             if not agree(p.read_text(encoding="utf-8"), f(p.read_text(encoding="utf-8")))]
    assert not split, "두 지문기가 다른 답을 낸다:\n" + "\n".join(split)


def test_the_axis_bites_when_the_old_rule_comes_back():
    """★ 카나리아 — 넓은 판별로 되돌리면 **갈린다.** 그물이 비어 있지 않다는 증거다."""
    src = "def f():\n    if 1:\n        'bare'\n        return 2\n"
    alt = "def f():\n    if 1:\n        'other'\n        return 2\n"
    assert not agree(src, alt, wide=True), "종전 판별인데 합의한다 — 합성 결함을 못 본다"
    assert agree(src, alt), "좁힌 판별인데 갈린다"


def test_a_bare_string_statement_is_absent_from_the_tree():
    """좁히는 쪽으로 합쳐도 지문이 안 움직인 **사유**. 늘면 이 수가 운다."""
    found = []
    for p in tracked():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if not isinstance(body, list) or isinstance(node, DOC_OWNERS):
                continue
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(getattr(body[0], "value", None), ast.Constant)
                    and isinstance(body[0].value.value, str)):
                found.append(f"  {p.relative_to(ROOT).as_posix()}:{body[0].lineno}")
    assert not found, (
        "몸통 첫 줄의 맨 문자열이 있다 — 두 판별이 이 자리에서 갈렸던 꼴이다:\n"
        + "\n".join(found))


#: 두 지문기 — (파일, 함수 이름). 이 둘만 본다.
PRINTERS = (("tools/golden.py", "logic_text"), ("src/firelane/shardseal.py", "logic_print"))


def _body(rel: str, name: str) -> ast.AST:
    for node in ast.walk(ast.parse((ROOT / rel).read_text(encoding="utf-8"))):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"`{rel}` 에 `{name}` 이 없다 — 옮겼으면 이 목록을 고쳐라")


def hand_rolled(fn: ast.AST) -> bool:
    """이 함수가 docstring 판별을 **제 안에서** 다시 짜는가."""
    names = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)} \
        | {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    return "Constant" in names and "DOC_OWNERS" not in names


def test_both_fingerprinters_read_the_same_declaration():
    """판별이 다시 둘이 되는 것을 막는다 — 둘 다 `DOC_OWNERS` 를 지목하고,
    제 안에서 문자열 문장을 **직접 가려내지 않는다.**"""
    bad = []
    for rel, name in PRINTERS:
        fn = _body(rel, name)
        used = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        if "DOC_OWNERS" not in used:
            bad.append(f"  {rel}::{name} 가 `DOC_OWNERS` 를 안 든다")
        if hand_rolled(fn):
            bad.append(f"  {rel}::{name} 가 판별을 제 안에서 다시 짠다")
    assert not bad, "판별이 한 자리가 아니다:\n" + "\n".join(bad)


def test_that_guard_bites_a_hand_rolled_rule():
    """★ 카나리아 — 손으로 짠 판별을 넣으면 위 시험이 운다."""
    rolled = ast.parse("def f(b):\n    return isinstance(b[0].value, ast.Constant)\n").body[0]
    assert hand_rolled(rolled), "손으로 짠 판별인데 안 운다"
    assert not hand_rolled(_body(*PRINTERS[1])), "실물이 손으로 짠 것으로 세진다"


def test_neither_fingerprinter_swallows_unreadable_source():
    """안 읽히는 글에서 **둘 다** 터진다. 한쪽만 바이트로 해시하면 답이 갈린다."""
    bad = "def f(:\n"
    with pytest.raises(SyntaxError):
        G.logic_text(bad)
    with pytest.raises(SyntaxError):
        _dump(bad)


def test_the_shipped_function_matches_this_file_s_copy():
    """이 파일의 `_dump` 가 **실물과 같은 일**을 하는가. 아니면 위 전수가 헛것이다."""
    p = ROOT / "src" / "firelane" / "shardseal.py"
    from firelane.shardseal import _short
    assert logic_print(p) == _short(_dump(p.read_text(encoding="utf-8")))

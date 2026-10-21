"""시험의 단언이 **거짓이 될 수 있는가.**  (DECISIONS §541)

★ 2026-10-20 전수 정독이 `assert ... or True` 둘을 찾았다 — `or` 뒤의
  상수 참이 앞을 덮어 **그 단언은 거짓이 될 수 없다.** 하나는 도장 순서
  불변성이었고(`tests/test_docseal.py`), 그 시험 이름은 지금도 그것을
  잰다고 말한다. **이름이 지키는 척하는 것이 없는 것보다 나쁘다.**

★ 그래서 인스턴스를 고치는 대신 **족을 문다.** 같은 꼴은 급할 때 또
  생기고, 그때 이 그물이 울어야 한다. 사람이 두 번 찾지 않는다.

★ 문법 나무로 본다 — grep 이 아니다. 문자열·주석·독스트링 안의 같은
  글자에 걸리면 검사기가 제 어휘에 물려 첫 히트가 늘 자기 자신이 된다.

IN    tests/**/*.py
OUT   없음
밖    `src`·`tools` 의 `assert` 는 안 본다 — 그쪽은 단언이 계약 표명이고
      `-O` 로 지워지는 것이 다른 이야기다(PLAN 에 행이 따로 선다).
      `assert any(...)`·`assert len(x) >= 0` 같은 **뜻으로** 공허한 꼴도
      안 본다. 문법으로 판별되는 것만 문다 — 그물의 끝을 여기 적어둔다.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
SRC = ROOT / "src"
TOOLS = ROOT / "tools"


def _truthy(x: ast.expr) -> bool:
    """상수로 참이 확정되는가.

    ★ 다중 `isinstance` 를 안 쓴다 — ruff 가 `A | B | C` 를 요구하는 판이
      있고 그것은 판마다 다르다. `elts` 는 List·Tuple·Set 이 다 들고 있다.
    """
    if isinstance(x, ast.Constant):
        return bool(x.value)
    if isinstance(x, ast.Dict):
        return bool(x.keys)
    return bool(getattr(x, "elts", None))


def vacuous(src: str) -> list[tuple[int, str]]:
    """공허한 단언 — (줄, 사유). 이 함수가 이 시험의 정본이다."""
    out: list[tuple[int, str]] = []
    for n in ast.walk(ast.parse(src)):
        if not isinstance(n, ast.Assert):
            continue
        t = n.test
        if isinstance(t, ast.Tuple) and t.elts:
            out.append((n.lineno, "튜플 리터럴 — 늘 참이다 (쉼표가 오타다)"))
        elif _truthy(t):
            out.append((n.lineno, "상수가 참이다"))
        elif isinstance(t, ast.BoolOp) and isinstance(t.op, ast.Or):
            if any(_truthy(v) for v in t.values):
                out.append((n.lineno, "`or` 뒤 상수 참이 앞을 덮는다"))
        elif isinstance(t, ast.IfExp) and (_truthy(t.body) or _truthy(t.orelse)):
            out.append((n.lineno, "삼항의 한 가지가 상수 참이다"))
    return out


def test_no_assertion_in_the_repo_is_vacuously_true():
    """★ 저장소 전수(src · tools · tests). 면제 목록이 **없다** — 필요하면 DECISIONS 가 먼저 선다."""
    bad: list[str] = []
    seen = 0
    per: dict[str, int] = {}
    # ★ 2026-10-21 (1021). 종전에는 `TESTS` 하나만 훑으면서 docstring 이
    #   **「저장소 전수」**라고 적었다 — `deadcheck ⑤` 가 잡았다(189/439 ·
    #   `src`·`tools` 의 250개가 대상 밖). 이름이 하는 말과 코드가 하는 일이
    #   달랐고, 면제로 덮지 않고 **넓혔다**. 빈 단언은 `tools` 의 자기검사에도
    #   살고, 거기 있으면 「자기검사 69개 전부 초록」 중 하나가 아무것도 안 묻는다.
    # ★ 한 문장에 세 뿌리를 **폴더로** 적는다 — `deadcheck` 가 보는 것은 훑기
    #   호출의 수신자이고, 변수 하나로 돌면 프로브가 뿌리를 못 읽어 **조용히
    #   통과한다.** 넓히는 것과 프로브를 헷갈리게 하는 것은 다르다.
    files = [*SRC.rglob("*.py"), *TOOLS.rglob("*.py"), *TESTS.rglob("*.py")]
    for p in sorted(files):
        seen += 1
        per[p.relative_to(ROOT).parts[0]] = \
            per.get(p.relative_to(ROOT).parts[0], 0) + 1
        for line, why in vacuous(p.read_text(encoding="utf-8")):
            bad.append(f"{p.relative_to(ROOT)}:{line} — {why}")
    assert seen > 300, f"파일을 {seen}개만 읽었다 — 이 그물이 좁아졌다"
    # ★ 뿌리 셋이 **각각** 기여했는가. 수 하나만 보면 한 뿌리가 통째로 빠져도
    #   나머지가 그 수를 채운다 — 분모가 조용히 줄어드는 꼴이다(§443 의 「줄지
    #   않는 쪽이 줄 수 있는 쪽을 가린다」와 같은 자리).
    assert len(per) == 3 and all(per.values()), f"훑은 뿌리가 모자라다 — {per}"
    assert not bad, "거짓이 될 수 없는 단언:\n  " + "\n  ".join(bad)


def test_the_net_is_alive():
    """★ 카나리아 — 합성 입력으로 **양방향** 증명한다. 0건이 죽음이 아님."""
    assert vacuous("assert x == 1 or True\n"), "`or True` 를 안 문다"
    assert vacuous("assert True\n"), "`assert True` 를 안 문다"
    assert vacuous("assert 1\n"), "참 상수를 안 문다"
    assert vacuous("assert (a, b)\n"), "튜플 리터럴을 안 문다"
    assert vacuous("assert x if y else True\n"), "삼항을 안 문다"
    assert vacuous("assert x or [1]\n"), "참 리터럴을 안 문다"

    assert not vacuous("assert x == 1\n"), "멀쩡한 단언을 문다"
    assert not vacuous("assert a or b\n"), "두 쪽이 다 식인데 문다"
    assert not vacuous("assert x, 'or True'\n"), "메시지 글자에 걸린다"
    assert not vacuous("# assert x or True\n"), "주석에 걸린다"
    assert not vacuous('s = "assert x or True"\n'), "문자열에 걸린다"
    assert not vacuous("assert x or False\n"), "`or False` 는 공허하지 않다"
    assert not vacuous("assert not x\n"), "부정을 문다"

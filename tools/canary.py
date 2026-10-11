#!/usr/bin/env python3
"""
canary.py — 강제자가 제 판별식을 **합성 결함으로 밀어 봤는가.**

    uv run python tools/canary.py            판정 (verify.sh · CI)
    uv run python tools/canary.py --table    카나리아 없는 강제자 전부
    uv run python tools/canary.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 (2026-10-09 · DECISIONS §445 · PLAN #56 ① 닫힘) ───
이 저장소는 「카나리아를 같이 만든다」를 §159 부터 규약으로 적고 실제로 여러 번
만들었다(`test_plan_status_probe_is_alive` · `test_rules_table_probe_is_alive` ·
`test_code_change_alone_forces_full_run` · `test_that_guard_would_catch_the_old_text`).
**그런데 세는 자리가 없었다.** 새 강제자에 카나리아가 빠져도 아무도 안 울고,
그 강제자는 **실물에서만 초록인** 검사가 된다.

`#56 ①` 이 「판별식을 먼저 정해야 셀 수 있다. 정의 없이 세면 재현되지 않는
분모다」라고 적었다. 그 정의를 여기 둔다 —

    카나리아 = **같은 파일에서 같은 함수를 양쪽으로 미는 단정 쌍**
               `assert not f(…)`  (정상 입력에서 조용하다)
               `assert … f(…) …`  (합성 입력에서 운다)

이름(`*_is_alive` · `*_bites`)으로 세지 않는다 — 이름은 규약이 아니고, 낱말로
세면 ① 이 영영 0건이 되는 그 병에 걸린다(§444-1 과 같은 자리). **문법으로 센다.**

── 왜 `deadcheck` 의 프로브가 아닌가 ─────────────────────────
`#56 ①` 은 「`deadcheck` 가 래칫으로 센다」고 적었다. **그 자리에 못 둔다** —
`tests/test_deadcheck_probes.py::test_every_ceiling_is_zero` 가 「천장이 전부
0」을 단정하고 그 사유가 **「분류가 끝난 프로브를 0 보다 높은 래칫으로 두면
다시 들어와도 천장 안이라 안 운다 — 그 천장이 곧 미분류의 다른 이름이었다」**다.
카나리아 57 은 **분류가 끝나지 않은 빚**이라 그 불변식과 성질이 다르다.
행이 적은 자리와 저장소의 불변식이 부딪혔고 **불변식을 지켰다**(§445).

── 판정 (양방향) ──────────────────────────────────────────────
    카나리아 없는 강제자가 늘었다    실패 — 새 강제자가 그물 없이 들어왔다
    줄었다                           실패 — **`NO_CANARY` 를 그 수로 내려라**
    분모가 0 이다                    실패 — 수집기가 죽었다(빈 그물)

IN    tests/test_*.py · tools/*.py (이름)
OUT   표준출력 (판정)
PARAM NO_CANARY · EXEMPT
밖    **카나리아가 옳은가는 안 본다** — 합성 입력이 실물과 같은 꼴인지는 사람이
      본다(§436-6). 여기는 **쌍이 있는가**만 센다. **도구 쪽 자기검사는 안 센다**
      — 그쪽은 `mutate` 가 흔들어서 잰다.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 경로로 도구를 집는 꼴. `importlib` 로 여는 시험이 이 꼴을 쓴다.
_BYPATH = (re.compile(r'tools/([\w]+)\.py'),
           re.compile(r'"tools"\s*/\s*"([\w]+)\.py"'))


def tool_names(root: Path = ROOT) -> set[str]:
    return {p.stem for p in (root / "tools").rglob("*.py")
            if "__pycache__" not in p.parts}


def _called(node: ast.AST) -> set[str]:
    """그 식 안에서 **불린 이름** 전부. `a.b(…)` 는 `b` 로 센다."""
    out: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name):
            out.add(f.id)
        elif isinstance(f, ast.Attribute):
            out.add(f.attr)
    return out


def touches(src: str, tree: ast.AST, tools: set[str]) -> set[str]:
    """그 시험이 미는 **도구 이름.** import 와 경로 둘 다 본다."""
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
        elif isinstance(n, ast.Import):
            mods.update(a.name.split(".")[0] for a in n.names)
    for rx in _BYPATH:
        mods |= set(rx.findall(src))
    return mods & tools


def pairs(tree: ast.AST) -> tuple[set[str], set[str]]:
    """(**음성**으로 민 이름, **양성**으로 민 이름).

    ★ 음성 = `assert not f(…)` — 「정상 입력에서 조용하다」.
      양성 = 그 밖의 단정 안에서 불린 것 — `assert f(…)` · `assert len(f(…)) == 1` ·
      `assert any("x" in b for b in f(…))`. **식 전체를 훑는다**: 양성 쪽을
      `assert f(…)` 꼴로만 좁히면 실측에서 넷이 빠졌다(세는 꼴이 실물과 달라지면
      그 검사는 제 그물이 아니라 내 손을 잰다 · §436-6).
    """
    neg: set[str] = set()
    pos: set[str] = set()
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assert):
            continue
        t = n.test
        if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
            neg |= _called(t.operand)
        else:
            pos |= _called(t)
    return neg, pos


def has_canary(tree: ast.AST) -> bool:
    neg, pos = pairs(tree)
    return bool(neg & pos)


def findings(root: Path = ROOT) -> list[tuple[Path, int, str, str]]:
    """(파일, 줄, 이름, 무엇이 없나). **판정은 안 한다.**"""
    tools = tool_names(root)
    out: list[tuple[Path, int, str, str]] = []
    for p in sorted((root / "tests").rglob("test_*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        hit = touches(src, tree, tools)
        if not hit or has_canary(tree):
            continue
        out.append((p, 1, p.stem,
                    f"{', '.join(sorted(hit)[:3])} 를 미는데 **합성 결함을 넣어"
                    " 우는 것을 본 자리가 없다** — 같은 판별식을 "
                    "`assert not f(…)` 와 `assert … f(…)` 둘로 밀어라"))
    return out


def denominator(root: Path = ROOT) -> int:
    """도구를 미는 시험 수. **분모를 세는 자리도 하나여야 한다.**"""
    tools = tool_names(root)
    n = 0
    for p in sorted((root / "tests").rglob("test_*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        if touches(src, tree, tools):
            n += 1
    return n


#: 카나리아를 **못 만드는** 강제자. `"파일::이름"` → 사유.
#: ★ 비었다. 오늘 57 은 면제가 아니라 **빚**이고 그것은 아래 래칫이 든다.
#:   면제가 생기면 사유와 함께 여기 한 줄이다(§69).
EXEMPT: dict[str, str] = {}

#: 카나리아 없는 강제자 수. **내려가는 쪽.** 2026-10-09 실측 57 / 분모 98.
NO_CANARY = 56

RATCHETS = {"NO_CANARY": "down"}


def ratchet_values() -> dict[str, int]:
    """지금 수. **재기만 한다** — 판정은 `faults()` 가 든다."""
    return {"NO_CANARY": len(rows())}


def rows(root: Path = ROOT) -> list[tuple[Path, str]]:
    """(파일, 무엇이 없나). 면제를 뺀 뒤의 목록이다."""
    out = []
    for p, _ln, name, what in findings(root):
        rel = p.relative_to(root).as_posix()
        if f"{rel}::{name}" in EXEMPT:
            continue
        out.append((p, what))
    return out


def faults(n: int, limit: int = NO_CANARY, denom: int = 1) -> list[str]:
    """양방향 래칫 + 빈 그물. **순수 함수**다."""
    if denom <= 0:
        return ["분모가 0 이다 — 도구를 미는 시험을 하나도 못 찾았다. 수집기가 죽었다"]
    if n > limit:
        return [f"카나리아 없는 강제자 {n} > 기록 {limit} — 새 강제자가 "
                "**합성 결함을 넣어 우는 것을 본 자리** 없이 들어왔다"]
    if n < limit:
        return [f"카나리아 없는 강제자 {n} 으로 줄었다 — "
                f"tools/canary.py 의 `NO_CANARY` 를 {n} 으로 내려라"]
    return []


def selftest() -> int:
    bad: list[str] = []
    import ast as _a
    # ★ 쌍을 가르는가 — 양방향
    pair = _a.parse("def t():\n    assert not f(1)\ndef c():\n    assert f(2)\n")
    one = _a.parse("def t():\n    assert not f(1)\n")
    if not has_canary(pair):
        bad.append("양방향 쌍을 못 본다")
    if has_canary(one):
        bad.append("음성만 있는데 카나리아로 센다")
    # ★ 식 안쪽까지 훑는가 — `assert len(f(…)) == 1` 꼴이 실물의 과반이다
    deep = _a.parse("def t():\n    assert not f(1)\ndef c():\n    assert len(f(2)) == 1\n")
    if not has_canary(deep):
        bad.append("단정 식 안쪽의 호출을 못 본다")
    # ★ 분모 — 도구를 미는 시험만
    tools = tool_names()
    if not tools:
        bad.append("도구 이름을 0개 셌다")
    if touches("import json", _a.parse("import json"), tools):
        bad.append("표준 꾸러미를 도구로 센다")
    if not touches('p = ROOT / "tools" / "golden.py"',
                   _a.parse('p = 1'), tools):
        bad.append("경로로 집는 꼴을 못 본다")
    # ★ 판정 — 양방향 · 빈 그물
    if not faults(NO_CANARY + 1, denom=98):
        bad.append("늘었는데 안 운다")
    if not faults(NO_CANARY - 1, denom=98):
        bad.append("줄었는데 안 운다 — 느슨한 래칫은 지난 기록이다")
    if faults(NO_CANARY, denom=98):
        bad.append("기록과 같은데 운다")
    if not faults(0, limit=0, denom=0):
        bad.append("분모 0 에서 통과한다 — 빈 그물")
    if denominator() <= 0:
        bad.append("실물에서 분모를 0 으로 셌다")

    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 쌍 가름 · 식 안쪽 · 분모 · 양방향 · 빈 그물")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="강제자의 카나리아 래칫")
    ap.add_argument("--table", action="store_true", help="카나리아 없는 강제자 전부")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    got = rows()
    denom = denominator()
    if a.table:
        for p, what in got:
            print(f"  {p.relative_to(ROOT).as_posix():<46} {what[:60]}")
    bad = faults(len(got), denom=denom)
    if bad:
        print(f"✗ 카나리아 {len(bad)}건")
        for b in bad:
            print(f"    {b}")
        print("  정의 — 같은 파일에서 같은 함수를 `assert not f(…)` 와 "
              "`assert … f(…)` 둘로 민다. 이름으로 세지 않는다(§445).")
        return 1
    print(f"✓ 카나리아 — 도구를 미는 시험 {denom} · 없음 {len(got)} = 래칫 {NO_CANARY}"
          f" · 면제 {len(EXEMPT)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

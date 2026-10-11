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
from pathlib import Path

# ★ 2026-10-12 (DECISIONS §489). 꼴 판별은 `canaryshape.py` 가 든다 —
#   다섯 판(§480 · §485 · §486 · §487 · §489)이 전부 그쪽을 키웠고,
#   이쪽은 §445 이후 안 움직였다. 「무엇이 쌍인가」와 「쌍이 몇인가」를 가른다.
import canaryshape
from canaryshape import (  # noqa: F401 — `pairs` · `code_only` 는 시험이 끌어 쓴다
    code_only,
    has_canary,
    judge_names,
    pairs,
    tool_names,
    touches,
)

ROOT = Path(__file__).resolve().parents[1]

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
        if not hit or has_canary(tree, judge_names(src, tree, hit, root)):
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
#: ★ 비었다. 오늘 29 은 면제가 아니라 **빚**이고 그것은 아래 래칫이 든다.
#:   면제가 생기면 사유와 함께 여기 한 줄이다(§69).
EXEMPT: dict[str, str] = {}

#: 카나리아 없는 강제자 수. **내려가는 쪽.** 분모는 「도구를 미는 시험」이다.
#
#: ★ **이력은 수와 사유 한 줄씩**만 둔다 — 긴 사유는 그 판의 DECISIONS 절에
#:   있고, 두 벌로 적으면 갈린다. 네 판이 **코드를 거의 안 고치고** 이 수를
#:   움직였다: 세는 꼴이 실물과 달랐던 것이고, 그 네 번이 다른 자리였다.
#
#:     §445    22 → 23   `canary.NO_CANARY` 자체가 래칫에 들어왔다
#:     §480    56 → 30   음성 쪽 **두 줄 꼴**(`bad = f(x)` · `assert not bad`)
#:     §480-1  30 → 29   `colorsim.faults()` 를 빼서 갚았다
#:     §485    29 → 16   **내장 제외**(거짓 초록 다섯) · **분류기 꼴**(열하나) ·
#:                       **`== []` 꼴**(일곱). 하나는 부풀리고 둘은 깎았다
#:     §486    16 → 25   **표준 라이브러리 이름**으로 센 쌍 아홉을 걷었다 —
#:                       쌍을 **이름의 출처**로 거른다(`judge_names`)
#:     §486    25 → 24   `test_commit_policy`(`check_paths`) ·
#:                       `test_cost_inputs`(`judge`) 둘을 갚았다
#:     §487    24 → 17   분모 112 → 101. 경로를 **코드에서만** 찾는다 —
#:                       머리말에 이름만 적은 열하나가 분모에 있었다
#:     §487    17 → 16   `test_nfa_compare`(`constbasis.scan` · `ungrounded`)
#:     §488    16 → 14   `test_selftests_are_run`(두 판정을 합성 파일로) ·
#:                       `test_fieldseal`(`diff` 를 네 갈래로)
#:     §489    14 → 11   **짝 묶음**(`bad, none = judge(…)`)을 보게 했다 —
#:                       판정이 짝을 내는 꼴 셋이 안 보였다. 그리고
#:                       `test_toolclass` 가 `judge` 의 **일곱 갈래**를 민다
#:     §490    11 → 9    `test_tile_zoom_agreement`(머케이터 식 둘을 교차) ·
#:                       `test_declaration_reality`(`treecheck.check_names` —
#:                       **저장소 어디에도 미는 자리가 없던** 네 갈래)
#:     §491    9 → 7     `test_delivery_is_read`(`notice` · `drift` ·
#:                       `closure_target` — §292 의 판정↔통보 가름) ·
#:                       `test_defect_evidence`(증표 해석자를 빼서 양방향)
#
#: ★ 남은 7 은 빚이다. 올라간 판(§486)은 **느슨해진 것이 아니라** 거짓 초록을
#:   걷은 것이고, 그 둘을 가르는 것이 래칫에 사유를 요구하는 이유다.
NO_CANARY = 7

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
    # ★ 2026-10-12 (§480). **두 줄 꼴**을 보는가 — 양방향
    two = _a.parse("def t():\n    bad = f(1)\n    assert not bad\n"
                   "def c():\n    assert f(2)\n")
    if not has_canary(two):
        bad.append("`bad = f(…)` 뒤의 `assert not bad` 를 못 본다")
    two_one = _a.parse("def t():\n    bad = f(1)\n    assert not bad\n")
    if has_canary(two_one):
        bad.append("두 줄 꼴 음성만 있는데 카나리아로 센다")
    # ★ 묶음이 **함수**다 — 다른 함수의 이름을 끌어오면 안 된다
    cross = _a.parse("def t():\n    bad = f(1)\n"
                     "def u():\n    assert not bad\n"
                     "def c():\n    assert f(2)\n")
    if has_canary(cross):
        bad.append("다른 함수에 묶인 이름을 제 증거로 센다")

    # ★ 분모 — 도구를 미는 시험만
    tools = tool_names()
    if not tools:
        bad.append("도구 이름을 0개 셌다")
    if touches("import json", _a.parse("import json"), tools):
        bad.append("표준 꾸러미를 도구로 센다")
    if not touches('p = ROOT / "tools" / "golden.py"',
                   _a.parse('p = 1'), tools):
        bad.append("경로로 집는 꼴을 못 본다")
    # ★ 2026-10-12 (DECISIONS §485) — **내장 함수로는 쌍이 안 된다**
    #   ★ 안쪽 이름을 **다르게** 둔다 — 같으면 그 이름으로 쌍이 성립하고
    #     그것은 옳은 쌍이다. 거짓 쌍은 **공유하는 것이 내장뿐**일 때 생긴다.
    blt = _a.parse('def t():\n    assert not len(f(1))\n'
                   'def c():\n    assert len(g(2)) == 3\n')
    if has_canary(blt):
        bad.append("`len` 하나로 쌍을 세운다 — 다섯 시험이 그렇게 거짓으로 초록이었다")
    # ★ 그런데 **그 안의 진짜 이름**은 세어야 한다 — 내장만 빼는 것이다
    inner = _a.parse('def t():\n    assert not len(f(1))\n'
                     'def c():\n    assert f(2) == 3\n'
                     'def d():\n    assert f(3) == 4\n')
    if not has_canary(inner):
        bad.append("내장을 빼면서 안쪽 이름까지 버렸다")

    # ★ **분류기 꼴** — 같은 자를 서로 다른 낱말 둘과 댄 것
    cls2 = _a.parse('def t():\n    assert g(1) == "a"\n'
                    'def c():\n    assert g(2) == "b"\n')
    if not has_canary(cls2):
        bad.append("분류기를 낱말 둘로 밀었는데 안 센다 — 열한 시험이 그렇게 깎였다")
    cls1 = _a.parse('def t():\n    assert g(1) == "a"\n'
                    'def c():\n    assert g(2) == "a"\n')
    if has_canary(cls1):
        bad.append("같은 낱말만 둘인데 양방향으로 센다 — 한 갈래만 민 것이다")
    if has_canary(_a.parse('def t():\n    assert g(1) == "a"\n')):
        bad.append("낱말 하나로 양방향을 센다")

    # ★ 2026-10-12 (§485) — **「조용하다」 꼴**과 그 자기쌍 방어
    sil = _a.parse('def t():\n    assert f(1) == []\n'
                   'def c():\n    assert f(2)\n')
    if not has_canary(sil):
        bad.append("`assert f(…) == []` 을 음성으로 안 센다 — 목록을 내는 판정이"
                   " 그렇게 적을 수밖에 없다(일곱 시험이 그 꼴이었다)")
    alone = _a.parse('def t():\n    assert f(1) == []\n')
    if has_canary(alone):
        bad.append("`assert f(…) == []` **한 줄이 혼자 쌍을 이룬다** — 같은 단정을"
                   " 음성과 양성에 둘 다 넣으면 그 줄 하나로 초록이 된다")
    chain = _a.parse('def t():\n    assert g(1) == "a" == "b"\n')
    if has_canary(chain):
        bad.append("한 단정 안의 사슬을 두 자리로 센다 — 한 자리에서 민 것이다")

    # ★ 2026-10-12 (§486) — **판정 이름 안에서만** 센다
    lib = _a.parse('def t():\n    assert not p.read_text()\n'
                   'def c():\n    assert q.read_text()\n')
    if has_canary(lib, allowed={"판정"}):
        bad.append("표준 라이브러리 이름으로 쌍을 세운다 — 아홉 시험이 그렇게"
                   " 거짓으로 초록이었다")
    if not has_canary(lib):
        bad.append("허용 집합을 안 주면 거르지 말아야 한다 — 합성 판별식이 죽는다")
    mine = _a.parse('def 판정(x):\n    return []\n'
                    'def t():\n    assert not 판정(1)\n'
                    'def c():\n    assert 판정(2)\n')
    if not has_canary(mine, allowed=canaryshape._defs(mine)):
        bad.append("그 파일이 정의한 판정으로 민 쌍을 안 센다")
    # ★ 허용 집합이 **어디서 오는가** — 미는 도구의 함수가 들어야 한다
    nm = judge_names("import canaryshape", _a.parse("import canaryshape"),
                     {"canaryshape"})
    if "has_canary" not in nm or "judge_names" not in nm:
        bad.append("미는 도구의 함수 이름을 허용 집합에 안 넣는다")
    if judge_names("", _a.parse(""), {"없는도구"}):
        bad.append("없는 도구에서 이름을 만든다")

    # ★ 2026-10-12 (§487) — **머리말의 이름은 푸시가 아니다**
    names = {"golden", "verify"}
    doc = '"""`tools/golden.py` 가 든다."""\nimport json\n'
    if touches(doc, _a.parse(doc), names):
        bad.append("문서열에 적힌 도구 이름을 푸시로 센다 — 실측 112 중 열하나가"
                   " 그 꼴이었다(§481 의 그 걱정이 참이었다)")
    cmt = "# tools/golden.py 를 쓸 수도 있다\nimport json\n"
    if touches(cmt, _a.parse(cmt), names):
        bad.append("주석에 적힌 도구 이름을 푸시로 센다")
    real = 'p = ROOT / "tools" / "golden.py"\n'
    if not touches(real, _a.parse(real), names):
        bad.append("코드의 경로를 푸시로 안 센다 — 분모가 비어 간다")
    if code_only("x = 1  # tools/verify.sh") != code_only("x = 1"):
        bad.append("주석을 떼면서 코드를 건드린다")

    # ★ 2026-10-12 (§489) — **짝으로 받는 꼴**
    tup = _a.parse('def t():\n    bad, none = j(1)\n    assert not bad\n'
                   'def c():\n    bad, none = j(2)\n    assert none\n')
    if not has_canary(tup):
        bad.append("`bad, none = j(…)` 짝 묶음을 안 본다 — 판정이 짝을 내는"
                   " 꼴이 실물에 셋 있었다")
    # ★ 묶음은 여전히 **함수 안**이다 — 다른 함수의 짝을 제 증거로 안 센다
    far = _a.parse('def t():\n    bad, none = j(1)\n'
                   'def c():\n    assert not bad\n')
    if has_canary(far):
        bad.append("다른 함수의 짝 묶음을 제 증거로 센다")

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
    print(f"{'✗' if bad else '✓'} 자기검사 — 쌍 가름 · 식 안쪽 · **두 줄 꼴** · 함수 경계 · **내장 제외** · **분류기 꼴** · 분모 · 양방향 · 빈 그물")
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

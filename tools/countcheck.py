#!/usr/bin/env python3
"""
countcheck.py — 문서가 **시험 수를 손으로 적은 자리.** (DECISIONS §366-4)

    uv run python tools/countcheck.py           센다
    uv run python tools/countcheck.py --fix     수만 뺀다 (꾸밈말은 남긴다)
    uv run python tools/countcheck.py --selftest

── 무엇이 결함인가 ──────────────────────────────────────────────
강제자 칸이 시험 파일을 지목할 때 괄호에 **수를 적는 자리**다 —

    `tests/test_docseal.py`(19)            ← 결함
    `web/navi/test/track.test.ts`(17)      ← 결함
    `tests/test_docseal_view.py`(15 — 양방향)  ← 수만 결함. 꾸밈말은 정보다

★ **낡아서 결함이 아니다. 낡았는지 알 수 없어서 결함이다.** 실측하면 그 수가
  무엇을 센 것인지 자리마다 다르다 — 어떤 것은 그 파일의 `def test_` 전수이고,
  어떤 것은 **그 배치가 더한 수**다(`test_batch_tools.py`(2) · (4) · (6) 셋이
  같은 파일을 가리키고 실측 전수는 40 이다). 세는 기준이 없으면 사람도 기계도
  대조할 수 없고, 대조할 수 없는 수는 **영원히 참으로 보인다.**

★ §246-2 가 이미 규칙을 적었다 — **정본이 없는 값은 문서에 적지 않는다.**
  §364-2 가 그 규칙으로 여섯 자리를 뺐고, **그 밤에 §363 이 새로 셋을 적었다.**
  규칙만 있고 세는 자리가 없으면 배치마다 샌다. 그래서 이 도구가 생겼다.

── 무엇은 결함이 아닌가 (범위) ─────────────────────────────────
    `tools/sizecheck.py`(646)        **정본이 있다** — `EXCEPTIONS` 의 값이다
    `tests/test_lake.py`(상한 0)      이름이 붙은 값. 그 상수가 정본이다
    `web/navi/test/progress.test.ts`(안내 문턱 12·6·2.5초)
                                     임계값이다. `domain` 상수가 정본이다
    (2026-08-24 신설, 3종)           날짜다
그래서 그물을 **시험 파일 + 수뿐인 괄호**로 좁혔다. 도구 파일의 수는 대개
선언된 상수라 안 본다 — 넓히면 오탐이 나고, **시끄러운 검사는 꺼진다**(§78-4).

RATCHETS  COUNTS — 내려가는 쪽으로만

IN    docs/DECISIONS.md · docs/MASTER.md · docs/PLAN.md · README.md
OUT   없다 (검사) · `--fix` 는 위 넷을 제자리에서 고친다
밖    **시험이 몇 개여야 하는가는 안 본다.** 수를 적지 말라고만 한다.
      도구 파일의 괄호 안 수도 안 본다 — 그쪽은 대개 정본이 있다(위 범위).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ("docs/DECISIONS.md", "docs/MASTER.md", "docs/PLAN.md", "README.md")

#: 실측 0. **내려가는 쪽으로만.**
COUNTS = 0
RATCHETS = {"COUNTS": "down"}

#: 시험 파일 지목 뒤의 **수뿐인** 괄호. 꾸밈말이 뒤에 붙는 꼴까지 본다.
#:   ★ 수를 세 자리까지만 본다 — 네 자리는 **연도**다(`(2026-08-24 신설)`).
#:   ★ `판별식 9` 처럼 앞에 낱말이 붙어도 그것은 수를 세는 말이라 본다.
PAT = re.compile(
    r"`(?P<f>(?:tests/test_[\w/]+\.py|web/navi/test/[\w./]+\.test\.ts)(?:::\w+)?)`"
    r"(?P<open>\s*[(（]\s*)(?:(?P<word>판별식|건|개)\s*)?(?P<n>\d{1,3})"
    r"(?P<unit>\s*(?:건|개|판별식))?(?P<tail>\s*(?:[)）]|·|—|-))(?P<pad>\s*)")


def findings(docs: tuple[str, ...] = DOCS) -> list[tuple[str, int, str, int, str]]:
    """(파일, 줄, 지목한 시험, 적힌 수, 그 줄)."""
    out = []
    for rel in docs:
        p = ROOT / rel
        if not p.is_file():
            continue
        for n, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in PAT.finditer(ln):
                out.append((rel, n, m.group("f"), int(m.group("n")), ln.strip()))
    return out


def _strip(ln: str) -> str:
    """한 줄에서 **수만** 뺀다. 꾸밈말과 괄호 구조는 살린다.

    ★ 괄호째 지우지 않는다. `(15 — 양방향)` 의 「양방향」은 **정보**이고,
      지우면 그 절이 무엇을 무는지가 사라진다. 수가 빠져 괄호가 비면 그때만
      괄호를 지운다.
    """
    def rep(m: re.Match) -> str:
        closing = m.group("tail").strip() in (")", "）")
        if closing:
            # 괄호가 비었다 — 통째로 뺀다. 뒤 공백은 그 줄의 것이라 살린다
            return "`" + m.group("f") + "`" + m.group("pad")
        # 꾸밈말이 뒤에 있다 — 여는 괄호를 살리고 **수 · 구분자 · 그 뒤 공백**을
        # 뺀다. 공백을 남기면 `( 양방향)` 이 되고 그 꼴을 `docstyle` 이 다시 운다.
        return "`" + m.group("f") + "`" + m.group("open").rstrip()
    return PAT.sub(rep, ln)


def fix(docs: tuple[str, ...] = DOCS) -> int:
    n = 0
    for rel in docs:
        p = ROOT / rel
        if not p.is_file():
            continue
        src = p.read_text(encoding="utf-8")
        lines = src.splitlines(keepends=True)
        for i, ln in enumerate(lines):
            body = ln.rstrip("\n")
            new = _strip(body)
            if new != body:
                n += PAT.subn(lambda _m: "", body)[1]
                lines[i] = new + ("\n" if ln.endswith("\n") else "")
        out = "".join(lines)
        if out != src:
            p.write_text(out, encoding="utf-8")
    return n


def ratchet_values() -> dict[str, int]:
    return {"COUNTS": len(findings())}


def selftest() -> int:
    """★ 양성 **과** 음성. 둘 다 없으면 「늘 0」과 「늘 전부」를 못 가른다."""
    bad = []
    hit = [
        "강제자  `tests/test_x.py`(19)",
        "강제자  `web/navi/test/a.test.ts`(17)",
        "강제자  `tests/test_y.py`(15 — 양방향)",
        "강제자  `web/navi/test/b.test.ts`(판별식 9 — 두 자리)",
        "강제자  `tests/test_z.py`(12건 · 시계 다섯)",
    ]
    for ln in hit:
        if not PAT.search(ln):
            bad.append(f"못 잡았다: {ln}")
    miss = [
        "강제자  `tools/sizecheck.py`(646)",                   # 도구 · 정본 있다
        "강제자  `tests/test_lake.py`(상한 0)",                 # 이름 붙은 값
        "강제자  `tests/test_ci_env.py` (2026-08-24 신설, 3종)",  # 연도
        "강제자  `web/navi/test/p.test.ts`(안내 문턱 12·6·2.5초)",  # 임계값
        "강제자  `tests/test_a.py`(반대 방향까지)",              # 수가 없다
        "강제자  `tests/test_b.py::test_one` · `tests/test_c.py`",  # 괄호가 없다
    ]
    for ln in miss:
        if PAT.search(ln):
            bad.append(f"잘못 잡았다: {ln}")

    # ── 고치기 — **꾸밈말을 살리는가** ─────────────────────────
    pairs = [
        ("`tests/test_x.py`(19)", "`tests/test_x.py`"),
        ("`tests/test_y.py`(15 — 양방향)", "`tests/test_y.py`(양방향)"),
        ("`web/navi/test/b.test.ts`(판별식 9 — 두 자리)",
         "`web/navi/test/b.test.ts`(두 자리)"),
        ("`tests/test_z.py`(12건 · 시계 다섯)", "`tests/test_z.py`(시계 다섯)"),
        ("`tools/sizecheck.py`(646)", "`tools/sizecheck.py`(646)"),   # 안 건드린다
    ]
    for src, want in pairs:
        got = re.sub(r"\s+", " ", _strip(src)).strip()
        if got != want:
            bad.append(f"고치기가 어긋났다: {src!r} → {got!r} (기대 {want!r})")

    # ★ 그물이 비면 이 검사는 언제나 초록이다 — 합성 문서로 생사를 본다.
    if len(PAT.findall("`tests/test_q.py`(3) `tests/test_r.py`(4)")) != 2:
        bad.append("한 줄의 둘을 하나로 셌다")

    for b in bad:
        print(f"  ✗ {b}")
    print(f"{'✗' if bad else '✓'} 자기검사 판별식 {len(hit) + len(miss) + len(pairs) + 1}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="수만 뺀다")
    ap.add_argument("--ratchet", action="store_true", help="래칫 값만 찍는다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if a.fix:
        n = fix()
        print(f"손으로 적은 시험 수 {n}곳에서 수를 뺐다" if n else "뺄 것이 없다")
        return 0
    got = findings()
    if a.ratchet:
        print(f"COUNTS {len(got)}")
        return 0
    if not got:
        print(f"✓ 문서가 손으로 적은 시험 수 0 · 래칫 {COUNTS}")
        return 0
    print(f"✗ 문서가 **손으로 적은 시험 수** {len(got)}곳\n")
    for rel, n, f, said, ln in got:
        print(f"  {rel}:{n}  `{f}`({said})")
        print(f"      {ln[:88]}")
    print("")
    print("  ★ 낡아서가 아니라 **낡았는지 알 수 없어서** 결함이다 — 어떤 자리는")
    print("    그 파일 전수이고 어떤 자리는 **그 배치가 더한 수**다. 기준이 없으면")
    print("    대조할 수 없고, 대조할 수 없는 수는 영원히 참으로 보인다(§246-2).")
    print("  고침 — uv run python tools/countcheck.py --fix   (수만 빠지고 꾸밈말은 남는다)")
    return 1


if __name__ == "__main__":
    sys.exit(main())

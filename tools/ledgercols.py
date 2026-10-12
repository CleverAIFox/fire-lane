#!/usr/bin/env python3
"""
ledgercols.py — **대장의 어느 칸을 누가 읽는가.** 읽는 자가 0인 칸을 센다.

    uv run python tools/ledgercols.py            판정 (verify.sh · CI)
    uv run python tools/ledgercols.py --table    칸마다 읽는 자를 표로
    uv run python tools/ledgercols.py --selftest ★ 판별식이 살아 있나

── 왜 생겼나 (2026-10-09 · DECISIONS §444 · PLAN #134 ㉠) ──────
`sources.yaml` 은 칸이 **쉰** 이고, 프로브 여덟(`lakecheck L1~L6` · `triage` ·
`intake` · `ledger_stem` …)이 **각자** 그 칸을 읽는다. 그런데 **어느 프로브가
어느 칸을 읽는지 아무도 대조하지 않았다.** `#134` 가 적은 닫는 법이 그것이다 —
「선언 칸 목록을 한 곳에 두고 『이 프로브가 어느 칸을 읽는가』를 선언으로」.

★ **선언하는 쪽을 뒤집었다.** 「누가 무엇을 읽는가」를 손으로 적으면 그 목록이
  곧 낡는다(이 저장소가 세 번 배운 것 — §285-2 · §284-4 · §286). 읽는 쪽은
  **코드에서 도출**하고, 손으로 적는 것은 **「기계가 안 읽는 칸」**뿐이다.
  그쪽은 수가 적고(아홉) 줄어드는 쪽이라 래칫이 걸린다.

── 두 축 ───────────────────────────────────────────────────────
① 읽는 자 0 인데 `PROSE` 에 없다   새 칸이 조용히 들어왔거나 독자가 죽었다
② `PROSE` 인데 기계가 읽는다        선언이 낡았다 — 지워라
③ `PROSE` 인데 대장에 그 칸이 없다  칸이 사라졌다 — 선언도 지워라

★ ②③ 이 **양방향**이다. ① 만 있으면 선언을 늘려 통과시키는 길이 열리고,
  그 순간 이 도구는 「선언한 만큼 초록」이 된다.

── 어떻게 도출하나 ─────────────────────────────────────────────
`src/firelane` · `tools` · `tests` 의 `.py` 를 **AST 로** 훑어
`X.get("칸")` · `X["칸"]` 꼴의 **문자열 리터럴**만 집는다. 주석·문서·로그
문자열은 안 센다 — 글자만 훑으면 `note` 같은 흔한 낱말이 어디서나 걸려
**읽는 자 0 인 칸이 영원히 0건**이 되고, 그러면 ① 이 죽은 그물이 된다.

★ 과소 계산이 있다 — `e[k]` 처럼 **변수로 접근**하는 자리는 못 본다. 그쪽은
  칸 이름이 코드에 없으므로 「어느 칸을 읽는가」를 애초에 말할 수 없다.
  못 보는 것을 **본 척하지 않는다.**

IN    sources.yaml · src/firelane/**.py · tools/**.py · tests/**.py
OUT   표준출력 (판정)
PARAM PROSE (래칫 · 내려가는 쪽으로만)
밖    **칸이 옳은가는 안 본다.** 값의 뜻은 `tools/ledger_fields.py` 와
      `MASTER §11` 이 든다. 여기는 **읽는 자가 있는가** 하나다.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 칸이 사는 블록. `sources.yaml` 의 최상위 넷이다.
BLOCKS = ("datasets", "retired", "outputs", "raw_only")

#: 칸 이름이 코드에 나올 수 있는 자리.
SCAN = ("src/firelane", "tools", "tests")

#: **기계가 안 읽는 칸과 그 사유.** 사람이 읽는 자리다.
#: ★ 사유 없이 넣지 마라 — 사유 없는 면제는 그물을 비운다(§69).
#: ★ **내려가는 쪽으로만**(래칫). 칸이 기계에 물리거나 지워지면 줄어든다.
#:   늘리려면 「왜 기계가 못 읽는가」를 여기 적어야 한다.
PROSE: dict[str, str] = {
    "absent": "「이 칸이 원본에 없다」를 열별로 적은 표. 어느 열이 어디에 있고 없는지는\n"
              "            사람이 재취득을 판단하는 근거다 — 기계가 쓸 판정이 아직 없다",
    "known_issues": "그 산출물이 **아는 흠**의 목록. 문장이라 기계가 못 센다 —\n"
                    "            세려면 흠마다 PLAN 행이 되어야 하고 그것이 올바른 길이다",
    "notified": "제공기관에 오류를 알린 날. 회신이 오면 사람이 지운다",
    "read_note": "그 자산을 **어떻게 읽어야 하는가**의 산문. 읽는 코드가 이미\n"
                 "            그렇게 짜여 있고 이 칸은 왜 그런지를 남긴다",
    "restored": "폐기에서 되살린 날과 사유. `retired` 에 남은 흔적이고\n"
                "            되살아난 항목은 `datasets` 에 제 줄이 있다",
    "successor": "그 자산을 대신하는 항목의 이름. 사람이 「어디로 갔나」를 찾는 자리다",
    "survey_year": "조사 연도. 자료의 나이를 사람이 읽는다 — `updated` 와 다르다\n"
                   "            (받은 날이 아니라 **조사한 해**다)",
    "used_for": "그 표를 **무엇에 썼나**의 산문. 배선(`feeds`)과 다르다 —\n"
                "            feeds 는 기계가 읽고 이쪽은 한 번 쓰고 끝난 조사를 적는다",
    "what_fix": "`what` 을 **왜 고쳤나**. 정정의 기록이라 값이 아니다",
}


def columns() -> dict[str, int]:
    """칸 → 그 칸을 가진 항목 수. **대장에서 도출한다.**"""
    from firelane import ledger
    y = ledger.load()
    out: dict[str, int] = {}
    for blk in BLOCKS:
        for e in (y.get(blk) or {}).values():
            for c in (e or {}):
                out[c] = out.get(c, 0) + 1
    return out


def reads(src: str, known: set[str]) -> set[str]:
    """그 소스가 **이름으로 집는** 칸. `X.get("c")` · `X["c"]` 만."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    got: set[str] = set()
    for n in ast.walk(tree):
        lit = None
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get" and n.args
                and isinstance(n.args[0], ast.Constant)):
            lit = n.args[0].value
        elif isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant):
            lit = n.slice.value
        if isinstance(lit, str) and lit in known:
            got.add(lit)
    return got


def readers(known: set[str], root: Path = ROOT) -> dict[str, set[str]]:
    """칸 → 그 칸을 읽는 파일들."""
    out: dict[str, set[str]] = {}
    for d in SCAN:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            for c in reads(p.read_text(encoding="utf-8", errors="replace"), known):
                out.setdefault(c, set()).add(p.relative_to(root).as_posix())
    return out


def faults(cols: dict[str, int], who: dict[str, set[str]],
           prose: dict[str, str] | None = None) -> list[str]:
    """세 축. **순수 함수** — 시험이 합성 선언까지 넣어 부른다.

    ★ `prose` 를 인자로 받는 이유 — 합성 입력으로 밀 때 실물 선언 아홉이
      같이 끌려오면 축 ③ 이 아홉 번 울어서 **다른 축을 못 민다.** 판별식의
      입력은 전부 인자여야 한다(§443-6 과 같은 규율).
    """
    prose = PROSE if prose is None else prose
    bad = []
    if not cols:
        return ["대장에서 칸을 하나도 못 읽었다 — 빈 그물이다"]
    for c in sorted(cols):
        if who.get(c) or c in prose:
            continue
        bad.append(f"① `{c}` ({cols[c]}개 항목) — 읽는 자가 없는데 `PROSE` 에도 없다.\n"
                   f"       기계에 물리거나, **왜 사람만 읽는지**를 `PROSE` 에 적어라")
    for c in sorted(prose):
        if c not in cols:
            bad.append(f"③ `{c}` — `PROSE` 인데 대장에 그 칸이 없다. 선언을 지워라")
        elif who.get(c):
            bad.append(f"② `{c}` — `PROSE` 인데 {sorted(who[c])[0]} 가 읽는다. "
                       "선언이 낡았다 — 지워라")
    return bad


#: 사람만 읽는 칸의 **수**. 내려가는 쪽이다 — 읽는 자가 생기면 그 칸이 표에서 빠진다.
#:
#: ★ 2026-10-09 (DECISIONS §444-1). 종전에 래칫이 `PROSE` 를 직접 걸었는데
#:   `ratchet --write` 가 「최상위 정수 상수가 아니다」로 울었다 — 그 표는
#:   **칸 → 사유** 사전이라 기계가 수로 고쳐 쓸 자리가 없다. 수를 따로 둔다.
#:   `sizetable` 이 표와 래칫 선언을 같이 두는 꼴과 같고, 선언이 실측과 같은지는
#:   `ratchet.py` 가 든다(§309).
PROSE_MAX = 9

RATCHETS = {"PROSE_MAX": "down"}


def ratchet_values() -> dict[str, int]:
    """선언 수. **판정은 `faults()` 소관**이다."""
    return {"PROSE_MAX": len(PROSE)}


def selftest() -> int:
    bad: list[str] = []
    cols = columns()
    if len(cols) < 20:
        bad.append(f"대장 칸이 {len(cols)}개뿐이다 — 도출을 의심하라")
    who = readers(set(cols))
    if not who:
        bad.append("읽는 자를 하나도 못 찾았다 — AST 도출이 죽었다")
    if faults(cols, who):
        bad.append("지금 트리에서 운다 — 실물이 이미 어긋난다")

    # ★ **합성으로 양방향.** 실물을 안 건드린다(§443-6).
    syn = {"산문칸": "사유"}
    if not faults({"새칸": 1}, {}, {}):
        bad.append("① 읽는 자 없는 새 칸에 안 운다")
    if faults({"새칸": 1}, {"새칸": {"tools/x.py"}}, {}):
        bad.append("읽는 자가 있는 칸에 운다 — 거짓 경보")
    if faults({"산문칸": 1}, {}, syn):
        bad.append("선언된 산문 칸에 운다 — 거짓 경보")
    if not faults({"산문칸": 1}, {"산문칸": {"tools/x.py"}}, syn):
        bad.append("② `PROSE` 인데 기계가 읽는 것을 안 잡는다")
    if not faults({"다른칸": 1}, {"다른칸": {"tools/x.py"}}, syn):
        bad.append("③ 대장에 없는 `PROSE` 선언을 안 잡는다")
    if not faults({}, {}, {}):
        bad.append("대장이 비었는데 통과한다 — 빈 그물을 안 막는다")

    # ★ 글자가 아니라 **문법**으로 집는가. 주석·로그는 읽는 것이 아니다.
    if reads('x = e.get("note")\n', {"note"}) != {"note"}:
        bad.append("`.get()` 을 못 집는다")
    if reads('x = e["note"]\n', {"note"}) != {"note"}:
        bad.append("첨자를 못 집는다")
    if reads('# note 를 읽는다\nprint("note")\n', {"note"}):
        bad.append("주석·로그 문자열을 읽는 것으로 센다 — ① 이 죽은 그물이 된다")
    if reads("def (:::", {"note"}):
        bad.append("문법 오류에서 칸을 낸다")

    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 세 축 · 합성 양방향 · 문법 집기 넷")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cols = columns()
    who = readers(set(cols))
    if a.table:
        print(f"{'칸':<16} {'항목':>4} {'읽는 자':>6}  어디서")
        for c in sorted(cols, key=lambda x: (-len(who.get(x, ())), x)):
            w = sorted(who.get(c, ()))
            tag = " · ".join(x.split("/")[-1] for x in w[:3]) or "— 사람이 읽는다"
            print(f"{c:<16} {cols[c]:>4} {len(w):>6}  {tag}")
        return 0
    bad = faults(cols, who)
    print(f"대장 칸 {len(cols)} · 기계가 읽는 칸 {len(who)} · 사람이 읽는 칸 {len(PROSE)}")
    if bad:
        print("\n★ 대장 칸의 독자가 어긋난다")
        for b in bad:
            print(f"    {b}")
        return 1
    print("✓ 칸마다 읽는 자가 있거나 **왜 사람만 읽는지**가 적혀 있다")
    return 0


if __name__ == "__main__":
    sys.exit(main())

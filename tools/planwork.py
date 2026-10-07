#!/usr/bin/env python3
"""
planwork.py — `PLAN §1` 이 **빚 목록인지 이력 창고인지** 잰다.

    uv run python tools/planwork.py              잰다 (0 같다 · 1 늘었다)
    uv run python tools/planwork.py --rows        행별 글자 수 · 이력 비중
    uv run python tools/planwork.py --selftest    판별식이 살아 있나

── 왜 생겼나 (DECISIONS §390) ─────────────────────────────────
`PLAN §0-1` 이 「PLAN 은 빚 목록이라 줄어드는 것이 목표」라고 적는다. 그 말을
세 자리가 주석으로 되풀이한다 — `tools/dms.py` · `tools/plan_renumber.py` ·
`tests/test_docref.py`. **강제자는 없었다.** MASTER §17 이 그 꼴을 이렇게 든다 —
「강제되지 않는 규약은 장식이다」.

★ 줄 수나 행 수를 재면 안 된다. **새 일이 들어오면 행은 늘어야 한다** — 사람이
  시킨 일을 적는 자리가 여기이고, 못 적게 막는 관문은 일을 기억에 남긴다.
  그러면 기억이 날아갈 때 일도 같이 날아간다(족 1).

★ 그래서 재는 것은 **이력**이다. 행 안에 쌓인 `★ 2026-09-18 …` 꼴의 경과
  서술은 **정본이 DECISIONS** 다. PLAN 에 있는 사본이고, 사본은 갈린다.
  줄여야 하는 빚은 그것이고 새 일은 그것이 아니다.

    열린 일        늘어도 된다 — 시킨 일을 안 적으면 떨어진다
    이력 사본      **줄어야 한다** — 정본이 DECISIONS 다
    가리킴(§N)     이력을 대신한다. 한 줄이 백 줄을 가리킨다

IN    docs/PLAN.md
OUT   없음 (종료코드 · 수)
PARAM 없음
밖    **무엇이 열려 있는가는 안 본다.** 그것은 사람의 판단이고 `§1` 의 상태
      표기가 든다. 여기가 드는 것은 「이 표가 이력을 품고 있나」 하나다.
      **DECISIONS 가 그 이력을 정말 들고 있나도 안 본다.** 죽은 참조는
      `tools/dms.py verify` 가 든다.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "PLAN.md"

#: `§1` 의 일 행. 번호가 영구 식별자라 `| 51 |` 꼴이다.
_ROW = re.compile(r"^\|\s*(\d+)\s*\|(.*)$")
#: 행 안의 경과 서술. `★` 뒤에 날짜가 오면 그것은 **이력**이다.
#: 날짜 없는 `★` 는 규율·근거이고 이력이 아니다 — 그것은 PLAN 에 있어야 한다.
_HIST = re.compile(r"★\s*\**\s*20\d\d-\d\d-\d\d")
#: 문서·절 가리킴. 이력을 대신하는 것이고 길이에서 뺀다.
_REF = re.compile(r"(DECISIONS|MASTER|PLAN)\s*§[\d\-．.]+")
#: 억제 표시(`<!--stale-ok-->` 등). **이력이 아니다** — 「이 행은 낡아도 된다」는
#: 선언이고 그 수는 `tools/suppress.py` 가 양방향으로 센다(§279). 길이에서 뺀다.
#: ★ 2026-10-04. 안 빼서 되돌린 표시 둘이 이력 +34 로 세어졌다.
_MUTE = re.compile(r"<!--[^>]*-->")

#: **이력 글자 수.** 실측(2026-10-04 · 빚 9,867자를 갚은 뒤)이 분모다.
#: 내려가는 쪽으로만 움직인다 — 새 일 행이 늘어도 이 수는 안 는다.
PLAN_HISTORY = 1433
#: 한 행이 품은 이력이 이보다 길면 그 행은 **창고**다. 실측 최대.
PLAN_HISTORY_WORST = 489

RATCHETS = {"PLAN_HISTORY": "down", "PLAN_HISTORY_WORST": "down"}


def _section_one(text: str) -> list[str]:
    """`## 1.` 과 다음 `## ` 사이의 일 행만 돌려준다."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.startswith("## 1.")), None)
    if start is None:
        raise RuntimeError("PLAN 에 `## 1.` 이 없다 — 표의 자리를 못 찾았다")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    return [ln for ln in lines[start:end] if _ROW.match(ln)]


def history_chars(row: str) -> int:
    """행 안에서 **이력**으로 세는 글자 수.

    ★ 날짜가 나온 자리부터 다음 `★` 또는 행 끝까지를 이력으로 센다. 가리킴은
      뺀다 — 가리킴은 이력을 **대신하는** 것이고 줄이려는 대상의 반대다.
    """
    marks = [m.start() for m in re.finditer(r"★", row)]
    if not marks:
        return 0
    bounds = marks + [len(row)]
    total = 0
    for i, at in enumerate(marks):
        chunk = row[at:bounds[i + 1]]
        if _HIST.search(chunk):
            total += len(_MUTE.sub("", _REF.sub("", chunk)))
    return total


def rows() -> list[tuple[str, int, int]]:
    """(번호, 행 글자 수, 이력 글자 수)."""
    out = []
    for ln in _section_one(PLAN.read_text(encoding="utf-8")):
        m = _ROW.match(ln)
        assert m is not None
        out.append((m.group(1), len(ln), history_chars(ln)))
    return out


def ratchet_values() -> dict[str, int]:
    """★ 못 재면 **0 을 돌려주지 않는다.** 0 은 「깨끗하다」로 읽히고
    그 순간 이 관문이 영원히 초록이 된다(§372)."""
    got = rows()
    if not got:
        raise RuntimeError("PLAN §1 에서 일 행을 하나도 못 읽었다 — 실측 못 한다")
    return {"PLAN_HISTORY": sum(h for _, _, h in got),
            "PLAN_HISTORY_WORST": max(h for _, _, h in got)}


def _selftest() -> int:
    hist = "| 9 | 제목 | 🟡 | 본문 ★ 2026-09-18 그때 이랬다 |"
    rule = "| 9 | 제목 | 🟡 | 본문 ★ 날짜 없는 규율은 이력이 아니다 |"
    ref = "| 9 | 제목 | 🟡 | 본문 ★ 2026-09-18 DECISIONS §190-6 |"
    # ★ 공백을 더하지 않는다 — 더하면 길이가 2 만큼 달라져 이 탐침이
    #   억제가 아니라 **공백**을 재게 된다. 한 번 그렇게 울었다.
    mute = hist[:-1] + "<!--stale-ok-->|"
    bad = []
    if history_chars(hist) <= 0:
        bad.append("날짜 붙은 ★ 를 이력으로 안 센다")
    if history_chars(rule) != 0:
        bad.append("날짜 없는 ★ 를 이력으로 센다 — 규율은 PLAN 에 있어야 한다")
    if not 0 < history_chars(ref) < history_chars(hist):
        bad.append("가리킴을 안 뺀다 — 가리킴은 이력을 대신하는 것이다")
    if history_chars(mute) != history_chars(hist):
        bad.append("억제 표시를 이력으로 센다 — 그것은 선언이고 suppress 가 센다")
    # ★ 빈 그물 반대 방향. 표를 못 찾으면 **0 이 아니라 예외**여야 한다.
    try:
        _section_one("# 문서\n\n본문뿐이고 표가 없다\n")
        bad.append("`## 1.` 이 없는데 조용히 넘어간다")
    except RuntimeError:
        pass
    if bad:
        print("★ 자기검사 실패")
        for b in bad:
            print(f"    {b}")
        return 1
    print("✓ 자기검사 — 이력 · 규율 · 가리킴 셋을 가른다 · 표가 없으면 운다")
    return 0


def main(argv: list[str]) -> int:
    # ★ `argparse` 를 쓴다 — 깃발을 `in argv` 로 보면 **모르는 깃발을 조용히
    #   무시하고 일을 한다.** `tests/test_cli_surface.py` 가 그 자리를 문다.
    ap = argparse.ArgumentParser(description="PLAN §1 의 이력 빚을 잰다")
    ap.add_argument("--rows", action="store_true", help="행별 글자 수 · 이력 비중")
    ap.add_argument("--selftest", action="store_true", help="판별식이 살아 있나")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    got = rows()
    vals = ratchet_values()
    if args.rows:
        print(f"{'행':>5s} {'글자':>7s} {'이력':>7s}  이력 비중")
        for num, size, hist in sorted(got, key=lambda r: -r[2]):
            if hist:
                print(f"{num:>5s} {size:7d} {hist:7d}  {100 * hist / size:5.1f}%")
    total = sum(s for _, s, _ in got)
    print(f"\n── PLAN §1  일 {len(got)}행 · 글자 {total:,}"
          f" · **이력 {vals['PLAN_HISTORY']:,}** ({100 * vals['PLAN_HISTORY'] / total:.0f}%)"
          f" · 최악 한 행 {vals['PLAN_HISTORY_WORST']:,}")
    print("   「열린 일」은 늘어도 된다 — 시킨 일을 안 적으면 떨어진다")
    print("   줄여야 하는 빚은 **이력 사본**이다. 정본은 DECISIONS 다")
    bad = [k for k, v in vals.items() if v > globals()[k]]
    if bad:
        print(f"\n★ 이력이 늘었다 — {', '.join(bad)}")
        print("   PLAN 에 경과를 적지 말고 DECISIONS 에 절을 세워 **가리켜라.**")
        return 1
    print("\n✓ 이력이 선언과 같거나 줄었다")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

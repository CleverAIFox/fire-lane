#!/usr/bin/env python3
"""
planclose.py — **열린 행이 전부 어느 판에 실려 있는가.**

    uv run python tools/planclose.py
    uv run python tools/planclose.py --selftest

── 왜 생겼나 (2026-10-13 · DECISIONS §520) ────────────────────
`PLAN §10-1` 의 배치 표가 「합 44. 지금 56행이고 못 닫는 열둘을 빼면 44 다 —
**남는 것도 겹치는 것도 없다**」라고 적는다. 그 주장이 **셋을 손으로 센 것**
이었고, 세 보니 틀렸다 — 열린 행 **57** · 못 닫는 **12** · 표가 드는 행 **43**.
`57 − 12 = 45 ≠ 43` 이고, 빠진 둘은 `#170` · `#171` 이다. 넉 달 동안
**아무 판도 안 드는 행**이었다.

그 둘이 중요한 이유는 수가 틀렸다는 것이 아니다 — 「무한 프로젝트는 할 수
없으니 판마다 어디에 뭘 실을지 **같이 관리하라**」가 이 표의 뜻이고, 행이
표 밖에 있으면 그 관리가 거짓이 된다. 끝이 나는지를 묻는 자리가 **제 분모를
안 세고 있었다.**

항등식 하나를 든다 —

    §1 열린 행  −  못 닫는 행  =  배치 표가 「드는 행」으로 적은 행

어긋나면 **이름을 댄다.** 수만 대면 어느 행인지 사람이 또 찾아야 한다.

★ **판이 몇 개인가는 안 본다.** 판을 쪼개고 합치는 것은 사람의 판단이고
  (`§10-1` 의 쪼개는 사유 둘), 여기가 묻는 것은 **빠진 행이 있는가** 하나다.

IN    docs/PLAN.md — §1 행 표 · §10-1 배치 표 · 「못 닫는」 표
OUT   `orphans()` · `ghosts()` · `counts()`
PARAM 없음 (항등식이라 래칫이 없다 — 빚이 아니라 **맞거나 틀리다**)
밖    **판 배정이 옳은지는 안 본다.** `#171` 이 `Zs` 가 아니라 `Zn` 이어야
      하는지는 사람이 안다. 「드는 행」 칸이 가리키는 §1 행이 **실재하는가**는
      `tools/plan_renumber.py` 소관이고, 닫는 수 칸의 합이 산문과 같은가는
      이 자리가 든다. 행 안의 내용(도착 조건 · 전건)은 `planwork` 가 든다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from firelane.cli import no_args

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "PLAN.md"

#: §1 행 표의 첫 칸. `| 170 | 커버리지 래칫이 … |` 꼴이다.
_ROW = re.compile(r"^\| (\d+) \|", re.M)
#: 배치 표의 한 줄. 판 이름 · … · 드는 행 · 닫는 수.
_BATCH = re.compile(r"^\| `([^`]+)` \|")
_HASH = re.compile(r"`#(\d+)`")

#: 「드는 행」 칸의 표식. **이 판이 닫겠다고 약속한 행이 아니다.**
#:
#: ★ 2026-10-14 (DECISIONS §524). 그 칸이 **두 가지 뜻**을 한 칸에 담고
#:   있었다 — 「닫을 행」과 「원인·전건으로 **언급만** 하는 행」. 그래서
#:   `닫는 수` 를 기계가 못 받았고, 판마다 세 보니 세 줄이 어긋났다
#:   (`Zm` 선언 1 · 살아있는 행 2 · `Zm5` 선언 0 · 1). 셋 다 **정상**이라
#:   사람은 안 고쳤고, 그 말은 **그 칸이 틀려도 아무도 모른다**는 뜻이다.
#:   §519 가 한 줄에서 규칙 둘을 가른 것과 같은 자다.
MENTION = ("언급", "조건부")


_HEAD = "| 판 | 성질 | 전건 | 드는 행 | 닫는 수 |"


def _table(src: str | None = None) -> list[str]:
    """배치 표의 **행들**. 끝은 표가 정한다 — 산문 낱말이 아니다.

    ★ 2026-10-14 (DECISIONS §524-1). 종전에는 표의 끝을 그 아래 산문의
      첫 낱말로 찾았다. 그 산문을 고치자 **파서가 죽었다** — 표를 읽는 자가
      표 밖의 글자에 매달려 있었다. 표는 `|` 로 시작하지 않는 첫 줄에서
      끝난다. 그것이 표의 성질이고 산문이 바뀌어도 안 바뀐다.
    """
    t = _text(src)
    out = []
    for ln in t[t.index(_HEAD):].splitlines():
        if not ln.startswith("|"):
            break
        out.append(ln)
    return out


def _text(src: str | None = None) -> str:
    return PLAN.read_text(encoding="utf-8") if src is None else src


def open_rows(src: str | None = None) -> set[int]:
    """§1 이 든 **열린** 행 번호. 닫힌 행은 지워지므로 표에 없다."""
    t = _text(src)
    i = t.index("## 1.")
    j = t.index("### 1-27.", i)
    return {int(m.group(1)) for m in _ROW.finditer(t[i:j])}


def _rows_marked(cell: str) -> list[tuple[int, str]]:
    """「드는 행」 칸 → (행 번호, **바로 뒤에 붙은 표식**) 목록.

    표식은 괄호 한 쌍 안에 있고 번호 **직후**에만 붙는다 — 칸 어딘가에 그
    낱말이 있는 것으로는 안 센다(§317 이 `feeds_why` 첫 줄로 가른 그 자).
    """
    out = []
    for m in _HASH.finditer(cell):
        tail = cell[m.end():m.end() + 10]
        out.append((int(m.group(1)), tail if tail.startswith("(") else ""))
    return out


def batches(src: str | None = None) -> dict[str, tuple[set[int], int | None]]:
    """배치 표 → 판 이름: (드는 행, 닫는 수)."""
    out: dict[str, tuple[set[int], int | None]] = {}
    for ln in _table(src):
        if not (m := _BATCH.match(ln)):
            continue
        col = ln.split("|")
        rows = {int(x) for x in _HASH.findall(col[4])}
        n = col[5].strip()
        out[m.group(1)] = (rows, int(n) if n.isdigit() else None)
    return out


def claims(src: str | None = None) -> dict[str, tuple[int, int]]:
    """판 이름 → (선언한 닫는 수, **센 수**).

    센 수 = 표식 없는 열린 행 + 이 판에서 **이미 닫은** 행(묘비). 표식이
    붙은 행(`언급` · `조건부`)은 **약속이 아니라서** 안 센다.
    """
    from plan_renumber import CLOSED
    op, cc = open_rows(src), cannot_close(src)
    out: dict[str, tuple[int, int]] = {}
    for ln in _table(src):
        if not (m := _BATCH.match(ln)):
            continue
        col = ln.split("|")
        n = col[5].strip()
        got = 0
        for num, tail in _rows_marked(col[4]):
            if any(w in tail for w in CLOSED):
                got += 1                      # 같은 판에서 닫았다 — 약속을 지켰다
            elif any(w in tail for w in MENTION):
                continue                      # 언급 · 조건부. 약속이 아니다
            elif num in op and num not in cc:
                got += 1
        out[m.group(1)] = (int(n) if n.isdigit() else 0, got)
    return out


def promised(src: str | None = None) -> set[int]:
    """어느 판이 **무조건** 닫겠다고 적은 열린 행. 표식이 붙은 것은 빠진다."""
    from plan_renumber import CLOSED
    op, cc = open_rows(src), cannot_close(src)
    out: set[int] = set()
    for ln in _table(src):
        if not _BATCH.match(ln):
            continue
        for num, tail in _rows_marked(ln.split("|")[4]):
            if any(w in tail for w in CLOSED + MENTION):
                continue
            if num in op and num not in cc:
                out.add(num)
    return out


def cannot_close(src: str | None = None) -> set[int]:
    """「물리적으로 못 닫는」 표가 든 행. 판에 실리지 않는 것이 정상이다."""
    t = _text(src)
    i = t.index("**물리적으로 못 닫는")
    j = t.index("\n---", i)
    return {int(x) for x in _HASH.findall(t[i:j])}


def _taken(src: str | None = None) -> set[int]:
    """배치 표가 「드는 행」으로 적은 행 전부. 두 자리가 이것을 쓴다."""
    took: set[int] = set()
    for rows, _ in batches(src).values():
        took |= rows
    return took


def orphans(src: str | None = None) -> set[int]:
    """열려 있고 · 못 닫는 것도 아니고 · **아무 판도 안 드는** 행. 순수하다."""
    return open_rows(src) - cannot_close(src) - _taken(src)


def ghosts(src: str | None = None) -> set[int]:
    """판이 드는데 §1 에 없고 **죽었다고 적지도 않은** 행.

    ★ `#14`(닫힘) 처럼 그 자리에 「죽었다」를 적은 것은 자국이 아니라 **묘비**다 —
      `tools/plan_renumber.py` 의 `CLOSED` 어휘가 그 규약의 정본이고 여기서
      목록을 다시 만들지 않는다(족 2 — 사본이 하나 더 생긴다).
    """
    from plan_renumber import CLOSED
    live: set[int] = set()
    for ln in _table(src):
        if not _BATCH.match(ln):
            continue
        col = ln.split("|")
        for m in _HASH.finditer(col[4]):
            tail = col[4][m.end():m.end() + 8]
            if not any(w in tail for w in CLOSED):
                live.add(int(m.group(1)))
    return live - open_rows(src)


def counts(src: str | None = None) -> dict[str, int]:
    """항등식의 세 수 + 선언된 닫는 수 합."""
    b = batches(src)
    took = _taken(src)
    return {"열린": len(open_rows(src)),
            "못 닫는": len(cannot_close(src)),
            "표가 드는 행": len(took & open_rows(src)),
            "무조건 닫는다": len(promised(src)),
            "닫는 수 선언 합": sum(n or 0 for _, n in b.values())}


def selftest() -> int:
    """합성 PLAN 으로 **양방향**을 민다(§405 의 규율)."""
    bad: list[str] = []
    synth = (
        "## 1. 일\n| 1 | a |\n| 2 | b |\n| 3 | c |\n| 9 | d |\n### 1-27. 측정\n"
        "| 판 | 성질 | 전건 | 드는 행 | 닫는 수 |\n|---|---|---|---|---|\n"
        "| `Za` | x | 없다 | `#1` `#2` | 2 |\n"
        "| `Zb` | y | `Za` | `#9` `#77` | 1 |\n"
        "**합 3.**\n"
        "**물리적으로 못 닫는 하나 — 그리고 왜**\n\n| 행 | 왜 |\n| `#3` 바깥 | 외부다 |\n\n---\n")
    if open_rows(synth) != {1, 2, 3, 9}:
        bad.append(f"§1 행을 잘못 읽는다 — {sorted(open_rows(synth))}")
    if cannot_close(synth) != {3}:
        bad.append(f"못 닫는 행을 잘못 읽는다 — {sorted(cannot_close(synth))}")
    if set(batches(synth)) != {"Za", "Zb"}:
        bad.append(f"배치 표를 잘못 읽는다 — {sorted(batches(synth))}")
    if orphans(synth):
        bad.append(f"빠진 행이 없는데 댄다 — {sorted(orphans(synth))}")
    if ghosts(synth) != {77}:
        bad.append(f"§1 에 없는 행을 못 집는다 — {sorted(ghosts(synth))}")
    # ★ 빠진 행을 **만들어** 민다 — 한쪽만 밀면 빈 그물이 초록이다
    hole = synth.replace("| `#1` `#2` | 2 |", "| `#1` | 1 |")
    if orphans(hole) != {2}:
        bad.append(f"빠진 행을 못 집는다 — {sorted(orphans(hole))}")
    if counts(synth)["닫는 수 선언 합"] != 3:
        bad.append("닫는 수 합을 잘못 센다")
    # ★ 표식. 번호 **직후**의 괄호만 표식이고 칸 어딘가의 낱말은 아니다
    cell = "`#1`(언급) `#2` `#3`(닫힘) 언급"
    got = [(n, bool(tail)) for n, tail in _rows_marked(cell)]
    if got != [(1, True), (2, False), (3, True)]:
        bad.append(f"표식을 잘못 읽는다 — {_rows_marked(cell)}")
    if "언급" not in _rows_marked(cell)[0][1]:
        bad.append("표식을 읽었는데 낱말이 안 담겼다 — 어휘로 가를 수 없다")
    if _rows_marked("`#4` (언급)")[0][1] != "":
        bad.append("번호와 괄호 사이가 벌어진 것을 표식으로 읽는다")
    # ★ 선언 ↔ 센 수. 양방향으로 민다
    if claims(synth) != {"Za": (2, 2), "Zb": (1, 1)}:
        bad.append(f"선언과 센 수를 잘못 센다 — {claims(synth)}")
    marked = synth.replace("| `#1` `#2` | 2 |", "| `#1` `#2`(언급) | 2 |")
    if claims(marked).get("Za") != (2, 1):
        bad.append("표식을 붙였는데 센 수가 안 줄었다 — 그 가지가 죽었다")
    if 2 in promised(marked):
        bad.append("`(언급)` 행을 **약속**으로 센다")
    if promised(synth) != {1, 2, 9}:
        bad.append(f"약속한 행을 잘못 센다 — {sorted(promised(synth))}")
    # ★ §524-1 — 표 **아래 산문**을 고쳐도 같은 수를 읽는가
    moved = synth.replace("**합 3.**", "손으로 세지 않는다 — 도구가 센다.")
    if counts(moved) != counts(synth) or claims(moved) != claims(synth):
        bad.append("표 아래 산문을 고치자 수가 달라졌다 — 파서가 산문에 매달렸다")
    # ★ 겹친 행을 **만들어** 민다 — `orphans()` 가 못 집는 쪽이다
    both = synth.replace("| `#3` 바깥 | 외부다 |", "| `#1` 바깥 | 외부다 |")
    if not (cannot_close(both) & _taken(both)):
        bad.append("못 닫는다고 적은 행을 판이 드는데 안 집는다 — 그 가지가 죽었다")
    if orphans(both) == {1}:
        bad.append("겹친 행을 **빠진 행**으로 센다 — 둘은 다른 결함이다")
    # ★ 실물 — 항등식이 맞아야 한다
    c = counts()
    if c["열린"] - c["못 닫는"] != c["표가 드는 행"]:
        bad.append(f"실물 항등식이 어긋난다 — {c}")
    bad += _block_is_current(c)
    if bad:
        print("★ 자기검사 실패")
        for b in bad:
            print(" ", b)
        return 1
    print("selftest 초록")
    return 0


#: `§10-1b` 가 세 수를 **글로 적은** 블록. 「손으로 세지 않는다」고 선언한
#: 자리라 그 수가 낡으면 선언이 거짓이 된다.
_BLOCK = re.compile(
    r"열린 (\d+) − 못 닫는 (\d+) = (\d+).*?"
    r"무조건 닫는다\s+(\d+).*?"
    r"닫는 수 선언 합\s+(\d+)", re.S)


def _block_is_current(c: dict[str, int]) -> list[str]:
    """`§10-1b` 의 세 수가 **지금 실측과 같은가.**

    ★ 2026-10-14 (DECISIONS 533). 그 절은 「손으로 세지 않는다」고 적어 두고
      **수는 손으로 적어** 뒀다. `#177` 이 들어오자 다섯 수가 다 틀렸고
      아무 자도 안 울었다 — §520 이 고친 병의 재발이다. 선언한 자리는
      **그 선언을 재는 자**가 있어야 선언이다(§390).
    """
    m = _BLOCK.search(PLAN.read_text(encoding="utf-8"))
    if not m:
        return ["§10-1b 의 세 수 블록을 못 찾았다 — 꼴이 바뀌었으면 이 자도 고쳐라"]
    want = (c["열린"], c["못 닫는"], c["열린"] - c["못 닫는"],
            c["무조건 닫는다"], c["닫는 수 선언 합"])
    got = tuple(int(g) for g in m.groups())
    if got != want:
        return [f"§10-1b 의 수가 낡았다 — 적힌 {got} · 실측 {want}. "
                "그 절은 「손으로 세지 않는다」고 선언한 자리다"]
    return []


def main() -> int:
    c = counts()
    orph, gh = sorted(orphans()), sorted(ghosts())
    print(f"§1 열린 {c['열린']} − 못 닫는 {c['못 닫는']} = {c['열린'] - c['못 닫는']}"
          f"  ·  배치 표가 드는 행 {c['표가 드는 행']}"
          f"  ·  무조건 닫는다 {c['무조건 닫는다']}"
          f"  ·  닫는 수 선언 합 {c['닫는 수 선언 합']}")
    if bad := {k: v for k, v in claims().items() if v[0] != v[1]}:
        print(f"\n✗ **닫는 수가 센 수와 다른 판 {len(bad)}**")
        for k, (dec, got) in sorted(bad.items()):
            print(f"    `{k}` 선언 {dec} · 센 수 {got}")
        print(f"  「드는 행」 칸의 번호 뒤에 {' · '.join(f'({w})' for w in MENTION)} 를")
        print("  붙이면 **약속이 아니다**로 센다. 닫을 행만 맨번호로 두어라 —")
        print("  한 칸이 두 뜻을 담으면 그 수가 틀려도 아무도 모른다(DECISIONS §524)")
        return 1
    if (une := sorted(set(promised()) ^ (open_rows() - cannot_close()))):
        print(f"\n  ! **어느 판도 무조건 닫겠다고 안 한 행 {len(une)}** — "
              f"{' '.join(f'#{n}' for n in une)}")
        print("    조건부에만 걸려 있다. 조건이 깨지면 그 행을 닫는 판이 없다.")
    if gh:
        print(f"\n  ! 판이 드는데 §1 에 없는 행 {len(gh)} — "
              f"{' '.join(f'#{n}' for n in gh)}")
        print("    닫힌 뒤 「드는 행」 칸에서 안 지운 자국이다. 지워라.")
    if orph:
        print(f"\n✗ **아무 판도 안 드는 행 {len(orph)}** — "
              f"{' '.join(f'#{n}' for n in orph)}")
        print("  열려 있고, 물리적으로 못 닫는 것도 아닌데 어느 판에도 없다.")
        print("  배치 표의 「드는 행」에 실어라 — 표 밖의 행은 **관리되지 않는다**.")
        print("  (DECISIONS §520 — 끝이 나는지 묻는 자리가 제 분모를 안 셌다)")
        return 1
    if dbl := sorted(cannot_close() & _taken()):
        # ★ 이 가지는 **도달 가능하다** — 못 닫는다고 적은 행을 어느 판이
        #   「드는 행」으로 들면 `열린 − 못 닫는 > 표가 드는 행` 이 된다.
        #   `orphans()` 는 그것을 **못 집는다**(빠진 것이 아니라 겹친 것이다).
        print(f"\n✗ **못 닫는다고 적은 행을 판이 든다 {len(dbl)}** — "
              f"{' '.join(f'#{n}' for n in dbl)}")
        print("  한 행이 두 자리에 산다. 「못 닫는」에서 빼거나 판에서 빼라 —")
        print("  둘 다 두면 그 행이 닫혔는지 아무 수도 말하지 않는다.")
        return 1
    print("\n✓ 열린 행이 전부 어느 판에 실려 있다")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    no_args(__doc__)
    sys.exit(main())

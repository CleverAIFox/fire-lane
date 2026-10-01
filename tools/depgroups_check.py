#!/usr/bin/env python3
"""
depgroups_check.py — **봇이 판정을 건드릴 때 그렇다고 말하는가.**

    uv run python tools/depgroups_check.py            판정 (verify.sh · CI)
    uv run python tools/depgroups_check.py --table    폐포 ↔ 그룹 배정 전부
    uv run python tools/depgroups_check.py --fix      그룹을 폐포로 다시 쓴다
    uv run python tools/depgroups_check.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-10-02 (DECISIONS §347). 전날 §345 가 잠금 폐포를 66 → 13 으로 좁혔다.
  그 다음 날 아침 Dependabot PR 넷이 열렸고 **셋이 초록, 하나가 빨강**이었다.
  빨간 하나는 `rest` 그룹이고 `networkx 3.6.1 → 3.7` 을 들고 있었다 —
  `networkx` 는 구간을 쪼개는 그래프 라이브러리이고 **판정 폐포 안**이다.

  빨간 것은 옳다. 폐포가 움직이면 산출물이 움직일 수 있고, 봇은 파이프라인을
  못 돌리니 재잠금 없이는 초록이 될 길이 없다. 문제는 **그것이 PR 제목에
  안 적혀 있었다**는 것이다. 제목은 `bump the rest group with 3 updates` 다.

      geo-abi    numpy · pandas · rasterio · pyogrio · geopandas · shapely · pyproj
      dev-tools  ruff · pytest* · pre-commit
      rest       "*"  ← `networkx` 가 `colorama` 와 같은 자루에 담겼다

  `geo-abi` 의 일곱은 2026-09-18 에 **사람이 손으로 적은 목록**이다. 그날은
  맞았고, 그 뒤로 폐포가 무엇인지 아무도 안 셌다. `networkx` 는 그 사이에
  들어왔다. **손으로 적은 목록은 적은 날만 맞다**(§338 과 같은 족).

★ 이제는 셀 수 있다 — `shardseal.lock_deps` 가 바로 그 목록이다. 그래서
  **그룹을 사람이 적지 않는다. 폐포에서 받는다.**

── 무엇을 보는가 ───────────────────────────────────────────────
① **덮는가** — `judgment-closure` 그룹의 패턴 집합이 폐포와 **정확히 같은가**.
   더 적으면 빠진 패키지가 `rest` 로 새고, 더 많으면 낡은 손목록이다.
② **먼저인가** — Dependabot 은 **처음 걸리는 그룹**에 넣는다. 그래서 선언
   순서가 판정이다. `judgment-closure` 뒤에 있는 그룹이 폐포 패키지를
   가로채면 실패다.
③ **빈 그물** — 폐포가 0이거나 그룹이 0이면 실패. 둘 중 하나가 죽으면
   ①·② 가 조용히 통과한다(MASTER §17-0 ③).

`--fix` 가 `patterns:` 줄을 다시 쓴다. 주석은 건드리지 않는다 —
**사람이 베껴 적을 일을 안 남긴다.**

★ 이 도구는 **판 번호를 안 본다.** 어느 판으로 올릴지는 Dependabot 이 정하고,
  올라간 것이 판정을 움직이는지는 `golden` 이 잡는다. 여기가 드는 물음은
  「움직일 수 있는 것이 **따로 담겨 오는가**」 하나다.

IN    .github/dependabot.yml · uv.lock · src/firelane/**
OUT   표준출력 (판정) · `--fix` 면 .github/dependabot.yml
밖    **npm · github-actions · docker 생태계는 안 본다** — 잠금 폐포는
      파이썬 축이고, 다른 생태계에는 대응하는 폐포 계산이 없다.
      **그룹이 실제로 그렇게 묶여 오는지도 안 본다** — 그것은 GitHub 의
      일이고, 여기는 선언만 읽는다.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YML = ROOT / ".github" / "dependabot.yml"

#: 폐포를 따로 담는 그룹의 이름. 이 이름이 정본이다.
GROUP = "judgment-closure"
#: 파이썬 잠금을 보는 생태계.
ECOSYSTEM = "uv"


def closure() -> list[str]:
    """판정 폐포 — 봉인된 축 전부의 합집합. 판 번호는 뗀다."""
    from firelane.shardseal import SEALED_AXES, lock_deps
    out: set[str] = set()
    for axis in SEALED_AXES:
        out |= {x.split("==")[0] for x in lock_deps(axis)}
    return sorted(out)


# ── 선언 읽기 ───────────────────────────────────────────────────
def groups(text: str | None = None) -> list[tuple[str, list[str], list[str]]]:
    """`uv` 생태계의 그룹들 — 선언 순서로 `(이름, patterns, exclude)`.

    ★ YAML 로 안 읽고 **들여쓰기로 읽는다.** `--fix` 가 같은 파일을 주석째
      다시 써야 하는데, 라운드트립 쓰기를 하려면 `ruamel-yaml` 이 코어로
      올라와야 한다(지금 dev 다). 선언 꼴이 고정이라 그럴 값어치가 없다.
    """
    text = YML.read_text(encoding="utf-8") if text is None else text
    out: list[tuple[str, list[str], list[str]]] = []
    eco = name = None
    key: list[str] | None = None
    for ln in text.splitlines():
        if m := re.match(r"\s*- package-ecosystem:\s*(\S+)", ln):
            eco, name, key = m[1].strip("\"'"), None, None
            continue
        if eco != ECOSYSTEM:
            continue
        if re.match(r"\s{4}\S", ln) and not re.match(r"\s*(groups|#)", ln):
            name = key = None                      # groups 블록을 벗어났다
        if m := re.match(r"\s{6}([\w.-]+):\s*$", ln):
            name, key = m[1], None
            out.append((name, [], []))
            continue
        if name and (m := re.match(r"\s{8}(patterns|exclude-patterns):\s*(.*)$", ln)):
            key = {"patterns": out[-1][1], "exclude-patterns": out[-1][2]}[m[1]]
            key += _items(m[2])
            continue
        if key is not None and (m := re.match(r"\s{10}- (.+)$", ln)):
            key += _items("[" + m[1] + "]")
    return out


def _items(raw: str) -> list[str]:
    """`["a", "b"]` 또는 빈 꼬리."""
    raw = raw.split("#", 1)[0].strip()
    if not raw.startswith("["):
        return []
    return [x.strip().strip("\"'") for x in raw[1:-1].split(",") if x.strip()]


def owner(pkg: str, gs: list[tuple[str, list[str], list[str]]]) -> str | None:
    """Dependabot 규칙 — **처음 걸리는 그룹**. exclude 가 이긴다."""
    for name, pats, excl in gs:
        if any(fnmatch.fnmatch(pkg, e) for e in excl):
            continue
        if any(fnmatch.fnmatch(pkg, p) for p in pats):
            return name
    return None


# ── 판정 ────────────────────────────────────────────────────────
def judge(clo: list[str], gs: list[tuple[str, list[str], list[str]]]) -> list[str]:
    """실패 사유들. 빈 리스트면 초록."""
    bad: list[str] = []
    if not clo:
        bad.append("판정 폐포가 비었다 — `shardseal.lock_deps` 가 죽었다")
    if not gs:
        bad.append(f"`{YML.name}` 에서 `{ECOSYSTEM}` 그룹을 하나도 못 읽었다 — 선언 꼴이 바뀌었다")
    if bad:
        return bad

    mine = next((g for g in gs if g[0] == GROUP), None)
    if mine is None:
        return [f"`{GROUP}` 그룹이 없다 — 폐포가 `rest` 로 샌다"]

    have, want = set(mine[1]), set(clo)
    if miss := sorted(want - have):
        bad.append(f"폐포에 있는데 `{GROUP}` 에 없다 {len(miss)} — {' '.join(miss)}")
    if gone := sorted(have - want):
        bad.append(f"`{GROUP}` 에 있는데 폐포에 없다 {len(gone)} — {' '.join(gone)}")

    for pkg in clo:
        who = owner(pkg, gs)
        if who != GROUP:
            bad.append(f"`{pkg}` 가 `{who}` 로 간다 — `{GROUP}` 을 더 앞에 선언해라")
    return bad


# ── 고침 ────────────────────────────────────────────────────────
def rewrite(text: str, clo: list[str]) -> str:
    """`judgment-closure` 의 `patterns:` 한 줄을 폐포로 다시 쓴다."""
    want = "[" + ", ".join(f'"{p}"' for p in clo) + "]"
    pat = re.compile(rf"(^\s{{6}}{re.escape(GROUP)}:\s*\n(?:\s*#.*\n)*\s{{8}}patterns:\s*)"
                     r"\[[^\]]*\]", re.M)
    new, n = pat.subn(lambda m: m[1] + want, text, count=1)
    if n != 1:
        raise RuntimeError(f"`{GROUP}` 의 `patterns:` 줄을 못 찾았다 — 손으로 고쳐라")
    return new


# ── 표 ──────────────────────────────────────────────────────────
def table(clo: list[str], gs: list[tuple[str, list[str], list[str]]]) -> None:
    print(f"\n판정 폐포 {len(clo)} — 어느 그룹으로 가는가")
    for pkg in clo:
        print(f"   {pkg:18} {owner(pkg, gs) or '— 그룹 없음 (개별 PR)'}")
    print("\n선언 순서")
    for name, pats, excl in gs:
        tail = f"  제외 {len(excl)}" if excl else ""
        print(f"   {name:18} 패턴 {len(pats)}{tail}")


# ── 자기검사 ────────────────────────────────────────────────────
Y = """\
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    groups:
      judgment-closure:
        # 주석이 있어도 읽는다
        patterns: ["networkx", "numpy"]
      rest:
        patterns: ["*"]
  - package-ecosystem: npm
    directory: /web/navi
    groups:
      navi-all:
        patterns: ["*"]
"""


def selftest() -> int:
    """판별식 — 하나라도 틀리면 이 도구가 거짓말을 한다."""
    g = groups(Y)
    ok: list[tuple[str, bool]] = [
        ("uv 생태계만 읽는다", [n for n, _, _ in g] == ["judgment-closure", "rest"]),
        ("패턴을 읽는다", g[0][1] == ["networkx", "numpy"]),
        ("주석이 끼어도 읽는다", len(g[0][1]) == 2),
        ("빈 그물 — 그룹 0이면 실패", bool(judge(["numpy"], []))),
        ("빈 그물 — 폐포 0이면 실패", bool(judge([], g))),
        ("덮으면 초록", judge(["networkx", "numpy"], g) == []),
        ("빠지면 빨강", any("폐포에 있는데" in b for b in judge(["networkx", "numpy", "six"], g))),
        ("낡은 이름이 남으면 빨강", any("폐포에 없다" in b for b in judge(["numpy"], g))),
        ("순서가 뒤집히면 빨강",
         any("더 앞에" in b for b in judge(["numpy"], [g[1], ("judgment-closure", ["numpy"], [])]))),
        ("exclude 가 이긴다", owner("numpy", [("x", ["*"], ["numpy"]), ("y", ["numpy"], [])]) == "y"),
        ("그룹 없는 패키지는 None", owner("zzz", [("x", ["aaa"], [])]) is None),
        ("--fix 가 그 줄만 바꾼다",
         rewrite(Y, ["six"]).count('patterns: ["*"]') == 2
         and 'patterns: ["six"]' in rewrite(Y, ["six"])),
        ("--fix 가 못 찾으면 터뜨린다", _raises(lambda: rewrite("version: 2\n", ["six"]))),
        ("폐포가 실물에서 안 비었다", len(closure()) >= 10),
        ("GROUP 이 실물 선언에 있다", any(n == GROUP for n, _, _ in groups())),
    ]
    for what, good in ok:
        print(f"   {'OK ' if good else '✗  '} {what}")
    bad = [w for w, g_ in ok if not g_]
    print(f"\n판별식 {len(ok)} · 실패 {len(bad)}")
    return 1 if bad else 0


def _raises(fn) -> bool:
    try:
        fn()
    except RuntimeError:
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="의존성 그룹이 판정 폐포를 덮는가")
    ap.add_argument("--table", action="store_true", help="폐포 ↔ 그룹 배정 전부")
    ap.add_argument("--fix", action="store_true", help="그룹을 폐포로 다시 쓴다")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    clo = closure()
    if a.fix:
        txt = YML.read_text(encoding="utf-8")
        new = rewrite(txt, clo)
        if new == txt:
            print(f"✓ `{GROUP}` 이 이미 폐포 {len(clo)} 와 같다")
        else:
            YML.write_text(new, encoding="utf-8")
            print(f"✓ `{GROUP}` 을 폐포 {len(clo)} 로 다시 썼다 → {YML.relative_to(ROOT)}")
        return 0

    gs = groups()
    print(f"판정 폐포 {len(clo)}   `{ECOSYSTEM}` 그룹 {len(gs)}")
    if a.table:
        table(clo, gs)

    if bad := judge(clo, gs):
        print("\n✗ 의존성 그룹")
        for b in bad:
            print(f"   {b}")
        print("\n  손으로 적지 마라 — `uv run python tools/depgroups_check.py --fix` 가 쓴다.")
        print("  그룹 순서만 사람이 본다: `judgment-closure` 가 `rest` 보다 먼저여야 한다.")
        return 1
    print("✓ 의존성 그룹")
    return 0


if __name__ == "__main__":
    sys.exit(main())

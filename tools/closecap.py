#!/usr/bin/env python3
"""
tools/closecap.py — **한 커밋이 닫는 PLAN 행은 셋까지다.** 넘으면 사유를 DECISIONS 에 적어야 통과한다.  (DECISIONS §732 · E1)

    uv run python tools/closecap.py                 스테이지된 diff 검사 (훅용)
    uv run python tools/closecap.py --range A..B    그 범위의 커밋마다 닫은 수를 센다(보고만 · 실패 안 함)
    uv run python tools/closecap.py --selftest      ★ 프로브가 살아 있나

IN    `git diff --cached -U0 -- docs/PLAN.md docs/DECISIONS.md`
OUT   종료코드 0(통과) · 1(막음) · 2(git 이 안 된다 — 못 본 것을 통과로 안 읽는다)
PARAM `CAP = 3`

★ 왜 생겼나 — 닫힌 행은 지워지고 본문은 git 기록에만 남는다. 한 커밋이 여럿을 한꺼번에 닫으면 **하나씩 읽지 않고 닫은 행**이 섞인다(⓲G 실측: 닫힌 행 99 중 같은 커밋에
  묶여 닫힌 것이 많았고 `#144` 가 그 안에서 반만 닫힌 채 지워졌다). 사후 감사는 되는데 닫는 순간에 막는 것이 없었다.
★ **닫은 행** = diff 에서 `| N |` 로 시작하는 줄이 지워졌고 같은 N 이 다시 추가되지 않은 것. 줄만 고친 행은 안 센다.
★ **통과냐 막느냐는 막는다.** 사유를 요구하는 것만으로는 「사유를 적었다」가 도장이 되므로 사유는 **기록으로 남는 곳**(DECISIONS 에 이 커밋이 더한 줄)에만 인정한다:
      **한 커밋에 닫은 행 N개(상한 3) — 사유:** …(스무 자 이상)
  N 이 실제 닫은 수와 같아야 한다(거짓 사유 · 복사 사유를 막는다). 사유가 있으면 통과한다 — 셋을 넘는 것이 늘 틀린 것은 아니다(같은 근거로 한 번에 닫히는 묶음).
★ **과거는 못 고친다.** `--range` 는 분포를 보이는 보고용이고 실패하지 않는다. 막는 것은 지금부터 들어오는 커밋뿐이다.
밖    행이 **옳게** 닫혔는지는 안 본다(그것은 `planclose` · 사람의 읽기다). 닫는 **수**만 문다.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = 3
MIN_WHY = 20
_ROW = re.compile(r"^([+-])\| (\d+) \|")
_WHY = re.compile(r"한 커밋에 닫은 행 (\d+)개\(상한 3\) — 사유:\**\s*(.+)")


def closed_rows(plan_diff: str) -> list[int]:
    """`-U0` diff 에서 지워지고 다시 안 나온 행 번호(오름차순)."""
    gone: set[int] = set()
    back: set[int] = set()
    for ln in plan_diff.splitlines():
        m = _ROW.match(ln)
        if m:
            (gone if m.group(1) == "-" else back).add(int(m.group(2)))
    return sorted(gone - back)


def why_given(decisions_diff: str, n: int) -> str | None:
    """이 커밋이 DECISIONS 에 **더한** 줄에서 n 개를 말하는 사유. 없거나 짧으면 None."""
    for ln in decisions_diff.splitlines():
        if not ln.startswith("+") or ln.startswith("+++"):
            continue
        m = _WHY.search(ln)
        if m and int(m.group(1)) == n and len(m.group(2).strip()) >= MIN_WHY:
            return m.group(2).strip()
    return None


def verdict(plan_diff: str, decisions_diff: str) -> tuple[int, str]:
    rows = closed_rows(plan_diff)
    if len(rows) <= CAP:
        return 0, f"닫은 행 {len(rows)}개 — 상한 {CAP} 안"
    why = why_given(decisions_diff, len(rows))
    names = " ".join(f"#{r}" for r in rows)
    if why:
        return 0, f"닫은 행 {len(rows)}개({names}) — 상한 {CAP} 초과, 사유가 기록돼 있다: {why[:60]}"
    return 1, (f"✗ 한 커밋에 닫은 행 {len(rows)}개({names}) — 상한 {CAP}\n"
               f"  닫는 순간에 하나씩 읽었는지 이 검사는 모른다 — 묶어 닫은 행이 반만 닫힌 채 지워진 것이 `#144` 였다(DECISIONS §729).\n"
               f"  ① 커밋을 나눠라(권장) ② 사유를 DECISIONS 에 더한 줄로 남겨라:\n"
               f"     **한 커밋에 닫은 행 {len(rows)}개(상한 {CAP}) — 사유:** (스무 자 이상 · 같은 근거로 닫히는 묶음인 까닭)")


def git_out(*args: str) -> str | None:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    return r.stdout if r.returncode == 0 else None


def staged() -> int:
    plan = git_out("diff", "--cached", "-U0", "--", "docs/PLAN.md")
    dec = git_out("diff", "--cached", "-U0", "--", "docs/DECISIONS.md")
    if plan is None or dec is None:
        print("✗ git diff 가 안 된다 — 닫은 수를 못 봤다. 통과로 안 읽는다")
        return 2
    code, msg = verdict(plan, dec)
    print(("✓ " if code == 0 else "") + msg)
    return code


def history(rng: str) -> int:
    log = git_out("log", "--format=%h", rng, "--", "docs/PLAN.md")
    if log is None:
        print("✗ git log 가 안 된다")
        return 2
    over: list[tuple[str, int]] = []
    total = 0
    for h in log.split():
        d = git_out("show", "-U0", "--format=", h, "--", "docs/PLAN.md") or ""
        n = len(closed_rows(d))
        total += n
        if n > CAP:
            over.append((h, n))
    print(f"범위 {rng} — 닫은 행 {total} · 상한 {CAP} 을 넘긴 커밋 {len(over)}")
    for h, n in sorted(over, key=lambda x: -x[1])[:15]:
        print(f"  {h}  {n}개")
    return 0


def selftest() -> int:
    plan = "".join(f"-| {n} | x |\n" for n in (1, 2, 3, 4)) + "+| 9 | y |\n-| 9 | y0 |\n"
    ok = closed_rows(plan) == [1, 2, 3, 4]                                        # 고친 행(9)은 안 센다
    ok &= verdict(plan, "")[0] == 1                                                # 넷 · 사유 없음 → 막음
    why = "+**한 커밋에 닫은 행 4개(상한 3) — 사유:** 같은 근거로 한 번에 닫히는 묶음이다 · 하나씩 읽었다\n"
    ok &= verdict(plan, why)[0] == 0                                               # 사유 → 통과
    ok &= verdict(plan, why.replace("4개", "5개"))[0] == 1                         # 수가 다른 사유 → 막음
    ok &= verdict(plan, "+**한 커밋에 닫은 행 4개(상한 3) — 사유:** 짧다\n")[0] == 1  # 스무 자 미만 → 막음
    ok &= verdict("-| 1 | a |\n-| 2 | b |\n-| 3 | c |\n", "")[0] == 0               # 셋은 통과
    print("✓ 프로브가 산다" if ok else "✗ 프로브가 죽었다")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--range" in argv:
        return history(argv[argv.index("--range") + 1])
    return staged()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

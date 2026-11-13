#!/usr/bin/env python3
"""
tools/closewords.py — **행을 닫는 문단의 어휘는 닫힌 목록이다.** 후속이 필요한 말로 닫으면 후속 행이 PLAN 에 있어야 통과한다.  (DECISIONS §733 · E2)

    uv run python tools/closewords.py             스테이지된 diff 검사 (훅용)
    uv run python tools/closewords.py --selftest  ★ 카나리아(#144 옛 닫는 문단)가 빨갛게 뜨나

IN    `git diff --cached -U0 -- docs/PLAN.md docs/DECISIONS.md` · `git show :docs/PLAN.md`(닫은 뒤의 PLAN)
OUT   종료코드 0 · 1(막음) · 2(git 이 안 된다)

★ 규칙 — 이 커밋이 PLAN 행을 **하나라도 닫았고**, DECISIONS 에 **더한 줄**에 후속 어휘(`안 한 것` · `범위가 아니다` · `확인 필요` · `남은 것` · `미뤘다`)가 있으면
  그 줄은 **닫은 뒤의 PLAN 에 실제로 있는 열린 행 `#M`** 을 인용해야 한다. 인용한 행이 없거나 PLAN 에 없으면 막는다.
★ 허용 어휘 — `확인 불가로 닫는다` 가 그 줄에 있으면 후속이 필요 없다(§635 · §674 선례: 더 알 수 없다는 닫음이다).
★ 왜 — `#144` 가 「`uq164` 는 **이 행의 범위가 아니다**」 로 닫혔고 그 말을 든 행이 지워져 18면이 임자 없이 남았다(§729). 후속이 필요한 말은 **행이 대신 들어야** 한다.
밖    인용한 행이 **그 일을 정말 드는지** 는 못 안다(번호의 실재만 본다). 후속 어휘가 목록 밖의 말로 쓰이면 못 잡는다 — 목록은 닫혀 있되 늘릴 수 있다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 같은 tools/ 의 형제 — 스크립트로 돌 때는 tools/ 가 경로 맨 앞이고 pytest 는 `pythonpath` 가 든다
from closecap import closed_rows, git_out

ROOT = Path(__file__).resolve().parents[1]
FOLLOWUP = ("안 한 것", "범위가 아니다", "확인 필요", "남은 것", "미뤘다")   # 「미결」은 뺐다 — 읽은 3건이 전부 오탐(DECISIONS §747)
OK_WORD = "확인 불가로 닫는다"
_REF = re.compile(r"#(\d+)")
_PLANROW = re.compile(r"^\| (\d+) \|", re.M)


def added_lines(decisions_diff: str) -> list[str]:
    return [ln[1:] for ln in decisions_diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def verdict(plan_diff: str, decisions_diff: str, plan_after: str) -> tuple[int, str]:
    closed = closed_rows(plan_diff)
    if not closed:
        return 0, "닫은 행 없음 — 닫는 문단 규칙이 볼 것이 없다"
    open_rows = {int(n) for n in _PLANROW.findall(plan_after)} - set(closed)
    bad: list[str] = []
    for ln in added_lines(decisions_diff):
        words = [w for w in FOLLOWUP if w in ln]
        if not words or OK_WORD in ln:
            continue
        refs = {int(n) for n in _REF.findall(ln)}
        if not (refs & open_rows):
            bad.append(f"  「{'」「'.join(words)}」 — {ln.strip()[:90]}")
    if not bad:
        return 0, f"닫은 행 {len(closed)}개 — 후속 어휘는 실재하는 열린 행을 인용하거나 없다"
    return 1, (f"✗ 행 {' '.join('#' + str(c) for c in closed)} 을 닫는 커밋이 후속이 필요한 말을 후속 행 없이 적었다 ({len(bad)}줄)\n"
               + "\n".join(bad[:6]) + "\n"
               "  ① 후속 행을 PLAN 에 세우고 그 줄에 `#M` 을 적어라 ② 더 알 수 없다면 「확인 불가로 닫는다」 로 적어라(§635 · §674)\n"
               "  ★ `#144` 가 「uq164 는 이 행의 범위가 아니다」 로 닫힌 것이 이 꼴이었다(§729).")


def staged() -> int:
    plan = git_out("diff", "--cached", "-U0", "--", "docs/PLAN.md")
    dec = git_out("diff", "--cached", "-U0", "--", "docs/DECISIONS.md")
    after = git_out("show", ":docs/PLAN.md")
    if plan is None or dec is None or after is None:
        print("✗ git 이 안 된다 — 닫는 문단을 못 봤다. 통과로 안 읽는다")
        return 2
    code, msg = verdict(plan, dec, after)
    print(("✓ " if code == 0 else "") + msg)
    return code


CANARY_PLAN = "-| 144 | 토지이용 면이 없다 | 📄 | 주차장 · 광장 · 공원 · 학교를 지도에서 메운다 |\n"
CANARY_DEC = ("+**안 한 것.** 사람이 지도를 눈으로 보는 일은 `PLAN` 에 남는 사람 몫이다(⑤의 목록). `vworld_uq164`(주차장 · 학교 면)는 "
              "이 행의 범위가 아니다 — 대장에 `raw_only` 로 그대로 서 있고 `unused` 에 든 채다.\n")  # §696 의 옛 닫는 문단 그대로


def selftest() -> int:
    plan_after = "| 7 | 다른 행 |\n| 225 | 후속 |\n"
    ok = verdict(CANARY_PLAN, CANARY_DEC, plan_after)[0] == 1                                   # ★ 카나리아가 빨갛다
    ok &= verdict(CANARY_PLAN, CANARY_DEC.replace("이 행의", "`#225` 가 든다 — 이 행의"), plan_after)[0] == 0   # 실재 행 인용 → 통과
    ok &= verdict(CANARY_PLAN, CANARY_DEC.replace("이 행의", "`#999` 가 든다 — 이 행의"), plan_after)[0] == 1   # 없는 행 → 막음
    ok &= verdict(CANARY_PLAN, CANARY_DEC.replace("이 행의 범위가 아니다", "더 알 수 없어 확인 불가로 닫는다"), plan_after)[0] == 0  # 허용 어휘
    ok &= verdict("", CANARY_DEC, plan_after)[0] == 0                                           # 안 닫았으면 볼 것 없다
    ok &= verdict(CANARY_PLAN, CANARY_DEC.replace("이 행의", "`#144` 가 든다 — 이 행의"), "| 144 | 아직 있다 |\n")[0] == 1       # 닫은 행 자신을 후속으로 못 쓴다
    print("✓ 카나리아가 빨갛게 뜬다" if ok else "✗ 프로브가 죽었다")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    return selftest() if "--selftest" in argv else staged()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

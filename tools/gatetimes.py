#!/usr/bin/env python3
"""
gatetimes.py — `pre-push.gates` 의 **셋째 열(훅 안에서 잰 벽시계 초)**을 잰다.  (PLAN #210)

    uv run python tools/gatetimes.py --measure                 훅을 실제로 돌려 게이트마다 초를 낸다(화면만)
    uv run python tools/gatetimes.py --measure --write         셋째 열을 다시 쓴다
    uv run python tools/gatetimes.py --measure --runs 3        세 번 돌려 중앙값(기본 3)

★★ **셋째 열의 뜻은 「훅 안에서 잰 벽시계」다 — 단독으로 잰 초가 아니다.** 2026-11-08 실측에서 `deadcheck` 가 단독 10.7초인데 훅 안에서 28~29초였다 —
  훅은 게이트를 **병렬로** 띄워 서로 CPU 를 나눈다. 그 조건은 DECISIONS §665 가 이미 정했다(**훅 전체 벽시계 · 게이트 동시 · 8코어**). 이 열을 단독 초로 읽으면
  게이트 하나를 고쳐 얼마나 빨라지는지를 틀리게 어림한다 — 그래서 열이 있는 파일 머리와 이 머리말이 같은 말을 한다.

★ **사람이 손으로 돌린다**(`testpick --measure` 꼴). 훅이 제 초를 쓰면 푸시마다 파일이 바뀐다 — 그래서 훅은 셋째 열을 **읽고 버린다**(`read -r name cmd _secs`).
  재는 것은 **훅 자신이 낸 줄**(`  ✓ 이름   12.3초`)이다 — 따로 시계를 두지 않는다(두 시계는 갈린다).

★ **빈 열은 거짓이다.** 이 도구가 열을 쓴다 — 손으로 안 적고, 안 적으면 열이 없다(훅은 둘째 열까지만 있어도 돈다).
  그러나 일부만 쓰지는 않는다: **게이트가 하나라도 빨갛거나 줄이 안 읽히면 안 쓴다**(빨강의 초는 실패까지 걸린 시간이라 값이 아니다).

IN    `.githooks/pre-push`(실제로 실행한다 — 게이트가 읽는 트리가 **커밋된 깨끗한 트리**여야 한다) · `.githooks/pre-push.gates`
OUT   화면 · `--write` 가 **셋째 열만** 다시 쓴다(주석 · 이름 · 명령은 그대로)
PARAM --runs · --write
밖    **게이트를 고르거나 예산을 판정하지 않는다**(예산은 훅이 말한다). 훅 밖의 환경(CI)에서의 초도 안 잰다. 기계마다 다른 수라 문서에 안 적는다.
부류  조사   사람이 손으로 돌려 수를 내고 멈춘다(DECISIONS §398 — 어느 관문에도 안 올렸다)
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".githooks" / "pre-push"
GATES = ROOT / ".githooks" / "pre-push.gates"
ZERO = "0" * 40

#: 훅이 게이트마다 찍는 줄 — `  ✓ 이름  12.3초` · `  ✗ 이름  12.3초`(빨강은 색 코드가 앞뒤에 붙는다).
_LINE = re.compile(r"^\s*(?:\x1b\[\d+m)?\s*([✓✗])\s+(.+?)\s+(\d+(?:\.\d+)?)초(?:\x1b\[0m)?\s*$")


def parse(out: str) -> dict[str, tuple[bool, float]]:
    """훅 출력 → {게이트 이름: (초록인가, 초)}. 못 읽은 줄은 건너뛴다."""
    got: dict[str, tuple[bool, float]] = {}
    for ln in out.splitlines():
        m = _LINE.match(ln)
        if m:
            got[m.group(2)] = (m.group(1) == "✓", float(m.group(3)))
    return got


def names(path: Path = GATES) -> list[str]:
    return [ln.split("\t")[0] for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def run_hook(root: Path = ROOT) -> str:
    """훅을 **실제로** 돈다 — 푸시할 브랜치 갱신 한 줄을 표준입력으로 준다(`test_prepush_hook` 과 같은 모양)."""
    line = f"refs/heads/part/gatetimes {'1' * 40} refs/heads/part/gatetimes {ZERO}\n"
    r = subprocess.run(["bash", str(root / ".githooks" / "pre-push")], cwd=root, input=line, capture_output=True, text=True, timeout=900, check=False)
    return r.stdout + r.stderr


def merge(runs: list[dict[str, tuple[bool, float]]], expect: list[str]) -> dict[str, float] | str:
    """여러 번의 결과 → {이름: 중앙값}. **하나라도 빨갛거나 빠졌으면 이유 문장**(쓰지 않는다)."""
    for i, r in enumerate(runs, 1):
        miss = [n for n in expect if n not in r]
        if miss:
            return f"{i}번째 실행에서 줄을 못 읽은 게이트가 있다(훅이 게이트를 안 돌았거나 출력 꼴이 바뀌었다): {', '.join(miss)}"
        red = [n for n in expect if not r[n][0]]
        if red:
            return f"{i}번째 실행에서 빨간 게이트가 있다 — 빨강의 초는 값이 아니다: {', '.join(red)}"
    return {n: round(statistics.median(r[n][1] for r in runs), 1) for n in expect}


def write(secs: dict[str, float], path: Path = GATES) -> None:
    """셋째 열만 다시 쓴다. 주석 · 빈 줄 · 이름 · 명령은 글자 그대로 둔다."""
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            out.append(ln)
            continue
        cols = ln.split("\t")
        out.append("\t".join([cols[0], cols[1], f"{secs[cols[0]]:.1f}"]) if cols[0] in secs else ln)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pre-push.gates 셋째 열(훅 안 벽시계 초)을 잰다", formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--measure", action="store_true", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        print("✗ 추적 파일에 안 커밋한 수정이 있다 — 훅이 게이트를 안 돈다(작업 트리를 잰다). 커밋하고 다시:\n" + dirty, file=sys.stderr)
        return 1
    expect = names()
    runs = []
    for i in range(a.runs):
        out = run_hook()
        runs.append(parse(out))
        print(f"  {i + 1}/{a.runs} 번째 — 읽은 게이트 {len(runs[-1])}/{len(expect)}", file=sys.stderr)
    res = merge(runs, expect)
    if isinstance(res, str):
        print(f"✗ 안 썼다 — {res}", file=sys.stderr)
        return 1
    print(f"훅 안 벽시계 초(게이트 동시 · 중앙값 {a.runs}회)")
    for n in expect:
        print(f"  {res[n]:6.1f}  {n}")
    print(f"  합 {sum(res.values()):.1f} (병렬이라 훅 전체 벽시계가 아니다 — 가장 긴 것이 가깝다)")
    if a.write:
        write(res)
        print(f"셋째 열을 {GATES} 에 썼다")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
finish_656_seal.py — §656 가 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_656_seal.py            계획만
    uv run python tools/finish_656_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
MASTER §23-3 에 시험 `tests/test_plan_tables.py` 와 이 파일 자신(§23-2)을 등재한다.
`sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636) — `finish_654_seal.py` 가 선례다. 멱등이다.
앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

IN    docs/MASTER.md
OUT   같은 파일 (--apply 일 때만)
PARAM 없음
부류  생산   문서의 줄을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서)
밖    절이 옳은지는 안 본다(`sealcov` 도 안 본다).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MASTER = Path(__file__).resolve().parent.parent / "docs" / "MASTER.md"
TOOLS_ANCHOR = "| `tools/fetch_api.py` |"
TESTS_ANCHOR = "| `tests/test_snap_groups.py` |"
TOOL = ("tools/finish_656_seal.py",
        "| `tools/finish_656_seal.py` | §656 이 만든 문서 빈 곳을 닫는다 — 새 시험 하나 등재. `sealcov` 는 `--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |")
TEST = ("tests/test_plan_tables.py",
        "| `tests/test_plan_tables.py` | PLAN 의 표 셋(`§1` 행 · `§10-1` 배치 표 · `§10-5` 구획 표)이 같은 행을 같은 식으로 가리키는가 — `planclose` 의 파서를 pytest 안으로 들인다. 열린 행이 판에 있는가 · 무조건 닫는 판이 있는가 · 닫는 수 · 유령 행 · **구획 표와 배치 표가 같은 행을 든다.** 판 배정이 옳은지는 못 본다 |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t = MASTER.read_text(encoding="utf-8")
    new = t
    for (key, row), anchor in ((TOOL, TOOLS_ANCHOR), (TEST, TESTS_ANCHOR)):
        if key in new:
            print(f"이미 등재돼 있다 — 건너뛴다: {key}")
        elif new.count(anchor) != 1:
            print(f"✗ 앵커가 {new.count(anchor)}번 — 하나여야 한다: {anchor}", file=sys.stderr)
            return 1
        else:
            new = new.replace(anchor, row + "\n" + anchor, 1)
            print(f"등재한다: {key}")
    if new != t and a.apply:
        MASTER.write_text(new, encoding="utf-8")
        print("✓ 썼다")
    elif new != t:
        print("(계획만 — --apply 로 쓴다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

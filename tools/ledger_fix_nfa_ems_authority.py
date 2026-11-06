#!/usr/bin/env python3
"""
ledger_fix_nfa_ems_authority.py — `datasets.nfa_ems.authority` 에 받은 경로 괄호를 붙인다.

    uv run python tools/ledger_fix_nfa_ems_authority.py          계획만
    uv run python tools/ledger_fix_nfa_ems_authority.py --apply  실행

§646 이 `nfa_ems` 를 등재하며 괄호 없이 적어 `test_lake` 의 「받은 경로 없음」 래칫이 17 → 18 이 됐다.
상한을 올리지 않고 **꼴을 맞춘다** — 판정기는 `AUTHORITY = ^\\S.*\\S \\((route)\\)$` 이고,
통과하는 항목(`소방청 화재대응조사과 (보도자료 · …)` 등)과 같은 `기관 (경로)` 꼴이다.
yaml.dump 금지(주석이 날아간다) — 블록 안의 그 한 줄만 텍스트로 바꾼다. 멱등.

IN    sources.yaml
OUT   sources.yaml (--apply 일 때만)
PARAM 없음
부류  생산   대장을 고친다
밖    다른 항목의 authority 는 안 건드린다(남은 17 은 문서 작업이다 — 상한이 지킨다).
"""
from __future__ import annotations

import sys
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "sources.yaml"
OLD = "    authority: 소방청 소방안전 빅데이터 플랫폼\n"
NEW = "    authority: 소방청 (소방안전 빅데이터 플랫폼 내려받기)\n"


def main() -> int:
    lines = LEDGER.read_text(encoding="utf-8").split("\n")
    start = lines.index("  nfa_ems:")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("  ") and not lines[i].startswith("   ")), len(lines))
    hit = [i for i in range(start, end) if lines[i] + "\n" in (OLD, NEW)]
    if len(hit) != 1:
        print(f"✗ nfa_ems 블록에서 authority 줄을 정확히 하나 못 찾았다: {hit}", file=sys.stderr)
        return 1
    if lines[hit[0]] + "\n" == NEW:
        print("이미 고쳐져 있다")
        return 0
    print(f"sources.yaml:{hit[0] + 1}\n  - {OLD.strip()}\n  + {NEW.strip()}")
    if "--apply" in sys.argv:
        lines[hit[0]] = NEW.rstrip("\n")
        LEDGER.write_text("\n".join(lines), encoding="utf-8")
    else:
        print("계획만 했다. 쓰려면 --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

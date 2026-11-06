#!/usr/bin/env python3
"""
finish_655_seal.py — §655 가 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_655_seal.py            계획만
    uv run python tools/finish_655_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
MASTER §23-3 에 시험 `tests/test_ops_token_wiring.py` 와 이 파일 자신(§23-2)을 등재한다.
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
TOOL = ("tools/finish_655_seal.py",
        "| `tools/finish_655_seal.py` | §655 가 만든 문서 빈 곳을 닫는다 — 새 시험 하나 등재. `sealcov` 는 `--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |")
TEST = ("tests/test_ops_token_wiring.py",
        "| `tests/test_ops_token_wiring.py` | 중계 토큰이 배포 사슬을 끝까지 건너는가 — `deploy.yml` 두 곳 → `stage-site` → `build-navi` → `VITE_OPS_TOKEN`. YAML 을 **파싱해** 읽는다(출처는 secrets · 이음매는 값을 그대로 건넨다 · 액션이 vite 가 읽는 이름으로 준다 · 주소만 있고 토큰이 없으면 경고하고 값은 안 찍는다). **저장소 밖**(Secrets 에 값이 있는가 · 배포본에서 실제로 이어지는가)은 못 본다 |")


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

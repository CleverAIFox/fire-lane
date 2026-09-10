#!/usr/bin/env python3
"""
b2_close122.py — B2 **종결.** §122 두 줄을 고친다.

    uv run python tools/b2_close122.py --apply

★ 두 번 다 내가 만든 것이고 두 번 다 규약이 옳다.

  ㊻ bare `§125~§127`
      `b2_last ㊳` 이 "팀 문서의" 를 앞에 붙였는데 검사는 앞 12자에
      `MASTER · PLAN · DECISIONS · 기획서 · workflow · playbook` 만 본다.
      "팀 문서" 는 그 목록에 없다. **§ 기호 자체를 안 쓰는 것**이 맞다 —
      이 저장소의 `§N` 은 이 저장소의 절을 뜻하고, 남의 문서 절 번호에
      그 기호를 쓰면 그 규약이 흐려진다.

  ㊼ 강제자 줄 없음
      2026-08-24 이후 절은 강제자를 지목해야 한다. **없으면 '없다' 고
      적는다** — 없다는 사실 자체가 기록이어야 한다(test_doc_style:296).
      §122 의 강제자는 실재한다. `docnum_check` 다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEC = ROOT / "docs" / "DECISIONS.md"


def edit(old: str, new: str, why: str, apply: bool) -> int:
    s = DEC.read_text(encoding="utf-8")
    n = s.count(old)
    if n == 0:
        print(f"  = {why} (이미 적용)")
        return 0
    if n > 1:
        print(f"  ✗ {why} — {n}건. 모호하면 안 바꾼다")
        return 1
    print(f"  {'→' if apply else '·'} {why}")
    if apply:
        DEC.write_text(s.replace(old, new, 1), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    A = ap.parse_args().apply
    print(f"{'적용' if A else 'dry-run — --apply 로 실행'}\n")
    f = 0

    print("── ㊻ bare § 를 안 쓴다")
    f += edit(
        "코드를 받게 되면 그때 팀 문서의 §125~§127(범위·건물 확대 ·\n"
        "오매칭 진단 · 중심선 보정)로 들어온 판단을 여기 흡수한다.\n"
        "★ 그 번호는 **팀 쪽 문서의 절**이고 이 저장소에는 없다.",
        "코드를 받게 되면 팀 문서의 결정 셋(범위·건물 확대 · 오매칭 진단 ·\n"
        "중심선 보정)을 여기 흡수한다.\n"
        "★ 번호는 적지 않는다. 이 저장소에서 `§N` 은 **이 저장소의 절**을\n"
        "  뜻한다(MASTER §0-2). 남의 문서 절 번호에 같은 기호를 쓰면 그\n"
        "  규약이 흐려지고, 검사도 그것을 실체 없는 참조로 잡는다.",
        "§122 — bare §125~§127 제거", A)

    print("\n── ㊼ 강제자 줄")
    f += edit(
        "> 2026-09-10 · 오창준\n",
        "> 2026-09-10 · 오창준\n"
        "\n"
        "강제자  `tools/docnum_check.py` — 문서 숫자를 산출물과 대조한다.\n"
        "        산출물 없이 문서만 1,281 로 고치면 여기서 잡힌다.\n"
        "        지금 이 저장소의 산출물은 1,101구간이고 그 검사가 통과한다.\n",
        "§122 — 강제자 지목 (docnum_check)", A)

    print(f"\n{'실패 ' + str(f) + '건' if f else '전부 통과'}")
    if A and not f:
        print("\n검증 —")
        print("  uv run pytest tests/test_doc_style.py "
              "tests/test_declaration_sync.py -q")
        print("  bash tools/verify.sh")
        print("\n이 파일도 일회성이다 —")
        print("  mv tools/b2_close122.py tools/batches/")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())

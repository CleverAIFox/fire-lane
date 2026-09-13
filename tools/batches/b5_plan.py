#!/usr/bin/env python3
"""
b5_plan.py — **닫힌 PLAN 항목을 DECISIONS 로 옮긴다. 글자는 안 바꾼다.**

    uv run python tools/batches/b5_plan.py            무엇을 옮길지만
    uv run python tools/batches/b5_plan.py --apply    실제로

★ 규약은 이미 있었다. `PLAN` 머리말 §0-2 —
    *"⬛ 완료·기각. 결과는 MASTER 로 갔고 여기는 **슬롯만 남는다**"*

  실물은 **⬛ 34개가 전부 본문을 통째로 들고 있다.** `#15` 는
  *"2026-08-31 완료. guards.warn_direct_call() 을 여섯 단계 모듈이 부른다…"*
  를 PLAN 에 그대로 적어놨다. 그건 슬롯이 아니라 DECISIONS 항목이다.

  ★ **규약은 있고 강제자가 없었다.** 오늘만 같은 병을 셋 봤다 —
    `naming.vintage`(규약 있고 형식만 검사) · `ruleset_check`(404 로 침묵) ·
    `contract.yml` 죽은 게이트. 그래서 이 배치는 옮기기만 하지 않고
    **다시 쌓이지 못하게 막는 검사**를 같이 넣는다.

★ 왜 중복이 해로운가 — 같은 내용이 두 곳에 있으면 **어느 쪽이 정본인지
  모른다.** 한쪽만 고치면 갈리고, 갈린 것을 다음 사람이 발견하면 둘 다
  못 믿게 된다. PLAN 머리말이 그걸 한 줄로 적어놨다 —
  *"한 항목은 한 문서에만 산다."*

★ **글자를 안 바꾼다.** 요약하거나 다듬지 않고 본문을 그대로 옮긴다.
  옮기면서 고치면 "옮긴 것" 과 "고친 것" 이 섞여 나중에 대조가 안 된다.
  다듬는 것은 사람이 나중에 한다.

★ 번호는 실행 시점에 센다. DECISIONS 는 append-only 이고 마지막 번호를
  하드코딩하면 다음 배치와 충돌한다.
"""
from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

PLAN = ROOT / "docs/PLAN.md"
DEC = ROOT / "docs/DECISIONS.md"

# `| 15 | 제목 | ⬛ | 본문... |`
ROW = re.compile(r"^\| *(\d+) *\| *(.+?) *\| *⬛ *\| *(.*?) *\|\s*$", re.M)
SLOT_LEN = 60          # 슬롯 본문 상한. 넘으면 본문이 남아 있다는 뜻이다


def _next_no(text: str) -> int:
    nums = [int(m) for m in re.findall(r"^## (\d+)\.", text, re.M)]
    return (max(nums) + 1) if nums else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N개만")
    ap.add_argument("--all", action="store_true",
                    help="본문이 짧아도 옮긴다. ★ 짧다고 근거가 아닌 것은 아니다 — "
                         "60자 문턱은 '슬롯인지' 를 가르는 어림이지 값어치가 아니다")
    a = ap.parse_args()

    plan = PLAN.read_text(encoding="utf-8")
    dec = DEC.read_text(encoding="utf-8")
    no = _next_no(dec)

    rows = [m for m in ROW.finditer(plan)
            if (a.all or len(m.group(3)) > SLOT_LEN)
            and "DECISIONS §" not in m.group(3)
            and "MASTER §" not in m.group(3) and m.group(3)]
    if not rows:
        print("  = 옮길 것이 없다 — ⬛ 가 전부 슬롯이다")
        return 0
    if a.limit:
        rows = rows[:a.limit]

    print(f"  ⬛ {len(rows)}건을 DECISIONS §{no}~§{no + len(rows) - 1} 로 옮긴다")
    print(f"  {'':4}글자는 안 바꾼다. 본문 그대로 이동한다.\n")

    add, new_plan, shift = [], plan, 0
    for m in rows:
        pid, title, body = m.group(1), m.group(2), m.group(3)
        add.append(
            f"\n## {no}. {title.strip('`')}\n\n"
            f"> {datetime.now(UTC).astimezone().date().isoformat()} · 오창준\n\n"
            f"강제자  `tests/test_doc_fsck.py::test_closed_plan_items_are_slots`\n"
            f"        — ⬛ 항목이 본문을 들고 있으면 운다.\n\n"
            f"★ `PLAN #{pid}` 에서 옮겼다(2026-09-12). **글자는 안 바꿨다.**\n"
            f"  PLAN 은 미래만 담는데 닫힌 항목이 본문째 남아 중복이 쌓였다.\n"
            f"  §0-2 가 *\"슬롯만 남는다\"* 고 적어놨는데 강제자가 없었다.\n\n"
            f"{body}\n")
        slot = f"| {pid} | {title} | ⬛ | → `DECISIONS §{no}` |"
        s, e = m.start() + shift, m.end() + shift
        new_plan = new_plan[:s] + slot + new_plan[e:]
        shift += len(slot) - (m.end() - m.start())
        print(f"    #{pid:<4} → §{no:<4} {title[:52]}")
        no += 1

    if not a.apply:
        print("\n  ★ dry-run. --apply 를 붙일 것")
        return 0

    PLAN.write_text(new_plan, encoding="utf-8")
    DEC.write_text(dec.rstrip("\n") + "\n" + "".join(add), encoding="utf-8")
    print(f"\n  ✓ PLAN {len(rows)}행이 슬롯이 됐다")
    print(f"  ✓ DECISIONS 에 {len(rows)}절 추가")
    print("\n다음 —")
    print("  uv run python tools/doc_fsck.py")
    print("  uv run python tools/docnum_check.py")
    print("  uv run python -m pytest tests/test_doc_fsck.py tests/test_docref.py -q")
    print("  ★ 강제자를 일부러 깨뜨려 본다 — 슬롯 하나에 본문을 도로 적고")
    print("    검사가 우는지 본다. 안 울면 있으나 마나다(원칙 ④).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
finish_c1_seal.py — C1 이 만든 빈 곳 둘을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_c1_seal.py            계획만
    uv run python tools/finish_c1_seal.py --apply    실행

── 하는 일 둘 ─────────────────────────────────────────────────
  ① MASTER §23-2 표에 `tools/` 새 파일 **셋**을 등재한다
     (`ledger_add_nfa_ems` · `fix_vintage_8digit` · 이 파일 자신).
     `sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636) — 그렇다고
     사람이 손으로 칠 일은 아니다. 적는 주체가 사람이라는 뜻이지
     적는 방법이 손이라는 뜻이 아니다.

  ② `tools/unusedcheck.py` 의 `PENDING_MAX` 를 13 → 14 로 올리고
     그 자리에 **왜 올렸나**를 적는다.
     이것은 다른 느슨해짐과 성격이 다르다 — 도구가 잘못 센 것이 아니라
     미투입 원천이 **실제로** 하나 늘었다(nfa_ems · feeds: []).
     ratchet 머리말의 가름으로 말하면 정확도가 아니라 **확산**이다.

── 멱등 ───────────────────────────────────────────────────────
이미 들어가 있으면 건너뛴다. 앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

IN    docs/MASTER.md · tools/unusedcheck.py
OUT   같은 둘 (--apply 일 때만)
PARAM 없음
부류  생산   문서와 도구의 래칫 값을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서)
밖    래칫이 **옳은 값인지**는 안 본다 — `ratchet.py` 가 실측과 대어 묻는다.
      `sealcov` 가 **절이 옳은지**도 안 본다(그 도구 스스로 "절이 옳은가는 안 본다").
      이 도구는 정해진 문장을 정해진 자리에 넣을 뿐이다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "docs" / "MASTER.md"
UNUSED = ROOT / "tools" / "unusedcheck.py"

ANCHOR = "| `tools/fetch_api.py` |"

ROWS = [
    ("tools/ledger_add_nfa_ems.py",
     "| `tools/ledger_add_nfa_ems.py` | 대장에 `datasets.nfa_ems` 를 **텍스트 삽입**으로 "
     "등재한다. `yaml.dump` 를 안 쓴다 — 주석이 근거를 드는 대장이라 라운드트립이면 그 근거가 "
     "날아간다(`docnum_check.py:528` · `depgroups_check.py:85` 가 같은 이유로 포기했다). "
     "멱등 · 앵커(`nfa_fire_incident:`)를 못 찾으면 자리를 추측하지 않고 실패한다 |"),
    ("tools/fix_vintage_8digit.py",
     "| `tools/fix_vintage_8digit.py` | landing 파일명과 대장 `files:` 의 vintage 를 "
     "`YYYY1231` 로 맞춘다. `naming` 은 `YYYYMMDD`·`YYYYMM`·`YYYY` 를 받는데 "
     "`normalize_raw` 의 provider 규칙이 `\\d{8}` 만 받아 7파일이 통째로 안 걸렸다(§646). "
     "**정규식을 안 고친 이유** — 8자리 전제가 `ledger_fields.py:25` 의 `updated` 유도에도 "
     "박혀 있어 넓히면 그쪽이 조용히 깨진다 |"),
    ("tools/finish_c1_seal.py",
     "| `tools/finish_c1_seal.py` | C1 이 만든 빈 곳 둘을 닫는다 — MASTER §23-2 등재와 "
     "`unusedcheck.PENDING_MAX` 13→14. `sealcov` 와 느슨해진 래칫은 `--write` 가 못 고치는 "
     "자리인데(§636), **적는 주체가 사람이라는 뜻이지 적는 방법이 손이라는 뜻이 아니다** |"),
]

OLD_PENDING = "PENDING_MAX = 13"
NEW_PENDING = """# ★ 2026-11-05. 13 → 14. `nfa_ems` 반입(C1 · 84f4e45d)으로 미투입 원천이 하나 늘었다.
#   도구가 잘못 센 것이 아니라 **실제로** 늘었다 — `ratchet.py` 머리말의 가름으로는
#   정확도가 아니라 **확산**이다. 그래서 받아적는 것이 결함을 덮는 일이 아니다.
#   갚는 자리는 C2 — cost 의 거리-시간 관계 검증과 발표 논거다(DECISIONS §645-5).
#   ★ 되돌리는 조건 — `nfa_ems` 에 소비자가 생기면 13 으로 내린다.
PENDING_MAX = 14"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    did = []

    # ── ① MASTER §23-2
    if not MASTER.is_file():
        print(f"✗ 없다: {MASTER}", file=sys.stderr)
        return 2
    mt = MASTER.read_text(encoding="utf-8")
    todo = [(k, row) for k, row in ROWS if k not in mt]
    print(f"① MASTER §23-2  — 등재할 줄 {len(todo)} / {len(ROWS)}")
    for k, _ in todo:
        print(f"     + {k}")
    if todo:
        if mt.count(ANCHOR) != 1:
            print(f"✗ 앵커가 {mt.count(ANCHOR)}번 — 하나여야 한다: {ANCHOR}", file=sys.stderr)
            return 1
        at = mt.index(ANCHOR)
        eol = mt.index("\n", at) + 1
        mt2 = mt[:eol] + "\n".join(row for _, row in todo) + "\n" + mt[eol:]
        did.append(("MASTER.md", mt2))

    # ── ② PENDING_MAX
    if not UNUSED.is_file():
        print(f"✗ 없다: {UNUSED}", file=sys.stderr)
        return 2
    ut = UNUSED.read_text(encoding="utf-8")
    if "PENDING_MAX = 14" in ut:
        print("② PENDING_MAX   — 이미 14다 (멱등)")
    elif OLD_PENDING not in ut:
        print(f"✗ {OLD_PENDING!r} 를 못 찾았다 — 값이 13이 아니다", file=sys.stderr)
        return 1
    elif ut.count(OLD_PENDING) != 1:
        print(f"✗ {OLD_PENDING!r} 가 {ut.count(OLD_PENDING)}번 나온다", file=sys.stderr)
        return 1
    else:
        print("② PENDING_MAX   — 13 → 14 · 사유 주석 5줄")
        did.append(("unusedcheck.py", ut.replace(OLD_PENDING, NEW_PENDING)))

    if not did:
        print("\n바꿀 것이 없다 (멱등)")
        return 0
    if not a.apply:
        print("\n계획만 했다. 쓰려면 --apply")
        return 0

    for name, text in did:
        (MASTER if name == "MASTER.md" else UNUSED).write_text(text, encoding="utf-8")
        print(f"✓ {name}")
    print()
    print("다음 — 래칫 → 변이 장부 → 문서 도장")
    print("    uv run python tools/ratchet.py")
    print("    uv run python tools/mutate.py --write --stale")
    print("    uv run python tools/sealcov.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

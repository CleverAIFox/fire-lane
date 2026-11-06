#!/usr/bin/env python3
"""
finish_648_seal.py — §648 이 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_648_seal.py            계획만
    uv run python tools/finish_648_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
  ① MASTER §23-2 에 `tools/` 파일 둘을 등재한다 — `ledger_extract`(범용 추출 선언 도구) · 이 파일 자신.
  ② MASTER 의 `ledger_contract_nfa_ems` 행을 「비웠다 · 새 도구를 가리킨다」로 고친다(낡은 설명을 두면 다음 사람이 그 도구로 대장을 고치려 든다).
  ③ MASTER 의 `extract_decl.py` · `read/extract.py` 행에 `upper_strip` · `scope_max` 를 더한다.
  ④ MASTER §23-3 에 시험 `tests/test_ledger_extract.py` 한 줄을 등재한다(`sealcov` 빈 곳 — 새 시험 파일도 절이 지목해야 한다).

`sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636). 적는 주체가 사람이라는 뜻이지 적는 방법이 손이라는 뜻이 아니다 — `finish_647_seal.py` 가 선례다.
멱등이다. 앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

IN    docs/MASTER.md
OUT   같은 파일 (--apply 일 때만)
PARAM 없음
부류  생산   문서의 줄을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서)
밖    절이 옳은지는 안 본다(`sealcov` 도 안 본다).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MASTER = Path(__file__).resolve().parent.parent / "docs" / "MASTER.md"
ANCHOR = "| `tools/fetch_api.py` |"

ROWS = [
    ("tools/ledger_extract.py",
     "| `tools/ledger_extract.py` | 대장 `datasets.<키>.contract` 에 **추출 선언**(normalize_columns · filter · scope_min · scope_max)을 텍스트로 넣는 **범용** 도구다 — "
     "`--key` · `--normalize` · `--filter COL=VAL`(반복 = AND) · `--scope-min` · `--scope-max`. 옛 `ledger_contract_nfa_ems` 가 단일 조건을 박아 406,168행을 냈다(§647) · "
     "「동명동」도 세 곳이다(§648). **쓰기 전에 `extract_decl.problems` 에 태워** 잘못된 선언은 안 쓴다 · 같은 선언이면 멱등 · 다른 선언이면 `--replace` 없이는 거절 · "
     "기존 블록에 주석이 있으면 거절한다(텍스트로 다시 쓰면 날아간다) |"),
    ("tools/finish_648_seal.py",
     "| `tools/finish_648_seal.py` | §648 이 만든 문서 빈 곳을 닫는다 — 이 절의 도구 둘 등재 · `ledger_contract_nfa_ems` 행 갱신 · `extract` 두 행의 갱신. "
     "`sealcov` 는 `--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |"),
]
TEST_ANCHOR = "| `tests/test_snap_groups.py` |"
TEST_ROW = ("| `tests/test_ledger_extract.py` | 범용 추출 선언 도구가 **대장 텍스트를 안전하게 고치는가** — 같은 선언은 멱등 · 다른 선언은 `--replace` 없이 거절 · 주석 있는 블록은 거절 · "
            "**잘못된 선언은 파일에 안 쓴다**(정규화 뒤 이름 · schema 에 없는 칸 · 상한 < 하한) |")
OLD_ROW = re.compile(r"^\| `tools/ledger_contract_nfa_ems\.py` \|.*$", re.M)
NEW_ROW = ("| `tools/ledger_contract_nfa_ems.py` | **비웠다.** `tools/ledger_extract.py` 를 가리키고 종료 2 로 안내만 한다(§648). 이 도구가 nfa_ems 에 박은 단일 조건 필터가 광주 밖 다섯 광역시를 섞어 "
           "406,168행을 냈다(§647). 지우지 않은 까닭 — MASTER 등재 · DECISIONS · 문서 도장 · `finish_647_seal.py` 가 이 경로를 가리킨다 |")
REPL = [
    ("`normalize_columns` · `filter`({column, equals} 하나 또는 그 **목록 = AND**)가 읽는 갈래",
     "`normalize_columns`(`lower_strip` · `upper_strip` — 출력 칸 이름이 하류의 이름과 같은 쪽) · `filter`({column, equals} 하나 또는 그 **목록 = AND**) · `scope_max`(상한)가 읽는 갈래"),
    ("판정 폐포 밖(DECISIONS §646 · §647) |",
     "판정 폐포 밖 · `valueprofile` 이 추출 항목은 슬라이스를 읽는다(DECISIONS §646 · §647 · §648) |"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t = MASTER.read_text(encoding="utf-8")
    new = t
    todo = [(k, r) for k, r in ROWS if k not in t]
    print(f"① MASTER §23-2 — 등재할 줄 {len(todo)} / {len(ROWS)}")
    if todo:
        if t.count(ANCHOR) != 1:
            print(f"✗ 앵커가 {t.count(ANCHOR)}번 — 하나여야 한다: {ANCHOR}", file=sys.stderr)
            return 1
        new = new.replace(ANCHOR, "\n".join(r for _, r in todo) + "\n" + ANCHOR, 1)
    if NEW_ROW in new:
        print("② 이미 비웠다고 적혀 있다 — 건너뛴다")
    else:
        if len(OLD_ROW.findall(new)) != 1:
            print("✗ ledger_contract_nfa_ems 행이 하나가 아니다", file=sys.stderr)
            return 1
        new = OLD_ROW.sub(lambda _m: NEW_ROW, new, count=1)
        print("② ledger_contract_nfa_ems 행을 고친다")
    for old, rep in REPL:
        if rep in new:
            print("③ 이미 들어가 있다 — 건너뛴다")
            continue
        if new.count(old) < 1:
            print(f"✗ 앵커가 없다: {old[:40]}…", file=sys.stderr)
            return 1
        i = new.index(old)
        new = new[:i] + rep + new[i + len(old):]
        print(f"③ 고친다: {old[:40]}…")
    if TEST_ROW[:40] in new:
        print("④ 이미 등재돼 있다 — 건너뛴다")
    elif new.count(TEST_ANCHOR) != 1:
        print(f"✗ 앵커가 {new.count(TEST_ANCHOR)}번 — 하나여야 한다: {TEST_ANCHOR}", file=sys.stderr)
        return 1
    else:
        new = new.replace(TEST_ANCHOR, TEST_ROW + "\n" + TEST_ANCHOR, 1)
        print("④ tests/test_ledger_extract.py 를 등재한다")
    if new != t and a.apply:
        MASTER.write_text(new, encoding="utf-8")
        print("✓ 썼다")
    elif new != t:
        print("(계획만 — --apply 로 쓴다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
finish_647_seal.py — §647 이 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_647_seal.py            계획만
    uv run python tools/finish_647_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
  ① MASTER §23-2 표에 `tools/` 파일 둘을 등재한다 — `ledger_contract_nfa_ems`(§646 이 올렸고 `sealcov` 빈 곳이다) · 이 파일 자신.
  ② MASTER 의 `extract_decl.py` · `read/extract.py` 행을 §647 의 사실로 고친다(filter 목록 AND · `--extract-from` · 원본을 내린 항목의 계보 보존).
     낡은 설명을 두면 다음 사람이 `{column, equals}` 하나뿐이라고 읽는다.

`sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636). 적는 주체가 사람이라는 뜻이지 적는 방법이 손이라는 뜻이 아니다 — `finish_c1_seal.py` 가 선례다.

멱등이다. 앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

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
ANCHOR = "| `tools/fetch_api.py` |"

ROWS = [
    ("tools/ledger_contract_nfa_ems.py",
     "| `tools/ledger_contract_nfa_ems.py` | 대장 `datasets.nfa_ems` 에 `contract` 블록(추출 선언)을 **텍스트 삽입**으로 넣는다(§646). "
     "추출 선언을 든 항목은 `hits` 전부를 읽으므로 `primary` 요구가 사라지고 무계약 래칫이 돌아온다 — 래칫을 올려 덮지 않고 원인을 없앴다. "
     "★ 이 도구가 넣은 `filter` 는 `sgg_nm=동구` **하나**였고 광주 외 다섯 광역시의 동구를 섞었다(406,168행) — §647 이 시도 조건을 더해 고쳤다. "
     "멱등 · 앵커를 못 찾으면 실패한다 |"),
    ("tools/finish_647_seal.py",
     "| `tools/finish_647_seal.py` | §647 이 만든 문서 빈 곳을 닫는다 — 이 절의 도구 둘 등재와 `extract` 두 행의 갱신. `sealcov` 는 "
     "`--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |"),
]

REPL = [("`normalize_columns` · `filter`({column, equals})가 읽는 갈래",
         "`normalize_columns` · `filter`({column, equals} 하나 또는 그 **목록 = AND**)가 읽는 갈래")]
ROW_EXTRACT_OLD = "계보에 입력 파일별 sha · 필터 전 · 후 행 수를 남긴다. 0행 · `scope_min` 미달은 FAIL. 판정 폐포 밖(DECISIONS §646) |"
ROW_EXTRACT_NEW = ("계보에 입력 파일별 sha · **바이트** · 필터 전 · 후 행 수를 남긴다. 0행 · `scope_min` 미달은 FAIL(★ 하한은 **과다**를 못 잡는다 — 「동구」가 여섯 광역시에 있어 "
                   "단일 조건이 406,168행을 냈다 · 시도 조건 AND 로 고쳤다 · §647). `paths` · `source_dir`(`ingest --only <키> --extract-from <폴더>` — 전국본을 raw 에 안 올리고 제자리에서 읽는다) · "
                   "`kept`(원본을 `status: missing` 으로 내린 항목의 지난 계보 · 산출물을 보존). 판정 폐포 밖(DECISIONS §646 · §647) |")


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
    steps = [(REPL[0][0], REPL[0][1]), (ROW_EXTRACT_OLD, ROW_EXTRACT_NEW)]
    for old, rep in steps:
        if rep in new:
            print("② 이미 들어가 있다 — 건너뛴다")
            continue
        if new.count(old) != 1:
            print(f"✗ 앵커가 {new.count(old)}번 — 하나여야 한다: {old[:40]}…", file=sys.stderr)
            return 1
        new = new.replace(old, rep, 1)
        print(f"② 고친다: {old[:40]}…")
    if new != t and a.apply:
        MASTER.write_text(new, encoding="utf-8")
        print("✓ 썼다")
    elif new != t:
        print("(계획만 — --apply 로 쓴다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
ledger_contract_nfa_ems.py — datasets.nfa_ems 에 contract 블록을 넣는다.

    uv run python tools/ledger_contract_nfa_ems.py            계획만
    uv run python tools/ledger_contract_nfa_ems.py --apply    실행

── 왜 ─────────────────────────────────────────────────────────
2026-11-05 반입(84f4e45d)에서 contract 블록 없이 등재했다. 그 탓에 둘이 울었다 —

    ledger_check   files 7개인데 primary 가 없다
                   (「하나만 읽는데 files 여럿 → primary 요구」)
    contract_vocab 무계약 래칫 38 → 39

둘 다 추출 선언 하나로 풀린다. §646 의 read/extract.py 가 추출 선언을 든 항목은
hits 전부를 읽으므로 primary 요구가 사라지고, schema 를 같이 적으면 무계약도
돌아온다. 래칫을 올려 덮는 것이 아니라 **원인을 없앤다.**

── 선언 ───────────────────────────────────────────────────────
    normalize_columns  2024 경계에서 칸 이름이 대문자 71/71 → 소문자 0/71 로 갈린다.
                       이걸 흡수하지 않으면 139행 사고가 반복된다(§644-3).
    filter             sgg_nm == 동구. 환자 발생지 기준이고 전수 47,632행이다.
    scope_min          40000. 실측 47,632 에 여유를 둔다 — 필터가 조용히 빗나가면
                       행 수가 급감하므로 하한이 그것을 잡는다.
    required_cols      ★ **정규화 뒤 소문자**로 적는다. extract_decl 이 그것을 검사한다.

── 멱등 ───────────────────────────────────────────────────────
이미 contract 가 있으면 아무것도 안 한다. 앵커를 못 찾으면 자리를 추측하지 않고 실패.

IN    sources.yaml
OUT   sources.yaml (--apply 일 때만)
PARAM 없음
부류  생산   대장을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 대장)
밖    선언이 **문법에 맞는지**는 안 본다 — `extract_decl` · `ledger_check` 가 묻는다.
      필터가 실제로 몇 행을 남기는지도 안 본다 — `ingest` 가 돌 때 계보에 남는다.
      이 도구는 블록 하나를 정해진 자리에 끼워 넣을 뿐이다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "sources.yaml"

KEY = "  nfa_ems:\n"
ANCHOR = "    kind: csv_table\n    encoding: utf-8\n"   # nfa_ems 안의 그 두 줄

BLOCK = """    contract:
      normalize_columns: lower_strip
      filter:
        column: sgg_nm
        equals: 동구
      scope_min: 40000
      required_cols: [sgg_nm, grnds_dstnc, dclr_tm, dspt_tm, grnds_arvl_tm, ptn_cntc_tm]
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not LEDGER.is_file():
        print(f"✗ 대장이 없다: {LEDGER}", file=sys.stderr)
        return 2
    text = LEDGER.read_text(encoding="utf-8")

    if KEY not in text:
        print("✗ datasets.nfa_ems 가 없다 — 먼저 ledger_add_nfa_ems.py 를 돌려라",
              file=sys.stderr)
        return 1

    start = text.index(KEY)
    nxt = text.find("\n  nfa_fire_incident:", start)
    if nxt < 0:
        print("✗ nfa_ems 블록의 끝을 못 찾았다", file=sys.stderr)
        return 1
    body = text[start:nxt]

    if "    contract:" in body:
        print("이미 contract 블록이 있다 — 아무것도 안 한다 (멱등)")
        return 0

    if body.count(ANCHOR) != 1:
        print(f"✗ 앵커가 nfa_ems 안에 {body.count(ANCHOR)}번 — 하나여야 한다", file=sys.stderr)
        print(f"   찾은 것: {ANCHOR!r}", file=sys.stderr)
        return 1

    at = start + body.index(ANCHOR) + len(ANCHOR)
    new = text[:at] + BLOCK + text[at:]

    print(f"대장   {LEDGER}")
    print(f"자리   nfa_ems 의 `encoding: utf-8` 바로 뒤 ({text[:at].count(chr(10)) + 1}행)")
    print(f"삽입   {BLOCK.count(chr(10))}줄")
    print()
    print(BLOCK.rstrip())

    if not a.apply:
        print("\n계획만 했다. 쓰려면 --apply")
        return 0

    LEDGER.write_text(new, encoding="utf-8")
    print("\n✓ 썼다. 다음으로 검증한다 —")
    print("    uv run python -m firelane.contract --declared 2>&1 | tail -20")
    print("    uv run python tools/ledger_check.py 2>&1 | tail -20")
    print("    uv run python tools/ledger_schema.py && uv run python tools/ledger_fields.py")
    print("    uv run python tools/ratchet.py            # 무계약이 38 로 돌아와야 한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

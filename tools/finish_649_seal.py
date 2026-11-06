#!/usr/bin/env python3
"""
finish_649_seal.py — §649 가 만든 문서 빈 곳을 닫는다. 손으로 안 적는다.

    uv run python tools/finish_649_seal.py            계획만
    uv run python tools/finish_649_seal.py --apply    실행

── 하는 일 ────────────────────────────────────────────────────
  ① MASTER §23-2 에 이 파일 자신을 등재한다.
  ② MASTER 의 `extract_decl.py` · `ledger_extract.py` 행에 `one_of`(필터 값 여럿 중 하나 · §649)를 더한다.
  ③ MASTER 의 「`retired` 4종」 세 곳을 8종으로 고친다 — §649-2 가 수동 파생본 넷을 retired 로 선언했다(`docnum_check` 가 「대장 retired 종수 [4, 4, 4] → 8」로 잡았다).
     낡은 설명을 두면 다음 사람이 `{column, equals}` 만 있다고 읽고 이름이 바뀐 값을 `equals` 로 걸어 행을 잃는다.

`sealcov` 는 `ratchet --write` 가 못 고치는 자리다(§636). 적는 주체가 사람이라는 뜻이지 적는 방법이 손이라는 뜻이 아니다 — `finish_648_seal.py` 가 선례다.
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
ROW = ("| `tools/finish_649_seal.py` | §649 가 만든 문서 빈 곳을 닫는다 — 이 도구 등재와 `extract_decl` · `ledger_extract` 두 행에 `one_of` 를 더한다. "
       "`sealcov` 는 `--write` 가 못 고치는 자리(§636)라 스크립트로 넣는다 |")
ALL = [("`datasets` 88종 · `retired` 4종", "`datasets` 88종 · `retired` 8종", 2)]       # (옛, 새, 있어야 하는 횟수)
REPL = [
    ("현재 `retired` 4종이 있다(NGI 원본 20도엽 · 기본도 옛 판 · 건축물대장 동구 판 · 도로명주소 건물DB 전남광주 판 — DECISIONS §183-2)",
     "현재 `retired` 8종이 있다(NGI 원본 20도엽 · 기본도 옛 판 · 건축물대장 동구 판 · 도로명주소 건물DB 전남광주 판 · 소방청 수동 파생본 넷(119 · 화재 · 구조 · 소방대상물 · 전국본 재추출로 대체 — DECISIONS §649-2) — DECISIONS §183-2)"),
    ("`filter`({column, equals} 하나 또는 그 **목록 = AND**)",
     "`filter`({column, equals} 또는 {column, **one_of**(이름이 바뀐 값 여럿 중 하나 · §649)} 하나 또는 그 **목록 = AND**)"),
    ("`--filter COL=VAL`(반복 = AND)",
     "`--filter COL=VAL`(반복 = AND) · `--one-of COL=A|B`(이름이 바뀐 값 · 다른 조건과 AND)"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t = MASTER.read_text(encoding="utf-8")
    new = t
    if ROW[:40] in t:
        print("① 이미 등재돼 있다 — 건너뛴다")
    elif t.count(ANCHOR) != 1:
        print(f"✗ 앵커가 {t.count(ANCHOR)}번 — 하나여야 한다: {ANCHOR}", file=sys.stderr)
        return 1
    else:
        new = new.replace(ANCHOR, ROW + "\n" + ANCHOR, 1)
        print("① tools/finish_649_seal.py 를 등재한다")
    for old, rep in REPL:
        if rep in new:
            print("② 이미 들어가 있다 — 건너뛴다")
            continue
        if new.count(old) != 1:
            print(f"✗ 앵커가 {new.count(old)}번 — 하나여야 한다: {old[:40]}…", file=sys.stderr)
            return 1
        new = new.replace(old, rep, 1)
        print(f"② 고친다: {old[:40]}…")
    for old, rep, n in ALL:
        if rep in new and old not in new:
            print("③ 이미 들어가 있다 — 건너뛴다")
        elif new.count(old) != n:
            print(f"✗ 앵커가 {new.count(old)}번 — {n}번이어야 한다: {old}", file=sys.stderr)
            return 1
        else:
            new = new.replace(old, rep)
            print(f"③ {n}곳을 고친다: {old}")
    if new != t and a.apply:
        MASTER.write_text(new, encoding="utf-8")
        print("✓ 썼다")
    elif new != t:
        print("(계획만 — --apply 로 쓴다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

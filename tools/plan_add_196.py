#!/usr/bin/env python3
"""
plan_add_196.py — PLAN 에 #196(landing 파일명 vintage 의 8자리 전제)을 신설한다. 표 셋 다.

    uv run python tools/plan_add_196.py            계획만
    uv run python tools/plan_add_196.py --apply    실행

PLAN §0-1: 행을 신설하면 표가 셋이다 — §1(행) · §10-1(배치 표 · 판의 행 목록과 닫는 수) · §10-5(구획 표).
세 군데를 한 번에 고친다. §10-1b 의 세 수와 §1 제목의 수는 `tools/docgen.py` 가 채운다(손으로 안 적는다).

배치 · 구획은 #195 와 같다 — 대장의 일이라 판 `Zs`, 새 자료를 들이되 판정을 안 움직이는 일이라 구획 `C`.
멱등이다. 앵커를 못 찾으면 자리를 추측하지 않고 실패한다.

IN    docs/PLAN.md
OUT   같은 파일 (--apply 일 때만)
PARAM 없음
부류  생산   문서의 줄을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 문서)
밖    행 내용이 옳은지는 안 본다. 행을 지우지 않고 닫는 일도 안 한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "docs" / "PLAN.md"

ROW195_HEAD = "| 195 | 119 출동 실측이"
ROW = (
    "| 196 | landing 파일명의 vintage 가 `YYYYMMDD` 만 받는 규칙에 걸려 `YYYY` 파일이 정규화를 못 통과한다 — "
    "`normalize_raw` 의 provider 규칙은 `\\d{8}` 이고 `naming.py` 는 `YYYYMMDD` · `YYYYMM` · `YYYY` 를 받는다 | 🟡 | "
    "**2026-11-06 (CI 복구).** 한 번 났고 우회로 막았다 — landing 파일명의 `YYYY` 를 `YYYY1231` 로 맞추는 일회용 스크립트가 **그 일을 끝내고 지워졌다**(git 이력 · §646). "
    "**근본 원인은 남아 있다**: 규칙이 `\\d{8}` 만 받으니 연도만 적힌 vintage 는 다시 오면 같은 곳에서 걸린다. "
    "★ **규칙만 넓히면 안 된다** — 8자리 전제가 `tools/ledger_fields.py:25` 의 `updated` 유도에도 박혀 있다(「정본은 파일명의 8자리 · 못 얻으면 채우지 않는다」). "
    "정규화가 `YYYY` 를 통과시키면 `updated` 유도는 그 파일을 **조용히 건너뛴다**(채우지 않는 쪽으로 깨진다 — 시끄럽지 않다). "
    "**도착 조건(무조건 — 판 `Zs` 가 닫는다)** — ① `normalize_raw` 의 provider 규칙이 `naming.py` 의 vintage 문법(`YYYYMMDD` · `YYYYMM` · `YYYY`)을 **그 문법 한 곳에서** 읽는다(정규식 사본 없음) "
    "② `ledger_fields` 의 `updated` 유도가 `YYYYMM` · `YYYY` 를 어떻게 다루는지 정하고(정밀도를 잃는 채움 vs 채우지 않음) 시험으로 박는다 "
    "③ 두 시험 — 연도만 적힌 파일명이 정규화를 통과한다 · 그때 `updated` 가 선언한 방식대로 나온다. 판정 폐포 밖이고 판정 수를 안 움직인다 |"
)
ZS_OLD = "`#195` | 23 |"
ZS_NEW = "`#195` `#196` | 24 |"
C_OLD = "#191 #195 | A | 0 |"
C_NEW = "#191 #195 #196 | A | 0 |"


def main() -> int:
    lines = PLAN.read_text(encoding="utf-8").split("\n")
    if any(l.startswith("| 196 |") for l in lines):
        print("이미 있다")
        return 0
    at = [i for i, l in enumerate(lines) if l.startswith(ROW195_HEAD)]
    zs = [i for i, l in enumerate(lines) if l.startswith("| `Zs` |") and l.rstrip().endswith(ZS_OLD)]
    c = [i for i, l in enumerate(lines) if l.startswith("| C | 새 원천") and C_OLD in l]
    if len(at) != 1 or len(zs) != 1 or len(c) != 1:
        print(f"✗ 앵커를 못 찾았다 — #195 행 {at} · Zs 행 {zs} · C 행 {c}", file=sys.stderr)
        return 1
    print(f"§1 #195 행(:{at[0] + 1}) 뒤에 #196 · §10-1 Zs(:{zs[0] + 1}) 닫는 수 23 → 24 · §10-5 C(:{c[0] + 1})")
    if "--apply" not in sys.argv:
        print("계획만 했다. 쓰려면 --apply (그 뒤 `tools/docgen.py` 로 수를 채운다)")
        return 0
    lines[zs[0]] = lines[zs[0]].rstrip()[:-len(ZS_OLD)] + ZS_NEW
    lines[c[0]] = lines[c[0]].replace(C_OLD, C_NEW, 1)
    lines.insert(at[0] + 1, ROW)
    PLAN.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

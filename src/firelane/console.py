"""
console.py — 터미널 표시. **판정에 안 닿는다.**

★ 2026-09-14. `col` 과 팔레트가 일곱 벌, `human` 이 세 벌이었다.
  `col` 일곱은 글자까지 같았고, `human` 셋은 **답이 달랐다** —

      acquire    B..GB   100바이트 → "100.0 B"
      tidy       B..GB   100바이트 → "100 B"
      scan_data  B..TB   1TB → "1.0 TB" · 천단위 콤마

  `scan_data` 판을 정본으로 삼는다. TB 를 알고, 천단위를 끊고, `B` 는
  정수로 낸다. 셋 중 가장 많이 아는 판이 정본이 되는 것이 맞다.

★ `dupcheck` 는 `human` 셋을 문턱 12 에서도 못 잡았다. AST 지문이
  인자 이름은 지우는데 **타입 주석은 안 지운다** — `n: int` 와
  `n: float` 가 다른 지문을 낸다. 그물의 구멍이고 여기 적어둔다.

IN    없음
OUT   없음 (순수 표시)
"""
from __future__ import annotations

import sys

# ★ 상위집합이다. `tidy` · `ship` 에만 있던 `c` 를 포함한다.
#   키가 느는 것은 기존 동작을 안 바꾼다.
C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m", "c": "\033[36m",
     "d": "\033[90m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    """터미널이면 색을 입힌다. 파이프로 넘기면 안 입힌다."""
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def human(n: float) -> str:
    """바이트 → 사람이 읽는 크기. `B` 는 정수, 그 위는 소수 한 자리."""
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:,.1f} {u}" if u != "B" else f"{n:,.0f} B"
        n /= 1024
    return ""

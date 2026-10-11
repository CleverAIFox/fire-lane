#!/usr/bin/env python3
"""
test_console_size.py — **크기를 사람이 읽는 글자로 바꾸는 정본 하나.** (§495)

── 왜 생겼나 ───────────────────────────────────────────────────
`firelane.console` 머리말이 적는다 — 2026-09-14 에 `human` 이 **세 벌**이었고
**답이 달랐다**:

    acquire    B..GB   100바이트 → "100.0 B"
    tidy       B..GB   100바이트 → "100 B"
    scan_data  B..TB   1TB → "1.0 TB" · 천단위 콤마

`scan_data` 판을 정본으로 삼았다 — **셋 중 가장 많이 아는 판**이다. 그런데
그 선택을 미는 자리가 없었다: `tools/srccov.py` 가 「시험이 이름으로도 안
부른다」로 셌다(§493). 세 벌을 하나로 합친 판에 시험이 없으면, 다음 사람이
네 번째를 짓는 것을 아무도 못 막는다.

★ 그리고 머리말이 **그물의 구멍**까지 적어 두었다 — `dupcheck` 는 문턱 12
  에서도 그 셋을 못 잡았다. AST 지문이 인자 이름은 지우는데 **타입 주석은
  안 지워서** `n: int` 와 `n: float` 가 다른 지문을 냈다. 그러니 네 번째
  사본을 막는 것은 지문이 아니라 **여기 적힌 답**이다.

IN    없음
OUT   없음 (검사)
PARAM 없음
밖    **색(`col`)은 안 본다** — 그쪽은 글자를 안 바꾸고 터미널 제어문자만
      두르며, `tools/colorsim.py` 가 대비를 따로 든다.
"""
from __future__ import annotations

from firelane.console import human

#: 정본이 **더 많이 아는** 세 가지. 합칠 때 고른 이유가 이 셋이다.
CANON = {
    1: "1 B",                       # B 는 **정수**다 (tidy 판)
    1023: "1,023 B",                # 천단위를 끊는다 (scan_data 판)
    1024: "1.0 KB",
    1024**2: "1.0 MB",
    1024**3: "1.0 GB",
    1024**4: "1.0 TB",              # TB 를 안다 (scan_data 판)
}


def test_the_canon_answers_what_the_three_copies_disagreed_about():
    """★ 본체. 세 벌이 갈렸던 그 입력들에 **한 답**을 낸다."""
    for n, want in CANON.items():
        assert human(n) == want, f"{n} → {human(n)!r} (기대 {want!r})"


def test_bytes_are_whole_and_everything_above_has_one_decimal():
    """★ `B` 만 정수다 — 「100.0 B」 는 세 벌 중 **버린** 판의 답이다."""
    assert human(100) == "100 B"
    assert "." not in human(999)
    for n in (1024, 1536, 1024**2 + 512 * 1024):
        assert human(n).count(".") == 1, human(n)


def test_the_unit_climbs_exactly_at_the_binary_boundary():
    """1023 B 와 1024 → 1.0 KB. 1000 에서 오르면 크기가 **다른 수**가 된다."""
    assert human(1023).endswith(" B") and human(1024).endswith(" KB")
    assert human(1024**2 - 1).endswith(" KB")
    assert human(1024**3 - 1).endswith(" MB")


def test_it_never_runs_out_of_units():
    """★ TB 가 천장이다 — 더 큰 수는 **TB 로 적는다.** 빈 글자를 내지 않는다.

    코드에 `return ""` 가 있고 그 줄은 **닿지 않는다.** 닿는 날이 오면
    크기 표시가 통째로 사라지므로 여기서 못박는다.
    """
    for n in (1024**5, 1024**6, 10.0**20):
        got = human(n)
        assert got.endswith(" TB") and got[0].isdigit(), got


def test_zero_is_zero_bytes_not_an_empty_string():
    """0 바이트도 **글자가 있다** — 빈 칸이면 표가 깨진다."""
    assert human(0) == "0 B"

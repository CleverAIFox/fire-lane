#!/usr/bin/env python3
"""
test_constbasis.py — 「출처를 댈 수 있는가」 판별식이 양방향으로 무는가.

── 왜 생겼나 (2026-10-03 · DECISIONS §380) ─────────────────────
폭이 열 배 틀린 자리를 파다가 같은 모양이 셋 나왔다 — `WMAX_CAP 60.0` ·
`XSEC_EXCL 5.0` · 층고 `3.3`. 셋 다 **「제일 큰 경우가 안 죽게」** 정한 수고,
그래서 나머지 전부가 그 문을 무사통과한다. 실측한 교차로 650개 중
231개(36%)가 `XSEC_EXCL` 보다 크다.

★ 값이 틀렸다는 말이 아니다. **어디서 왔는지 아무도 못 댄다**는 말이다.

IN    tools/constbasis.py
OUT   없음 (검사)
PARAM 없음
밖    **값이 옳은가는 안 본다.** `WMAX_CAP` 이 60 이어야 하는지는 이 시험이
      모르고 도구도 모른다. 드는 것은 판별식이 ① 출처를 출처로 치고
      ② 정책 문장을 출처로 안 치는가 둘이다.
"""
from __future__ import annotations

from pathlib import Path

import constbasis as B

ROOT = Path(__file__).resolve().parents[1]


def _one(src: str) -> dict:
    rows = B.scan(src)
    assert len(rows) == 1, f"상수를 {len(rows)}개 읽었다"
    return rows[0]


# ── ① 근거 표지 넷을 전부 무는가 ──────────────────────────────
def test_a_document_section_counts_as_a_basis():
    assert _one("A = 1.0  # DECISIONS §12 가 정했다")["basis"]


def test_a_standard_number_counts_as_a_basis():
    """차량 쪽 `height_m 3.2` 에는 `KFS-1-0073 §3.3` 이 붙어 있다."""
    assert _one("A = 3.2  # KFS-1-0073 §3.3")["basis"]


def test_an_arithmetic_derivation_counts_as_a_basis():
    assert _one("A = 3.0  # 전폭 2.5m + 사이드미러 여유")["basis"]


def test_a_measurement_counts_as_a_basis():
    assert _one("A = 5.0  # 교차로 650개를 쟀다")["basis"]


# ── ② 정책 문장은 출처가 아니다 ───────────────────────────────
def test_a_policy_sentence_is_not_a_basis():
    """★ 「15m 로 잡으면 대로가 전멸한다」는 **사유**지 출처가 아니다.

    사유는 왜 그렇게 정했는지를 말하고, 출처는 그 수가 어디서 왔는지를
    말한다. 둘을 같이 치면 모든 상수가 근거를 갖게 되고 이 관문이 죽는다.
    """
    assert not _one("A = 60.0  # 15m로 잡으면 대로가 전멸한다")["basis"]


def test_a_bare_constant_is_not_a_basis():
    assert not _one("A = 1.0")["basis"]


# ── ③ 읽는 범위 ──────────────────────────────────────────────
def test_a_continued_comment_on_the_next_line_is_read():
    """사유가 값 옆에 안 들어가 아래 줄로 넘어간 꼴이 실재한다."""
    assert _one("A = 0.5  # 노드 동일시 반경\n" + " " * 12 + "# MASTER §3")["basis"]


def test_tables_and_tuples_are_not_numeric_constants():
    assert not B.scan('A = {"x": 1}\nB = ("y",)\nC = "z"\n')


def test_negative_and_integer_values_are_constants():
    assert len(B.scan("A = -1\nB = 7\n")) == 2


# ── ④ 실물 ───────────────────────────────────────────────────
def test_the_declared_ratchet_matches_what_the_file_actually_says():
    """선언과 실측이 갈리면 래칫이 조용히 아무것도 안 본다."""
    assert B.ratchet_values()["CONST_NO_BASIS"] == B.CONST_NO_BASIS


def test_the_two_constants_found_on_2026_10_03_are_still_ungrounded():
    """★ 음성 대조. 누가 근거를 붙이면 이 시험이 울고, 그때 지운다.

    §379 가 판 자리다 — `WMAX_CAP` 은 「대로가 전멸한다」로, `XSEC_EXCL` 은
    「blob 폭 폭발 방지」로 적혀 있고 둘 다 **그 수가 어디서 왔는지**는 안
    적는다. 실측한 교차로 650개의 반경 중앙이 4.0m · p90 이 9.3m 인데
    제외 반경은 5.0m 하나다.
    """
    bad = {r["name"] for r in B.ungrounded(
        B.scan(B.PARAMS.read_text(encoding="utf-8")))}
    assert {"WMAX_CAP", "XSEC_EXCL"} <= bad


def test_the_tool_passes_its_own_selftest():
    assert B.selftest() == 0

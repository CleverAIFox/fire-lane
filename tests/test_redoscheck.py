#!/usr/bin/env python3
r"""
test_redoscheck.py — 되짚기 폭발 판별식이 **양방향으로** 무는가.

── 왜 생겼나 (2026-10-04 · DECISIONS §385) ─────────────────────
§360 · §377 이 되짚기 폭발 넷을 손으로 찾아 고쳤고, §377 이 「구조로 좁히고
시간으로 판정하는 도구는 다음 배치다」라고 적고 끝났다.

★ **시간으로 판정하지 않는다.** 기계마다 다르고 CI 러너는 더 흔들린다.
  흔들리는 관문은 사람이 끄게 되고 끄는 습관이 진짜 경보를 죽인다(§73).

★ 그리고 **넓게 잡으면 안 된다.** 처음 판별식은 열일곱을 잡았는데 그중
  열대여섯이 `(_[a-z0-9]+)*` 꼴 — 반복마다 구분자를 반드시 먹어 갈래가
  하나뿐인, 폭발하지 않는 패턴이었다. 넓은 그물은 빈 그물과 같다.

IN    tools/redoscheck.py
OUT   없음 (검사)
PARAM 없음
밖    **안전한가는 안 본다.** 안 걸린 것이 안전하다는 뜻이 아니다 — 이 셋
      밖의 모양으로도 터질 수 있고, 입력이 닿는가는 호출부를 읽어야 안다.
"""
from __future__ import annotations

from pathlib import Path

import redoscheck as R

ROOT = Path(__file__).resolve().parents[1]


# ── ① 터지는 꼴을 잡는가 ──────────────────────────────────────
def test_the_pattern_that_took_seventeen_seconds_is_caught():
    r"""§377 넷째가 실제로 쓰던 꼴이다 — n=14 에서 16.9초가 걸렸다."""
    assert R.shapes(r"((?:[\w.\-\[\]]+ ?)+)")


def test_a_quantified_atom_followed_only_by_optionals_is_ambiguous():
    assert R.shapes(r"(\w+ ?)+")
    assert R.shapes(r"([a-z]* ?)*")


def test_overlapping_alternatives_are_caught():
    assert "겹치는 선택" in R.shapes(r"(ab|ab?)+")


# ── ② 멀쩡한 꼴을 안 잡는가 ───────────────────────────────────
def test_the_fix_that_replaced_it_is_not_caught():
    """§377 이 넣은 평평한 문자군. 고침이 걸리면 고칠 길이 없어진다."""
    assert not R.shapes(r"pip install ([\w.\-\[\] ]*)")


def test_a_mandatory_separator_makes_the_split_unique():
    r"""★ `(_[a-z0-9]+)*` 는 반복마다 `_` 를 **반드시** 먹는다 — 갈래가 하나다."""
    for p in (r"^[a-z0-9]+(_[a-z0-9]+)*$", r"([\w_]+(?:\.[\w_]+)*)",
              r"(?:\s+[^\s]+)*", r"`([\w.-]+(?:/[\w.@-]+)+/?)`"):
        assert not R.shapes(p), p


def test_a_space_before_the_quantifier_belongs_to_the_space():
    r"""★ 정규식 안의 공백은 **리터럴**이다. `( … ) *` 의 `*` 는 묶음이 아니라
    그 공백에 붙는다 — 이것을 놓쳐서 멀쩡한 표 파서 둘이 걸렸었다."""
    assert not R.shapes(r"^\| *(\d+\w*) *\| *([^|]*?) *\|")


def test_plain_patterns_are_left_alone():
    for p in (r"^[a-z][a-z0-9_]*$", r"\d{4}-\d{2}-\d{2}", r"(foo|bar)",
              r"[A-Z_][A-Z0-9_]*"):
        assert not R.shapes(p), p


# ── ③ 읽는 범위 ──────────────────────────────────────────────
def test_patterns_in_comments_are_not_counted(tmp_path):
    """글자로 긁으면 주석의 예시까지 세고, 이 저장소는 주석에 정규식을 자주 적는다."""
    f = tmp_path / "x.py"
    f.write_text('# re.compile(r"(a+ ?)+")\ns = "(a+ ?)+"\n', encoding="utf-8")
    assert not R._patterns(f)


def test_a_real_call_is_read(tmp_path):
    f = tmp_path / "x.py"
    f.write_text('import re\nre.compile(r"(a+ ?)+")\n', encoding="utf-8")
    assert len(R._patterns(f)) == 1


# ── ④ 실물 ───────────────────────────────────────────────────
def test_the_declared_ratchet_matches_the_tree():
    assert R.ratchet_values()["REDOS_SHAPES"] == R.REDOS_SHAPES


def test_the_denominator_is_not_empty():
    """분모가 비면 「0건」이 **못 물었다**는 뜻이 된다 — 빈 그물 초록이다."""
    files = [p for r in R.ROOTS for p in (ROOT / r).rglob("*.py")
             if "__pycache__" not in p.parts]
    assert len(files) > 100


def test_the_tool_passes_its_own_selftest():
    assert R.selftest() == 0

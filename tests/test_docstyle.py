#!/usr/bin/env python3
"""
test_docstyle.py — 기획서에 **개요 층**이 있는가. 편마다 다른 계층을 구분하는가.

── 왜 생겼나 (2026-09-28 · DECISIONS §278-3·4) ─────────────────
기획서는 **문서 넷 중 유일하게 밖이 읽는 것**인데 두 결함이 검사 59개를
전부 초록으로 통과하고 있었다 —

  ① 본문 단락에 `pStyle` 도 `outlineLvl` 도 하나도 없었다. 제목 계층이
     **사람 눈에만** 있었고, 63쪽 PDF 의 북마크가 0 이었다.
  ② 편마다 장(章) 꼴이 다른데 — Part I·III 은 `1.` 이 장이고 **Part II 는
     `□` 가 장이다 — 꼴 하나로 층을 정하면 부모·자식이 뒤집힌다.

둘 다 「없는 것을 안 보는」 결함이다. 쪽수도 글자 수도 그림 수도 안 변하고,
사람이 눈으로 볼 때만 걸린다. 그래서 여기 시험을 둔다.

★ 그림 겹침과 정본 없는 그림 래칫은 `tests/test_figure_fit.py` 가 든다.

IN    tools/docstyle.py
OUT   없음 (검사)
PARAM 없음
밖    **글꼴 · 크기 · 색이 예쁜가는 안 본다.** 이 도구가 넣는 것은
      `w:outlineLvl` 뿐이고 보이는 것은 하나도 안 바꾼다 — 레이아웃은
      사람이 눈으로 본다. **PDF 에 북마크가 실제로 박혔는지도 안 본다** —
      `tools/proposal_pdf.py` 의 `BOOKMARKS_MIN` 이 굽고 나서 센다.
      **말투 · 어휘도 안 본다** — `tools/tonecheck.py` 소관이다.
"""
from __future__ import annotations

import docstyle


# ── ① 개요 층 ──────────────────────────────────────────────────
def test_every_heading_has_an_outline_level():
    """제출본에 개요가 실제로 있는가. 없으면 목차도 PDF 북마크도 안 생긴다."""
    miss, have, _odd = docstyle.survey(docstyle._open())
    assert not miss, (
        f"개요 층이 없는 제목 {len(miss)}/{len(miss) + len(have)} — "
        f"{[s for _i, _l, s in miss[:5]]}\n"
        "  uv run python tools/docstyle.py --write")
    assert have, "제목이 하나도 안 잡혔다 — HIER 가 실물과 갈렸다"


def test_part_two_inverts_the_hierarchy():
    """★ 이 도구가 있는 이유. Part I·III 은 장이 `1.` 인데 **Part II 는 `□`** 다.

    꼴 하나로 층을 정하면 Part II 의 부모·자식이 뒤집힌다. 편별 지도가
    죽으면 여기서 운다.
    """
    assert docstyle.level_of("1. 데이터 수집", "I") == 1
    assert docstyle.level_of("1. 데이터 수집", "II") == 2
    assert docstyle.level_of("□ 어떤 절", "I") == 2
    assert docstyle.level_of("□ 어떤 절", "II") == 1


def test_unknown_part_gets_no_level():
    """선언에 없는 편에는 층을 안 준다 — 모르는 것에 층을 주면 안 된다."""
    assert docstyle.level_of("1. 개요", "IV") is None
    assert docstyle.level_of("1. 개요", None) is None


def test_long_bold_lines_are_not_headings():
    """굵게 쓴 강조 **문장**을 제목으로 보면 개요가 쓰레기가 된다."""
    assert docstyle.level_of("1. " + "가" * 90, "I") is None
    assert docstyle.level_of("판정 통과선 = 펌프차 차체폭 + 미러 돌출분", "III") is None


def test_no_dead_form_declarations():
    """`HIER` 에 선언했는데 실물에서 안 걸리는 꼴이 있으면 죽은 선언이다."""
    dead = docstyle._dead(docstyle._open())
    assert not dead, "죽은 꼴 선언 — " + " · ".join(dead)


def test_every_part_in_the_document_is_declared():
    assert not docstyle._undeclared(docstyle._open())


def test_selftest_is_not_an_empty_net():
    assert docstyle.selftest() == 0


def test_selftest_cries_when_the_map_dies(monkeypatch):
    """★ 편별 지도를 하나로 뭉개면 자기검사가 우는가."""
    flat = dict.fromkeys(docstyle.HIER, (r"^\d+\.\s", r"^□\s"))
    monkeypatch.setattr(docstyle, "HIER", flat)
    assert docstyle.selftest() == 1

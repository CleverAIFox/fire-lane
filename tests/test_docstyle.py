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
    miss, have, _odd, wrong = docstyle.survey(docstyle._open())
    assert not miss, (
        f"개요 층이 없는 제목 {len(miss)}/{len(miss) + len(have)} — "
        f"{[s for _i, _l, s in miss[:5]]}\n"
        "  uv run python tools/docstyle.py --write")
    assert have, "제목이 하나도 안 잡혔다 — HIER 가 실물과 갈렸다"


def test_all_parts_share_one_hierarchy():
    """★ 편마다 다른 지도를 두면 **엉망을 코드로 박제**하는 것이다.

    첫 판은 Part II 만 `□` 가 장이라고 선언했었다(§278-7). 기획서를 통일했고
    `HIER` 는 튜플 하나다 — 편별 지도라는 것 자체가 없어야 한다.
    """
    assert isinstance(docstyle.HIER, tuple), "`HIER` 가 다시 편별로 갈렸다"
    assert docstyle.level_of("1. 데이터 수집") == 1
    assert docstyle.level_of("□ 어떤 절") == 2


def test_the_document_has_no_level_skips():
    """개요가 층을 건너뛰지 않는가 — Part II 뒤집힘을 잡은 강제자다."""
    bad = docstyle.skips(docstyle._open())
    assert not bad, "개요가 층을 건너뛴다 — " + " · ".join(bad)


def test_renumber_is_idempotent_on_the_real_document():
    """이미 통일된 문서를 또 맞바꾸면 안 된다."""
    assert docstyle.swap_plan(docstyle._open()) == []


def test_labels_hang_under_the_heading_above_them():
    """이름표는 절대층이 아니다 — `3. 시장현황` 바로 아래면 2층이다."""
    assert docstyle.level_of("[분석 요약]", under=1) == 2
    assert docstyle.level_of("[분석 요약]", under=2) == 3


def test_every_outline_level_matches_the_form():
    """★ 「빠졌나」만 보면 「틀렸나」가 통과한다(§278-8)."""
    _m, _h, _o, wrong = docstyle.survey(docstyle._open())
    assert not wrong, (
        f"개요 층이 틀린 제목 {len(wrong)}개 — "
        f"{[(t[:30], got, lvl) for _i, lvl, t, got in wrong[:4]]}")


def test_long_bold_lines_are_not_headings():
    """굵게 쓴 강조 **문장**을 제목으로 보면 개요가 쓰레기가 된다."""
    assert docstyle.level_of("1. " + "가" * 90, "I") is None
    assert docstyle.level_of("판정 통과선 = 펌프차 차체폭 + 미러 돌출분", "III") is None


def test_no_dead_form_declarations():
    """`HIER` 에 선언했는데 실물에서 안 걸리는 꼴이 있으면 죽은 선언이다."""
    dead = docstyle._dead(docstyle._open())
    assert not dead, "죽은 꼴 선언 — " + " · ".join(dead)


def test_selftest_is_not_an_empty_net():
    assert docstyle.selftest() == 0


def test_selftest_cries_when_the_map_dies(monkeypatch):
    """★ 계층 선언을 비우면 자기검사가 우는가 — 빈 그물은 초록으로 위장한다."""
    monkeypatch.setattr(docstyle, "HIER", ())
    assert docstyle.selftest() == 1

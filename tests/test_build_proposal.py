#!/usr/bin/env python3
"""
test_build_proposal.py — 기획서를 굽는 자의 **순수 함수들**을 민다. (§481)

── 왜 생겼나 ───────────────────────────────────────────────────
`tools/build_proposal.py` 는 `부류 관문` 이고, 기획서는 **문서 넷 중 유일하게
외부가 읽는 것**이다(PLAN `#142`). 그런데 이 도구를 미는 시험도 자기검사도
없었다 — §481 이 그 분모를 쟀다.

★ 여기가 드는 것은 **`carried()`** 하나가 본체다. 그 함수는 「바이트 대조와
  **따로** 서는 자」로 적혀 있다 — 생성물이 정본의 제목·표·그림을 **다
  담았나**를 따로 묻는다. 그 자가 죽으면 `--check` 가 바이트만 보고,
  바이트는 **둘 다 같이 낡으면** 조용하다.

★ 날짜 옮기기(`touched`)도 든다. 그 함수의 머리말이 **「순수 함수다 — 시험이
  합성 입력으로 민다」**고 적어 두고 있었고, 그 시험이 없었다.

IN    없음 (합성 마크다운)
OUT   없음 (검사)
PARAM 없음
밖    **실물을 굽지 않는다** — `--check` 의 바이트 대조는 `verify.sh` 와
      `doc_fsck` 의 일이다. 여기가 드는 것은 **판단하는 함수들**이다.
      HTML 이 예쁜가도 안 본다(`svg_fit` · `htmlfigs` 소관).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def bp():
    """경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering)."""
    spec = importlib.util.spec_from_file_location(
        "build_proposal", ROOT / "tools/build_proposal.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


# ── ① 날짜 옮기기 — 순수 함수 ──────────────────────────────────
COVER = """# 기획서

최종 수정 2026. 09. 01.

모든 수치는 2026-09-01 기준으로 적는다.
"""


def test_the_cover_date_moves_to_the_given_day(bp):
    got = bp.touched(COVER, "2026-10-12")
    assert "최종 수정 2026. 10. 12." in got, got
    assert "모든 수치는 2026-10-12 기준으로" in got, got
    assert "2026. 09. 01." not in got and "2026-09-01" not in got, "옛 날짜가 남았다"


def test_moving_the_date_twice_gives_the_same_text(bp):
    """★ 멱등. 같은 날로 두 번 옮겨도 같아야 한다 — 아니면 매일 운다."""
    once = bp.touched(COVER, "2026-10-12")
    assert bp.touched(once, "2026-10-12") == once


def test_text_without_the_cover_lines_is_untouched(bp):
    """표지 두 줄이 없으면 **안 건드린다** — 아무 날짜나 바꾸면 본문이 망가진다."""
    body = "# 제목\n\n2026-01-01 에 측량했다.\n"
    assert bp.touched(body, "2026-10-12") == body


# ── ② `carried()` — **바이트 대조와 따로 서는 자** ──────────────
#   ★ 바닥이 크다(제목 60 · 표 40 · 칸 3). **그래서 합성 정본도 크게 짓는다** —
#     작게 지으면 「다 담았는데도 운다」가 되어 그 시험이 바닥만 밀고
#     잃은 것을 안 민다. 바닥은 「둘이 같이 비면 대조가 조용하다」를 막는
#     자이고, 여기서 미는 것은 **잃은 것을 짚는가** 쪽이다.
N_HEAD, N_TABLE, N_FIG = 64, 44, 3


def _canon() -> str:
    out = ["# 기획서", ""]
    for i in range(1, N_HEAD + 1):
        out += [f"## {i}. 절 {i}", "", "본문.", ""]
        if i <= N_TABLE:
            out += ["| ID | 값 |", "|---|---|", f"| A{i} | {i} |", ""]
        if i <= N_FIG:
            out += [f"![]( fig{i}.png )".replace(" ", ""), ""]
    return "\n".join(out) + "\n"


MD = _canon()


def _made(*, heads: int = N_HEAD, tables: int = N_TABLE, figs: int = N_FIG,
          panes: int = 9) -> str:
    """정본을 다 담은 **합성 생성물**. 숫자를 줄이면 그만큼 잃은 것이다."""
    out = ["<h1>기획서</h1>"]
    out += [f"<h2>{i}. 절 {i}</h2>" for i in range(1, heads + 1)]
    out += ["<table></table>"] * tables
    out += ['<img src="x">'] * figs
    out += ['<div class="pane"></div>'] * panes
    return "\n".join(out)


def test_the_synthetic_canon_is_above_the_floors(bp):
    """★ 이 파일의 전제 — 합성 정본이 바닥을 넘는가. 안 넘으면 아래 시험들이
    **바닥만 밀고** 잃은 것을 안 민다(빈 그물의 반대쪽이다)."""
    assert N_HEAD >= bp.FLOOR_HEADS and N_TABLE >= bp.FLOOR_TABLES, (
        f"합성 정본이 바닥 아래다 — 제목 {N_HEAD}/{bp.FLOOR_HEADS} ·"
        f" 표 {N_TABLE}/{bp.FLOOR_TABLES}. 바닥이 올랐으면 이 수를 올려라")


def test_a_faithful_render_is_silent(bp):
    """★ 다 담았으면 **조용하다.** 여기가 빨간불이면 자가 과하다."""
    assert not bp.carried(_made(), MD), bp.carried(_made(), MD)


def test_a_lost_heading_is_caught(bp):
    bad = bp.carried(_made(heads=N_HEAD - 1), MD)
    assert any("제목" in b for b in bad), f"제목을 잃었는데 안 짚는다 — {bad}"


def test_a_lost_table_is_caught(bp):
    bad = bp.carried(_made(tables=N_TABLE - 1), MD)
    assert any("표가" in b for b in bad), f"표를 잃었는데 안 짚는다 — {bad}"


def test_a_lost_figure_is_caught(bp):
    bad = bp.carried(_made(figs=N_FIG - 1), MD)
    assert any("그림이" in b for b in bad), f"그림을 잃었는데 안 짚는다 — {bad}"


def test_an_empty_render_does_not_pass(bp):
    """★ **빈 그물.** 아무것도 안 담은 생성물이 통과하면 그 자는 없는 것과 같다."""
    assert bp.carried("", MD), "빈 생성물이 통과한다"


def test_the_floors_catch_a_thin_canon(bp):
    """★ 바닥 — **정본이 얇아도** 운다. 둘이 같이 비면 대조는 조용하다."""
    thin = "# 기획서\n\n## 1. 하나\n\n본문.\n"
    bad = bp.carried(_made(heads=1, tables=0, figs=0), thin)
    assert any("바닥" in b for b in bad), f"얇은 정본을 안 짚는다 — {bad}"


def test_entities_do_not_count_as_lost(bp):
    """★ 머리말이 적은 그 사고 — `&` 를 든 제목이 `&amp;` 와 안 맞아 **넷이
    거짓으로** 걸렸다. 엔티티를 되돌린 뒤 대야 한다."""
    md = MD.replace("## 1. 절 1", "## 1. 가 & 운데")
    made = _made().replace("<h2>1. 절 1</h2>", "<h2>1. 가 &amp; 운데</h2>")
    assert not any("제목" in b for b in bp.carried(made, md)), \
        "엔티티 때문에 멀쩡한 제목을 잃었다고 짚는다"


# ── ③ 슬러그 — 같은 제목 둘이 같은 닻이 되면 링크가 섞인다 ─────
def test_duplicate_headings_get_distinct_slugs(bp):
    seen: dict[str, int] = {}
    a = bp.slug("같은 제목", seen)
    b = bp.slug("같은 제목", seen)
    assert a != b, f"같은 제목 둘이 같은 닻을 받는다 — {a}"


# ── 칸이 실제로 켜지는가 (DECISIONS §526) ──────────────────────
#
# ★ 발행물 하나를 **글자로** 민다. 브라우저가 없으면 `display` 를 못 재지만,
#   칸이 안 켜진 원인은 CSS 가 아니라 **문서 구조**였다 — 그 구조는 글자로 잰다.
def _built() -> str:
    """발행된 화면. **주석을 걷고** 준다.

    ★ 2026-10-14. 걷지 않으면 이 검사가 **제 사유를 적은 주석에 걸린다** —
      그 주석이 `<header>` 라는 글자를 담고 있어서 `index("<header")` 가
      진짜 태그보다 먼저 거기를 짚었다. 구조를 재는 자는 **태그만** 본다.
    """
    t = (ROOT / "web" / "proposal.html").read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", t, flags=re.S)


def test_the_radios_are_siblings_of_main_not_children_of_header():
    """`#tN:checked ~ main #pN` 이 맞으려면 input 이 **`main` 의 앞 형제**여야 한다.

    2026-10-14 까지 input 이 `<header>` **안**에 살았다. `~` 는 뒤 형제만 보고
    `main` 은 input 의 형제가 아니라 header 의 형제라서 **네 칸이 전부 꺼진 채**
    발행됐다 — 기획서 화면이 목차만 있고 **본문이 통째로 비어 있었다.**
    심사위원이 볼 화면이고, 아무 관문도 안 울었다.
    """
    t = _built()
    hd, he, mn = t.index("<header"), t.index("</header>"), t.index("<main")
    first = t.index('<input type="radio" name="pane"')
    assert not (hd < first < he), (
        "라디오가 `<header>` 안에 있다 — `~ main` 이 아무것도 안 맞고 "
        "**모든 칸이 꺼진다**(DECISIONS §526)")
    assert first < mn, "라디오가 `main` 보다 뒤에 있다 — `~` 는 뒤 형제만 본다"


def test_every_pane_has_a_rule_that_turns_it_on():
    """칸마다 **켜는 규칙이 하나씩** 있는가. 수가 맞아야 한다."""
    t = _built()
    panes = t.count('<section class="pane"')
    assert panes >= 2, f"칸이 {panes}개다 — 굽는 자가 쪼개지 못했다"
    on = sum(f"#t{k}:checked~main #p{k}{{display:block}}" in t for k in range(panes))
    assert on == panes, f"칸 {panes}개 중 켜는 규칙이 {on}개다 — 나머지는 영영 안 보인다"


def test_exactly_one_radio_starts_checked():
    """첫 칸 하나만 `checked` — 0이면 빈 화면, 둘이면 뒤엣것만 선다."""
    t = _built()
    assert t.count('name="pane"') == t.count('<section class="pane"')
    assert t.count('name="pane" id="t0" checked') == 1
    assert t.count(" checked>") == 1, "처음 켜진 칸이 하나가 아니다"

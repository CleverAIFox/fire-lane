#!/usr/bin/env python3
"""
test_figure_text.py — 그림에 **마크다운이 그려지는가**.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §13 W4-6). `docs/figures/cctv.svg` 에 백틱이 그려져 있었다.

    밖은 `unknown` — 모른다고 적지 통과로 보지 않는다.

`tools/render_figures.py:172` 가 문자열을 그렇게 적었고, SVG `<text>` 는
마크다운을 모른다. 그래서 **코드 표기 의도가 그냥 글자 두 개**가 됐다.

★ 아무것도 안 울었다. `render_figures.py --check` 는 **지문이 정본과 같은가**를
  본다 — 틀린 글자를 그대로 두 번 만들면 지문도 같고 검사도 초록이다.
  「재현되는가」와 「맞는가」는 다른 물음이고, 이 저장소는 그 둘을 여러 번 혼동했다.

★ 글자는 사람이 쓰는 것이라 자동으로 고칠 수 없다. **그러나 셀 수는 있다.**
  마크다운 표기는 산문 습관이고, 그림 문자열에 섞이는 것은 습관이 흘러든 것이다.
  한 번 나면 또 난다 — 인스턴스를 고치고 족을 세운다.

── 무엇을 보는가 ───────────────────────────────────────────────
    발행되는 SVG 의 `<text>` 안에 마크다운 표기가 있는가

★ **범위를 선언한다.** 백틱 · `**` · `__` 셋만 본다. 대괄호 링크나 `#` 제목은
  안 본다 — 그림 라벨에 정상적으로 쓰일 수 있는 글자라(각주 번호 · 색 코드)
  세면 거짓 경보가 나고, 거짓 경보는 검사를 끄게 만든다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "docs" / "figures"

TEXT = re.compile(r"<text\b[^>]*>(.*?)</text>", re.S)
MARKDOWN = {
    "`": "백틱 — SVG 는 코드 표기를 모른다. 그냥 글자로 그려진다",
    "**": "굵게 표기 — SVG 는 `font-weight` 로 한다",
    "__": "밑줄 표기 — SVG 는 `text-decoration` 으로 한다",
}


def _svgs() -> list[Path]:
    return sorted(FIGS.glob("*.svg"))


def test_the_probe_is_not_an_empty_net():
    """그림을 한 장도 못 찾으면 아래가 조용히 통과한다(deadcheck ①)."""
    got = _svgs()
    assert len(got) >= 5, (
        f"`docs/figures/*.svg` 를 {len(got)}장밖에 못 찾았다 — "
        "그림이 옮겨졌거나 이 검사가 빈 그물이 됐다.")


@pytest.mark.parametrize("svg", _svgs(), ids=lambda p: p.name)
def test_no_markdown_is_drawn_into_the_figure(svg: Path):
    """`<text>` 안에 마크다운 표기가 있는가."""
    bad: list[str] = []
    for body in TEXT.findall(svg.read_text(encoding="utf-8")):
        # 태그 안쪽(tspan 등)을 걷어내고 실제로 그려지는 글자만 본다
        shown = re.sub(r"<[^>]+>", "", body)
        for tok, why in MARKDOWN.items():
            if tok in shown:
                bad.append(f"    {tok!r}  {why}\n      … {shown.strip()[:70]}")
    assert not bad, (
        f"`{svg.name}` 에 마크다운이 **그려져 있다**:\n" + "\n".join(bad) + "\n"
        "  정본은 `tools/render_figures.py` 다 — 거기 문자열을 고치고 다시 그려라:\n"
        "    uv run python tools/render_figures.py\n"
        "  ★ `--check` 는 이것을 못 잡는다. 그것이 묻는 것은 「재현되는가」지\n"
        "    「맞는가」가 아니다 — 틀린 글자를 두 번 만들면 지문도 같다.")

#!/usr/bin/env python3
"""
test_figure_fit.py — 그림 라벨이 **폭까지** 화면·박스 안에 드는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22 (DECISIONS §218-6). `tools/render_figures.py` 의 `_fits()` 는 `<text>` 의
기준점 한 점만 보았다. 기준점이 viewBox 안이면 라벨이 오른쪽 밖으로 한참 나가도
통과했다 — 넘쳐도 SVG 는 오류 없이 그려진다(1족 무음 통과).

이제 라벨 폭을 어림한다(한글 1.0em · 라틴·숫자 0.6em × font-size, text-anchor
반영). 이 검사는 **일부러 넘치는 라벨이 잡히는가**를 본다 — 안 잡히면 그물이 빈 것이다.
그 검사를 켜자 판정 분포·사유 분해 그림의 범례가 막대를 덮는 것이 드러났다.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _rf():
    spec = importlib.util.spec_from_file_location(
        "render_figures", ROOT / "tools" / "render_figures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rf = _rf()


def test_anchor_inside_but_label_overflows_is_caught():
    """기준점은 안인데 라벨이 오른쪽으로 넘친다 — 예전 검사는 통과시켰다."""
    body = ('<text x="600" y="40" font-size="14">'
            '이 라벨은 기준점만 안에 있고 글자는 화면 밖으로 나간다</text>')
    bad = rf._fits(body, 720, 100)
    assert bad and "밖이다" in bad[0], bad


@pytest.mark.parametrize("anchor,x", [("middle", 10), ("end", 60)])
def test_anchor_middle_and_end_overflow_left(anchor: str, x: int):
    body = (f'<text x="{x}" y="40" font-size="12" text-anchor="{anchor}">'
            '왼쪽으로 넘치는 긴 라벨입니다</text>')
    assert rf._fits(body, 720, 100)


def test_label_wider_than_its_box_is_caught():
    body = ('<rect x="100" y="10" width="80" height="40"/>'
            '<text x="140" y="35" font-size="12" text-anchor="middle">'
            '박스보다 훨씬 긴 라벨</text>')
    bad = rf._fits(body, 720, 100)
    assert bad and "박스" in bad[0], bad


def test_legend_running_onto_a_bar_is_caught():
    body = ('<rect x="60" y="70" width="200" height="30"/>'
            '<text x="12" y="91" font-size="12">영상판정 불가</text>')
    assert rf._fits(body, 720, 120)


def test_fitting_labels_pass():
    body = ('<rect x="100" y="10" width="160" height="40"/>'
            '<text x="180" y="35" font-size="12" text-anchor="middle">main</text>'
            '<text x="12" y="80" font-size="12">짧은 라벨 OK 123</text>')
    assert rf._fits(body, 720, 100) == []


def test_width_estimate_rules():
    """한글 1.0em · 라틴 0.6em · 엔티티는 풀어서 센다."""
    left, right, _, shown = rf.text_extent('x="0" font-size="10"', "가A&amp;")
    assert shown == "가A&"
    assert right - left == pytest.approx(10 + 6 + 6)


@pytest.mark.parametrize("name", sorted(rf.FIGURES))
def test_published_figures_fit(name: str):
    """발행된 SVG 도 같은 검사를 통과한다(생성 시 `_svg` 가 막지만 손댄 파일도 본다)."""
    svg = (ROOT / "docs" / "figures" / f"{name}.svg").read_text(encoding="utf-8")
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    assert m
    # 배경 rect(전체 크기)는 모든 글자를 품으므로 빼고 본다
    body = re.sub(r'<rect width="\d+" height="\d+" fill="#fff"/>', "", svg, count=1)
    assert rf._fits(body, int(m.group(1)), int(m.group(2))) == []

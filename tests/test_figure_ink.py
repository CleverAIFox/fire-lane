#!/usr/bin/env python3
"""
test_figure_ink.py — 막대의 **잉크가 값에 비례하는가**.

── 왜 생겼나 (2026-10-08 · DECISIONS §436-9) ───────────────────
세종대 데이터시각화 교안 「21 Practical issue 4 — Proportional ink」가 적는다 —
**선형 스케일 막대는 늘 0 에서 시작한다**(p.4 Note 1), 로그 스케일 막대는 비율
이므로 1 에서 시작한다(p.8 Note 2). 잘린 축은 같은 수로 **다른 그림**을 만든다.

★ 교안 결론 넷 중 **기계가 볼 수 있는 것은 이 하나다.** 회색조 단계 수 · 콘스위트
  윤곽선 · 휘도 대비로 강조 — 셋은 사람의 선택이라 권고로 적었다. 못 만드는
  강제자를 만든 척하지 않는다(MASTER §17).

── 무엇을 보는가 ───────────────────────────────────────────────
발행되는 SVG 에서 **가로 막대와 그 값 라벨을 짝지어** `길이 / 값` 이 막대마다
같은가를 본다. 같으면 0 에서 시작하고 선형이다. 0 이 아닌 밑동이나 비선형
스케일은 그 비를 깨뜨린다 — **값을 다시 계산하지 않고** 그림만 보고 안다.

★ 짝짓기는 **기하로** 한다 — 막대의 세로 범위 안에 글자 밑줄이 있고 그 글자가
  막대 **오른쪽**에서 시작하며 수로 시작하는 것. 좌표 상수를 적으면 배치가
  움직이는 날 그물이 조용히 비고, 빈 그물은 초록으로 거짓말한다.

★ 그래서 **카나리아를 둔다** — 짝이 하나도 안 잡히면 운다. `fig_verdict` 가
  막대 넷을 그리는 한 그 수는 0 이 될 수 없다.

밖    넘침 · 겹침은 `tests/test_figure_fit.py` 가, 글자 안 마크다운은
      `tests/test_figure_text.py` 가 든다. 여기는 **길이 하나**만 든다.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: 비가 어긋나도 봐주는 폭. 생성 코드가 `round(..., 1)` 로 길이를 쓰므로
#: 작은 막대에서 반올림만큼 흔들린다. 1% 는 그 흔들림보다 크고 **밑동 하나보다
#: 작다** — 0 이 아닌 밑동은 가장 작은 막대의 비를 몇 배로 띄운다.
TOL = 0.01

#: 짝이 적어도 이만큼은 잡혀야 한다. `fig_verdict` 의 막대 넷이다.
PAIRS_MIN = 4

_RECT = re.compile(r'<rect\b[^>]*>')
_TEXT = re.compile(r'<text\b([^>]*)>([^<]*)</text>')
#: 값 라벨 — **수로 시작하고 그 수가 거기서 끝난다.** 꼬리를 `\s|$` 로 닫는
#: 이유: `36.2%` 와 `2026-09-24` 를 값으로 읽으면 백분율과 날짜가 막대의 값이
#: 되고 비가 엉뚱하게 갈려 거짓 경보가 난다.
_NUM = re.compile(r"^\s*([0-9][0-9,]*)(?:\.[0-9]+)?(?:\s|$)")


def _attr(tag: str, name: str) -> float | None:
    m = re.search(rf'\b{name}="(-?[0-9.]+)"', tag)
    return float(m.group(1)) if m else None


def _pairs(svg: str) -> list[tuple[float, float]]:
    """(값, 막대 길이) 짝. 기하로 짓는다 — 좌표 상수를 안 적는다."""
    bars = []
    for tag in _RECT.findall(svg):
        x, y = _attr(tag, "x"), _attr(tag, "y")
        w, h = _attr(tag, "width"), _attr(tag, "height")
        if None in (x, y, w, h) or w <= 0:
            continue
        bars.append((x, y, w, h))
    labels = []
    for at, body in _TEXT.findall(svg):
        x, y = _attr(at, "x"), _attr(at, "y")
        m = _NUM.match(body)
        if x is None or y is None or not m:
            continue
        labels.append((x, y, float(m.group(1).replace(",", ""))))
    out = []
    for x, y, w, h in bars:
        for lx, ly, val in labels:
            # 글자 밑줄이 막대의 세로 범위 안이고, 막대 **오른쪽**에서 시작한다
            if y <= ly <= y + h and lx >= x + w and val > 0:
                out.append((val, w))
                break
    return out


def _mod(name: str):
    """도구를 **파일에서** 든다. `sys.path` 조작은 `tests/test_layering.py` 가 막는다."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _figures() -> dict[str, str]:
    return {name: fn() for name, fn in _mod("render_figures").FIGURES.items()}


def test_every_bar_is_as_long_as_its_value():
    """막대마다 `길이 / 값` 이 같은가 — 같으면 0 에서 시작하고 선형이다."""
    found, bad = 0, []
    for name, svg in _figures().items():
        pairs = _pairs(svg)
        if len(pairs) < 2:
            continue
        found += len(pairs)
        r = [w / v for v, w in pairs]
        if max(r) / min(r) > 1 + TOL:
            worst = max(pairs, key=lambda p: abs(p[1] / p[0] - sum(r) / len(r)))
            bad.append(
                f"{name} — 비가 {min(r):.4f}~{max(r):.4f} 로 갈린다 "
                f"(값 {worst[0]:g} ↔ 길이 {worst[1]:g})")
    assert not bad, (
        "막대 길이가 값에 비례하지 않는다 — 축이 0 이 아닌 곳에서 시작하거나\n"
        "  스케일이 선형이 아니다. 교안 「Proportional ink」 p.4 Note 1:\n"
        "  선형 막대는 늘 0 에서 시작한다. 로그 막대를 쓰려면 1 에서 시작하고\n"
        "  **그 사실을 그림에 적는다** — 이 검사는 로그를 모른다.\n  "
        + "\n  ".join(bad))
    assert found >= PAIRS_MIN, (
        f"막대 짝이 {found}개뿐이다 — 그물이 비었다(하한 {PAIRS_MIN}).\n"
        "  배치가 바뀌어 짝짓기가 못 잡는 것이면 `_pairs` 를 고쳐라. "
        "막대를 없앴다면 이 하한을 그 수로 내려라.")


def test_the_net_catches_a_truncated_axis():
    """★ 음성 대조 — **잘린 축을 합성해** 그물이 잡는지 본다. 빈 그물 방지다."""
    good = ('<rect x="10" y="10" width="100" height="20"/>'
            '<text x="120" y="25">100</text>'
            '<rect x="10" y="40" width="50" height="20"/>'
            '<text x="70" y="55">50</text>')
    assert len(_pairs(good)) == 2
    r = [w / v for v, w in _pairs(good)]
    assert max(r) / min(r) <= 1 + TOL

    # 같은 수인데 밑동을 40 에서 시작한 그림 — 100 은 60, 50 은 10 이 된다
    cut = ('<rect x="10" y="10" width="60" height="20"/>'
           '<text x="80" y="25">100</text>'
           '<rect x="10" y="40" width="10" height="20"/>'
           '<text x="30" y="55">50</text>')
    r = [w / v for v, w in _pairs(cut)]
    assert max(r) / min(r) > 1 + TOL, "잘린 축을 그물이 못 잡는다"


@pytest.mark.parametrize("svg,why", [
    ('<rect x="10" y="10" width="100" height="20"/>'
     '<text x="20" y="25">100</text>', "글자가 막대 안이면 막대가 아니다"),
    ('<rect x="10" y="10" width="100" height="20"/>'
     '<text x="120" y="80">100</text>', "세로 범위 밖이면 그 막대의 라벨이 아니다"),
    ('<rect x="10" y="10" width="100" height="20"/>'
     '<text x="120" y="25">통과</text>', "수로 시작하지 않으면 값이 아니다"),
])
def test_the_pairing_rule_rejects_what_is_not_a_bar(svg, why):
    """짝짓기가 **넓어지지 않는가.** 넓으면 범례와 칸이 막대로 셰어 거짓 경보가 난다."""
    assert _pairs(svg) == [], why

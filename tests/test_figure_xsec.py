#!/usr/bin/env python3
"""
test_figure_xsec.py — [그림 13] 이 **규칙을 그리는가, 폴백을 그리는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
★ 2026-09-24 (PLAN §12 #15 닫힘 · DECISIONS §236). 기획서 [그림 13] 은
  **반경 5m 원 하나만** 그렸다. 캡션은 2026-09-01 에 「평면교차점 실형상
  제외」로 고쳐졌는데 그림은 안 고쳐졌다 — 캡션과 그림이 서로 다른 모델을
  말한 채 석 주를 서 있었다.

★ 아무것도 안 울었다. `docx_check` 는 캡션 글자를 저장소 어휘와 대조하고
  `render_figures --check` 는 지문이 정본과 같은가를 본다. **틀린 그림을
  그대로 두 번 만들면 지문도 같다** — 「재현되는가」와 「맞는가」는 다른
  물음이다(`test_figure_text` 가 2026-09-20 에 같은 것을 배웠다).

★ 그래서 이 파일은 **그림이 말하는 내용**을 문다. 실제 규칙은
  `seg/width.py` 가 든다 — 평면교차점 폴리곤이 가까이 있으면 폴리곤만
  믿고, 폴리곤이 아예 없는 교차로에서만 노드 반경으로 폴백한다.
  그림 두 줄이 **같은 길 · 같은 표본**인데 버리는 수가 달라야 그 말이 된다.

IN    tools/render_figures.py · tools/docx_figs.py · src/firelane/seg/params.py
OUT   없음 (검사)
밖    **원과 폴리곤의 모양이 실제 교차부와 닮았는가는 안 본다.** 교차부
      실형상은 교차부마다 다르고 정본은 `ngii1k_xsec_5186.gpkg` 다 —
      이 그림은 값이 아니라 규칙을 그리는 구조 그림이다(`fig_branch` 와 같다).
      그리고 배치(글자가 화면·도형을 넘는가)는 `test_figure_fit` 소관이다.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_{name}", ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rf = _load("render_figures")
SVG = rf.fig_xsec()
COUNTS = [(int(a), int(b)) for a, b in
          re.findall(r"표본 (\d+) · 버림 (\d+)", SVG)]


def test_two_rows_are_drawn():
    """줄이 둘인가 — 하나면 대비가 없고, 대비가 이 그림의 전부다."""
    assert len(COUNTS) == 2, f"「표본 N · 버림 K」 가 {len(COUNTS)}개다: {COUNTS}"


def test_same_samples_different_drops():
    """★ 같은 길 · 같은 표본인데 **버리는 수가 다르다.**

    이것이 「원은 규칙이 아니라 폴백」의 근거다. 같으면 그림이 아무 말도
    안 하는 것이고, 그 상태가 2026-09-01 부터 오늘까지였다.
    """
    (n_fb, k_fb), (n_poly, k_poly) = COUNTS
    assert n_fb == n_poly, f"두 줄의 표본 수가 다르다 {n_fb} vs {n_poly} — 같은 길이어야 한다"
    assert k_fb > k_poly, (
        f"폴백(원)이 실형상보다 덜 버린다 {k_fb} ≤ {k_poly} — "
        "원이 작은 교차부를 과하게 도려낸다는 그림의 주장이 뒤집혔다")


def test_neither_row_is_an_empty_net():
    """양쪽 다 실제로 버려야 한다. 0 이면 교차부 제외가 안 그려진 것이다."""
    for n, k in COUNTS:
        assert 0 < k < n, f"버림 {k} / 표본 {n} — 제외가 안 그려졌거나 전부 버렸다"


def test_the_radius_comes_from_params_not_from_here():
    """반경의 정본이 `params.py` 하나인가."""
    src = (ROOT / "src/firelane/seg/params.py").read_text(encoding="utf-8")
    m = re.search(r"^XSEC_EXCL\s*=\s*([\d.]+)", src, re.M)
    assert m, "params.py 에 XSEC_EXCL 이 없다 — 이 시험의 전제가 깨졌다"
    want = float(m.group(1))
    assert f"{want:g}m" in SVG, f"그림이 {want:g}m 를 안 적는다"

    # ★ 그림 코드에 그 수가 literal 로 박혀 있으면 정본이 둘이 된다.
    import ast
    tree = ast.parse((ROOT / "tools/render_figures.py").read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "fig_xsec")
    lit = [n.value for n in ast.walk(fn)
           if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
           and not isinstance(n.value, bool) and float(n.value) == want]
    assert not lit, f"반경 {want:g} 가 그림 코드에 박혀 있다: {lit} — 정본은 params.py 하나다"


def test_both_the_rule_and_the_fallback_are_drawn():
    """폴리곤(규칙)과 원(폴백)이 **둘 다** 있는가. 하나만이면 종전 상태다."""
    assert "<circle" in SVG, "폴백 원이 없다"
    assert "fill=\"#fed7aa\"" in SVG, "평면교차점 실형상 폴리곤이 없다"
    txt = " ".join(re.findall(r"<text\b[^>]*>(.*?)</text>", SVG, re.S))
    assert "폴백" in txt and "실형상" in txt, txt[:200]
    assert "이쪽이 규칙이다" in txt, "어느 쪽이 규칙인지 그림이 안 말한다"


def test_it_is_placed_at_figure_13():
    """기획서 자리 선언이 있는가. 없으면 `docx_figs --check` 가 운다."""
    df = _load("docx_figs")
    assert df.PLACE["xsec"]["fig"] == 13, df.PLACE["xsec"]


def test_plan_row_is_closed():
    """§12 #15 가 닫혔는가 — 그림을 고쳤으면 표에서 나가야 한다."""
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    assert "[그림 13] 이미지가 옛 방식을 그린다" not in plan, (
        "§12 #15 가 아직 있다 — 그림은 고쳤는데 대장이 안 닫혔다")

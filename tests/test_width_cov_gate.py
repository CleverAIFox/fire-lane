"""
test_width_cov_gate.py — 커버율 자격 검사가 **표본 수와 무관하게** 걸리는가.
(DECISIONS §308 · §245)

── 왜 이 파일이 생겼나 (2026-09-29) ────────────────────────────
`seg/width.py` 의 자격 검사에 `and _n_reg >= 3` 이 붙어 있었다 — 표본이 3개
미만이면 검사를 건너뛴다. **근거가 가장 얇은 곳에서 관문이 꺼졌다.**

그 면제를 무는 시험이 없었다. §245 가 `COV_MIN` 을 세울 때 시험을 표본이
넉넉한 경우로만 짰기 때문이다 — 관문의 시험이 관문이 꺼지는 경우를 안 밟으면
그 관문은 꺼진 채로 초록이다.

실측 결과(면제를 뗀 뒤): clear 465→464 · needs_cv 226→225 · blocked 191→192 ·
unknown 399→400. DM02918 이 폭 29.91m·clear 에서 1.4m·unknown 으로 갔다.

IN    src/firelane/seg/width.py · seg/params.py(COV_MIN · WIDTH_SRCS)
OUT   없음
밖    **폭 값이 옳은가는 안 본다.** 어느 소스가 진실인지도 안 본다 — 자격 규칙이
      표본 수에 따라 갈리지 않는가만 든다.
      **`widths()` 를 끝까지 돌리지 않는다.** 그것은 기하와 레이크가 필요하고,
      그 경로는 `tests/test_seg_width.py` · `tests/test_measurements.py` 가 든다. 여기는 **채택 규칙의 글**을
      본다 — 조건절이 돌아오는 것을 막는 것이 이 파일의 일이다.
      **선언된 예외(「전부 자격 미달이면 하나는 쓴다」)는 건드리지 않는다.**
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from firelane.seg.params import COV_MIN, WIDTH_SRCS

WIDTH = Path(__file__).resolve().parents[1] / "src" / "firelane" / "seg" / "width.py"


def src() -> str:
    return WIDTH.read_text(encoding="utf-8")


def _gate_lines() -> list[str]:
    """`COV_MIN` 을 쓰는 조건줄들. 주석은 걷는다."""
    out = []
    for ln in src().splitlines():
        bare = re.sub(r"#.*$", "", ln)
        if "COV_MIN" in bare:
            out.append(bare.strip())
    return out


def test_the_gate_exists_at_all():
    """★ 빈 그물 방어. 이 검사가 볼 줄이 없으면 아래 시험들이 전부 공허하다."""
    assert _gate_lines(), "`width.py` 에서 COV_MIN 을 쓰는 조건줄을 못 찾았다"
    assert 0 < COV_MIN <= 1.0, f"COV_MIN 이 비율이 아니다: {COV_MIN}"


def test_the_gate_does_not_depend_on_the_sample_count():
    """★ 이것이 §308 의 본론이다. 자격 검사가 표본 수를 보면 안 된다.

    표본이 적을수록 커버율은 **더 못 믿을 값**이다(표본 1개면 자동으로 1.0 이 되고,
    2개 중 1개면 0.5 다). 그런데 종전 조건은 표본이 적을 때 검사를 **껐다** —
    방향이 거꾸로였다.
    """
    bad = [ln for ln in _gate_lines() if "_n_reg" in ln or "n_reg" in ln]
    assert not bad, (
        "커버율 자격 검사가 표본 수를 본다:\n  " + "\n  ".join(bad) +
        "\n\n  표본이 적을수록 커버율은 더 못 믿을 값이다 — 그때 관문을 끄면\n"
        "  가장 위험한 구간이 검사를 통과한다(DECISIONS §308).\n"
        "  표본 수로 갈라야 하는 규칙이라면 `verdict()` 의 `nreg` 처럼\n"
        "  **판정 쪽**에 두고 그 사유를 적어라.")


def test_the_gate_is_a_skip_not_a_pick():
    """자격 미달이면 **다음 순위로 넘긴다**(continue). 커버율로 소스를 고르면
    실폭도로가 늘 이겨 결정 63(수치지도 주 소스)이 뒤집힌다."""
    tree = ast.parse(src())
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if "COV_MIN" not in ast.dump(node.test):
            continue
        found = True
        assert any(isinstance(b, ast.Continue) for b in node.body), (
            "자격 미달 분기가 `continue` 가 아니다 — 자격은 고르는 기준이 아니다")
    assert found, "COV_MIN 조건을 AST 에서 못 찾았다"


def test_the_priority_order_still_has_one_home():
    """순서의 정본이 `WIDTH_SRCS` 하나다. `width.py` 가 순서를 재기술하지 않는다."""
    assert WIDTH_SRCS == ("ngii1k", "ngii", "silpok"), WIDTH_SRCS
    body = re.sub(r"#.*$", "", src(), flags=re.M)
    literal = re.findall(r'\(\s*"ngii1k"\s*,\s*"ngii"\s*,\s*"silpok"\s*\)', body)
    assert not literal, (
        f"폭 소스 순서를 {len(literal)}곳에서 다시 적었다 — 정본은 "
        "`seg/params.py` 의 `WIDTH_SRCS` 하나다(DECISIONS §245)")


def test_the_declared_fallback_is_still_declared():
    """「전부 자격 미달이면 우선순위대로 하나는 쓴다」는 **선언된** 예외다.

    ★ 선언된 예외와 선언 안 된 예외는 다른 것이다. 이 시험은 그 예외를 지우라는
      것이 아니라, 그것이 **사유와 함께** 남아 있는지를 본다 — 사유가 사라지면
      다음 사람이 그것을 §308 의 면제와 구별할 수 없다.
    """
    body = src()
    assert "전부 자격 미달이면" in body, "선언된 폴백의 사유 문장이 사라졌다"
    assert "폭을 못 내는 것보다 낫다" in body, (
        "폴백의 근거 문장이 사라졌다 — 근거 없는 예외가 된다")

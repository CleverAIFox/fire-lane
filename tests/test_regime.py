"""`firelane.regime` — 2×2 체제가 정의대로 갈리고 문턱이 분수 상수로 박혀 있다.  (Zm23)

IN    src/firelane/regime.py · src/firelane/segments.py(폐포 밖 확인)
OUT   없음 (검사)
PARAM 없음
밖    **체제 분류가 형태와 맞는가**는 안 본다 — 0판 평가셋 채점(Q5)의 일이다. 정의대로 갈리는지만 본다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pyfiles

from firelane import regime as R

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/firelane/regime.py").read_text(encoding="utf-8")


def test_the_four_cells_of_the_two_by_two() -> None:
    assert R.regime_of(0.0, ["carve", "carve"]) == R.NONE_
    assert R.regime_of(0.5, ["carve"]) == R.ECC_ONLY
    assert R.regime_of(0.1, ["carve", "escape"]) == R.ESCAPE_ONLY
    assert R.regime_of(0.9, ["escape"]) == R.BOTH


def test_the_boundary_is_one_third_inclusive() -> None:
    assert R.ecc_fires(1 / 3) is True
    assert R.ecc_fires(1 / 3 - 1e-9) is False
    # 기하: ecc = (넓은 − 좁은)/전폭. 넓은 쪽 2 · 좁은 쪽 1 → 전폭 3 → 1/3
    assert abs((2 - 1) / (2 + 1) - R.ECC_THRESHOLD) < 1e-12


def test_one_escape_sample_is_enough_and_zero_is_not() -> None:
    assert R.escape_fires(["carve"] * 50 + ["escape"])
    assert not R.escape_fires(["carve", "sum", None, ""])
    assert not R.escape_fires([])


def test_a_missing_eccentricity_is_not_read_as_fine() -> None:
    assert R.ecc_fires(None) is None and R.regime_of(None, ["escape"]) is None


def test_the_cells_are_exclusive_and_exhaustive() -> None:
    seen = {R.regime_of(e, w) for e in (0.0, 1.0) for w in (["carve"], ["escape"])}
    assert seen == set(R.REGIMES) and len(R.REGIMES) == 4


def test_the_threshold_is_a_fraction_constant_not_computed_from_a_distribution() -> None:
    assert R.ECC_THRESHOLD == 1 / 3
    assert re.search(r"^ECC_THRESHOLD = 1 / 3\s*$", SRC, re.M), "문턱을 분수로 박지 않았다"
    body = "\n".join(ln for ln in SRC.splitlines() if not ln.lstrip().startswith("#"))
    for w in ("quantile", "percentile", "np.", "median", "statistics"):
        assert w not in body.split('"""', 2)[2], f"문턱이 분포에서 계산될 길이 열려 있다: {w}"


def test_it_is_outside_the_judgment_closure() -> None:
    from firelane.shardseal import code_closure

    files = {p.relative_to(ROOT).as_posix() for p in code_closure("firelane.segments")}
    assert "src/firelane/regime.py" not in files
    # ★ Zm35. 훑기는 src · tools · tests 전부 하고 **단언이 src 만 본다** — 평가셋 도구(tools/evalset.py)와 이 시험이 체제를 부르는 것은 정상이다.
    #   금지되는 것은 판정 쪽(src)이 부르는 것 하나다(deadcheck ⑤ — 훑는 폴더를 좁히면 좁음이 의도인지 빠뜨림인지 안 읽힌다).
    users = []
    for u in pyfiles.rel(ROOT, pyfiles.all_py(ROOT)):
        if not u.startswith("src/") or u == "src/firelane/regime.py":
            continue
        text = (ROOT / u).read_text(encoding="utf-8")
        if re.search(r"\bregime\b", text) and "import" in text and re.search(r"from firelane import[^\n]*\bregime\b|firelane\.regime", text):
            users.append(u)
    assert not users, f"판정 쪽이 체제를 부른다: {users}"

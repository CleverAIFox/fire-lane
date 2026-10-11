#!/usr/bin/env python3
"""
test_toolchain_declarations.py — 도구 선언이 **실제와 같은가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §13 W3-1 · W3-20 · W3-15). 셋이 한 배치로 닫혔다 —
셋 다 `uv lock` 재해결을 요구해 수용 조건이 같았기 때문이다.
형태도 하나다 — **선언이 실제와 다르다.**

    W3-20  `requires-python >=3.11` 인데 3.11 은 아무 데서도 안 돈다
    W3-1   `dev` 목록이 둘이고 내용이 달랐다 (pytest >=8.3 vs >=9.1.1)
    W3-15  워크플로는 머지되기 전에 문법조차 안 봤다

★ 셋 다 「읽는 사람이 속는다」는 같은 손해를 낸다. 틀린 선언은 없는
  선언보다 나쁘다 — 없으면 사람이 보고, 있으면 안 본다(MASTER §17).
"""
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _toml() -> dict:
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


def test_requires_python_matches_the_pinned_runtime() -> None:
    """`requires-python` 이 `.python-version` 보다 **넓지 않은가** (W3-20).

    ★ W3-17 이 `.python-version` 을 런타임 정본으로 세웠다. CI · 배포 ·
      이미지가 전부 거기서 판을 읽는데 `pyproject` 만 `>=3.11` 이었다 —
      **3.11 을 지원한다고 적어놓고 아무 데서도 안 돌렸다.**
    """
    pin = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    req = str(_toml()["project"]["requires-python"])
    assert req.startswith(f">={pin}"), (
        f"`requires-python = {req!r}` 인데 정본 `.python-version` 은 {pin} 이다.\n"
        "  선언이 실제보다 넓으면 지원한다고 적어놓고 아무 데서도 안 돌린다.\n"
        "  좁히려면 `uv lock` 재해결이 따라온다 — 그 배치는 수용 조건이 다르다.")


def test_dev_dependencies_have_one_home() -> None:
    """`dev` 목록이 하나인가 (W3-1).

    ★ extras 의 `dev` 와 `[dependency-groups]` 의 `dev` 가 같이 있으면
      **이름이 같고 내용이 다르다.** `uv sync --extra dev` 를 친 사람만
      pytest-cov 도 olefile 도 없는 **조용히 약한 환경**을 받는다.
    """
    t = _toml()
    extras = t.get("project", {}).get("optional-dependencies", {})
    assert "dev" not in extras, (
        "`[project.optional-dependencies] dev` 가 살아 있다.\n"
        "  dev 도구의 집은 `[dependency-groups] dev` 하나다 — 둘이면 갈린다.\n"
        "  extras 가 필요하면 이름을 다르게 지어라.")
    assert "dev" in t.get("dependency-groups", {}), "`[dependency-groups] dev` 가 없다"


def linter_faults(verify: str, ci: str, dev: list[str]) -> list[str]:
    """워크플로 린터가 **양쪽에서 같은 판으로** 도는가. 순수 함수.

    ★ 2026-10-12 (DECISIONS §484). 종전에는 이 판정이 시험 본문의
      `assert` 넷이었다 — **합성 입력으로 밀 수가 없었다.** 그래서
      「무엇에나 통과한다」와 구별이 안 됐다(`tools/canary.py` 의 축).
      판정을 함수로 빼고 아래에서 **양방향**으로 민다.
    """
    bad = []
    if "actionlint" not in verify:
        bad.append("verify.sh 가 actionlint 을 안 부른다")
    if "actionlint" not in ci:
        bad.append("CI 가 actionlint 을 안 부른다 — 로컬 전용이 된다")
    if "actionlint" in verify:
        at = verify.index("actionlint")
        if "# ci-exempt: " in verify[max(0, at - 200):at]:
            bad.append("actionlint 단계에 면제가 붙어 있다 — 이 검사는 CI 에서"
                       " 돌 수 있고, 그러면 면제가 거짓말이 된다(W3-10)")
    if not any("actionlint" in d for d in dev):
        bad.append("actionlint 이 잠금 안에 없다 — 기계마다 다른 판이 돌거나"
                   " 아예 없고, 그러면 검사가 조용히 안 돈다")
    return bad


def _real() -> tuple[str, str, list[str]]:
    return (
        (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8"),
        (ROOT / ".github" / "workflows" / "contract.yml").read_text(encoding="utf-8"),
        [str(d) for d in _toml()["dependency-groups"]["dev"]],
    )


def test_workflow_linter_runs_on_both_sides() -> None:
    """워크플로 린터가 로컬과 CI **양쪽**에서 도는가 (W3-15).

    ★ 한쪽에만 있으면 「내 기계에서는 됐는데」가 난다. 잠금으로 깔리므로
      두 기계가 **같은 판**을 돌린다 — 그래서 `ci-exempt` 가 필요 없다.
    """
    v, c, dev = _real()
    assert not linter_faults(v, c, dev), linter_faults(v, c, dev)


def test_the_judge_bites_each_of_the_four_ways_it_can_break() -> None:
    """★ **카나리아.** 네 갈래를 하나씩 망가뜨려 그 자가 우는지 본다.
    한쪽만 밀면 「무엇에나 통과한다」와 구별이 안 된다."""
    v, c, dev = _real()
    assert linter_faults(v.replace("actionlint", "없는린터"), c, dev), \
        "verify.sh 에서 린터가 사라졌는데 조용하다"
    assert linter_faults(v, c.replace("actionlint", "없는린터"), dev), \
        "CI 에서 린터가 사라졌는데 조용하다"
    assert linter_faults(v, c, [d for d in dev if "actionlint" not in d]), \
        "잠금에서 린터가 빠졌는데 조용하다 — 기계마다 다른 판이 돈다"
    at = v.index("actionlint")
    exempted = v[:at - 1] + "# ci-exempt: 아무 사유\n" + v[at - 1:]
    assert linter_faults(exempted, c, dev), "면제가 붙었는데 조용하다"

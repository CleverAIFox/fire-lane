"""`scipy` 는 dev 그룹에만 있고 `src/` 는 import 하지 않는다.  (감사 N9 · Zm20 · B — 사람이 잠그기 전)

core 의존성에 있으면 `uv sync --no-dev` 로 깐 판정 환경에도 따라 들어온다 — 쓰는 곳은 조사 도구 둘뿐이다.
`uv.lock` 이 움직이므로 골든 코드 지문이 달라진다(재잠금은 사람이 한다).

IN    pyproject.toml · src/**
OUT   없음 (검사)
PARAM 없음
밖    **`uv sync --no-dev` 환경에서 실제로 도는지**는 안 본다 — 그것은 `pytest tests/test_classify.py` 를
      `--no-dev` 환경에서 돌려 확인했다(DECISIONS §566). 여기는 선언과 import 만 본다. `tools/` 는 `.py` 만 훑는다 — `.sh` 는 안 본다.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pyfiles

ROOT = Path(__file__).resolve().parents[1]


def _names(reqs: list[str]) -> set[str]:
    return {re.split(r"[<>=\[ ;~!]", r, maxsplit=1)[0].lower() for r in reqs}


def _scipy_in(group: list[str]) -> bool:
    return "scipy" in _names(group)


def test_scipy_is_declared_in_dev_and_not_in_core() -> None:
    d = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert not _scipy_in(d["project"]["dependencies"]), "scipy 가 core 에 있다 — dev 그룹으로 내렸다"
    assert _scipy_in(d["dependency-groups"]["dev"]), "scipy 가 dev 그룹에 없다"


def test_scipy_is_not_a_core_import() -> None:
    """`src/` 가 scipy 를 import 하면 deptry 면제(`DEP004`)가 거짓이 된다.

    ★ Zm35. 훑기는 src · tools · tests 전부 하고 **단언이 폴더로 갈린다** — `src` 에는 0 이어야 하고(면제가 참인 조건), `tools` 에는 1 이상이어야 한다
    (`DEP004` 면제는 `deptry src tools` 가 tools 를 비-dev 로 보기 때문이고, tools 에 쓰는 곳이 없으면 그 면제가 빈 그물이다). tests 가 scipy 를 쓰는 것은
    면제의 근거가 아니라 셈에 안 든다. (종전에는 훑는 폴더를 `src` 와 `tools` 로 따로 적어 각각 좁았다 — deadcheck ⑤.)
    """
    hits = [u for u in pyfiles.rel(ROOT, pyfiles.all_py(ROOT))
            if re.search(r"^\s*(?:from|import)\s+scipy\b", (ROOT / u).read_text(encoding="utf-8"), re.M)]
    src = [h for h in hits if h.startswith("src/")]
    assert not src, f"src 가 scipy 를 import 한다: {src}"
    tools = [h for h in hits if h.startswith("tools/")]
    assert tools, "tools 에도 scipy 를 쓰는 곳이 없다 — 이 시험과 DEP004 면제가 빈 그물이다"

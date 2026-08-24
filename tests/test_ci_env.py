#!/usr/bin/env python3
"""
test_ci_env.py — CI 환경과 로컬이 같은 것을 보는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-24. `contract.yml` 이 의존성을 **손으로 나열**하고 있었다.

    pip install pytest shapely numpy ruff pyyaml
    pip install -e . --no-deps

`pyproject.toml` 과 `uv.lock` 에 의존성이 있는데 CI 는 그것을 안 읽는다.
**정본이 둘이고, 새 모듈을 쓰는 검사가 들어올 때마다 사람이 맞춰야 했다.**
2026-08-23 에 pyyaml 을 뒤늦게 붙인 것이 그 증거다.

결과: 로컬 283 · CI 216. **67개가 CI 에서 한 번도 안 돌았다.**
그중 `test_route_graph_snaps_nodes_like_build_graph` 는 PR #40 이 2,468줄을
지운 것을 잡을 수 있었던 검사다. 그 PR 은 초록불로 머지됐다.

초록불이 무엇을 보증하는지 모르면 CI 는 없는 것만 못하다 —
있다고 믿게 만들기 때문이다.

IN    .github/workflows/*.yml · pyproject.toml
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = sorted((ROOT / ".github/workflows").glob("*.yml"))


def test_ci_installs_from_lock_not_a_handpicked_list():
    bad = []
    for p in WF:
        t = p.read_text(encoding="utf-8")
        body = "\n".join(l for l in t.splitlines()
                         if not l.lstrip().startswith("#"))
        for m in re.finditer(r"pip install\s+(?!-e\s+\.)([^\n]+)", body):
            bad.append(f"  {p.name}: pip install {m.group(1)[:50]}")
    assert not bad, (
        "CI 가 의존성을 손으로 나열한다. uv.lock 이 정본이다.\n"
        + "\n".join(bad)
        + "\n  목록이 둘이면 반드시 어긋난다 — 로컬 283 vs CI 216 (2026-08-24).")


def test_ci_uses_uv_sync():
    hits = [p.name for p in WF
            if "uv sync" in p.read_text(encoding="utf-8")]
    assert hits, "어느 워크플로도 uv sync 를 쓰지 않는다"


def test_ci_runs_everything_through_uv():
    """시스템 python 으로 부르면 uv 가 만든 환경을 안 본다."""
    bad = []
    for p in WF:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            m = re.search(r"run:\s*(python3?|pytest|ruff)\b", code)
            if m:
                bad.append(f"  {p.name}:{i}  {line.strip()[:60]}")
    assert not bad, (
        "CI 가 시스템 인터프리터를 부른다. `uv run` 을 붙여라.\n"
        + "\n".join(bad))

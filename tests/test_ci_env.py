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
            # ★ 2026-08-24 확대. 종전에는 `run:` 바로 뒤만 봤다. 그래서
            #   `run: |` 블록 안의 `if [ -f x ]; then python ...` 를 놓쳤고,
            #   CI 가 `web/data 계보 검사` 에서 ModuleNotFoundError 로 죽었다.
            #   **검사가 사고와 같은 사각을 갖고 있었다.**
            if "uv run" in code or "uv sync" in code:
                continue
            m = re.search(r"(?<![-\w/.])(python3?|pytest|ruff|pip)(?=\s)", code)
            if m:
                bad.append(f"  {p.name}:{i}  {line.strip()[:60]}")
    assert not bad, (
        "CI 가 시스템 인터프리터를 부른다. `uv run` 을 붙여라.\n"
        + "\n".join(bad))


def test_navi_node_version_has_one_source_of_truth():
    """게이트와 빌드가 같은 노드에서 도는가 (DECISIONS §186-2).

    ★ 2026-09-18. `contract` 의 내비 타입 검사는 22, 배포 액션 `build-navi` 는 20 이었다.
      그 게이트는 maplibre 5→6 · vite 5→6 이 PR 초록 · 0 vulnerabilities 로 통과해 main 에서
      `TS1192` 로 죽은 사고 때문에 생긴 것이다(contract.yml). **런타임이 다르면 같은 형태가 또 난다** —
      게이트가 통과시킨 판과 배포가 빌드하는 판이 애초에 다르기 때문이다.
      정본은 `web/navi/.nvmrc` 하나. 노드 판을 손으로 두 군데 적지 않는다.
    """
    nvmrc = ROOT / "web/navi/.nvmrc"
    assert nvmrc.exists(), "web/navi/.nvmrc 가 없다 — 내비 노드 판의 정본이 사라졌다"
    assert nvmrc.read_text(encoding="utf-8").strip().isdigit(), "web/navi/.nvmrc 는 메이저 판 하나만 적는다"

    bad = []
    for p in [*WF, ROOT / ".github/actions/build-navi/action.yml"]:
        t = p.read_text(encoding="utf-8")
        body = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
        # 노드를 **직접 세우는** 파일만 본다. `build-navi` 에 위임하는 배포 셋은
        # 자기 자리에 판을 안 적으므로 정본이 갈릴 여지가 없다.
        if "actions/setup-node" not in body or "web/navi" not in body:
            continue
        if "node-version-file: web/navi/.nvmrc" not in body:
            bad.append(f"  {p.name}: web/navi 에서 노드를 세우는데 .nvmrc 를 안 읽는다")
        # 같은 파일 안에서 내비 구간이 판을 손으로 적으면 정본이 둘이 된다
        for m in re.finditer(r"node-version:\s*[\"']?(\d+)", body):
            seg = body[max(0, m.start() - 400):m.start() + 400]
            if "web/navi" in seg:
                bad.append(f"  {p.name}: 내비 근처에 node-version: {m.group(1)} 을 손으로 적었다")
    assert not bad, (
        "내비 노드 판의 정본이 둘 이상이다.\n" + "\n".join(bad)
        + "\n  게이트와 빌드가 다른 판에서 돌면 초록불이 배포를 보증하지 않는다.")


def test_devcontainer_actually_runs_its_setup_script():
    """`.devcontainer/setup.sh` 를 아무도 안 불렀다 (DECISIONS §186-1).

    ★ 2026-09-18. `postCreateCommand` 가 `uv sync` 한 줄이라 setup.sh 는 **한 번도 안 돌았다.**
      그 안의 `core.quotepath` · `core.precomposeunicode` 가 안 걸려 한글 파일명이 팔진수로 나온다.
      "기계 차이로 하루에 세 번 걸렸다" 는 이유로 만든 파일이 정작 배선이 빠져 있었다 —
      이 저장소가 반복해 겪은 **있는데 아무도 안 부르는** 그 형태다.
    """
    import json

    dc = ROOT / ".devcontainer/devcontainer.json"
    setup = ROOT / ".devcontainer/setup.sh"
    assert setup.exists(), ".devcontainer/setup.sh 가 없다"
    cmd = json.loads(dc.read_text(encoding="utf-8")).get("postCreateCommand", "")
    cmd = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    assert "setup.sh" in cmd, (
        f"postCreateCommand 가 setup.sh 를 안 부른다 — 지금: {cmd!r}\n"
        "  setup.sh 는 있는데 아무도 안 부르면 그 안의 방어가 전부 없는 것과 같다")
    assert "uv sync" not in cmd, "setup.sh 가 이미 uv sync 를 한다 — postCreateCommand 에서 또 하지 않는다"

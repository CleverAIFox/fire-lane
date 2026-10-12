#!/usr/bin/env python3
"""
test_pages_navi.py — 배포가 내비를 빌드하는가를 **묻는 자**를 민다. (§481)

── 왜 생겼나 ───────────────────────────────────────────────────
`tools/pages_add_navi.py` 는 `부류 관문` 이고 다섯 갈래로 운다 —
사이트를 짓는 워크플로가 없다 · 둘이다 · `stage-site → build-navi` 사슬이
끊겼다 · 그 워크플로가 `stage-site` 를 두 번 안 부른다 · `push` 와
`pull_request` 를 둘 다 안 든다.

**그 다섯 갈래가 한 번도 안 돌았다.** 미는 시험도 자기검사도 없었고
(§481 이 그 분모를 쟀다), 갈래마다 **실기 사고의 자국**이 적혀 있는데
(W1 의 2족 · §217-5 · §224) 그 자국을 지키는 자가 없었다.

★ 실물 저장소에서 **조용한가**를 먼저 들고, 그 다음 갈래마다 합성 트리로
  **우는가**를 든다. 한쪽만 들면 「무엇에나 운다」와 구별이 안 된다.

IN    없음 (실물 저장소 + 합성 트리)
OUT   없음 (검사)
PARAM 없음
밖    **워크플로가 옳은가는 안 본다** — YAML 문법 · 액션 판 · 권한은
      GitHub 와 `tools/gate_parity.py` 의 일이다. 여기가 드는 것은
      **그 다섯 갈래가 살아 있는가** 하나다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: 성립하는 최소 트리. 갈래마다 **이것을 한 군데 망가뜨려** 민다.
GOOD_WF = """
on:
  push:
    branches: [main]
  pull_request:
jobs:
  deploy:
    steps:
      - uses: ./.github/actions/stage-site
  dry:
    steps:
      - uses: ./.github/actions/stage-site
"""

GOOD_SITE = """
runs:
  steps:
    - uses: ./.github/actions/build-navi
"""


@pytest.fixture
def pan():
    """경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering)."""
    spec = importlib.util.spec_from_file_location(
        "pages_add_navi", ROOT / "tools/pages_add_navi.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _tree(tmp: Path, *, wf: str | None = GOOD_WF, site: str | None = GOOD_SITE,
          extra: str | None = None) -> Path:
    """합성 트리 하나. `None` 을 주면 그 파일을 안 만든다."""
    wfd = tmp / ".github" / "workflows"
    wfd.mkdir(parents=True)
    if wf is not None:
        (wfd / "deploy.yml").write_text(wf, encoding="utf-8")
    if extra is not None:
        (wfd / "deploy2.yml").write_text(extra, encoding="utf-8")
    if site is not None:
        d = tmp / ".github" / "actions" / "stage-site"
        d.mkdir(parents=True)
        (d / "action.yml").write_text(site, encoding="utf-8")
    return tmp


# ── ① 실물은 **조용하다** ───────────────────────────────────────
def test_the_real_repository_passes(pan):
    """여기가 빨간불이면 배포에서 내비가 빠졌다는 뜻이다."""
    assert not pan.check(), "실물 저장소에서 배포 사슬이 안 성립한다"


def test_a_minimal_synthetic_tree_passes(pan, tmp_path):
    """★ 합성 트리의 **성립하는 꼴**도 조용해야 한다 — 아니면 아래 갈래들이
    「트리가 합성이라서」 우는 것이 되고, 그 시험은 아무것도 안 민다."""
    assert not pan.check(_tree(tmp_path)), "성립하는 합성 트리에서 운다"


# ── ② 갈래마다 **운다** ────────────────────────────────────────
def test_no_workflow_builds_the_site(pan, tmp_path):
    assert pan.check(_tree(tmp_path, wf=None)), \
        "사이트를 짓는 워크플로가 없는데 조용하다 — 배포 본문이 사라져도 모른다"


def test_two_workflows_build_the_site(pan, tmp_path):
    """★ W1 이 닫은 2족 — 둘이면 나중 것이 앞의 것을 덮는다."""
    assert pan.check(_tree(tmp_path, extra=GOOD_WF)), \
        "사이트를 짓는 워크플로가 둘인데 조용하다"


def test_the_chain_to_build_navi_is_broken(pan, tmp_path):
    assert pan.check(_tree(tmp_path, site="runs:\n  steps: []\n")), \
        "stage-site 에서 build-navi 로 가는 사슬이 끊겼는데 조용하다"


def test_the_stage_site_action_is_missing(pan, tmp_path):
    assert pan.check(_tree(tmp_path, site=None)), \
        "stage-site 액션이 아예 없는데 조용하다"


def test_deploy_and_dry_run_do_not_share_the_body(pan, tmp_path):
    """★ §217-5 — PR 에서 통과한 것과 main 에서 도는 것이 다르면 시운전이
    아무것도 보증하지 않는다. `stage-site` 호출이 **둘**이어야 한다."""
    one = GOOD_WF.replace("""  dry:
    steps:
      - uses: ./.github/actions/stage-site
""", "")
    assert "stage-site" in one and one.count("stage-site") == 1
    assert pan.check(_tree(tmp_path, wf=one)), \
        "배포와 시운전이 같은 본문을 안 쓰는데 조용하다"


@pytest.mark.parametrize("drop", ["push:", "pull_request:"])
def test_one_of_the_two_triggers_is_missing(pan, tmp_path, drop: str):
    assert pan.check(_tree(tmp_path, wf=GOOD_WF.replace(drop, "schedule:"))), \
        f"`{drop}` 가 빠졌는데 조용하다 — 배포와 시운전 중 하나가 없다"


# ── ③ 이름을 박지 않는가 ───────────────────────────────────────
def test_the_workflow_file_may_be_renamed(pan, tmp_path):
    """★ 이 도구의 머리말이 적은 규율 — 파일 **이름을 박지 않는다.**
    박으면 다음에 파일을 옮길 때 검사가 **조용히 죽는다**(1족)."""
    t = _tree(tmp_path)
    wfd = t / ".github" / "workflows"
    (wfd / "deploy.yml").rename(wfd / "아무이름.yml")
    assert not pan.check(t), "워크플로 파일 이름을 바꾸자 운다 — 이름을 박았다"

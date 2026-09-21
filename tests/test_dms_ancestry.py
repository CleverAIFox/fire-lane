#!/usr/bin/env python3
"""
test_dms_ancestry.py — **`dms.py ancestry` 가 네 모양을 다 가르는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-21 (PLAN §13 W11-1 · DECISIONS §204 · §210). 봉인이 `2130b14` 를 가리켰는데
그 커밋은 `refs/pull/108/head` 에만 있었다. feat 가지에서 찍고 그 가지를
스쿼시했기 때문이다. `dms delta` 는 그 동안 「전수 재검사다」만 찍고 rc=0 이었고,
이틀 동안 §202~§208 의 blank 39 가 그 문으로 조용히 지나갔다.

★ 실제 저장소로는 이 도구를 **못 시험한다** — CI 클론이 얕아서다. 그래서 합성
  저장소를 짓고 네 모양을 하나씩 심는다. 실제 트리에 대한 판정은 `verify.sh` 의
  「봉인 조상」 단계(로컬 전용)가 든다.

    조상이다       → 0
    옆 가지 커밋   → 1  (찍은 가지가 스쿼시되기 전 — 아직 있기는 하다)
    없는 커밋      → 1  (스쿼시 뒤 — `2130b14` 의 모양)
    얕은 클론      → 1  (못 잰 것을 통과로 치지 않는다)
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _dms():
    spec = importlib.util.spec_from_file_location("_dms_anc", ROOT / "tools" / "dms.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


dms = _dms()


def _git(d: Path, *a: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                        "-c", "init.defaultBranch=main", *a],
                       cwd=d, capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _commit(d: Path, name: str) -> str:
    (d / name).write_text(name, encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", name)
    return _git(d, "rev-parse", "--short", "HEAD")


def _seal(d: Path, commit: str) -> None:
    p = d / "data" / "dms"
    p.mkdir(parents=True, exist_ok=True)
    (p / "SEAL.json").write_text(json.dumps({"commit": commit}, indent=1), encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    d = tmp_path / "r"
    d.mkdir()
    _git(d, "init", "-q")
    _commit(d, "a")
    return d


def test_ancestor_is_green(repo: Path):
    c = _git(repo, "rev-parse", "--short", "HEAD")
    _commit(repo, "b")
    _seal(repo, c)
    rc, why = dms.ancestry(repo)
    assert rc == 0, why


def test_side_branch_commit_is_red(repo: Path):
    """찍은 가지가 **아직 있는** 경우 — 커밋은 있는데 이 트리의 역사 밖이다."""
    _git(repo, "switch", "-q", "-c", "feat/x")
    side = _commit(repo, "side")
    _git(repo, "switch", "-q", "main")
    _commit(repo, "c")
    _seal(repo, side)
    rc, why = dms.ancestry(repo)
    assert rc == 1 and "조상이 아니다" in why, why


def test_vanished_commit_is_red(repo: Path):
    """스쿼시 뒤 — 이 저장소가 모르는 해시. `2130b14` 가 이 모양이었다."""
    _seal(repo, "2130b14")
    rc, why = dms.ancestry(repo)
    assert rc == 1 and "없다" in why, why


def test_shallow_clone_is_red_not_skipped(repo: Path, tmp_path: Path):
    """얕은 클론은 **실패**다. 못 잰 것을 통과로 치면 CI 에서 영원히 초록이다."""
    c = _git(repo, "rev-parse", "--short", "HEAD")
    for n in "bcd":
        _commit(repo, n)
    _seal(repo, c)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seal")
    shallow = tmp_path / "s"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow)],
                   check=True, capture_output=True)
    rc, why = dms.ancestry(shallow)
    assert rc == 1 and "얕은" in why, why


def test_malformed_or_missing_seal_is_red(repo: Path):
    rc, why = dms.ancestry(repo)
    assert rc == 1 and "봉인이 없다" in why, why
    _seal(repo, "(git 밖)")
    rc, why = dms.ancestry(repo)
    assert rc == 1 and "해시 꼴" in why, why


def test_verify_runs_the_step():
    """verify 가 이 단계를 실제로 부르는가 — 도구만 있고 배선이 없으면 없는 것과 같다."""
    s = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    assert 'step "봉인 조상" uv run python tools/dms.py ancestry' in s, (
        "verify.sh 에 「봉인 조상」 단계가 없다 — `dms.py ancestry` 가 아무 데서도 안 돈다")

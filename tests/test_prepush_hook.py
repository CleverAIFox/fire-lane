"""pre-push 훅이 **실제로 걸리는가** — 합성 결함으로 민다.  (Zm39 · DECISIONS §580)

IN    .githooks/pre-push · .githooks/pre-push.gates · .githooks/global-pre-push.sh
OUT   없음 (검사)
밖    **게이트 각각이 옳은가는 안 본다** — 그것은 각 도구의 시험이 든다. 여기는 훅 **배선**이다:
      게이트가 빨가면 푸시가 막히는가 · 우회가 있는가 · 시간을 찍는가 · 전역 이음이 저장소 훅에 **도달**하는가.

★ 「훅이 있다」와 「훅이 돈다」는 다르다(`global-chain.sh` 가 pre-commit 에서 치른 1족). 그래서 **진짜 `git push`** 를 임시 저장소 · 임시 원격으로 돌린다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".githooks"


def _git(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    e = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", **(env or {})}
    return subprocess.run(["git", *args], cwd=cwd, env=e, capture_output=True, text=True, check=False, timeout=60)


@pytest.fixture
def repo(tmp_path: Path):
    """저장소 + 원격 + **전역 이음**(임시 hooksPath). 훅 본체는 이 저장소의 것을 복사한다."""
    work, remote, glob = tmp_path / "work", tmp_path / "remote.git", tmp_path / "global"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, timeout=60)
    work.mkdir()
    glob.mkdir()
    _git(work, "init", "-q", "-b", "part/x")
    (work / ".githooks").mkdir()
    shutil.copy(HOOKS / "pre-push", work / ".githooks/pre-push")
    shutil.copy(HOOKS / "global-pre-push.sh", glob / "pre-push")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    _git(work, "add", "-A")
    assert _git(work, "commit", "-q", "-m", "c1").returncode == 0
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "config", "core.hooksPath", str(glob))
    return work


def _gates(work: Path, body: str) -> dict:
    g = work / "gates.txt"
    g.write_text(body, encoding="utf-8")
    return {"FIRE_LANE_PREPUSH_GATES": str(g)}


def _push(work: Path, env: dict, *extra: str) -> subprocess.CompletedProcess:
    return _git(work, "push", *extra, "origin", "HEAD:refs/heads/part/x", env=env)


def test_a_failing_gate_blocks_the_push_and_names_it(repo: Path) -> None:
    env = _gates(repo, "초록 게이트\ttrue\n빨간 게이트\techo 합성 결함; exit 3\n끝 게이트\ttrue\n")
    r = _push(repo, env)
    assert r.returncode != 0, "빨간 게이트가 있는데 푸시가 통과했다 — 훅이 안 돈다"
    out = r.stdout + r.stderr
    assert "빨간 게이트" in out and "합성 결함" in out, out
    assert "끝 게이트" in out, "첫 빨강에서 멈췄다 — 한 번에 다 보여야 왕복이 준다"
    assert _git(repo, "ls-remote", "origin").stdout.strip() == "", "막혔는데 원격에 올라갔다"


def test_green_gates_pass_and_print_the_elapsed_time(repo: Path) -> None:
    r = _push(repo, _gates(repo, "하나\ttrue\n둘\ttrue\n"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "pre-push 통과 —" in r.stdout + r.stderr and "초" in r.stdout + r.stderr, "시간을 안 찍는다"
    assert _git(repo, "ls-remote", "origin").stdout.strip() != "", "통과했는데 원격에 안 올라갔다"


def test_the_bypass_exists_and_warns_every_time(repo: Path) -> None:
    env = _gates(repo, "빨강\tfalse\n")
    assert _push(repo, env, "--no-verify").returncode == 0, "--no-verify 가 안 통한다"
    _git(repo, "push", "-q", "--delete", "origin", "part/x")
    r = _push(repo, {**env, "FIRE_LANE_SKIP_PREPUSH": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "우회했다" in r.stdout + r.stderr, "우회가 조용하다 — 쓴 흔적이 남아야 한다"


def test_a_dirty_tracked_tree_blocks_because_gates_measure_the_tree_not_the_commit(repo: Path) -> None:
    (repo / "a.txt").write_text("안 커밋한 수정\n", encoding="utf-8")
    r = _push(repo, _gates(repo, "초록\ttrue\n"))
    assert r.returncode != 0 and "안 커밋한 수정" in r.stdout + r.stderr, r.stdout + r.stderr


def test_a_gate_that_rewrites_a_tracked_file_blocks(repo: Path) -> None:
    r = _push(repo, _gates(repo, "고쳐 쓰는 게이트\techo x >> a.txt\n"))
    assert r.returncode != 0 and "추적 파일을 바꿨다" in r.stdout + r.stderr, r.stdout + r.stderr


def test_deleting_a_branch_skips_the_gates(repo: Path) -> None:
    assert _push(repo, _gates(repo, "초록\ttrue\n")).returncode == 0
    r = _git(repo, "push", "origin", "--delete", "part/x", env=_gates(repo, "빨강\tfalse\n"))
    assert r.returncode == 0, "삭제 푸시가 게이트에 막혔다 — 지울 수 없게 된다"


def test_the_probe_blocks_loudly_instead_of_passing(repo: Path) -> None:
    """도달 탐침이 켜져 있으면 막는다 — 조용한 영구 우회 스위치가 되지 않게(pre-commit 이 치른 것)."""
    r = _push(repo, {**_gates(repo, "초록\ttrue\n"), "FIRE_LANE_HOOK_PROBE": "1"})
    assert r.returncode != 0 and "pre-push 체인 진입" in r.stdout + r.stderr


def test_the_real_gate_file_lists_only_tools_that_exist() -> None:
    gates = [ln.split("\t", 1) for ln in (HOOKS / "pre-push.gates").read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
    assert len(gates) >= 7, gates
    for name, cmd in gates:
        for tok in cmd.split():
            if tok.startswith("tools/"):
                assert (ROOT / tok).exists(), f"{name}: {tok} 가 없다"


def test_the_hooks_are_executable() -> None:
    for f in ("pre-push", "global-pre-push.sh"):
        assert os.access(HOOKS / f, os.X_OK), f"{f} 에 실행권한이 없다 — 전역 훅이 후보로 안 집는다"

"""물려받은 `GIT_DIR` 이 본 저장소를 건드리지 못하는가 — 훅 쪽(`unset`)과 시험 쪽(`conftest` 픽스처) 둘 다. (PLAN #200)

★ 2026-11-08 복제본 실측. worktree 에서 푸시하면 훅이 `GIT_DIR=<본>/.git/worktrees/<이름>` 을 물려받고, 게이트의 `pytest` 와 시험의 자식 `git` 이 그것을 상속해
  `git init` · `config core.hooksPath` 가 본 저장소에 `core.bare=true` · `hooksPath` 를 남긴다. 길이 둘이라 막는 곳도 둘이다 —
  훅 머리의 `unset`(훅을 거치는 모든 게이트) · `conftest` 의 픽스처(사람이 `uv run pytest` 를 직접 칠 때).

★ 양성 대조 — 각각 **막는 줄을 빼면 운다**: 훅은 `unset` 줄을 지운 사본으로, 시험 쪽은 `--noconftest` 로 돌려 미끼 저장소가 실제로 오염되는 것을 본다.

밖    **11-07 에 무엇이 `GIT_DIR` 을 물려줬는지는 모른다**(그날 게이트에는 `시험 묶음` 이 없었다). 이 시험은 재현된 경로 둘만 막는다.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-push"
PROBE = ROOT / "tests" / "gitenv_probe_case.py"
ZERO = "0" * 40


def _decoy(tmp: Path) -> Path:
    """미끼 저장소 — 오염되면 안 되는 쪽. `core.bare` 와 `core.hooksPath` 를 본다."""
    d = tmp / "decoy"
    d.mkdir()
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q"], cwd=d, check=True, timeout=60, env=clean)
    # 커밋이 있어야 한다 — 중첩 pytest 의 세션 가드(`tracked_guard`)가 물려받은 GIT_DIR 로 `git diff HEAD` 를 먼저 부른다
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "c0"],
                   cwd=d, check=True, timeout=60, env=clean)
    return d


def _cfg(decoy: Path, key: str) -> str:
    r = subprocess.run(["git", "config", "--local", "--get", key], cwd=decoy, capture_output=True, text=True, timeout=60,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})
    return r.stdout.strip()


def _run_probe(decoy: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_DIR": str(decoy / ".git")}
    return subprocess.run([sys.executable, "-m", "pytest", str(PROBE), "-q", "-p", "no:cacheprovider", *extra],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)


def test_conftest_scrubs_the_inherited_git_dir_so_the_decoy_stays_clean(tmp_path):
    decoy = _decoy(tmp_path)
    r = _run_probe(decoy)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _cfg(decoy, "core.hooksPath") == "" and _cfg(decoy, "core.bare") in ("", "false")


def test_without_the_fixture_the_probe_pollutes_the_decoy_so_the_test_above_can_fail(tmp_path):
    """양성 대조 — `--noconftest` 면 같은 탐침이 미끼의 config 에 쓴다(= 사고 #200 의 모양)."""
    decoy = _decoy(tmp_path)
    r = _run_probe(decoy, "--noconftest")
    polluted = _cfg(decoy, "core.hooksPath") != "" or _cfg(decoy, "core.bare") not in ("", "false") or r.returncode != 0
    assert polluted, "픽스처 없이도 미끼가 멀쩡하다 — 탐침이 사고를 못 만든다(위 시험이 아무것도 안 잰다)"


def _hook_env_gate(tmp: Path, hook: Path) -> subprocess.CompletedProcess:
    """물려받은 `GIT_DIR` 을 **게이트가** 보는가. 게이트 하나가 그 변수가 비어 있어야 초록이다."""
    work = tmp / "work"
    work.mkdir()
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q", "-b", "part/x"], cwd=work, check=True, timeout=60, env=clean)
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True, timeout=60, env=clean)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c1"], cwd=work, check=True, timeout=60, env=clean)
    gates = tmp / "gates.txt"
    gates.write_text('GIT_DIR 이 비었다\ttest -z "${GIT_DIR:-}"\n', encoding="utf-8")
    (work / ".githooks").mkdir()
    (work / ".githooks" / "pre-push").write_text(hook.read_text(encoding="utf-8"), encoding="utf-8")
    env = {**clean, "GIT_DIR": str(work / ".git"), "FIRE_LANE_PREPUSH_GATES": str(gates)}
    line = f"refs/heads/part/x {'1' * 40} refs/heads/part/x {ZERO}\n"
    return subprocess.run(["bash", str(work / ".githooks" / "pre-push")], cwd=work, env=env, input=line, capture_output=True, text=True, timeout=120)


def test_the_hook_unsets_the_inherited_git_dir_before_the_gates_run(tmp_path):
    r = _hook_env_gate(tmp_path, HOOK)
    assert r.returncode == 0, r.stdout + r.stderr


def test_without_the_unset_line_the_gate_sees_git_dir_so_the_test_above_can_fail(tmp_path):
    """양성 대조 — `unset` 줄을 지운 사본에서는 게이트가 `GIT_DIR` 을 본다."""
    stripped = tmp_path / "pre-push.stripped"
    src = HOOK.read_text(encoding="utf-8")
    kept = [ln for ln in src.splitlines(keepends=True) if "local-env-vars" not in ln]
    assert len(kept) == len(src.splitlines(keepends=True)) - 1, "unset 줄이 한 줄이 아니다 — 대조가 무엇을 지우는지 알 수 없다"
    stripped.write_text("".join(kept), encoding="utf-8")
    r = _hook_env_gate(tmp_path, stripped)
    assert r.returncode != 0 and "GIT_DIR 이 비었다" in r.stdout + r.stderr, r.stdout + r.stderr


def test_the_session_guard_reads_its_own_tree_even_with_an_inherited_git_dir(tmp_path, monkeypatch):
    """★★ 세션 훅(`tracked_guard`)은 자동 픽스처보다 **먼저** 돈다 — 그쪽이 못 막는 구멍. (PLAN #200 ⑤)

    양성 대조 — 물려받은 `GIT_DIR` 이 미끼를 가리키는데 가드는 **자기 트리**(`tmp_path/work`)의 더러움을 읽어야 한다.
    같은 환경에서 맨 `git diff HEAD` 는 미끼를 본다(= 막는 줄이 없으면 가드가 엉뚱한 저장소를 읽는다는 증거).
    """
    import tracked_guard as G
    decoy = _decoy(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    def run(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=work, check=True, timeout=60, env=clean, capture_output=True)
    run("init", "-q")
    (work / "f.txt").write_text("1", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "c")
    (work / "f.txt").write_text("2", encoding="utf-8")                 # 더럽힌다
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    raw = subprocess.run(["git", "diff", "HEAD", "--name-only"], cwd=work, capture_output=True, text=True, timeout=60)
    assert "f.txt" not in raw.stdout                                    # 맨 git 은 물려받은 미끼를 본다
    assert list(G.snapshot(work)) == ["f.txt"]                          # 가드는 제 트리를 본다

#!/usr/bin/env python3
"""
test_batch_tools.py — **배치 도구가 저장소 안에서 재현되는가.**  (DECISIONS §214-1)

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22. 배치를 돌리는 `fl.sh` · `tidy.sh` 가 INBOX(다운로드 폴더)에만 살았다.
버전 관리 · 시험 밖이었고, INBOX 를 비우자 **도구가 통째로 사라졌다.** 같은 날
레이크 검사(L3)가 INBOX 의 우리 패치 zip 을 「레이크 밖 원본」으로 잡아 verify 가
빨개졌다 — 우리가 만든 포장물을 우리 검사가 모르는 상태였다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 세 스크립트가 bash 문법으로 읽힌다
    2. 부트스트랩이 **패치 안의** tools/fl.sh 를 고른다 — 새로 만드는 패치도,
       저장소 판을 고치는 패치도. 없으면 저장소 판
    3. fl.sh 가 방송을 `exec` 하지 않는다 — 뒤에 정리가 있다. 정리는 `--auto`
    4. fl.sh 가 소비한 포장물을 INBOX 에서 치운다
    5. 레이크 처분 목록이 우리 패치 zip 을 안다
"""
from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "tools"
SCRIPTS = [T / "fl.sh", T / "branch_tidy.sh", T / "inbox_fl.sh"]


def _zip(out: Path, *files: Path) -> None:
    """포장물 zip 을 만든다. ★ `zip` 명령을 쓰지 않는다 — 사용자 기계(WSL)에 없어서
    skip 이 났고, skip 정책(tests/skip_policy.py)이 사유 없는 skip 을 실패로 셌다."""
    import zipfile
    with zipfile.ZipFile(out, "w") as z:
        for f in files:
            z.write(f, f.name)


def test_scripts_parse():
    for s in SCRIPTS:
        assert s.exists(), f"{s.relative_to(ROOT)} 가 없다"
        r = subprocess.run(["bash", "-n", str(s)], capture_output=True, text=True)
        assert r.returncode == 0, f"{s.name} 문법 오류\n{r.stderr}"


def _git(cwd: Path, *a: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True,
                          text=True, env=env).stdout


def _fake(repo: Path, body: str) -> None:
    (repo / "tools").mkdir(exist_ok=True)
    (repo / "tools" / "fl.sh").write_text(f"#!/usr/bin/env bash\necho {body} \"$@\"\n")


def _world(tmp: Path, seed: str | None):
    """bare 원격 · 작업 저장소(origin/part/infra) · INBOX 를 만든다."""
    bare, work, inbox = tmp / "r.git", tmp / "work", tmp / "inbox"
    _git(tmp, "init", "-q", "--bare", str(bare))
    _git(tmp, "clone", "-q", str(bare), str(work))
    (work / "README").write_text("x\n")
    if seed:
        _fake(work, seed)
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "init")
    _git(work, "push", "-q", "origin", "HEAD:refs/heads/part/infra")
    _git(work, "fetch", "-q", "origin")
    inbox.mkdir()
    shutil.copy(T / "inbox_fl.sh", inbox / "fl.sh")
    return work, inbox


def _patch(work: Path, body: str, out: Path) -> None:
    _git(work, "switch", "-q", "-c", "tmp-patch", "origin/part/infra")
    _fake(work, body)
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "patch")
    out.write_text(_git(work, "format-patch", "-1", "--stdout"))
    _git(work, "switch", "-q", "-")


def _run(inbox: Path, work: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "FIRE_LANE_REPO": str(work)}
    return subprocess.run(["bash", str(inbox / "fl.sh"), "feat/x", "--all"],
                          capture_output=True, text=True, env=env)


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_prefers_patch_that_creates_the_tool(tmp_path):
    work, inbox = _world(tmp_path, seed=None)
    _patch(work, "NEW", inbox / "0001-fix.patch")
    r = _run(inbox, work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NEW feat/x --all" in r.stdout, r.stdout


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_applies_patch_on_top_of_repo_version(tmp_path):
    work, inbox = _world(tmp_path, seed="OLD")
    _patch(work, "NEWER", inbox / "0001-fix.patch")
    r = _run(inbox, work)
    assert "NEWER feat/x --all" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_falls_back_to_repo_version(tmp_path):
    work, inbox = _world(tmp_path, seed="OLD")
    r = _run(inbox, work)
    assert "OLD feat/x --all" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("unzip"), reason="환경skip(도구) — unzip 이 없다(부트스트랩 · fl.sh 가 쓴다)")
def test_bootstrap_reads_patch_inside_zip(tmp_path):
    work, inbox = _world(tmp_path, seed="OLD")
    p = tmp_path / "0001-fix.patch"
    _patch(work, "ZIPPED", p)
    _zip(inbox / "fire-lane-x.zip", p)
    r = _run(inbox, work)
    assert "ZIPPED feat/x --all" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("unzip"), reason="환경skip(도구) — unzip 이 없다(부트스트랩 · fl.sh 가 쓴다)")
def test_bootstrap_same_patch_in_zip_and_loose(tmp_path):
    """평소 절차는 zip 을 INBOX 에 풀어 **같은 패치가 두 벌** 남는다 — 한 번만 얹는다."""
    work, inbox = _world(tmp_path, seed="OLD")
    _patch(work, "ONCE", inbox / "0001-fix.patch")
    _zip(inbox / "fire-lane-x.zip", inbox / "0001-fix.patch")
    r = _run(inbox, work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ONCE feat/x --all" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_ignores_foreign_patches(tmp_path):
    """INBOX 는 공용 다운로드 폴더다. 남의 패치가 tools/fl.sh 를 건드려도 집지 않는다."""
    work, inbox = _world(tmp_path, seed="OLD")
    _patch(work, "FOREIGN", inbox / "D0216.patch")
    r = _run(inbox, work)
    assert "OLD feat/x --all" in r.stdout, r.stdout + r.stderr


FOREIGN = "From x\nSubject: other repo\n---\n+++ b/README\n"


def _pick(inbox: Path) -> list[str]:
    env = {**os.environ, "FIRE_LANE_INBOX": str(inbox), "FIRE_LANE_REPO": str(ROOT)}
    r = subprocess.run(["bash", str(T / "fl.sh"), "feat/x", "--pick"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    return [l for l in r.stdout.splitlines() if l.endswith(".patch") and "무시" not in l]


@pytest.mark.skipif(not shutil.which("unzip"), reason="환경skip(도구) — unzip 이 없다(fl.sh 가 쓴다)")
def test_fl_picks_only_this_batch(tmp_path):
    """2026-09-22 실제 사고 — hathor · thoth 의 패치가 적용 후보에 올라 3단계에서 멈췄다."""
    inbox = tmp_path / "in"
    inbox.mkdir()
    (inbox / "0001-fix.patch").write_text("From a\nSubject: ours\n")
    _zip(inbox / "fire-lane-x.zip", inbox / "0001-fix.patch")
    (inbox / "D0216.patch").write_text(FOREIGN)
    (inbox / "thoth-105-fixture-honest.patch").write_text(FOREIGN + "x")
    assert _pick(inbox) == ["0001-fix.patch"]


def test_fl_without_zip_takes_format_patch_names_only(tmp_path):
    inbox = tmp_path / "in"
    inbox.mkdir()
    (inbox / "0001-a.patch").write_text("From a\n")
    (inbox / "0002-b.patch").write_text("From b\n")
    (inbox / "D0216.patch").write_text(FOREIGN)
    assert _pick(inbox) == ["0001-a.patch", "0002-b.patch"]


def test_fl_runs_tidy_after_release_and_clears_inbox():
    s = (T / "fl.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    assert "exec bash tools/merge_batch.sh" not in code, "방송을 exec 하면 정리가 안 돈다"
    assert "bash tools/merge_batch.sh --release" in code
    assert "bash tools/branch_tidy.sh --auto" in code, "배치 끝에 가지 정리가 없다"
    assert "_applied" in code, "소비한 포장물을 INBOX 에서 안 치운다 — 다음 실행이 옛 패치를 또 집는다"
    assert "FL_RELOCATED" in code, "자기 복사 없이 가지를 바꾸면 도는 중에 다른 판을 읽는다"


def test_tidy_auto_never_closes_or_deletes_remote():
    s = (T / "branch_tidy.sh").read_text(encoding="utf-8")
    # ask() 가 --auto 에서 거짓을 내므로 PR 닫기 · 원격 삭제는 대화형에서만 닿는다
    assert '[ "$AUTO" = 1 ] && return 1' in s, "--auto 의 ask 가 거짓을 내지 않는다"
    assert "merged_by_content" in s


def test_lake_disposition_knows_our_patch_zip():
    # ★ 경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering — 경로 조작 금지)
    import importlib.util

    from firelane import ledger

    spec = importlib.util.spec_from_file_location("lakecheck_t", T / "lakecheck.py")
    assert spec and spec.loader
    lakecheck = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lakecheck)
    globs = lakecheck.disposed(ledger.load_sources())
    for name in ("fire-lane-navi-closed-loop.zip", "fire-lane-turn-radius.zip"):
        assert any(fnmatch.fnmatch(name, g) for g in globs), (
            f"{name} 을 레이크 L3 가 「밖에 있는 원본」으로 잡는다 — landing_disposition 에 적는다")


def test_fl_work_dir_is_per_run():
    """2026-09-22 실제 사고 — verify 안의 `--pick` 시험이 고정 경로 /tmp/fl-patches 를
    비워 7분 뒤 PR 단계가 PR_BODY.md 를 못 찾았다. 실행마다 새 자리여야 한다."""
    s = (T / "fl.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    assert "WORK=/tmp/fl-patches" not in code
    assert "mktemp -d /tmp/fl-patches." in code
    assert "applied()" in code, "다시 돌 때 이미 얹힌 패치를 건너뛰지 않는다"


def test_fl_rebuilds_branch_holding_older_version():
    """2026-09-22 실제 사고 — 6단계에서 멈춘 가지에 **고친 판** 패치를 얹으려다 4단계가
    파일마다 「already exists」 로 멈췄다. 3단계는 base 에 대 봤고 4단계는 옛 가지에
    얹었다. 옛 판이 있으면 base 에서 새로 짓고, 원격에 올라간 가지는 건드리지 않는다."""
    s = (T / "fl.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    assert 'git switch -q -C "$BR" "origin/$BASE"' in code
    assert 'git rev-parse -q --verify "origin/$BR"' in code, "원격 가지를 몰래 갈아 끼운다"
    assert "MISSING" in code

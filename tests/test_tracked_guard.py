"""세션 지문 장치가 **실제로 무는가** — 합성 결함으로 양쪽을 민다.  (Zm39 · DECISIONS §580)

IN    tests/tracked_guard.py
OUT   없음 (검사)
밖    **실제 저장소의 세션이 깨끗한지는 안 본다** — 그것은 장치가 매 세션 끝에 스스로 잰다. 여기는 장치가 **살아 있는지**다:
      추적 파일을 바꾸면 세션이 실패하고 · 안 바꾸면 통과하고 · 이미 더러운 파일이 또 바뀌어도 잡는다.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import tracked_guard as G

TESTS = Path(__file__).resolve().parent


def _git(cwd: Path, *a: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", *a], cwd=cwd, env=env, check=True, capture_output=True, timeout=60)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "tracked.txt").write_text("원본\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("다른\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "c")
    return tmp_path


def test_snapshot_sees_only_dirty_tracked_files(repo: Path) -> None:
    assert G.snapshot(repo) == {}
    (repo / "tracked.txt").write_text("바뀜\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("추적 안 됨\n", encoding="utf-8")
    assert set(G.snapshot(repo)) == {"tracked.txt"}, "추적 안 된 파일을 센다 — 산출물은 시험이 만드는 것이 정상이다"


def test_changed_catches_clean_to_dirty_dirty_to_clean_and_dirty_again(repo: Path) -> None:
    (repo / "other.txt").write_text("세션 전부터 더러움\n", encoding="utf-8")
    before = G.snapshot(repo)
    (repo / "tracked.txt").write_text("세션 중에 바뀜\n", encoding="utf-8")          # 깨끗 → 더러움
    (repo / "other.txt").write_text("더러운 채 또 바뀜\n", encoding="utf-8")         # 더러움 → 더 바뀜
    assert G.changed(before, G.snapshot(repo)) == ["other.txt", "tracked.txt"]
    (repo / "tracked.txt").write_text("원본\n", encoding="utf-8")                  # 더러움 → 되돌림도 변화다
    assert G.changed(before, G.snapshot(repo)) == ["other.txt"]


def test_unchanged_dirty_state_is_not_a_change(repo: Path) -> None:
    (repo / "tracked.txt").write_text("세션 전부터 더러움\n", encoding="utf-8")
    assert G.changed(G.snapshot(repo), G.snapshot(repo)) == []


def _session(repo: Path, body: str) -> subprocess.CompletedProcess:
    (repo / "test_x.py").write_text(body, encoding="utf-8")
    _git(repo, "add", "test_x.py")
    _git(repo, "commit", "-q", "-m", "t")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(TESTS), os.environ.get("PYTHONPATH", "")])}
    # 장치의 **훅 두 개**를 플러그인으로 건다. 시험 본체는 임시 저장소의 것이고 `ROOT` 는 그 저장소로 돌려 쓴다.
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "tg_for_test", "test_x.py"],
                          cwd=repo, env=env, capture_output=True, text=True, timeout=120, check=False)


@pytest.fixture
def plugin(tmp_path_factory, monkeypatch) -> None:
    """`tracked_guard` 를 임시 저장소 루트로 돌려 쓰는 얇은 플러그인 — `ROOT` 만 `cwd` 로 바꾼다."""
    d = tmp_path_factory.mktemp("plug")
    (d / "tg_for_test.py").write_text(
        "import tracked_guard as g\nfrom pathlib import Path\n"
        "g.ROOT = Path.cwd()\n"
        "_s = g.snapshot\n"
        "g.snapshot = lambda root=None: _s(g.ROOT)\n"
        "pytest_sessionstart = g.pytest_sessionstart\npytest_sessionfinish = g.pytest_sessionfinish\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([str(d), os.environ.get("PYTHONPATH", "")]))


def test_a_session_that_rewrites_a_tracked_file_fails_even_though_every_test_passes(repo: Path, plugin) -> None:
    r = _session(repo, "from pathlib import Path\n\ndef test_quiet_writer():\n    Path('tracked.txt').write_text('시험이 조용히 씀\\n')\n")
    out = r.stdout + r.stderr
    assert "1 passed" in out, out
    assert r.returncode != 0, "시험은 초록인데 추적 파일이 바뀐 세션이 통과했다 — 장치가 안 문다\n" + out
    assert "tracked.txt" in out and "추적 파일을 바꿨다" in out, out


def test_a_session_that_writes_nothing_tracked_passes(repo: Path, plugin) -> None:
    r = _session(repo, "from pathlib import Path\n\ndef test_writes_an_untracked_artifact():\n    Path('artifact.csv').write_text('산출물\\n')\n")
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_session_whose_test_rewrites_a_tracked_file_and_puts_it_back_still_fails(repo: Path, plugin) -> None:
    """★ 전후 지문이 **못 잡던** 것 — 고쳤다 되돌린다(`test_refcheck_paths` 의 모양). 앞뒤 해시는 같다. 쓰는 순간을 보는 감사 훅이 문다."""
    body = ("from pathlib import Path\n\ndef test_probe_and_restore():\n    p = Path('tracked.txt')\n    keep = p.read_text()\n"
            "    p.write_text(keep + 'probe')\n    p.write_text(keep)\n")
    r = _session(repo, body)
    out = r.stdout + r.stderr
    assert "1 passed" in out, out
    assert r.returncode != 0, "고쳤다 되돌린 세션이 통과했다 — 감사 훅이 안 문다\n" + out
    assert "tracked.txt" in out and "제자리에서 쓰기로 열었다" in out and "test_probe_and_restore" in out, out


def test_reading_and_writing_untracked_or_temp_files_is_quiet(repo: Path, plugin) -> None:
    body = ("from pathlib import Path\n\ndef test_ok(tmp_path):\n    Path('tracked.txt').read_text()\n"
            "    (tmp_path / 'x').write_text('a')\n    Path('artifact.csv').write_text('b')\n")
    r = _session(repo, body)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_mirror_copies_only_what_is_asked_and_links_the_rest(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "a" / "b").mkdir(parents=True)
    (src / "a" / "b" / "f.txt").write_text("원본", encoding="utf-8")
    (src / "a" / "g.txt").write_text("옆", encoding="utf-8")
    (src / "top.txt").write_text("위", encoding="utf-8")
    m = G.mirror_tree(tmp_path / "m", replace={"a/b/f.txt": "바뀜"}, root=src)
    assert (m / "a" / "b" / "f.txt").read_text(encoding="utf-8") == "바뀜" and not (m / "a" / "b" / "f.txt").is_symlink()
    assert (m / "a" / "g.txt").is_symlink() and (m / "top.txt").is_symlink()
    assert (src / "a" / "b" / "f.txt").read_text(encoding="utf-8") == "원본"       # 실물은 안 건드린다

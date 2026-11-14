"""
test_deliver_guards.py — `deliver.py pack` 의 입구 가드 넷을 **심은 결함으로** 문다.

W13-19 밑동이 가지 끝이면 공허하게 참 · W13-21 `.venv` 없을 때 낳는 쪽 ·
W13-22 없는 `--extra` · W13-24 EXPECT pytest 줄의 벽시계.
저장소는 전부 tmp_path 의 합성이다 — 실제 저장소의 추적 파일은 안 건드린다.

IN    tools/deliver.py · tools/delivercheck.py · 합성 저장소(tmp_path)
OUT   없음 (검사)
PARAM 없음
밖    **`pack` 전 경로(원격 · 레이크)는 안 돈다** — 입구 가드만 합성으로 문다. `.venv` 없는 실제 워크트리에서의 끝까지 실행은 사람이 한 번 본다.
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("deliver", ROOT / "tools/deliver.py")
assert _spec and _spec.loader
DL = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = DL
_spec.loader.exec_module(DL)


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                       cwd=cwd, capture_output=True, text=True, check=True, timeout=60)
    return r.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, list[str]]:
    _git(tmp_path, "init", "-q", "-b", "main")
    shas = []
    for i in range(3):
        (tmp_path / "f").write_text(str(i), encoding="utf-8")
        _git(tmp_path, "add", "f")
        _git(tmp_path, "commit", "-q", "-m", f"c{i}")
        shas.append(_git(tmp_path, "rev-parse", "HEAD"))
    return tmp_path, shas


def _runner(cwd: Path):
    def run(args):
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout + p.stderr
    return run


def test_w13_19_base_must_be_a_proper_ancestor_of_the_branch_tip(tmp_path):
    repo, (c0, c1, c2) = _repo(tmp_path)
    run = _runner(repo)
    assert DL.base_verdict(c0, f"{c0}..{c2}", run) == "", "정상 밑동에 운다"
    assert DL.base_verdict(c1, f"{c1}..HEAD", run) == "", "끝이 HEAD 인 범위에 운다"
    # 심은 결함 ① 밑동 == 끝 (포장 전에 푸시한 꼴)
    assert "끝과 같다" in DL.base_verdict(c2, f"{c0}..{c2}", run)
    # 심은 결함 ② 조상이 아닌 밑동
    _git(repo, "checkout", "-q", "-b", "other", c0)
    (repo / "g").write_text("x", encoding="utf-8")
    _git(repo, "add", "g")
    _git(repo, "commit", "-q", "-m", "side")
    side = _git(repo, "rev-parse", "HEAD")
    assert "조상이 아니다" in DL.base_verdict(side, f"{c0}..{c2}", run)
    assert "못 읽었다" in DL.base_verdict(c0, "c0..nope", run), "끝을 못 읽으면 통과시킨다"


def test_w13_19_pack_stops_before_formatting_patches(tmp_path, monkeypatch):
    repo, (c0, _c1, c2) = _repo(tmp_path)
    monkeypatch.setattr(DL, "ROOT", repo)
    monkeypatch.setattr(DL, "remote_tip", lambda b, fetch=True: (c2, "tip"))
    monkeypatch.setattr(DL, "_run", lambda args, cwd=None, **k: _runner(repo)(args))
    out = tmp_path / "out"
    a = argparse.Namespace(out=str(out), extra=None, range=f"{c0}..{c2}", branch="b",
                           zip=None, no_tests=True)
    assert DL.cmd_pack(a) == 1
    assert not list(out.glob("*.patch")), "멈추기 전에 패치를 떴다"


def test_w13_22_missing_extra_cries_and_keeps_the_out_dir(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep").write_text("k", encoding="utf-8")
    monkeypatch.setattr(DL, "remote_tip", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("없는 --extra 를 보기 전에 원격으로 갔다")))
    a = argparse.Namespace(out=str(out), extra=[str(tmp_path / "없다.md")], range="a..b",
                           branch="b", zip=None, no_tests=True)
    assert DL.cmd_pack(a) == 1
    assert (out / "keep").exists(), "울기 전에 --out 을 비웠다"


def test_w13_22_extra_inside_out_is_not_eaten(tmp_path, monkeypatch):
    """`--out` 안의 파일은 `rmtree` 가 먹었다 — 옆에 떠 뒀다가 되돌린다."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "PR_BODY.md").write_text("body", encoding="utf-8")
    seen = {}

    def stop(*a, **k):
        seen["out"] = sorted(p.name for p in out.iterdir())
        raise RuntimeError("stop")
    monkeypatch.setattr(DL, "remote_tip", stop)
    a = argparse.Namespace(out=str(out), extra=[str(out / "PR_BODY.md")], range="a..b",
                           branch="b", zip=None, no_tests=True)
    try:
        DL.cmd_pack(a)
    except RuntimeError:
        pass
    assert seen["out"] == [], "rmtree 뒤 out 은 비어야 한다(되돌리는 것은 패치 뒤)"


def test_w13_21_birth_side_goes_through_uv_run_without_venv(tmp_path):
    no_venv = DL._py_cmd(tmp_path, uv="/bin/uv")
    assert no_venv[:3] == ["/bin/uv", "run", "--quiet"] and no_venv[-1] == "python"
    assert str(tmp_path) in no_venv, "환경 자리를 root 로 못 박지 않았다"
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").write_text("", encoding="utf-8")
    assert DL._py_cmd(tmp_path, uv="/bin/uv") == [str(tmp_path / ".venv/bin/python")]


def test_w13_24_pytest_summary_has_no_wall_clock_and_still_parses():
    for line in ("2291 passed, 1 warning in 457.32s (0:07:37)", "2291 passed, 1 warning in 12.0s",
                 "2 failed, 9 passed in 3.1s"):
        red, tail = DL._scan_pytest(line + "\n", 0)
        assert " in " not in tail and "s)" not in tail, tail
        assert tail.split(",")[0].split()[1] in ("passed", "failed")
        assert DL.parse(DL.render({"pytest": tail})) == {"pytest": tail}
    # 두 번 재면 같다 — 시간만 다른 두 줄이 같은 값이 된다
    assert DL._scan_pytest("5 passed in 1.0s\n", 0) == DL._scan_pytest("5 passed in 9.9s\n", 0)
    # 요약이 없으면 종전대로 rc
    assert DL._scan_pytest("", 7)[1] == "rc=7"


def test_w13_24_expectcheck_parses_expect_without_time(tmp_path):
    sys.modules.setdefault("deliver", DL)
    import expectcheck as ec  # noqa: PLC0415 — `tools` 를 sys.path 에 깐 뒤에야 import 된다
    want = DL.parse("# h\nbase.sha=\npytest=3 passed · 새 빨간불 0\nunexercised=0\n")
    assert want["pytest"].startswith("3 passed")
    assert ec.drift(want, {"closure.ingest": "x", "closure.segments": "y", "webdata": "unchanged"}) == []
    assert ec.notice(want)[0].strip().endswith("0")

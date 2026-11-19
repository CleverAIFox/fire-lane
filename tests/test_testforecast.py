"""시험 묶음의 예보와 pre-push 예산의 중앙값 판정(`tools/testforecast.py` · PLAN #264 · DECISIONS §837).

IN    tools/testforecast.py · tools/testpick.py(`pick` 의 새 시험 몫) · .githooks/pre-push
OUT   없음 (검사)
밖    **호스트가 실제로 얼마나 흔들리는가는 안 본다** — 그 수는 DECISIONS §837 이 든다. 여기는 판정 규칙이 선언대로 서는가를 본다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import testforecast as F  # `pyproject` 의 `pythonpath` 가 tools 를 얹는다
import testpick as P

ROOT = Path(__file__).resolve().parents[1]


def test_the_median_cries_but_a_single_spike_only_notes() -> None:
    lvl, msg = F.judge([22.0, 23.0, 24.0, 22.5], 37.0, 30.0, 5)
    assert lvl == "note" and "이번 회차 37.0초(중앙값 23.0초)" in msg
    lvl, msg = F.judge([31.0, 32.0, 33.0, 22.0], 34.0, 30.0, 5)
    assert lvl == "cry" and "중앙값 32.0초" in msg


def test_a_window_that_is_not_full_does_not_cry() -> None:
    lvl, msg = F.judge([40.0], 41.0, 30.0, 5)
    assert lvl == "short" and "기록 2/5" in msg and "넘었다" in msg
    assert F.judge([], 20.0, 30.0, 5)[0] == "short"


def test_a_sustained_slowdown_cries_at_the_middle_round() -> None:
    """지속되는 느려짐은 창의 절반을 넘기는 회차에 운다 — 5 회 창이면 셋째 느린 회차(DECISIONS §837 의 표)."""
    base = [23.0, 22.0, 24.0, 23.5, 22.5]
    seq, cried = list(base), None
    for k in range(1, 6):
        lvl, _ = F.judge(seq, 33.0, 30.0, 5)
        seq.append(33.0)
        if lvl == "cry" and cried is None:
            cried = k
    assert cried == 3


def test_the_record_keeps_only_green_key_matched_rounds_and_trims(tmp_path: Path) -> None:
    rec = tmp_path / "secs"
    for i in range(25):
        F.append_record(rec, 20.0 + i, "k1", keep=10)
    F.append_record(rec, 99.0, "k2", keep=10)
    assert F.read_records(rec, "k1") == [float(f"{20.0 + i:.1f}") for i in range(16, 25)]     # 최근 열 줄 중 k2 를 뺀 아홉
    assert F.read_records(rec, "k2") == [99.0]
    assert F.read_records(tmp_path / "없음", "k1") == []


def test_a_broken_record_line_is_skipped(tmp_path: Path) -> None:
    rec = tmp_path / "secs"
    rec.write_text("1\t12.0\tk\n깨진 줄\n2\t음수아님\tk\n3\t14.0\tk\n", encoding="utf-8")
    assert F.read_records(rec, "k") == [12.0, 14.0]


def test_the_budget_has_a_note_that_says_it_has_no_basis() -> None:
    assert "근거 없음" in F.BUDGET_NOTE and "§580" in F.BUDGET_NOTE and "§586" in F.BUDGET_NOTE
    hook = (ROOT / ".githooks/pre-push").read_text(encoding="utf-8")
    assert "BUDGET=30" in hook, "수는 그대로다 — 근거 없는 수를 다른 근거 없는 수로 바꾸지 않는다"
    assert "근거가 없다" in hook and "§580" in hook


def test_new_tests_are_counted_inside_the_estimate_and_they_displace_short_ones() -> None:
    files = [f"test_k{i}.py" for i in range(10)] + ["test_new_a.py", "test_new_b.py"]
    ledger = {f"test_k{i}.py": 2.0 + i for i in range(10)}
    _, with_new = P.pick(files, ledger, 14.0, 4, startup=1.0, load=0.0)
    _, without = P.pick([f for f in files if "new" not in f], ledger, 14.0, 4, startup=1.0, load=0.0)
    med = with_new["median"]
    assert with_new["new_est"] == pytest.approx(med * 2 / 4)
    assert with_new["est"] >= without["est"], "새 시험은 추정 **안**에 들어 있다"
    assert with_new["displaced"] == 1 and without["displaced"] == 0      # 짧은 순 여덟이 들던 것이 새 시험 둘(중앙값 6.5 × 2)에 밀려 일곱


def test_the_hook_line_starts_with_the_marker_the_hook_greps() -> None:
    info = {"est": 20.0, "new": ["a", "b", "c"], "new_est": 2.6, "median": 4.4, "displaced": 5}
    line = F.hook_line(info, 17.0)
    assert line.startswith("예보 ") and "새 시험 3개" in line and "2.6초" in line and "밀었다" in line and "×0.85" in line


def test_the_accuracy_line_names_numerator_and_denominator_and_the_hook_zero() -> None:
    assert F.accuracy_line(280, 281, 27.8, 28.0, True) == "읽기 정확도 280/281개 파일(실측 · 낡지 않음) · 예상 27.8초 · 예산 28초"
    assert "읽기 장부를 안 읽는다" in F.accuracy_line(280, 281, 27.8, 28.0, False)
    assert F.over_budget_warning(28.1, 28.0) and F.over_budget_warning(28.0, 28.0) is None


def test_the_forecast_table_is_monotone_and_the_truth_is_the_unfiltered_reads() -> None:
    texts = {"test_a.py": "x", "test_b.py": "x", "test_c.py": "x"}
    raw = {"test_a.py": ["f.md", "bg.md"], "test_b.py": ["bg.md"], "test_c.py": ["bg.md"]}
    ledger = {"test_a.py": 4.0, "test_b.py": 4.0, "test_c.py": 4.0}
    rows = F.forecast_table({"r": ["f.md"]}, texts, raw, ledger, P.touching, P.ambient)
    assert rows[0].startswith("| 바뀐 범위 |") and "A 정적 스캔만" in rows[0]
    cells = [c.strip() for c in rows[2].split("|")[2:-1]]
    assert cells[0].startswith("0개 · 정답 대비 0%")                                   # 정적 스캔은 `f.md` 를 아무도 안 언급해 놓친다
    assert cells[1] == cells[2] == "1개 · 정답 대비 100% · 1초"                        # 문턱 0.9 · 0.5 — `f.md` 는 시험의 1/3 만 읽어 배경이 아니다(4 ÷ 4)
    assert cells[3].startswith("0개") and cells[4].startswith("0개")                   # 0.3 · 0.1 — 1/3 은 문턱 이상이라 배경으로 빠진다(정확도가 내려간다)


def test_the_hook_judges_by_the_median_from_an_untracked_record(tmp_path: Path) -> None:
    work = tmp_path / "w"
    work.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": os.environ["PATH"],
           "HOME": str(tmp_path), "FIRE_LANE_PREPUSH_PY": sys.executable}

    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=work, env=env, capture_output=True, text=True, check=False, timeout=60)

    git("init", "-q", "-b", "part/x")
    (work / ".githooks").mkdir()
    (work / "tools").mkdir()
    shutil.copy(ROOT / ".githooks/pre-push", work / ".githooks/pre-push")
    shutil.copy(ROOT / "tools/testforecast.py", work / "tools/testforecast.py")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "c1")
    gates = work.parent / "gates.txt"
    gates.write_text("초록\ttrue\n", encoding="utf-8")
    key = subprocess.run(["git", "hash-object", "--stdin"], input=(work / ".githooks/pre-push").read_text(encoding="utf-8") + gates.read_text(encoding="utf-8"),
                         capture_output=True, text=True, check=True, cwd=work, timeout=60).stdout.strip()[:12]
    gitdir = Path(git("rev-parse", "--absolute-git-dir").stdout.strip())
    (gitdir / "fire-lane-prepush-secs").write_text("".join(f"{i}\t41.0\t{key}\n" for i in range(4)), encoding="utf-8")
    sha = git("rev-parse", "HEAD").stdout.strip()
    r = subprocess.run([".githooks/pre-push"], cwd=work, env={**env, "FIRE_LANE_PREPUSH_GATES": str(gates)}, capture_output=True, text=True, timeout=120, check=False,
                       input=f"refs/heads/part/x {sha} refs/heads/part/x {'0' * 40}\n")
    assert r.returncode == 0, r.stderr
    assert "중앙값 41.0초가 예산 30초를 넘었다" in r.stderr and "느려진 것이다" in r.stderr
    assert git("status", "--porcelain", "--untracked-files=no").stdout == "", "기록이 추적 파일이면 다음 푸시를 막는다 — 추적 안 하는 파일이어야 한다"
    assert len((gitdir / "fire-lane-prepush-secs").read_text(encoding="utf-8").splitlines()) == 5

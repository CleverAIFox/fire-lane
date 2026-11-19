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
    assert cells[1] == cells[2] == "1개 · 정답 대비 100% · 4초"                        # 문턱 0.9 · 0.5 — `f.md` 는 시험의 1/3 만 읽어 배경이 아니다(합 4 ÷ 4 = 1 이나 시험 하나가 4초라 벽시계는 4초 아래일 수 없다)
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


# ── 예보와 실측의 비(DECISIONS §838) ────────────────────────────────────────────────────────

#: 실측한 훅 축의 비, 시간 순서 — 사용자 네 회(.84 .85 .73 .79) · 이 절의 측정 여덟 회(뒤 둘 앞의 1.35 · 1.45 는 호스트 흔들림이었다). 모형 추정 27.9초 · 실측 20.5 ~ 40.3초
HOOK_AXIS_RATIOS = [0.84, 0.85, 0.73, 0.79, 0.79, 0.76, 0.78, 0.77, 1.35, 1.45, 0.83, 0.81]
#: ㉥ 축 — 같은 `--run` 으로 잰 비(추정 37.2 · 111.1 · 234.1초 대 실측 37.4 · 160.1 · 303.6초)와 DECISIONS §837 의 한 표본(×1.40)
TOUCHED_AXIS_RATIOS = [1.00, 1.44, 1.30, 1.40]


def test_one_formula_serves_both_axes_and_the_load_term_flips_the_sign() -> None:
    """같은 식이 두 축을 맡는다 — 훅 축과 ㉥ 축의 모형 추정은 **남의 일**(`load`) 항만 다르고 그 차이는 정확히 `load ÷ 실효 병렬`이다(훅 60 ÷ 5 = 12초)."""
    files = [f"test_k{i}.py" for i in range(20)]
    ledger = {f: 0.5 for f in files}
    _, hook = P.pick(files, ledger, 1e9, 6, load=60.0)
    _, touched = P.pick(files, ledger, 1e9, 6, load=0.0)
    assert hook["est"] - touched["est"] == pytest.approx(60.0 / P.EFF) == pytest.approx(12.0)
    assert F.axis_tag(60.0, False) != F.axis_tag(0.0, True) != F.axis_tag(0.0, False)
    assert "남의 일 60" in F.axis_tag(60.0, False) and "닿는 시험" in F.axis_tag(0.0, True)


def test_the_lines_name_the_axis_and_the_hook_marker_survives() -> None:
    info = {"est": 27.9, "new": [], "new_est": 0.0, "median": 0.4, "displaced": 0}
    line = F.hook_line(info, 21.8, axis=F.axis_tag(60.0, False))
    assert line.startswith("예보 ") and "[pre-push 묶음 · 남의 일 60]" in line and "모형 추정 27.9초" in line and "×0.78" in line
    assert "(모형 · pre-push 묶음 · 남의 일 60)" in F.accuracy_line(1, 1, 27.9, 28.0, False, F.axis_tag(60.0, False))


def test_the_corrected_forecast_waits_for_records_and_then_uses_the_axis_median() -> None:
    fc, msg = F.corrected([0.8, 0.8], 27.9)
    assert fc is None and "기록 2/3" in msg and "모형 추정만" in msg
    fc, msg = F.corrected(HOOK_AXIS_RATIOS[:5], 27.9)
    assert fc == pytest.approx(27.9 * 0.79) and "중앙값 ×0.79" in msg
    fc, _ = F.corrected(HOOK_AXIS_RATIOS, 27.9)                  # 열두 회 중 최근 다섯(.77 · 1.35 · 1.45 · .83 · .81) — 중앙값이 흔들림 둘을 이긴다
    assert fc == pytest.approx(27.9 * 0.83)


def test_the_measured_hook_series_never_cries_and_the_two_host_spikes_only_note() -> None:
    seq: list[float] = []
    grades = []
    for r in HOOK_AXIS_RATIOS:
        grades.append(F.ratio_verdict(seq, r)[0])
        seq.append(r)
    assert grades[:5] == ["short"] * 5 and "cry" not in grades
    assert grades[8:10] == ["note", "note"] and grades[5:8] == ["ok"] * 3 and grades[10:] == ["ok", "ok"]


def test_the_touched_axis_series_is_too_short_to_judge_and_says_so() -> None:
    """표본 넷으로는 ㉥ 축의 비를 못 가린다 — 판정이 울지도 안 울지도 않고 「센 몫 k/3」을 말한다(DECISIONS §838 의 「넷으로는 못 가린다」)."""
    seq: list[float] = []
    for r in TOUCHED_AXIS_RATIOS:
        lvl, msg = F.ratio_verdict(seq, r)
        seq.append(r)
        assert lvl == "short" and "/3" in msg


def test_a_regime_shift_cries_from_the_second_shifted_round_and_a_stable_stream_never_does() -> None:
    seq = [0.78, 0.80, 0.77, 0.79, 0.78]
    assert F.ratio_verdict(seq, 0.79)[0] == "ok"
    levels = []
    for _ in range(5):
        levels.append(F.ratio_verdict(seq, 1.3)[0])               # 모형이 바뀌어 비가 ×0.78 에서 ×1.3 으로 옮겨 갔다
        seq.append(1.3)
    assert levels == ["note", "cry", "cry", "cry", "cry"]
    lvl, msg = F.ratio_verdict([0.78, 0.8, 0.77, 0.79, 0.78], 1.3)
    assert lvl == "note" and "호스트 흔들림" in msg


def test_the_ratio_record_separates_axes_and_skips_broken_lines(tmp_path: Path) -> None:
    rec = tmp_path / "ratios"
    F.append_ratio(rec, 27.9, 21.8, "A")
    F.append_ratio(rec, 100.0, 130.0, "B")
    F.append_ratio(rec, 0.0, 5.0, "A")                               # 추정이 0 이면 비가 없다 — 쌓지 않는다
    with rec.open("a", encoding="utf-8") as fh:
        fh.write("깨진 줄\n1\t음수아님\tA\n2\t-1\tA\n")
    assert F.read_ratios(rec, "A") == [pytest.approx(21.8 / 27.9, abs=1e-3)] and F.read_ratios(rec, "B") == [1.3]
    assert F.read_ratios(tmp_path / "없음", "A") == []
    for i in range(30):
        F.append_ratio(rec, 10.0, 10.0 + i, "A", keep=8)
    assert len(rec.read_text(encoding="utf-8").splitlines()) == 8


def test_the_forecast_floor_is_the_longest_test_not_the_sum_over_par() -> None:
    """실측: 닿는 시험 다섯 개(장부 합 41.4 · 가장 긴 34.6)가 병렬 4 에서 28.4초 걸렸다 — 합 ÷ 4 = 10.3초는 ×2.74 틀렸다."""
    texts = {"test_long.py": "x", "test_a.py": "x", "test_c.py": "x"}
    raw = {"test_long.py": ["f.md"], "test_a.py": ["f.md"], "test_c.py": ["bg.md"]}          # `f.md` 는 시험의 2/3 만 읽어 배경(0.9)이 아니다
    ledger = {"test_long.py": 34.6, "test_a.py": 6.8, "test_c.py": 1.0}
    rows = F.forecast_table({"r": ["f.md"]}, texts, raw, ledger, P.touching, P.ambient, shares=(0.9,))
    assert "2개 · 정답 대비 100% · 35초" in rows[2] and "가장 긴 시험" in rows[-1]


def test_the_testpick_run_prints_the_axis_before_running(capsys: pytest.CaptureFixture[str]) -> None:
    assert P.main(["--list", "--no-touched", "--budget", "28", "--load", "60", "--jobs", "6"]) == 0
    err = capsys.readouterr().err
    assert "예상" in err and "(모형 · pre-push 묶음 · 남의 일 60)" in err and "예보 [pre-push 묶음 · 남의 일 60]" in err

"""tests/test_closecap.py — 한 커밋이 닫는 PLAN 행은 셋까지다 (DECISIONS §732 · E1).

IN    tools/closecap.py · .pre-commit-config.yaml · git 기록(5a8543ad — 없으면 건너뛴다)
OUT   없음 (검사)
밖    행이 옳게 닫혔는지는 안 본다(`planclose` 의 일) · 훅이 실제 커밋에서 도는지는 안 본다(등록만 본다)
PLAN 본문  규칙 없음 — 닫는 수를 무는 검사이고 PLAN 의 어느 행도 이 파일을 근거로 서지 않는다
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import closecap  # noqa: E402 — 경로를 넣은 뒤에 불러야 한다(tools/ 는 패키지가 아니다)


def _rows(*ns: int) -> str:
    return "".join(f"-| {n} | 행 |\n" for n in ns)


def test_closed_rows_counts_deleted_rows_and_ignores_edited_ones():
    d = _rows(1, 2, 3, 4) + "+| 9 | 고친 행 |\n-| 9 | 옛 |\n"
    assert closecap.closed_rows(d) == [1, 2, 3, 4]


def test_three_pass_and_four_without_reason_block():
    assert closecap.verdict(_rows(1, 2, 3), "")[0] == 0
    code, msg = closecap.verdict(_rows(1, 2, 3, 4), "")
    assert code == 1 and "#1" in msg and "나눠라" in msg


def test_reason_must_be_recorded_match_the_count_and_be_long_enough():
    plan = _rows(1, 2, 3, 4)
    ok = "+**한 커밋에 닫은 행 4개(상한 3) — 사유:** 같은 근거로 한 번에 닫히는 묶음이고 하나씩 읽었다\n"
    assert closecap.verdict(plan, ok)[0] == 0
    assert closecap.verdict(plan, ok.replace("4개", "5개"))[0] == 1, "수가 다른 사유가 통과했다"
    assert closecap.verdict(plan, "+**한 커밋에 닫은 행 4개(상한 3) — 사유:** 짧다\n")[0] == 1
    assert closecap.verdict(plan, ok.replace("+", " ", 1))[0] == 1, "더한 줄이 아닌 옛 줄이 사유로 통과했다"


def test_selftest_probe_is_alive():
    assert closecap.selftest() == 0


def test_the_hook_is_registered():
    cfg = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "tools/closecap.py" in cfg, "훅이 안 달렸다 — 검사기가 있어도 아무도 안 돌린다"


@pytest.mark.skipif(subprocess.run(["git", "cat-file", "-e", "5a8543ad"], cwd=ROOT, capture_output=True).returncode != 0,
                    reason="이 복제에 그 커밋이 없다(얕은 복제)")
def test_the_real_history_has_commits_that_this_gate_would_have_stopped():
    """실물 앵커 — 29행을 한 커밋에 닫은 과거가 있다(고칠 수 없다 · 앞으로를 막는다)."""
    d = subprocess.run(["git", "show", "-U0", "--format=", "5a8543ad", "--", "docs/PLAN.md"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8").stdout
    assert len(closecap.closed_rows(d)) > closecap.CAP
    assert closecap.verdict(d, "")[0] == 1

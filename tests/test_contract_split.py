"""
test_contract_split.py — `contract` 를 속도로 쪼갠 모양과 「혼자」 예외의 종료 조건.  (PLAN #192 · DECISIONS §633)

── 이 시험이 무는 것 ──────────────────────────────────────────
① 시험 조각 넷이 `tests/**/test_*.py` 를 **빠짐없이 · 겹침 없이** 나눈다 — 새 시험 파일이 어느 조각에도 안 들어가면 그 시험은 CI 에서
   **영원히 안 돈다**(조용한 구멍). 조각을 나누는 셸 줄을 워크플로에서 **그대로 꺼내** 돌려 본다 — 시험이 줄을 베끼지 않는다.
② 필수 체크의 이름 `contract-shared` 는 셋(`-fast` · `-heavy` · `-tests`)의 **집계**다 — 룰셋이 그 이름을 안다. 집계가 `always()` 가 아니면 위 셋이 빨개도 건너뛰어
   「초록도 빨강도 아닌」 필수 체크가 된다.
③ **「혼자」 예외는 둘째 사람이 들어오면 끝난다**(§633-4). CODEOWNERS 의 소유자가 둘이 되면 이 시험이 운다 — 예외를 닫고 PR 경로로 간다.

★ ①②는 **분리 전 워크플로에서는 건너뛴다**(사람이 패치를 밀기 전). 밀고 나면 자동으로 켜진다.

IN    .github/workflows/contract.yml · .github/CODEOWNERS · tests/
OUT   없음
밖    **CI 러너의 실제 속도는 안 본다**(장부 값은 로컬에서 CI 조건으로 잰 상대 시간이다 — DECISIONS §760). 시험이 서로 독립인지는 안 본다.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import testsplit as ts
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "contract.yml"


def _jobs() -> dict:
    return YAML(typ="safe").load(WF.read_text(encoding="utf-8"))["jobs"]


def _split_or_skip() -> dict:
    jobs = _jobs()
    if "contract-tests" not in jobs:
        pytest.skip("유예skip — 「필수 체크가 29분이라 사람이 우회한다 — 검사 배치를 속도로 가른다」 · 2026-11-05 — contract-shared 가 아직 쪼개지지 않았다(패치 전)")
    return jobs


def _ledger() -> dict[str, float]:
    import json
    p = ROOT / "data" / "golden" / "ci_testtimes.json"
    return {k: float(v) for k, v in json.loads(p.read_text(encoding="utf-8"))["seconds"].items()} if p.is_file() else {}


def _piece(jobs: dict, part: int) -> list[str]:
    # ★ 2026-11-13 (DECISIONS §760). 조각은 `tools/testsplit.py`(실측 시간 LPT)가 가른다 — 워크플로가 부르는 **그 줄을 그대로** 돌린다.
    step = next(s for s in jobs["contract-tests"]["steps"] if "testsplit.py" in s.get("run", ""))
    line = next(ln for ln in step["run"].splitlines() if "testsplit.py" in ln and not ln.lstrip().startswith("#"))
    assert "--part" in line and "--of 4" in line, f"워크플로가 testsplit 을 이상하게 부른다: {line}"
    return subprocess.run([sys.executable, "tools/testsplit.py", "--part", str(part), "--of", "4"], cwd=ROOT, text=True, capture_output=True,
                          check=True, timeout=60).stdout.split()


def test_the_four_pieces_cover_every_test_file_once():
    jobs = _split_or_skip()
    matrix = jobs["contract-tests"]["strategy"]["matrix"]["part"]
    assert sorted(matrix) == [1, 2, 3, 4]
    pieces = [_piece(jobs, p) for p in matrix]
    every = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").rglob("test_*.py"))
    flat = [f for pc in pieces for f in pc]
    assert sorted(flat) == every, "조각의 합이 `tests/**/test_*.py` 와 다르다 — 빠진 파일은 CI 에서 안 돈다"
    assert len(set(flat)) == len(flat), "같은 파일이 두 조각에 들어갔다"
    # ★ 파일 수가 아니라 **실측 시간**이 균형이다(§760): 장부(`ci_testtimes.json`)로 센 조각 합의 최대/최소가 2 배 안이어야 한다.
    sec = _ledger()
    if sec:
        med = sorted(sec.values())[len(sec) // 2]
        sums = [sum(sec.get(Path(f).name, med) for f in pc) for pc in pieces]
        assert max(sums) <= 2 * min(sums), f"조각의 예상 시간이 2 배 넘게 어긋난다: {[round(x) for x in sums]}"


def test_the_required_name_aggregates_both_halves_even_when_they_fail():
    jobs = _split_or_skip()
    agg = jobs["contract-shared"]
    assert set(agg["needs"]) == {"contract-fast", "contract-heavy", "contract-tests", "contract-smoke"}
    assert "always()" in str(agg["if"]), "집계가 always() 가 아니면 위 셋이 빨개도 필수 체크가 건너뜀으로 남는다"
    run = "\n".join(s.get("run", "") for s in agg["steps"])
    assert "success" in run and "exit 1" in run


def test_the_solo_exception_ends_when_a_second_person_appears():
    """§633-4. 소유자가 둘이 되는 날 이 시험이 운다 — 「선언된 예외」가 낡은 채 남지 않게 한다."""
    owners = set(re.findall(r"@[\w-]+(?:/[\w-]+)?", "\n".join(
        ln for ln in (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#"))))
    assert len(owners) == 1, (
        f"CODEOWNERS 의 소유자가 {sorted(owners)} 로 둘 이상이다 — `part/**` 직접 푸시 예외(DECISIONS §633-4)의 종료 조건이다. "
        "예외 절을 닫고 PR 경로로 간다(룰셋은 이미 서 있다).")


def test_the_workflow_pieces_pass_the_same_judge_the_tool_uses():
    """워크플로가 부르는 줄이 낸 조각을 `testsplit.defects` 로 민다 — 깨끗하면 비고 합성 결함이면 운다."""
    jobs = _split_or_skip()
    pieces = [_piece(jobs, p) for p in jobs["contract-tests"]["strategy"]["matrix"]["part"]]
    files, sec = ts.test_files(), ts.load_seconds()
    assert not ts.defects(files, pieces, sec)
    assert ts.defects(files, [pieces[0][1:], *pieces[1:]], sec)

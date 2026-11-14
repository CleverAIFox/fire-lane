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


# ── 같은 나무를 두 번 재지 않는다 (판계획 ㉕ · CI 중복 · 2026-11-14) ───────────────────────────────────────────────────
# 워크플로의 「이 나무가 이미 초록이었나」 단계를 **그대로 꺼내** 가짜 `git` · `gh` 로 돌린다 — 시험이 줄을 베끼지 않는다.
def _seen_step() -> str:
    step = next(s for s in _split_or_skip()["contract-tests"]["steps"] if s.get("name", "").startswith("★ 이 나무가 이미 초록이었나"))
    return step["run"]


def _run_seen(tmp_path, *, event="push", tree="T_NEW", green_ref=False, ok_shas=(), deploy_shas=(), trees=None, gh_dies=False) -> str:
    """단계를 돌리고 `GITHUB_ENV` 의 **마지막** FL_GREEN 값을 돌려준다(뒤 줄이 앞 줄을 덮는다)."""
    import os
    bin_ = tmp_path / "bin"
    bin_.mkdir(parents=True)
    (bin_ / "git").write_text('#!/bin/bash\nif [ "$1" = rev-parse ]; then echo "$FAKE_TREE"; exit 0; fi\nif [ "$1" = ls-remote ]; then [ "$FAKE_GREEN_REF" = 1 ]; exit $?; fi\nexit 1\n', encoding="utf-8")
    (bin_ / "gh").write_text(
        '#!/bin/bash\n[ "$FAKE_GH_DIES" = 1 ] && exit 1\n'
        'case "$*" in\n'
        '  *workflows/contract.yml*) printf "%s\\n" $FAKE_CONTRACT ;;\n'
        '  *workflows/deploy.yml*) printf "%s\\n" $FAKE_DEPLOY ;;\n'
        '  *git/commits/*) sha="${2##*/}"; sha="${sha%%\\?*}"; v="FAKE_TREE_$sha"; echo "${!v}" ;;\n'
        'esac\n', encoding="utf-8")
    for f in ("git", "gh"):
        (bin_ / f).chmod(0o755)
    env_file = tmp_path / "envout"
    env_file.write_text("", encoding="utf-8")
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_ENV": str(env_file), "REPO": "o/r", "EVENT": event, "GH_TOKEN": "x",
           "FAKE_TREE": tree, "FAKE_GREEN_REF": "1" if green_ref else "0", "FAKE_CONTRACT": " ".join(ok_shas), "FAKE_DEPLOY": " ".join(deploy_shas),
           "FAKE_GH_DIES": "1" if gh_dies else "0", **{f"FAKE_TREE_{k}": v for k, v in (trees or {}).items()}}
    subprocess.run(["bash", "-eo", "pipefail", "-c", _seen_step()], env=env, check=True, capture_output=True, text=True, timeout=30)
    return [ln for ln in env_file.read_text(encoding="utf-8").splitlines() if ln.startswith("FL_GREEN=")][-1]


def test_a_new_tree_runs_every_test_and_only_a_green_push_of_the_same_tree_skips_them(tmp_path):
    """(a) 트리가 새것이면 안 건너뛴다 (b) 같은 트리의 **성공한 푸시 실행**이 있을 때만 건너뛴다 — 계약 · 배포(main 게이트) 양쪽에서 찾는다."""
    # 성공 푸시가 있지만 다른 트리
    assert _run_seen(tmp_path / "a", ok_shas=["s1", "s2"], trees={"s1": "T_OLD", "s2": "T_OLD2"}) == "FL_GREEN=0"
    # 성공한 푸시 목록이 비었다(= 같은 트리여도 실패 · 진행 중 · 취소 실행은 목록에 안 든다)
    assert _run_seen(tmp_path / "b", ok_shas=[], trees={"s1": "T_NEW"}) == "FL_GREEN=0"
    # 같은 트리(다른 커밋 — 스쿼시) 의 성공 푸시
    assert _run_seen(tmp_path / "c", ok_shas=["s1", "s2"], trees={"s1": "T_OLD", "s2": "T_NEW"}) == "FL_GREEN=1"
    # main 게이트(배포 실행)가 쟀던 나무도 증거다
    assert _run_seen(tmp_path / "d", ok_shas=["s1"], deploy_shas=["s9"], trees={"s1": "T_OLD", "s9": "T_NEW"}) == "FL_GREEN=1"
    # 열차가 적은 refs/green 은 그대로 산다
    assert _run_seen(tmp_path / "e", green_ref=True) == "FL_GREEN=1"


def test_the_drift_run_and_a_manual_rerun_never_skip_and_a_dead_api_means_run(tmp_path):
    """시간이 만드는 드리프트(`schedule`)와 사람이 누른 재실행(`workflow_dispatch`)은 증거가 있어도 돈다. API 가 죽으면 **모르니까 돈다**."""
    hit = {"ok_shas": ["s1"], "trees": {"s1": "T_NEW"}}
    assert _run_seen(tmp_path / "a", event="schedule", **hit) == "FL_GREEN=0"
    assert _run_seen(tmp_path / "b", event="workflow_dispatch", **hit) == "FL_GREEN=0"
    assert _run_seen(tmp_path / "c", event="pull_request", **hit) == "FL_GREEN=1"      # PR(합성 커밋의 나무)이 앞선 푸시와 같으면 건너뛴다
    assert _run_seen(tmp_path / "d", gh_dies=True, **hit) == "FL_GREEN=0"


def test_only_the_full_test_step_is_ever_skipped_and_the_gate_still_demands_every_job():
    """(c) 빼는 것은 `전체 테스트` 하나뿐이다. 다른 잡의 어떤 단계도 FL_GREEN 을 안 읽는다 — 나무 밖 입력(PR 본문 · 이력 · 시각)을 읽는 단계가 그 안에 있다.
    main 게이트: 배포가 push 전건에서 `gate` 를 무조건 부르고 · strict 는 main 에서 건너뛰어지지 않고 · 집계는 다섯 잡 전부 success 를 요구하며 · `deploy` 는 gate 를 기다린다."""
    jobs = _split_or_skip()
    readers = [(j, s.get("name")) for j, job in jobs.items() for s in job.get("steps", []) if "FL_GREEN" in str(s.get("if", ""))]
    assert readers == [("contract-tests", next(s["name"] for s in jobs["contract-tests"]["steps"] if "FL_GREEN" in str(s.get("if", ""))))], readers
    full = next(s for s in jobs["contract-tests"]["steps"] if "FL_GREEN" in str(s.get("if", "")))
    assert "pytest" in full["run"] and "schedule" in full["if"], "건너뛰는 단계는 전체 테스트 하나이고 schedule 은 예외다"
    for name in ("contract-fast", "contract-heavy", "contract-smoke", "contract-strict"):
        assert "FL_GREEN" not in str(jobs[name].get("if", "")) and "contract-seen" not in str(jobs[name].get("needs", "")), name
    assert "github.ref == 'refs/heads/main'" in jobs["contract-strict"]["if"], "main 에서 strict 가 건너뛰어지면 안 된다"
    run = "\n".join(s.get("run", "") for s in jobs["contract-shared"]["steps"])
    assert all("!= success" in run and k in run for k in ("FAST", "HEAVY", "TESTS", "SMOKE"))
    dep = YAML(typ="safe").load((ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8"))
    assert dep["jobs"]["gate"]["uses"] == "./.github/workflows/contract.yml" and dep["jobs"]["gate"]["if"].replace(" ", "") == "${{github.event_name!='pull_request'}}"
    assert dep["jobs"]["deploy"]["needs"] == "gate"
    assert "main" in dep["on"]["push"]["branches"] and "paths" not in dep["on"]["push"], "main 푸시 전건에서 gate 가 돌아야 한다(contract.yml 의 push 에서 main 을 뺀 전제)"


def test_the_lookup_is_read_only_in_both_workflows():
    """`actions: read` 가 호출자 · 피호출자 양쪽에 있고 쓰기가 아니다 — 배포 권한은 넓어지지 않는다(§196-4)."""
    for name in ("contract.yml", "deploy.yml"):
        perms = YAML(typ="safe").load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))["permissions"]
        assert perms.get("actions") == "read", name
        assert "write" not in {v for k, v in perms.items() if k not in ("pull-requests", "pages", "id-token")}, name


def test_the_seal_check_is_skipped_only_on_a_bot_pr():
    """W13-23. 「문서 정합 도장」은 **PR 이면서 작성자가 `Bot` 일 때만** 건너뛴다 — 사람 PR · 푸시 · 스케줄 · 호출(workflow_call)에서는 돈다.
    조건식을 워크플로에서 **그대로 꺼내** 같은 의미의 파이썬 식으로 번역해 모든 경우를 돌린다."""
    step = next(s for s in _jobs()["contract-fast"]["steps"] if s.get("name") == "문서 정합 도장")
    cond = step["if"].strip()
    assert cond == "github.event_name != 'pull_request' || github.event.pull_request.user.type != 'Bot'", cond

    def runs(event: str, user_type: str | None) -> bool:
        return event != "pull_request" or user_type != "Bot"
    assert runs("pull_request", "User") and not runs("pull_request", "Bot")
    assert all(runs(e, None) for e in ("push", "schedule", "workflow_dispatch", "workflow_call"))
    assert "docseal.py check" in step["run"]

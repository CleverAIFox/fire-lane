#!/usr/bin/env python3
"""
test_run_basis.py — **산출물이 적는 재현 기반.** (§495)

── 왜 생겼나 ───────────────────────────────────────────────────
`datalog.git_state` 는 산출물마다 「어느 커밋에서 · 깨끗한 나무에서 나왔나」를
적는다. §372 가 거기서 **「확인했다」와 「확인할 수 없었다」가 같은 값이 되는**
결함을 고쳤다 — `dirty: bool(dirty)` 였고 git 이 못 답하면 `None` →
`bool(None)` → **`False`**, 즉 「깨끗하다」로 기록됐다. 그러면
「`git_dirty` 인 산출물은 재현 불가」 규율이 그 기계에서 조용히 무력해진다.

그 수선을 미는 자리가 없었다 — `tools/srccov.py` 가 셌다(§493).
`quiet_gdal.suppressed` 도 같은 족이다: 머리말이 「예상 밖으로 늘면 새 문제가
섞인 것이다」라고 적는데, 그 집계를 읽는 쪽에서 **고칠 수 있으면** 그 판정에
뜻이 없다.

★ `tests/test_reproducibility.py` 에 두지 않았다 — 그 파일은 700줄 상한에
  닿아 있었고(703 으로 넘겼다) `MASTER §18-5` 의 R1·R4·R5 를 드는 집이다.
  **회색을 NULL 로 적는가**는 그 셋과 다른 축이다.

IN    없음 (`gitq` 를 갈아끼운다)
OUT   없음 (검사)
PARAM 없음
밖    **R1 · R4 · R5 는 안 본다** — `tests/test_reproducibility.py` 가 든다.
"""
from __future__ import annotations


# ── 재현 기반 · 억제 집계 — 이름을 안 부르고 있었다 (§495) ────
# ★ `datalog.git_state` 는 **산출물의 재현 기반**을 적는 자다. §372 가 거기서
#   「확인했다」와 「확인할 수 없었다」가 같은 값이 되는 결함을 고쳤는데
#   (`bool(None)` → `False`), 그 수선을 미는 자리가 없었다 — `tools/srccov.py`
#   가 셌다(§493). 이 파일이 재현성 규약의 집이라 여기 둔다.
def test_git_state_records_unknown_dirtiness_as_null_not_clean(monkeypatch):
    """★ **회색은 NULL 이다**(§455 · §372). `False` 로 적으면 「깨끗하다」가 된다.

    그러면 「`git_dirty` 인 산출물은 재현 불가」 규율이 그 기계에서
    **조용히 무력해진다** — 못 물어본 것이 확인된 것으로 기록되기 때문이다.
    """
    from firelane import datalog, gitq

    monkeypatch.setattr(gitq, "dirty", lambda _root: None)
    monkeypatch.setattr(gitq, "head", lambda _root: None)
    got = datalog.git_state()
    assert got["dirty"] is None, f"{got['dirty']!r} — 모르는 것을 단정했다"
    assert got["dirty_files"] == []


def test_git_state_records_a_dirty_tree_as_true_with_a_bounded_list(monkeypatch):
    """더러우면 `True` 이고 파일 목록은 **열 건까지**다 — 기록이 산문이 되지 않게."""
    from firelane import datalog, gitq

    files = [f"a/{i}.py" for i in range(25)]
    monkeypatch.setattr(gitq, "dirty", lambda _root: files)
    monkeypatch.setattr(gitq, "head", lambda _root: "abc1234")
    got = datalog.git_state()
    assert got["dirty"] is True and got["sha"] == "abc1234"
    assert got["dirty_files"] == files[:10]


def test_git_state_records_a_clean_tree_as_false(monkeypatch):
    """★ 음성 — 깨끗하면 `False` 다. `None` 과 갈려야 한다."""
    from firelane import datalog, gitq

    monkeypatch.setattr(gitq, "dirty", lambda _root: [])
    monkeypatch.setattr(gitq, "head", lambda _root: "abc1234")
    got = datalog.git_state()
    assert got["dirty"] is False and got["dirty_files"] == []


def test_the_suppressed_counter_hands_out_a_copy():
    """★ `quiet_gdal.suppressed()` 는 **사본**을 준다.

    머리말이 「예상 밖으로 늘면 새 문제가 섞인 것이다」라고 적는다 —
    그 판정이 집계를 읽는 쪽에서 **고쳐질 수 있으면** 아무 뜻이 없다.
    """
    from firelane import quiet_gdal

    before = quiet_gdal.suppressed()
    assert isinstance(before, dict) and before, "집계 칸이 비었다"
    got = quiet_gdal.suppressed()
    got[next(iter(got))] = 10**6
    got["없는칸"] = 1
    after = quiet_gdal.suppressed()
    assert after == before, f"밖에서 고친 것이 안으로 들어갔다 — {after}"


# ── git 에게 묻고, **못 물었으면 None** (§499) ────────────────
# ★ `gitq.ignored` 도 같은 규율을 진다 — 위 `git_state` 와 한 축이다.
#   `tools/treecheck.py` 가 그것으로 「저장소에 있어야 할 것이 없다」와
#   「무시 규칙이라 없는 것이 맞다」를 가른다. 빈 집합을 내면 그 둘이
#   섞이고, 그러면 D 축이 §457-1 처럼 죽는다.
def test_ignored_asks_git_with_no_index_so_tracked_files_are_seen():
    """★ `--no-index` 가 있어야 **추적 중인 파일**도 보고된다(git 사양).

    무시 규칙인데 추적 중인 상태가 바로 찾으려는 것이라, 빼면 영원히 0건이다.
    """
    import inspect

    from firelane import gitq

    src = inspect.getsource(gitq.ignored)
    assert "--no-index" in src, "추적 중인 파일이 영원히 안 보고된다"


def test_ignored_reports_what_the_repo_actually_ignores():
    """★ 실물로 민다 — `__pycache__` 는 무시되고 `README.md` 는 아니다."""
    from pathlib import Path

    from firelane import gitq

    root = Path(__file__).resolve().parents[1]
    got = gitq.ignored(["tests/__pycache__/x.pyc", "README.md"], root)
    assert got is not None, "git 에 못 물었다 — 이 기계에 저장소가 없다"
    assert "tests/__pycache__/x.pyc" in got
    assert "README.md" not in got


def test_ignored_treats_no_match_as_an_answer_not_a_failure():
    """★ `check-ignore` 는 **일치가 없으면 rc=1** 이다 — 실패가 아니다.

    `ask` 로 감싸면 그 1 이 실패로 읽혀 `None`(못 물었음)이 되고, 그러면
    「무시되는 것이 없다」가 「모른다」로 바뀐다.
    """
    from pathlib import Path

    from firelane import gitq

    root = Path(__file__).resolve().parents[1]
    assert gitq.ignored(["README.md"], root) == frozenset()


def test_ignored_on_an_empty_list_answers_without_asking():
    """빈 목록은 빈 집합이다 — `None` 이 아니다(물을 것이 없는 것은 모름이 아니다)."""
    from firelane import gitq

    assert gitq.ignored([]) == frozenset()


def test_ignored_returns_none_when_git_cannot_be_asked(monkeypatch):
    """★ 못 물었으면 **None** — 빈 집합과 갈려야 한다(회색=NULL)."""
    import subprocess

    from firelane import gitq

    def boom(*_a, **_k):
        raise OSError("git 이 없다")

    monkeypatch.setattr(subprocess, "run", boom)
    assert gitq.ignored(["a.txt"]) is None

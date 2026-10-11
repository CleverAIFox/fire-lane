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

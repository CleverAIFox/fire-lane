"""tools/testpick.py — 푸시 전에 도는 시험 묶음을 **실측 장부에서 계산**한다. (PLAN #209)

★ 손 목록이 아니라 계산이다 — 그래서 시험이 지키는 것은 **계산의 성질**이다: 예산 안인가 · 새 시험은 무조건 드는가 ·
  장부가 비면 닫힌 쪽으로 실패하는가 · 실물 장부에서 구조 규약 시험이 실제로 드는가.

밖    실제로 시험을 돌리지 않는다(`run_file` 은 부르지 않는다) — 고르는 계산과 장부의 모양만 본다.
"""
from __future__ import annotations

import json

import testpick as T  # `pyproject` 의 `pythonpath` 가 tools 를 얹는다

LEDGER = {"a.py": 1.0, "b.py": 2.0, "c.py": 4.0, "d.py": 100.0}
FILES = ["a.py", "b.py", "c.py", "d.py"]


def test_cheapest_first_until_the_budget_and_the_long_one_is_out():
    chosen, info = T.pick(FILES, LEDGER, budget=2.0, jobs=2, startup=0)      # 합 ÷ 2 ≤ 2 → 합 4 까지
    assert chosen == ["a.py", "b.py"] and info["skipped"] == ["c.py", "d.py"]
    assert info["est"] <= 2.0


def test_a_single_file_longer_than_the_budget_never_enters_however_many_jobs():
    chosen, _ = T.pick(FILES, LEDGER, budget=50.0, jobs=64, startup=0)
    assert "d.py" not in chosen and {"a.py", "b.py", "c.py"} <= set(chosen)


def test_a_new_test_always_enters_and_is_priced_at_the_median():
    chosen, info = T.pick([*FILES, "new.py"], LEDGER, budget=0.5, jobs=1, startup=0)
    assert "new.py" in chosen and info["new"] == ["new.py"]
    assert info["median"] == 3.0                    # a b c d 의 중앙값 (2 · 4)


def test_the_choice_grows_with_the_ledger_without_anyone_listing_files():
    more = {**LEDGER, **{f"s{i}.py": 0.5 for i in range(10)}}
    c1, _ = T.pick(FILES, LEDGER, 5.0, 1, 0)
    c2, _ = T.pick([*FILES, *[f"s{i}.py" for i in range(10)]], more, 5.0, 1, 0)
    assert len(c2) > len(c1) or all(f"s{i}.py" in c2 for i in range(10))


def test_the_choice_is_deterministic():
    assert T.pick(FILES, LEDGER, 10.0, 2, 0) == T.pick(list(reversed(FILES)), LEDGER, 10.0, 2, 0)


def test_files_gone_from_the_tree_are_reported_not_run():
    chosen, info = T.pick(["a.py"], {**LEDGER, "gone.py": 1.0}, 10.0, 1, 0)
    assert chosen == ["a.py"] and info["gone"] == ["b.py", "c.py", "d.py", "gone.py"]


def test_an_empty_ledger_fails_closed_instead_of_running_everything(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(T, "LEDGER", tmp_path / "none.json")
    assert T.main(["--list"]) == 1
    assert "장부" in capsys.readouterr().err


def test_a_broken_ledger_reads_as_empty(tmp_path):
    p = tmp_path / "l.json"
    p.write_text("{not json", encoding="utf-8")
    assert T.load_ledger(p) == {}


def test_bins_balance_by_the_ledger_and_keep_every_file_once():
    b = T.bins(FILES, 2, LEDGER)
    assert sorted(f for g in b for f in g) == FILES and ["d.py"] in b


def test_the_real_ledger_picks_the_structure_rules_within_budget():
    """도착 조건 — 구조 규약을 무는 시험이 **실측으로** 묶음에 들고, 그 묶음이 예산 안이다."""
    ledger = T.load_ledger()
    assert ledger, "장부가 비었다 — `tools/testpick.py --measure --write`"
    files = T.test_files()
    chosen, info = T.pick(files, ledger, T.DEFAULT_BUDGET, jobs=8)
    for must in ("test_layering.py", "test_no_unbounded_waits.py", "test_sizecheck.py"):
        assert must in chosen, f"{must} 가 묶음 밖이다 — 장부 {ledger.get(must)}초 · 예산 {T.DEFAULT_BUDGET}초"
    assert info["est"] <= T.DEFAULT_BUDGET + 1e-9


def test_the_ledger_file_is_one_json_with_seconds():
    d = json.loads(T.LEDGER.read_text(encoding="utf-8"))
    assert set(d["seconds"].values()) and all(isinstance(v, (int, float)) for v in d["seconds"].values())

"""tools/testpick.py — 푸시 전에 도는 시험 묶음을 **실측 장부에서 계산**한다. (PLAN #209)

★ 손 목록이 아니라 계산이다 — 그래서 시험이 지키는 것은 **계산의 성질**이다: 예산 안인가 · 새 시험은 무조건 드는가 ·
  장부가 비면 닫힌 쪽으로 실패하는가 · 실물 장부에서 구조 규약 시험이 실제로 드는가.

PLAN 본문  규칙 없음 — PLAN.md 를 읽어 규칙을 세우지 않는다. 「바뀐 파일에 닿는 시험」 스캔의 입력으로 파일 이름 문자열만 쓴다
밖    실제로 시험을 돌리지 않는다(`run_file` 은 부르지 않는다) — 고르는 계산과 장부의 모양만 본다.
"""
from __future__ import annotations

import json
import os
import subprocess

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


def test_other_gates_load_shrinks_the_choice_and_zero_load_is_the_standalone_model():
    more = {f"s{i}.py": 2.0 for i in range(40)}
    fs = list(more)
    alone, a = T.pick(fs, more, 20.0, 8, startup=0, load=0)
    inside, b = T.pick(fs, more, 20.0, 8, startup=0, load=60)
    assert len(inside) < len(alone) and b["est"] <= 20.0 and a["est"] <= 20.0


def test_the_hook_line_declares_the_condition_the_budget_is_measured_under():
    """예산 30초는 **훅 전체 벽시계 · 게이트 동시**의 30초다(PLAN #210 ㉡) — 줄이 `--load` 로 그 조건을 적고 있는가."""
    gate = next(ln for ln in (T.ROOT / ".githooks" / "pre-push.gates").read_text(encoding="utf-8").splitlines()
                if "testpick.py" in ln and not ln.lstrip().startswith("#"))
    assert "--load" in gate and "--budget" in gate
    assert float(gate.split("--budget")[1].split()[0]) < 30


def test_measuring_only_some_files_overwrites_just_those_ledger_cells(tmp_path, monkeypatch):
    """`--only` — 고친 시험 하나를 11분 안 들이고 갱신한다. 나머지 칸은 그대로여야 한다."""
    led = tmp_path / "t.json"
    led.write_text(json.dumps({"seconds": {"test_a.py": 9.0, "test_b.py": 7.0, "test_gone.py": 1.0}}), encoding="utf-8")
    monkeypatch.setattr(T, "LEDGER", led)
    monkeypatch.setattr(T, "test_files", lambda root=T.ROOT: ["test_a.py", "test_b.py"])
    monkeypatch.setattr(T, "run_all", lambda names, jobs, ledger, root=T.ROOT, measuring=False: ({"test_a.py": 0.5}, {}))
    assert T.main(["--measure", "--write", "--only", "test_a.py"]) == 0
    assert json.loads(led.read_text(encoding="utf-8"))["seconds"] == {"test_a.py": 0.5, "test_b.py": 7.0}


def test_a_red_file_blocks_writing_the_ledger(tmp_path, monkeypatch):
    """★ 빨간 파일이 있으면 장부를 안 쓴다 — 흔들린 판의 초가 추정을 오염시키지 않는다. 끝나면 장부는 그대로다."""
    led = tmp_path / "t.json"
    before = json.dumps({"seconds": {"test_a.py": 9.0}})
    led.write_text(before, encoding="utf-8")
    monkeypatch.setattr(T, "LEDGER", led)
    monkeypatch.setattr(T, "test_files", lambda root=T.ROOT: ["test_a.py"])
    monkeypatch.setattr(T, "run_all", lambda names, jobs, ledger, root=T.ROOT, measuring=False: ({"test_a.py": 0.5}, {"test_a.py": "boom"}))
    assert T.main(["--measure", "--write"]) == 1
    assert led.read_text(encoding="utf-8") == before


def test_the_hook_runs_the_bundle_with_six_workers_and_loses_no_file():
    """PLAN #214 — 워커를 8 → 6 으로 줄인 것이 훅이 도는 **파일을 줄이지 않는다**(`eff = min(jobs, EFF)`).

    훅 줄이 `--jobs 6` 을 적고 있고, 같은 조건(예산 · 남의 일)에서 6 · 8 이 같은 묶음을 고른다."""
    gates = (T.ROOT / ".githooks" / "pre-push.gates").read_text(encoding="utf-8")
    line = next(ln for ln in gates.splitlines() if "tools/testpick.py --run" in ln and not ln.startswith("#"))
    args = line.split("\t")[1].split()
    assert args[args.index("--jobs") + 1] == "6", "훅 줄의 워커가 6 이 아니다 — 실측(DECISIONS §679)을 거스른다"
    budget, load = float(args[args.index("--budget") + 1]), float(args[args.index("--load") + 1])
    files, ledger = T.test_files(), T.load_ledger()
    six, _ = T.pick(files, ledger, budget, 6, load=load)
    eight, _ = T.pick(files, ledger, budget, 8, load=load)
    assert six == eight, "워커 6 과 8 이 다른 묶음을 고른다 — 6 은 검증 범위를 잃는다"


# ── PLAN #218 — 바뀐 파일에 닿는 시험은 예산과 무관하게 든다 ──────────────────────────────

TEXTS = {
    "test_a.py": 'p = ROOT / "docs" / "PLAN.md"',                 # 파일명으로 읽는다
    "test_b.py": 'open("tools/foo.py")',                            # 경로 전체
    "test_c.py": "from foo import bar",                             # 모듈 import
    "test_d.py": "x = 1",                                           # 아무것도 안 읽는다
    "test_e.py": "# docs/PLAN.mdx 는 다른 파일이다",                # 접미가 다르다 — 닿지 않는다
}


def test_a_changed_file_picks_the_tests_that_name_it_by_path_basename_or_import():
    got = T.touching(["docs/PLAN.md", "tools/foo.py"], TEXTS)
    assert got == {"test_a.py": ["docs/PLAN.md"], "test_b.py": ["tools/foo.py"], "test_c.py": ["tools/foo.py"]}


def test_a_test_that_names_nothing_changed_is_not_touched_and_a_changed_test_touches_itself():
    assert T.touching(["docs/MASTER.md"], TEXTS) == {}
    assert T.touching(["tests/test_d.py"], TEXTS) == {"test_d.py": ["tests/test_d.py"]}


def test_the_scan_is_a_lower_bound_a_path_built_by_a_helper_is_not_counted():
    """★ 하한이라는 것 — 파일명이 본문에 글자 그대로 없으면 못 센다. 머리말이 그렇게 적고 있고 시험이 그것을 붙든다."""
    assert T.touching(["docs/PLAN.md"], {"test_h.py": "p = doc_path('plan')"}) == {}
    assert "하한" in (T.__doc__ or "")


def test_touched_tests_over_the_cap_are_named_not_dropped_and_unknown_ones_enter():
    touch = {"short.py": ["x"], "long.py": ["x"], "new.py": ["x"]}
    go, over = T.pick_touched(touch, {"short.py": 3.0, "long.py": 304.0}, cap=40.0)
    assert go == ["new.py", "short.py"] and over == {"long.py": 304.0}


def test_the_long_tests_touching_docs_and_ledger_are_over_the_cap_on_the_real_ledger():
    """실물 장부 — 긴 다섯은 상한에 걸려 **이름이 난다**(조용히 안 빠진다). 상한이 45초짜리도 가른다.

    ★ 2026-11-12 (DECISIONS §707). 여섯이었다 — `test_fix_door.py`(335초)는 문을 갈라(`fix.sh --skip`) 6.5초가 돼 **상한 아래로 내려왔다.** 빠진 것은 좋은 일이고
      그 시험은 이제 푸시 전 묶음에 **든다**(아래 시험이 그것을 문다). 상한을 올려서 넣은 것이 아니다."""
    led = T.load_ledger()
    five = ["test_ledger_accessor.py", "test_normalize_rules.py", "test_ledger_outputs.py", "test_guards.py", "test_tools_are_wired.py"]
    _, over = T.pick_touched({n: ["x"] for n in five}, led)
    assert sorted(over) == sorted(five)
    go, none = T.pick_touched({"test_fix_door.py": ["x"]}, led)
    assert go == ["test_fix_door.py"] and not none, "문 시험이 아직 상한 위다 — 갈랐는데도 길다"


def test_the_real_tree_a_changed_doc_pulls_in_a_test_outside_the_budget_pick(capsys):
    """도착 조건 — 예산이 고른 묶음에 안 드는데 바뀐 파일을 읽는 시험이 실제로 **더해진다**(예전에는 안 돌았다)."""
    files, led = T.test_files(), T.load_ledger()
    base, _ = T.pick(files, led, T.DEFAULT_BUDGET, 6, load=60.0)
    texts = {n: (T.ROOT / "tests" / n).read_text(encoding="utf-8", errors="replace") for n in files}
    go, over = T.pick_touched(T.touching(["docs/MASTER.md", "docs/PLAN.md", "docs/DECISIONS.md", "sources.yaml"], texts), led)
    assert set(go) - set(base), "문서를 읽는 시험이 전부 이미 묶음에 있다 — 규칙이 아무것도 안 더한다"
    assert all(led.get(n, 0) <= T.TOUCH_CAP for n in go)


def test_the_files_flag_adds_touched_tests_and_the_no_touched_flag_removes_them(capsys):
    assert T.main(["--list", "--files", "docs/MASTER.md"]) == 0
    with_t = set(capsys.readouterr().out.split())
    assert T.main(["--list", "--no-touched"]) == 0
    without = set(capsys.readouterr().out.split())
    assert without < with_t


def test_changed_files_reads_the_range_and_falls_back_when_it_cannot(tmp_path):
    import subprocess as sp

    def g(*a):
        return sp.run(["git", *a], cwd=tmp_path, capture_output=True, text=True, check=True, timeout=60,
                      env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}).stdout.strip()
    g("init", "-q")
    (tmp_path / "a.txt").write_text("1", encoding="utf-8")
    g("add", "."); g("commit", "-qm", "1")
    base = g("rev-parse", "HEAD")
    (tmp_path / "b.txt").write_text("2", encoding="utf-8")
    g("add", "."); g("commit", "-qm", "2")
    (tmp_path / "a.txt").write_text("changed", encoding="utf-8")
    got, _ = T.changed_files(tmp_path, [f"{base}..HEAD"])
    assert got == ["a.txt", "b.txt"]                 # 범위(b) ∪ 작업 트리(a)
    got, notes = T.changed_files(tmp_path, ["deadbeef..HEAD"])
    assert got == ["a.txt"] and any("못 읽" in n for n in notes)       # 범위를 못 읽으면 말한다 · 작업 트리는 본다


def test_the_hook_turns_the_touched_link_off_and_pushready_takes_all_of_it():
    """b — 훅은 30초를 지키므로 연동을 끄고(`--no-touched`), `pushready` ㉥ 는 상한 없이 전부 든다(`--no-cap`). 같은 `select` 를 부른다(#216)."""
    gate = next(ln for ln in (T.ROOT / ".githooks" / "pre-push.gates").read_text(encoding="utf-8").splitlines()
                if "testpick.py" in ln and not ln.lstrip().startswith("#"))
    assert "--no-touched" in gate
    pr = (T.ROOT / "tools" / "pushready.py").read_text(encoding="utf-8")
    assert '"tools/testpick.py", "--run", "--no-cap"' in pr


def test_one_selector_serves_both_callers_and_only_the_arguments_differ():
    files, led = T.test_files(), T.load_ledger()
    texts = {n: (T.ROOT / "tests" / n).read_text(encoding="utf-8", errors="replace") for n in files}
    ch = ["docs/MASTER.md", "sources.yaml"]
    hook, _ = T.select(files, led, texts, ch, 28.0, 6, load=60.0, touched=False)
    base, _ = T.pick(files, led, 28.0, 6, load=60.0)
    ready, info = T.select(files, led, texts, ch, 28.0, 8, touched=True, cap=None)
    assert hook == base                                         # 훅 = 종전 묶음
    assert set(base) < set(ready) and not info["over"]          # pushready ⊃ 훅 · 상한에 걸려 빠진 것이 없다
    assert {"test_fix_door.py", "test_ledger_accessor.py"} <= set(ready)


def test_only_the_measuring_path_lengthens_the_per_test_timeout(monkeypatch):
    """★ 재는 길만 시험당 시한이 길다(머리의 ★ — 재는 것이지 시험이 아니다). `--run` 쪽은 pyproject 의 300초 그대로다 — 느슨하게 한 것이 아니다."""
    seen: list[list[str]] = []

    class R:
        returncode, stdout, stderr = 0, "", ""

    def fake_run(cmd, **kw):
        seen.append(cmd)
        seen.append(kw["timeout"])
        return R()

    monkeypatch.setattr(T.subprocess, "run", fake_run)
    T.run_bin(["test_a.py"], measuring=True)
    T.run_bin(["test_a.py"])
    m_cmd, m_lim, r_cmd, r_lim = seen
    assert f"timeout={T.MEASURE_TEST_TIMEOUT}" in m_cmd and m_lim == T.MEASURE_PROC_TIMEOUT
    assert not any(str(x).startswith("timeout=") for x in r_cmd) and r_lim == T.PROC_TIMEOUT
    assert T.MEASURE_TEST_TIMEOUT > 300, "재는 길이 평소와 같으면 이 장치가 없는 것과 같다"


def test_measure_asks_run_all_for_the_measuring_path(tmp_path, monkeypatch):
    got = {}
    monkeypatch.setattr(T, "LEDGER", tmp_path / "t.json")
    monkeypatch.setattr(T, "test_files", lambda root=T.ROOT: ["test_a.py"])
    monkeypatch.setattr(T, "run_all", lambda names, jobs, ledger, root=T.ROOT, measuring=False: (got.setdefault("m", measuring) and ({"test_a.py": 0.5}, {})) or ({"test_a.py": 0.5}, {}))
    T.main(["--measure"])
    assert got["m"] is True


# ── #218 ② 읽기 실측이 정적 스캔의 하한을 메운다 ────────────────────────────────────────

def test_a_measured_read_touches_a_test_whose_path_the_static_scan_cannot_see():
    texts = {"test_h.py": "p = doc_path('plan')", "test_o.py": "x = 1"}
    assert T.touching(["docs/PLAN.md"], texts) == {}
    got = T.touching(["docs/PLAN.md"], texts, {"test_h.py": ["docs/PLAN.md"]})
    assert got == {"test_h.py": ["docs/PLAN.md"]}, "실측으로 읽은 시험이 안 닿는다 — 정적 스캔의 하한이 안 메워졌다"


def test_a_measured_read_of_another_test_file_does_not_touch():
    texts = {"test_a.py": "x = 1"}
    assert T.touching(["tests/test_b.py"], texts, {"test_a.py": ["tests/test_b.py"]}) == {}


def test_files_nearly_every_test_reads_are_ambient_and_dropped(tmp_path):
    reads = {f"test_{i}.py": ["src/infra.py", f"docs/d{i}.md"] for i in range(10)}
    assert T.ambient(reads) == ["src/infra.py"]
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"reads": reads}), encoding="utf-8")
    assert "src/infra.py" not in T.load_reads(f)["test_0.py"] and "src/infra.py" in T.load_reads(f, drop_ambient=False)["test_0.py"]


def test_a_missing_or_broken_reads_ledger_reads_as_empty_so_only_the_static_scan_remains(tmp_path):
    assert T.load_reads(tmp_path / "none.json") == {}
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert T.load_reads(tmp_path / "bad.json") == {}


def test_the_real_reads_ledger_names_only_real_test_files_and_sorted_reads():
    d = json.loads(T.READS_LEDGER.read_text(encoding="utf-8"))["reads"]
    assert set(d) <= set(T.test_files()), f"없어진 시험이 읽기 장부에 남았다: {sorted(set(d) - set(T.test_files()))[:3]}"
    assert d and all(v == sorted(v) for v in d.values())


def test_measure_reads_runs_one_process_per_file_and_writes_the_ledger(monkeypatch, tmp_path):
    calls: list[str] = []
    monkeypatch.setattr(T, "test_files", lambda root=T.ROOT: ["test_a.py", "test_b.py"])
    monkeypatch.setattr(T, "run_reads", lambda n, *a, **k: (calls.append(n) or (0, "", ["docs/x.md"])))
    monkeypatch.setattr(T, "READS_LEDGER", tmp_path / "r.json")
    monkeypatch.setattr(T, "test_hash", lambda n, root=T.ROOT: "h")
    assert T.main(["--measure-reads", "--write", "--jobs", "2"]) == 0
    assert sorted(calls) == ["test_a.py", "test_b.py"]
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["reads"] == {"test_a.py": ["docs/x.md"], "test_b.py": ["docs/x.md"]}


def test_a_red_file_blocks_writing_the_reads_ledger(monkeypatch, tmp_path):
    monkeypatch.setattr(T, "test_files", lambda root=T.ROOT: ["test_a.py"])
    monkeypatch.setattr(T, "run_reads", lambda n, *a, **k: (1, "빨강", []))
    monkeypatch.setattr(T, "READS_LEDGER", tmp_path / "r.json")
    assert T.main(["--measure-reads", "--write"]) == 1
    assert not (tmp_path / "r.json").exists()


# ── #218 ⑥ 읽기 장부의 낡음을 도구가 말한다 · 배경 목록은 장부 파일이 든다 ──────────────────

def _tests_dir(tmp_path, names):
    (tmp_path / "tests").mkdir(exist_ok=True)
    for n, body in names.items():
        (tmp_path / "tests" / n).write_text(body, encoding="utf-8")
    return tmp_path


def test_a_new_test_and_a_changed_test_and_a_gone_test_are_each_named_as_stale(tmp_path):
    root = _tests_dir(tmp_path, {"test_a.py": "1", "test_b.py": "2", "test_c.py": "3"})
    led = tmp_path / "r.json"
    led.write_text(json.dumps({"reads": {"test_a.py": [], "test_b.py": [], "test_old.py": []},
                               "hashes": {"test_a.py": T.test_hash("test_a.py", root), "test_b.py": "0000"}}), encoding="utf-8")
    new, changed, gone = T.reads_stale(["test_a.py", "test_b.py", "test_c.py"], led, root)
    assert (new, changed, gone) == (["test_c.py"], ["test_b.py"], ["test_old.py"])


def test_an_old_cell_without_a_hash_counts_as_stale_not_fresh(tmp_path):
    root = _tests_dir(tmp_path, {"test_a.py": "1"})
    led = tmp_path / "r.json"
    led.write_text(json.dumps({"reads": {"test_a.py": []}}), encoding="utf-8")
    assert T.reads_stale(["test_a.py"], led, root)[1] == ["test_a.py"]


def test_the_stale_reads_ledger_says_what_it_fell_back_to_and_never_falls_back_silently(tmp_path, capsys, monkeypatch):
    _tests_dir(tmp_path, {"test_new.py": "x", "test_ch.py": "y"})
    monkeypatch.setattr(T, "ROOT", tmp_path)
    led = tmp_path / "r.json"
    led.write_text(json.dumps({"reads": {"test_ch.py": ["docs/a.md"]}, "hashes": {"test_ch.py": "0000"}, "ambient": []}), encoding="utf-8")
    monkeypatch.setattr(T, "READS_LEDGER", led)
    monkeypatch.setattr(T, "test_files", lambda root_=T.ROOT: ["test_new.py", "test_ch.py"])
    monkeypatch.setattr(T, "test_hash", lambda n, root_=T.ROOT: "ffff")
    monkeypatch.setattr(T, "load_ledger", lambda path=None: {"test_new.py": 1.0, "test_ch.py": 1.0})
    T.main(["--list", "--files", "docs/a.md"])
    err = capsys.readouterr().err
    assert "읽기 장부가 낡았다" in err and "새 시험 1" in err and "바뀐 시험 1" in err
    assert "정적 스캔만" in err and "옛 실측 ∪ 정적 스캔" in err and "--measure-reads --write --only" in err


def test_the_ambient_list_lives_in_the_ledger_file_and_matches_the_measured_reads():
    """배경 목록은 코드가 아니라 **장부 파일**이 든다 — 그리고 그 목록이 실측과 어긋나면(시험이 늘어 배경이 바뀌었다) 운다."""
    d = json.loads(T.READS_LEDGER.read_text(encoding="utf-8"))
    assert d.get("ambient"), "장부 파일에 배경 목록이 없다 — `--measure-reads --write` 가 적는다"
    assert d["ambient"] == T.ambient(d["reads"]), "장부의 배경 목록이 실측과 다르다 — 다시 잰다"
    tracked = set(subprocess.run(["git", "ls-files"], cwd=T.ROOT, capture_output=True, text=True, check=True, timeout=30).stdout.split("\n"))
    assert set(d["ambient"]) <= tracked, f"추적에 없는 배경 파일: {sorted(set(d['ambient']) - tracked)}"


def test_load_reads_drops_exactly_the_ambient_the_file_lists(tmp_path):
    led = tmp_path / "r.json"
    led.write_text(json.dumps({"ambient": ["a.py"], "reads": {"test_x.py": ["a.py", "b.py"], "test_y.py": ["a.py"]}}), encoding="utf-8")
    assert T.load_reads(led) == {"test_x.py": ["b.py"], "test_y.py": []}
    assert T.load_reads(led, drop_ambient=False)["test_y.py"] == ["a.py"]


def test_measure_reads_only_overwrites_the_measured_cells_and_their_hashes(monkeypatch, tmp_path):
    led = tmp_path / "r.json"
    led.write_text(json.dumps({"ambient": [], "hashes": {"test_a.py": "old", "test_b.py": "keep"}, "reads": {"test_a.py": ["x"], "test_b.py": ["y"]}}), encoding="utf-8")
    monkeypatch.setattr(T, "READS_LEDGER", led)
    monkeypatch.setattr(T, "test_files", lambda root=T.ROOT: ["test_a.py", "test_b.py"])
    monkeypatch.setattr(T, "run_reads", lambda n, *a, **k: (0, "", ["z"]))
    monkeypatch.setattr(T, "test_hash", lambda n, root=T.ROOT: "new")
    assert T.main(["--measure-reads", "--write", "--only", "test_a.py"]) == 0
    d = json.loads(led.read_text(encoding="utf-8"))
    assert d["reads"] == {"test_a.py": ["z"], "test_b.py": ["y"]} and d["hashes"] == {"test_a.py": "new", "test_b.py": "keep"}


def test_no_ledger_file_reaches_the_per_test_timeout():
    """★ 장부(8병렬 경합 기준 · 파일 합계) 어느 칸도 시험당 시한(pyproject 300초)에 닿지 않는다. (DECISIONS §712 · ⓲B-③)

    파일 합계가 300 미만이면 그 안의 어느 시험도 같은 부하에서 300을 못 넘는다 — 거꾸로 합계가 300 이상이면 **시한을 넘는 시험이 있을 수 있다.**
    `test_ratchet` 가 장부 331초이면서 시험 하나가 전부(약 100초 × 병렬 5배)였고 시한에서 죽었다. 칸이 300 에 닿으면 시한을 늘리지 말고 **시험을 쪼개거나 줄인다.**
    """
    from pathlib import Path
    sec = json.loads((Path(__file__).resolve().parents[1] / "data" / "golden" / "testtimes.json").read_text(encoding="utf-8"))["seconds"]
    over = {k: v for k, v in sec.items() if v >= 300}
    assert not over, f"장부 칸이 시험당 시한 300초에 닿았다 — 시한을 올리지 말고 시험을 줄여라: {over}"

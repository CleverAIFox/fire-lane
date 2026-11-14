"""tools/pushready.py — 「푸시해도 되는가」 한 명령. 다섯 축을 **하나씩 망가뜨려** 각각 걸리는지 본다. (PLAN #207)

★ 양성 대조다. 초록 하나(`_green`)에서 시작해 ㉠~㉤ 를 하나씩만 깨고, **그 축만** 걸리는지 본다.
  ㉣ 는 합성이 아니라 **실제 git 저장소**로 한다 — 도장 파일만 고치고 커밋을 안 한 꼴(2026-11-08 에 두 번 물렸다).

밖    **실제 `ratchet.py` · `docseal.py` · `mutate.py` 를 안 돈다** — 합성 출력으로 「그 출력을 어떻게 읽는가」만 본다(실물은 2분이다).
      그 도구들이 옳게 우는가는 각자의 시험이 든다. 여기서는 **각 축이 막는가**와 **닫힌 쪽으로 실패하는가**만 본다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import pushready as P  # `pyproject` 의 `pythonpath` 가 tools 를 얹는다 — sys.path 를 손대지 않는다

GREEN = {
    "ratchet": (0, "래칫 83개 · 낡음 0 (조이는 쪽 0 · 느슨해진 쪽 0)\n✓ 래칫이 전부 실측과 같다\n"),
    "mutate": (0, ""),
    "invalid": (0, ""),
    "unsealed": (0, "DECLARED 0\n"),
    "git": (0, ""),
    "tests": (0, "✓ 시험 묶음 198개 파일 · 빨강 0 · 25.0초\n"),
    "upstream": (0, "origin/part/infra\n"),
    "behind": (0, "3\t0\n"),
    "mirror": (0, "✓\n"),
    "obligations": (0, "새 파일이 없다 — 추적 안 된 것도 스테이징한 새 것도 없다\n"),
}


def _runner(**over):
    """argv 를 보고 합성 출력을 낸다. `over` 로 한 축만 갈아 끼운다."""
    table = {**GREEN, **over}

    def run(argv: list[str], cwd: Path) -> tuple[int, str]:
        s = " ".join(argv)
        if argv[0] in ("env", "bash"):               # ㉨ — 훅 게이트(`bash -c`)와 CI 빠른 잡 명령(레이크 없이 `env … bash -c`)
            return table["mirror"]
        if "rev-list" in s:
            return table["behind"]
        if "rev-parse" in s:
            return table["upstream"]
        if "obligations.py" in s:
            return table["obligations"]
        if "testpick.py" in s:
            return table["tests"]
        if "ratchet.py" in s:
            return table["ratchet"]
        if "import mutate" in s:
            return table["mutate"]
        if "--invalid-list" in s:
            return table["invalid"]
        if "import docseal" in s:
            return table["unsealed"]
        if argv[0] == "git":
            return table["git"]
        raise AssertionError(f"모르는 명령 {argv}")
    return run


def _keys(**over):
    return [b.key for b in P.survey(ROOT, _runner(**over))]


def test_all_green_is_pushable_and_exit_zero():
    assert P.survey(ROOT, _runner()) == []
    assert "푸시 가능" in P.render([])


def test_ratchet_loose_and_tight_are_caught_with_the_right_command():
    loose = (1, "래칫 83개 · 낡음 1 (조이는 쪽 0 · 느슨해진 쪽 1)\n"
                "\n  ✗ suppress.py · SUPPRESS — **느슨해지는 쪽**이다  선언 55 → 실측 56 (down)\n")
    b = P.survey(ROOT, _runner(ratchet=loose))
    assert [x.key for x in b] == ["㉠"] and "손으로" in " ".join(b[0].cmds) and "ratchet.py --write" not in " ".join(b[0].cmds)
    tight = (1, "래칫 83개 · 낡음 1 (조이는 쪽 1 · 느슨해진 쪽 0)\n  · planwork.py · PLAN_HISTORY  393 → 392  (--write 로 고친다)\n")
    b = P.survey(ROOT, _runner(ratchet=tight))
    assert [x.key for x in b] == ["㉠"] and any("ratchet.py --write" in c for c in b[0].cmds)


def test_ratchet_failing_with_unreadable_output_fails_closed():
    assert _keys(ratchet=(1, "Traceback ...\nboom\n")) == ["㉠"]


def test_ratchet_items_owned_by_other_axes_are_not_double_counted():
    only_seal = (1, "래칫 83개 · 낡음 1\n  ✗ docseal.py · UNSEALED — **느슨해지는 쪽**이다  선언 0 → 실측 1 (down)\n"
                    "  ✗ mutate.py · — — `ratchet_values()` 가 죽었다\n")
    assert _keys(ratchet=only_seal) == []      # ㉢ · ㉤ 이 맡는다 — 그 둘이 초록이면 여기서 막지 않는다


def test_invalid_seals_are_caught():
    b = P.survey(ROOT, _runner(invalid=(0, "DECISIONS/190-5\nPLAN/10-5\n")))
    assert [x.key for x in b] == ["㉡"] and "2절" in b[0].what and any("stamp" in c for c in b[0].cmds)


def test_unsealed_above_the_declared_count_is_caught():
    b = P.survey(ROOT, _runner(unsealed=(0, "DECLARED 0\nUNSEALED DECISIONS/661\n")))
    assert [x.key for x in b] == ["㉢"] and "DECISIONS/661" in " ".join(b[0].detail)
    # 선언과 같으면 통과한다(선언이 1 이면 1 은 허용)
    assert _keys(unsealed=(0, "DECLARED 1\nUNSEALED DECISIONS/661\n")) == []


def test_stale_mutation_ledger_is_caught():
    b = P.survey(ROOT, _runner(mutate=(1, "RuntimeError: 2개가 잰 뒤로 바뀌었다 — sizecheck, srccov.")))
    assert [x.key for x in b] == ["㉤"] and any("mutate.py --write --stale" in c for c in b[0].cmds)


def _git(cwd: Path, *a: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd, check=True, capture_output=True, timeout=60)


def test_a_stamp_without_a_commit_is_caught_in_a_real_repo(tmp_path: Path):
    """★★ 도장만 찍고 커밋 안 한 상태. 나머지 네 축은 초록이어도 ㉣ 가 막는다."""
    _git(tmp_path, "init", "-q")
    seal = tmp_path / P.SEAL_FILE
    seal.parent.mkdir(parents=True)
    seal.write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    assert P.check_dirty(tmp_path, P.real_run) is None            # 깨끗하면 통과
    (tmp_path / "new_untracked.txt").write_text("x", encoding="utf-8")
    assert P.check_dirty(tmp_path, P.real_run) is None            # 추적 안 된 새 파일은 막지 않는다
    seal.write_text('{"stamped": 1}\n', encoding="utf-8")         # 도장만 찍고 커밋 안 함
    b = P.check_dirty(tmp_path, P.real_run)
    assert b is not None and b.key == "㉣"
    assert "test_fix_door" in " ".join(b.detail) and "git commit" in b.cmds
    _git(tmp_path, "add", "-A")                                   # 스테이징만 해도 아직 커밋이 아니다
    assert P.check_dirty(tmp_path, P.real_run) is not None
    _git(tmp_path, "commit", "-q", "-m", "stamp")
    assert P.check_dirty(tmp_path, P.real_run) is None            # 커밋하면 풀린다


def test_every_blocker_prints_a_command_and_exit_code_follows(capsys, monkeypatch):
    blocks = P.survey(ROOT, _runner(invalid=(0, "A/1\n"), git=(0, " M data/golden/docseal.json\n"),
                                    mutate=(1, "x")))
    assert [b.key for b in blocks] == ["㉤", "㉡", "㉣"]       # 사슬 순서 — 변이 장부 → 도장 → 커밋
    text = P.render(blocks)
    assert text.count("사람이 칠 명령") == 3 and "푸시 불가" in text
    monkeypatch.setattr(P, "survey", lambda *a, **k: blocks)
    assert P.main([]) == 1
    monkeypatch.setattr(P, "survey", lambda *a, **k: [])
    assert P.main([]) == 0
    assert P.main(["--write"]) == 2          # 쓰기 옵션은 없다 — 읽기 전용


def test_a_red_test_bundle_blocks_first_in_the_chain():
    b = P.survey(ROOT, _runner(tests=(1, "  ✗ test_layering.py\n      E   sys.path 조작\n✗ 시험 묶음 198개 파일 · 빨강 1\n")))
    assert [x.key for x in b] == ["㉥"] and "testpick.py --run" in " ".join(b[0].cmds)
    assert [k for k, _ in P.CHECKS][:2] == ["㉧", "㉥"]    # 받기 다음 · 고치면 도장이 낡으므로 시험이 그 뒤 맨 앞이다


def test_a_missing_registration_blocks_and_names_what_is_missing():
    out = "✗ 빠진 의무 — 파일 1개\n\n  tools/x.py\n      · 머리말 「밖」  (tools/scopedecl.py 가 운다)\n"
    b = P.survey(ROOT, _runner(obligations=(1, out)))
    assert [x.key for x in b] == ["㉦"] and any("머리말 「밖」" in d for d in b[0].detail)
    assert [k for k, _ in P.CHECKS][1:3] == ["㉥", "㉦"]    # 시험 다음 · 래칫 앞 — 등재를 적으면 도장이 낡으므로


# ── ㉧ 로컬이 원격 추적 가지보다 뒤인가 (PLAN #211) ─────────────────
def _commit(cwd: Path, name: str) -> None:
    (cwd / name).write_text(name, encoding="utf-8")
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-q", "-m", name)


def _two_clones(tmp_path: Path) -> tuple[Path, Path]:
    """원격(bare) 하나와 그 클론 둘 — 한쪽이 푸시하고 다른 쪽이 fetch 만 하면 **로컬이 뒤**다(2026-11-08 의 꼴)."""
    remote, a, b = tmp_path / "r.git", tmp_path / "a", tmp_path / "b"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True, capture_output=True, timeout=60)
    _git(tmp_path, "clone", "-q", str(remote), "a")
    _commit(a, "x1")
    _git(a, "push", "-q", "origin", "HEAD:main")
    _git(tmp_path, "clone", "-q", str(remote), "b")
    return a, b


def test_a_local_behind_its_upstream_is_blocked_and_names_the_receiving_command(tmp_path: Path):
    """★★ 양성 대조 — 합성 저장소로 로컬이 뒤인 꼴을 만든다. 막고, **받을 명령**을 대고, 한계를 적는다."""
    a, b = _two_clones(tmp_path)
    assert P.check_behind(b, P.real_run) is None                        # 같으면 통과
    _commit(b, "local1")
    assert P.check_behind(b, P.real_run) is None                        # 앞서기만 하면 막지 않는다
    _commit(a, "x2")
    _git(a, "push", "-q", "origin", "HEAD:main")
    _git(b, "fetch", "-q")                                              # 원격 추적 가지만 앞으로 간다 — 로컬은 안 받았다
    blk = P.check_behind(b, P.real_run)
    assert blk is not None and blk.key == "㉧" and "1 커밋 뒤" in blk.what and "앞 1" in blk.what
    assert blk.cmds[0].startswith("git merge origin/main")
    assert "git fetch" in " ".join(blk.detail) and "못 본다" in " ".join(blk.detail)
    _git(b, "merge", "-q", "--no-edit", "origin/main")
    assert P.check_behind(b, P.real_run) is None                        # 받으면 풀린다


def test_a_branch_without_upstream_is_not_blocked_only_noted(tmp_path: Path):
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "x")
    assert P.check_behind(tmp_path, P.real_run) is None
    assert "업스트림이 없는 가지" in " ".join(P.notes(tmp_path, P.real_run))


def test_behind_check_reads_only_and_fails_closed_on_unreadable_output():
    seen: list[list[str]] = []

    def run(argv, cwd):
        seen.append(argv)
        return (0, "origin/x\n") if "rev-parse" in argv else (0, "garbage")
    blk = P.check_behind(ROOT, run)
    assert blk is not None and blk.key == "㉧"                          # 못 읽으면 닫힌 쪽
    assert not any(a[1] in ("fetch", "pull", "merge", "push") for a in seen)     # 네트워크 · 쓰기 명령을 안 부른다


def test_behind_blocks_first_in_survey_and_green_output_states_the_limit():
    b = P.survey(ROOT, _runner(behind=(0, "2\t5\n")))
    assert [x.key for x in b] == ["㉧"] and "5 커밋 뒤" in b[0].what
    assert "마지막 `git fetch` 이후" in P.render([], [])


# ── #220 몇 바퀴 남았나 — 되먹임 변으로 바퀴 수를 말한다(읽기 전용 · 모델) ──────────────────

def _blk(key: str, cmds: list[str] | None = None) -> P.Block:
    return P.Block(key, "x", [], cmds or [])


WRITE = "uv run python tools/ratchet.py --write   # 조이는 쪽만 쓴다"


def test_only_a_stale_stamp_is_one_lap_and_moves_nothing_back():
    f = P.forecast([_blk("㉡")])
    assert (f.sure, f.most, f.capped) == (1, 1, False)


def test_an_unsealed_stamp_is_first_in_the_order_so_it_is_one_lap_and_still_says_why():
    """2026-11-14 — ㉢ 이 래칫 **앞**이다. 도장을 먼저 찍어 `UNSEALED` 를 조이면 그 뒤의 래칫이
    같은 바퀴에서 조여진 상수를 쓴다. 종전 순서(㉠ ㉤ ㉡ ㉢)에서는 확정 2바퀴였다(사람이 그 순서로
    쳐서 2 → 1 로 줄었음이 실증됐다)."""
    f = P.forecast([_blk("㉢")])
    assert f.sure == 1, "㉢ 이 래칫 앞인데 확정 바퀴가 1 이 아니다"
    assert any("UNSEALED" in x for x in f.lines), "㉢→㉠ 변의 사유(UNSEALED)를 안 말한다"


def test_the_whole_chain_in_the_declared_order_is_one_sure_lap():
    f = P.forecast([_blk("㉢"), _blk("㉠", [WRITE]), _blk("㉤"), _blk("㉡")])
    assert f.sure == 1 and f.capped and f.most == P.LAP_CAP


def test_the_old_order_would_cost_two_laps_so_the_new_order_is_load_bearing(monkeypatch):
    """순서를 되돌리면 확정 바퀴가 늘어야 한다 — 순서가 장식이 아니라는 증거."""
    monkeypatch.setattr(P, "ORDER", ["㉠", "㉤", "㉡", "㉢"])
    assert P.forecast([_blk("㉢")]).sure == 2


def test_the_order_the_human_walks_is_the_order_the_report_lists_and_the_forecast_uses():
    chain = [k for k, _ in P.CHECKS if k in P.ORDER]
    assert chain == P.ORDER, "목록 순서(사람이 칠 순서)와 forecast 의 ORDER 가 갈렸다"
    assert P.ORDER == ["㉢", "㉠", "㉤", "㉡"]


def test_ratchet_then_ledger_then_stamp_is_one_sure_lap_but_can_come_back_without_a_fixed_point_claim():
    f = P.forecast([_blk("㉠", [WRITE]), _blk("㉤"), _blk("㉡")])
    assert f.sure == 1 and f.capped and f.most == P.LAP_CAP
    text = "\n".join(f.lines)
    assert "래칫이 `data/golden/mutation.json` 을 읽는다" in text and "제 래칫 상수를 맨 끝에 적는다" in text
    assert "고정점은 증명 안 됨" in text and "5바퀴" in text


def test_a_loosened_ratchet_that_only_a_human_fixes_writes_no_constant_so_it_pulls_nothing_forward():
    f = P.forecast([_blk("㉠", ["# 느슨해진 쪽은 손으로"])])
    assert (f.sure, f.most) == (1, 1)


def test_nothing_blocking_in_the_chain_is_zero_laps():
    assert P.forecast([_blk("㉣")]).sure == 0 and P.forecast([]).sure == 0


def test_every_edge_connects_chain_steps_and_names_its_evidence():
    for a, b, sure, why in P.EDGES:
        assert a in P.ORDER and b in P.ORDER and isinstance(sure, bool)
        assert "실측" in why or "서술" in why, f"{a}→{b} 에 근거(실측 · 서술)가 없다"


def test_the_forecast_is_pure_and_the_rendered_report_carries_it_without_running_anything(capsys):
    out = P.render([_blk("㉠", [WRITE]), _blk("㉡")])
    assert "몇 바퀴 남았나" in out and "치지 않는다" in out
    assert "몇 바퀴" not in P.render([]), "막는 것이 없으면 바퀴 절은 안 낸다 — 초록 출력은 그대로다"


# ── #216 ㉨ 미러 — 훅 게이트 전부 + CI 빠른 잡 중 훅 예산에 못 든 것을 글자 그대로 돈다 ──────────────────

def _all_commands(run_log):
    def run(argv, cwd):
        if argv[0] in ("env", "bash"):
            run_log.append(argv)
            return 0, ""
        return _runner()(argv, cwd)
    return run


def test_the_mirror_runs_every_hook_gate_and_every_ready_command_exactly_as_declared():
    import gate_parity as GP
    import gatefast as GF
    seen: list[list[str]] = []
    assert P.check_ci_mirror(ROOT, _all_commands(seen)) is None
    ran = {a[-1] for a in seen}
    hook = {c for _n, c in GP.gate_commands() if not (GP.keys(c) and GP.keys(c)[0] in P.HOOK_REPLACED)}
    ready = {c for _k, c in GF.ready_commands()}          # 단계 스크립트 전문 — 한 단계가 열쇠 여럿을 들면 한 번만 돈다
    assert ran == hook | ready and len(ready) > 30 and len(hook) >= 20, "㉨ 가 도는 것이 선언(훅 파일 · CI)과 다르다 — 사본이 생겼다"
    assert all(a[:3] == ["env", "FIRE_LANE_DATA=", "FIRE_LANE_RAW="] for a in seen if a[0] == "env"), "ready 는 레이크 없이 돈다 — CI 빠른 잡과 같은 조건"
    assert all(a[:2] == ["bash", "-c"] for a in seen if a[0] == "bash"), "훅 게이트는 훅이 도는 꼴(`bash -c`)이다"


def test_pushready_is_no_weaker_than_the_hook_every_hook_gate_runs_or_is_replaced_with_a_reason():
    """#216 의 본체 — 먼저 보는 도구가 나중 도구보다 약하면 거짓 안심을 준다. 훅 게이트는 전부 돌거나 **사유와 함께** 더 센 축으로 대체된다."""
    import gate_parity as GP
    hook_keys = {GP.keys(c)[0] for _n, c in GP.gate_commands() if GP.keys(c)}
    jobs, skipped = P.mirror_commands()
    assert set(skipped) == set(P.HOOK_REPLACED) and set(P.HOOK_REPLACED) <= hook_keys, "대체 표에 훅에 없는 열쇠가 남았다(죽은 대체)"
    assert all(len(why) >= 5 for why in P.HOOK_REPLACED.values())
    assert sum(1 for j in jobs if j[0] == "훅") + len(skipped) == len(GP.gate_commands()), "훅 게이트가 돌지도 대체되지도 않고 샜다"


def test_a_red_mirror_check_blocks_names_the_check_and_prints_its_own_command():
    import gatefast as GF
    (key, args), cmd = GF.ready_commands()[0]
    key = GF.fmt_id((key, args))

    def run(argv, cwd):
        if argv[0] == "env" and argv[-1] == cmd:
            return 1, "검사가 빨갛다 — 이유 하나\n"
        return _runner()(argv, cwd) if argv[0] not in ("bash",) else (0, "")

    b = P.check_ci_mirror(ROOT, run)
    assert b is not None and b.key == "㉨" and any(key in d for d in b.detail) and cmd in b.cmds


def test_a_red_hook_gate_in_the_mirror_is_named_with_its_layer():
    import gate_parity as GP
    name, cmd = next((n, c) for n, c in GP.gate_commands() if "deadcheck" in c)

    def run(argv, cwd):
        if argv[0] == "bash" and argv[-1] == cmd:
            return 1, "deadcheck 가 빨갛다\n"
        return (0, "") if argv[0] in ("bash", "env") else _runner()(argv, cwd)

    b = P.check_ci_mirror(ROOT, run)
    assert b is not None and any(d.startswith("[훅] " + name) for d in b.detail)


def test_the_mirror_blocks_when_the_layer_table_drifts_from_ci(monkeypatch):
    import gatefast as GF
    monkeypatch.setattr(GF, "LAYERS", {**GF.LAYERS, ("tools/없는검사.py", ""): ("ready", "사유가 있다 — 없는 검사")})
    b = P.check_ci_mirror(ROOT, _all_commands([]))
    assert b is not None and any("죽은 선언" in d and "없는검사" in d for d in b.detail)


def test_the_survey_includes_the_mirror_after_obligations_and_before_the_ratchet():
    keys = [k for k, _ in P.CHECKS]
    assert keys.index("㉦") < keys.index("㉨") < keys.index("㉠")


def test_an_axis_layer_names_a_pushready_axis_that_really_exists_and_the_strict_checks_are_in_the_mirror():
    import gatefast as GF
    axes = {k for k, _ in P.CHECKS}
    for k, (layer, why) in GF.LAYERS.items():
        if layer == "axis":
            assert why.split()[0] in axes, f"{GF.fmt_id(k)} 가 가리키는 축 {why.split()[0]!r} 이 pushready 에 없다"
    scripts = " ".join(j[2][-1] for j in P.mirror_commands()[0])
    for want in ("tools/docnum_check.py", "tools/unusedcheck.py", "tools/owned_paths.py", "--config .ruff-strict.toml"):
        assert want in scripts, f"엄격 잡의 검사 {want} 가 ㉨ 에 안 든다"


# ── 병렬(PLAN ㉕ B-③) — 칸을 한꺼번에 띄워도 같은 것을 같은 순서로 잡는가 ──────────────────
_DEFECTS = {                                   # 합성 결함 — 칸마다 하나씩 심는다
    "㉥": dict(tests=(1, "✗ 시험 묶음 1개 · 빨강 1\n")),
    "㉦": dict(obligations=(1, "새 파일 x.py 가 등재 안 됐다\n")),
    "㉠": dict(ratchet=(1, "  ✗ ratchet.py · NAME · 느슨\n래칫 1개 · 낡음 1\n")),
    "㉤": dict(mutate=(1, "RuntimeError: 1개가 잰 뒤로 바뀌었다 — sizecheck.")),
    "㉡": dict(invalid=(0, "DECISIONS/1\n")),
    "㉣": dict(git=(0, " M x.py\n")),
    "㉧": dict(behind=(0, "2\t5\n")),
}


def test_parallel_survey_catches_every_planted_defect_alone_and_all_together_in_chain_order():
    for key, over in _DEFECTS.items():
        assert key in [b.key for b in P.survey(ROOT, _runner(**over))], f"{key}: 병렬에서 안 잡혔다"
    every = {k: v for over in _DEFECTS.values() for k, v in over.items()}
    got = [b.key for b in P.survey(ROOT, _runner(**every))]
    assert got == [k for k, _ in P.CHECKS if k in got] and len(got) == len(_DEFECTS)


def test_parallel_and_serial_survey_give_the_same_blocks():
    every = {k: v for over in _DEFECTS.values() for k, v in over.items()}
    a = [(b.key, b.what, b.detail, b.cmds) for b in P.survey(ROOT, _runner(**every), parallel=True)]
    b = [(b.key, b.what, b.detail, b.cmds) for b in P.survey(ROOT, _runner(**every), parallel=False)]
    assert a == b


def test_a_check_that_raises_in_parallel_kills_the_survey_not_turns_green():
    def run(argv, cwd):
        if "testpick.py" in " ".join(argv):
            raise RuntimeError("죽은 칸")
        return _runner()(argv, cwd)
    try:
        P.survey(ROOT, run)
    except RuntimeError as e:
        assert "죽은 칸" in str(e)
    else:
        raise AssertionError("죽은 칸이 초록으로 읽혔다")


def test_the_branch_sync_is_named_as_a_human_step_and_no_workflow_moves_branches():
    """PLAN #221 — 「브로드캐스트」라는 이름이 **사람이 치는** 단계를 자동 과정처럼 말했다(두 번 헛되이 기다렸다).

    ① `.github/workflows` 에 가지를 옮기는 명령(`git push` · `git merge` · `gh pr merge` · `update-branch`)이 **실행 줄로** 한 곳도 없다
       (`::error::`/`echo` 안내문과 `merge-base` 는 실행이 아니다) — 이 사실이 깨지면(자동화가 생기면) 아래 ② 의 문장이 거짓이 된다.
    ② 코드 · 시험 · 워크플로(문서 `docs/` 는 주인이 따로 고친다)에서 낱말 「브로드캐스트」가 나오면 **같은 줄 ±2줄 안**에 사람 손임을 말하는 낱말(`사람이` · `merge_batch`)이 있다.
    밖  `docs/DECISIONS.md` 2곳 · `docs/MASTER.md` 1곳은 이 시험이 안 본다 — 문서 정리가 끝나면 `DOCS` 에 넣는다.
    """
    import re

    mover = re.compile(r"git push|git merge(?!-base)|gh pr merge|update-branch")

    def runs_a_mover(line: str) -> bool:
        t = line.strip()
        return bool(mover.search(t)) and not t.startswith("#") and "::error::" not in t and not t.startswith("echo")

    assert runs_a_mover("        run: git push origin HEAD") and not runs_a_mover('echo "::error::x — git merge origin/main"')   # 합성 결함
    wf = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    hits = [f"{f.name}:{i}" for f in wf for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if runs_a_mover(ln)]
    assert not hits, f"워크플로가 가지를 옮긴다 — 「사람이 친다」는 서술이 거짓이 됐다: {hits}"

    def unmarked(lines: list[str]) -> list[int]:
        return [i + 1 for i, ln in enumerate(lines) if "브로드캐스트" in ln
                and not any(k in " ".join(lines[max(0, i - 2): i + 3]) for k in ("사람이", "merge_batch"))]

    assert unmarked(["이 단계는 브로드캐스트가 한다"]) == [1] and unmarked(["브로드캐스트 — 사람이 친다"]) == []   # 합성 결함
    tracked = subprocess.run(["git", "ls-files", "tools", "src", "tests", ".github"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60).stdout.split()
    bad = {}
    for rel in tracked:
        p = ROOT / rel
        if p.suffix not in (".py", ".sh", ".yml", ".ts", ".tsx", ".md") or p.name == "test_pushready.py":
            continue
        u = unmarked(p.read_text(encoding="utf-8", errors="replace").splitlines())
        if u:
            bad[rel] = u
    assert not bad, f"「브로드캐스트」가 사람 손임을 안 말한다: {bad}"


# ── #220 도착 열거 ① ② — 사람이 감사 훅을 켜고 돈 사슬의 로그에서 `EDGES` 의 근거를 읽는다(합성 로그 · 이 시험은 사슬을 안 친다) ──────────

def _rows(*triples):
    return [(k, p, t) for k, p, t in triples]


def test_measured_edges_reads_each_verdict_from_a_synthetic_chain_log():
    m = P.measured_edges(_rows(
        ("r", "data/golden/docseal.json", "㉢"), ("w", "data/golden/docseal.json", "㉢"),
        ("r", "data/golden/docseal.json", "㉠"), ("r", "data/golden/mutation.json", "㉠"), ("w", "tools/suppress.py", "㉠"),
        ("r", "tools/suppress.py", "㉤"), ("r", "tools/mutate.py", "㉤"), ("r", "data/golden/mutation.json", "㉤"), ("w", "data/golden/mutation.json", "㉤"),
        ("r", "tools/gatefast.py", "㉡"), ("r", "data/golden/docseal.json", "㉡"), ("w", "data/golden/docseal.json", "㉡"),
        ("w", "tools/suppress.py", "test_x.py"), ("r", "tools/suppress.py", "인코딩·개행"),            # 사슬 칸이 아닌 꼬리표는 안 센다
    ))
    got = {(a, b): (verdict, fs) for a, b, _sure, verdict, fs in m["edges"]}
    assert got[("㉠", "㉤")] == ("밟혔다", ["tools/suppress.py"])
    assert got[("㉠", "㉡")] == ("안 밟혔다", []), "㉡ 이 그 도구를 안 읽었으면 이번에는 안 밟힌 것이다"
    assert got[("㉤", "㉠")] == ("밟혔다", ["data/golden/mutation.json"]) and got[("㉢", "㉠")] == ("밟혔다", ["data/golden/docseal.json"])
    assert got[("㉤", "㉤")] == ("안 밟혔다", []), "제 장부를 읽고 쓰는 것은 자기 루프의 증거가 아니다"
    assert m["extra"] == [("㉡", "㉠", ["data/golden/docseal.json"])], "㉢ · ㉡ 은 같은 도구라 도장 파일을 주고받는 것은 변이 아니다 — 그러나 ㉡ 이 쓴 도장 파일을 래칫이 읽는 쌍은 모델에 없으니 낸다"
    assert m["steps"]["㉠"]["w"] == {"tools/suppress.py"} and len(m["steps"]["㉠"]["r"]) == 2
    assert set(got) == {(a, b) for a, b, *_ in P.EDGES}, "EDGES 의 변마다 판정이 하나씩 있어야 한다"


def test_measured_edges_sees_the_self_loop_an_unmodelled_pair_and_an_unmeasured_step():
    m = P.measured_edges(_rows(
        ("r", "tools/mutate.py", "㉤"), ("w", "tools/mutate.py", "㉤"), ("w", "data/golden/mutation.json", "㉤"),
        ("r", "tools/mutate.py", "㉡"), ("w", "data/golden/docseal.json", "㉡"),
    ))
    got = {(a, b): (verdict, fs) for a, b, _sure, verdict, fs in m["edges"]}
    assert got[("㉤", "㉤")] == ("밟혔다", ["tools/mutate.py"]), "제 소스를 쓰고 읽으면 자기 루프가 밟힌 것이다"
    assert got[("㉠", "㉤")][0] == got[("㉠", "㉡")][0] == got[("㉢", "㉠")][0] == "안 쟀다", "한쪽 칸의 줄이 0 이면 「안 밟혔다」가 아니라 「안 쟀다」다"
    assert m["extra"] == [("㉤", "㉡", ["tools/mutate.py"])], "모델에 없는 쓰기→읽기 쌍은 따로 낸다"
    out = P.render_edges(m)
    assert "㉤→㉤ [가능] 실측 — 밟혔다: tools/mutate.py" in out and "㉤→㉡ [모델에 없다]" in out and "㉠→㉤ [확정] 실측 — 안 쟀다" in out
    assert all(v == "안 쟀다" for _a, _b, _s, v, _f in P.measured_edges([])["edges"]), "빈 로그는 변이 없다는 뜻이 아니다"


def test_a_write_that_was_undone_is_not_evidence_of_an_edge():
    """`mutate` 는 과녁 도구를 제자리에서 흔들고 되돌린다 — 훅은 그것도 쓰기로 적는다. 사슬 뒤에 실제로 달라진 파일(`kept`)에 없으면 증거로 안 친다."""
    rows = _rows(("w", "tools/suppress.py", "㉤"), ("r", "tools/suppress.py", "㉤"), ("w", "tools/mutate.py", "㉤"), ("r", "tools/mutate.py", "㉤"), ("w", "data/golden/mutation.json", "㉤"))
    naive = {(a, b): fs for a, b, _s, _v, fs in P.measured_edges(rows)["edges"]}
    assert naive[("㉤", "㉤")] == ["tools/mutate.py", "tools/suppress.py"], "거르지 않으면 흔든 과녁이 전부 자기 루프로 보인다(이 시험이 막는 오독)"
    m = P.measured_edges(rows, kept={"tools/mutate.py", "data/golden/mutation.json"})
    assert {(a, b): (v, fs) for a, b, _s, v, fs in m["edges"]}[("㉤", "㉤")] == ("밟혔다", ["tools/mutate.py"])
    assert m["steps"]["㉤"]["u"] == {"tools/suppress.py"} and m["steps"]["㉤"]["w"] == {"tools/mutate.py", "data/golden/mutation.json"}
    assert "썼다 되돌린 것 1 · 쓰기 2" in P.render_edges(m)
    only_undone = P.measured_edges(_rows(("w", "tools/suppress.py", "㉤")), kept=set())
    assert {(a, b): v for a, b, _s, v, _f in only_undone["edges"]}[("㉤", "㉤")] == "안 밟혔다", "되돌린 쓰기뿐이어도 그 칸은 돈 것이다(안 쟀다가 아니다)"


def test_the_edges_reader_reads_a_log_that_real_tagged_children_wrote_and_runs_nothing(tmp_path: Path, monkeypatch, capsys):
    """복사 블록과 같은 길을 작은 임시 뿌리에서 걷는다 — `fsaudit.prepare` → `PYTHONPATH`(`sitecustomize`) → `FIRE_LANE_AUDIT_TAG=<칸>` 자식 둘 → `--edges`."""
    import importlib.util
    import os
    import sys
    site = ROOT / "tests" / "audit_site"
    spec = importlib.util.spec_from_file_location("fsaudit_for_pushready", site / "fsaudit.py")
    fsaudit = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fsaudit
    spec.loader.exec_module(fsaudit)
    root, audit = tmp_path / "repo", tmp_path / "audit"
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "x.py").write_text("N = 1\n", encoding="utf-8")
    (root / "untracked.txt").write_text("u\n", encoding="utf-8")
    fsaudit.prepare(str(audit), str(root), {"tools/x.py"})
    env = {**os.environ, "FIRE_LANE_AUDIT_DIR": str(audit), "PYTHONPATH": str(site)}
    for tag, code in (("㉠", "open('tools/x.py', 'w', encoding='utf-8').write('N = 2\\n'); open('untracked.txt', 'w', encoding='utf-8').write('v')"),
                      ("㉤", "open('tools/x.py', encoding='utf-8').read(); open('untracked.txt', encoding='utf-8').read()")):
        r = subprocess.run([sys.executable, "-c", code], cwd=root, env={**env, "FIRE_LANE_AUDIT_TAG": tag}, capture_output=True, text=True, timeout=60, check=False)
        assert r.returncode == 0, r.stderr
    assert P.audit_rows(audit) == [x[:3] for x in fsaudit.read_log(str(audit))], "로그 꼴을 `fsaudit.read_log` 와 다르게 읽는다"
    m = P.measured_edges(P.audit_rows(audit))
    assert ("㉠", "㉤", True, "밟혔다", ["tools/x.py"]) in m["edges"], m["edges"]
    assert m["steps"]["㉠"]["w"] == {"tools/x.py"}, "추적 안 된 파일은 안 센다"
    ran: list[list[str]] = []
    monkeypatch.setattr(P, "real_run", lambda argv, cwd: (ran.append(argv), (0, "tools/x.py\n"))[1])
    assert P.main(["--edges", str(audit), "abc123"]) == 0
    assert ran == [["git", "diff", "--name-only", "abc123"]], f"--edges 는 읽는 git 한 줄만 돈다 — {ran}"
    assert "㉠→㉤ [확정] 실측 — 밟혔다: tools/x.py" in capsys.readouterr().out
    monkeypatch.setattr(P, "real_run", lambda argv, cwd: (0, ""))                # 사슬 뒤에 달라진 것이 없다 = 썼다 되돌렸다
    assert P.main(["--edges", str(audit)]) == 0 and "㉠→㉤ [확정] 실측 — 안 밟혔다" in capsys.readouterr().out
    monkeypatch.setattr(P, "real_run", lambda argv, cwd: (128, "fatal: bad revision"))
    assert P.main(["--edges", str(audit), "없는커밋"]) == 1, "git 이 죽으면 닫힌 쪽 — 거르지 않은 실측을 내지 않는다"
    capsys.readouterr()
    import pytest
    with pytest.raises(OSError):
        P.audit_rows(tmp_path / "없는 디렉터리")       # 로그가 없으면 죽는다 — 빈 실측으로 안 읽는다


def test_the_forecast_names_both_samples_the_old_order_and_the_new_one():
    line = next(x for x in P.forecast([_blk("㉠", [WRITE])]).lines if "표본" in x)
    assert f"{P.SAMPLE_LAPS}바퀴" in line and "옛 순서" in line and f"사슬 {P.SAMPLE_NEW_ORDER[0]}건" in line and f"{P.SAMPLE_NEW_ORDER[1]}바퀴" in line
    assert "증명은 아니다" in line, "표본을 고정점의 증명처럼 적지 않는다"
    assert P.SAMPLE_NEW_ORDER[1] == P.forecast([_blk(k) for k in ("㉢", "㉤", "㉡")] + [_blk("㉠", [WRITE])]).sure, "실증 표본이 모델의 확정 바퀴와 다르면 문구가 거짓이다"

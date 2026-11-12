"""tools/gatefast.py — 훅 게이트가 CI 빠른 잡에 **덮이는가**를 세 갈래로 센다.  (PLAN #210)

★ 양성 대조가 본체다 — 같은 합성 입력에서 ① 이름도 인자도 같으면 「덮인다」 ② **이름은 같고 인자가 다르면 「인자가 다르다」**(덮인다도 안 덮인다도 아니다 —
  이름만 맞는 것을 덮인다에 넣으면 그 수가 거짓이다) ③ 이름이 없으면 「안 덮인다」 ④ 면제는 검사기 경로로 붙는다.

IN    `tools/gatefast.py` · 합성 게이트 · 합성 워크플로
OUT   없음 (검사)
PARAM 없음
밖    인자가 다른 것이 결함인지 의도인지는 안 가린다(그것은 사람이 `# ci-exempt:` 로 적는다). `contract-heavy` · `contract-tests` 는 안 본다.
"""
from __future__ import annotations

import json

import gatefast as F
import pytest

GATES = [
    ("같다", "uv run python tools/aaa.py --ratchet"),
    ("인자 다르다", "uv run python tools/bbb.py --ratchet"),
    ("없다", "uv run python tools/ccc.py"),
    ("모듈", "uv run python -m firelane.ddd check"),
    ("시험", "uv run pytest tests/test_eee.py -q -p no:cacheprovider"),
    ("시험 없음", "uv run pytest tests/test_fff.py -q"),
]
FAST = [
    "uv run python tools/aaa.py --ratchet",
    "uv run python tools/bbb.py",                     # 같은 검사기 · 다른 인자(전수)
    "uv run python -m firelane.ddd check",
    "uv run pytest tests/test_eee.py -q -p no:cacheprovider",
]


def test_no_gates_means_nothing_to_classify_and_a_real_gate_is_classified():
    """카나리아 쌍 — 게이트가 없으면 조용하고(`assert not`) 합성 게이트는 갈래가 붙는다(`assert … ==`)."""
    assert not F.classify([], FAST, {})
    assert F.classify(GATES, FAST, {})["같다"]["갈래"] == "덮인다"


def test_the_three_kinds_are_told_apart():
    res = F.classify(GATES, FAST, {})
    assert res["같다"]["갈래"] == "덮인다"
    assert res["인자 다르다"]["갈래"] == "인자가 다르다" and res["인자 다르다"]["CI"] == [""]     # CI 는 인자 없이 돈다
    assert res["없다"]["갈래"] == "안 덮인다"
    assert res["모듈"]["갈래"] == "덮인다" and res["시험"]["갈래"] == "덮인다" and res["시험 없음"]["갈래"] == "안 덮인다"


def test_same_name_with_other_arguments_is_never_counted_as_covered():
    """★ 이 시험이 막으려는 거짓 — 「훅이 `--ratchet` 만 도는데 CI 가 같은 검사기를 전수로 돈다」를 덮임으로 세지 않는다."""
    res = F.classify([("g", "uv run python tools/x.py --ratchet")], ["uv run python tools/x.py"], {})
    assert res["g"]["갈래"] == "인자가 다르다"
    assert res["g"]["갈래"] != "덮인다"


def test_an_exemption_is_attached_by_the_checker_path_and_not_invented():
    res = F.classify(GATES, FAST, {"tools/ccc.py": "레이크가 필요하다"})
    assert res["없다"]["면제"] == "레이크가 필요하다" and res["같다"]["면제"] is None and res["인자 다르다"]["면제"] is None


def test_a_bare_pytest_is_not_a_key_and_the_test_file_is():
    assert F.keys("uv run pytest tests/test_eee.py -q") == ["tests/test_eee.py"]
    assert F.keys("uv run python tools/aaa.py x") == ["tools/aaa.py"]
    assert not F.keys("echo hi")                           # 열쇠가 없는 명령은 조용하다(카나리아의 정상 입력 쪽)


def test_a_gate_without_a_key_is_named_not_counted():
    res = F.classify([("무열쇠", "echo hi")], FAST, {})
    assert res["무열쇠"]["갈래"] == "열쇠 없음"       # 못 잰 것 — 덮인다로도 안 덮인다로도 안 센다


def test_a_third_column_does_not_leak_into_the_command(tmp_path):
    """셋째 열(실측 초 등)이 생겨도 명령에 안 섞인다 — 이 도구는 첫 두 열만 읽는다."""
    g = tmp_path / "g.gates"
    g.write_text("# 주석\n이름\tuv run python tools/x.py --ratchet\t12.3\n", encoding="utf-8")
    assert F.gate_commands(g) == [("이름", "uv run python tools/x.py --ratchet")]


def test_fast_commands_join_continuations_and_skip_comments(tmp_path):
    wf = tmp_path / "w.yml"
    wf.write_text("jobs:\n  contract-fast:\n    steps:\n      - run: |\n          # 주석\n          uv run python tools/a.py \\\n            --x 1\n          uv run python tools/b.py\n"
                  "  contract-heavy:\n    steps:\n      - run: uv run python tools/h.py\n", encoding="utf-8")
    assert F.fast_commands(wf) == ["uv run python tools/a.py --x 1", "uv run python tools/b.py"]     # heavy 잡은 안 본다


def test_the_real_tree_every_gate_has_a_key_and_the_three_numbers_add_up():
    res = F.classify()
    assert res and all(v["갈래"] != "열쇠 없음" for v in res.values()), [n for n, v in res.items() if v["갈래"] == "열쇠 없음"]
    assert len(res) == len(F.gate_commands())
    assert {v["갈래"] for v in res.values()} <= {"덮인다", "인자가 다르다", "안 덮인다"}


def test_the_cli_prints_the_three_numbers_and_json_roundtrips(capsys):
    assert F.main([]) == 0
    assert "덮인다" in capsys.readouterr().out
    assert F.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("cmd,key,want", [
    ("uv run python tools/aaa.py --ratchet", "tools/aaa.py", ["--ratchet"]),
    ("uv run python tools/docpatch.py check a b", "tools/docpatch.py", ["check", "a", "b"]),
    ("uv run python -m firelane.ddd check", "firelane.ddd", ["check"]),
])
def test_arguments_are_read_after_the_key(cmd, key, want):
    assert F.args_of(cmd, key) == want


def test_an_exemption_does_not_change_the_kind_it_is_counted_apart():
    """면제가 붙어도 「안 덮인다」는 그대로 센다 — 면제는 따로 세어 사유 없는 것이 몇인지 본다."""
    res = F.classify([("a", "uv run python tools/a.py"), ("b", "uv run python tools/b.py")], [], {"tools/a.py": "의도"})
    assert res["a"]["갈래"] == "안 덮인다" and res["a"]["면제"] == "의도" and res["b"]["면제"] is None
    head = F.render(res).splitlines()[0]
    assert "안 덮인다 2" in head and "면제 1" in head and "사유 없음 1" in head


# ── #216 반대 방향 — CI(다섯 잡) → 훅 · ready · axis · ci, 그리고 층 선언표(단일 선언 · 열쇠는 (열쇠, 인자)) ───────────────────

def _ents(*cmds: str) -> dict:
    """합성 명령 → `entries()` 와 같은 모양(잡 `j` · 스크립트 = 명령 그대로)."""
    out = {}
    for c in cmds:
        k = F.keys(c)[0]
        out[(k, " ".join(F.args_of(c, k)))] = {"job": "j", "cmd": c, "script": c}
    return out


A, B, N = ("tools/a.py", ""), ("tools/b.py", ""), ("tools/n.py", "")
LAYERS = {B: ("ready", "훅 예산 — 합치면 넘는다"), N: ("ci", "망이 필요하다")}
CMDS = ("uv run python tools/a.py", "uv run python tools/b.py", "uv run python tools/n.py")


def test_the_reverse_direction_sorts_ci_checks_into_hook_ready_and_ci_only():
    rep = F.layer_report(_ents(*CMDS), {A}, LAYERS)
    assert (rep["훅"], rep["ready"], rep["ci"]) == ([A], [B], [N])
    assert not any(rep[k] for k in ("미선언", "죽은 선언", "훅과 겹친다", "사유 부족", "층 이름"))


def test_a_new_ci_check_without_a_layer_is_undeclared_so_the_row_cannot_silently_reopen():
    rep = F.layer_report(_ents(*CMDS, "uv run python tools/new.py"), {A}, LAYERS)
    assert rep["미선언"] == [("tools/new.py", "")]


def test_a_table_entry_that_ci_dropped_is_a_dead_declaration_and_one_that_the_hook_took_is_an_overlap():
    rep = F.layer_report(_ents(CMDS[0], CMDS[1]), {A, B}, LAYERS)
    assert rep["죽은 선언"] == [N] and rep["훅과 겹친다"] == [B]


def test_a_short_reason_or_an_unknown_layer_name_is_caught():
    rep = F.layer_report(_ents(*CMDS), {A}, {B: ("ready", "네"), N: ("몰라", "사유가 충분히 길다")})
    assert rep["사유 부족"] == [B] and rep["층 이름"] == [N]


def test_ready_commands_are_ci_s_own_step_text_not_a_copy():
    assert F.ready_commands(_ents(*CMDS), LAYERS) == [(B, "uv run python tools/b.py")]


def test_the_same_tool_with_different_arguments_is_two_checks_so_the_strict_one_cannot_hide_behind_the_plain_one():
    """★ 2026-11-11 PR 이 빨갰던 모양 — `ruff` 가 기본 룰셋(fast)과 엄격 룰셋(strict)으로 둘인데 열쇠만 쓰면 둘째가 첫째 뒤에 숨는다."""
    ents = _ents("uv run ruff check src tools tests", "uv run ruff check $FILES --config .ruff-strict.toml")
    assert set(ents) == {("ruff", "check src tools tests"), ("ruff", "check $FILES --config .ruff-strict.toml")}
    plain = ("ruff", "check src tools tests")
    rep = F.layer_report(ents, set(), {plain: ("ready", "기본 룰셋을 이미 올렸다")})
    assert rep["미선언"] == [("ruff", "check $FILES --config .ruff-strict.toml")], "엄격 ruff 가 기본 ruff 뒤에 숨었다"


def test_the_hook_covers_a_check_only_when_the_arguments_match():
    ents = _ents("uv run python tools/a.py --ratchet")
    assert F.layer_report(ents, {("tools/a.py", "--ratchet")}, {})["훅"] == [("tools/a.py", "--ratchet")]
    assert F.layer_report(ents, {("tools/a.py", "")}, {})["미선언"] == [("tools/a.py", "--ratchet")], "인자가 다른 훅 게이트가 CI 검사를 덮은 것으로 셌다"


def test_shell_syntax_is_not_an_argument(tmp_path):
    """`owned_paths --py-only | wc -l)` 의 파이프와 닫는 괄호가 인자로 세어져 같은 검사가 셋으로 갈렸다."""
    ents = _ents("N=$(uv run python tools/owned_paths.py --py-only | wc -l)", "FILES=$(uv run python tools/owned_paths.py --py-only)")
    assert set(ents) == {("tools/owned_paths.py", "--py-only")}


def test_all_five_ci_jobs_are_read_not_only_contract_fast(tmp_path):
    wf = tmp_path / "w.yml"
    def steps(c: str) -> str:
        return "    steps:\n      - run: " + c + "\n"
    body = "jobs:\n" + "".join(f"  {j}:\n" + steps(f"uv run python tools/{j.split('-')[1]}.py") for j in F.JOBS)
    wf.write_text(body, encoding="utf-8")
    got = F.entries(wf)
    assert {k for k, _ in got} == {f"tools/{j.split('-')[1]}.py" for j in F.JOBS}, "다섯 잡 중 일부만 읽었다"
    assert {v["job"] for v in got.values()} == set(F.JOBS)


def test_a_multi_line_step_runs_as_one_script_so_a_variable_given_in_one_line_reaches_the_next():
    run = "FILES=$(uv run python tools/owned_paths.py --py-only)\n# 주석\ntest -n \"$FILES\" || exit 0\nuv run ruff check $FILES --config .ruff-strict.toml\n"
    script = F.step_script(run)
    assert "FILES=$(" in script and "ruff check $FILES" in script and "주석" not in script


def test_the_real_tree_every_ci_check_has_a_layer_and_the_table_has_no_dead_entry():
    """★ 이 시험이 `#216` 이 다시 안 열리게 하는 이음매다 — 다섯 잡 어디든 검사를 더하고 층을 안 적으면 여기서 빨개진다(CI `contract-tests` 가 전수로 돈다)."""
    rep = F.layer_report()
    bad = {k: v for k, v in rep.items() if k in ("미선언", "죽은 선언", "훅과 겹친다", "사유 부족", "층 이름") and v}
    assert not bad, f"층 선언표(tools/gatefast.py LAYERS)가 CI 와 어긋난다: {bad}"
    assert ("tools/env_check.py", "") in rep["훅"], "env_check 는 훅에 든다 — 2026-11-11 CI 가 이것 때문에 빨갰다"
    assert any(k[0] == "ruff" and ".ruff-strict.toml" in k[1] for k in rep["ready"]), "엄격 ruff 가 ready 층에 없다 — PR CI 가 그것으로 빨갰다"
    assert {k[0] for k in rep["ready"]} >= {"tools/docnum_check.py", "tools/unusedcheck.py", "tools/owned_paths.py"}, "엄격 잡의 싼 셋이 ready 가 아니다"


# ── #216 · 2026-11-11 — env_check 가 훅에 **실제로 들어 있고 실제로 무는가**(같은 결함으로 CI 가 하루에 두 번 빨갰다) ──────────────

def _env_check_gate() -> tuple[str, str]:
    import gate_parity as GP
    hits = [(n, c) for n, c in GP.gate_commands() if "tools/env_check.py" in GP.keys(c)]
    assert len(hits) == 1, f"훅에 env_check 게이트가 {len(hits)}개다 — 하나여야 한다(없으면 `paths.py` 밖의 os.environ 독자가 CI 에서만 빨갛다)"
    return hits[0]


def test_env_check_is_a_hook_gate_with_the_same_command_as_ci_and_is_not_in_the_layer_table():
    name, _cmd = _env_check_gate()
    assert F.classify()[name]["갈래"] == "덮인다", "훅의 env_check 가 CI 와 인자까지 같지 않다 — 로컬 초록이 CI 초록이 아니다"
    assert ("tools/env_check.py", "") not in F.LAYERS, "훅으로 올린 검사는 층 표에 있으면 안 된다(훅과 겹친다) — 올렸으면 표에서 뺀다"
    assert ("tools/env_check.py", "") in F.layer_report()["훅"]


def test_the_hook_s_own_env_check_command_goes_red_on_a_reader_outside_paths_py(tmp_path):
    """훅 파일의 **그 명령 그대로** 돌려 본다 — 선언만 있고 안 무는 게이트(이름만 있는 줄)를 막는다. 거울에 결함을 심는다."""
    import subprocess
    import sys

    from tracked_guard import mirror_tree
    _name, cmd = _env_check_gate()
    argv = cmd.replace("uv run python", "", 1).split()
    root = F.ROOT
    clean = subprocess.run([sys.executable, *argv], cwd=root, capture_output=True, text=True, timeout=120, check=False)
    assert clean.returncode == 0, "실물에서 env_check 가 이미 빨갛다:\n" + clean.stdout + clean.stderr
    m = mirror_tree(tmp_path / "m", copy=("tools",), replace={"tools/zz_env_probe.py": "import os\nX = os.environ.get('HOME')\n"})
    bad = subprocess.run([sys.executable, *argv], cwd=m, capture_output=True, text=True, timeout=120, check=False)
    assert bad.returncode != 0 and "zz_env_probe.py" in bad.stdout + bad.stderr, "훅의 env_check 가 심은 결함을 못 문다\n" + bad.stdout + bad.stderr


def test_gatefast_counts_hook_to_pushready_too_every_hook_gate_runs_in_the_mirror_or_is_replaced_with_a_reason():
    import gate_parity as GP
    hp = F.hook_vs_pushready()
    assert len(hp["돈다"]) + len(hp["대신"]) == len(GP.gate_commands()), "훅 게이트가 ㉨ 에서도 대체 표에서도 빠졌다 — 먼저 보는 도구가 나중 도구보다 약하다"
    assert hp["돈다"] and all(" — " in x and len(x.split(" — ", 1)[1]) >= 5 for x in hp["대신"])


def test_the_navi_unit_tests_run_before_the_push_not_only_in_ci():
    """★ `vitest` 전수는 **푸시 전에** 돈다(`ready` 층 — `pushready` ㉨ 이 CI 의 명령 글자 그대로). (DECISIONS §719 · ⓲B 재잠금 ⑥)

    `#53` 재잠금이 `web/data` 의 판정을 움직였고 `astarbench` 둘이 **CI 에서야** 빨갰다 — `testpick` 은 pytest 만 고르고, 이 검사는 `ci` 층(사유: 「npm 이 필요하다」)에 있어
    푸시 전 어느 그물에도 없었다. 그 사유는 `npm ci`(망)와 `npm run test`(`node_modules` 만 있으면 된다)를 뭉친 것이었다. 되돌리면 같은 구멍이 열린다.
    """
    import gatefast as GF
    layer, why = GF.LAYERS[("navi:test", "@web/navi")]
    assert layer == "ready", f"`vitest` 전수가 `{layer}` 층이다 — 재잠금이 움직이는 수를 푸시 전에 못 본다"
    assert "vitest" in why and "§719" in why, "사유가 이 결정을 안 적었다"


# ── 세 번째 축: 작업 디렉터리 (2026-11-12 · DECISIONS §720 · 재잠금 ⑦) ───────────────────────────────

def _wf(tmp_path, *runs: str):
    """합성 워크플로 — 잡 하나 · 단계마다 `run:` 하나."""
    import yaml
    steps = [{"name": f"s{i}", "run": r} for i, r in enumerate(runs)]
    p = tmp_path / "wf.yml"
    p.write_text(yaml.safe_dump({"jobs": {"contract-fast": {"steps": steps}}}), encoding="utf-8")
    return p


def test_the_same_command_in_two_directories_is_two_entries(tmp_path):
    """★ **한 이름 뒤에 둘이 숨는다**(엄격 ruff 가 기본 뒤에 · `npm ci` 가 `npm run test` 뒤에 — 이제 디렉터리). 열쇠에 디렉터리가 없으면 둘째가 첫째 뒤에 숨는다."""
    wf = _wf(tmp_path, "cd sub_a\nuv run python tools/z.py", "cd sub_b\nuv run python tools/z.py", "uv run python tools/z.py")
    got = F.entries(wf, ("contract-fast",))
    assert set(got) == {("tools/z.py", "@sub_a"), ("tools/z.py", "@sub_b"), ("tools/z.py", "")}, sorted(got)


def test_the_script_that_runs_is_made_from_the_same_line_as_the_key(tmp_path):
    """★ **선언과 실행이 같은 곳에서 나온다.** 열쇠가 `@디렉터리` 면 실행 스크립트는 `cd 디렉터리 &&` 로 시작한다 — 루트에서 돌려도 같은 곳에서 돈다(`ENOENT package.json`)."""
    wf = _wf(tmp_path, "uv run python tools/a.py\ncd web/x\nuv run python tools/z.py --q\ncd ../..\nuv run python tools/b.py")
    got = F.entries(wf, ("contract-fast",))
    assert got[("tools/a.py", "")]["script"] == "uv run python tools/a.py"
    assert got[("tools/z.py", "@web/x --q")]["script"] == "cd web/x && uv run python tools/z.py --q", got
    assert got[("tools/b.py", "")]["script"] == "uv run python tools/b.py", "`cd ../..` 로 되돌아온 줄이 아직 web/x 에서 돈다"


def test_cd_and_chain_on_one_line_carries_to_the_next_lines(tmp_path):
    """`cd X && …` 는 현재 셸의 디렉터리를 바꾼다 — 셸이 읽는 대로 이후 줄도 X 에서 돈다."""
    wf = _wf(tmp_path, "cd q && uv run python tools/a.py\nuv run python tools/b.py")
    got = F.entries(wf, ("contract-fast",))
    assert ("tools/a.py", "@q") in got and ("tools/b.py", "@q") in got, sorted(got)


def test_every_real_entry_with_a_directory_runs_from_the_root_without_enoent():
    """실물: 디렉터리가 있는 CI 검사는 전부 그 디렉터리가 **실재**하고 스크립트가 `cd` 로 들어간다 — `pushready` ㉨ 는 저장소 루트에서 글자 그대로 돈다(`npm run test` 가 루트에서 ENOENT 였다)."""
    root = F.ROOT
    bad = []
    for k, e in F.entries().items():
        if e.get("cwd"):
            if not (root / e["cwd"]).is_dir():
                bad.append(f"{k}: {e['cwd']} 가 없다")
            if not e["script"].startswith(f"cd {e['cwd']} && "):
                bad.append(f"{k}: 스크립트가 `cd {e['cwd']}` 로 안 시작한다 — {e['script'][:60]}")
    assert not bad, bad
    assert any(k[0] == "navi:test" for k, e in F.entries().items() if e.get("cwd")), "`navi:test` 가 디렉터리를 못 얻었다"

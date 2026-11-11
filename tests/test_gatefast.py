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


# ── #216 반대 방향 — CI → 훅 · ready · ci, 그리고 층 선언표(단일 선언) ─────────────────────────────

LAYERS = {"tools/b.py": ("ready", "훅 예산 — 합치면 넘는다"), "tools/n.py": ("ci", "망이 필요하다")}
FAST2 = ["uv run python tools/a.py", "uv run python tools/b.py", "uv run python tools/n.py"]


def test_the_reverse_direction_sorts_ci_checks_into_hook_ready_and_ci_only():
    rep = F.layer_report(FAST2, {"tools/a.py"}, LAYERS)
    assert (rep["훅"], rep["ready"], rep["ci"]) == (["tools/a.py"], ["tools/b.py"], ["tools/n.py"])
    assert not any(rep[k] for k in ("미선언", "죽은 선언", "훅과 겹친다", "사유 부족", "층 이름"))


def test_a_new_ci_check_without_a_layer_is_undeclared_so_the_row_cannot_silently_reopen():
    rep = F.layer_report([*FAST2, "uv run python tools/new.py"], {"tools/a.py"}, LAYERS)
    assert rep["미선언"] == ["tools/new.py"]


def test_a_table_entry_that_ci_dropped_is_a_dead_declaration_and_one_that_the_hook_took_is_an_overlap():
    rep = F.layer_report(["uv run python tools/a.py", "uv run python tools/b.py"], {"tools/a.py", "tools/b.py"}, LAYERS)
    assert rep["죽은 선언"] == ["tools/n.py"] and rep["훅과 겹친다"] == ["tools/b.py"]


def test_a_short_reason_or_an_unknown_layer_name_is_caught():
    rep = F.layer_report(FAST2, {"tools/a.py"}, {"tools/b.py": ("ready", "네"), "tools/n.py": ("몰라", "사유가 충분히 길다")})
    assert rep["사유 부족"] == ["tools/b.py"] and rep["층 이름"] == ["tools/n.py"]


def test_ready_commands_are_ci_s_own_text_not_a_copy():
    assert F.ready_commands(FAST2, LAYERS) == [("tools/b.py", "uv run python tools/b.py")]


def test_the_real_tree_every_ci_fast_check_has_a_layer_and_the_table_has_no_dead_entry():
    """★ 이 시험이 `#216` 이 다시 안 열리게 하는 이음매다 — CI 빠른 잡에 검사를 더하고 층을 안 적으면 여기서 빨개진다(CI `contract-tests` 가 전수로 돈다)."""
    rep = F.layer_report()
    bad = {k: v for k, v in rep.items() if k in ("미선언", "죽은 선언", "훅과 겹친다", "사유 부족", "층 이름") and v}
    assert not bad, f"층 선언표(tools/gatefast.py LAYERS)가 CI 와 어긋난다: {bad}"
    assert "tools/env_check.py" in rep["훅"], "env_check 는 훅에 든다 — 2026-11-11 CI 가 이것 때문에 빨갰다"


# ── #216 · 2026-11-11 — env_check 가 훅에 **실제로 들어 있고 실제로 무는가**(같은 결함으로 CI 가 하루에 두 번 빨갰다) ──────────────

def _env_check_gate() -> tuple[str, str]:
    import gate_parity as GP
    hits = [(n, c) for n, c in GP.gate_commands() if "tools/env_check.py" in GP.keys(c)]
    assert len(hits) == 1, f"훅에 env_check 게이트가 {len(hits)}개다 — 하나여야 한다(없으면 `paths.py` 밖의 os.environ 독자가 CI 에서만 빨갛다)"
    return hits[0]


def test_env_check_is_a_hook_gate_with_the_same_command_as_ci_and_is_not_in_the_layer_table():
    name, _cmd = _env_check_gate()
    assert F.classify()[name]["갈래"] == "덮인다", "훅의 env_check 가 CI 와 인자까지 같지 않다 — 로컬 초록이 CI 초록이 아니다"
    assert "tools/env_check.py" not in F.LAYERS, "훅으로 올린 검사는 층 표에 있으면 안 된다(훅과 겹친다) — 올렸으면 표에서 뺀다"
    assert "tools/env_check.py" in F.layer_report()["훅"]


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

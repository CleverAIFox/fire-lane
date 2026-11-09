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
    assert F.keys("echo hi") == []


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

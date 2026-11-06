"""
test_ledger_extract.py — `tools/ledger_extract.py`(범용 추출 선언 도구)가 **대장 텍스트를 안전하게 고치는가**.  (DECISIONS §648)

IN    합성 대장 텍스트(임시 파일) · 도구의 `main()`
OUT   통과/실패
밖    실제 `sources.yaml` 은 안 건드린다. 선언이 실물과 맞는지(행 수)는 `ingest` 의 몫이다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from firelane import ledger

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ledger_extract", ROOT / "tools/ledger_extract.py")
assert _spec and _spec.loader
tool = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = tool
_spec.loader.exec_module(tool)

HEAD = "datasets:\n"
A = """  a_src:
    stem: a_src
    kind: csv_table
    encoding: utf-8-sig
    schema:
      columns: ['SGG_NM', 'CTPV_NM', 'N']
"""
FLOW = A.replace("    schema:", "    contract: {encoding: utf-8-sig}\n    schema:")
BLOCK_C = A.replace("    schema:", "    contract:\n      # 주석이 있다\n      rows: 5\n    schema:")
B = "  b_src:\n    stem: b_src\n    kind: csv_table\n"
ARGS = ["--key", "a_src", "--normalize", "upper_strip", "--filter", "SGG_NM=동구", "--filter", "CTPV_NM=광주광역시",
        "--scope-min", "10", "--scope-max", "20"]


def _run(tmp_path, monkeypatch, text, *args):
    f = tmp_path / "sources.yaml"
    f.write_text(text, encoding="utf-8")
    monkeypatch.setattr(tool, "LEDGER", f)
    monkeypatch.setattr(sys, "argv", ["ledger_extract", *args])
    return tool.main(), f.read_text(encoding="utf-8")


def _con(text, key="a_src"):
    return ledger.parse(text)["datasets"][key]["contract"]


def test_inserts_a_block_after_kind_and_leaves_the_neighbour_alone(tmp_path, monkeypatch):
    src = HEAD + A + B
    rc, out = _run(tmp_path, monkeypatch, src, *ARGS, "--apply")
    assert rc == 0 and _con(out) == {"normalize_columns": "upper_strip", "scope_min": 10, "scope_max": 20,
                                     "filter": [{"column": "SGG_NM", "equals": "동구"}, {"column": "CTPV_NM", "equals": "광주광역시"}]}
    assert out.endswith(B) and "contract" not in ledger.parse(out)["datasets"]["b_src"]


def test_a_dry_run_writes_nothing(tmp_path, monkeypatch):
    src = HEAD + A
    rc, out = _run(tmp_path, monkeypatch, src, *ARGS)
    assert rc == 0 and out == src


def test_a_one_line_contract_is_unfolded_and_its_other_keys_survive(tmp_path, monkeypatch):
    rc, out = _run(tmp_path, monkeypatch, HEAD + FLOW, *ARGS, "--apply")
    assert rc == 0 and _con(out)["encoding"] == "utf-8-sig" and _con(out)["scope_max"] == 20


def test_the_same_declaration_is_idempotent(tmp_path, monkeypatch):
    _, once = _run(tmp_path, monkeypatch, HEAD + A, *ARGS, "--apply")
    rc, twice = _run(tmp_path, monkeypatch, once, *ARGS, "--apply")
    assert rc == 0 and twice == once


def test_a_different_declaration_is_refused_without_replace(tmp_path, monkeypatch):
    _, once = _run(tmp_path, monkeypatch, HEAD + A, *ARGS, "--apply")
    other = [*ARGS[:-1], "30"]
    rc, out = _run(tmp_path, monkeypatch, once, *other, "--apply")
    assert rc == 1 and out == once, "조용히 덮지 않는다"
    rc, out = _run(tmp_path, monkeypatch, once, *other, "--apply", "--replace")
    assert rc == 0 and _con(out)["scope_max"] == 30


def test_a_contract_with_comments_is_refused(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="주석"):
        _run(tmp_path, monkeypatch, HEAD + BLOCK_C, *ARGS, "--apply")


@pytest.mark.parametrize("args,why", [
    (["--normalize", "upper_strip", "--filter", "sgg_nm=동구"], "정규화"),               # 소문자 칸을 대문자 정규화와 같이
    (["--filter", "NOPE=동구"], "schema.columns"),                                      # 없는 칸
    (["--filter", "SGG_NM=동구", "--scope-min", "9", "--scope-max", "3"], "통과할 수 있는 행"),  # 상한 < 하한
])
def test_an_invalid_declaration_is_never_written(tmp_path, monkeypatch, capsys, args, why):
    src = HEAD + A
    rc, out = _run(tmp_path, monkeypatch, src, "--key", "a_src", *args, "--apply")
    assert rc == 1 and out == src and why in capsys.readouterr().err


def test_no_filter_or_a_malformed_filter_is_a_usage_error(tmp_path, monkeypatch):
    assert _run(tmp_path, monkeypatch, HEAD + A, "--key", "a_src", "--apply")[0] == 2
    assert _run(tmp_path, monkeypatch, HEAD + A, "--key", "a_src", "--filter", "SGG_NM", "--apply")[0] == 2
    assert _run(tmp_path, monkeypatch, HEAD + A, "--key", "a_src", "--filter", "SGG_NM=", "--apply")[0] == 2


def test_an_unknown_key_stops(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="0개"):
        _run(tmp_path, monkeypatch, HEAD + A, "--key", "nope", "--filter", "SGG_NM=동구")


def test_render_writes_one_condition_as_a_mapping_and_several_as_a_list():
    one = tool.render({"filter": {"column": "A", "equals": "x"}})
    many = tool.render({"filter": [{"column": "A", "equals": "x"}, {"column": "B", "equals": "y"}], "scope_min": 1})
    assert "column: A" in one and "- {column: A" not in one and "- {column: B, equals: y}" in many

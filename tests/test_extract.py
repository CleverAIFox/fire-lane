"""
test_extract.py — 전국 원본에서 지역 파생본을 만드는 **추출 단계**.  (DECISIONS §646)

── 이 시험이 무는 것 ──────────────────────────────────────────
① 대문자 헤더 파일과 소문자 헤더 파일이 **한 결과로 합쳐진다**(`normalize_columns` — 2024 경계에서 칸 이름 케이스가 갈린다. 대문자 필터가 2024 이후를 0행으로 만들어
   139행을 잃은 사고가 이 시험의 이유다) · 값은 한 글자도 안 바뀐다.
② `filter` 가 지정한 행만 남기고 · 청크 크기가 결과를 안 바꾸고 · **공백을 걷어야 맞은 행**을 센다.
③ 계보(`rec["extract"]`)에 입력 파일별 sha · 필터 전 · 후 행 수가 남는다.
④ **조용히 덜 하지 않는다**: 필터가 0행이면 FAIL · `scope_min` 미달이면 FAIL · 필터 칸 이름이 틀리면 **죽는다** · 선언의 모양이 틀리면 `problems` 가 가린다.
⑤ 선언이 없으면 종전 경로 그대로다(회귀 없음) · 어휘가 `ledger.CONTRACT_KEYS` 에 있고 `read/extract.py` 가 그 이름을 읽는다.

밖    **실제 전국 파일로는 안 돌렸다**(합성 입력만) · 실제 대장 항목에 키를 안 달았다(대장의 `scope` 를 바꾸지 않는다 — 추출이 선 뒤의 사람 판단).
"""
from __future__ import annotations

import hashlib
import pathlib

import pytest

from firelane import ledger_check
from firelane.read import extract
from firelane.read.ctx import Ctx
from firelane.read.delimited import read_csv_table, read_csv_table_multi

UPPER = "DCLR_YR,CLMTY_EMD_NM,NOTE\n2023,동명동,가\n2023,산수동,나\n2023, 동명동 ,다\n"
LOWER = 'dclr_yr,clmty_emd_nm,note\n2024,동명동,N/A\n2024,지산동,\n2025,동명동,"  띄어쓰기  "\n'
CON = {"normalize_columns": "lower_strip", "filter": {"column": "clmty_emd_nm", "equals": "동명동"}}


def _ctx(tmp_path, files: dict[str, str | bytes], contract=CON, kind="csv_table", **extra):
    hits = []
    for name, body in files.items():
        p = tmp_path / name
        p.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
        hits.append(p)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    e = {"kind": kind, "encoding": "utf-8", "contract": dict(contract), **extra}
    return Ctx(key="t", e=e, src=hits[0], hits=hits, crs="", tmp=tmp_path, out=out, rec={"key": "t", "ambiguous": ["x"]}, save=lambda *a, **k: {})


def _sub(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


def _out(c):
    import pandas as pd
    return pd.read_csv(c.out / "t.csv", dtype=str, na_filter=False, encoding="utf-8-sig")


# ── ① 케이스가 갈린 파일이 한 결과로 합쳐진다 ──
def test_upper_and_lower_case_headers_merge_into_one_result(tmp_path):
    c = _ctx(tmp_path, {"a_2023.csv": UPPER, "b_2024.csv": LOWER})
    rec = read_csv_table(c)
    d = _out(c)
    assert rec["status"] == "OK" and rec["columns"] == ["dclr_yr", "clmty_emd_nm", "note"]
    assert d["dclr_yr"].tolist() == ["2023", "2023", "2024", "2025"], "대문자 파일의 동명동 둘 + 소문자 파일의 동명동 둘"
    assert rec["features"] == 4 and "ambiguous" not in rec and rec["resolved"] == "a_2023.csv + b_2024.csv"


def test_the_old_uppercase_filter_would_have_lost_the_lowercase_years(tmp_path):
    """★ 139행 사고의 재현 — 정규화 없이 대문자 칸 이름으로 거르면 소문자 헤더 파일은 **칸이 없어서** 죽는다(0행으로 조용히 통과하지 않는다)."""
    c = _ctx(tmp_path, {"b_2024.csv": LOWER}, contract={"filter": {"column": "CLMTY_EMD_NM", "equals": "동명동"}})
    with pytest.raises(ValueError, match="헤더에 없다"):
        read_csv_table(c)


def test_values_are_not_touched_only_column_names(tmp_path):
    c = _ctx(tmp_path, {"b_2024.csv": LOWER})
    read_csv_table(c)
    d = _out(c)
    assert d["note"].tolist() == ["N/A", "  띄어쓰기  "], "N/A · 안쪽 공백이 원문 그대로다(na_filter=False · strip 은 비교에만)"
    assert d["clmty_emd_nm"].tolist() == ["동명동", "동명동"]


# ── ② 필터 · 청크 · 공백 ──
def test_the_filter_keeps_only_the_named_rows_and_counts_whitespace_matches(tmp_path):
    c = _ctx(tmp_path, {"a.csv": UPPER})
    rec = read_csv_table(c)
    f = rec["extract"]["files"][0]
    assert (f["rows_in"], f["rows_out"], f["stripped_matches"]) == (3, 2, 1), "공백을 걷어야 맞은 행(` 동명동 `)을 숨기지 않고 센다"
    assert _out(c)["note"].tolist() == ["가", "다"]
    assert _out(c)["clmty_emd_nm"].tolist() == ["동명동", " 동명동 "], "저장값은 공백 그대로"


def test_the_chunk_size_does_not_change_the_result(tmp_path, monkeypatch):
    body = "A,B\n" + "".join(f"{i},{'x' if i % 3 == 0 else 'y'}\n" for i in range(25))
    flt = {"normalize_columns": "lower_strip", "filter": {"column": "b", "equals": "x"}}
    big = _ctx(_sub(tmp_path, "big"), {"f.csv": body}, contract=flt)
    got_big = read_csv_table(big)
    monkeypatch.setattr(extract, "CHUNK", 4)
    small = _ctx(_sub(tmp_path, "small"), {"f.csv": body}, contract=flt)
    got_small = read_csv_table(small)
    assert got_big["features"] == got_small["features"] == 9
    assert _out(big).equals(_out(small))


def test_a_declared_encoding_is_tried_first_then_the_candidates(tmp_path):
    cp = UPPER.encode("cp949")
    c = _ctx(tmp_path, {"a.csv": cp}, encoding="utf-8")
    assert read_csv_table(c)["features"] == 2, "대장의 encoding 이 틀려도 후보로 넘어간다 — 청크 중간의 디코드 실패도 처음부터 다시"


# ── ③ 계보 ──
def test_the_lineage_names_every_input_file_with_its_hash_and_row_counts(tmp_path):
    c = _ctx(tmp_path, {"a_2023.csv": UPPER, "b_2024.csv": LOWER})
    rec = read_csv_table_multi(c)
    ex = rec["extract"]
    assert ex["normalize_columns"] == "lower_strip" and ex["filter"] == CON["filter"]
    assert (ex["rows_in"], ex["rows_out"]) == (6, 4)
    assert [f["name"] for f in ex["files"]] == ["a_2023.csv", "b_2024.csv"]
    for f in ex["files"]:
        assert f["sha256"] == hashlib.sha256(pathlib.Path(tmp_path / f["name"]).read_bytes()).hexdigest()
        assert f["bytes"] == (tmp_path / f["name"]).stat().st_size, "바이트도 계보에 든다 — 원본을 내린 뒤 acquire --verify 의 짝"
    assert rec["source_sha256"] == ",".join(f["sha256"][:16] for f in ex["files"])


# ── 같은 이름이 여러 시도에 있다(동구) — 조건 하나로는 못 가른다 ──
def test_a_filter_list_keeps_only_rows_matching_every_condition(tmp_path):
    body = "SGG_NM,CTPV_NM,n\n동구,광주광역시,1\n동구,대구광역시,2\n 동구 ,광주광역시,3\n서구,광주광역시,4\n"
    flt = [{"column": "sgg_nm", "equals": "동구"}, {"column": "ctpv_nm", "equals": "광주광역시"}]
    c = _ctx(tmp_path, {"a.csv": body}, contract={"normalize_columns": "lower_strip", "filter": flt})
    rec = read_csv_table(c)
    assert _out(c)["n"].tolist() == ["1", "3"], "대구 동구(2)와 광주 서구(4)는 빠진다"
    assert rec["extract"]["filter"] == flt and rec["extract"]["files"][0]["stripped_matches"] == 1


def test_every_condition_of_a_filter_list_is_validated():
    e = {"kind": "csv_table", "contract": {"filter": [{"column": "a", "equals": "x"}, {"column": "b"}]}}
    assert any("둘뿐" in m for m in extract.problems("k", e))


def test_conditions_accepts_one_dict_or_a_list_and_nothing_is_none():
    one = {"column": "a", "equals": "x"}
    assert extract.conditions(one) == [one] and extract.conditions([one, one]) == [one, one] and extract.conditions(None) == []


# ── 원본을 내린 항목은 계보를 지키고, 그 폴더에서 읽는 길이 있다(§647) ──
def test_kept_preserves_the_last_record_only_when_the_raw_is_absent_and_declared_missing(tmp_path):
    (tmp_path / "t.csv").write_text("x", encoding="utf-8")
    prev = {"status": "OK", "extract": {"rows_out": 1}, "outputs": ["t.csv"]}
    e = {"kind": "csv_table", "status": "missing", "missing_why": "받지 않기로 했다", "contract": dict(CON)}
    assert extract.kept(prev, e, tmp_path, []) is prev
    assert extract.kept(prev, e, tmp_path, [tmp_path / "a.csv"]) is None, "실물이 있으면 다시 읽는다"
    assert extract.kept(prev, {**e, "status": "ok"}, tmp_path, []) is None, "missing 을 선언하지 않았으면 MISSING 이 맞다"
    assert extract.kept({**prev, "outputs": ["gone.csv"]}, e, tmp_path, []) is None, "산출물이 없으면 지난 기록은 거짓이다"
    assert extract.kept({"status": "OK", "outputs": ["t.csv"]}, e, tmp_path, []) is None, "계보가 없는 기록은 지킬 이유가 없다"
    assert extract.kept(None, e, tmp_path, []) is None


def test_paths_match_the_ledger_names_in_a_flat_folder(tmp_path):
    for n in ("nfa_ems_kr_2019.csv", "nfa_ems_kr_2020.csv", "other.csv"):
        (tmp_path / n).write_text("x", encoding="utf-8")
    e = {"stem": "nfa_ems", "ext": ["csv"], "files": ["nfa/nfa_ems_kr_2019.csv", "nfa/nfa_ems_kr_2020.csv"]}
    assert [q.name for q in extract.paths(e, tmp_path)] == ["nfa_ems_kr_2019.csv", "nfa_ems_kr_2020.csv"]


def test_source_dir_needs_a_folder_and_an_explicit_only(tmp_path):
    import pytest
    assert extract.source_dir(str(tmp_path), ["nfa_ems"]) == tmp_path.resolve()
    with pytest.raises(SystemExit, match="폴더가 아니다"):
        extract.source_dir(str(tmp_path / "nope"), ["nfa_ems"])
    with pytest.raises(SystemExit, match="--only"):
        extract.source_dir(str(tmp_path), None)


def test_scope_max_catches_an_overbroad_filter_that_scope_min_lets_through(tmp_path):
    body = "SGG_NM,CTPV_NM\n" + "동구,광주광역시\n" * 3 + "동구,대구광역시\n" * 9
    one = {"normalize_columns": "lower_strip", "filter": {"column": "sgg_nm", "equals": "동구"}, "scope_min": 2, "scope_max": 5}
    c = _ctx(tmp_path, {"a.csv": body}, contract=one)
    rec = read_csv_table(c)
    assert rec["status"] == "FAIL" and "scope_max" in rec["error"] and not (c.out / "t.csv").exists(), "12행 > 상한 5 — 하한 2 는 이것을 통과시켰다"
    both = {**one, "filter": [one["filter"], {"column": "ctpv_nm", "equals": "광주광역시"}]}
    assert read_csv_table(_ctx(_sub(tmp_path, "ok"), {"a.csv": body}, contract=both))["features"] == 3


@pytest.mark.parametrize("bad", [0, -1, True, "9", 1.5])
def test_scope_max_must_be_a_positive_integer(bad):
    e = {"kind": "csv_table", "contract": {"filter": {"column": "a", "equals": "x"}, "scope_max": bad}}
    assert any("scope_max" in m for m in extract.problems("k", e))


def test_scope_max_below_scope_min_is_refused():
    e = {"kind": "csv_table", "contract": {"filter": {"column": "a", "equals": "x"}, "scope_min": 10, "scope_max": 5}}
    assert any("통과할 수 있는 행" in m for m in extract.problems("k", e))


def test_upper_strip_unifies_the_year_boundary_case_to_the_downstream_names(tmp_path):
    con = {"normalize_columns": "upper_strip", "filter": {"column": "CLMTY_EMD_NM", "equals": "동명동"}}
    c = _ctx(tmp_path, {"a_2023.csv": UPPER, "b_2024.csv": LOWER}, contract=con)
    rec = read_csv_table(c)
    assert rec["columns"] == ["DCLR_YR", "CLMTY_EMD_NM", "NOTE"] and rec["features"] == 4, "하류가 읽는 이름(대문자)으로 나온다"
    bad = {"kind": "csv_table", "contract": {"normalize_columns": "upper_strip", "filter": {"column": "clmty_emd_nm", "equals": "x"}}}
    assert any("정규화 **뒤**" in m for m in extract.problems("k", bad)), "필터 칸도 정규화 뒤(대문자)로 적는다"


# ── one_of — 이름이 바뀐 값을 조용히 잃지 않는다(§649) ──
def test_one_of_keeps_rows_under_either_province_name_and_still_requires_the_other_conditions(tmp_path):
    body = ("CTPV_NM,SGG_NM,n\n광주광역시,동구,1\n전남광주통합특별시,동구,2\n 전남광주통합특별시 ,동구,3\n"
            "대구광역시,동구,4\n광주광역시,서구,5\n")
    flt = [{"column": "ctpv_nm", "one_of": ["광주광역시", "전남광주통합특별시"]}, {"column": "sgg_nm", "equals": "동구"}]
    c = _ctx(tmp_path, {"a.csv": body}, contract={"normalize_columns": "lower_strip", "filter": flt})
    rec = read_csv_table(c)
    assert _out(c)["n"].tolist() == ["1", "2", "3"], "새 이름 · 옛 이름 둘 다 오고 대구 동구 · 광주 서구는 빠진다"
    assert rec["extract"]["files"][0]["stripped_matches"] == 1 and rec["extract"]["filter"] == flt
    only_old = [{"column": "ctpv_nm", "equals": "광주광역시"}, flt[1]]
    c2 = _ctx(_sub(tmp_path, "old"), {"a.csv": body}, contract={"normalize_columns": "lower_strip", "filter": only_old})
    assert read_csv_table(c2)["features"] == 1, "equals 하나로는 새 이름 행을 조용히 잃는다 — one_of 가 필요한 까닭"


@pytest.mark.parametrize("bad", [["a"], [], ["a", "a"], ["a", ""], ["a", True], "a|b"])
def test_one_of_must_be_two_or_more_distinct_nonempty_values(bad):
    e = {"kind": "csv_table", "contract": {"filter": {"column": "a", "one_of": bad}}}
    assert any("one_of" in m for m in extract.problems("k", e)), bad


def test_a_condition_cannot_mix_equals_and_one_of():
    e = {"kind": "csv_table", "contract": {"filter": {"column": "a", "equals": "x", "one_of": ["x", "y"]}}}
    assert any("둘뿐" in m for m in extract.problems("k", e))


# ── ④ 조용히 덜 하지 않는다 ──
def test_a_filter_that_keeps_nothing_is_a_failure_not_a_silent_pass(tmp_path):
    c = _ctx(tmp_path, {"a.csv": UPPER}, contract={**CON, "filter": {"column": "clmty_emd_nm", "equals": "없는동"}})
    rec = read_csv_table(c)
    assert rec["status"] == "FAIL" and rec["features"] == 0 and "scope_min" in rec["error"] and not (c.out / "t.csv").exists()


def test_scope_min_is_enforced_after_the_filter(tmp_path):
    c = _ctx(tmp_path, {"a.csv": UPPER}, contract={**CON, "scope_min": 3})
    rec = read_csv_table(c)
    assert rec["status"] == "FAIL" and "3" in rec["error"]
    ok = _ctx(_sub(tmp_path, "ok"), {"a.csv": UPPER}, contract={**CON, "scope_min": 2})
    assert read_csv_table(ok)["status"] == "OK"


def test_files_with_different_columns_stop_unless_the_ledger_declares_them_optional(tmp_path):
    other = "dclr_yr,clmty_emd_nm,note,extra\n2024,동명동,x,새칸\n"
    c = _ctx(tmp_path, {"a.csv": UPPER, "b.csv": other})
    with pytest.raises(ValueError, match="선언 안 된"):
        read_csv_table(c)
    ok = _ctx(_sub(tmp_path, "ok"), {"a.csv": UPPER, "b.csv": other}, contract={**CON, "optional_cols": ["extra"]})
    rec = read_csv_table(ok)
    assert rec["columns"][-1] == "extra" and _out(ok)["extra"].tolist() == ["", "", "새칸"], "선언된 결손은 빈 값으로 채운다"


def test_normalized_names_that_collide_stop(tmp_path):
    c = _ctx(tmp_path, {"a.csv": "A,a,B\n1,2,3\n"}, contract={"normalize_columns": "lower_strip"})
    with pytest.raises(ValueError, match="겹친다"):
        read_csv_table(c)


# ── 선언의 모양 ──
@pytest.mark.parametrize("contract,kind,schema,needle", [
    ({"normalize_columns": "upper"}, "csv_table", None, "어휘"),
    ({"filter": {"column": "a", "equals": "x", "in": ["y"]}}, "csv_table", None, "둘뿐"),
    ({"filter": {"column": "a"}}, "csv_table", None, "둘뿐"),
    ({"filter": {"column": "", "equals": "x"}}, "csv_table", None, "비었다"),
    ({"filter": {"column": "a", "equals": ""}}, "csv_table", None, "equals"),
    ({"normalize_columns": "lower_strip", "filter": {"column": "CLMTY", "equals": "x"}}, "csv_table", None, "정규화 **뒤**"),
    ({"filter": {"column": "clmty_emd_nm", "equals": "x"}}, "csv_table", ["A", "B"], "schema.columns"),
    ({"normalize_columns": "lower_strip"}, "csv_points", None, "안 읽는다"),
])
def test_problems_names_a_malformed_declaration(contract, kind, schema, needle):
    e = {"kind": kind, "contract": contract, **({"schema": {"columns": schema}} if schema else {})}
    got = extract.problems("t", e)
    assert any(needle in m for m in got), got


def test_a_valid_declaration_has_no_problem_and_the_schema_columns_are_checked_after_normalizing():
    e = {"kind": "csv_table", "contract": CON, "schema": {"columns": ["DCLR_YR", "CLMTY_EMD_NM"]}}
    assert extract.problems("t", e) == [] and extract.declared(e)
    assert extract.problems("t", {"kind": "csv_table", "contract": {"encoding": "utf-8"}}) == [] and not extract.declared({"contract": {}})


def test_the_ledger_check_turns_a_bad_declaration_into_a_fail():
    e = {"kind": "csv_table", "what": "x", "scope": "jngj-dongmyeong", "updated": "2026-11-05", "stem": "t", "ext": ["csv"], "feeds": [], "schema": {"columns": ["A"]},
         "contract": {"filter": {"column": "typo", "equals": "x"}}}
    msgs = [i.msg if hasattr(i, "msg") else str(i) for i in ledger_check.check_entry("t", e) if i.level == "FAIL"]
    assert any("filter.column" in m for m in msgs), msgs


# ── ⑤ 회귀 없음 · 어휘 ──
def test_without_the_keys_the_old_path_is_untouched(tmp_path):
    c = _ctx(tmp_path, {"a.csv": UPPER}, contract={"encoding": "utf-8"})
    rec = read_csv_table(c)
    assert rec["status"] == "OK" and rec["features"] == 3 and "extract" not in rec, "키가 없으면 전부 읽는다 — 종전 그대로"
    assert rec["columns"] == ["DCLR_YR", "CLMTY_EMD_NM", "NOTE"], "정규화도 안 한다"


def test_the_vocabulary_names_the_reading_module():
    from firelane import ledger
    assert ledger.CONTRACT_KEYS["normalize_columns"][1] == ledger.CONTRACT_KEYS["filter"][1] == "firelane.read.extract"


def test_only_the_extract_entries_use_the_keys_and_every_declaration_is_well_formed():
    """대장의 `scope` 를 바꾸지 않는다 — 추출이 선 뒤의 사람 판단이다. 이 키를 쓰는 항목은 전국 원본에서 거르는 다섯(nfa_ems · nfa_dispatch_119 · nfa_fire_incident · nfa_rescue · nfa_target_building)이고 모양이 맞아야 한다."""
    from firelane import ledger
    ds = ledger.load_sources()["datasets"]
    assert sorted(k for k, e in ds.items() if extract.declared(e)) == ["nfa_dispatch_119", "nfa_ems", "nfa_fire_incident", "nfa_rescue", "nfa_target_building"]
    assert all(extract.problems(k, e) == [] for k, e in ds.items())


def test_read_extracted_is_the_entry_both_table_kinds_share(tmp_path):
    """두 표 갈래(`csv_table` · `csv_table_multi`)가 **같은 함수**로 간다 — 갈래 이름이 달라도 결과가 같다."""
    one = read_csv_table(_ctx(_sub(tmp_path, "one"), {"a.csv": UPPER, "b.csv": LOWER}))
    two = extract.read_extracted(_ctx(_sub(tmp_path, "two"), {"a.csv": UPPER, "b.csv": LOWER}, kind="csv_table_multi"))
    assert one["extract"]["rows_out"] == two["extract"]["rows_out"] == 4 and one["columns"] == two["columns"]


def test_the_single_pick_rule_does_not_fire_when_the_extraction_reads_every_file():
    """`csv_table` 은 원래 하나만 읽어서 files 가 여럿이면 `primary` 를 요구한다 — 추출 선언이 있으면 **전부 읽으므로** 그 요구가 틀린 경보다."""
    base = {"kind": "csv_table", "what": "x", "scope": "jngj-dongmyeong", "updated": "2026-11-05", "stem": "t", "ext": ["csv"], "feeds": [],
            "schema": {"columns": ["A"]}, "encoding": "utf-8", "files": ["a_2023.csv", "b_2024.csv"]}
    plain = [i.msg for i in ledger_check.check_entry("t", base) if i.level == "FAIL" and "하나만 읽는데" in i.msg]
    ext = [i.msg for i in ledger_check.check_entry("t", {**base, "contract": {"normalize_columns": "lower_strip"}}) if i.level == "FAIL" and "하나만 읽는데" in i.msg]
    assert plain and not ext

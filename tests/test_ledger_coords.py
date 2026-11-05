"""
test_ledger_coords.py — 대장의 `coords:` · `none:` · `schema.profile` 과 그 강제자.  (PLAN #193 · DECISIONS §634)

── 이 시험이 무는 것 ──────────────────────────────────────────
① `ledger.coords(key, 역할)` 접근자 — 칸 이름을 대장에서 받고, 선언이 없거나 `not_for` 용도면 **죽는다**(코드가 제 판단으로 고르는 길이 없다).
② `coords_problems` — 좌표로 읽히는 칸이 있는 표가 `coords:` 를 안 들면 거부, 「좌표가 없다」(`none`)는 사유와 함께 받는다.
③ `profile_problems` — 실물 방언(빈 셀 · **공백 문자열** · 센티넬)이 사람의 `none:` 선언보다 넓으면 거부. 공백 문자열은 선언이 **필수**다(`notna()` 사고).
④ `valueprofile` — 집계만 적고(표본값 없음) 원문의 주석 · 다른 칸을 안 건드린다. ⑤ `ingest.build` 가 선언 없는 좌표 표를 읽기 전에 거부한다.

밖    **프로필이 실물과 같은가**는 레이크가 필요해 `python -m firelane.valueprofile --check` 의 몫이다.
"""
from __future__ import annotations

import pandas as pd
import pytest
import yaml

from firelane import ingest, ledger, valueprofile

COLS = ["DCLR_YR", "LOT", "LAT", "ARVL"]


def _e(**kw) -> dict:
    return {"kind": "csv_table", "schema": {"columns": COLS}, **kw}


# ── ① 접근자 ──
def test_the_accessor_returns_the_columns_the_ledger_names():
    assert ledger.coords("nfa_dispatch_119", "site") == ("LOT", "LAT")
    assert ledger.coords("nfa_dispatch_119", "reporter") == ("DCLR_PSTN_LOT", "DCLR_PSTN_LAT")
    assert ledger.coords("nfa_rescue", "reporter") == ("DCLR_PSTN_LOT", "DCLR_PSTN_LAT")


def test_the_accessor_dies_instead_of_guessing():
    with pytest.raises(KeyError):
        ledger.coords("nfa_dispatch_119", "unconfirmed")        # 그 역할이 없다
    with pytest.raises(KeyError):
        ledger.coords("nfa_fire_incident", "site")              # 좌표 없음 선언 — 칸을 내주지 않는다
    with pytest.raises(KeyError):
        ledger.coords("nfa_fire_incident", "none")
    with pytest.raises(KeyError):
        ledger.coords("없는원천", "site")


def test_a_use_the_ledger_forbids_is_refused():
    with pytest.raises(ValueError, match="not_for"):
        ledger.coords("nfa_dispatch_119", "reporter", use="지도 표출")
    assert ledger.coords("nfa_dispatch_119", "reporter", use="통계") == ("DCLR_PSTN_LOT", "DCLR_PSTN_LAT")


# ── ② 선언의 모양과 거부 ──
def test_a_table_with_coordinate_looking_columns_needs_a_declaration():
    assert any("coords:" in m for m in ledger.coords_problems("t", _e()))
    assert ledger.coords_problems("t", {"kind": "csv_table", "schema": {"columns": ["A", "B"]}}) == []     # 좌표처럼 안 생기면 안 묻는다
    assert ledger.coords_problems("t", {"kind": "csv_docs", "schema": {"columns": COLS}}) == []            # 좌표를 안 읽는 갈래는 안 묻는다


def test_a_point_source_must_say_which_columns_it_reads():
    """점 자료의 읽을 칸은 `coords.site` 가 말한다(종전 `x_col` · `y_col` 을 흡수 — DECISIONS §641). 없으면 거부한다."""
    site = {"x": "LOT", "y": "LAT", "crs": 4326, "means": "설치 위치"}
    pt = {"kind": "csv_points", "schema": {"columns": COLS}}
    assert any("coords.site" in m for m in ledger.coords_problems("t", pt))
    assert any("coords.site" in m for m in ledger.coords_problems("t", {**pt, "coords": {"reporter": site}}))
    assert any("coords.site" in m for m in ledger.coords_problems("t", {**pt, "coords": {"none": "사유"}})), "점 자료는 좌표 없음이 못 된다"
    assert ledger.coords_problems("t", {**pt, "coords": {"site": site}}) == []
    assert ledger.coords_in({"coords": {"site": site}}) == ("LOT", "LAT")
    with pytest.raises(KeyError):
        ledger.coords_in({"coords": {"reporter": site}})
    assert ledger.point_cols({**pt, "coords": {"site": site}}) == ("LOT", "LAT")
    assert ledger.point_cols(pt) == (None, None) and ledger.point_cols(_e(coords={"site": site})) == (None, None), "표 갈래 · 선언 없음은 죽지 않고 (None, None)"


def test_every_real_point_source_declares_site_and_the_old_columns_are_gone():
    led = ledger.load()["datasets"]
    pts = {k: e for k, e in led.items() if e.get("kind") in ledger.POINT_KINDS}
    assert len(pts) >= 9
    assert all("x_col" not in e and "y_col" not in e for e in led.values()), "정본이 둘이다 — x_col/y_col 이 남았다"
    assert all(ledger.point_cols(e)[0] for e in pts.values())
    assert ledger.coords_in(led["fire_station"]) == ("Y좌표", "X좌표"), "컬럼명이 뒤집힌 원천이 그대로 읽힌다"


def test_no_coordinates_is_a_declaration_with_a_reason():
    assert ledger.coords_problems("t", _e(coords={"none": "LOT 은 지번이다"})) == []
    assert ledger.coords_problems("t", _e(coords={"none": " "}))
    assert ledger.coords_problems("t", _e(coords={"none": "사유", "site": {}}))


def test_a_malformed_declaration_is_named():
    ok = {"x": "LOT", "y": "LAT", "crs": 4326, "means": "재해 위치"}
    assert ledger.coords_problems("t", _e(coords={"site": ok})) == []
    assert ledger.coords_problems("t", _e(coords={"home": ok}))                                     # 모르는 역할
    assert ledger.coords_problems("t", _e(coords={"site": {**ok, "means": "신고자 휴대폰 위치"}}))      # 역할과 뜻이 안 맞는다
    assert ledger.coords_problems("t", _e(coords={"site": {**ok, "x": "없는칸"}}))                  # schema.columns 에 없다
    assert ledger.coords_problems("t", _e(coords={"site": {"x": "LOT"}}))                           # 칸이 모자란다


def test_the_real_ledger_has_no_coordinate_or_profile_problem():
    led = ledger.load()["datasets"]
    bad = {k: ledger.coords_problems(k, e) + ledger.profile_problems(e) for k, e in led.items()}
    assert not {k: v for k, v in bad.items() if v}
    assert sum(1 for e in led.values() if e.get("kind") in ledger.TABLE_KINDS and ledger.coord_columns(e)) >= 6, "좌표 표 판별이 죽었다"


# ── ③ 프로필 ↔ none ──
def _pf(**cols) -> dict:
    return {"schema": {"columns": COLS, "profile": {"n": 10, "cols": cols}}}


def test_a_blank_string_column_must_be_declared():
    assert ledger.profile_problems(_e(**_pf(ARVL={"empty": 0, "ws": 3})))
    ok = _e(none={"ARVL": {"forms": ["공백"]}}, **_pf(ARVL={"empty": 0, "ws": 3}))
    assert ledger.profile_problems(ok) == []


def test_none_forms_reads_exactly_what_the_ledger_declares():
    assert ledger.none_forms(_e(none={"ARVL": {"forms": ["빈 셀", "0.0"]}}), "ARVL") == {"빈 셀", "0.0"}
    assert ledger.none_forms(_e(), "ARVL") == set() and ledger.none_forms({}, "ARVL") == set()


def test_a_declared_column_must_cover_what_was_measured():
    e = _e(none={"ARVL": {"forms": ["빈 셀"]}}, **_pf(ARVL={"empty": 2, "ws": 5}))
    assert any("공백" in m for m in ledger.profile_problems(e))
    wide = _e(none={"ARVL": {"forms": ["빈 셀", "공백", "미상"]}}, **_pf(ARVL={"empty": 2, "ws": 5}))
    assert ledger.profile_problems(wide) == [], "선언이 더 넓은 것은 괜찮다(부분집합이 규칙이다)"


def test_a_sentinel_in_a_declared_coordinate_column_must_be_declared():
    e = _e(coords={"site": {"x": "LOT", "y": "LAT", "crs": 4326, "means": "재해 위치"}},
           **_pf(LOT={"empty": 0, "ws": 0, "sentinel": {"0.0": 4}}))
    assert any("0.0" in m for m in ledger.profile_problems(e))
    e["none"] = {"LOT": {"forms": ["0.0"]}}
    assert ledger.profile_problems(e) == []


def test_the_year_dialect_is_visible_in_the_real_profile():
    """2022 · 2023 은 빈 셀, 2024 · 2025 는 공백 문자열 — 한 칸 안에서 연도로 갈린다(§631-3)."""
    by = ledger.load()["datasets"]["nfa_dispatch_119"]["schema"]["profile"]["cols"]["HSPTL_ARVL_DT"]["by"]
    assert set(by["2022"]) == {"empty"} and set(by["2023"]) == {"empty"}
    assert set(by["2024"]) == {"ws"} and set(by["2025"]) == {"ws"}


# ── ④ valueprofile ──
def _df() -> pd.DataFrame:
    return pd.DataFrame({
        "DCLR_YR": ["2022", "2022", "2024", "2024"], "LOT": ["127.1", "0.0", "", "127.2"], "LAT": ["35.1", "0.0", "", "35.2"],
        "ARVL": ["", "SAMPLEVAL", " ", " "], "NOTE": ["a", "b", "미상", "d"], "CLEAN": ["1", "2", "3", "4"]})


def test_measure_counts_every_dialect_and_keeps_no_sample_value():
    pf = valueprofile.measure(_df(), {"ARVL": {"by": "DCLR_YR"}})
    c = pf["cols"]
    assert pf["n"] == 4 and "CLEAN" not in c and "DCLR_YR" not in c, "없음 꼴이 없는 칸은 안 적는다"
    assert c["LOT"]["sentinel"] == {"0.0": 1} and c["LOT"]["empty"] == 1 and c["LOT"]["range"] == [127.1, 127.2]
    assert c["ARVL"]["empty"] == 1 and c["ARVL"]["ws"] == 2 and c["ARVL"]["by"] == {"2022": {"empty": 1}, "2024": {"ws": 2}}
    assert c["NOTE"]["text_none"] == {"미상": 1}
    assert "SAMPLEVAL" not in str(c) and "127.1" not in str(c["ARVL"]), "표본값이 샜다"


def test_fmt_writes_aggregates_only_in_a_form_yaml_reads_back():
    pf = {"n": 2, "cols": {"A": {"empty": 1, "ws": 0, "range": [1.5, 2.5], "by": {"2022": {"empty": 1}}}}}
    got = yaml.safe_load("schema:\n" + valueprofile.fmt(pf))["schema"]["profile"]
    assert got == pf and valueprofile.fmt({"n": 0, "cols": {}}).endswith("cols: {}\n")


def test_splice_replaces_the_profile_and_touches_nothing_else():
    src = ("datasets:\n  t:\n    kind: csv_table\n    # 사람의 주석\n    schema:                       # AUTO\n      columns: ['A']\n"
           "      encoding_seen: 'utf-8'\n  u:\n    kind: x\n")
    pf = {"n": 3, "cols": {"A": {"empty": 1, "ws": 0}}}
    once = valueprofile.splice(src, "t", pf)
    twice = valueprofile.splice(once, "t", {"n": 3, "cols": {"A": {"empty": 2, "ws": 0}}})
    assert "# 사람의 주석" in twice and "  u:\n    kind: x\n" in twice
    got = yaml.safe_load(twice)["datasets"]["t"]["schema"]
    assert got["profile"] == {"n": 3, "cols": {"A": {"empty": 2, "ws": 0}}} and got["columns"] == ["A"]
    assert twice.count("profile:") == 1, "두 번 적으면 갈아 끼워야 한다"
    assert yaml.safe_load(once)["datasets"]["t"]["schema"]["profile"] == pf, "적은 것이 읽어서 같아야 한다"
    assert yaml.safe_load(valueprofile.splice(src, "t", {"n": 0, "cols": {}}))["datasets"]["t"]["schema"]["profile"]["cols"] == {}


# ── ⑤ ingest 거부 ──
def test_ingest_refuses_a_coordinate_table_without_a_declaration(tmp_path):
    with pytest.raises(ValueError, match="좌표 선언"):
        ingest.build("t", _e(stem="t", ext=["csv"]), tmp_path)


def test_the_rescue_coordinates_are_the_reported_position_by_the_source_guide():
    """★ 원천 활용가이드(column_info 51칸 전수)가 이 칸을 「신고위치」라 부른다(설명 「신고 내용의 좌표」는 부정확하다 — 근거는 칸 이름 + dispatch 실측 교차 · DECISIONS §642). 사고 위치로 안 쓴다."""
    r = ledger.load()["datasets"]["nfa_rescue"]
    c = ledger.coords_decl(r)
    assert set(c) == {"reporter"} and c["reporter"]["means"] == "신고 위치", "unconfirmed 는 지워졌다"
    for use in ("위치 분석", "거리 계산"):
        with pytest.raises(ValueError, match="not_for"):
            ledger.coords("nfa_rescue", "reporter", use=use)
    assert ledger.coords("nfa_rescue", "reporter", use="지도 표출") == ("DCLR_PSTN_LOT", "DCLR_PSTN_LAT"), "발행은 「신고위치」 점으로 보인다"

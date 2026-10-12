#!/usr/bin/env python3
"""
test_text_table.py — **머리 줄이 없는 표**를 읽는 갈래. (§497)

── 왜 생겼나 ───────────────────────────────────────────────────
`read_text_table` 은 내비게이션용DB(건물 33열 · 지번 20열)와 상세주소를
읽는다. 그 파일들은 **머리 줄이 없다** — 컬럼명이 파일에 없고 제공처
활용가이드에만 있다. 그래서 이 갈래가 혼자 지고 있는 규율이 셋이다 —

    ① **첫 행이 데이터다.** `csv` 로 읽으면 컬럼명으로 먹고 1행을 잃는다
    ② **이름을 지어내지 않는다.** 대장 `contract.columns` 가 없으면 `c00`…
    ③ **법정동코드로 자른다.** 동 이름으로 자르면 2,701행이 나오고 그중
       623 이 **목포시** 동명동이다(전남+광주 통합 파일)

셋 다 **조용히 틀리는** 꼴이다. 1행을 잃어도, 이름이 c00 이어도, 목포가
섞여도 건수는 그럴듯하다. `tools/srccov.py` 가 이 함수를 「시험이 이름으로도
안 부른다」로 셌다(§493 — 입출력 부류라 물리지도 않았다).

IN    없음 (합성 `|` 텍스트 · zip)
OUT   없음 (검사 · 산출은 tmp 로 간다)
PARAM 없음
밖    **구분자 기본값은 안 정한다** — 정본은 `ledger.delimiter_of` 하나이고
      (§284-4) 여기서는 그것이 주는 값을 쓴다. **열 이름이 옳은가도 안
      본다** — 활용가이드 대조는 `DECISIONS §181-1` 이 든다.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from firelane.read.ctx import Ctx
from firelane.read.delimited import read_text_table

#: 법정동코드가 다른 세 줄. 셋째는 **목포시** 동명동이다 — 이름으로 자르면 섞인다.
BODY = ("1221010800|동명로|6.0\n"
        "1221010800|충장로|12.5\n"
        "2711010100|목포동명로|4.0\n")


def _ctx(tmp_path: Path, e: dict, src: Path | None = None) -> Ctx:
    """`kind: text_table` 한 벌. 구분자는 그 kind 에서 **유도된다**."""
    p = src if src is not None else tmp_path / "t.txt"
    if src is None:
        p.write_bytes(BODY.encode("cp949"))
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    return Ctx(key="navi_build", e={"kind": "text_table", **e}, src=p, hits=[p],
               crs="EPSG:5186", tmp=tmp_path, out=out,
               rec={"key": "navi_build"}, save=lambda *a, **k: {})


# ── ① 첫 행이 데이터다 ───────────────────────────────────────
def test_the_first_row_is_data_not_a_header(tmp_path):
    """★ 본체. 세 줄이면 **세 행**이다 — `csv` 로 읽으면 둘이 된다."""
    got = read_text_table(_ctx(tmp_path, {}))
    assert got["features"] == 3, f"{got['features']}행 — 첫 줄을 머리로 먹었다"
    assert got["status"] == "OK" and got["outputs"] == ["navi_build.csv"]


# ── ② 이름을 지어내지 않는다 ─────────────────────────────────
def test_without_a_declaration_the_columns_are_numbered(tmp_path):
    """★ `c00` · `c01` … 이다. **뜻을 지어내지 않는다** — 뜻은 대장이 적는다."""
    assert read_text_table(_ctx(tmp_path, {}))["columns"] == ["c00", "c01", "c02"]


def test_the_declared_column_names_are_used_as_given(tmp_path):
    """대장이 적으면 그 이름이 그대로 붙는다."""
    e = {"contract": {"columns": ["법정동코드", "도로명", "폭"]}}
    assert read_text_table(_ctx(tmp_path, e))["columns"] == \
        ["법정동코드", "도로명", "폭"]


def test_a_column_count_mismatch_dies_instead_of_shifting(tmp_path):
    """★ 선언이 실물과 다르면 **죽는다.** 붙이면 이름과 값이 엇갈린다."""
    e = {"contract": {"columns": ["법정동코드", "도로명"]}}
    with pytest.raises(ValueError, match="2개인데 실물은 3열"):
        read_text_table(_ctx(tmp_path, e))


# ── ③ 법정동코드로 자른다 ────────────────────────────────────
def test_select_cuts_by_the_declared_code_prefix(tmp_path):
    """★ 코드 접두로 자른다 — 목포시 줄이 **빠진다.**"""
    e = {"select": {"col": 0, "prefix": "1221010800"}}
    got = read_text_table(_ctx(tmp_path, e))
    assert got["features"] == 2, "목포 줄이 남았거나 광주 줄이 빠졌다"


def test_select_can_also_match_the_whole_code(tmp_path):
    """`equals` 갈래 — 접두가 아니라 **그 코드 하나**다."""
    e = {"select": {"col": 0, "equals": "2711010100"}}
    assert read_text_table(_ctx(tmp_path, e))["features"] == 1


def test_a_cut_that_keeps_nothing_is_a_failure_not_a_green(tmp_path):
    """★ **0건을 조용히 통과시키지 않는다.**

    법정동코드 개편(2026-07-01 · 광주 29→12)처럼 코드 체계가 바뀌면 선언이
    맞는데도 0건이 나온다. 그것이 초록으로 지나가면 다음 단계가 **빈 표**를
    쓴다. 그래서 읽은 행 수까지 말하며 죽는다.
    """
    e = {"select": {"col": 0, "prefix": "9999999999"}}
    with pytest.raises(ValueError, match="0건이다"):
        read_text_table(_ctx(tmp_path, e))
    # ★ 죽을 때 **무엇을 확인해야 하는지**를 말한다 — 읽은 행 수와 개편 날짜
    with pytest.raises(ValueError, match="법정동코드 개편"):
        read_text_table(_ctx(tmp_path, e))


def test_a_select_column_outside_the_file_dies(tmp_path):
    """★ 없는 열로 자르려 하면 죽는다 — 조용히 전건을 남기지 않는다."""
    with pytest.raises(ValueError, match=r"select\.col=9 인데 실물은 3열"):
        read_text_table(_ctx(tmp_path, {"select": {"col": 9, "prefix": "1"}}))


def test_a_select_without_a_rule_dies(tmp_path):
    """`select` 를 적고 **무엇으로 자를지** 안 적으면 죽는다."""
    with pytest.raises(ValueError, match="prefix 도 equals 도 없다"):
        read_text_table(_ctx(tmp_path, {"select": {"col": 0}}))


# ── zip 안 한 파일만 고른다 ──────────────────────────────────
def _zip(tmp_path: Path, names: list[str]) -> Path:
    zp = tmp_path / "pack.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for n in names:
            z.writestr(n, BODY.encode("cp949"))
    return zp


def test_inner_contains_picks_exactly_one_member(tmp_path):
    """전국 전체분이 시도별로 나뉘어 온다 — 하나만 읽는다(전부 읽으면 터진다)."""
    zp = _zip(tmp_path, ["adrdc_gwangju.txt", "adrdc_seoul.txt"])
    got = read_text_table(_ctx(tmp_path, {"inner_contains": "gwangju"}, src=zp))
    assert got["features"] == 3


def test_an_ambiguous_inner_match_dies_with_the_candidates(tmp_path):
    """★ 둘에 걸리면 **죽고 후보를 말한다** — 첫 것을 집으면 조용히 서울을 읽는다."""
    zp = _zip(tmp_path, ["adrdc_gwangju.txt", "adrdc_seoul.txt"])
    with pytest.raises(ValueError, match="2개에 걸린다"):
        read_text_table(_ctx(tmp_path, {"inner_contains": "adrdc"}, src=zp))


def test_a_missing_inner_member_dies(tmp_path):
    """zip 안에 그 이름이 없으면 죽는다 — 빈 표를 내지 않는다."""
    zp = _zip(tmp_path, ["adrdc_gwangju.txt"])
    with pytest.raises(ValueError, match="zip 안에"):
        read_text_table(_ctx(tmp_path, {"inner_contains": "없는것"}, src=zp))


# ── 산출물 ───────────────────────────────────────────────────
def test_the_written_csv_carries_a_bom_and_the_lineage_says_what_it_made(tmp_path):
    """★ `utf-8-sig` 로 쓴다 — 엑셀로 여는 사람이 있고, 그 BOM 이 그 약속이다.

    그리고 계보 조각이 **열 이름과 건수**를 같이 든다 — 그것이 다음 단계가
    읽는 선언이다.
    """
    c = _ctx(tmp_path, {})
    got = read_text_table(c)
    p = c.out / "navi_build.csv"
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "BOM 이 없다"
    assert raw.decode("utf-8-sig").splitlines()[0] == "c00,c01,c02"
    assert got["columns"] == ["c00", "c01", "c02"] and got["geom"] == []

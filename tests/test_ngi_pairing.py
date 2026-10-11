#!/usr/bin/env python3
"""
test_ngi_pairing.py — **.ngi 와 .nda 가 레코드 번호로 짝지어지는가.** (§495)

── 왜 생겼나 ───────────────────────────────────────────────────
`src/firelane/ngi.py` 의 머리말이 이 모듈의 존재 이유를 한 문장으로 적는다 —

    ★ 레코드 순서로 짝짓는다. 어느 한쪽에서 파싱 실패로 레코드를 건너뛰면
      그 뒤가 전부 밀린다. 그래서 실패한 레코드도 None 으로 자리를 지킨다.
      기존 코드는 except 에서 continue 라 조용히 밀렸다.

그 「조용히 밀렸다」가 무슨 사고인지가 중요하다 — **엉뚱한 도로에 엉뚱한
폭**이 들어가고 그 수가 그대로 폭 판정에 쓰인다. 밀린 폭은 범위 안의
그럴듯한 수라서 **어떤 검사도 안 운다.**

그런데 `tools/srccov.py` 가 `parse_ngi` · `parse_nda` 를 「시험이 이름으로도
안 부른다」로 셌다(§493). **이 모듈이 막으려고 생긴 그 사고를 미는 자리가
없었다** — 합친 자(`read_ngi`)만 이름이 불렸고, 자리를 지키는 쪽은
그 둘이다.

IN    없음 (합성 NGI/NDA 를 임시 폴더에 쓴다)
OUT   없음 (검사)
PARAM 없음
밖    **실물 도엽을 안 읽는다.** 3,102 파일은 레이크에 있고 CI 에 없다 —
      그리고 여기가 드는 것은 「형식을 읽는 꼴」이라 합성으로 충분하다.
      실물 쪽은 `firelane.ngii1k` 가 들고, 그 짝 불일치는 `read_ngi` 가
      **속성을 생략하고 소리 내는 것**으로 막는다(아래 ④가 그것을 든다).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from firelane.ngi import layer_index, parse_nda, parse_ngi, read_ngi

#: ★ 둘째 레코드의 좌표가 **깨진** 도엽. 그 한 건이 이 파일의 과녁이다.
NGI = """<LAYER_START>
$LAYER_NAME
"A0020000"
<DATA>
$RECORD 1
LINESTRING
2
192740.1 283600.2
192750.1 283600.2
$RECORD 2
LINESTRING
2
192750.1 283600.2
깨진좌표
$RECORD 3
POINT
192760.0 283601.0
<LAYER_END>
<LAYER_START>
$LAYER_NAME
"A9999999"
<LAYER_END>
"""

#: 값에 **쉼표가 든 문자열**이 있다. `split(",")` 로 읽으면 칸이 밀린다.
NDA = """<LAYER_START>
$LAYER_NAME
"A0020000"
$ASPATIAL_FIELD_DEF
ATTRIB("UFID",STRING,34,0,TRUE)
ATTRIB("도로명",STRING,40,0,TRUE)
ATTRIB("도로폭",NUMERIC,9,3,TRUE)
<DATA>
$RECORD 1
1, "동명로25번길, 1길", 6.0
$RECORD 2
2, "충장로", 12.5
$RECORD 3
3, "제봉로", 8.0
<LAYER_END>
"""


@pytest.fixture
def sheet(tmp_path: Path) -> Path:
    """cp949 로 쓴 짝 한 벌. 실물이 그 인코딩이다."""
    (tmp_path / "t.ngi").write_bytes(NGI.encode("cp949"))
    (tmp_path / "t.nda").write_bytes(NDA.encode("cp949"))
    return tmp_path / "t.ngi"


# ── ① 자리를 지키는가 ─────────────────────────────────────────
def test_a_broken_record_keeps_its_slot_as_none(sheet: Path):
    """★ 본체. 깨진 레코드가 **None 으로 자리를 지킨다.**

    건너뛰면 길이가 3 → 2 가 되고, 그 뒤의 짝이 **한 칸 밀린다.**
    """
    got = parse_ngi(sheet)["A0020000"]
    assert len(got) == 3, f"레코드 수가 {len(got)} — 깨진 건을 건너뛰었다"
    assert got[1] is None, "깨진 레코드가 None 이 아니다"
    assert [None if g is None else g.geom_type for g in got] == \
        ["LineString", None, "Point"]


def test_the_attribute_side_keeps_its_slots_too(sheet: Path):
    """속성 쪽도 같은 규율이다 — 한쪽만 지키면 짝이 밀린다."""
    rows = parse_nda(sheet.with_suffix(".nda"))["A0020000"]["rows"]
    assert len(rows) == 3
    assert [r["UFID"] for r in rows] == ["1", "2", "3"]


def test_the_third_road_gets_its_own_width_not_the_second_ones(sheet: Path):
    """★ **이 모듈이 막으려고 생긴 그 사고**를 한 줄로 든다.

    둘째 기하가 깨졌으므로 셋째 기하에는 **셋째** 속성이 붙어야 한다.
    밀리면 `제봉로`(8.0m) 가 `충장로`(12.5m) 의 폭을 받고, 12.5 는
    범위 안의 그럴듯한 수라 **어떤 검사도 안 운다.**
    """
    recs = read_ngi(sheet)["A0020000"]["records"]
    assert len(recs) == 2, "깨진 건을 뺀 수가 아니다"
    assert recs[0]["도로명"] == "동명로25번길, 1길"
    assert recs[1]["도로명"] == "제봉로" and recs[1]["도로폭"] == "8.0", (
        f"셋째 기하에 {recs[1].get('도로명')!r} 가 붙었다 — 속성이 밀렸다")


# ── ② 쉼표 든 값 ─────────────────────────────────────────────
def test_a_comma_inside_a_quoted_name_does_not_shift_the_columns(sheet: Path):
    """★ 값은 CSV 다. `split(",")` 로 읽으면 도로명이 둘로 쪼개져 폭이 밀린다."""
    rows = parse_nda(sheet.with_suffix(".nda"))["A0020000"]["rows"]
    assert rows[0]["도로명"] == "동명로25번길, 1길", rows[0]
    assert rows[0]["도로폭"] == "6.0", "쉼표 때문에 폭 칸이 밀렸다"


def test_the_field_names_come_with_their_types(sheet: Path):
    """형(型)까지 낸다 — `NUMERIC` 인지 `STRING` 인지가 폭 채택의 전제다."""
    f = parse_nda(sheet.with_suffix(".nda"))["A0020000"]["fields"]
    assert f == [("UFID", "STRING"), ("도로명", "STRING"), ("도로폭", "NUMERIC")]


# ── ③ 칸 수가 안 맞으면 **죽는다** ───────────────────────────
def test_a_value_count_mismatch_dies_instead_of_truncating(tmp_path: Path):
    """★ 머리말의 선택을 못박는다 — 「죽는 편이 낫다」.

    `zip(..., strict=True)` 가 그 선택이다. 조용히 자르면 **마지막 칸이
    사라진** 레코드가 생기고, 그 칸이 도로폭이면 폭이 통째로 빈다.
    """
    bad = NDA.replace('3, "제봉로", 8.0', '3, "제봉로", 8.0, 군더더기')
    p = tmp_path / "t.nda"
    p.write_bytes(bad.encode("cp949"))
    with pytest.raises(ValueError):
        parse_nda(p)


# ── ④ 짝이 안 맞으면 속성을 **붙이지 않는다** ────────────────
def test_a_length_mismatch_drops_the_attributes_and_says_so(tmp_path: Path,
                                                            capsys):
    """★ 밀린 채로 붙이는 것보다 **없는 것**이 낫다 — 그리고 소리를 낸다.

    조용히 생략하면 「폭이 원래 없는 도엽」과 구별되지 않는다.
    """
    (tmp_path / "t.ngi").write_bytes(NGI.encode("cp949"))
    short = NDA.replace('$RECORD 3\n3, "제봉로", 8.0\n', "")
    (tmp_path / "t.nda").write_bytes(short.encode("cp949"))
    out = read_ngi(tmp_path / "t.ngi")["A0020000"]
    assert out["has_attr"] is False, "짝이 안 맞는데 속성을 붙였다"
    assert all("도로폭" not in r for r in out["records"])
    assert "불일치" in capsys.readouterr().out, "조용히 생략했다"


def test_without_an_nda_the_geometry_still_reads(tmp_path: Path):
    """.nda 가 없는 도엽도 읽힌다 — 기하만 내고 속성은 빈다."""
    (tmp_path / "t.ngi").write_bytes(NGI.encode("cp949"))
    out = read_ngi(tmp_path / "t.ngi")["A0020000"]
    assert out["n_geom"] == 3 and out["n_geom_failed"] == 1
    assert len(out["records"]) == 2 and out["has_attr"] is False
    assert out["fields"] == []


# ── ⑤ 레이어 고르기 · 빈 레이어 ──────────────────────────────
def test_a_layer_without_data_is_an_empty_list_not_a_missing_key(sheet: Path):
    """★ 빈 레이어도 **키를 낸다** — 없으면 부르는 쪽이 KeyError 로 죽는다."""
    got = parse_ngi(sheet)
    assert got["A9999999"] == [], got.get("A9999999")


def test_want_filters_layers_without_parsing_the_rest(sheet: Path):
    """`want` 를 주면 그 레이어만 낸다 — 도엽 3,102 을 다 파싱하면 몇 분이다."""
    assert sorted(parse_ngi(sheet, want={"A0020000"})) == ["A0020000"]
    assert sorted(parse_nda(sheet.with_suffix(".nda"),
                            want={"A9999999"})) == []


def test_the_index_counts_without_building_geometry(sheet: Path):
    """★ 요약은 **건수와 형**만 본다. 깨진 건도 **센다** — 건수는 원본의 사실이다."""
    idx = layer_index(sheet)
    assert idx["A0020000"]["n"] == 3, "요약이 깨진 건을 빼고 셌다"
    assert idx["A0020000"]["geom_type"] == "LINESTRING"
    assert idx["A0020000"]["fields"] == ["UFID", "도로명", "도로폭"]
    assert idx["A9999999"]["n"] == 0 and idx["A9999999"]["geom_type"] is None

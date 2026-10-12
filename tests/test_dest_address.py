#!/usr/bin/env python3
"""
test_dest_address.py — **목적지 색인의 주소 글자를 짓는 꼴.** (§495)

── 왜 생겼나 ───────────────────────────────────────────────────
`tools/srccov.py` 가 `destinations` 의 넷을 「시험이 이름으로도 안 부른다」로
셌다(§493) — `road_addr` · `jibun_by_pk` · `from_civil` · `from_store`.
넷은 **사람이 검색창에 치는 글자**를 만든다. 틀리면 검색이 안 되는데,
안 되는 쪽은 **조용하다**: 색인에 「동구 필문대로 230-0」 이 들어가도 건수는
맞고 좌표도 맞다. 사람이 「230-1」 을 쳐야 비로소 안 나온다.

★ `tests/test_dest_scope.py` 는 **범위**를 든다(동명동 안인가 · 몇 건인가).
  발행물을 읽으므로 레이크·발행 뒤에만 돈다. 여기가 드는 것은 **글자**이고
  합성 표로 든다 — 그래서 CI 에서 돈다.

IN    없음 (합성 DataFrame)
OUT   없음 (검사)
PARAM 없음
밖    **검색 질의 동작은 안 본다** — 초성·부분일치는 `web/navi` 쪽이다.
      **열 번호(c02 · c05 …)가 맞는가도 안 본다** — 그것은 「내비게이션용DB
      활용방법 붙임」과 대조할 일이고 `DECISIONS §181-1` 이 든다. 여기서는
      그 상수를 **이름으로** 쓴다(숫자를 두 벌로 적지 않는다).
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from firelane import destinations as D


def _build(**cols: list[str]) -> pd.DataFrame:
    """건물 표 한 벌. **열 번호는 모듈 상수로 쓴다** — 숫자를 안 적는다."""
    return pd.DataFrame(cols)


# ── ① 도로명주소 ─────────────────────────────────────────────
def test_the_sub_number_is_dropped_when_it_is_zero_or_blank():
    """★ `-0` 을 붙이지 않는다. 붙으면 사람이 치는 글자와 **안 맞는다.**

    실물에서 부번은 `0` 으로 오거나 빈 값으로 온다 — 두 꼴이 **같은 뜻**이고
    한쪽만 거르면 색인에 두 가지 글자가 섞인다.
    """
    d = _build(**{D.B_SIGUNGU: ["동구"] * 3, D.B_ROAD: ["제봉로"] * 3,
                  D.B_UNDER: ["0"] * 3, D.B_MAIN: ["5", "5", "5"],
                  D.B_SUB: ["0", "", "12"]})
    assert D.road_addr(d).tolist() == [
        "동구 제봉로 5", "동구 제봉로 5", "동구 제봉로 5-12"]


def test_underground_gets_its_word_and_only_when_the_flag_is_one():
    """★ `지하` 는 **번호 앞**에 붙는다 — 뒤에 붙으면 주소가 아니다."""
    d = _build(**{D.B_SIGUNGU: ["동구"] * 3, D.B_ROAD: ["중앙로"] * 3,
                  D.B_UNDER: ["1", "0", ""], D.B_MAIN: ["12"] * 3,
                  D.B_SUB: [""] * 3})
    assert D.road_addr(d).tolist() == [
        "동구 중앙로 지하 12", "동구 중앙로 12", "동구 중앙로 12"]


def test_a_missing_cell_does_not_become_the_word_nan():
    """★ 빈 칸이 `nan` 으로 색인에 들어가면 **검색이 그 글자를 찾는다.**"""
    d = _build(**{D.B_SIGUNGU: ["동구"], D.B_ROAD: [None],
                  D.B_UNDER: [None], D.B_MAIN: ["7"], D.B_SUB: [None]})
    got = D.road_addr(d).tolist()[0]
    assert "nan" not in got and "None" not in got, got


# ── ② 지번 ───────────────────────────────────────────────────
def test_one_building_collects_every_lot_without_repeating_one():
    """★ 한 건물에 지번이 여럿이다. 중복은 **한 번만** 적는다."""
    j = pd.DataFrame({
        D.J_EMD: ["동명동"] * 3, D.J_RI: [""] * 3, D.J_SAN: ["0"] * 3,
        D.J_MAIN: ["18"] * 3, D.J_SUB: ["12", "11", "12"],
        D.J_PK: ["A"] * 3})
    assert D.jibun_by_pk(j).to_dict() == {"A": "동명동 18-12 · 동명동 18-11"}


def test_the_mountain_flag_becomes_the_word_in_front_of_the_number():
    """`산521-3` — 산 지번은 **번호 앞**에 글자가 붙는다(뒤면 다른 땅이다)."""
    j = pd.DataFrame({
        D.J_EMD: ["지산동"], D.J_RI: [""], D.J_SAN: ["1"],
        D.J_MAIN: ["521"], D.J_SUB: ["3"], D.J_PK: ["B"]})
    assert D.jibun_by_pk(j).to_dict() == {"B": "지산동 산521-3"}


def test_a_ri_is_inserted_between_the_dong_and_the_number():
    """리가 있으면 읍면동 뒤에 들어간다 — 빠지면 다른 동네의 같은 번지가 된다."""
    j = pd.DataFrame({
        D.J_EMD: ["지산동"], D.J_RI: ["갈전리"], D.J_SAN: ["0"],
        D.J_MAIN: ["3"], D.J_SUB: ["0"], D.J_PK: ["C"]})
    assert D.jibun_by_pk(j).to_dict() == {"C": "지산동 갈전리 3"}


def test_the_keys_are_sorted_so_the_published_file_is_stable():
    """★ 건물관리번호로 **정렬**한다 — 안 하면 발행물이 매 실행 달라진다."""
    j = pd.DataFrame({
        D.J_EMD: ["동명동"] * 3, D.J_RI: [""] * 3, D.J_SAN: ["0"] * 3,
        D.J_MAIN: ["1", "2", "3"], D.J_SUB: ["0"] * 3,
        D.J_PK: ["C", "A", "B"]})
    assert list(D.jibun_by_pk(j).index) == ["A", "B", "C"]


# ── ③ 민원행정기관 · 상가 ────────────────────────────────────
def _civil() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"유형": ["학교", "행정", "학교"],
         "기관명": ["조대부고", "동구청", "동명초"],
         "상세분류": ["고등학교", "구청", "초등학교"],
         "도로명주소": ["동구 필문대로 309", "동구 서남로 1", "동구 동명로 1"]},
        geometry=[Point(126.92, 35.15), Point(126.93, 35.14),
                  Point(126.924, 35.149)], crs=4326)


def test_schools_are_their_own_category_and_the_rest_are_offices():
    """★ 학교만 가른다. 셋째 갈래가 생기면 `SRC_RANK` 정렬 밖으로 나간다."""
    got = D.from_civil(_civil())
    assert got["cat"].tolist() == ["학교", "관공서", "학교"]
    assert got["src"].tolist() == ["civil"] * 3


def test_the_two_sources_publish_exactly_the_declared_columns():
    """★ `COLS` **그대로** 낸다 — `search.ts` 가 여섯을 다 읽고 둘은 필수다.

    (§435 가 「옛 필드만 읽어도 돈다」는 거짓 주장을 지운 자리다.)
    """
    store = gpd.GeoDataFrame(
        {"name": ["가게"], "cat": ["음식"], "sub": ["한식"], "addr": ["동구 1"]},
        geometry=[Point(126.9, 35.1)], crs=4326)
    for got, src in ((D.from_civil(_civil()), "civil"),
                     (D.from_store(store), "store")):
        assert list(got.columns) == D.COLS, list(got.columns)
        assert (got["src"] == src).all()
        assert (got["alt"] == "").all(), "지번 칸은 이 두 원천에 없다"


def test_the_output_is_in_the_web_crs():
    """발행물은 4326 이다 — 미터 좌표가 섞이면 지도가 아프리카로 간다."""
    m = _civil().to_crs(5186)
    assert D.from_civil(m).crs.to_epsg() == 4326


def test_a_civil_file_without_the_declared_columns_dies():
    """★ 칸 이름이 바뀌면 **죽는다.** 조용히 빈 색인을 내지 않는다."""
    bad = _civil().rename(columns={"기관명": "name"})
    with pytest.raises(KeyError):
        D.from_civil(bad)

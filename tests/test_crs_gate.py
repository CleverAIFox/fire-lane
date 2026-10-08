#!/usr/bin/env python3
"""
test_crs_gate.py — **MASTER §18-3 의 「CRS 변경 → ★중단」 관문이 실제로 있는가.**

── 왜 생겼나 (2026-09-28 · DECISIONS §284-2) ───────────────────
그 관문은 **선언만 있고 구현이 없었다.** 서로를 가리키는 고리였다 —

    MASTER §18-3        「CRS 변경 → ★중단」
    contract.py 머리말   「crs: 선언 CRS 와 실물 .prj / set_crs 대조」
    krgis/crs.py        래퍼 셋을 지우며 「contract.py 가 선언과 실물을
                         대조하며」 를 그 근거로 들었다

셋이 서로를 가리키고 **실제로 대조하는 쪽이 없었다.** 게다가 `contract` 의
`crs` 키는 항목 수준 `crs_native` 로 개명된 뒤였고 대장에 0건이었다 —
머리말만 옛 이름을 들고 남아 약속처럼 읽혔다.

★ `krgis/crs.py` 가 그때 이렇게 적었다 — 「아무도 안 부르는 래퍼를 남겨두면
  다음 사람이 "쓰이나 보다" 하고 유지한다」. 옳은 말이었고, 같은 일이
  **약속 쪽에서** 일어났다. 안 지키는 약속을 남겨두면 다음 사람이 「하고
  있나 보다」 하고 안 만든다.

★ 판정을 **순수 함수 둘**로 갈라 둔 이유가 이 파일이다. 레이크 없는 곳에서
  실물 대조는 못 돌리지만 **판정 자체**는 합성 입력으로 물릴 수 있다.
  레이크가 붙은 곳에서 처음 도는 날 시끄러울 것이고, 그것이 목적이다.

IN    firelane.contract_crs(`prj_verdict` · `coord_verdict` · `prj_in`)
OUT   없음 (검사)
PARAM 없음
밖    **실물 raw 는 안 읽는다.** 광주 원본이 실제로 어느 좌표계인지는 레이크가
      붙은 곳에서 `python -m firelane.contract` 가 잰다. 여기가 드는 것은
      「판정식이 맞는 것을 맞다 하고 틀린 것을 틀리다 하는가」 하나다.
"""
from __future__ import annotations

import zipfile

import pytest

from firelane.contract import FAIL, WARN, coord_verdict, prj_in, prj_verdict

#: 동명동 한 점을 각 좌표계로 옮긴 값. `krgis/crs.py` 머리말의 지문표와 같다.
#: ★ 값을 손으로 적지 않는다 — 옮겨 적으면 그것이 낡을 자리다.
#: ★ 2026-10-08 (DECISIONS §433). **적고 있었다.** 같은 수가 `crs.py` 주석 ·
#:   `crs.py::__main__` · 여기 **세 벌**이었다. 정본을 하나 두고 읽는다.
from firelane.krgis.crs import REF_WGS84 as DONGMYEONG_4326


def at(epsg: str) -> tuple[float, float]:
    from pyproj import Transformer
    return Transformer.from_crs("EPSG:4326", epsg, always_xy=True).transform(
        *DONGMYEONG_4326)


def wkt(epsg: str) -> str:
    from pyproj import CRS
    return CRS.from_user_input(epsg).to_wkt()


# ── ① 선언 ↔ .prj ──────────────────────────────────────────────
def test_matching_prj_passes():
    assert prj_verdict("EPSG:5186", wkt("EPSG:5186")) is None


def test_mismatched_prj_fails():
    v = prj_verdict("EPSG:5186", wkt("EPSG:5181"))
    assert v and v[0] == FAIL and "5181" in v[1]


def test_a_missing_prj_is_a_warning_not_a_failure():
    """국내 SHP 는 `.prj` 가 없는 것이 흔하다. 없는 것과 틀린 것은 다르다."""
    v = prj_verdict("EPSG:5186", "")
    assert v and v[0] == WARN


def test_an_unreadable_prj_is_a_warning():
    v = prj_verdict("EPSG:5186", "이건 WKT 가 아니다")
    assert v and v[0] == WARN


def test_no_declaration_means_nothing_to_compare():
    assert prj_verdict("", wkt("EPSG:5186")) is None


def test_the_same_crs_written_differently_still_passes():
    """★ 같은 좌표계를 다른 글로 적은 것을 실패로 내면 매번 오탐한다."""
    from pyproj import CRS
    assert prj_verdict("EPSG:5186",
                       CRS.from_epsg(5186).to_wkt(version="WKT1_GDAL")) is None


# ── ①′ datum 변환만 더 적은 `.prj` ────────────────────────────
#: `vworld_uq153` 의 실물 `.prj` 그대로. **AUTHORITY 가 5174 라고 적고 있다.**
#: ★ 2026-10-08 실측(DECISIONS §433). 투영 변수는 선언과 글자까지 같고 다른 것은
#:   `TOWGS84` 하나뿐인데, 그 항이 `to_epsg()` 를 모든 신뢰도에서 `None` 으로
#:   만들고 `equals()` 를 거짓으로 만들어 **옳은 선언이 실패로 울었다.**
UQ153_PRJ = (
    'PROJCS["Korean 1985 / Modified Central Belt", GEOGCS["Korean 1985", '
    'DATUM["Korean Datum 1985", SPHEROID["Bessel 1841", 6377397.155, 299.1528128, '
    'AUTHORITY["EPSG","7004"]], TOWGS84[-115.8, 474.99, 674.11, 1.16, -2.31, -1.63, 6.43], '
    'AUTHORITY["EPSG","6162"]], PRIMEM["Greenwich", 0.0, AUTHORITY["EPSG","8901"]], '
    'UNIT["degree", 0.017453292519943295], AXIS["Geodetic longitude", EAST], '
    'AXIS["Geodetic latitude", NORTH], AUTHORITY["EPSG","4162"]], '
    'PROJECTION["Transverse_Mercator"], PARAMETER["central_meridian", 127.00289027777775], '
    'PARAMETER["latitude_of_origin", 38.0], PARAMETER["scale_factor", 1.0], '
    'PARAMETER["false_easting", 200000.0], PARAMETER["false_northing", 500000.0], '
    'UNIT["m", 1.0], AXIS["Easting", EAST], AXIS["Northing", NORTH], '
    'AUTHORITY["EPSG","5174"]]'
)


def test_a_prj_that_only_adds_a_datum_shift_is_a_warning_with_the_distance():
    """같은 좌표계 + 명시 7변수 → **경고**다. 그리고 **몇 m 인지 적는다.**

    ★ 실패로 내면 옳은 선언이 운다. 통과로 내면 재투영이 갈려도 조용하다.
      둘 다 틀렸고, 답은 「경고 + 잰 수」다 — `krgis` 의 첫 원칙이 그것이다.
    """
    got = prj_verdict("EPSG:5174", UQ153_PRJ)
    assert got is not None, "7변수를 더 적은 `.prj` 를 조용히 통과시킨다"
    lvl, msg = got
    assert lvl == WARN, f"옳은 선언을 {lvl} 로 낸다 — 관문이 오탐한다: {msg}"
    assert "7변수" in msg and "m" in msg, f"몇 m 인지 안 적는다 — {msg}"


def test_the_same_prj_without_the_shift_passes():
    """★ 대조군. 7변수만 빼면 그냥 통과해야 한다 — 그 항이 유일한 차이다."""
    import re as _re
    bare = _re.sub(r",\s*TOWGS84\[[^\]]*\]", "", UQ153_PRJ)
    assert prj_verdict("EPSG:5174", bare) is None


def test_a_real_mismatch_still_fails_even_with_a_datum_shift():
    """★ **카나리아.** 새 갈래가 진짜 어긋남까지 삼키면 관문이 죽는다."""
    got = prj_verdict("EPSG:5186", UQ153_PRJ)
    assert got is not None and got[0] == FAIL, (
        f"선언 5186 · 실물 5174 인데 {got} 를 낸다 — 관문이 죽었다")


def test_the_shift_tolerance_matches_the_node_tolerance():
    """상한의 **근거가 살아 있는가.** 두 집에 같은 수를 두되 어긋나면 운다.

    ★ `DATUM_SHIFT_TOL_M` 은 「그래프를 못 움직이는 크기」이고 그 정의가
      `seg/params.NODE_TOL`(끝점을 한 노드로 묶는 거리)다. import 로 묶지
      않은 이유는 `contract` 가 판정 상수에 매이면 상수를 고칠 때 관문이
      같이 흔들리기 때문이다 — 대신 여기가 **대조한다.**
    """
    from firelane.contract_crs import DATUM_SHIFT_TOL_M
    from firelane.seg.params import NODE_TOL
    assert DATUM_SHIFT_TOL_M == NODE_TOL, (
        f"상한 {DATUM_SHIFT_TOL_M} 이 `NODE_TOL` {NODE_TOL} 과 갈렸다 — "
        "둘 중 하나를 고쳤으면 사유를 적고 다른 쪽도 고쳐라")


# ── ② 선언 ↔ 좌표 실측 ─────────────────────────────────────────
@pytest.mark.parametrize("epsg", ["EPSG:5186", "EPSG:5187", "EPSG:5179"])
def test_a_coordinate_in_the_declared_crs_passes(epsg):
    assert coord_verdict(epsg, *at(epsg)) is None


def test_a_coordinate_that_is_really_another_crs_fails_with_the_distance():
    """★ 5181 데이터를 5186 이라 선언한 사고. 실측이 잡고 거리를 낸다."""
    v = coord_verdict("EPSG:5186", *at("EPSG:5181"))
    assert v and v[0] == FAIL
    assert "m 어긋난다" in v[1], v[1]


def test_the_bessel_pair_is_reported_as_ambiguous_not_silently_passed():
    """★ 좌표 실측의 **한계**를 시험으로 고정한다.

    `5181`(중부 y+50만) 과 `5174`(보정중부 Bessel) 는 지상 300m 차이라
    광주 bbox 안에 나란히 떨어진다 — 좌표만으로는 못 가른다. 실측으로
    후보 열하나를 전부 재 보았고 **모호한 쌍은 이것 하나뿐이다.**

    못 가르는 것 자체는 결함이 아니다. **못 가르면서 조용히 통과하는 것**이
    결함이다. 그래서 경고를 내고 `.prj` 에게 넘긴다.
    """
    v = coord_verdict("EPSG:5181", *at("EPSG:5174"))
    assert v and v[0] == WARN, f"모호한데 조용히 통과했다 — {v}"
    assert "5174" in v[1] and "못 가른다" in v[1], v[1]


def test_the_prj_check_covers_what_the_probe_cannot():
    """★ 좌표가 못 가른 그 쌍을 `.prj` 는 가른다. 둘이 사각지대를 덮는다."""
    v = prj_verdict("EPSG:5181", wkt("EPSG:5174"))
    assert v and v[0] == FAIL, "좌표도 .prj 도 못 가르면 이 관문의 값이 없다"


def test_an_unambiguous_crs_gives_no_noise():
    """모호 경고가 아무 데서나 울면 사람이 관문을 끈다."""
    for epsg in ("EPSG:5186", "EPSG:5187", "EPSG:5179", "EPSG:4326"):
        assert coord_verdict(epsg, *at(epsg)) is None, f"{epsg} 에서 헛울었다"


def test_a_coordinate_outside_gwangju_is_a_warning():
    """대상 지역 밖은 실패가 아니다 — 전국 파일을 받아 자르는 일이 흔하다."""
    v = coord_verdict("EPSG:5186", 0.0, 0.0)
    assert v and v[0] == WARN


def test_no_declaration_means_no_measurement():
    assert coord_verdict("", *at("EPSG:5186")) is None


# ── ③ .prj 를 실제로 꺼내는가 ──────────────────────────────────
def test_prj_is_read_from_a_zip(tmp_path):
    z = tmp_path / "원본.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("어떤레이어.shp", b"\x00")
        f.writestr("어떤레이어.prj", wkt("EPSG:5186"))
    assert prj_verdict("EPSG:5186", prj_in(z, "어떤레이어.shp")) is None


def test_the_right_prj_is_picked_when_a_zip_holds_several(tmp_path):
    """★ zip 안에 레이어가 여럿이면 **그 레이어의** `.prj` 를 봐야 한다.

    아무 것이나 집으면 옆 레이어의 좌표계로 판정한다 — 틀린 것끼리 맞는다.
    """
    z = tmp_path / "여러개.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("가.prj", wkt("EPSG:5181"))
        f.writestr("나.prj", wkt("EPSG:5186"))
    assert prj_verdict("EPSG:5186", prj_in(z, "나.shp")) is None
    v = prj_verdict("EPSG:5186", prj_in(z, "가.shp"))
    assert v and v[0] == FAIL, "레이어별 .prj 를 안 가린다"


def test_prj_is_read_beside_a_bare_shp(tmp_path):
    (tmp_path / "홀로.prj").write_text(wkt("EPSG:5187"), encoding="utf-8")
    assert prj_in(tmp_path / "홀로.shp").strip()


def test_a_broken_zip_is_not_a_crash(tmp_path):
    bad = tmp_path / "깨진.zip"
    bad.write_text("이건 zip 이 아니다", encoding="utf-8")
    assert prj_in(bad, "무엇.shp") == ""


def test_a_zip_without_any_prj_gives_an_empty_string(tmp_path):
    z = tmp_path / "prj없음.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("레이어.shp", b"\x00")
    assert prj_in(z, "레이어.shp") == ""


# ── ④ 관문이 실제로 배선됐는가 ─────────────────────────────────
def test_check_one_actually_calls_both_verdicts():
    """★ 순수 함수만 만들고 안 부르면 §284-2 를 한 번 더 하는 것이다."""
    import inspect

    from firelane import contract
    body = inspect.getsource(contract.check_one)
    for name in ("prj_verdict", "coord_verdict", "prj_in"):
        assert name in body, f"`check_one` 이 {name} 를 안 부른다 — 관문이 또 장식이다"

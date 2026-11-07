#!/usr/bin/env python3
"""
test_segkey.py — **모든 산출물의 조인 키**를 만드는 자. (DECISIONS §493)

── 왜 생겼나 ───────────────────────────────────────────────────
`seg_uid` 는 실측·관측점·영상판정·DB PK 가 전부 쓰는 키다(§144). 그런데
그것을 만드는 함수 셋(`make_seg_uid` · `parse_seg_uid` · `bearing_at`)을
**시험이 이름으로도 안 부르고 있었다** — §482 가 번들에 한 질문을 판정
폐포(`src/firelane`)에 하자 공개 함수 211 중 44 가 그랬고, 그중 가장 센
자리가 여기다.

★ 밀어 보니 **머리말의 규칙 하나가 거짓**이었다(§493) — 「`None` 과 `""` 가
  같은 키를 받으면 안 된다」고 적는데 코드는 같은 키를 준다. 그리고 그것이
  옳다. 선언을 실물에 맞췄고, 그 사실을 여기가 든다.

IN    없음 (합성 선분)
OUT   없음 (검사)
PARAM 없음
밖    **좌표가 옳은가는 안 본다** — 중점이 실제 그 구간의 가운데인지는
      `segments.py` 와 발행물이 든다. 여기가 드는 것은 **키의 성질**이다:
      꼴 · 되읽기 · 반올림 · 좌표계 가드 · 이름 없는 꼴.
      **유지율도 안 본다**(`uid_retention` · 레이크가 있어야 돈다).
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import LineString

from firelane import segkey as sk

#: 5186 미터 좌표의 합성 구간. 동서로 100m.
EW = LineString([(192700, 283600), (192800, 283600)])


def test_the_key_has_the_declared_shape():
    """★ 꼴이 선언 그대로인가 — 지역 · X · Y · 해시 네 토막."""
    uid = sk.make_seg_uid(EW, "제봉로")
    region, x, y, h = uid.split("-")
    assert region == sk.REGION
    assert len(x) == len(y) == sk.COORD_DIGITS and x.isdigit() and y.isdigit()
    assert len(h) == sk.HASH_LEN and h.isupper()


def test_the_key_reads_back():
    """★ 파싱만으로 정보가 나온다 — 로그에서 좌표만 보고 자리를 짚는다."""
    uid = sk.make_seg_uid(EW, "제봉로")
    got = sk.parse_seg_uid(uid)
    assert got["region"] == sk.REGION
    assert got["x"] == 192750 and got["y"] == 283600
    assert got["road_hash"] == uid.split("-")[-1]


def test_the_midpoint_is_by_length_not_by_vertex_count():
    """★ **§144 의 그 규율.** 꺾임이 촘촘한 쪽으로 쏠리면 키가 그 쏠림을
    따라가고, `segments.py` 가 들고 있던 같은 수식과 조용히 갈린다."""
    bent = LineString([(192700, 283600), (192701, 283600),
                       (192702, 283600), (192800, 283600)])
    # 좌표 개수의 중간은 192702 쪽이다 — 길이의 절반은 192750 이다
    assert sk.midpoint(bent).x == pytest.approx(192750, abs=0.5)
    assert sk.make_seg_uid(bent, "제봉로") == sk.make_seg_uid(EW, "제봉로"), (
        "길이 중점이 같은 두 선이 다른 키를 받는다 — 좌표 개수를 보고 있다")


def test_the_key_rounds_to_a_metre():
    """★ 반올림의 사유 — 소수점 끝자리가 바뀔 때마다 키가 갈리면 안 된다."""
    jitter = LineString([(192700.2, 283600.3), (192800.2, 283600.3)])
    assert sk.make_seg_uid(jitter, "제봉로") == sk.make_seg_uid(EW, "제봉로")
    # ★ 그러나 1m 를 넘게 움직이면 **갈려야 한다** — 안 갈리면 키가 뭉갠다
    moved = LineString([(192702, 283600), (192802, 283600)])
    assert sk.make_seg_uid(moved, "제봉로") != sk.make_seg_uid(EW, "제봉로")


def test_a_wrong_crs_is_refused_not_absorbed():
    """★ 4326 을 넣으면 **죽는다.** 조용히 넘기면 전부 같은 접두사를 받아
    키가 무의미해진다 — 그 가드가 이 파일에서 제일 센 한 줄이다."""
    with pytest.raises(ValueError, match="CRS_M"):
        sk.make_seg_uid(LineString([(126.9266, 35.151), (126.9276, 35.151)]), "제봉로")


def test_the_road_name_only_breaks_ties():
    """★ 좌표가 주 키다 — 같은 자리 다른 도로는 **해시만** 달라진다."""
    a = sk.make_seg_uid(EW, "제봉로")
    b = sk.make_seg_uid(EW, "동명로")
    assert a != b, "같은 자리 다른 도로가 같은 키를 받는다"
    assert a.rsplit("-", 1)[0] == b.rsplit("-", 1)[0], "좌표 토막까지 갈렸다"


def test_every_nameless_form_gets_one_token():
    """★ **§493 이 선언을 고친 자리.** `None` · `""` · 문자열이 아닌 값이
    전부 같은 키를 받는다 — 셋 다 「이름이 없다」는 뜻이고, 가르면 같은
    구간이 발행 판마다 다른 키를 받는다."""
    none = sk.make_seg_uid(EW, None)
    assert sk.make_seg_uid(EW, "") == none
    assert sk.make_seg_uid(EW, float("nan")) == none
    assert sk.make_seg_uid(EW, 3) == none, "수를 도로명으로 읽는다"
    # ★ 그런데 **이름이 있는 쪽과는** 달라야 한다
    assert sk.make_seg_uid(EW, "제봉로") != none


def test_a_road_literally_named_noname_does_not_collide():
    """★ 토큰에 `\\x00` 을 쓰는 사유 — 실제 도로명으로는 나올 수 없는 글자다."""
    assert sk.make_seg_uid(EW, "NONAME") != sk.make_seg_uid(EW, None)


def test_the_name_is_stripped_before_hashing():
    """공백만 다른 이름이 두 키를 받으면 발행 판마다 키가 흔들린다."""
    assert sk.make_seg_uid(EW, " 제봉로 ") == sk.make_seg_uid(EW, "제봉로")


def test_the_bearing_at_an_offset_follows_the_line():
    """★ 관측점 국소 방위각 — 동서로 뻗은 선에서 90°(동) 쪽이어야 한다."""
    got = sk.bearing_at(EW, 50.0)
    assert got is not None
    assert math.isclose(got % 180, 90.0, abs_tol=1.0), got


def test_the_bearing_window_slides_inward_at_the_ends():
    """★ 머리말이 적은 규율 — 「끝단에서는 구간 밖으로 나가지 않게 창을
    안쪽으로 민다」. 그래서 선 밖을 물어도 **끝 접선**이 나오고 `None` 이
    아니다. 부르는 쪽이 `None` 을 안 다뤄도 되는 근거가 이것이다.

    ★ 이 성질을 시험이 적어 두는 이유 — 가드를 「밖이면 `None`」으로 바꾸면
      `obs_context` 가 조용히 빈 칸을 내고, 그 빈 칸은 횡단선을 못 긋는다.
    """
    end = sk.bearing_at(EW, 10_000.0)
    assert end is not None
    assert math.isclose(end % 180, 90.0, abs_tol=1.0), end
    assert sk.bearing_at(EW, -500.0) is not None, "음수 오프셋에서 죽는다"
    # 직선이면 어디서 물어도 같은 방향이다
    assert math.isclose(sk.bearing_at(EW, 0.0) % 180,
                        sk.bearing_at(EW, 100.0) % 180, abs_tol=1e-6)


def test_the_bearing_follows_a_bend():
    """★ **구간 하나에 방위각 하나를 주면 안 된다** — 굽은 골목은 지점마다
    도로가 뻗은 방향이 다르다. 그 주장을 꺾인 선으로 민다."""
    bend = LineString([(192700, 283600), (192750, 283600), (192750, 283700)])
    west = sk.bearing_at(bend, 10.0)      # 동서 구간
    north = sk.bearing_at(bend, 90.0)     # 남북 구간
    assert math.isclose(west % 180, 90.0, abs_tol=5.0), west
    assert math.isclose(north % 180, 0.0, abs_tol=5.0) or \
        math.isclose(north % 180, 180.0, abs_tol=5.0), north
    assert abs((west - north) % 180) > 45, (west, north)


# ── 이력 표 (DECISIONS §499) ─────────────────────────────────
def test_the_uid_map_is_sorted_and_carries_only_the_declared_columns(tmp_path):
    """★ `save_uid_map` — 런 간 대조용 이력이다. **정렬**이 그 쓸모다.

    머리말이 「git 에 커밋한다(작다) · 유지율 회귀를 눈으로 잡는다」를 적는다.
    정렬이 없으면 매 실행 줄 순서가 흔들려 **diff 가 전부 빨강**이 되고,
    그러면 사람이 그 표를 안 본다.
    """
    import geopandas as gpd
    from shapely.geometry import LineString

    from firelane.segkey import save_uid_map

    g = gpd.GeoDataFrame(
        {"seg_uid": ["DM-000003-000003-zzzz", "DM-000001-000001-aaaa"],
         "seg_id": [2, 1], "road_name": ["충장로", "동명로"],
         "length_m": [12.0, 6.0], "버릴칸": ["x", "y"]},
        geometry=[LineString([(0, 0), (1, 1)]), LineString([(2, 2), (3, 3)])],
        crs=5186)
    out = tmp_path / "hist" / "uid_map.csv"
    save_uid_map(g, out)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "seg_uid,seg_id,road_name,length_m", lines[0]
    assert lines[1].startswith("DM-000001"), "정렬이 안 됐다"
    assert "버릴칸" not in lines[0] and "LINESTRING" not in lines[1]


def test_the_uid_map_survives_a_frame_that_lacks_a_column(tmp_path):
    """★ 칸이 없으면 **그 칸만 빠진다** — 죽지 않는다.

    보정 전 프레임에는 `road_name` 이 없을 수 있고, 그때 이력이 안 적히면
    회귀를 비교할 상대가 사라진다.
    """
    import geopandas as gpd
    from shapely.geometry import LineString

    from firelane.segkey import save_uid_map

    g = gpd.GeoDataFrame({"seg_uid": ["DM-000001-000001-aaaa"]},
                         geometry=[LineString([(0, 0), (1, 1)])], crs=5186)
    out = tmp_path / "uid_map.csv"
    save_uid_map(g, out)
    assert out.read_text(encoding="utf-8").splitlines()[0] == "seg_uid"


def test_road_hash_folds_whitespace_only_names_into_the_no_name_token():
    """#179 — 공백뿐인 이름(`"   "` · 탭 · 줄바꿈 · 전각 공백)이 `""` · `None` 과 같은 무명 토큰을 받는다.

    종전: `(road_name or NONAME).strip()` 이라 `"   "` 는 truthy 로 통과한 뒤 `strip()` 에서 빈 문자열이 돼 **무명 토큰이 아닌 제3의 해시**를 받았다.
    그러면 같은 무명 도로가 입력 경로에 따라 `seg_uid` 꼬리 둘을 가진다. 실 경로는 `skeleton.as_road` 가 먼저 `None` 으로 바꿔 안 닿았지만 보호가 한 자리뿐이었다.
    실제 도로명(공백이 있어도 글자가 있는 이름)의 해시는 안 바뀐다 — 기존 `seg_uid` 가 갈리지 않는다.
    """
    from firelane.segkey import _road_hash

    none_tok = _road_hash(None)
    for blank in ("", " ", "   ", "\t", "\n", " \t\r\n ", "　", " "):
        assert _road_hash(blank) == none_tok, f"공백뿐인 이름이 무명으로 안 접힌다: {blank!r}"
    for nm in ("필문대로289번길", " 경양로 ", "2순환로"):
        assert _road_hash(nm) != none_tok, f"글자가 있는 이름이 무명으로 접혔다: {nm!r}"
        assert _road_hash(nm) == _road_hash(nm.strip()), f"바깥 공백이 해시를 갈랐다: {nm!r}"

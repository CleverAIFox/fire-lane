#!/usr/bin/env python3
"""
test_dest_facility.py — **건물 면의 이름이 목적지 색인에 든다.**  (PLAN #244 · DECISIONS §785 · §786)

── 왜 생겼나 ───────────────────────────────────────────────────
사람이 관제 화면에서 「전당 · 법원 부지가 검게 비었고 이름도 안 뜬다」고 세 번째 지적했다. 면은 `building.geojson` 에 있었고(`BULD_NM` ·
`POS_BUL_NM`) 색인(`destinations.build_index`)이 그 이름을 안 읽었다. 이 시험은 **합성 면**으로 읽는 규칙을 묻고(CI 에서 돈다),
**발행물**로 사람이 든 곳을 이름으로 묻는다(발행 뒤에만 돈다 — 없으면 건너뛴다).

── 이 시험이 무는 것 ──────────────────────────────────────────
① 이름 칸 둘 다 읽는다(`BULD_NM` · `POS_BUL_NM`) · 이름당 한 점(면적 최대 면) · 여섯 용도 밖은 안 든다.
② 지번이 이름 자리에 든 면은 안 든다. ③ `BULD_NM_DC` 는 이름이 아니라 `alt` 다(`광주지방법원`).
④ 다른 원천에 같은 이름이 있으면 그쪽이 정본이다 · 민원기관에 더 긴 이름이 있으면(`서석초등학교` ⊂ `광주서석초등학교`) 안 더한다.
⑤ 발행 색인에서 전당 · 법원 · 체육센터 · 롯데백화점이 **이름으로** 뜬다 · 건물 원천이다 · 주소 칸은 지어내지 않는다(빈 글자).
⑥ 전남대병원은 **지도 이동 범위 밖**이라 색인에 없다(§730-3 · 사람이 정한 범위) — 범위를 넓히면 이 시험이 울어 ⑤ 로 옮기라고 말한다.

IN    합성 도형 · `web/data/dest.geojson`(⑤ ⑥)
OUT   없음
PARAM 없음
밖    점이 맞는 건물 위인가(사람 눈) · 검색 질의의 점수 규칙(`web/navi/test/destFacility.test.ts` 가 화면 쪽 질의를 문다)
"""
from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from firelane import destinations as D
from firelane.paths import ROOT

DEST = ROOT / "web" / "data" / "dest.geojson"
X0, Y0 = 126.92, 35.15
EMPTY_STORE = gpd.GeoDataFrame({"name": [], "cat": [], "sub": [], "addr": []}, geometry=[], crs=4326)
EMPTY_CIVIL = gpd.GeoDataFrame({"유형": [], "상세분류": [], "기관명": [], "도로명주소": []}, geometry=[], crs=4326)
CLIP = box(X0 - 1, Y0 - 1, X0 + 1, Y0 + 1)


def _sq(dx: float, s: float = 0.0004):
    return box(X0 + dx, Y0, X0 + dx + s, Y0 + s)


def _faces(rows):
    """rows: (건물번호, BDTYP_CD, BULD_NM, POS_BUL_NM, BULD_NM_DC, 도형)"""
    return gpd.GeoDataFrame(
        {"BUL_MAN_NO": [r[0] for r in rows], "BDTYP_CD": [r[1] for r in rows], "BULD_NM": [r[2] for r in rows],
         "POS_BUL_NM": [r[3] for r in rows], "BULD_NM_DC": [r[4] for r in rows]},
        geometry=[r[5] for r in rows], crs=4326)


ROWS = [
    (1, "05999", "국립전당", None, None, _sq(0.00)),
    (2, "07107", "큰병원", "예전병원", None, _sq(0.01)),             # 이름 칸 둘
    (3, "07107", "큰병원", None, None, _sq(0.02, 0.0001)),            # 같은 이름 · 더 작은 면 → 위 면이 이긴다
    (4, "10101", "법원동", None, "광주지방법원", _sq(0.03)),           # 동 상세명은 alt
    (5, "10202", "서석동 126-1 제1종근린생활시설 (주식회사)", None, None, _sq(0.04)),   # 지번이 이름 자리
    (6, "01001", "단독주택이름", None, None, _sq(0.05)),              # 여섯 용도 밖
    (7, "08101", "서석초등학교", None, None, _sq(0.06)),              # 민원기관에 더 긴 이름
    (8, "09006", None, "동구체육센터", None, _sq(0.07)),             # 이름이 `POS_BUL_NM` 에만
]


def test_names_from_both_columns_one_point_per_name_and_six_uses_only():
    out = D.from_facility_faces(_faces(ROWS))
    got = set(out["name"])
    assert {"국립전당", "큰병원", "예전병원", "법원동", "동구체육센터", "서석초등학교"} <= got
    assert "단독주택이름" not in got, "여섯 용도 밖이 들었다"
    assert not any("126-1" in n for n in got), "지번이 이름이 됐다"
    assert list(out["name"]).count("큰병원") == 1, "같은 이름이 두 점이다"
    big = out[out["name"] == "큰병원"].geometry.iloc[0]
    assert big.x < X0 + 0.015, "면적 최대 면의 점이 아니다"
    assert set(out["src"]) == {"build"} and set(out["cat"]) == {"건물"} and set(out["addr"]) == {""}
    assert out.loc[out["name"] == "법원동", "alt"].iloc[0] == "광주지방법원"
    assert out.loc[out["name"] == "국립전당", "sub"].iloc[0] == "문화집회"


def test_build_index_keeps_other_sources_and_skips_duplicates_and_longer_civil_names():
    civil = gpd.GeoDataFrame({"유형": ["학교"], "상세분류": ["초등학교"], "기관명": ["광주서석초등학교"], "도로명주소": ["x"]},
                             geometry=gpd.points_from_xy([X0 + 0.06], [Y0]), crs=4326)
    store = gpd.GeoDataFrame({"name": ["국립 전당"], "cat": ["x"], "sub": ["x"], "addr": ["x"]},
                             geometry=gpd.points_from_xy([X0], [Y0]), crs=4326)
    nb = pd.DataFrame({c: [] for c in [f"c{i:02d}" for i in range(33)]})
    out, st = D.build_index(store, nb, pd.DataFrame({c: [] for c in [f"c{i:02d}" for i in range(20)]}), civil, CLIP,
                            faces=_faces(ROWS))
    names = list(out["name"])
    assert "국립전당" not in names, "공백만 다른 같은 이름이 둘이다"
    assert "서석초등학교" not in names and "광주서석초등학교" in names
    assert "큰병원" in names and st["facility"] == names.count("큰병원") + len({"예전병원", "법원동", "동구체육센터"})


def test_faces_are_optional_and_clipped():
    nb = pd.DataFrame({c: [] for c in [f"c{i:02d}" for i in range(33)]})
    nj = pd.DataFrame({c: [] for c in [f"c{i:02d}" for i in range(20)]})
    base, st = D.build_index(EMPTY_STORE, nb, nj, EMPTY_CIVIL, CLIP)
    assert "facility" not in st and len(base) == 0
    tiny = box(X0 - 0.001, Y0 - 0.001, X0 + 0.0005, Y0 + 0.001)
    out, st = D.build_index(EMPTY_STORE, nb, nj, EMPTY_CIVIL, tiny, faces=_faces(ROWS))
    assert set(out["name"]) == {"국립전당"} or len(out) <= 1, "범위 밖 점이 들었다"


def _dest():
    if not DEST.is_file():
        pytest.skip("발행물 없음 — publish_web 뒤에만 돈다")
    return json.loads(DEST.read_text(encoding="utf-8"))["features"]


@pytest.mark.parametrize("name", ["국립아시아문화전당", "광주지방.고등법원", "동구국민체육센터", "롯데백화점 광주점"])
def test_published_index_has_the_places_a_person_named(name):
    hit = [f["properties"] for f in _dest() if f["properties"]["name"] == name]
    assert len(hit) == 1, f"{name} 이 색인에 {len(hit)}번 있다"
    assert hit[0]["src"] == "build" and hit[0]["addr"] == "", "건물 면 이름 점은 건물 원천이고 주소를 지어내지 않는다"


def test_published_court_is_found_by_its_district_name():
    p = [f["properties"] for f in _dest() if f["properties"]["name"] == "광주지방.고등법원"][0]
    assert "광주지방법원" in p["alt"]


def test_university_hospital_is_outside_the_map_move_bounds_so_not_indexed():
    """§730-3 — 색인은 지도 이동 범위 안만이다. 전남대병원은 그 밖(건물 면 이름 `전남의대부속병원` · `전남대학교병원`)이라 없다.
    범위를 넓히면 이 시험이 운다 — 그때 위 목록에 올린다."""
    names = {f["properties"]["name"] for f in _dest()}
    assert not ({"전남의대부속병원", "전남대학교병원"} & names)

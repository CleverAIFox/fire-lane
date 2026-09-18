"""R3a — 뼈대 시험 교체 스위치와 `skeleton.as_road`. 합성 기하(EPSG:5186 미터). (DECISIONS §188)"""
from __future__ import annotations

import ast
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, box

from firelane import skeleton as S

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = ROOT / "src/firelane/segments.py"


def gdf(lines, **cols):
    return gpd.GeoDataFrame(cols, geometry=lines, crs=5186)


def test_switch_is_off_by_default_and_import_stays_inside_it():
    """★ 스위치가 꺼져 있으면 뼈대 모듈이 **아예 안 불린다.**

    import 를 모듈 꼭대기로 올리면 스위치와 무관하게 실행되고, 그 순간 R3a 가 판정 불변이 아니게 된다.
    2026-09-18. 이 저장소가 반복해 겪은 형태는 '있는데 안 부른다' 였는데, 여기는 반대 방향이다 —
    **안 부르기로 한 것이 조용히 불린다.**
    """
    src = SEGMENTS.read_text(encoding="utf-8")
    assert "FIRE_LANE_SKELETON" in src, "뼈대 스위치가 없다"
    tree = ast.parse(src)
    top = {n.module for n in ast.walk(tree)
           if isinstance(n, ast.ImportFrom) and n.col_offset == 0 and n.module}
    assert "firelane.skeleton" not in top, (
        "skeleton import 가 모듈 최상단에 있다 — 스위치와 무관하게 돈다")
    guarded = [n for n in ast.walk(tree)
               if isinstance(n, ast.If) and "FIRE_LANE_SKELETON" in ast.dump(n.test)
               and any(isinstance(x, (ast.Import, ast.ImportFrom)) for x in ast.walk(n))]
    assert guarded, "skeleton import 가 FIRE_LANE_SKELETON 분기 안에 없다"


def test_switch_is_registered_as_a_shell_switch_not_a_setting():
    """분류 — 설정은 `.env`, 스위치는 셸 export (`env_check` 가 강제한다).

    ★ 2026-09-18 R3a verify 1회차. 등재를 빠뜨려 `환경변수 선언↔실물` 이 둘로 울었다 —
      ① `.env.example` 에 없다(= 미분류 유령) ② `paths` 밖에서 `os.environ` 을 읽는다.
      스위치는 `.env.example` 에 **적으면 안 되고**(분류 위반) `env_check.SWITCHES` 에 등재해야 한다.
    """
    import env_check

    assert "FIRE_LANE_SKELETON" in env_check.SWITCHES, "env_check.SWITCHES 에 등재가 없다 — 유령 변수로 운다"
    assert "FIRE_LANE_SKELETON" not in env_check.SETTINGS
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    for line in env.splitlines():
        head = line.split("#", 1)[0].strip()
        assert not head.startswith("FIRE_LANE_SKELETON"), ".env.example 에 스위치를 설정으로 적었다(분류 위반)"


def test_switch_is_read_through_paths_not_os_environ():
    """`paths` 밖에서 `os.environ` 을 읽으면 `env_check` 의 단일 독자 규칙이 운다."""
    src = SEGMENTS.read_text(encoding="utf-8")
    code = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())   # 주석은 본다(설명이 그 이름을 쓴다)
    assert "os.environ" not in code, "segments.py 가 os.environ 을 직접 읽는다 — paths.flag 를 쓴다"
    assert "_flag(\"FIRE_LANE_SKELETON\")" in src, "paths.flag 로 안 읽는다"


def test_as_road_takes_width_from_ngii_but_name_from_road_link():
    """정본이 칸마다 다르다 — 폭은 NGII 측량, 이름은 도로명주소(§189-1)."""
    e = gdf([LineString([(0, 0), (100, 0)])], 도로명=["가길"], 도로폭=[6.5])
    rl = gdf([LineString([(0, 8), (100, 8)])], RN=["나길"], RDS_DPN_SE=["1"], ROAD_BT=[3.0])
    r = S.as_road(e, rl).iloc[0]
    assert r["RN"] == "나길", "법정 도로명(road_link)이 NGII 표기에 밀렸다"
    assert r["RDS_DPN_SE"] == "1", "RDS_DPN_SE 는 road_link 것을 따른다"
    assert r["ROAD_BT"] == 6.5, "ROAD_BT 는 NGII 측량 도로폭이어야 한다(폭 원천과 뼈대를 같은 측량으로)"


def test_as_road_fills_blank_ngii_name_from_road_link_beyond_roadname_band():
    """`roadname.BAND` 는 0.5m 다. 뼈대가 8m 옆에 서면 그 창으로는 한 건도 못 채운다 — 넓은 창이 필요하다."""
    e = gdf([LineString([(0, 0), (100, 0)])], 도로명=[""], 도로폭=[None])
    rl = gdf([LineString([(0, 8), (100, 8)])], RN=["나길"], RDS_DPN_SE=["1"], ROAD_BT=[3.0])
    r = S.as_road(e, rl).iloc[0]
    assert r["RN"] == "나길" and r["RDS_DPN_SE"] == "1" and r["ROAD_BT"] == 3.0
    far = gdf([LineString([(0, 40), (100, 40)])], RN=["다길"], RDS_DPN_SE=["0"], ROAD_BT=[9.0])
    assert S.as_road(e, far).iloc[0]["RN"] is None, "40m 밖 도로명을 가져왔다"


def test_as_road_defaults_dpn_to_main_road_when_unknown():
    """RDS_DPN_SE 0=주도로 · 1=부속. 모르면 0 이다 — 부속으로 잘못 찍으면 폭 경고가 통째로 죽는다."""
    e = gdf([LineString([(0, 0), (100, 0)])], 도로명=["가길"], 도로폭=[6.0])
    r = S.as_road(e, gdf([])).iloc[0]
    assert r["RDS_DPN_SE"] == "0" and r["RN"] == "가길"


def test_as_road_keeps_every_edge_and_geometry():
    keep = box(-10, -60, 210, 60)
    ngii = gdf([LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])],
               도로폭=[3.0, 3.0], 도로명=["가길", ""], 분리대유무=["무", "무"])
    edges = S.build(ngii, gdf([LineString([(0, 40), (200, 40)])]), keep)
    out = S.as_road(edges, gdf([LineString([(0, 41), (200, 41)])], RN=["나길"], RDS_DPN_SE=["0"], ROAD_BT=[7.0]))
    assert len(out) == len(edges), "엣지가 사라졌다"
    assert list(out.geometry) == list(edges.geometry), "기하가 바뀌었다 — as_road 는 속성만 입힌다"
    assert set(out.columns) >= {"RN", "RDS_DPN_SE", "ROAD_BT", "src"}


def test_road_hash_treats_nan_as_no_name_and_keeps_string_results_identical():
    """★ R3a 탐침(2026-09-18)이 잡은 것 — `NaN 은 truthy` 라 `or` 가 안 걸리고 `.strip()` 에서 죽었다.

    도로명주소 뼈대에서는 `RoadNameIndex` 가 못 맞추면 `None` 을 줘서 한 번도 안 터졌다.
    NGII 뼈대로 돌리자 무명 엣지가 생기며 파이프라인 **맨 끝** `attach_seg_uid` 에서 터졌다.
    문자열 입력의 결과는 종전과 같아야 한다 — 다르면 기존 seg_uid 가 전부 갈린다.
    """
    import math

    from firelane.segkey import _road_hash

    none_tok = _road_hash(None)
    assert _road_hash(float("nan")) == none_tok, "NaN 을 무명으로 안 접는다"
    assert _road_hash(math.nan) == none_tok
    assert _road_hash("") == none_tok, "빈 문자열 처리가 바뀌었다"
    for nm in ("필문대로289번길", "동계천로", " 경양로 ", "2순환로"):
        assert _road_hash(nm) == _road_hash(nm.strip() or None) if nm.strip() else True
    # 서로 다른 이름은 여전히 갈린다
    assert _road_hash("동계천로") != _road_hash("동명로") != none_tok


def test_as_road_never_emits_nan_into_name_or_width():
    """빈 값은 **None 하나로** 접는다. NaN 을 흘리면 하류가 `or` 로 못 거른다(§188-5)."""
    import pandas as pd

    e = gdf([LineString([(0, 0), (100, 0)])], 도로명=[float("nan")], 도로폭=[float("nan")])
    rl = gdf([LineString([(0, 5), (100, 5)])], RN=[float("nan")], RDS_DPN_SE=[float("nan")], ROAD_BT=[float("nan")])
    r = S.as_road(e, rl).iloc[0]
    assert r["RN"] is None and not isinstance(r["RN"], float), f"RN 에 NaN 이 샜다: {r['RN']!r}"
    assert r["ROAD_BT"] is None or not pd.isna(r["ROAD_BT"]), "ROAD_BT 에 NaN 이 샜다"
    assert r["RDS_DPN_SE"] == "0", "RDS_DPN_SE 가 문자열 '0' 이 아니다"
    blank = gdf([LineString([(0, 0), (100, 0)])], 도로명=["   "], 도로폭=[3.0])
    assert S.as_road(blank, gdf([])).iloc[0]["RN"] is None, "공백 이름을 이름으로 쳤다"


def test_road_link_name_wins_over_ngii_name():
    """★ 2026-09-18 (§189-1). 법정 도로명은 `road_link` 다. NGII 도로명은 측량 도면 표기라 보조다.

    R3a 1회차는 반대로 뒀고, 그 결과 도로명에 속한 구간 수가 반토막 나며(제봉로184번길 19→0)
    소방서 절대편차가 8.31m → 16.79m 로 벌어졌다. 폭이 아니라 이름이 갈린 것이다.
    """
    e = gdf([LineString([(0, 0), (100, 0)])], 도로명=["측량표기길"], 도로폭=[6.5])
    rl = gdf([LineString([(0, 5), (100, 5)])], RN=["법정도로명길"], RDS_DPN_SE=["0"], ROAD_BT=[5.0])
    r = S.as_road(e, rl).iloc[0]
    assert r["RN"] == "법정도로명길", "NGII 표기가 법정 도로명을 이겼다"
    assert r["ROAD_BT"] == 6.5, "ROAD_BT 는 NGII 측량 도로폭이어야 한다 — 이름과 폭의 정본은 다르다"
    # road_link 가 닿지 않으면 NGII 가 받는다
    assert S.as_road(e, gdf([])).iloc[0]["RN"] == "측량표기길"


def test_twin_needs_the_same_road_name():
    """478 중 108 이 금남로 ↔ 금남로169번길 형태의 **다른 골목**이었다. 이름이 다르면 쌍선이 아니다."""
    same = gdf([LineString([(0, 0), (100, 0)]), LineString([(0, 10), (100, 10)])],
               도로폭=[8.0, 8.0], 도로명=["가길", "가길"], 분리대유무=["무", "무"])
    assert S.twin_partner(same) == [1, 0]
    diff = same.copy()
    diff["도로명"] = ["가길", "가길169번길"]
    assert S.twin_partner(diff) == [None, None], "다른 도로명을 쌍선으로 셌다"
    blank = same.copy()
    blank["도로명"] = [None, None]
    assert S.twin_partner(blank) == [None, None], "무명끼리 짝을 지었다"



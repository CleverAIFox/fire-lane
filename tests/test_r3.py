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


def test_the_skeleton_switch_stays_out_of_the_judgment_closure():
    """★ 2026-09-27 (DECISIONS §266). 스위치를 **걷었다.** 다시 들어오면 운다.

    R3a 가 배선한 `FIRE_LANE_SKELETON` 은 판정을 한 번도 안 움직였고(기본 꺼짐),
    R3c 는 하지 않기로 결정됐다(DECISIONS §189-5). 그런데 그 한 줄이 `skeleton.py`
    417줄을 **판정 지문 안**에 넣고 있어서, 뼈대 상수를 만질 때마다 재잠금이
    따라왔다 — DECISIONS §247-1 이 고친 것과 같은 형태다.

    ★ 되살리려면 **판정 폐포가 늘어난다는 것을 알고** 되살려야 한다. 그래서 여기서
      막는다 — 지우는 것이 아니라 **값을 보이게** 하는 자리다.

    밖  `skeleton.as_road` 의 동작은 아래 시험들이 그대로 든다 —
        모듈은 살아 있고 `tools/skeleton_compare.py` 가 R1 대조로 쓴다.
    """
    src = SEGMENTS.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = {n.module for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.module}
    imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                for a in n.names}
    assert "firelane.skeleton" not in imports, (
        "`segments.py` 가 다시 `skeleton` 을 든다 — 판정 폐포가 16 → 17 로 는다.\n"
        "  정말 되살릴 것이면 `tests/test_lake.py` 의 폐포 래칫과 이 시험을 같이 고쳐라.")

    from firelane.shardseal import code_closure
    n = len(code_closure("firelane.segments"))
    # ★ 2026-09-29 (DECISIONS §303). 16 → 17. `seg/classify.py` 가 들어왔다.
    #   **판정 면적이 늘어난 것이 아니다** — 사슬 일곱 줄 중 둘이 `segments.py`
    #   (이미 폐포 안) 에서 새 파일로 나갔을 뿐이고, 새 파일도 폐포 안이다.
    #   폐포는 「판정을 만지면 재잠금이 따라오는 파일들」이라 이 이사는 수를
    #   하나 늘린다. 줄이려면 `verdict()` 를 `classify.py` 로 합쳐야 하는데
    #   그러면 `geom.verdict()` 를 보는 기존 시험 스물여섯이 함께 이사한다.
    assert n == 17, f"판정 폐포가 {n}이다 — 17 이어야 한다(DECISIONS §266 · §303)"

    import importlib.util
    import sys as _sys
    spec = importlib.util.spec_from_file_location("envchk_r3", ROOT / "tools" / "env_check.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    _sys.modules[spec.name] = m       # @dataclass 가 되짚는다 (DECISIONS §258-10)
    spec.loader.exec_module(m)
    assert "FIRE_LANE_SKELETON" not in m.SWITCHES, (
        "`env_check.SWITCHES` 에 등재가 남았다 — 유령 변수다")


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



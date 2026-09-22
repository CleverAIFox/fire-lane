"""
test_building_road_overlap.py — 발행된 건물이 도로면 위에 올라앉지 않는가.

2026-09-22 (DECISIONS §217-3 · §218). 도로면(수치지형도 · 실폭도로)과 건물(도로명주소)은 원천 ·
축척이 달라 5% 넘게 도로 위에 있는 건물이 370동이었다. 화면에서 **건물이 길을 덮었고** v0.34 까지
아무도 안 셌다 — 판정은 폭 표본을 따로 재서 무관했지만, 관제 · 내비를 보는 사람은 길이 막힌 것처럼
본다. `publish_web` 이 겹침 1~50% 인 건물에서 도로면을 뺀다. 이 시험이 **발행물**로 그것을 본다 —
발행 코드를 누가 되돌리거나 도로면이 바뀌어 새 겹침이 생기면 운다.

★ 절반 넘게 도로 위인 건물은 잘라내지 않는다(지우면 건물이 사라진다) — 그것은 데이터 쪽 문제라
  수를 상한으로만 묶는다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "web" / "data"

#: 잘라낸 뒤 남아도 되는 겹침 몫(부동소수 · buffer(0) 부스러기)
TOL = 0.011
#: 절반 넘게 도로 위라 그대로 둔 건물의 상한 — 2026-09-22 실측 83
MAX_MOSTLY_ON_ROAD = 90
#: 발행 쪽은 원본 도로면으로 「절반」 을 가르고, 여기서는 단순화된 발행 도로면으로 잰다 — 경계가
#: 최대 SIMPLIFY_M(0.4m) 움직여 그 몫이 조금 줄어든다. 그 차이만큼 아래로 연다
MOSTLY = 0.4


def _load():
    shapely = pytest.importorskip("shapely")
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    b = json.loads((W / "buildings.geojson").read_text(encoding="utf-8"))["features"]
    r = json.loads((W / "road_area.geojson").read_text(encoding="utf-8"))["features"]
    road = [shape(f["geometry"]).buffer(0) for f in r]
    return [shape(f["geometry"]) for f in b], road, STRtree(road), unary_union, shapely


def test_buildings_do_not_sit_on_roads():
    bld, road, tree, unary_union, _ = _load()
    partial, mostly = [], 0
    for i, g in enumerate(bld):
        if g.is_empty or g.area == 0:
            continue
        hit = [road[j] for j in tree.query(g)]
        if not hit:
            continue
        # 위경도 면적의 **비율**만 본다 — 좌표계를 안 바꿔도 몫은 같다
        share = g.intersection(unary_union(hit)).area / g.area
        if share > MOSTLY:
            mostly += 1
        elif share > TOL:
            partial.append((i, round(share, 3)))
    assert not partial, (f"건물 {len(partial)}동이 도로면에 1~50% 걸쳐 있다 — publish_web 의 도로면 빼기가 "
                         f"안 먹었다. 앞 5: {partial[:5]}")
    assert mostly <= MAX_MOSTLY_ON_ROAD, f"절반 넘게 도로 위인 건물 {mostly}동 > 상한 {MAX_MOSTLY_ON_ROAD}"

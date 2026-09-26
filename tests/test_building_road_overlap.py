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
    """건물 · 도로면을 **배열**로. 판정은 shapely 2 의 벡터 연산이 한다.

    ★ 2026-09-24 (PLAN §13 W12-6). 종전에는 건물 12,663개를 파이썬 루프로
      돌며 하나씩 `unary_union` + `intersection` 했다. **34.6초** — 전체
      시험 시간의 25%였고, 그러고 산 신호는 정수 비교 하나였다.

      실물을 보니 도로면은 **63장**뿐이라 STRtree 의 bbox 예선이 거의 아무도
      안 떨군다(12,663건물 → 12,917쌍). `predicate="intersects"` 로 실제
      교차를 예선에서 보게 하면 **124쌍**으로 줄고, 그 뒤 교차·면적은
      벡터 한 번이다. 8.4초 — 같은 답(겹침 83 · 부분 0)을 넉 배 빠르게 낸다.
    """
    shapely = pytest.importorskip("shapely")
    import numpy as np
    from shapely.geometry import shape
    from shapely.strtree import STRtree
    b = json.loads((W / "buildings.geojson").read_text(encoding="utf-8"))["features"]
    r = json.loads((W / "road_area.geojson").read_text(encoding="utf-8"))["features"]
    # ★ `buffer(0)` 은 **전량**에 건다. 깨진 것만 고치면 `side location conflict` 가
    #   난다 — 2026-09-24 에 실제로 났다. `is_valid` 가 참이어도 교차가 터진다.
    road = np.array([shape(f["geometry"]).buffer(0) for f in r], dtype=object)
    bld = np.array([shape(f["geometry"]) for f in b], dtype=object)
    return shapely, np, STRtree, bld, road


def _share(g, hit) -> float:
    """건물 하나가 도로면에 걸친 **몫**. 순수 함수라 합성 도형으로 흔들 수 있다.

    도로면끼리 안 겹치므로(`test_road_polygons_do_not_overlap_each_other`)
    **더해도 합집합과 같다.** 본 검사가 벡터로 하는 것과 같은 셈이다.
    """
    return sum(g.intersection(h).area for h in hit) / g.area


def test_the_overlap_judge_bites():
    """★ 2026-09-24 (PLAN §13 W12-6 · DECISIONS §239). `partial.append(...)` 이
    **한 번도 안 돈다**(커버리지 실측). 실물이 깨끗하다는 뜻이지만, 그 상태에서는
    「빼기가 먹었다」와 「판정기가 죽었다」를 못 가른다 — 34.6초를 쓰고 살아 있는
    신호는 `mostly <= 90` 정수 비교 하나뿐이었다.

    합성 사각형으로 세 갈래를 **밀리초에** 확인한다.
    """
    pytest.importorskip("shapely")
    from shapely.geometry import box

    g = box(0, 0, 10, 10)                       # 건물 100
    assert _share(g, [box(20, 20, 30, 30)]) == 0                     # 안 겹침
    assert _share(g, [box(0, 0, 1, 10)]) == pytest.approx(0.10)
    assert _share(g, [box(0, 0, 9, 10)]) == pytest.approx(0.90)
    # 안 겹치는 두 장은 **더해서** 낸다
    assert _share(g, [box(0, 0, 3, 10), box(7, 0, 10, 10)]) == pytest.approx(0.60)

    # 임계 셋이 서로 다른 갈래를 탄다
    assert _share(g, [box(0, 0, 1, 10)]) > TOL                       # partial
    assert _share(g, [box(0, 0, 9, 10)]) > MOSTLY                    # mostly
    assert _share(g, [box(0, 0, 0.05, 10)]) <= TOL                   # 부스러기


def test_road_polygons_do_not_overlap_each_other():
    """★ 아래 판정의 **전제**다. 건물별 몫을 도로면마다 **더해서** 내므로,
    도로면끼리 겹치면 같은 자리를 두 번 세어 몫이 부풀고 거짓 빨강이 난다.

    실측(2026-09-24) — 서로 겹치는 면적의 최댓값이 **0.0** 이다.
    """
    shapely, _np, STRtree, _bld, road = _load()
    assert len(road) > 10, f"도로면이 {len(road)}장이다 — 발행물이 비었다"
    pair = STRtree(road).query(road)
    ov = pair[:, pair[0] != pair[1]]
    # ★ 빈 배열이어도 **빠져나가지 않는다.** 겹치는 짝이 없으면 최댓값이 0 이고
    #   그것이 곧 「안 겹친다」의 증거다 — `return` 으로 나가면 못 잰 것과
    #   깨끗한 것이 같아 보인다(deadcheck ③).
    mx = (float(shapely.area(shapely.intersection(road[ov[0]], road[ov[1]])).max())
          if ov.size else 0.0)
    assert mx < 1e-12, (
        f"도로면끼리 {mx} 만큼 겹친다 — 아래 검사가 몫을 **두 번 센다.**\n"
        "  합이 아니라 합집합으로 바꾸거나, 발행 쪽에서 도로면을 합쳐라.")


def test_buildings_do_not_sit_on_roads():
    shapely, np, STRtree, bld, road = _load()
    # 예선에서 **실제 교차**를 본다 — bbox 만 보면 63장짜리 도로면이 거의
    # 아무도 안 떨군다(12,917쌍 → 124쌍).
    pair = STRtree(road).query(bld, predicate="intersects")
    if pair.size == 0:
        inter_area = np.zeros(0)
    else:
        inter_area = shapely.area(shapely.intersection(bld[pair[0]], road[pair[1]]))
    bld_area = shapely.area(bld)

    got: dict[int, float] = {}
    for i, a in zip(pair[0], inter_area, strict=True):
        got[int(i)] = got.get(int(i), 0.0) + float(a)

    partial, mostly = [], 0
    for i, tot in got.items():
        if bld_area[i] <= 0:
            continue
        # 위경도 면적의 **비율**만 본다 — 좌표계를 안 바꿔도 몫은 같다
        share = tot / bld_area[i]
        if share > MOSTLY:
            mostly += 1
        elif share > TOL:
            partial.append((i, round(share, 3)))

    assert not partial, (f"건물 {len(partial)}동이 도로면에 1~50% 걸쳐 있다 — publish_web 의 도로면 빼기가 "
                         f"안 먹었다. 앞 5: {partial[:5]}")
    assert mostly <= MAX_MOSTLY_ON_ROAD, f"절반 넘게 도로 위인 건물 {mostly}동 > 상한 {MAX_MOSTLY_ON_ROAD}"
    # ★ 빈 그물 방지 — 0동이면 예선이 죽었거나 발행물이 빈 것이다.
    assert mostly > 0, "도로 위 건물이 0동이다 — 예선(predicate=intersects)이 죽었거나 발행물이 비었다"

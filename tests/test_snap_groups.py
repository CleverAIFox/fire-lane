"""노드 접합이 **한 곳에서** 일어나는가 — 그리고 그 한 곳이 옳은가.

★ 2026-09-25 (PLAN §1 #125 · #47 · DECISIONS §252). 같은 union-find 15줄이
  `seg/graph.py`(§4 노드 접합)와 `segments.py::_write_route`(2차 경로) 두 곳에
  있었다. `PLAN #125` 는 「공백까지 같게」라 적었지만 **틀렸다** — 합집합
  방향이 달랐다:

      graph.py     _par[ri] = rj
      segments.py  _par[max(ri, rj)] = min(ri, rj)

  집합 분할은 같지만 **대표 인덱스가 다르다.** 그것이 하류에 새면 두 그래프가
  갈린다 — `segments.py` 머리말이 「**두 곳이 다른 규칙으로 노드를 묶으면
  그래프가 두 개가 된다**」고 적고 있었는데, 정작 그 두 곳이 다른 규칙이었다.

★ **추론으로 합치지 않았다.** `#47` 이 「`_find` ×5 동치성이 확인되지 않았다」로
  들고 있었고(2026-10-08 닫혔다 — `seg/unionfind.py` · DECISIONS §431) 합치기
  전에 증명이 먼저다. `graph.py` 쪽 방향을 바꾼 상태로
  `segments` 를 재실행해 판정 산출물 다섯이 바이트 동일함을 먼저 확인하고,
  그 다음에 `segments.py` 를 합쳤다.

IN    없음 (합성 점)
OUT   없음
PARAM 없음
밖    `tol` 값이 **옳은지**는 안 본다 — `NODE_TOL = 0.5` 의 근거는
      `seg/params.py` 가 들고 `PLAN §1 #70`(근거 없는 상수)이 재는 자리다.
      여기서 보는 것은 「같은 입력에 같은 묶음인가」와 「두 곳이 같은 문을
      쓰는가」 둘이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

from shapely.geometry import Point

from firelane.seg.geom import snap_groups

ROOT = Path(__file__).resolve().parent.parent

#: 종전에 각자 union-find 를 갖고 있던 둘.
USERS = ("src/firelane/seg/graph.py", "src/firelane/segments.py")


# ── 한 문인가 ───────────────────────────────────────────────────
def test_nobody_rolls_their_own_union_find_any_more():
    """두 곳이 **자기 것**을 다시 만들면 규칙이 또 갈린다."""
    bad = []
    for rel in USERS:
        src = (ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in ("_find", "find"):
                bad.append(f"{rel}:{node.lineno} {node.name}()")
    assert not bad, (
        "노드 접합을 다시 구현했다:\n  " + "\n  ".join(bad) + "\n"
        "  집은 `firelane.seg.geom.snap_groups` 하나다. 두 곳이 다른 규칙으로\n"
        "  묶으면 **그래프가 두 개가 된다** — `segments.py` 머리말이 그것을 적는데\n"
        "  정작 그 두 곳이 2026-09-25 까지 다른 규칙이었다(#125).")


def test_both_users_actually_call_the_one_door():
    """카나리아 — 아무도 안 부르면 위 검사는 **빈 그물**이다."""
    for rel in USERS:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "snap_groups(" in src, (
            f"{rel} 이 `snap_groups` 를 안 부른다 — 접합을 어디서 하는가?\n"
            "  안 하게 됐으면 USERS 에서 빼라. 남겨 두면 초록이 거짓말을 한다.")


# ── 옳은가 ──────────────────────────────────────────────────────
def test_points_within_tolerance_join_and_others_do_not():
    """`tol` 안은 묶이고 밖은 안 묶인다. **경계는 포함**이다(`<=`)."""
    pts = [Point(0, 0), Point(0.5, 0), Point(1.01, 0), Point(9, 9)]
    rep = snap_groups(pts, 0.5)
    assert rep[0] == rep[1], "정확히 tol 떨어진 둘이 안 묶였다 — 경계가 `<` 가 됐나"
    assert rep[1] != rep[2], "tol 밖(0.51)이 묶였다"
    assert rep[3] not in rep[:3], "9m 떨어진 점이 묶였다"


def test_joining_is_transitive():
    """A-B 가 붙고 B-C 가 붙으면 **A-C 도 한 노드**다. 사슬이 끊기면 그래프가 갈린다."""
    pts = [Point(0, 0), Point(0.4, 0), Point(0.8, 0), Point(1.2, 0)]
    rep = snap_groups(pts, 0.5)
    assert len(set(rep)) == 1, (
        f"사슬이 한 노드로 안 묶였다: {rep}\n"
        "  A-B 0.4 · B-C 0.4 · C-D 0.4 — 이웃끼리 전부 tol 안이다.\n"
        "  A-D 는 1.2m 지만 union-find 는 **이행적**이다.")


def test_the_representative_is_the_smallest_index():
    """대표 규칙이 결정적인가. 순회 순서에 기대면 실행마다 노드 ID 가 흔들린다."""
    pts = [Point(0, 0), Point(0.1, 0), Point(0.2, 0)]
    assert snap_groups(pts, 0.5) == [0, 0, 0], "가장 작은 인덱스가 대표여야 한다"
    pts2 = [Point(9, 9), Point(0, 0), Point(0.1, 0)]
    assert snap_groups(pts2, 0.5) == [0, 1, 1], "입력 순서가 바뀌어도 규칙은 같다"


def test_it_survives_the_degenerate_inputs():
    """빈 입력 · 한 점 · 전부 같은 점. 여기서 죽으면 파이프라인이 선다."""
    assert snap_groups([], 0.5) == []
    assert snap_groups([Point(0, 0)], 0.5) == [0]
    assert snap_groups([Point(0, 0)] * 4, 0.5) == [0, 0, 0, 0]
    assert snap_groups([Point(0, 0), Point(99, 99)], 0.0) == [0, 1], \
        "tol 0 이면 겹친 점만 묶인다"


def test_the_tolerance_actually_changes_the_answer():
    """카나리아 — `tol` 이 무시되면 위 검사들이 우연히 초록일 수 있다."""
    pts = [Point(0, 0), Point(3, 0)]
    assert snap_groups(pts, 0.5) == [0, 1], "3m 떨어진 둘이 tol 0.5 에서 묶였다"
    assert snap_groups(pts, 5.0) == [0, 0], "tol 을 키웠는데 안 묶인다 — 인자가 안 닿는다"

def test_a_two_centimetre_gap_still_joins():
    """**2026-08-24 사고의 경계.** 격자 반올림이면 여기서 갈린다.

    `_write_route` 가 끝점을 `round(x / 0.5)` 격자로 묶던 시절, 10.24 는 격자
    20 이고 10.26 은 21 이었다 — **0.02m 차이로 노드가 갈렸다.** 그 결과 폭
    15~18m 대로가 「도달 불가」로 나왔다(동계로 6-323 · 경양로347번길 1-347).

    union-find 는 경계가 없으므로 `tol` 안이면 어디서 끊기든 붙는다.
    """
    for base in (10.24, 0.49, 99.99, 1234.5):
        rep = snap_groups([Point(base, 0), Point(base + 0.02, 0)], 0.5)
        assert rep[0] == rep[1], (
            f"x={base} 와 x={base + 0.02} 가 다른 노드가 됐다 — 격자 반올림이 돌아왔다.\n"
            "  폭 15m 대로가 「도달 불가」로 나오는 것이 그 증상이다(2026-08-24).")


# ── 목적지 노드를 붙이는 길 — 접속선이 있으면 그 끝점, 없으면 직선 최근접 (PLAN #58 · DECISIONS §616) ──
def _targets_fixture():
    """노드 둘: A(0,0) · B(30,0). 출입구는 A 에 훨씬 가깝지만 접속선은 B 쪽 도로로 닿는다."""
    import geopandas as gpd
    import networkx as nx
    from shapely.geometry import LineString, box

    G = nx.Graph()
    G.add_edge((0.0, 0.0), (30.0, 0.0), geom=LineString([(0, 0), (30, 0)]), length=30.0)
    poly = box(-50, -50, 50, 50)
    rm, rs, out = Point(2, 5), Point(2, -5), Point(200, 200)
    ent = gpd.GeoDataFrame({"ENT_MAN_NO": [1, 2, 3], "ENTRC_SE": ["RM", "RS", "RM"]},
                           geometry=[rm, rs, out], crs=5186)
    # 접속선 — 끝점 순서를 일부러 뒤집어 준다(원천은 순서를 약속하지 않는다): 도로 쪽 끝이 앞에 온다.
    conn = gpd.GeoDataFrame({"ENT_MAN_NO": [1, 3]},
                            geometry=[LineString([(29, 1), (2, 5)]), LineString([(29, 1), (200, 200)])], crs=5186)
    return G, ent, poly, conn


def test_without_connectors_targets_are_the_straight_line_nearest_nodes():
    from firelane.seg.graph import access_targets
    G, ent, poly, _ = _targets_fixture()
    assert access_targets(G, ent, poly, None) == {(0.0, 0.0)}, "conn=None 은 종전(np.argmin)이어야 한다"


def test_an_entrance_with_a_connector_goes_to_the_road_end_node():
    from firelane.seg.graph import access_targets
    G, ent, poly, conn = _targets_fixture()
    got = access_targets(G, ent, poly, conn)
    assert (30.0, 0.0) in got, "접속선이 있는 출입구가 도로 쪽 끝점의 노드(B)에 안 붙었다 — 직선 최근접(A)에 남았다"


def test_an_entrance_without_a_connector_keeps_the_straight_line_fallback():
    """혼합이다 — `RS` 에는 접속선이 없고 종전대로 붙는다. 둘 다 있어야 한다."""
    from firelane.seg.graph import access_targets
    G, ent, poly, conn = _targets_fixture()
    assert access_targets(G, ent, poly, conn) == {(0.0, 0.0), (30.0, 0.0)}, \
        "RM(접속선→B) 하나와 RS(직선 최근접→A) 하나가 각자 붙어야 한다"


def test_entrances_outside_the_polygon_are_not_targets():
    from firelane.seg.graph import access_targets
    G, ent, poly, conn = _targets_fixture()
    # 3번은 poly 밖이다 — 접속선이 있어도 목적지가 아니다. 위 기대값이 둘뿐인 것이 그 증거다.
    assert len(access_targets(G, ent.iloc[[2]], poly, conn)) == 0

#!/usr/bin/env python3
"""
seg/geom.py — 폐포 없는 순수 함수.

`segments.py` 의 `main()` 안에 중첩 정의돼 있던 것들이다. AST 로 자유변수를
세어 **바깥 로컬을 하나도 잡지 않는 것**만 골라 옮겼다(2026-08-18 Stage 1).
로직은 한 글자도 바꾸지 않았다. `tools/golden.py` 로 산출물 동일을 증명한다.

왜 중첩이 문제였나
    1,041줄 `main()` 안에서는 이 함수들을 단위 테스트할 수 없었다.
    `verdict` 는 이 프로젝트의 결론 그 자체인데(clear/needs_cv/blocked/unknown)
    테스트가 0개였다. 표본 1개 clear 억제 같은 규칙은 주석으로만 존재했다.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from firelane.seg.params import NODE_TOL, PARK, TRUCK


def _seal(polys):
    """도로 폴리곤을 하나로 합친다.

    원본은 도로별·블록별로 쪼개져 있고 좌표가 mm 단위로 어긋나 있다.
    unary_union 만으로는 인접면이 안 붙어 얇은 틈이 경계선으로 남고,
    법선이 그 경계에서 끊겨 폭이 0.5m 로 나온다(중앙로 실측 사례).
    노딩에서 겪은 것과 같은 문제다(§3-2 T자 접합).
    살짝 부풀렸다 되돌려 틈을 닫는다.
    """
    u = unary_union([shapely.make_valid(g) for g in polys])
    return u.buffer(0.15, join_style=2).buffer(-0.15, join_style=2)


VERDICT_RULE = (
    "wmax < 3.0 -> blocked (통과 하한 미달)",
    "wmax 없음 + wmin 없거나 < 3.0 + ROAD_BT < 3.0 -> blocked (두 근거 독립 일치)",
    "wmin >= 7.0 + 정규표본 2개 이상 -> clear (양쪽 주차해도 통과)",
    "wmin >= 7.0 + 정규표본 1개 -> needs_cv (표본 하나로 clear 를 주지 않는다)",
    "wmin 있음 -> needs_cv (상습주차 여부로 갈림. 영상판정 대상)",
    "그 외 -> unknown (reason=width). 폭 산출 불가",
    "needs_cv 인데 CCTV 25m 밖 -> unknown (reason=no_cctv). 영상판정 불가",
)
"""판정 규칙의 문언 정본.

산출물 스키마(`segments.schema.json`)의 `verdict_rule` 은 이 상수에서
생성된다. 손으로 적으면 규칙을 고칠 때 한쪽만 바뀐다 — 실제로
`nreg <= 1` 보류 규칙이 코드·테스트·UI 에는 있고 스키마에만 없었다.

순서는 아래 `verdict()` 의 분기 순서이며, 마지막 줄만 `segments.py` 가
CCTV 거리로 적용한다. 강제자 — `tests/test_declaration_sync.py`
"""


def verdict(wmin, wmax, nreg=None):
    """소방청 기준 판정 4종.

        blocked   wmax <  3.0   통과 하한 미달. 장애물이 없어도 못 지나간다
        clear     wmin >= 7.0   양쪽에 주차가 있어도 통과. 영상판정 불필요
        unknown   폭 산출 불가
        needs_cv  나머지        상습주차 여부로 갈린다. 영상판정 대상
    """
    # ★ 표본 1개로는 clear 를 주지 않는다.
    #   DM02825(동계천로95번길, 길이 2.7m)는 표본 하나가 교차로를 대각선으로
    #   가로질러 42.1m 가 나왔고 그것이 곧 wmin 이 되어 clear 로 판정됐다.
    #   실제로는 사거리 한복판이다(네이버 거리뷰 확인, 2026-08-14).
    #   표본이 하나면 커버율이 자동으로 1.0 이 되어 COV_MIN 검사도 통과한다.
    #   clear 는 '영상판정조차 필요 없다'는 가장 강한 주장이라 근거가 필요하다.
    #   blocked 는 막는 쪽이라 표본 1개여도 유지한다(미탐:오탐 = 100:1).
    #   ※ widths() 에서 None 을 반환하면 3m 미만 구간이 fragment 로 떨어져
    #     44개 구간이 산출물에서 사라진다. 그래서 판정 단계에서 막는다.
    if wmax is not None and wmax < TRUCK:           return "blocked"
    if wmin is not None and wmin >= TRUCK + 2*PARK:
        if nreg is not None and nreg <= 1:
            return "needs_cv"
        return "clear"
    # 도로폭이 있으면 판정한다. wmax(담~담) 가 없는 것은 실패가 아니다.
    # 대로는 건물이 WMAX_CAP(60m) 밖이라 벽 사이를 잴 수 없고,
    # 그런 구간은 도로폭만으로 이미 판정이 끝난다.
    # ★ 2026-08-23 주석 정정. 여기 40m 라고 적혀 있었으나 params.WMAX_CAP 은
    #   60.0 이다. MASTER §16 미결 안건이 이 불일치를 적어두고도 안 고쳤다.
    # ★ 그리고 이 설명은 결손 496건(45%)을 덮지 못한다. 폭 0~3m 골목의 38.7%가
    #   결손인데 그런 골목에 건물이 60m 밖일 수는 없다. 진짜 원인은 width.py 의
    #   담~담 측정이 **좌우 동시 검출을 요구**하는 것이다(DECISIONS 08-22
    #   clearance 조사). 설명이 사례를 안 덮으면 설명이 틀린 것이다.
    # 이 줄이 없어서 필문대로·밤실로 같은 대로 392구간이 회색으로 떨어졌다.
    if wmin is not None:                            return "needs_cv"
    return "unknown"


def _dirv(geom, node, back=3.0):
    """node 쪽 끝에서 형상 안쪽을 향하는 단위벡터."""
    c = list(geom.coords)
    nd = Point(node)
    if Point(c[0]).distance(nd) <= Point(c[-1]).distance(nd):
        base, tgt = Point(c[0]), geom.interpolate(min(back, geom.length))
    else:
        base, tgt = Point(c[-1]), geom.interpolate(max(geom.length-back, 0.0))
    dx, dy = tgt.x-base.x, tgt.y-base.y
    L = np.hypot(dx, dy)
    return (dx/L, dy/L) if L > 0 else None


def _join(g1, g2):
    """접합점에서 두 형상을 용접한다.

    노드 접합으로 두 형상의 끝점이 최대 NODE_TOL 만큼 어긋나 있어
    linemerge 가 실패한다. 중점으로 용접해 틈을 없앤다.
    """
    c1, c2 = list(g1.coords), list(g2.coords)
    best = None
    for i1, e1 in ((0, c1[0]), (-1, c1[-1])):
        for i2, e2 in ((0, c2[0]), (-1, c2[-1])):
            dd = np.hypot(e1[0]-e2[0], e1[1]-e2[1])
            if best is None or dd < best[0]:
                best = (dd, i1, i2)
    dd, i1, i2 = best
    if dd > NODE_TOL * 2:
        return None
    A = c1 if i1 == -1 else c1[::-1]
    B = c2 if i2 == 0 else c2[::-1]
    mid = ((A[-1][0]+B[0][0])/2.0, (A[-1][1]+B[0][1])/2.0)
    return LineString(A[:-1] + [mid] + B[1:])

def snap_groups(pts, tol: float = NODE_TOL) -> list[int]:
    """끝점을 `tol` 안에서 union-find 로 묶는다. **각 점의 대표 인덱스**를 준다.

    ★ 2026-09-25 (PLAN §1 #125 · DECISIONS §252). 같은 15줄이 `seg/graph.py`
      (§4 노드 접합)와 `segments.py::_write_route`(2차 경로) 두 곳에 있었다.
      **둘이 글자까지 같지는 않았다** — 행은 「공백까지 같게」라 적었지만
      합집합 방향이 달랐다:

          graph.py     _par[ri] = rj                 먼저 만난 쪽을 뒤로
          segments.py  _par[max(ri, rj)] = min(...)  큰 인덱스를 작은 쪽 아래로

      **집합 분할은 같다** — union-find 에서 대표가 누구인가는 묶음을 안 바꾼다.
      다른 것은 대표 인덱스뿐이고, 두 쓰임 다 그것에 안 기댄다: `graph.py` 는
      그룹의 무게중심을 쓰고, `segments.py` 는 그룹의 **최소 인덱스 점** 좌표를
      쓴다(`_rep.setdefault` 가 오름차순 순회에서 첫 점을 잡는다).

      그래도 **추론으로 합치지 않았다** — `PLAN §1 #47` 이 「`_find` ×5 동치성이
      확인되지 않았다」로 들고 있고, 합치기 전에 증명이 먼저다. `segments`
      단계를 재실행해 판정 산출물 다섯이 바이트 동일함을 확인하고 합쳤다.

    ★ 대표 규칙은 `max → min` 을 골랐다. **가장 작은 인덱스가 대표**라는 것이
      읽는 사람에게 설명 없이 전달되고, 순회 순서와 무관하게 결정적이다.

    밖  무엇을 묶을지는 안 정한다 — `tol` 은 부르는 쪽이 준다. 기본값
        `NODE_TOL` 은 두 쓰임이 같은 값을 쓰기 때문이고, 다른 값이 필요하면
        넘겨라. mm 반올림으로 노드를 식별하면 4cm 떨어진 두 점이 별개가 되고
        그 사이에 길이 0.04m 엣지가 남는다(§4).
    """
    from shapely.strtree import STRtree

    par = list(range(len(pts)))

    def find(i: int) -> int:
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i

    tree = STRtree(pts)
    for i, pt in enumerate(pts):
        for j in tree.query(pt.buffer(tol)):
            j = int(j)
            if j != i and pts[i].distance(pts[j]) <= tol:
                ri, rj = find(i), find(j)
                if ri != rj:
                    par[max(ri, rj)] = min(ri, rj)
    return [find(i) for i in range(len(pts))]

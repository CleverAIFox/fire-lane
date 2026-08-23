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

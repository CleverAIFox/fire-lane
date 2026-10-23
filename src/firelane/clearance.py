"""
clearance.py — 구간별 **단순 내접원**(clearance, R = 0)을 칸으로 싣는다. **판정에 안 쓴다.** (Zm7 · DECISIONS §549)

IN    구간(EPSG:5186 선) · 실폭도로 면(`road_rw`) · 교차부 면(`ngii1k_xsec`)
OUT   `clear_min_m` · `clear_med_m` · `clear_max_m`(내접원 **지름** = 2 × 점에서 도로 경계까지의 거리) · `clear_src` · `clear_cov`
PARAM `RAY_M`(국소 클립 반경 — `seg.params`)
밖    **판정을 안 한다.** `seg/classify.py` 가 이 칸을 읽으면 시험이 운다(`tests/test_clearance.py`). 대표값을 `clear_min_m` 으로 할지 `clear_med_m` 으로 할지도 **아직 정하지 않았다**
      — 세 값을 다 싣고 사람이 현장 측정을 더 모은 뒤 정한다. 판정 폐포(`segments.py`) 밖이다 — 출판(`publish_web`)이 부른다.

── 왜 단순 내접원인가 ──────────────────────────────────────────
현장 16점(서로 다른 좌표 10 · 측선 ±1.0m)을 **같은 자리에서** 댔다(`tools/clearance_probe.py --field`). 로그오차 중앙(2배 초과 수):

    spot=mid   법선 w 0.911(9) · 대칭폭 0.532(5) · **실폭도로 R=0 0.247(2)** · 3소스 합집합 R=0 0.208(1) · ngii1k R=0 0.293(3)
    spot=off   법선 w 0.765(2) · 대칭폭 0.765(2) · **실폭도로 R=0 0.228(1)** · 3소스 합집합 R=0 0.810(2)(붕괴) · ngii1k R=0 0.753(2)

실폭도로 + R=0 이 두 spot 모두에서 안정적이다(합집합은 mid 최고이나 off 에서 붕괴). **R 보정(국소 최댓값)은 전부 악화된다**(R1 → R2.5 → R5 → R10 · 단조) — 단순 내접원이 맞다.
이전 지시(국소 최댓값 보정)는 틀렸다. 그래서 **R 상수를 만들지 않는다.**

★ 표본 위치 = 폭 엔진과 같다(`seg/width.py` 의 `_ts`: 양끝 `min(1.0, 0.25·길이)` 안쪽 · 2m 간격 · 짧으면 중점). 교차부 폴리곤 안의 표본은 뺀다(폭 엔진의 `XSEC` 제외와 같은 뜻 · 반경 폴백은 안 건다).
★ `clear_cov` = **실폭도로가 표본점을 덮는 비율**이다. 안 덮는 표본은 `NaN` 이라 min · med · max 에 안 들어간다. 이 수가 축 교체의 관건이다 — 덮지 않는 구간은 폴백이 필요하다.
★ 클립 반경 `RAY_M`(60m)을 넘는 경계는 안 본다 — 지름은 최대 120m 에서 잘린다(광장 · 대로 — 판정 문턱 3 · 7m 에는 닿지 않는 자리).
"""
from __future__ import annotations

import numpy as np

from firelane.seg.params import RAY_M

SRC = "road_rw"


def sample_positions(length: float) -> np.ndarray:
    """폭 엔진과 같은 표본 위치(`seg/width.py` `widths()` 의 `_ts`). 2m 간격은 그 엔진의 값이다."""
    lo = min(1.0, length * 0.25)
    ts = np.arange(lo, max(length - lo, length * 0.5 + 1e-9), 2.0)
    return ts if len(ts) else np.array([length / 2])


def robust_union(geoms):
    """무효 도형을 `make_valid` 로 정리하고 합친다 — 무효 도형을 그대로 합치면 **예외가 아니라 틀린 답**이 나온다."""
    import shapely
    g = np.asarray([x for x in geoms if x is not None and not x.is_empty], dtype=object)
    bad = ~shapely.is_valid(g)
    if bad.any():
        g[bad] = shapely.make_valid(g[bad])
    return shapely.union_all(g)


def inscribed(line, area_u, xsec_u=None):
    """한 구간의 표본 위치별 내접원 지름과 **덮임 비율**. 덮이지 않은 표본은 NaN.

    반환 `(지름 배열, 덮임 비율)`. 표본이 하나도 없으면 `(빈 배열, 0.0)`.
    """
    import shapely
    if line.geom_type != "LineString":
        line = max(line.geoms, key=lambda g: g.length)
    if line.length < 1e-6:
        return np.array([]), 0.0
    ts = sample_positions(line.length)
    pts = shapely.points(np.array([[line.interpolate(t).x, line.interpolate(t).y] for t in ts]))
    if xsec_u is not None:
        keep = ~shapely.intersects(xsec_u, pts)
        if keep.any():                         # 전부 교차부면 종전대로 전부 잰다(폭 엔진의 짧은 조각 규칙과 같은 뜻)
            pts = pts[keep]
    local = shapely.intersection(area_u, line.buffer(RAY_M))
    out = np.full(len(pts), np.nan)
    if local.is_empty:
        return out, 0.0
    inside = shapely.contains(local, pts)
    if inside.any():
        out[inside] = 2.0 * shapely.distance(local.boundary, pts[inside])
    return out, float(inside.mean())


def columns(lines, area_u, xsec_u=None):
    """구간 선 목록 → 다섯 칸의 딕셔너리 목록(같은 순서). 판정에 안 쓴다."""
    rows = []
    for ln in lines:
        d, cov = inscribed(ln, area_u, xsec_u)
        ok = d[~np.isnan(d)]
        if len(ok):
            rows.append(dict(clear_min_m=round(float(ok.min()), 2), clear_med_m=round(float(np.median(ok)), 2),
                             clear_max_m=round(float(ok.max()), 2), clear_src=SRC, clear_cov=round(cov, 3)))
        else:
            rows.append(dict(clear_min_m=None, clear_med_m=None, clear_max_m=None, clear_src=None, clear_cov=round(cov, 3)))
    return rows

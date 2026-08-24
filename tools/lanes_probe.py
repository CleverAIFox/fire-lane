#!/usr/bin/env python3
"""
tools/lanes_probe.py — 표준노드링크의 차로수·제한폭으로 폭을 교차검증한다

    uv run python tools/lanes_probe.py            대조표
    uv run python tools/lanes_probe.py --save     interim/lanes_join.csv

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 읽고 표를 낸다.

── 왜 만들었나 ─────────────────────────────────────────────────
`node_link` 1,366개를 받아서 **아무도 안 읽고 있었다.**
`guards.CRITICAL` 과 계보 게이트에만 이름이 있고, 판정에는 안 쓴다.

그런데 그 안에 폭의 **독립 근거**가 들어 있다.

    LANES       차로수. 2차로면 노면이 최소 5.5m 다
    REST_W      통행 제한 폭(m). 있으면 그게 곧 상한이다
    REST_H      제한 높이. 폭과 무관하지만 소방차 진입에는 든다
    REST_VEH    차량 제한 코드
    ROAD_RANK   도로 등급
    MAX_SPD     제한속도. 좁은 골목은 낮다

이것들은 **국토부 ITS 가 현장 조사로 채운 값**이라 우리 폭 산출
(수치지형도 트랜섹트)과 계보가 완전히 다르다. 오늘 찾던 그 축이다.

── 다만 한계가 분명하다 ────────────────────────────────────────
`node_link` 는 **차량 통행이 있는 도로만** 담는다. 동명동 골목 대부분은
표준노드링크에 없다. 매칭률이 낮게 나올 것이고, 그것 자체가 정보다 —
**매칭 안 되는 구간 = 국가가 차도로 안 보는 길** 이다.

`LANES` 는 차로수지 폭이 아니다. 환산은 가정이 들어간다.

    1차로  ≥ 3.0m      2차로  ≥ 5.5m      3차로  ≥ 8.5m

도로구조규칙의 최소 차로폭(소형도로 3.0m · 일반 3.25~3.5m)을 하한으로
쓴다. **하한이므로 "이보다 좁을 수는 없다" 만 말한다.** 실제는 더 넓다.

IN    data/processed/node_link_5186.gpkg
      data/processed/segments_5186.gpkg
OUT   없음. --save 를 주면 $FIRE_LANE_DATA/interim/lanes_join.csv
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

from firelane.paths import INTERIM, PROCESSED
from firelane.seg.params import TRUCK

SNAP = 8.0          # 구간과 링크를 같은 길로 볼 최대 거리(m)
ANGLE = 35.0        # 방위 차이가 이보다 크면 다른 길이다(도)

# 차로수 → 노면 폭 하한(m). 도로구조규칙 최소 차로폭 3.0m 기준.
# ★ 하한이다. "이보다 좁을 수는 없다" 만 말한다.
LANE_MIN = {1: 3.0, 2: 5.5, 3: 8.5, 4: 11.5, 5: 14.5, 6: 17.5}

C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m",
     "c": "\033[36m", "d": "\033[90m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def _coords(g):
    return list(g.coords) if g.geom_type == "LineString" else \
        list(max(g.geoms, key=lambda q: q.length).coords)


def bearing(g) -> float:
    """선분의 현(chord) 방위(0~180도). 표시용으로만 쓴다.

    ★ 2026-08-24. 매칭에는 쓰지 않는다. 결정 73 이 이 방식을 폐기했다 —
      *"굽은 골목은 지점마다 방향이 다르다. 밤실로4번안길 37m 에서
      75.2° → 73.9°"*. 구간 길이 중앙값이 36.3m 다.
    """
    c = _coords(g)
    dx, dy = c[-1][0] - c[0][0], c[-1][1] - c[0][1]
    return float(np.degrees(np.arctan2(dy, dx)) % 180)


def bearings(g) -> np.ndarray:
    """**부분선분마다의** 방위. 짧은 조각은 노이즈라 뺀다.

    ★ 2026-08-24 신설. 현(chord) 하나로 판정하니 거리로 붙은 479구간 중
      213(44%)이 각도에서 떨어졌다. 굽은 길은 현이 실제 방향과 어긋난다.
      결정 73 을 이 도구에도 적용한다.
    """
    c = np.asarray(_coords(g), dtype=float)
    d = np.diff(c[:, :2], axis=0)
    ln = np.hypot(d[:, 0], d[:, 1])
    keep = ln >= 2.0                       # 2m 미만 조각은 방위가 흔들린다
    if not keep.any():
        keep = ln == ln.max()
    return np.degrees(np.arctan2(d[keep, 1], d[keep, 0])) % 180


def angle_gap(a, b) -> float:
    """두 선의 **가장 가까운** 부분선분 쌍의 방위차(0~90).

    같은 길이면 어딘가 한 조각은 나란하다. 전 구간이 나란할 필요는 없다.
    """
    # ★ sjoin(how="left") 의 미매칭 행은 NaN(float)이다. 배열이 아니다.
    if not isinstance(a, np.ndarray) or not isinstance(b, np.ndarray):
        return 999.0
    if a.size == 0 or b.size == 0:
        return 999.0
    d = np.abs(a[:, None] - b[None, :])
    return float(np.minimum(d, 180 - d).min())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()

    nl_p = PROCESSED / "node_link_5186.gpkg"
    sg_p = PROCESSED / "segments_5186.gpkg"
    for p in (nl_p, sg_p):
        if not p.exists():
            print(col(f"{p} 가 없다. uv run fire-lane 를 먼저 돌려라.", "r"))
            return 1

    nl = gpd.read_file(nl_p)
    sg = gpd.read_file(sg_p)
    print(f"표준노드링크 {len(nl):,} · 구간 {len(sg):,}\n")

    have = [c for c in ("LANES", "REST_W", "REST_H", "REST_VEH",
                        "ROAD_RANK", "MAX_SPD", "ROAD_NAME") if c in nl.columns]
    print(f"{col('① 살아 있는 속성', 'c')}  {', '.join(have) or '(없다)'}")
    if "LANES" not in nl.columns:
        print(col("   LANES 가 없다 — ingest 가 버렸을 수 있다.", "r"))
        return 1
    nl["LANES"] = pd.to_numeric(nl.LANES, errors="coerce")
    print(f"   차로수 분포 {nl.LANES.value_counts().sort_index().to_dict()}")
    for c in ("REST_W", "REST_H"):
        if c in nl.columns:
            v = pd.to_numeric(nl[c], errors="coerce")
            n = int((v > 0).sum())
            print(f"   {c} 값 있는 링크 {n:,} / {len(nl):,}"
                  + (f" · 중앙 {v[v > 0].median():.1f}" if n else ""))

    # ── 매칭 ────────────────────────────────────────────────
    # ★ 최근접만으로는 안 된다. 나란히 붙은 다른 길을 집는다.
    #   방위가 비슷할 때만 같은 길로 본다.
    nl["brg"] = nl.geometry.map(bearings)
    sg["brg"] = sg.geometry.map(bearings)
    nl_m = nl.copy()
    nl_m["geometry"] = nl_m.geometry.buffer(SNAP)
    j = gpd.sjoin(sg, nl_m[["LANES", "brg", "geometry"]
                           + [c for c in ("REST_W", "ROAD_RANK") if c in nl_m]],
                  how="left", predicate="intersects", lsuffix="s", rsuffix="n")
    # ★ 2026-08-24. 종전 `fillna(999)` 는 **미매칭 행에 참을 냈다.**
    #   min(999, 180-999) = min(999, -819) = -819 이고 -819 <= 35 이다.
    #   지금은 뒤의 dropna 가 덮어서 결과가 안 틀렸을 뿐, 각도 검사가
    #   미매칭에 참을 내는 구조는 언제든 터진다. 미매칭은 먼저 뗀다.
    before = j.seg_uid.nunique()
    gap = [angle_gap(x, y) for x, y in zip(j.brg_s, j.brg_n, strict=True)]
    j = j[np.asarray(gap) <= ANGLE]
    print(col(f"   각도 필터 {before:,} → {j.seg_uid.nunique():,} 구간", "d"))
    # 구간마다 차로수가 가장 큰 링크를 취한다 (보수적 상한이 아니라 하한이므로)
    g = j.groupby("seg_uid").agg(lanes=("LANES", "max")).dropna()

    print(f"\n{col('② 매칭', 'c')}  구간 {len(g):,} / {len(sg):,} "
          f"({len(g)/len(sg)*100:.0f}%)")

    # ★ 2026-08-24. 종전에는 여기서 끝났고, 곧바로 "매칭 안 되는 구간 =
    #   국가가 차도로 안 보는 골목" 이라고 **단정**했다. 그것은 가설이지
    #   측정이 아니다. 24% 의 원인은 둘인데 구간 쪽만 세면 안 갈린다.
    #
    #       링크는 대부분 붙는데 구간이 24%  → 데이터. 골목이 원래 없다
    #       링크도 대량 미매칭               → 로직. 조인이 부실하다
    #
    #   ★ 역방향을 센다. 이 한 줄이 판정이다.
    hit_links = set(j["index_n"].dropna().astype(int)) if "index_n" in j else set()
    print(f"   링크 {len(hit_links):,} / {len(nl):,} "
          f"({len(hit_links)/max(len(nl),1)*100:.0f}%) 가 구간에 붙었다")

    # ★ 연장 가중. 개수 24% 와 연장 % 는 다른 이야기다. 표준노드링크는
    #   간선 위주라 266구간이 총연장의 절반 이상일 수 있다. 그러면
    #   "골목을 안 담는다" 가 숫자로 확정된다.
    if "length_m" in sg.columns:
        tot = sg.length_m.sum()
        got = sg[sg.seg_uid.isin(g.index)].length_m.sum()
        print(f"   연장 {got:,.0f} / {tot:,.0f} m ({got/max(tot,1)*100:.0f}%)")
        um = sg[~sg.seg_uid.isin(g.index)]
        print(f"   미매칭 구간 길이 중앙 {um.length_m.median():.1f} m · "
              f"매칭 {sg[sg.seg_uid.isin(g.index)].length_m.median():.1f} m")

    # ★ 2026-08-24. 링크도 25% 다 — "골목이 없어서" 가 아니다.
    #   원인을 더 가른다. 거리만 봤을 때와 각도까지 봤을 때를 나눈다.
    for r in (SNAP, 15.0, 25.0):
        nb = nl.copy()
        nb["geometry"] = nb.geometry.buffer(r)
        jj = gpd.sjoin(sg[["seg_uid", "geometry"]], nb[["geometry"]],
                       how="inner", predicate="intersects")
        ns = jj.seg_uid.nunique()
        nlk = jj.index_right.nunique()
        print(f"   거리 {r:>4.0f}m 만       구간 {ns:>5,} ({ns/len(sg)*100:>3.0f}%)"
              f" · 링크 {nlk:>5,} ({nlk/len(nl)*100:>3.0f}%)")

    # 스코프 밖 링크인가 — 구간 전체 형상에서 얼마나 떨어져 있나
    import shapely
    hull = shapely.union_all(sg.geometry.values)
    d = nl.geometry.distance(hull)
    for t in (8, 25, 50, 100):
        print(f"   구간망에서 {t:>3}m 안 링크 {int((d <= t).sum()):>5,}"
              f" ({(d <= t).mean()*100:>3.0f}%)")

    print()
    print(col("   판정 —", "c"))
    print(col("     링크 매칭률 높고 구간 낮다  → 데이터. 골목이 원래 없다", "d"))
    print(col("     링크도 낮다                → 로직. SNAP·ANGLE·현(chord)", "d"))
    print(col("     연장 % 가 개수 % 보다 훨씬 높다 → 간선만 담긴 것이 확정", "d"))

    m = sg.merge(g, on="seg_uid", how="inner")
    m["lane_min"] = m.lanes.map(LANE_MIN)
    m = m.dropna(subset=["lane_min", "width_min_m"])
    m["gap"] = m.width_min_m - m.lane_min

    print(f"\n{col('③ 우리 폭 vs 차로수 하한', 'c')}  {len(m):,}구간")
    print(f"   중앙 차이 {m.gap.median():+.2f} m · 표준편차 {m.gap.std():.2f}")
    bad = m[m.gap < -0.5]
    print(f"   {col('★ 하한보다 좁다', 'y')}  {len(bad)}구간 — "
          f"차로수가 맞다면 우리 폭이 과소다")
    if len(bad):
        cols = ["seg_label", "verdict", "width_min_m", "lanes", "lane_min",
                "width_cov", "length_m"]
        cols = [c for c in cols if c in bad.columns]
        print(bad.sort_values("gap")[cols].head(12).to_string(index=False))

    flip = m[(m.width_min_m < TRUCK) & (m.lane_min >= TRUCK)]
    print(f"\n{col('④ 판정이 갈리는 구간', 'c')} {len(flip)} — "
          f"우리는 {TRUCK}m 미만인데 차로수는 통과 가능이라 한다")
    if len(flip):
        cols = [c for c in ("seg_label", "verdict", "width_min_m", "lanes",
                            "lane_min", "width_cov", "n_sample") if c in flip.columns]
        print(flip.sort_values("width_min_m")[cols].head(12).to_string(index=False))

    if a.save:
        # ★ 2026-08-24. processed → interim. 이것은 탐색 산출물이고
        #   대장에 없다. processed 는 파이프라인 정본 자리다(§18-1).
        INTERIM.mkdir(parents=True, exist_ok=True)
        dst = INTERIM / "lanes_join.csv"
        keep = [c for c in ("seg_uid", "seg_label", "verdict", "width_min_m",
                            "lanes", "lane_min", "gap", "width_cov", "length_m")
                if c in m.columns]
        m[keep].to_csv(dst, index=False, encoding="utf-8-sig")
        print(f"\n{col('→', 'g')} {dst}")

    print(col("\n★ 판정에 반영하지 않았다. 차로수는 폭이 아니라 하한이다.", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

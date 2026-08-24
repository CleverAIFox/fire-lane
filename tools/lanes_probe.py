#!/usr/bin/env python3
"""
tools/lanes_probe.py — 표준노드링크의 차로수·제한폭으로 폭을 교차검증한다

    uv run python tools/lanes_probe.py            대조표
    uv run python tools/lanes_probe.py --save     data/processed/lanes_join.csv

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
OUT   없음. --save 를 주면 data/processed/lanes_join.csv
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

from firelane.paths import PROCESSED
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


def bearing(g) -> float:
    """선분의 방위(0~180도). 방향은 무시한다 — 일방통행도 같은 길이다."""
    c = list(g.coords) if g.geom_type == "LineString" else \
        list(max(g.geoms, key=lambda q: q.length).coords)
    dx, dy = c[-1][0] - c[0][0], c[-1][1] - c[0][1]
    return float(np.degrees(np.arctan2(dy, dx)) % 180)


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
    nl["brg"] = nl.geometry.map(bearing)
    sg["brg"] = sg.geometry.map(bearing)
    nl_m = nl.copy()
    nl_m["geometry"] = nl_m.geometry.buffer(SNAP)
    j = gpd.sjoin(sg, nl_m[["LANES", "brg", "geometry"]
                           + [c for c in ("REST_W", "ROAD_RANK") if c in nl_m]],
                  how="left", predicate="intersects", lsuffix="s", rsuffix="n")
    j = j[(j.brg_s - j.brg_n).abs().fillna(999).apply(
        lambda d: min(d, 180 - d)) <= ANGLE]
    # 구간마다 차로수가 가장 큰 링크를 취한다 (보수적 상한이 아니라 하한이므로)
    g = j.groupby("seg_uid").agg(lanes=("LANES", "max")).dropna()

    print(f"\n{col('② 매칭', 'c')}  {len(g):,} / {len(sg):,} "
          f"({len(g)/len(sg)*100:.0f}%)")
    print(col("   매칭 안 되는 구간 = 표준노드링크에 없는 길 =", "d"))
    print(col("   국가가 차도로 관리하지 않는 골목이다. 그것 자체가 정보다.", "d"))

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
        dst = PROCESSED / "lanes_join.csv"
        keep = [c for c in ("seg_uid", "seg_label", "verdict", "width_min_m",
                            "lanes", "lane_min", "gap", "width_cov", "length_m")
                if c in m.columns]
        m[keep].to_csv(dst, index=False, encoding="utf-8-sig")
        print(f"\n{col('→', 'g')} {dst}")

    print(col("\n★ 판정에 반영하지 않았다. 차로수는 폭이 아니라 하한이다.", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

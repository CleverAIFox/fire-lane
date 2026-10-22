#!/usr/bin/env python3
"""
tools/hydrant_reach.py — 통행 불가 구간 근처에 소화전이 닿는가 (PLAN #95)

    uv run python tools/hydrant_reach.py             40m 로 센다
    uv run python tools/hydrant_reach.py --reach 45  호스 3본 전량(15m x 3)으로 센다

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 읽고 수를 낸다. 판정을 안 움직인다.

── 무엇을 재나 ─────────────────────────────────────────────────
「도로엔 못 들어가도 근처 소화전이 있으면 호스로 대응 가능」의 **근처**가 `REACH_M` 이다.
소방호스 1본 15m, 통상 3본 45m, 여유를 두고 **40m** 로 정했다(PLAN #29 · DECISIONS §543).
이 수는 8m 였던 옛 매칭 반경을 대체한다.

각 구간에서 가장 가까운 소화전까지의 **직선거리**를 재어 `REACH_M` 이내면 「닿는다」.
★ 직선거리는 호스가 실제로 깔리는 길이의 **하한**이다 — 담·건물을 돌아 깔면 길어진다. 그래서 이 수는
  낙관적이다. 호스 경로 길이를 재려면 보행 그래프가 필요하고 이 도구는 거기까지 가지 않는다.
★ 소화전 좌표는 표준데이터 공개분이다. 비공개분은 없다(MASTER §3-12) — 「안 닿는다」는 「없다」가 아니다.

IN    data/processed/segments_5186.gpkg · hydrant_point_5186.gpkg
OUT   없음 (표준출력)
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
from collections import Counter

REACH_M = 40.0      # 소방호스 1본 15m · 통상 3본 45m · 여유 5m (PLAN #29)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reach", type=float, default=REACH_M, help="호스가 닿는 거리(m)")
    a = ap.parse_args()

    import geopandas as gpd

    from firelane.console import col
    from firelane.paths import PROCESSED

    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg")
    hyd = gpd.read_file(PROCESSED / "hydrant_point_5186.gpkg").to_crs(seg.crs)
    near = gpd.sjoin_nearest(seg[["seg_id", "verdict", "geometry"]], hyd[["geometry"]],
                             how="left", distance_col="d_m")
    near = near.groupby("seg_id").agg(verdict=("verdict", "first"), d_m=("d_m", "min"))
    print(f"소화전 {len(hyd)} · 구간 {len(seg)} · 닿는 거리 {a.reach:g}m\n")
    print(f"{col('판정', 'c'):>14}{'구간':>7}{'닿음':>7}{'비율':>8}")
    tot = Counter(near.verdict)
    hit = Counter(near[near.d_m <= a.reach].verdict)
    for v in ("blocked", "needs_cv", "unknown", "clear"):
        print(f"{v:>10}{tot[v]:>7}{hit[v]:>7}{(100 * hit[v] / tot[v] if tot[v] else 0):>7.1f}%")
    b = near[near.verdict == "blocked"].d_m
    print(f"\nblocked 의 가장 가까운 소화전까지  중앙 {b.median():.0f}m · 최대 {b.max():.0f}m")
    print(col("★ 직선거리라 호스 길이의 하한이다. 아무것도 안 바꿨다.", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

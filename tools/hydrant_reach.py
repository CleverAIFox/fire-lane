#!/usr/bin/env python3
"""
tools/hydrant_reach.py — 통행 불가 구간 근처에 소화전이 닿는가 (PLAN #95)

    uv run python tools/hydrant_reach.py             40m 로 센다
    uv run python tools/hydrant_reach.py --reach 45  호스 3본 전량(15m x 3)으로 센다

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 읽고 수를 낸다. 판정을 안 움직인다.

── 무엇을 재나 ─────────────────────────────────────────────────
「도로엔 못 들어가도 근처 소화전이 있으면 호스로 대응 가능」의 **근처**가 `REACH_M` 이다.
**임계 하나가 아니라 등급 셋이다**(PLAN #29 · 인터뷰 1차 D-30 · DECISIONS §544-4 정정). 근거 — 「호스 하나는 15m」「최대 10번까지 연결」(현장).
  ~15m  호스 1본 · ~45m  3본(통상) · ~140m  10본(법정 한계 · NFTC 401 수평거리 140m)
★ 140m **단일 임계는 1,281구간 전부가 닿아 변별력이 0 이다**(가장 먼 곳 120m). 그래서 문턱을 박지 않고 **구간별 거리를 내고 등급을 적는다.**
★ 판정에는 안 넣는다(판정 불변). `segments` 에 칸을 더하면 코드 축이 움직여 재잠금이라 **옆 파일**로 낸다.

각 구간에서 가장 가까운 소화전까지의 **직선거리**를 재어 `REACH_M` 이내면 「닿는다」.
★ 직선거리는 호스가 실제로 깔리는 길이의 **하한**이다 — 담·건물을 돌아 깔면 길어진다. 그래서 이 수는
  낙관적이다. 호스 경로 길이를 재려면 보행 그래프가 필요하고 이 도구는 거기까지 가지 않는다.
★ 소화전 좌표는 표준데이터 공개분이다. 비공개분은 없다(MASTER §3-12) — 「안 닿는다」는 「없다」가 아니다.

IN    data/processed/segments_5186.gpkg · hydrant_point_5186.gpkg
OUT   data/processed/hydrant_reach.csv (seg_id · hydrant_near_m · tier — processed 산출물이라 커밋 안 한다) · 표준출력
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
    밖    **호스가 실제로 깔리는 길이는 안 본다** — 직선거리만 잰다(하한). 담·건물·고저와 소화전의 작동 여부는 모른다.
"""
from __future__ import annotations

from collections import Counter

#: (이름, 상한 m). 호스 1본 15m · 통상 3본 45m · 10본 = 법정 한계 140m(NFTC 401). 위 등급 밖은 `far`.
TIERS = (("1본", 15.0), ("3본", 45.0), ("10본", 140.0))


def tier(d_m: float) -> str:
    return next((n for n, hi in TIERS if d_m <= hi), "far")


def main() -> int:
    import geopandas as gpd

    from firelane.console import col
    from firelane.paths import PROCESSED

    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg")
    hyd = gpd.read_file(PROCESSED / "hydrant_point_5186.gpkg").to_crs(seg.crs)
    near = gpd.sjoin_nearest(seg[["seg_id", "verdict", "geometry"]], hyd[["geometry"]],
                             how="left", distance_col="d_m")
    near = near.groupby("seg_id").agg(verdict=("verdict", "first"), d_m=("d_m", "min"))
    near["tier"] = near.d_m.map(tier)
    out = near.reset_index()[["seg_id", "d_m", "tier"]].rename(columns={"d_m": "hydrant_near_m"})
    out["hydrant_near_m"] = out.hydrant_near_m.round(1)
    out.to_csv(PROCESSED / "hydrant_reach.csv", index=False)
    print(f"소화전 {len(hyd)} · 구간 {len(seg)} → data/processed/hydrant_reach.csv\n")
    names = [n for n, _ in TIERS] + ["far"]
    print(f"{col('판정', 'c'):>14}{'구간':>7}" + "".join(f"{n:>7}" for n in names))
    for v in ("blocked", "needs_cv", "unknown", "clear"):
        g = near[near.verdict == v]
        c = Counter(g.tier)
        print(f"{v:>10}{len(g):>7}" + "".join(f"{c[n]:>7}" for n in names))
    d = near.d_m
    print(f"\n전체 가장 가까운 소화전까지  중앙 {d.median():.0f}m · p90 {d.quantile(.9):.0f}m · 최대 {d.max():.0f}m")
    print(col("★ 직선거리라 호스 길이의 하한이다. 판정은 아무것도 안 바꿨다.", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

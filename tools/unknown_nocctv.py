#!/usr/bin/env python3
"""
tools/unknown_nocctv.py — CCTV 미설치로 판정 불가한 구간 목록 (PLAN #60)

    uv run python tools/unknown_nocctv.py            목록을 쓴다 + 사유별 수

════════════════════════════════════════════════════════════════
★ 판정을 안 움직인다. `unknown` 447 은 그대로 두고 **목록만** 낸다.
  추정값(`estimated` 등급)을 만들지 않고 판정에 섞지 않는다 — 사람 결정(2026-10-22 · PLAN #60).

── 무엇을 내나 ─────────────────────────────────────────────────
`verdict == unknown` 이고 `unknown_reason` 이 `no_cctv_*` 인 구간. 폭이 3~7m 대(`band`)라 주정차로 갈리거나
(`narrow`) 표본이 얇은데(`thin` · `single`) 영상 없이는 못 가르는 구간이다. `ledger_disputes` 는 CCTV 문제가 아니라
대장 모순이므로 뺀다(수는 따로 찍는다).

각 구간의 중점 좌표(WGS84)를 같이 낸다 — 답사·설치 후보지를 지도에 바로 얹으라는 것이다.

IN    data/processed/segments_5186.gpkg
OUT   data/processed/unknown_no_cctv.csv (UTF-8 BOM · 정렬: 사유 → 길이 내림차순)
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
    밖    **`no_cctv_*` 밖의 `unknown` 사유는 안 센다** — 추정폭·위험도도 안 낸다. 사유별 목록과 수만 낸다.
"""
from __future__ import annotations

import csv
from collections import Counter

COLS = ["seg_uid", "seg_id", "road_name", "seg_label", "unknown_reason", "width_min_m", "width_max_m",
        "road_bt_m", "length_m", "cctv_dist_m", "cv_feasible", "nfa_designated", "route_usage", "lat", "lon"]


def main() -> int:
    import geopandas as gpd
    import pyproj

    from firelane.paths import PROCESSED

    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg")
    unk = seg[seg.verdict == "unknown"]
    got = unk[unk.unknown_reason.astype(str).str.startswith("no_cctv")].copy()
    to4326 = pyproj.Transformer.from_crs(seg.crs, 4326, always_xy=True).transform
    ll = [to4326(p.x, p.y) for p in (g.interpolate(0.5, normalized=True) for g in got.geometry)]
    got["lon"] = [round(x, 6) for x, _ in ll]
    got["lat"] = [round(y, 6) for _, y in ll]
    got = got.sort_values(["unknown_reason", "length_m"], ascending=[True, False])
    dst = PROCESSED / "unknown_no_cctv.csv"
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS)
        for r in got[COLS].itertuples(index=False):
            w.writerow(["" if v != v else v for v in r])
    why = Counter(got.unknown_reason)
    print(f"unknown {len(unk)} 중 CCTV 미설치로 판정 불가 {len(got)} → {dst}")
    for k, n in sorted(why.items()):
        print(f"  {k:16}{n:>5}")
    print(f"  (CCTV 문제가 아니라 뺀 것 {len(unk) - len(got)} — {dict(Counter(unk.unknown_reason) - why)})")
    print(f"  길이 합 {got.length_m.sum() / 1000:.1f}km · 판정은 안 건드렸다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

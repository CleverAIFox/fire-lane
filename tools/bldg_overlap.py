#!/usr/bin/env python3
"""
bldg_overlap.py — 발행 건물에서 **얹은 면이 기존 면과 겹쳐 솟는 것**을 기계가 세고 상위를 뽑는다.  (PLAN #245 · DECISIONS §792-H)

    uv run python tools/bldg_overlap.py              분포 표 + 겹침이 큰 상위 20면(눈으로 볼 목록)
    uv run python tools/bldg_overlap.py --top 50     상위 N면
    uv run python tools/bldg_overlap.py --csv OUT    목록 전체를 파일로(경위도 · 겹침 비율 · 맞댄 기존 면 수)

── 왜 있나 ────────────────────────────────────────────────────
`publish_web._add_gap_buildings` 는 덮임 10% 미만 · 도로 위 절반 이하인 빠진 면만 얹는다. 원천에서는 `bldg_fill.DUP_M`(무게중심 8m) 걸름이 어긋난 같은 건물을 뺀다.
둘 다 **기준이 원천의 면**이라, 발행 단계의 단순화 · 도로 깎임 뒤에 **화면에서** 겹치는 것은 안 센다. 4,037동을 사람이 하나씩 보는 것은 할 일이 아니므로
(사람 지적 · 2026-11-15) 겹침을 **기계가 세고** 사람은 이 목록의 상위만 눈으로 본다.

── 무엇을 세나 ────────────────────────────────────────────────
얹은 면(`publish_web.drop_gap` 이 뺀 면)마다 ① 기존 면과 겹친 면적 ÷ 제 면적 ② 다른 얹은 면과 겹친 면적 ÷ 제 면적 ③ 겹친 상대의 수.
**겹침 = 둘 중 큰 것.** 비율 문턱(0.1% · 1% · 5% · 10%)별 면 수와 면적 합을 내고, 비율이 큰 순서로 목록을 낸다(동률은 면적 큰 순).
번호는 발행 번호라 재발행하면 달라진다(§320) — 정렬 · 조인에 안 쓰고 **무게중심 좌표**로만 가리킨다.

IN    `web/data/buildings.geojson`(발행물 · 5186 으로 바꿔 잰다)
OUT   화면 표 · (`--csv`) 목록 파일. 저장소 파일을 안 쓴다 · 판정을 안 읽는다
PARAM `RATIOS` 0.001 · 0.01 · 0.05 · 0.1
밖    **어느 것이 정말 어긋난 면인지는 안 가린다**(그것은 사람 눈이다 — 목록 상위가 그 대상이다) · 높이 · 지반(묻힘)은 안 본다(PLAN #239) · 얹은 면의 **원천**이 맞는지는 안 본다
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398 — 어느 관문에도 안 올렸다)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
BUILDINGS = ROOT / "web" / "data" / "buildings.geojson"
RATIOS = (0.001, 0.01, 0.05, 0.1)


def split(b: gpd.GeoDataFrame, drop_gap) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """(기존 면, 얹은 면). 가르는 일은 `publish_web.drop_gap` 이 한다 — 그 번호를 만드는 자리가 거기라 밖에서 그 칸을 읽지 않는다(§320)."""
    base = drop_gap(b)
    return base, b.drop(base.index)


def overlaps(base: gpd.GeoDataFrame, added: gpd.GeoDataFrame) -> list[dict]:
    """얹은 면마다 겹침. `added` 의 행 순서대로."""
    bs, asx = base.sindex, added.sindex
    out = []
    for i, geom in enumerate(added.geometry):
        area = geom.area
        r_base = n_base = 0.0
        for j in bs.query(geom, predicate="intersects"):
            a = geom.intersection(base.geometry.iloc[j]).area
            if a > 0:
                r_base += a
                n_base += 1
        r_add = n_add = 0.0
        for j in asx.query(geom, predicate="intersects"):
            if j == i:
                continue
            a = geom.intersection(added.geometry.iloc[j]).area
            if a > 0:
                r_add += a
                n_add += 1
        ratio_base = r_base / area if area > 0 else 0.0
        ratio_add = r_add / area if area > 0 else 0.0
        c = geom.centroid
        out.append({"area_m2": area, "ratio_base": ratio_base, "ratio_added": ratio_add,
                    "ratio": max(ratio_base, ratio_add), "n_base": int(n_base), "n_added": int(n_add),
                    "x": c.x, "y": c.y})
    return out


def table(rows: list[dict]) -> list[str]:
    out = [f"얹은 면 {len(rows)}면 — 겹침 비율(= max(기존 면과 · 다른 얹은 면과)) 문턱별", "  문턱     면 수   면적 합(m²)   (기존 면과만 / 얹은 면끼리만)"]
    for th in RATIOS:
        sel = [r for r in rows if r["ratio"] > th]
        ob = sum(1 for r in sel if r["ratio_base"] > th)
        oa = sum(1 for r in sel if r["ratio_added"] > th)
        out.append(f"  >{th:<6.1%} {len(sel):>6} {sum(r['area_m2'] for r in sel):>13,.0f}   ({ob} / {oa})")
    return out


def top(rows: list[dict], n: int) -> list[str]:
    rk = sorted(rows, key=lambda r: (-r["ratio"], -r["area_m2"]))[:n]
    out = [f"겹침이 큰 상위 {len(rk)}면 — 눈으로 볼 목록(경위도는 무게중심 · 항공뷰에서 겹쳐 솟는지 본다)",
           "  순  겹침   기존과  얹은끼리  면적m²  상대(기존/얹은)   경도 위도"]
    for k, r in enumerate(rk, 1):
        out.append(f"  {k:>2} {r['ratio']:6.1%} {r['ratio_base']:7.1%} {r['ratio_added']:8.1%} {r['area_m2']:8.0f}   {r['n_base']}/{r['n_added']}"
                   f"        {r['lon']:.6f} {r['lat']:.6f}")
    return out


def run(b: gpd.GeoDataFrame, drop_gap, n: int) -> tuple[list[str], list[dict]]:
    base, added = split(b, drop_gap)
    rows = overlaps(base, added)
    pts = gpd.GeoSeries(gpd.points_from_xy([r["x"] for r in rows], [r["y"] for r in rows]), crs=b.crs).to_crs(4326)
    for r, p in zip(rows, pts, strict=True):
        r["lon"], r["lat"] = p.x, p.y
    return table(rows) + [""] + top(rows, n), rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--csv", type=Path)
    a = ap.parse_args(argv)
    from firelane.publish_web import drop_gap
    b = gpd.read_file(BUILDINGS).to_crs(5186)
    lines, rows = run(b, drop_gap, a.top)
    print("\n".join(lines))
    if a.csv:
        with a.csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: (-r["ratio"], -r["area_m2"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

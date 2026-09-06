#!/usr/bin/env python3
"""
tools/its_linkmap.py — ITS 소통정보 링크와 우리 구간을 잇는 대조표.

    uv run python tools/its_linkmap.py
    uv run python tools/its_linkmap.py --write data/processed/its_linkmap.csv

── 왜 필요한가 ─────────────────────────────────────────────────
실시간 교통량은 **간선에서만** 얻을 수 있다. 티맵은 2,000만 사용자
주행 데이터를 프로브로 쓰는데 우리는 사용자가 없다. 대신 국가가 주는
ITS 소통정보 API 가 있고, 그것이 덮는 범위가 우리 통행가능 총연장의
58%(간선·2차로 7m+ 17,865m / 30,979m)다.

    간선 58%   ITS 소통정보 → 구간 속도 → edge_cost
    골목 42%   ITS 도 티맵도 못 덮는다 → CV 실시간 통행폭 + 주정차 β

★ 이 도구는 **표를 만들 뿐 API 를 부르지 않는다.** 실시간 층은 나중에
  누가 붙이든 이 표만 있으면 된다 — `roadsectionid` → `seg_uid[]`.
  키를 저장소에 넣지 않으려는 것이기도 하다.

── 왜 매칭이 어려운가 ──────────────────────────────────────────
★ 표준노드링크는 **교차로에서 위상이 정리된 간선망**이고 우리 구간은
  기초번호 단위다. 하나가 여럿에 걸린다 — 그래서 1:N 표다.

★ `node_link` 는 골목을 안 담는다(폭 2m 이하 링크 3%). 매칭 안 되는
  구간이 많은 것이 **정상이고**, 그 42% 가 우리가 이기는 구간이다.

IN    data/processed/node_link.geojson (또는 gpkg) · web/data/segments.geojson
OUT   stdout · --write 로 CSV
PARAM --tol 25 · --write
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
W = ROOT / "web" / "data"

LAT0 = 35.151
MX = 111320 * math.cos(math.radians(LAT0))
MY = 110574

# 소통정보가 실려 오는 도로등급. 시군도(107)·기타(108)는 번호가 없다.
# 설명자료: 101 고속 · 102 도시고속 · 103 일반국도 · 104 특별광역시도
#          105 국가지원지방도 · 106 지방도 · 107 시군도 · 108 기타
TRAFFIC_RANKS = {"101", "102", "103", "104", "105", "106"}


def _pts(geom: dict) -> list:
    t = geom["type"]
    if t == "LineString":
        return geom["coordinates"]
    if t == "MultiLineString":
        return [p for part in geom["coordinates"] for p in part]
    return []


def _resample(coords: list, step: float = 10.0) -> list:
    """선을 step 미터 간격으로 샘플링한다. 근접 판정을 점 대 점으로 만든다."""
    out = []
    for i in range(len(coords) - 1):
        ax, ay = coords[i][0] * MX, coords[i][1] * MY
        bx, by = coords[i + 1][0] * MX, coords[i + 1][1] * MY
        d = math.hypot(bx - ax, by - ay)
        n = max(1, int(d // step))
        for k in range(n):
            f = k / n
            out.append((ax + (bx - ax) * f, ay + (by - ay) * f))
    if coords:
        out.append((coords[-1][0] * MX, coords[-1][1] * MY))
    return out


def _load_links() -> list:
    """`node_link` 산출물을 찾는다. 이름이 여러 가지라 넓게 찾는다."""
    cands = list(P.glob("node_link*.geojson")) + list(P.glob("*nodelink*.geojson"))
    for c in cands:
        try:
            d = json.load(c.open(encoding="utf-8"))
            if d.get("features"):
                return d["features"]
        except Exception:  # noqa: BLE001 — 다음 후보를 본다
            continue
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=25.0,
                    help="이 거리 안이면 같은 도로로 본다(m)")
    ap.add_argument("--write", help="CSV 경로")
    a = ap.parse_args()

    seg_path = W / "segments.geojson"
    if not seg_path.exists():
        print(f"★ {seg_path} 가 없다.  uv run fire-lane", file=sys.stderr)
        return 1
    segs = json.load(seg_path.open(encoding="utf-8"))["features"]

    links = _load_links()
    if not links:
        print("★ node_link 산출물을 못 찾았다.", file=sys.stderr)
        print("  `ingest` 는 돌았지만 processed 에 geojson 이 없을 수 있다.",
              file=sys.stderr)
        print("  publish 에서 node_link 를 내보내거나 gpkg 를 변환해라.",
              file=sys.stderr)
        return 1

    # 우리 구간을 격자에 넣는다.
    grid = defaultdict(list)
    for i, f in enumerate(segs):
        for x, y in _resample(_pts(f["geometry"])):
            grid[(int(x // a.tol), int(y // a.tol))].append((x, y, i))

    rows = []
    matched_seg = set()
    skipped_rank = 0
    for lf in links:
        p = lf["properties"]
        rank = str(p.get("ROAD_RANK") or "")
        if rank and rank not in TRAFFIC_RANKS:
            skipped_rank += 1
            continue
        hits = defaultdict(lambda: [0, 1e18])   # seg idx → [표본수, 최소거리]
        for x, y in _resample(_pts(lf["geometry"])):
            kx, ky = int(x // a.tol), int(y // a.tol)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for sx, sy, si in grid.get((kx + dx, ky + dy), ()):
                        d = math.hypot(sx - x, sy - y)
                        if d <= a.tol:
                            h = hits[si]
                            h[0] += 1
                            h[1] = min(h[1], d)
        for si, (n, d) in hits.items():
            sp = segs[si]["properties"]
            rows.append({
                "link_id": p.get("LINK_ID"),
                "road_rank": rank,
                "road_name_link": p.get("ROAD_NAME"),
                "lanes": p.get("LANES"),
                "max_spd": p.get("MAX_SPD"),
                "seg_uid": sp.get("seg_uid"),
                "seg_label": sp.get("seg_label"),
                "road_name_seg": sp.get("road_name"),
                "width_min_m": sp.get("width_min_m"),
                "samples": n,
                "min_dist_m": round(d, 1),
            })
            matched_seg.add(si)

    # ── 요약 ──────────────────────────────────────────────────
    passable = [i for i, f in enumerate(segs)
                if f["properties"]["verdict"] != "blocked"
                and (f["properties"].get("width_min_m") or 0) >= 3.0]
    cover = [i for i in passable if i in matched_seg]
    plen = sum(segs[i]["properties"].get("length_m") or 0 for i in passable)
    clen = sum(segs[i]["properties"].get("length_m") or 0 for i in cover)

    print("── ITS 소통정보 커버리지 ──────────────────────────")
    print(f"  링크          {len(links)} (등급 밖 제외 {skipped_rank})")
    print(f"  매칭 쌍       {len(rows)}")
    print(f"  통행가능 구간  {len(cover)}/{len(passable)} "
          f"({len(cover) / max(1, len(passable)) * 100:.0f}%)")
    print(f"  통행가능 연장  {clen:,.0f}m / {plen:,.0f}m "
          f"({clen / max(1, plen) * 100:.0f}%)")
    print()
    print("  → 덮이는 곳은 ITS 로, 안 덮이는 곳은 CV·주정차 β 로 간다.")
    print("     티맵도 골목은 프로브가 성기다 — 거기가 우리가 이기는 구간이다.")

    if a.write and rows:
        out = Path(a.write)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n→ {out}  ({len(rows)}행)")
        print("  실시간 층은 이 표만 있으면 붙는다 — roadsectionid → seg_uid[]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

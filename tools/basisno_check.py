#!/usr/bin/env python3
"""
tools/basisno_check.py — seg_label 의 기초번호를 상가 주소와 대조한다.

    uv run python tools/basisno_check.py

── 무엇을 보는가 ──────────────────────────────────────────────
`road_intrvl`(기초구간) 은 도로명주소법의 기초번호를 값으로 갖는다.
그 값이 실제 건물 주소와 맞는지 `poi_store`(소상공인 상가정보) 로 본다.

★ 이 대조는 진짜 독립 검증이다. 이전 판은 poi_store 로 오프셋을
  보정한 뒤 같은 자료로 정확도를 주장했다 — MASTER §4 가 경고한
  fit-vs-검증 함정이었다. 지금은 보정이 없으므로 poi_store 가
  외부 기준으로 남는다.

상가만 담아 표본이 상업지에 치우친다. 절대 정확도보다 **어긋난 도로가
어디인가**를 보는 데 쓴다.
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "etl"))
from seg.basisno import BasisIntervalIndex  # noqa: E402

P = Path("data/processed")


def main() -> int:
    for f in ("road_intrvl.geojson", "poi_store.geojson", "road_link.geojson"):
        if not (P / f).exists():
            print(f"없음: {P / f} — pipeline 을 먼저 돌려라")
            return 1

    road = gpd.read_file(P / "road_link.geojson")
    intrvl = gpd.read_file(P / "road_intrvl.geojson")
    poi = gpd.read_file(P / "poi_store.geojson")
    for g in (intrvl, poi):
        if road.crs is not None and g.crs != road.crs:
            g.to_crs(road.crs, inplace=True)

    ix = BasisIntervalIndex.from_gdf(intrvl)
    n_num = sum(1 for x in ix.odd if x is not None)
    print(f"기초구간 {len(intrvl)}개 · 홀수번호 보유 {n_num}개")

    rows = []
    for rn, num, geom in zip(poi["도로명"], poi["건물본번지"], poi.geometry):
        if rn is None or geom is None or geom.is_empty:
            continue
        try:
            actual = int(num)
        except (TypeError, ValueError):
            continue
        if actual <= 0:
            continue
        # 상가는 점이다. 아주 작은 선으로 만들어 겹침 질의에 태운다.
        hits = ix._hits(geom.buffer(8.0).exterior)
        if not hits:
            continue
        best = min(hits, key=lambda h: abs(h[1] - actual))
        rows.append((str(rn).split()[-1], actual, best[1]))

    if not rows:
        print("대조 가능한 상가가 없다.")
        return 1

    byrn = collections.defaultdict(list)
    for rn, a, c in rows:
        byrn[rn].append(a - c)
    devs = np.array([a - c for _, a, c in rows])

    print(f"\n대조 {len(rows)}건 · 도로명 {len(byrn)}개")
    print(f"  중앙 편차 {np.median(devs):+.0f}"
          f" · 평균 {devs.mean():+.1f}"
          f" · |편차|<=2 비율 {(np.abs(devs) <= 2).mean():.1%}"
          f" · |편차|<=4 비율 {(np.abs(devs) <= 4).mean():.1%}")

    print("\n★ 어긋난 도로 (표본 5건 이상 · |중앙편차| 5 초과)")
    hits = 0
    for rn, ds in sorted(byrn.items(), key=lambda x: -abs(np.median(x[1]))):
        if len(ds) < 5:
            continue
        med = float(np.median(ds))
        if abs(med) > 5:
            print(f"  {rn:24s} n={len(ds):4d}  중앙편차 {med:+6.0f}"
                  f"  IQR {np.percentile(ds, 75) - np.percentile(ds, 25):.0f}")
            hits += 1
        if hits >= 15:
            break
    if not hits:
        print("  없음 — 기초구간 값이 주소와 일치한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

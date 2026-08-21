#!/usr/bin/env python3
"""
tools/basisno_check.py — 계산한 기초번호를 실제 건물번호와 대조한다.

    uv run python tools/basisno_check.py

── 왜 poi_store 인가 ──────────────────────────────────────────
처음에는 `building_entrance.geojson` 을 쓰려 했으나 그 레이어는
수치지형도 출입구라 주소가 없다 — `BUL_MAN_NO` · `ENTRC_SE` · `SIG_CD` 뿐.

`poi_store.geojson`(소상공인 상가정보) 은 8,599건에 `도로명` ·
`건물본번지` · 좌표를 전부 갖고 있다. 상가만 담아 표본이 상업지에
치우치지만, **기점 방향이 뒤집혔는지**를 보는 데는 충분하다.

★ 이 검사의 목적은 정밀도가 아니라 방향 확인이다.
  한 도로에서 편차가 일관되게 한쪽으로 쏠리면 그 도로의 기점 방향이
  뒤집힌 것이다. `seg/basisno.py` 의 REVERSED 에 그 도로명만 넣어라.
  전역 규칙으로 바꾸면 맞던 도로가 전부 틀어진다.
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "etl"))
from seg.basisno import BasisNumberIndex, basis_no  # noqa: E402

P = Path("data/processed")
POI = P / "poi_store.geojson"
ROAD = P / "road_link.geojson"


def main() -> int:
    for f in (POI, ROAD):
        if not f.exists():
            print(f"없음: {f} — pipeline 을 먼저 돌려라")
            return 1

    road = gpd.read_file(ROAD)
    poi = gpd.read_file(POI)
    if poi.crs != road.crs:
        poi = poi.to_crs(road.crs)

    if "도로명" not in poi.columns or "건물본번지" not in poi.columns:
        print(f"컬럼 없음. 보유: {list(poi.columns)}")
        return 1

    bnx = BasisNumberIndex.from_gdf(road)
    n_off = bnx.load_offsets()
    print(f"도로 {len(bnx.line)}개 · BSI_INT {len(bnx.interval)}개 · 오프셋 {n_off}개")
    if n_off == 0:
        print("  ★ data/basisno_offset.json 없음 — "
              "tools/basisno_calibrate.py 를 먼저 돌려라.\n"
              "    본선은 클리핑 때문에 편차가 크게 나온다.")

    rows = []
    # poi 의 도로명은 '전남광주통합특별시 동구 충장로안길' 처럼 풀네임이다.
    # road_link 의 RN 은 '충장로안길'. 마지막 토큰만 쓴다.
    for rn, num, geom in zip(poi["도로명"], poi["건물본번지"], poi.geometry):
        if rn is None or geom is None or geom.is_empty:
            continue
        rn = str(rn).split()[-1]
        try:
            actual = int(num)
        except (TypeError, ValueError):
            continue
        if actual <= 0:
            continue
        base = bnx.line.get(str(rn))
        if base is None:
            continue
        iv = bnx.interval.get(str(rn), 20.0)
        off = int(bnx.offset.get(str(rn), 0))
        rows.append((str(rn), actual, basis_no(base.project(geom), iv) + off))

    if not rows:
        print("대조 가능한 상가가 없다. 도로명 표기가 서로 다를 수 있다.")
        print(f"  poi 도로명 예: {list(poi['도로명'].dropna().unique()[:5])}")
        print(f"  road RN  예: {list(road['RN'].dropna().unique()[:5])}")
        return 1

    byrn = collections.defaultdict(list)
    for rn, a, c in rows:
        byrn[rn].append(a - c)

    devs = np.array([a - c for _, a, c in rows])
    print(f"\n대조 {len(rows)}건 · 도로명 {len(byrn)}개")
    print(f"  중앙 편차 {np.median(devs):+.0f}"
          f" · 평균 {devs.mean():+.1f}"
          f" · |편차|<=4 비율 {(np.abs(devs) <= 4).mean():.1%}")
    print()
    print("★ 계통적 역전 의심 (편차가 크고 한쪽으로 쏠린 도로)")

    hits = 0
    for rn, ds in sorted(byrn.items(), key=lambda x: -abs(np.median(x[1]))):
        if len(ds) < 5:
            continue
        med = float(np.median(ds))
        same_sign = float((np.sign(ds) == np.sign(med)).mean())
        if abs(med) >= 10 and same_sign >= 0.8:
            print(f"  {rn:24s} n={len(ds):4d}  중앙편차 {med:+7.0f}  동일부호 {same_sign:.0%}")
            hits += 1
        if hits >= 20:
            break
    if not hits:
        print("  없음 — 기점 방향 가정이 유효하다")

    print()
    print("가장 잘 맞는 도로 (표본 10건 이상)")
    good = [(rn, float(np.median(ds)), len(ds))
            for rn, ds in byrn.items() if len(ds) >= 10]
    for rn, med, n in sorted(good, key=lambda x: abs(x[1]))[:8]:
        print(f"  {rn:24s} n={n:4d}  중앙편차 {med:+5.0f}")

    if bnx.unmerged:
        print()
        print(f"선이 끊긴 도로명 {len(bnx.unmerged)}개 — 해당 구간은 번호가 어긋날 수 있다")
        for rn in sorted(bnx.unmerged)[:10]:
            print(f"  {rn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

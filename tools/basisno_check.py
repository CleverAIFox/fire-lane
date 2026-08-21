#!/usr/bin/env python3
"""
tools/basisno_check.py — 계산한 기초번호를 실제 건물번호와 대조한다.

    uv run python tools/basisno_check.py

★ 가장 중요한 출력은 '계통적 역전' 이다. 한 도로명에서 계산값과 실제값이
  일관되게 반대 방향으로 어긋나면 그 도로의 기점 방향이 뒤집힌 것이다.
  seg/basisno.py 의 REVERSED 에 그 도로명만 넣어라. 전역 규칙으로 바꾸면
  맞던 도로가 전부 틀어진다.
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
ENT = P / "building_entrance.geojson"
ROAD = P / "road_link.geojson"

NUM_CANDIDATES = ("BULD_MNNM", "건물본번", "BLD_MAIN_NO", "buld_mnnm")
RN_CANDIDATES = ("RN", "도로명", "ROAD_NM", "rn", "RD_NM")


def main() -> int:
    for f in (ENT, ROAD):
        if not f.exists():
            print(f"없음: {f} — pipeline 을 먼저 돌려라")
            return 1

    road = gpd.read_file(ROAD)
    ent = gpd.read_file(ENT)
    if ent.crs != road.crs:
        ent = ent.to_crs(road.crs)

    numcol = next((c for c in NUM_CANDIDATES if c in ent.columns), None)
    rncol = next((c for c in RN_CANDIDATES if c in ent.columns), None)
    if numcol is None or rncol is None:
        print("건물번호/도로명 컬럼을 못 찾았다.")
        print(f"보유 컬럼: {list(ent.columns)}")
        return 1

    bnx = BasisNumberIndex.from_gdf(road)

    rows = []
    for _, r in ent.iterrows():
        rn = r[rncol]
        try:
            actual = int(r[numcol])
        except (TypeError, ValueError):
            continue
        if rn is None or actual <= 0:
            continue
        base = bnx.line.get(str(rn))
        if base is None:
            continue
        rows.append((str(rn), actual, basis_no(base.project(r.geometry))))

    if not rows:
        print("대조 가능한 출입구가 없다. 도로명 표기가 서로 다를 수 있다.")
        return 1

    byrn = collections.defaultdict(list)
    for rn, a, c in rows:
        byrn[rn].append(a - c)

    devs = np.array([a - c for _, a, c in rows])
    print(f"대조 {len(rows)}건 · 도로명 {len(byrn)}개")
    print(f"  중앙 편차 {np.median(devs):+.0f}"
          f" · 평균 {devs.mean():+.1f}"
          f" · |편차|<=2 비율 {(np.abs(devs) <= 2).mean():.1%}")
    print()
    print("★ 계통적 역전 의심 (편차가 크고 한쪽으로 쏠린 도로)")

    hits = 0
    for rn, ds in sorted(byrn.items(), key=lambda x: -abs(np.median(x[1]))):
        if len(ds) < 4:
            continue
        med = float(np.median(ds))
        same_sign = float((np.sign(ds) == np.sign(med)).mean())
        if abs(med) >= 8 and same_sign >= 0.8:
            print(f"  {rn:24s} n={len(ds):3d}  중앙편차 {med:+6.0f}  동일부호 {same_sign:.0%}")
            hits += 1
        if hits >= 15:
            break
    if not hits:
        print("  없음 — 기점 방향 가정이 유효하다")

    if bnx.unmerged:
        print()
        print(f"선이 끊긴 도로명 {len(bnx.unmerged)}개 — 해당 구간은 번호가 어긋날 수 있다")
        for rn in sorted(bnx.unmerged)[:10]:
            print(f"  {rn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
streetlight.py — 가로등 원본 → 지점 단위 집계


IN    processed/streetlight_5186.gpkg     ★ RAW 를 직접 읽지 않는다
OUT   processed/streetlight_point.geojson
PARAM pos_accuracy_m=50 (지번 대표점 반경)

    python -m firelane.streetlight

★ processed 계층에서 읽는다. RAW 를 직접 읽지 않는다.
  ingest.py 가 이미 스코프 필터 + 좌표 파싱을 끝낸 streetlight_5186.gpkg 를
  만든다. 여기서 RAW 를 다시 읽으면 정본이 둘이 되고, 실제로 그랬다
  (ingest 1786 vs segments.py 가 RAW 에서 읽은 3805).
  segments.py 의 light_count 도 향후 이 산출물로 통일한다.

★ distinct 를 쓰지 않는다. (MASTER §6 · 2026-08-14 개정)
  좌표당 1행만 남기면 등 수의 93% 를 날린다. 중복 행이 아니라
  지번 대표점으로 좌표만 뭉쳐진 서로 다른 등이다.
  group-by + count 로 등 수를 보존한다.

★ 이 좌표는 실제 폴 위치가 아니다.
  지번 단위 회로 대표점이다. pos_accuracy_m = 50 을 실어 보내
  UI 가 반경 50m 원을 그리게 한다. 점만 찍으면 "여기 가로등 1개"라는
  거짓말이 된다.
  실제 폴 위치는 C0220000(수치지형도 가로등·보안등 점) 편입으로 대체 예정.

산출
    data/processed/streetlight_point.geojson
      n_lights        이 지점에 묶인 등 수
      mgmt_no_sample  관리번호 예시(최대 3). 현장 대조용
      addr            소재지
      pos_accuracy_m  50
      verified        false
"""
from __future__ import annotations

import sys

import geopandas as gpd
import pandas as pd

from firelane.paths import PROCESSED

POS_ACCURACY_M = 50
COORD_PRECISION = 6          # 6자리 ≈ 11cm. 원본이 같은 지번에 동일 좌표를 준다

MGMT_CANDIDATES = ("관리번호", "가로등번호", "등번호", "시설물관리번호", "고유번호")
ADDR_CANDIDATES = ("소재지지번주소", "소재지도로명주소", "설치장소", "주소", "소재지")


def _pick(cols, cands):
    return next((c for c in cands if c in cols), None)


def main() -> None:
    src = PROCESSED / "streetlight_5186.gpkg"
    if not src.exists():
        # ★ 조용히 넘기지 않는다. 없으면 마커가 통째로 사라진다.
        print(f"! {src} 없음 — ingest 를 먼저 실행하라")
        sys.exit(1)

    g = gpd.read_file(src).to_crs(4326)
    n_raw = len(g)

    g["_lon"] = g.geometry.x.round(COORD_PRECISION)
    g["_lat"] = g.geometry.y.round(COORD_PRECISION)

    mgmt = _pick(g.columns, MGMT_CANDIDATES)
    addr = _pick(g.columns, ADDR_CANDIDATES)

    out = g.groupby(["_lon", "_lat"], as_index=False).size()
    out = out.rename(columns={"size": "n_lights"})

    if mgmt:
        s = (g.groupby(["_lon", "_lat"])[mgmt]
               .apply(lambda v: " / ".join(map(str, v.head(3))))
               .reset_index(name="mgmt_no_sample"))
        out = out.merge(s, on=["_lon", "_lat"], how="left")
    else:
        out["mgmt_no_sample"] = None

    if addr:
        s = g.groupby(["_lon", "_lat"])[addr].first().reset_index(name="addr")
        out = out.merge(s, on=["_lon", "_lat"], how="left")
    else:
        out["addr"] = None

    out["pos_accuracy_m"] = POS_ACCURACY_M
    out["verified"] = False

    gdf = gpd.GeoDataFrame(
        out.drop(columns=["_lon", "_lat"]),
        geometry=gpd.points_from_xy(out["_lon"], out["_lat"]),
        crs=4326,
    )

    dst = PROCESSED / "streetlight_point.geojson"
    dst.unlink(missing_ok=True)
    gdf.to_file(dst, driver="GeoJSON", COORDINATE_PRECISION=6)

    tot = int(gdf.n_lights.sum())
    print(f"  가로등 {n_raw}등 → {len(gdf)}지점 (등 수 보존 {tot})")
    print(f"  지점당 중앙 {gdf.n_lights.median():.0f} · 최대 {gdf.n_lights.max()}")

    # ★ 등 수 합이 입력과 다르면 어딘가에서 행이 사라진 것이다.
    if tot != n_raw:
        print(f"  ! 등 수 합 불일치 {tot} != {n_raw} — 좌표 결측 확인")
        sys.exit(1)
    print(f"  → {dst}")


if __name__ == "__main__":
    main()

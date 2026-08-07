"""정사영상 도엽 → 지오레퍼런싱 부여 → 동명동 모자이크.

배치: src/etl/crop_ortho.py
실행: uv run python src/etl/crop_ortho.py

배경
----
국토정보플랫폼이 배포하는 정사영상 .tif 는 GeoTIFF 가 아니며 .tfw 도
동봉되지 않는다. 메타데이터 XML 에도 도곽 좌표가 없다.
아래 규칙으로 원점을 복원한다. (2026-08-06 확정, 3중 검증)

  1. 도곽 = 경위도 1'30" x 1'30" 격자
     (함께 받은 수치지도 bounds 역산, 오차 0.5" 이내)
  2. 정사영상 = 도곽 + 사방 50m
     (4개 도엽의 영상 폭을 전부 1픽셀 이내로 예측)
  3. 수치지도 도로경계선 오버레이 육안 확인 완료

잔여 절대위치 오차 ±1~2m. 전역 평행이동이므로 폭 측정에는 영향 없음.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.windows import Window
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "ortho"
OUT = ROOT / "data" / "processed" / "dongmyeong_ortho.tif"

RES = 0.25                       # GSD (m/px)
MARGIN = 50.0                    # 도곽 대비 여백 (m)
STEP = 90 / 3600.0               # 도곽 1'30"
CRS = "EPSG:5186"
BBOX_WGS84 = (126.918, 35.145, 126.932, 35.156)   # 동명동 + 여유

# 도엽번호 -> 도곽 남서단 (경도, 위도)
SHEETS = {
    "35616037": (126 + 54 / 60, 35 + 9 / 60),      # 북서 (북구 중흥동)
    "35616038": (126 + 55.5 / 60, 35 + 9 / 60),    # 북동 (북구 두암동)
    "35616047": (126 + 54 / 60, 35 + 7.5 / 60),    # 남서 (남구 양림동)
    "35616048": (126 + 55.5 / 60, 35 + 7.5 / 60),  # 남동 (동구 학동)
}

_to = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)


def origin(lon: float, lat: float) -> tuple[float, float]:
    """도곽 남서단 경위도 -> 정사영상 좌상단 (X0, Y0) in EPSG:5186."""
    corners = [(lon, lat), (lon + STEP, lat),
               (lon + STEP, lat + STEP), (lon, lat + STEP)]
    poly = Polygon([_to.transform(x, y) for x, y in corners])
    b = poly.buffer(MARGIN, join_style=2).bounds
    return b[0], b[3]


def write_world_files() -> None:
    """원본 .tif 옆에 .tfw / .prj 생성."""
    from pyproj import CRS as _CRS
    wkt = _CRS.from_epsg(5186).to_wkt()
    for sheet, (lon, lat) in SHEETS.items():
        x0, y0 = origin(lon, lat)
        for tif in RAW.glob(f"*{sheet}*.tif"):
            tif.with_suffix(".tfw").write_text(
                f"{RES:.10f}\n0.0\n0.0\n{-RES:.10f}\n{x0:.4f}\n{y0:.4f}\n")
            tif.with_suffix(".prj").write_text(wkt)
            print(f"  {tif.name}  X0={x0:.2f} Y0={y0:.2f}")


def main() -> None:
    print("월드파일 생성")
    write_world_files()

    xs, ys = [], []
    for lon, lat in [(BBOX_WGS84[0], BBOX_WGS84[1]), (BBOX_WGS84[2], BBOX_WGS84[3])]:
        x, y = _to.transform(lon, lat)
        xs.append(x)
        ys.append(y)
    minx, maxx = min(xs) - 100, max(xs) + 100
    miny, maxy = min(ys) - 100, max(ys) + 100
    w, h = int((maxx - minx) / RES), int((maxy - miny) / RES)

    out = np.zeros((3, h, w), np.uint8)
    for sheet, (lon, lat) in SHEETS.items():
        tifs = list(RAW.glob(f"*{sheet}*.tif"))
        if not tifs:
            print(f"  ! {sheet} 없음 — 건너뜀")
            continue
        x0, y0 = origin(lon, lat)
        with rasterio.open(tifs[0]) as s:
            c0, r0 = int(round((minx - x0) / RES)), int(round((y0 - maxy) / RES))
            cc0, cc1 = max(0, c0), min(s.width, c0 + w)
            rr0, rr1 = max(0, r0), min(s.height, r0 + h)
            if cc1 <= cc0 or rr1 <= rr0:
                continue
            a = s.read(window=Window(cc0, rr0, cc1 - cc0, rr1 - rr0))
        tgt = out[:, rr0 - r0: rr0 - r0 + a.shape[1], cc0 - c0: cc0 - c0 + a.shape[2]]
        empty = tgt.sum(0) == 0
        tgt[:, empty] = a[:, empty]
        print(f"  merged {sheet} {a.shape[2]}x{a.shape[1]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = dict(driver="GTiff", height=h, width=w, count=3, dtype="uint8",
                crs=CRS, transform=from_origin(minx, maxy, RES, RES),
                compress="deflate", predictor=2, tiled=True)
    with rasterio.open(OUT, "w", **meta) as d:
        d.write(out)
    print(f"완료 {OUT.name}  {w}x{h}px = {w*RES:.0f}m x {h*RES:.0f}m  "
          f"{OUT.stat().st_size/1e6:.1f}MB")


if __name__ == "__main__":
    main()

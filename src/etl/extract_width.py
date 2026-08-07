"""도로폭 추출 — 소스 독립 파이프라인.

배치: src/etl/extract_width.py
실행: uv run python src/etl/extract_width.py

설계 원칙
---------
1. 소스를 하나로 고정하지 않는다. `width_src` 컬럼으로 출처를 기록하고,
   더 나은 소스가 나오면 이 파일의 SOURCES 딕셔너리만 고친다.
2. 모든 폭은 **두 가지 방법**으로 계산하고 불일치 구간을 먼저 리포트한다.
   (2026-08-06 사고: 수직선법 단독 사용 → 폴리곤 분할로 폭이 절반으로
    계산됐고 현장 답사에서야 발견됨. 재발 방지 장치.)
3. 실측 5곳(data/raw/field_survey_20260806.csv)이 유일한 정답지다.
   새 소스는 반드시 이 5곳 대조를 통과해야 채택한다.

출력
----
data/processed/road_width.csv
  segment_id, width_m, width_src, width_min_m, method_a, method_b, disagree_m, flag
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import shapefile
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString, Point, shape
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

CRS_WORK = "EPSG:5186"          # 정사영상·수치지도 작업 좌표계
RES = 0.25                       # 래스터 격자 (정사영상 GSD와 동일)
DISAGREE_TOL = 0.5               # 두 방법 차이 허용치 (m)

# ─────────────────────────────────────────────────────────────
# 폭 소스 등록부. 우선순위 순.
# 2026-08-06 실측 5곳 대조 결과(평균오차):
#   ngii_digitalmap 0.77m  <  road_bt 1.61m  <  silpok 1.86m
# 아직 어느 것도 확정 채택 아님. n=3으로 통계 불가.
# ─────────────────────────────────────────────────────────────
SOURCES = {
    "ngii_digitalmap": {
        "kind": "polygon",
        "path": RAW / "digitalmap",
        "layer": "NF_A_A01000",     # 도로경계면
        "crs": "EPSG:5179",
        "mae": 0.77,
    },
    "silpok": {
        "kind": "polygon",
        "path": RAW / "silpok",
        "layer": "TL_SPRD_RW",
        "crs": "EPSG:5179",
        "mae": 1.86,
    },
    # "ortho_seg": 정사영상 세그멘테이션. 미구현.
}


def load_polygons(src: dict):
    """소스에서 도로 폴리곤을 읽어 작업 좌표계로 변환."""
    tf = Transformer.from_crs(src["crs"], CRS_WORK, always_xy=True).transform
    polys = []
    for shp in sorted(Path(src["path"]).rglob(f"{src['layer']}*.shp")):
        r = shapefile.Reader(str(shp)[:-4])
        for sh in r.iterShapes():
            g = shape(sh.__geo_interface__).buffer(0)
            if not g.is_empty:
                polys.append(shp_transform(tf, g))
    if not polys:
        raise FileNotFoundError(f"폴리곤 없음: {src['path']}/{src['layer']}")
    return unary_union(polys)


def width_distance_transform(road, line: LineString, pad: float = 60.0):
    """방법 A — 거리변환. 도로 마스크의 중심축 값 × 2.

    폴리곤 파싱을 하지 않고 래스터 연산만 하므로, 폴리곤이 쪼개져
    있어도 폭이 절반으로 잘리지 않는다.
    """
    out = []
    n = max(3, int(line.length // 5))
    for k in range(1, n):
        p = line.interpolate(line.length * k / n)
        x0, y0 = p.x - pad, p.y + pad
        size = int(2 * pad / RES)
        sub = road.intersection(p.buffer(pad * 1.2))
        if sub.is_empty:
            continue
        m = rasterize([(sub, 1)], out_shape=(size, size),
                      transform=from_origin(x0, y0, RES, RES), dtype="uint8")
        d = distance_transform_edt(m) * RES * 2
        r, c = size // 2, size // 2
        win = d[max(0, r - 40):r + 40, max(0, c - 40):c + 40]
        if win.size and win.max() > 0:
            out.append(float(win.max()))
    return out


def width_area_over_length(road, line: LineString, band: float = 8.0):
    """방법 B — 면적 ÷ 길이. 전역 평균이라 국소 오류에 둔감."""
    seg = line.buffer(band).intersection(road)
    return seg.area / line.length if line.length else None


def main() -> None:
    seg_path = PROC / "road_segment_master.geojson"
    segs = json.loads(seg_path.read_text(encoding="utf-8"))["features"]
    to_work = Transformer.from_crs("EPSG:4326", CRS_WORK, always_xy=True).transform

    src_name = sys.argv[1] if len(sys.argv) > 1 else "ngii_digitalmap"
    if src_name not in SOURCES:
        raise SystemExit(f"알 수 없는 소스: {src_name} (가능: {list(SOURCES)})")
    road = load_polygons(SOURCES[src_name])
    print(f"소스={src_name}  도로면적={road.area:,.0f}m²")

    rows, disagree = [], 0
    for f in segs:
        p = f["properties"]
        g = shape(f["geometry"])
        g = g if g.geom_type == "LineString" else max(g.geoms, key=lambda x: x.length)
        line = shp_transform(to_work, g)

        a_all = width_distance_transform(road, line)
        a = float(np.median(a_all)) if a_all else None
        a_min = float(np.min(a_all)) if a_all else None
        b = width_area_over_length(road, line)

        gap = abs(a - b) if (a and b) else None
        flag = ""
        if a is None and b is None:
            flag = "NO_DATA"
        elif gap is not None and gap > DISAGREE_TOL:
            flag = "DISAGREE"
            disagree += 1

        rows.append({
            "segment_id": p["segment_id"],
            "road_name": p["road_name"],
            "width_m": round(a, 2) if a else (round(b, 2) if b else ""),
            "width_src": src_name,
            "width_min_m": round(a_min, 2) if a_min else "",
            "method_a": round(a, 2) if a else "",
            "method_b": round(b, 2) if b else "",
            "disagree_m": round(gap, 2) if gap else "",
            "flag": flag,
        })

    import csv
    out = PROC / "road_width.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    ok = sum(1 for r in rows if r["flag"] == "")
    print(f"완료 {out.name}  정상 {ok} / 불일치 {disagree} / "
          f"결측 {sum(1 for r in rows if r['flag'] == 'NO_DATA')}")
    if disagree:
        print("\n[불일치 상위 10]  ← 이것부터 확인할 것")
        bad = sorted((r for r in rows if r["flag"] == "DISAGREE"),
                     key=lambda r: -r["disagree_m"])[:10]
        for r in bad:
            print(f"  {r['segment_id']:10} {r['road_name']:14} "
                  f"A={r['method_a']:>6} B={r['method_b']:>6} Δ={r['disagree_m']}")


if __name__ == "__main__":
    main()

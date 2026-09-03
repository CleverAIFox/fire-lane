#!/usr/bin/env python3
"""
ortho.py — 항공정사영상을 지오레퍼런싱해 배경 타일로 굽는다.


IN    $FIRE_LANE_DATA/raw/ngii/ngii_ortho_*.tif + .xml  (도엽 4장)
OUT   web/data/ortho/**  (배경 타일)
      ★ web/data/view.json 에 orthoBounds 를 덧쓴다 · _manifest.json 에 기록
IN2   web/data/scope.geojson  ★ publish 산출을 읽는다. **후진 의존이다** —
      스코프가 바뀌면 정사영상이 한 실행 늦게 따라온다
      (tests/test_guards.py::BACKWARD · PLAN)
      processed/_manifest.json 의 ortho 절
PARAM 도엽 격자 역산 상수(EPSG:5186 TM 중부원점)

  ingest.py → segments.py → terrain.py → **ortho.py** → publish_web.py

★ 원본 TIF 에는 좌표 정보가 없다.
  메타데이터 XML 에 "TM 중부원점 / GRS80 / Easting 200000 / Northing 600000"
  즉 EPSG:5186 이라고만 적혀 있고, geotransform 은 파일에 안 들어 있다.
  그래서 도엽 격자로 좌표를 역산해 붙인다.

  검증 근거: 같은 도엽의 수치지도(5179)와 도엽 간격이 일치한다.
      동서 2277.2m · 남북 2772.5m
  정사영상은 2379 x 2874m 로 도엽보다 크다. 사방 약 51m 오버랩이다.

★ 해상도 25cm. V-World 위성영상보다 훨씬 선명하다.
  다만 판정에는 쓰지 않는다. 폭은 벡터(실폭도로·건물 폴리곤)로 잰다.
  래스터에서 도로 경계를 읽으려면 세그멘테이션이 필요하고,
  그림자·처마·주차 차량 때문에 정확도가 안 나온다.

산출
  web/data/ortho/{z}/{x}/{y}.jpg   스코프 범위 배경 타일
"""
from __future__ import annotations

import json
import math
import shutil
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject

# 대장 조회기는 하나다(firelane.ledger.globs).
from firelane import ledger as _led
from firelane import naming as nm
from firelane import quiet_gdal
from firelane.paths import PROCESSED, RAW, WEB

# ★ import 부수효과가 아니라 명시 호출이다. 종전에는 `import quiet_gdal` 이
#   rasterio 앞에 와야 한다는 순서 제약을 주석으로만 걸어놨고, ruff 의
#   import 정렬(I001)이 그것을 언제든 깨뜨릴 수 있었다. 지금은 호출 시점이
#   코드에 적혀 있으므로 import 순서와 무관하다.
quiet_gdal.disable_sidecar_scan()   # 정사영상 옆 .xml 을 GDAL 이 읽지 않게

OUT = PROCESSED



ORTHO_CRS = "EPSG:5186"     # TM 중부원점. 메타데이터 XML 기준
GSD = 0.25                  # 지상표본거리(m)
TILE_Z = (15, 16, 17, 18, 19)
# 원본 GSD 는 0.25m/px 다(캔버스 11540px / 2885m). z18 은 0.488m/px 라
# 원본 해상도의 절반을 버린다. z19 가 0.244m/px 로 원본과 맞는다.
# 3m 골목이 z18 에서 6px, z19 에서 12px — 책상 대조(desk_check.py)가
# 쓸모 있으려면 후자가 필요하다. 타일은 4배(≈1,500장 · 30MB).
TILE_PX = 256
JPEG_Q = 82

# 도엽 좌상단(5186). 수치지도 도엽 bbox 를 5186 으로 변환해 산출한 값이다.
# 정사영상은 도엽보다 사방 약 51m 크므로 그만큼 바깥에서 시작한다.
SHEET_5179 = {
    "037": (945348.7, 1684013.9, 947641.9, 1686799.9),
    "038": (947625.9, 1684001.1, 949918.4, 1686786.5),
    "047": (945332.0, 1681241.4, 947625.9, 1684027.4),
    "048": (947609.9, 1681228.5, 949903.0, 1684013.9),
}


def sheet_origin_5186(key: str, w_px: int, h_px: int) -> Affine:
    """도엽 bbox(5179)를 5186 으로 옮겨 정사영상 transform 을 만든다.

    영상이 도엽보다 큰 만큼(사방 약 51m) 좌상단을 바깥으로 밀어낸다.
    """
    b = SHEET_5179[key]
    box = gpd.GeoSeries.from_wkt(
        [f"POLYGON(({b[0]} {b[1]},{b[2]} {b[1]},{b[2]} {b[3]},{b[0]} {b[3]},{b[0]} {b[1]}))"],
        crs=5179).to_crs(ORTHO_CRS).total_bounds
    sheet_w, sheet_h = box[2] - box[0], box[3] - box[1]
    img_w, img_h = w_px * GSD, h_px * GSD
    pad_x, pad_y = (img_w - sheet_w) / 2, (img_h - sheet_h) / 2
    return Affine(GSD, 0, box[0] - pad_x, 0, -GSD, box[3] + pad_y)


def _ortho_tifs() -> list[str]:
    """정사영상 TIF 목록. **대장이 정본이다.**

    ★ `RAW/"ngii"/"ngii_ortho_gj*.tif"` 로 하드코딩돼 있었다. 개명 뒤
      0건이 되고, 그러면 `[SKIP] 정사영상 TIF 없음` 을 찍고 조용히
      넘어간다 — 배경 타일이 통째로 빠진 채 성공으로 보인다.
    """
    import yaml

    from firelane.paths import ROOT as _R
    d = yaml.safe_load((_R / "sources.yaml").read_text(encoding="utf-8")) or {}
    e = (d.get("datasets") or {}).get("ortho") or {}
    out: list[str] = []
    for pat in _led.globs(e):
        out += [str(x) for x in RAW.glob(str(pat)) if x.suffix.lower() == ".tif"]
    return sorted(set(out))


def main():
    # ★ 글롭도 개명을 탄다. 대장이 정본이므로 거기서 읽는다.
    tifs = _ortho_tifs()
    if not tifs:
        print("[SKIP] 정사영상 TIF 없음. sources.yaml 의 ortho 참조")
        return

    scope = gpd.read_file(WEB / "scope.geojson").to_crs(ORTHO_CRS).geometry.iloc[0]
    sb = scope.bounds
    print(f"스코프(5186) {sb[0]:.0f},{sb[1]:.0f} ~ {sb[2]:.0f},{sb[3]:.0f}")

    # 스코프에 걸치는 부분만 읽어 붙인다. 4장 전량(1.25GB)을 메모리에 올리지 않는다.
    pieces = []
    for f in tifs:
        # ★ 2026-08-27. 종전에는 `stem.split("_")[2][2:]` 였다 —
        #   **세 번째 토큰이 도엽**이라는 가정이다. 개명으로 그 자리가
        #   `jngj-dong`(스코프)이 되면서 `gj-dong` 이 나와 KeyError 로
        #   파이프라인이 죽었다.
        #
        #   파일명 문법의 정본은 `firelane.naming` 이다. 인덱스로 토큰을
        #   꺼내는 코드는 문법이 바뀌는 순간 조용히 틀리거나 시끄럽게
        #   죽는다. 파서를 쓴다.
        key = nm.parse(Path(f).name, strict=False).part or ""
        key = key[2:] if key.startswith("gj") else key
        with rasterio.open(f) as r:
            tr = sheet_origin_5186(key, r.width, r.height)
            inv = ~tr
            c0, r0 = inv * (sb[0], sb[3])
            c1, r1 = inv * (sb[2], sb[1])
            c0, c1 = sorted((int(c0), int(c1)))
            r0, r1 = sorted((int(r0), int(r1)))
            c0, r0 = max(c0, 0), max(r0, 0)
            c1, r1 = min(c1 + 1, r.width), min(r1 + 1, r.height)
            if c1 <= c0 or r1 <= r0:
                print(f"  {key}: 스코프 밖")
                continue
            win = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
            a = r.read(window=win)
            pieces.append((a, rasterio.windows.transform(win, tr)))
            print(f"  {key}: {a.shape[2]}x{a.shape[1]} px 읽음")

    if not pieces:
        print("[SKIP] 스코프에 걸치는 도엽이 없다")
        return

    # 스코프 전체를 덮는 캔버스에 조각을 얹는다
    pad = 60
    W = int((sb[2] - sb[0] + 2 * pad) / GSD)
    H = int((sb[3] - sb[1] + 2 * pad) / GSD)
    dst_tr = Affine(GSD, 0, sb[0] - pad, 0, -GSD, sb[3] + pad)
    canvas = np.zeros((3, H, W), dtype="uint8")
    inv = ~dst_tr
    for a, tr in pieces:
        x, y = tr * (0, 0)
        c, rr = inv * (x, y)
        c, rr = round(c), round(rr)
        h, w = a.shape[1], a.shape[2]
        cs, rs = max(c, 0), max(rr, 0)
        ce, re = min(c + w, W), min(rr + h, H)
        if ce <= cs or re <= rs:
            continue
        sub = a[:, rs - rr:re - rr, cs - c:ce - c]
        m = sub.any(axis=0)                          # 검은 여백은 덮어쓰지 않는다
        tgt = canvas[:, rs:re, cs:ce]
        for b in range(3):
            tgt[b][m] = sub[b][m]
    print(f"캔버스 {W}x{H} px ({W*GSD:.0f} x {H*GSD:.0f} m)")

    # WebMercator 재투영
    from rasterio.warp import calculate_default_transform
    mtr, mw, mh = calculate_default_transform(
        ORTHO_CRS, "EPSG:3857", W, H,
        left=dst_tr.c, top=dst_tr.f, right=dst_tr.c + W * GSD, bottom=dst_tr.f - H * GSD)
    merc = np.zeros((3, mh, mw), dtype="uint8")
    for b in range(3):
        reproject(source=canvas[b], destination=merc[b],
                  src_transform=dst_tr, src_crs=ORTHO_CRS,
                  dst_transform=mtr, dst_crs="EPSG:3857",
                  resampling=Resampling.bilinear)
    print(f"머케이터 {mw}x{mh} px")

    R = 6378137.0
    ORIGIN = math.pi * R
    tdir = WEB / "ortho"
    if tdir.exists():
        shutil.rmtree(tdir)

    count = 0
    bounds_xyz = []
    for z in TILE_Z:
        n = 2 ** z
        span = 2 * ORIGIN / n
        x0 = int((mtr.c + ORIGIN) / span)
        x1 = int((mtr.c + mw * mtr.a + ORIGIN) / span)
        y0 = int((ORIGIN - mtr.f) / span)
        y1 = int((ORIGIN - (mtr.f + mh * mtr.e)) / span)
        for tx in range(min(x0, x1), max(x0, x1) + 1):
            for ty in range(min(y0, y1), max(y0, y1) + 1):
                mx = -ORIGIN + (tx + (np.arange(TILE_PX) + .5) / TILE_PX) * span
                my = ORIGIN - (ty + (np.arange(TILE_PX) + .5) / TILE_PX) * span
                MX, MY = np.meshgrid(mx, my)
                cc = ((MX - mtr.c) / mtr.a).astype(int)
                rr = ((MY - mtr.f) / mtr.e).astype(int)
                inside = (cc >= 0) & (cc < mw) & (rr >= 0) & (rr < mh)
                if not inside.any():
                    continue
                ci, ri = np.clip(cc, 0, mw - 1), np.clip(rr, 0, mh - 1)
                px = np.dstack([merc[b][ri, ci] for b in range(3)])
                px[~inside] = 0
                if not px.any():
                    continue
                out = tdir / str(z) / str(tx)
                out.mkdir(parents=True, exist_ok=True)
                Image.fromarray(px, "RGB").save(out / f"{ty}.jpg", quality=JPEG_Q)
                bounds_xyz.append((z, tx, ty))
                count += 1
        print(f"  z{z}: 누적 {count}장")

    # 실제로 구운 범위를 view.json 에 기록한다(범위 밖 타일 404 방지).
    vj = WEB / "view.json"
    if vj.exists() and bounds_xyz:
        z0 = TILE_Z[-1]; n = 2 ** z0; sp = 2 * ORIGIN / n
        xs = [t[1] for t in bounds_xyz if t[0] == z0]
        ys = [t[2] for t in bounds_xyz if t[0] == z0]
        def _ll(mx, my):
            return (mx / R * 180 / math.pi,
                    (2 * math.atan(math.exp(my / R)) - math.pi / 2) * 180 / math.pi)
        w, s_ = _ll(-ORIGIN + min(xs) * sp, ORIGIN - (max(ys) + 1) * sp)
        e, n_ = _ll(-ORIGIN + (max(xs) + 1) * sp, ORIGIN - min(ys) * sp)
        v = json.loads(vj.read_text(encoding="utf-8"))
        v["orthoBounds"] = [round(w, 4), round(s_, 4), round(e, 4), round(n_, 4)]
        vj.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")

    size = sum(f.stat().st_size for f in tdir.rglob("*.jpg")) / 1e6
    mf = OUT / "_manifest.json"
    m = json.loads(mf.read_text(encoding="utf-8"))
    m["ortho"] = {
        "source": "국토지리정보원 항공정사영상 2025 (도엽 35616037/038/047/048)",
        "gsd_m": GSD,
        "src_crs": ORTHO_CRS,
        "georef": "원본 TIF 에 geotransform 없음. 도엽 격자로 역산",
        "tiles": f"web/data/ortho/{{z}}/{{x}}/{{y}}.jpg ({count}장, z{TILE_Z[0]}~{TILE_Z[-1]}, {size:.1f}MB)",
        "purpose": "배경 텍스처. 판정에는 사용하지 않는다.",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    from firelane import manifest
    manifest.write_stable(mf, m)   # 내용이 같으면 쓰지 않는다
    print(f"\n→ 타일 {count}장 · {size:.1f}MB")


if __name__ == "__main__":
    from firelane.guards import warn_direct_call

    warn_direct_call(__name__)
    main()

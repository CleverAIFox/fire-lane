#!/usr/bin/env python3
"""
terrain.py — 공개DEM 을 스코프로 클립·보간해 표고를 부여한다.


IN    $FIRE_LANE_DATA/raw/ngii/**  (DEM) · processed/segments_5186.gpkg
OUT   processed/dem_scope.tif · web/data/terrain/**  (Terrain-RGB 타일)
      processed/_manifest.json 의 terrain 절
PARAM 줌 단계 · exaggeration 기본 1.0

  ingest.py → segments.py → **terrain.py** → publish_web.py

★ 표현용이다. 판정에는 쓰지 않는다.
  공개DEM 은 90m 격자다. 동명동(0.43km2)이 12x12 픽셀이라 한 픽셀이
  골목 20개를 덮는다. 구간별 경사 산출은 불가능하다.
  쓸 수 있는 것은 "동명동은 표고 33~75m, 기복 42m 의 완만한 경사지"라는 배경뿐이다.
  8배 이중선형 보간은 없는 정보를 만드는 게 아니라 계단 현상을 없애는 것이다.

산출
  data/processed/dem_scope.tif       스코프 클립 + 보간 (5179)
  data/processed/*.gpkg              z 컬럼 추가 (표고, 최저점 기준 상대값)
  web/data/terrain/{z}/{x}/{y}.png   Terrain-RGB 타일

★ 지면 자체를 휘게 하려면 z 컬럼만으로는 안 된다.
  MapLibre 의 래스터 배경은 평면이라, 건물·선만 z 를 올리면 공중에 뜬다.
  raster-dem 소스 + map.setTerrain() 으로 지면을 변형해야 하고,
  그러려면 DEM 을 Terrain-RGB 로 인코딩한 타일이 필요하다.

  Terrain-RGB 인코딩 (mapbox 방식)
      height = -10000 + (R*65536 + G*256 + B) * 0.1
"""
from __future__ import annotations

import glob
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import shutil

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW, PROCESSED, WEB  # noqa: E402
OUT = PROCESSED

DEM_ZIP = RAW / "ngii" / "ngii_dem_gj35616_20251117.zip"
ZOOM = 8          # 보간 배율. 90m -> 11.25m. 표현용이므로 정보량은 그대로다.
LAYERS = ["segments", "building", "cctv", "hydrant_point", "fire_station"]
TILE_Z = (12, 13, 14, 15)   # 원본이 90m 라 z15 면 이미 과표본이다. 그 이상은 무의미
TILE_PX = 256


def upsample(a: np.ndarray, k: int) -> np.ndarray:
    """이중선형 업샘플. 계단 현상만 없앤다."""
    yy = np.linspace(0, a.shape[0] - 1, a.shape[0] * k)
    xx = np.linspace(0, a.shape[1] - 1, a.shape[1] * k)
    y0, x0 = np.floor(yy).astype(int), np.floor(xx).astype(int)
    y1 = np.minimum(y0 + 1, a.shape[0] - 1)
    x1 = np.minimum(x0 + 1, a.shape[1] - 1)
    wy, wx = (yy - y0)[:, None], (xx - x0)[None, :]
    return (a[np.ix_(y0, x0)] * (1 - wy) * (1 - wx) + a[np.ix_(y1, x0)] * wy * (1 - wx)
          + a[np.ix_(y0, x1)] * (1 - wy) * wx      + a[np.ix_(y1, x1)] * wy * wx)


def build_terrain_tiles(up, tr, src_crs):
    """DEM 을 WebMercator 로 재투영해 Terrain-RGB XYZ 타일로 굽는다.

    MapLibre 의 raster-dem 소스가 읽는 형식이다. 이게 있어야 map.setTerrain()
    으로 지면이 실제로 휘고, 그 위에 건물이 자연스럽게 얹힌다.
    """
    import math
    from PIL import Image
    from rasterio.warp import calculate_default_transform, reproject, Resampling

    dst_crs = "EPSG:3857"
    h, w = up.shape
    left, top = tr * (0, 0)
    right, bottom = tr * (w, h)
    dtr, dw, dh = calculate_default_transform(
        src_crs, dst_crs, w, h, left=min(left, right), bottom=min(top, bottom),
        right=max(left, right), top=max(top, bottom))
    merc = np.full((dh, dw), np.nan, dtype="float32")
    reproject(source=up.astype("float32"), destination=merc,
              src_transform=tr, src_crs=src_crs,
              dst_transform=dtr, dst_crs=dst_crs,
              resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)

    R = 6378137.0
    ORIGIN = math.pi * R                       # 20037508.34
    tdir = ROOT / "web" / "data" / "terrain"
    if tdir.exists():
        shutil.rmtree(tdir)

    inv = ~dtr
    count = 0
    bounds_xyz = []
    for z in TILE_Z:
        n = 2 ** z
        span = 2 * ORIGIN / n                  # 타일 한 변의 미터
        x0 = int((dtr.c + ORIGIN) / span)
        x1 = int((dtr.c + dw * dtr.a + ORIGIN) / span)
        y0 = int((ORIGIN - dtr.f) / span)
        y1 = int((ORIGIN - (dtr.f + dh * dtr.e)) / span)
        for tx in range(min(x0, x1), max(x0, x1) + 1):
            for ty in range(min(y0, y1), max(y0, y1) + 1):
                # 타일 픽셀 중심의 머케이터 좌표
                mx = -ORIGIN + (tx + (np.arange(TILE_PX) + .5) / TILE_PX) * span
                my = ORIGIN - (ty + (np.arange(TILE_PX) + .5) / TILE_PX) * span
                MX, MY = np.meshgrid(mx, my)
                cc = (MX - dtr.c) / dtr.a
                rr = (MY - dtr.f) / dtr.e
                ci = np.clip(cc.astype(int), 0, dw - 1)
                ri = np.clip(rr.astype(int), 0, dh - 1)
                vals = merc[ri, ci]
                inside = (cc >= 0) & (cc < dw) & (rr >= 0) & (rr < dh) & ~np.isnan(vals)
                # ★ 빈 타일도 최저 표고로 채워서 굽는다.
                #   건너뛰면 브라우저가 404 를 내고 그 자리에 구멍이 생긴다.
                #   지형은 타일이 하나라도 비면 그 경계에서 절벽처럼 끊긴다.
                if not inside.any():
                    vals = np.full_like(vals, np.nanmin(merc))
                    inside = np.ones_like(inside, dtype=bool)
                # 범위 밖은 최저 표고로 채운다. 타일 경계에서 절벽이 생기지 않게.
                vals = np.where(inside, vals, np.nanmin(merc))
                v = np.clip(((vals + 10000.0) * 10.0).astype(np.int64), 0, 256**3 - 1)
                rgb = np.dstack([(v >> 16) & 255, (v >> 8) & 255, v & 255]).astype("uint8")
                out = tdir / str(z) / str(tx)
                out.mkdir(parents=True, exist_ok=True)
                Image.fromarray(rgb, "RGB").save(out / f"{ty}.png")
                bounds_xyz.append((z, tx, ty))
                count += 1
    # 실제로 구운 범위를 view.json 에 기록한다.
    # 지도가 이걸 소스 bounds 로 쓰면 범위 밖 타일을 요청하지 않는다(404 방지).
    vj = ROOT / "web" / "data" / "view.json"
    if vj.exists() and bounds_xyz:
        import json as _j
        z0 = TILE_Z[-1]; n = 2 ** z0; sp = 2 * ORIGIN / n
        xs = [t[1] for t in bounds_xyz if t[0] == z0]
        ys = [t[2] for t in bounds_xyz if t[0] == z0]
        def _ll(mx, my):
            return (mx / R * 180 / math.pi,
                    (2 * math.atan(math.exp(my / R)) - math.pi / 2) * 180 / math.pi)
        w, s_ = _ll(-ORIGIN + min(xs) * sp, ORIGIN - (max(ys) + 1) * sp)
        e, n_ = _ll(-ORIGIN + (max(xs) + 1) * sp, ORIGIN - min(ys) * sp)
        v = _j.loads(vj.read_text(encoding="utf-8"))
        v["terrainBounds"] = [round(w, 4), round(s_, 4), round(e, 4), round(n_, 4)]
        vj.write_text(_j.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK     ] terrain tiles          {count}장 (z{TILE_Z[0]}~{TILE_Z[-1]})")
    return count


def main():
    if not DEM_ZIP.exists():
        print(f"[SKIP] {DEM_ZIP.name} 없음. sources.yaml 의 dem_public 참조")
        return

    scope = gpd.read_file(OUT / "segments_5186.gpkg").to_crs(5179)
    minx, miny, maxx, maxy = scope.total_bounds
    pad = 200
    with tempfile.TemporaryDirectory() as td:
        zipfile.ZipFile(DEM_ZIP).extractall(td)
        img = glob.glob(f"{td}/**/*.img", recursive=True)[0]
        with rasterio.open(img) as r:
            win = from_bounds(minx - pad, miny - pad, maxx + pad, maxy + pad,
                              r.transform).round_offsets().round_lengths()
            a = r.read(1, window=win, masked=True).astype(float).filled(np.nan)
            tw, crs = r.window_transform(win), r.crs

    up = upsample(a, ZOOM)
    tr = rasterio.Affine(tw.a / ZOOM, tw.b, tw.c, tw.d, tw.e / ZOOM, tw.f)
    inv = ~tr

    # 기준 표고는 패딩 포함 창 전체가 아니라 실제 대상 영역의 최저점이다.
    # 창 최저점을 쓰면 대상 전체가 공중에 뜬 것처럼 보인다.
    sb = scope.total_bounds
    (c0, r1), (c1, r0) = inv * (sb[0], sb[1]), inv * (sb[2], sb[3])
    sub = up[max(int(r0), 0):int(r1) + 1, max(int(c0), 0):int(c1) + 1]
    base = float(np.nanmin(sub))

    with rasterio.open(OUT / "dem_scope.tif", "w", driver="GTiff",
                       height=up.shape[0], width=up.shape[1], count=1,
                       dtype="float32", crs=crs, transform=tr, nodata=np.nan) as dst:
        dst.write(up.astype("float32"), 1)

    def sample(geoms):
        pts = gpd.GeoSeries(geoms, crs=geoms.crs).to_crs(5179)
        out = []
        for g in pts:
            if g is None or g.is_empty:
                out.append(0.0); continue
            px = g if g.geom_type == "Point" else g.centroid
            if px.is_empty:
                out.append(0.0); continue
            c, rw = inv * (px.x, px.y)
            ci, ri = int(c), int(rw)
            v = up[ri, ci] if 0 <= ri < up.shape[0] and 0 <= ci < up.shape[1] else np.nan
            out.append(round(float(v - base), 1) if v == v else 0.0)
        return out

    touched = []
    for key in LAYERS:
        f = OUT / f"{key}_5186.gpkg"
        if not f.exists():
            continue
        g = gpd.read_file(f)
        g["z"] = sample(g.geometry)
        g.to_file(f, driver="GPKG", layer=key)
        if (OUT / f"{key}.geojson").exists():
            g.to_crs(4326).to_file(OUT / f"{key}.geojson", driver="GeoJSON")
        touched.append(key)
        print(f"[OK     ] {key:22} z {g.z.min():.1f} ~ {g.z.max():.1f} m")

    # ── Terrain-RGB 타일 ────────────────────────────────────
    n_tiles = build_terrain_tiles(up, tr, crs)

    mf = OUT / "_manifest.json"
    m = json.loads(mf.read_text(encoding="utf-8"))
    m.setdefault("terrain", {})
    m["terrain"] = {
        "source": "dem_public (공개DEM 90m, 도엽 35616)",
        "raster": "dem_scope.tif",
        "grid_m": round(abs(tr.a), 2),
        "upsample": ZOOM,
        "base_elev_m": round(base, 1),
        "relief_m": round(float(np.nanmax(sub) - base), 1),
        "note_relief": "대상 영역 기준. 패딩 포함 창 전체는 더 넓다",
        "applied_to": touched,
        "tiles": f"web/data/terrain/{{z}}/{{x}}/{{y}}.png ({n_tiles}장, z{TILE_Z[0]}~{TILE_Z[-1]})",
        "encoding": "mapbox Terrain-RGB: -10000 + (R*65536+G*256+B)*0.1",
        "purpose": "표현용. 90m 격자는 구간별 경사 산출 불가. 판정에 사용하지 않는다.",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    mf.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ dem_scope.tif ({abs(tr.a):.1f}m 격자) · 대상 기복 {np.nanmax(sub)-base:.1f}m")
    print(f"→ _manifest.json 에 terrain 기록")


if __name__ == "__main__":
    main()

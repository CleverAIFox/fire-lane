#!/usr/bin/env python3
"""
terrain.py — 공개DEM 을 스코프로 클립·보간해 표고를 부여한다.


IN    $FIRE_LANE_DATA/raw/ngii/**  (DEM) · processed/segments_5186.gpkg
OUT   processed/dem_scope.tif · web/data/terrain/**  (Terrain-RGB 타일)
      덧쓰기(z) processed/{segments,building,cctv,hydrant_point,fire_station}_5186.gpkg ·
                building.geojson · cctv.geojson · hydrant_point.geojson · fire_station.geojson ·
                segments_5186.gpkg · building_5186.gpkg · cctv_5186.gpkg ·
                hydrant_point_5186.gpkg · fire_station_5186.gpkg
      ★ 2026-09-16 머리말에 적었다. ingest 산출물을 제자리 덧쓰므로 샤드 봉인지의
        out 칸을 파이프라인이 이 단계 뒤에 고친다(DECISIONS §165-6).
      ★ processed/segments.geojson 에 z 를 **덧쓴다.** 이 줄이 없어서
        2026-08-18 에 `--only publish` 로 z 가 소실됐다
      ★ web/data/view.json 에 demBounds 를 덧쓴다 (publish 산출. 후진 의존)
      ★ processed/_manifest.json 에 terrain 기록을 덧쓴다
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

import contextlib
import json
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.windows import from_bounds

from firelane import quiet_gdal  # noqa: F401  GDAL cp949 로그 잡음 억제. rasterio 보다 먼저
from firelane.paths import PROCESSED, RAW, ROOT

OUT = PROCESSED

# ★ 2026-08-30. 여기가 하드코딩이었다. 스코프를 `jngj-donggu` 로 개명하자
#   경로가 안 맞아 **조용히 [SKIP]** 됐고, 지형 타일이 없어 z 컬럼이
#   사라졌고, 그것이 계약 위반으로 하류에서 터졌다. 연쇄다.
#   그리고 golden 은 L1·L2·L3 를 통과했다 — z 를 안 보기 때문이다.
#   **두 검사가 다른 것을 본다. golden 만으로는 회귀를 못 잡는다.**
def _dem_zip():
    from firelane import ledger as _led
    e = (_led.load().get("datasets") or {}).get("dem_public") or {}
    hits = _led.paths_of(e, RAW)
    if not hits:
        raise FileNotFoundError(
            "dem_public 실물이 없다 — 대장 글롭 "
            f"{_led.globs(e) or '(선언 없음)'} 가 raw 에서 0건.\n"
            "  ★ 종전에는 여기서 조용히 SKIP 했다. 그러면 z 컬럼이 빠진 채"
            " 파이프라인이 초록불로 끝나고, 하류가 계약 위반으로 터진다.\n"
            "  없으면 여기서 죽는다. 원인 자리에서 죽는 것이 낫다.")
    return hits[0]
ZOOM = 8          # 보간 배율. 90m -> 11.25m. 표현용이므로 정보량은 그대로다.
LAYERS = ["segments", "building", "cctv", "hydrant_point", "fire_station"]
# ★ 2026-11-14 (PLAN 행 237). z16 까지 굽는다. 종전 주석은 「z15 면 이미 과표본이라 그 이상은 무의미」였다 — **정보**로는 맞다(원본 90m).
#   그런데 화면은 z17~18 에서 본다. z15 타일 한 픽셀이 3.9m 라 4~8배로 늘어났고, 그때 보이는 것은 지형이 아니라 **타일 픽셀**이었다.
#   z16(1.95m/픽셀)은 세부를 더하지 않는다 — 늘어나는 배율을 반으로 줄일 뿐이다. 읽는 쪽(`layers.ts` 의 `dem` 소스 `maxzoom`)과 같아야 한다
#   (`tests/test_tile_zoom_agreement.py` 가 문다).
TILE_Z = (12, 13, 14, 15, 16)
#: 타일 **범위**의 기준 줌. 이 줌까지는 DEM 이 닿는 타일을 굽고, 그 위 줌은 이 줌 타일의 **자식 전부**를 굽는다 — 그래야 `terrainBounds`
#: (이 줌의 타일 테두리 · `view.json` → `navi_graph.json`)가 줌을 더해도 안 움직이고, 그 범위 안에서 404(구멍 · 절벽)가 안 난다.
BOUNDS_Z = 15
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


def tile_range(z: int, x0: int, x1: int, y0: int, y1: int) -> tuple[range, range]:
    """줌 `z` 에서 구울 타일의 (x 범위, y 범위). `x0..y1` 은 **`BOUNDS_Z` 에서** DEM 이 닿는 타일의 양끝이다.

    `BOUNDS_Z` 위 줌은 그 타일들의 자식 전부다(한 줌에 가로 · 세로 2배) — 범위가 줌마다 같은 땅을 덮는다.
    """
    d = z - BOUNDS_Z
    if d <= 0:
        raise ValueError(f"tile_range 는 BOUNDS_Z({BOUNDS_Z}) 위 줌에만 쓴다 — z={z}")
    return range(x0 << d, ((x1 + 1) << d)), range(y0 << d, ((y1 + 1) << d))


def tile_heights(up32, tr, src_crs, z: int, tx: int, ty: int, lo: float, hi: float) -> np.ndarray:
    """타일 한 장의 표고(m · float32 · 256×256). DEM 밖은 NaN.

    ★ 2026-11-14 (PLAN 행 237). **쌍3차로 뽑는다.** 종전에는 3857 로 한 번 옮긴 격자(약 13.8m)를 `merc[ri, ci]` **정수 색인(최근접)** 으로 뽑았다 —
      z15 타일(3.9m/픽셀)에 한 칸이 약 3.5픽셀씩 복제되어 **12m 블록**이 구워졌고, 화면이 그것을 4~8배로 늘려 계단으로 보였다.
      지금은 원 격자(`dem_scope.tif` 와 같은 배열)에서 **타일 격자로 곧장** 쌍3차 재표본한다(재투영 한 번 · GDAL `cubic`).
    ★ 쌍3차는 입력 범위를 살짝 넘을 수 있다(오버슈트) — `[lo, hi]` 로 자른다. **없는 언덕 · 없는 골을 만들지 않는다.**
    ★ 세부는 안 는다. 원본은 90m 다 — 매끈해질 뿐이다.
    """
    import math

    from rasterio.warp import Resampling, reproject

    origin = math.pi * 6378137.0
    span = 2 * origin / 2 ** z
    px = span / TILE_PX
    ttr = rasterio.Affine(px, 0.0, -origin + tx * span, 0.0, -px, origin - ty * span)
    out = np.full((TILE_PX, TILE_PX), np.nan, dtype="float32")
    reproject(source=up32, destination=out, src_transform=tr, src_crs=src_crs,
              dst_transform=ttr, dst_crs="EPSG:3857",
              resampling=Resampling.cubic, src_nodata=np.nan, dst_nodata=np.nan)
    return np.clip(out, lo, hi)


def encode_rgb(vals: np.ndarray) -> np.ndarray:
    """표고(m) → mapbox Terrain-RGB(0.1m). 머리말의 식의 역이다 — 가장 가까운 0.1m 로 **반올림**한다(종전은 버림이라 5cm 낮게 치우쳤다)."""
    v = np.clip(np.rint((vals.astype("float64") + 10000.0) * 10.0).astype(np.int64), 0, 256**3 - 1)
    return np.dstack([(v >> 16) & 255, (v >> 8) & 255, v & 255]).astype("uint8")


def build_terrain_tiles(up, tr, src_crs):
    """DEM 을 WebMercator 로 재투영해 Terrain-RGB XYZ 타일로 굽는다.

    MapLibre 의 raster-dem 소스가 읽는 형식이다. 이게 있어야 map.setTerrain()
    으로 지면이 실제로 휘고, 그 위에 건물이 자연스럽게 얹힌다.
    """
    import math

    from PIL import Image
    from rasterio.warp import calculate_default_transform

    dst_crs = "EPSG:3857"
    h, w = up.shape
    left, top = tr * (0, 0)
    right, bottom = tr * (w, h)
    # 3857 에서 DEM 이 덮는 네모(타일 범위를 정하는 데만 쓴다 — 값은 `tile_heights` 가 원 격자에서 곧장 뽑는다)
    dtr, dw, dh = calculate_default_transform(
        src_crs, dst_crs, w, h, left=min(left, right), bottom=min(top, bottom),
        right=max(left, right), top=max(top, bottom))
    up32 = up.astype("float32")
    lo, hi = float(np.nanmin(up32)), float(np.nanmax(up32))

    R = 6378137.0
    ORIGIN = math.pi * R                       # 20037508.34
    tdir = ROOT / "web" / "data" / "terrain"
    if tdir.exists():
        shutil.rmtree(tdir)

    def natural(z: int) -> tuple[int, int, int, int]:
        """줌 z 에서 DEM 네모가 닿는 타일의 (x 작은 끝, x 큰 끝, y 작은 끝, y 큰 끝)."""
        span = 2 * ORIGIN / 2 ** z             # 타일 한 변의 미터
        xs = (int((dtr.c + ORIGIN) / span), int((dtr.c + dw * dtr.a + ORIGIN) / span))
        ys = (int((ORIGIN - dtr.f) / span), int((ORIGIN - (dtr.f + dh * dtr.e)) / span))
        return min(xs), max(xs), min(ys), max(ys)

    count = 0
    bounds_xyz = []
    for z in TILE_Z:
        if z <= BOUNDS_Z:
            x0, x1, y0, y1 = natural(z)
            xr, yr = range(x0, x1 + 1), range(y0, y1 + 1)
        else:
            xr, yr = tile_range(z, *natural(BOUNDS_Z))
        for tx in xr:
            for ty in yr:
                vals = tile_heights(up32, tr, src_crs, z, tx, ty, lo, hi)
                # ★ 빈 타일도 최저 표고로 채워서 굽는다.
                #   건너뛰면 브라우저가 404 를 내고 그 자리에 구멍이 생긴다.
                #   지형은 타일이 하나라도 비면 그 경계에서 절벽처럼 끊긴다.
                # 범위 밖은 최저 표고로 채운다. 타일 경계에서 절벽이 생기지 않게.
                vals = np.where(np.isnan(vals), lo, vals)
                rgb = encode_rgb(vals)
                out = tdir / str(z) / str(tx)
                out.mkdir(parents=True, exist_ok=True)
                Image.fromarray(rgb, "RGB").save(out / f"{ty}.png", optimize=True)
                bounds_xyz.append((z, tx, ty))
                count += 1
    # 실제로 구운 범위를 view.json 에 기록한다.
    # 지도가 이걸 소스 bounds 로 쓰면 범위 밖 타일을 요청하지 않는다(404 방지).
    vj = ROOT / "web" / "data" / "view.json"
    if vj.exists() and bounds_xyz:
        import json as _j
        z0 = min(BOUNDS_Z, TILE_Z[-1]); n = 2 ** z0; sp = 2 * ORIGIN / n
        xs = [t[1] for t in bounds_xyz if t[0] == z0]
        ys = [t[2] for t in bounds_xyz if t[0] == z0]
        from firelane.mercator import to_lonlat as _ll
        w, s_ = _ll(-ORIGIN + min(xs) * sp, ORIGIN - (max(ys) + 1) * sp)
        e, n_ = _ll(-ORIGIN + (max(xs) + 1) * sp, ORIGIN - min(ys) * sp)
        v = _j.loads(vj.read_text(encoding="utf-8"))
        v["terrainBounds"] = [round(w, 4), round(s_, 4), round(e, 4), round(n_, 4)]
        vj.write_text(_j.dumps(v, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    print(f"[OK     ] terrain tiles          {count}장 (z{TILE_Z[0]}~{TILE_Z[-1]})")
    return count


@contextlib.contextmanager
def _dem_image(archive: Path):
    """ZIP 안의 **유일한 IMG** 를 임시 파일 하나로 꺼낸다. 쓰고 나면 지운다.

    ★ 2026-10-06 (DECISIONS §413). 종전에는 이랬다 —

          zipfile.ZipFile(dem_zip).extractall(td)
          img = str(next(Path(td).rglob("*.img")))

      고친 이유는 **경로 순회가 아니다.** 처음에 그렇게 적으려다 재 봤더니
      CPython 의 `extractall` 은 `../` 와 선행 `/` 를 **이미 벗겨낸다** —
      합성 압축물로 확인했다. 흔히 듣는 말이라 그대로 믿을 뻔했다.

      진짜 이유는 `next(rglob(...))` 쪽이다. **IMG 가 둘이면 어느 것을 읽는지가
      파일 시스템 순서에 달린다** — 아무 말 없이 하나를 고르고, 다음 사람이
      DEM 을 바꿔도 수가 안 움직이는 날이 온다. 그 조용함이 제일 나쁘다.
      여기서는 **정확히 하나**를 요구하고, 아니면 멈춘다.

    ★ 덤으로 둘 — 압축물 전체를 안 풀어 쓰는 바이트가 줄고, 웅토피아 팀이
      적어 둔 Windows ACL 문제(「폴더는 만들지만 그 아래 ZIP 디렉터리를 못
      만든다」)를 비켜간다. 그쪽 `terrain.py` 에서 가져온 모양이다.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
    path = Path(tmp.name)
    try:
        with zipfile.ZipFile(archive) as z:
            imgs = [m for m in z.infolist()
                    if not m.is_dir() and Path(m.filename).suffix.lower() == ".img"]
            if len(imgs) != 1:
                raise RuntimeError(
                    f"DEM 압축물에 IMG 가 {len(imgs)}개다 — 정확히 하나여야 한다: {archive}")
            with tmp, z.open(imgs[0]) as src:
                shutil.copyfileobj(src, tmp)
        yield path
    finally:
        tmp.close()
        path.unlink(missing_ok=True)


def main():
    dem_zip = _dem_zip()

    scope = gpd.read_file(OUT / "segments_5186.gpkg").to_crs(5179)
    minx, miny, maxx, maxy = scope.total_bounds
    pad = 200
    with _dem_image(dem_zip) as img:
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
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    from firelane import manifest
    manifest.write_stable(mf, m)   # 내용이 같으면 쓰지 않는다
    print(f"\n→ dem_scope.tif ({abs(tr.a):.1f}m 격자) · 대상 기복 {np.nanmax(sub)-base:.1f}m")
    print("→ _manifest.json 에 terrain 기록")


if __name__ == "__main__":
    from firelane.guards import warn_direct_call

    warn_direct_call(__name__, doc=__doc__)   # doc → 모르는 깃발도 거절(§283-2)
    main()

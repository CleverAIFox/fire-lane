"""
bldg_ground.py — **경사면의 건물이 지형에 묻히거나 뜨는 만큼을 재서 발행 건물에 싣는다.**  (PLAN #239 · DECISIONS §797-A)

MapLibre 는 지형 위에서 건물을 **발자국 중심 한 점의 지형 표고**에 올린다(헤드리스 실측 — DECISIONS §796-A). 경사면에서는 오르막 쪽이 묻히고 내리막 쪽 아래가 빈다.
`add_ground` 가 건물마다 발자국 아래 지형(구운 z16 타일 · 쌍선형)의 중심 · 최저 · 최고를 재서, 묻힘(최고 − 중심) 또는 뜸(중심 − 최저)이 `SPARSE_M`(0.5m) 이상인 건물에만
칸 `zb`(= 최저 − 중심 · **음수** · 소수 1자리)를 달고 높이 `h` 에 묻힘을 더한다(지붕 = 최고 지반 + h). 화면은 `fill-extrusion-base` 를 `zb` 로 읽는다(없으면 0).

IN    발행 건물(면 · 칸 `h` · 경위도로 바꿔 잰다) · `web/data/terrain/16/{x}/{y}.png`(구운 지형 · mapbox Terrain-RGB 0.1m)
OUT   칸 `zb` 와 갱신된 `h` — 희소(해당 건물만 · 나머지는 칸이 없다). 타일 밖 건물은 건드리지 않는다(조용히 0 으로 안 채운다)
PARAM `ZOOM` 16 · `SPARSE_M` 0.5
밖    **판정을 안 읽는다 · 안 바꾼다** — 건물 발행물만 바뀐다. 지형 타일이 없으면 죽는다(`terrain` 단계가 먼저다)
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

TILE = 256
SPARSE_M = 0.5
ZOOM = 16


def lonlat_to_px(lon: float, lat: float, z: int = ZOOM) -> tuple[float, float]:
    """경위도 → 줌 z 의 전역 픽셀(타일 256). 웹 메르카토르."""
    n = TILE * 2 ** z
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def decode(rgb: np.ndarray) -> np.ndarray:
    """mapbox Terrain-RGB → 표고(m). `terrain.py` 머리말의 식."""
    r, g, b = (rgb[..., i].astype("float64") for i in range(3))
    return -10000.0 + (r * 65536 + g * 256 + b) * 0.1


class Dem:
    """구운 타일 모자이크. 없는 타일은 NaN 이다 — 조용히 0 으로 안 채운다."""

    def __init__(self, tiles: dict[tuple[int, int], np.ndarray]):
        self.tiles = tiles
        xs = [k[0] for k in tiles]
        ys = [k[1] for k in tiles]
        self.x0, self.y0 = min(xs), min(ys)
        nx, ny = max(xs) - self.x0 + 1, max(ys) - self.y0 + 1
        self.a = np.full((ny * TILE, nx * TILE), np.nan)
        for (tx, ty), h in tiles.items():
            self.a[(ty - self.y0) * TILE:(ty - self.y0 + 1) * TILE, (tx - self.x0) * TILE:(tx - self.x0 + 1) * TILE] = h

    def at(self, px: np.ndarray, py: np.ndarray) -> np.ndarray:
        """전역 픽셀 좌표(픽셀 가운데 = 정수 + 0.5)의 쌍선형 표고."""
        u = np.asarray(px) - self.x0 * TILE - 0.5
        v = np.asarray(py) - self.y0 * TILE - 0.5
        i0, j0 = np.floor(u).astype(int), np.floor(v).astype(int)
        fu, fv = u - i0, v - j0
        h, w = self.a.shape

        def g(j, i):
            ok = (i >= 0) & (i < w) & (j >= 0) & (j < h)
            out = np.full(np.shape(i), np.nan)
            out[ok] = self.a[j[ok], i[ok]]
            return out
        return (g(j0, i0) * (1 - fu) * (1 - fv) + g(j0, i0 + 1) * fu * (1 - fv)
                + g(j0 + 1, i0) * (1 - fu) * fv + g(j0 + 1, i0 + 1) * fu * fv)


def load_dem(root: Path, z: int = ZOOM) -> Dem:
    tiles = {}
    for p in sorted((root / str(z)).glob("*/*.png")):
        tiles[(int(p.parent.name), int(p.stem))] = decode(np.asarray(Image.open(p).convert("RGB")))
    if not tiles:
        raise SystemExit(f"★ {root / str(z)} 에 타일이 없다 — 지형을 먼저 구워라(`firelane.terrain`)")
    return Dem(tiles)


def center_point(geom, rule: str):
    if rule == "centroid":
        return geom.centroid
    if rule == "rep":
        return geom.representative_point()
    if rule == "bbox":
        b = geom.bounds
        from shapely.geometry import Point
        return Point((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    raise ValueError(rule)


def stats(dem: Dem, geom, rule: str = "centroid") -> dict:
    """발자국 아래 지형의 중심 · 최저 · 최고. 발자국 안의 DEM 픽셀 가운데 + 꼭짓점에서 잰다."""
    minx, miny, maxx, maxy = geom.bounds
    px0, py1 = lonlat_to_px(minx, miny)
    px1, py0 = lonlat_to_px(maxx, maxy)
    xs = np.arange(math.floor(px0), math.ceil(px1) + 1) + 0.5
    ys = np.arange(math.floor(py0), math.ceil(py1) + 1) + 0.5
    gx, gy = np.meshgrid(xs, ys)
    n = TILE * 2 ** ZOOM
    lon = gx / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * gy / n))))
    import shapely
    inside = shapely.contains_xy(geom, lon.ravel(), lat.ravel())
    vx, vy = [], []
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for p in polys:
        for lo, la in p.exterior.coords:
            x, y = lonlat_to_px(lo, la)
            vx.append(x)
            vy.append(y)
    hx = np.concatenate([gx.ravel()[inside], np.array(vx)])
    hy = np.concatenate([gy.ravel()[inside], np.array(vy)])
    h = dem.at(hx, hy)
    c = center_point(geom, rule)
    cx, cy = lonlat_to_px(c.x, c.y)
    hc = float(dem.at(np.array([cx]), np.array([cy]))[0])
    if not np.isfinite(h).any() or not math.isfinite(hc):
        return {"ok": False}
    return {"ok": True, "center": hc, "lo": float(np.nanmin(h)), "hi": float(np.nanmax(h))}




def ground(dem: Dem, geom, h: float) -> tuple[float, float] | None:
    """희소 건물이면 (`zb`, 새 `h`), 아니면 None. 타일 밖이면 None."""
    r = stats(dem, geom)
    if not r["ok"]:
        return None
    up, down = max(r["hi"] - r["center"], 0.0), max(r["center"] - r["lo"], 0.0)
    if up < SPARSE_M and down < SPARSE_M:
        return None
    return round(-down, 1), round(h + up, 1)


def add_ground(b, root: Path):
    """`b`(어느 좌표계든 · 칸 `h`)에 `zb` 를 달고 `h` 를 고친다. 희소가 아닌 건물의 `zb` 는 비어 있다(`strip_null_cells` 가 파일에서 뺀다)."""
    dem = load_dem(root)
    zb, hh = [], []
    for g, h in zip(b.geometry.to_crs(4326), b["h"], strict=True):
        r = ground(dem, g, float(h))
        zb.append(None if r is None else r[0])
        hh.append(float(h) if r is None else r[1])
    out = b.copy()
    out["zb"], out["h"] = zb, hh
    return out


def strip_null_cells(path: Path) -> None:
    """GDAL 은 빈 칸을 `null` 로 쓴다 — 빈 `zb`(희소라 대부분)와 빈 `BULD_NM`(16,283동)을 파일에서 뺀다. 화면은 `coalesce` 로 읽어 없는 칸과 빈 칸이 같다.

    ★ 칸을 더한 것(`zb`)이 `web/data` 나머지 바이트 래칫을 넘겨, 같은 파일의 군더더기를 걷어 맞췄다(DECISIONS §797-A) — 래칫을 올리지 않는다.
    """
    s = path.read_text(encoding="utf-8")
    path.write_text(s.replace(', "zb": null', "").replace('"BULD_NM": null, ', ""), encoding="utf-8")

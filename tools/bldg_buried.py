#!/usr/bin/env python3
"""
bldg_buried.py — **경사면에서 건물이 지형에 묻히는 정도를 건물마다 잰다.**  (PLAN #239 · DECISIONS §796)

    uv run python tools/bldg_buried.py                 분포 표 + 후보(A · B) 발행 비용(바이트)
    uv run python tools/bldg_buried.py --center rep    중심점 규칙을 바꿔 본다(centroid · rep · bbox)
    uv run python tools/bldg_buried.py --csv OUT       건물별 값(경위도 무게중심 · 중심 · 최저 · 최고 · 묻힘 · 높이)을 파일로

── 왜 있나 ────────────────────────────────────────────────────
MapLibre 는 지형 위에서 건물을 **발자국 중심 한 점의 지형 표고**에 올린다. 경사면에서는 발자국 한쪽이 그 높이보다 높아 **묻히고**(오르막 쪽) 다른 쪽은 **뜬다**(내리막 쪽).
지형을 z16 으로 세밀하게 구운 뒤 묻힘이 더 드러났다(사람이 배포본에서 봤다 · 2026-11-15). 맞는 고침은 건물마다 올림값을 발행물에 싣는 것이고 그 값과 바이트가 이 도구가 내는 것이다.

── 무엇을 재나 ────────────────────────────────────────────────
건물마다 발자국 아래 지형(구운 z16 타일 · 쌍선형)의 **중심 · 최저 · 최고** 고도. 묻힘 = 최고 − 중심(오르막 쪽 벽이 지형 아래로 들어가는 깊이) · 뜸 = 중심 − 최저(내리막 쪽 벽 아래가 비는 깊이).
**통째로 묻힘** = 높이 `h` 가 묻힘 이하(지붕이 오르막 지반 아래다). 후보 둘의 **발행 비용**: 건물 파일 `buildings.geojson` 에 칸 하나(올림값 · 소수 1자리)를 모든 건물에 더했을 때 늘어나는 바이트(원본 · gzip 6).
  A  `base = 최고 − 중심`(+ 높이 `h + base`)   안 묻힌다 — 내리막 쪽 아래가 뜬 채다
  B  `base = 최저 − 중심`(**음수**) · 높이 `h + 묻힘`(지붕 = 최고 지반 + h · 두께 = h + 최고 − 최저)   아래까지 메운다(옹벽 · 기초) — 음수 `base` 를 MapLibre 가 받는지는 이 도구가 안 본다(헤드리스 실측 — DECISIONS §796)

IN    `web/data/buildings.geojson`(발행물) · `web/data/terrain/16/{x}/{y}.png`(구운 지형 · mapbox Terrain-RGB 0.1m)
OUT   화면 표 · (`--csv`) 건물별 파일. 저장소 파일을 안 쓴다 · 판정을 안 읽는다
PARAM `ZOOM` 16 · `BURY` 1.0 · 3.0(m) · `SPARSE_M` 0.5 · `CENTERS` centroid · rep · bbox
밖    **MapLibre 가 실제로 어느 점을 중심으로 쓰는지는 안 본다**(세 규칙을 맞대어 어제의 215 · 23 · 6 에 맞는 것을 가릴 뿐이다) · 지형 위 그림이 어떻게 보이는지는 안 본다(헤드리스 실측)
      · 발행 번호(`BUL_MAN_NO`)를 안 읽는다(§320) · 높이 `h` 만 읽는다
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
BUILDINGS = ROOT / "web" / "data" / "buildings.geojson"
TERRAIN = ROOT / "web" / "data" / "terrain"
ZOOM = 16
TILE = 256
BURY = (1.0, 3.0)
CENTERS = ("centroid", "rep", "bbox")


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


def load_dem(root: Path = TERRAIN, z: int = ZOOM) -> Dem:
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


def table(rows: list[dict]) -> list[str]:
    ok = [r for r in rows if r["ok"]]
    bury = np.array([max(r["hi"] - r["center"], 0.0) for r in ok])
    float_ = np.array([max(r["center"] - r["lo"], 0.0) for r in ok])
    rng = np.array([r["hi"] - r["lo"] for r in ok])
    h = np.array([r["h"] for r in ok])
    whole = bury >= h
    out = [f"건물 {len(rows)}동 중 지형을 잰 것 {len(ok)}동(타일 밖 {len(rows) - len(ok)})",
           f"  묻힘(최고 − 중심) : 1m 초과 {int((bury > BURY[0]).sum())} · 3m 초과 {int((bury > BURY[1]).sum())} · **통째(높이 이하) {int(whole.sum())}**",
           f"  뜸(중심 − 최저)   : 1m 초과 {int((float_ > BURY[0]).sum())} · 3m 초과 {int((float_ > BURY[1]).sum())}",
           f"  최고 − 최저       : 중앙 {np.median(rng):.2f}m · p90 {np.quantile(rng, .9):.2f}m · 최대 {rng.max():.2f}m · 3m 초과 {int((rng > 3).sum())}",
           f"  묻힘 분포(m)      : 중앙 {np.median(bury):.2f} · p90 {np.quantile(bury, .9):.2f} · 최대 {bury.max():.2f}"]
    return out


SPARSE_M = 0.5


def costs(feats: list[dict], rows: list[dict]) -> list[str]:
    """후보 A · B 를 건물 파일에 실었을 때의 바이트 — 전부에 싣는 꼴과 **해당 건물에만**(희소 · 묻힘/뜸이 `SPARSE_M` 이상) 싣는 꼴."""
    base_raw = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":")).encode()
    base_gz = len(gzip.compress(base_raw, 6))
    out = []
    for name, kind, sparse in (("A  base = 최고 − 중심            · 전부", "A", False), ("A  base = 최고 − 중심            · 희소", "A", True),
                               ("B  base = 최저 − 중심(음수)      · 전부", "B", False), ("B  base = 최저 − 중심(음수)      · 희소", "B", True)):
        add, n_set = [], 0
        for ft, r in zip(feats, rows, strict=True):
            props = dict(ft["properties"])
            if r["ok"]:
                up, down = max(r["hi"] - r["center"], 0.0), max(r["center"] - r["lo"], 0.0)
                hit = (up >= SPARSE_M) if kind == "A" else (up >= SPARSE_M or down >= SPARSE_M)
                if hit or not sparse:
                    zb = round(up, 1) if kind == "A" else round(-down, 1)
                    props["zb"] = zb
                    props["h"] = round(float(props.get("h") or 0) + up, 1)   # `fill-extrusion-height` 는 중심 지반에서 **지붕까지**다 — 지붕은 최고 지반 + h
                    n_set += 1
            add.append({**ft, "properties": props})
        raw = json.dumps({"type": "FeatureCollection", "features": add}, ensure_ascii=False, separators=(",", ":")).encode()
        out.append((name, n_set, len(raw) - len(base_raw), len(gzip.compress(raw, 6)) - base_gz))
    return [f"후보 비용(건물 파일 `buildings.geojson` · 칸 `zb` + 높이 갱신 · 같은 직렬화로 맞댄 증가분 · 원본 {len(base_raw):,}B · gzip {base_gz:,}B · 희소 = 묻힘/뜸 ≥ {SPARSE_M}m 인 건물만)",
            "  후보                                     건물    원본 +B    gzip +B"] + [f"  {n:<36} {k:>6} {a:>10,} {b:>10,}" for n, k, a, b in out]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--center", choices=CENTERS, default="centroid")
    ap.add_argument("--csv", type=Path)
    a = ap.parse_args(argv)
    gj = json.loads(BUILDINGS.read_text(encoding="utf-8"))
    feats = gj["features"]
    dem = load_dem()
    rows = []
    for f in feats:
        g = shape(f["geometry"])
        r = stats(dem, g, a.center)
        r["h"] = float(f["properties"].get("h") or 0)
        c = g.centroid
        r["lon"], r["lat"] = c.x, c.y
        rows.append(r)
    print("\n".join(table(rows) + [""] + costs(feats, rows)))
    if a.csv:
        with a.csv.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["lon", "lat", "ok", "center", "lo", "hi", "h"])
            w.writeheader()
            w.writerows({k: r.get(k) for k in w.fieldnames} for r in rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

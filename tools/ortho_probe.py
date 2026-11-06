#!/usr/bin/env python3
"""
tools/ortho_probe.py — 정사영상으로 도로 폭을 **읽을 수 있는가**를 재는 조사 도구.  (DECISIONS §654)

    uv run python tools/ortho_probe.py --crops OUTDIR --points naver        naver_width 의 mid 지점마다 판독용 이미지
    uv run python tools/ortho_probe.py --crops OUTDIR --points evalset      평가셋 55구간마다 판독용 이미지(구간 중점)
    uv run python tools/ortho_probe.py --compare READINGS.csv               판독(사람이 눈으로 읽은 값)과 naver_width 의 오차

── 왜 생겼나 ──────────────────────────────────────────────────
#187(F판)은 평가셋 55구간을 현장에서 줄자로 재는 행이다. 독립 측정이 현장뿐이라고 본 것은 정사영상을 빠뜨린 탓이다 — 지적도는 필지 단위라 선에 안 붙고 수치지형도는 `width.py` 의
입력이라 순환이며 웅토피아 3D 는 우리 `segments` 의 소비자라 순환이다. 정사영상은 `width.py` 가 안 읽는다(grep 0줄 · 이 판이 대었다) · 25cm · 레이크에 4장.
§569-7 이 「평가셋의 사람 측정과 대어 보기 전에는 주장하지 않는다」고 적은 것이 이 도구가 하는 일이다 — **판독 오차를 재야 판독을 쓸 수 있다.**

── 무엇을 하나 ────────────────────────────────────────────────
 ① 정사영상 4장에서 한 지점을 **구간 방향에 맞춰 돌려** 오려 낸다(길 방향이 가로 · 폭이 세로). 위치는 `ortho.py::sheet_origin_5186` 의 역산을 그대로 쓴다(TIF 에 좌표가 없다).
    1m 격자(굵은 선은 5m)와 눈금 · 축척 막대를 얹는다 — **구간 벡터의 가장자리는 안 그린다**(판독이 벡터에 끌리지 않게). 지점은 구간 중심선 위로 옮긴 점이다.
 ② 판독은 **사람이(여기서는 눈으로) 읽는다** — 한쪽 · 다른 쪽 경계(담장 · 건물면)의 세로 위치(m)와 가림(차량 · 처마 · 그늘 · 나무)을 `READINGS.csv` 에 적는다.
    ★ 눈가림이어야 한다: 비교 대상의 값을 보기 **전에** 적는다. 이미지에는 그 값이 안 들어 있다.
 ③ `--compare` 는 판독 폭을 `naver_width_2610.csv` 의 같은 지점(같은 `seg_uid` · `spot=mid` · 좌표)과 대어 오차의 분포(중앙 · 사분위 · 부호)를 낸다.

★ **이 대조가 못 말하는 것** — `naver_width` 는 네이버 지도 거리재기(화면 측정 · 오차 ±1.0m · 대장이 「정량 기준이 아니다」라 적는다)다. 그러므로 이것은 **판독 대 참값이 아니라 화면 측정끼리의 일치**다.
  참값은 현장 줄자뿐이다. 이 도구는 오차의 **하한**(두 측정이 서로 얼마나 어긋나는가)과 **가림의 비율**을 잰다.
★ 판정 · 폭 · `width.py` 를 안 건드린다 — 정사영상을 거기 넣는 순간 독립성이 사라진다. 평가셋 값을 채우지 않는다(채점은 F판이다).

IN    $FIRE_LANE_DATA/raw/ngii/ngii_ortho_*.tif · data/processed/segments_5186.gpkg · data/field/naver_width_2610.csv · data/field/evalset_2610.csv(구간 목록만)
OUT   OUTDIR/*.png (판독용 이미지) · stdout
PARAM --crops · --points · --compare
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
밖    **참값을 모른다**(위). 경계가 담장인지 지붕 가장자리인지는 영상에서 못 가린다 — 건물 높이 변위(진정사영상이 아니면 천정각 10° 에서 15m 건물이 약 2.6m · §569-7)가 벽 기준 폭을 좁게 읽히게 한다.
      도엽별 이동(최대 약 1.8m · §569-6)은 **폭**에는 안 들어가지만(두 경계가 같은 이동을 겪는다) 지점 위치에는 들어간다.
"""
from __future__ import annotations

import argparse
import math
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image, ImageDraw
from rasterio.windows import Window
from scipy.ndimage import map_coordinates
from shapely.geometry import Point

from firelane.ortho import GSD, sheet_origin_5186
from firelane.paths import DATA, PROCESSED, ROOT

warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

HALF_U = 14.0          # 길 방향 반폭(m) — 지점에서 앞뒤로
HALF_V = 9.0           # 폭 방향 반폭(m)
SCALE = 5              # 출력 배율(원본 0.25m/px → 1m = 20px)
SHEETS = ("037", "038", "047", "048")


# ── 순수 함수 ───────────────────────────────────────────────────
def world_to_pixel(x: float, y: float, origin) -> tuple[float, float]:
    """5186 (x, y) → 도엽 영상의 (열, 행). `origin` 은 `sheet_origin_5186` 의 Affine(북서 모서리 · 아래로 증가)."""
    return (x - origin.c) / GSD, (origin.f - y) / GSD


def tangent_at(line, d: float) -> tuple[float, float]:
    """선 위 거리 `d` 부근의 단위 접선(앞뒤 3m 로 잰다)."""
    a, b = line.interpolate(max(d - 3.0, 0.0)), line.interpolate(min(d + 3.0, line.length))
    vx, vy = b.x - a.x, b.y - a.y
    n = math.hypot(vx, vy) or 1.0
    return vx / n, vy / n


def sample_grid(cx: float, cy: float, tx: float, ty: float, half_u: float = HALF_U, half_v: float = HALF_V, step: float = GSD / SCALE) -> tuple[np.ndarray, np.ndarray]:
    """돌려 오릴 출력 격자의 세계 좌표. u(길 방향 · 가로) · v(폭 방향 · 세로 · 위가 +). 법선 = 접선을 반시계로 90° 돌린 것."""
    nx, ny = -ty, tx
    us = np.arange(-half_u, half_u, step)
    vs = np.arange(half_v, -half_v, -step)
    U, V = np.meshgrid(us, vs)
    return cx + U * tx + V * nx, cy + U * ty + V * ny


def which_sheet(x: float, y: float, origins: dict, sizes: dict, margin_m: float = 20.0) -> str | None:
    """점이 **여유를 두고** 들어 있는 도엽. 도엽 가장자리는 건너뛴다 — 영상이 잘리면 판독이 거짓이다."""
    for k, o in origins.items():
        w, h = sizes[k]
        c, r = world_to_pixel(x, y, o)
        m = margin_m / GSD
        if m <= c < w - m and m <= r < h - m:
            return k
    return None


def draw_overlay(img: Image.Image, half_u: float = HALF_U, half_v: float = HALF_V, scale: int = SCALE) -> Image.Image:
    """1m 격자(굵은 선 5m) · 세로 눈금(m) · 축척 막대. **구간 벡터는 안 그린다.**"""
    px = scale / GSD                                    # 1m 의 픽셀
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    for k in range(-int(half_v), int(half_v) + 1):
        y = H / 2 - k * px
        major = k % 5 == 0
        d.line([(0, y), (W, y)], fill=(255, 255, 0, 150 if major else 55), width=1)
        if k % 2 == 0:
            d.text((3, y - 10), f"{k:+d}", fill=(255, 255, 0, 255))
    for k in range(-int(half_u), int(half_u) + 1):
        x = W / 2 + k * px
        major = k % 5 == 0
        if k % 2 == 0 or major:
            d.line([(x, 0), (x, H)], fill=(0, 255, 255, 110 if major else 35), width=1)
    d.line([(W / 2, 0), (W / 2, 12)], fill=(255, 0, 0, 255), width=3)               # 지점의 위치
    d.line([(W / 2, H - 12), (W / 2, H)], fill=(255, 0, 0, 255), width=3)
    d.rectangle([(W - 4 * px - 8, H - 18), (W - 8, H - 10)], fill=(255, 255, 255, 230))
    d.text((W - 4 * px - 8, H - 32), "4 m", fill=(255, 255, 255, 255))
    return img


def montage(tiles: list[tuple[str, Image.Image]], cols: int = 2) -> Image.Image:
    """라벨 붙은 타일을 `cols` 열로 모은다. 타일 크기는 같아야 한다 — 한 번에 여럿을 읽어 가림만 분류할 때 쓴다."""
    w, h = tiles[0][1].size
    rows = math.ceil(len(tiles) / cols)
    out = Image.new("RGB", (cols * w, rows * h), (0, 0, 0))
    d = ImageDraw.Draw(out)
    for i, (label, im) in enumerate(tiles):
        x, y = (i % cols) * w, (i // cols) * h
        out.paste(im, (x, y))
        d.rectangle([(x, y), (x + 8 * len(label) + 6, y + 14)], fill=(0, 0, 0))
        d.text((x + 3, y + 2), label, fill=(255, 255, 255))
    return out


def width_error(reading_m: float, ref_m: float) -> float:
    """오차 = 판독 − 기준(부호 있음). 양수면 판독이 넓다."""
    return reading_m - ref_m


def summarize_errors(errs) -> dict:
    """오차 분포. 중앙 · 사분위 · 절대값의 중앙 · 최대 · 부호 비율. 셋 미만이면 n 만."""
    e = np.asarray(list(errs), float)
    if len(e) < 3:
        return {"n": len(e)}
    return {"n": len(e), "median": float(np.median(e)), "q25": float(np.percentile(e, 25)), "q75": float(np.percentile(e, 75)),
            "abs_median": float(np.median(np.abs(e))), "abs_max": float(np.max(np.abs(e))), "neg_share": float((e < 0).mean()),
            "within_050": float((np.abs(e) <= 0.5).mean()), "within_100": float((np.abs(e) <= 1.0).mean())}


# ── 입력 ───────────────────────────────────────────────────────
def _tifs() -> tuple[dict, dict]:
    raw = DATA / "raw" / "ngii"
    paths = {k: next(raw.glob(f"ngii_ortho_*_gj{k}.tif")) for k in SHEETS}
    sizes, origins = {}, {}
    for k, p in paths.items():
        with rasterio.open(p) as s:
            sizes[k] = (s.width, s.height)
            origins[k] = sheet_origin_5186(k, s.width, s.height)
    return {k: p for k, p in paths.items()}, (sizes, origins)


def crop(paths, sizes, origins, cx, cy, tx, ty, half_u=HALF_U, half_v=HALF_V, scale=SCALE) -> tuple[Image.Image, str] | tuple[None, None]:
    k = which_sheet(cx, cy, origins, sizes)
    if k is None:
        return None, None
    X, Y = sample_grid(cx, cy, tx, ty, half_u, half_v, GSD / scale)
    C, R = world_to_pixel(X, Y, origins[k])
    c0, r0 = int(C.min()) - 2, int(R.min()) - 2
    w, h = int(C.max()) - c0 + 3, int(R.max()) - r0 + 3
    with rasterio.open(paths[k]) as s:
        win = s.read(window=Window(c0, r0, w, h)).astype(float)
    out = np.stack([map_coordinates(win[b], [R - r0, C - c0], order=1, mode="nearest") for b in range(3)], axis=-1)
    return Image.fromarray(np.clip(out, 0, 255).astype("uint8")), k


def points(which: str) -> pd.DataFrame:
    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg").set_index("seg_uid")
    if which == "naver":
        d = pd.read_csv(ROOT / "data" / "field" / "naver_width_2610.csv")
        d = d[(d.spot == "mid") & d.seg_uid.notna()].drop_duplicates(["seg_uid", "lat", "lon"])[["seg_uid", "lat", "lon", "road"]]
        pts = gpd.GeoSeries([Point(x, y) for x, y in zip(d.lon, d.lat, strict=True)], crs=4326).to_crs(5186)
    else:
        d = pd.read_csv(ROOT / "data" / "field" / "evalset_2610.csv", comment="#", encoding="utf-8-sig")
        d = d[["seg_uid"]].assign(road=d.get("road", ""))
        pts = None
    rows = []
    for i, r in enumerate(d.itertuples()):
        g = seg.geometry.get(r.seg_uid)
        if g is None:
            continue
        line = g if g.geom_type == "LineString" else max(g.geoms, key=lambda q: q.length)
        base = pts.iloc[i] if pts is not None else line.interpolate(0.5, normalized=True)
        dist = line.project(base)
        c = line.interpolate(dist)
        tx, ty = tangent_at(line, dist)
        rows.append({"seg_uid": r.seg_uid, "road": r.road, "lat": getattr(r, "lat", None), "lon": getattr(r, "lon", None), "cx": c.x, "cy": c.y, "tx": tx, "ty": ty, "off_m": base.distance(c), "length_m": float(seg.loc[r.seg_uid, "length_m"]),
                     "verdict": seg.loc[r.seg_uid, "verdict"]})
    return pd.DataFrame(rows)


# ── 실행 ───────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crops", metavar="OUTDIR")
    ap.add_argument("--points", choices=("naver", "evalset"), default="naver")
    ap.add_argument("--montage", type=int, metavar="N", help="--crops 와 같이: N 장을 한 이미지로(작은 창 ±12m × ±8m · 가림 분류용)")
    ap.add_argument("--compare", metavar="READINGS_CSV")
    a = ap.parse_args(argv)

    if a.crops:
        out = Path(a.crops)
        out.mkdir(parents=True, exist_ok=True)
        paths, (sizes, origins) = _tifs()
        pts = points(a.points)
        made = skipped = 0
        if a.montage:
            tiles = []
            for i, r in enumerate(pts.itertuples()):
                img, sheet = crop(paths, sizes, origins, r.cx, r.cy, r.tx, r.ty, 12.0, 8.0, 3)
                if img is None:
                    skipped += 1
                    continue
                tiles.append((f"{i:02d} {r.seg_uid[-4:]} {r.length_m:.0f}m", draw_overlay(img, 12.0, 8.0, 3)))
            for j in range(0, len(tiles), a.montage):
                montage(tiles[j:j + a.montage]).save(out / f"{a.points}_montage_{j // a.montage:02d}.png")
                made += 1
            pts.to_csv(out / f"{a.points}_points.csv", index=False, encoding="utf-8-sig")
            print(f"{a.points}: 모음 {made}장({len(tiles)}구간) · 건너뜀 {skipped} → {out}")
            return 0
        for i, r in enumerate(pts.itertuples()):
            img, sheet = crop(paths, sizes, origins, r.cx, r.cy, r.tx, r.ty)
            if img is None:
                skipped += 1
                print(f"  건너뜀 {r.seg_uid} — 도엽 가장자리(여유 20m 밖)")
                continue
            draw_overlay(img).save(out / f"{a.points}_{i:02d}_{r.seg_uid}.png")
            made += 1
        pts.to_csv(out / f"{a.points}_points.csv", index=False, encoding="utf-8-sig")
        print(f"{a.points}: 이미지 {made} · 건너뜀 {skipped} → {out}")
    if a.compare:
        rd = pd.read_csv(a.compare, encoding="utf-8-sig")
        nv = pd.read_csv(ROOT / "data" / "field" / "naver_width_2610.csv")
        nv = nv[(nv.spot == "mid") & nv.seg_uid.notna()]
        ref = nv.groupby(["seg_uid", "lat", "lon"]).w_m.agg(["mean", "min", "max", "size"]).reset_index()
        m = rd.merge(ref, on=["seg_uid", "lat", "lon"], how="inner")
        read = m[m.width_m.notna()].copy()                      # 읽은 값이 있는 지점만 — 못 읽은 것은 오차를 안 만든다(NaN 을 섞지 않는다)
        read["err"] = [width_error(w, r) for w, r in zip(read.width_m, read["mean"], strict=True)]
        print(f"대조 가능 {len(m)} 지점 · 읽은 값이 있는 것 {len(read)} · 못 읽은 것 {len(m) - len(read)} ({(len(m) - len(read)) / max(len(m), 1) * 100:.0f}%)")
        for r in read.itertuples():
            print(f"  {r.seg_uid[-9:]}  판독 {r.width_m:.1f}m (가림 {r.occlusion or '없음'}) · naver {r.mean:.2f}m [{r.min:.1f}~{r.max:.1f}] · 오차 {r.err:+.2f}m")
        print(f"  오차 분포 {summarize_errors(read.err)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

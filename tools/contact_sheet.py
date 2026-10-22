#!/usr/bin/env python3
"""
tools/contact_sheet.py — 접촉인화: 구간 한 장씩 정사영상 위에 폭 산출을 얹어 찍는다

    uv run python tools/contact_sheet.py DM01875               한 구간 → PNG 한 장
    uv run python tools/contact_sheet.py DM01875 DM00536       여러 장
    uv run python tools/contact_sheet.py DM01875 --margin 30   가장자리 여유(m)
    uv run python tools/contact_sheet.py DM01875 --no-ortho    배경 없이 폴리곤·단면만
    uv run python tools/contact_sheet.py DM01875 --out DIR     기본 data/processed/contact/

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 읽고 그림 한 장을 쓴다. 판정·산출물·`ortho.py` 를 건드리지 않는다.

── 왜 만들었나 ─────────────────────────────────────────────────
`width_min_m` 은 표본 수십 개의 **최솟값 하나**다. 숫자만 보면 「어느 법선이 그 값을 냈는가」「그 법선이 도로를
제대로 가로질렀는가」를 알 수 없다. 사람이 눈으로 확인하려면 영상 위에 법선을 그어 봐야 한다.
(`DM01875` 동계천로: min 1.76 · max 21.37 · 대장 4.0 · cov 0.517 — 60 단면 중 어느 선이 1.76 인가.)

── 한 장에 얹는 것 ─────────────────────────────────────────────
  배경      정사영상(`sheet_origin_5186` 으로 좌표를 붙인 TIF) — 구간 상자 + 여유
  면        폭 소스 세 개의 폴리곤 외곽 — 채택된 소스는 굵게, 나머지는 가늘게
  중심선    구간 지오메트리
  단면      표본마다 법선 — 길이는 **발행된 폭**(`width_samples.csv`), 색은 폭(짧을수록 붉다).
            좌우 위치는 채택 소스 폴리곤에 법선을 다시 그어 얻는다. 다시 얻은 값이 발행 폭과 안 맞으면
            (보도 차감 · 끌어당김 때문) 그 단면은 **중심선 대칭 점선**으로 그리고 `~` 를 단다
  min 단면  발행된 최솟값을 낸 표본 — 굵은 빨강 + 폭 수치
  결측 표본  회색 ×. 사유(`drop`)를 단다
  머리말    판정 · 폭 min/max · 대장폭 · 커버율 · 표본 수 · 폭 원천 · 길이

★ 정사영상은 도엽마다 최대 약 1.5m 어긋난다(DECISIONS §543-5, `tools/ortho_register.py`). 영상과 선이 1~2m 어긋나 보여도
  선이 틀린 것이 아닐 수 있다 — 그림에 같은 경고를 단다.
★ 글자는 ASCII 만 쓴다(한글 글꼴이 없는 기계에서도 같은 그림이 나온다).

IN    data/processed/{segments_5186,width_samples.csv,ngii1k_5186,ngii_road_5186,road_rw_5186}.gpkg · raw/ngii/ngii_ortho_*.tif
OUT   data/processed/contact/<seg_id>.png  (gitignore 밖이 아니다 — 그림은 산출물이 아니라 조사 결과다)
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

PX_M = 0.25          # 정사영상 원본 해상도(m/px)
RAY_M = 60.0         # 법선 길이 — `seg.params.RAY_M` 와 같다
SOURCES = (("ngii1k", (0, 160, 255)), ("ngii", (255, 170, 0)), ("silpok", (0, 200, 120)))
LAYER_FILES = {"ngii1k": "ngii1k_5186.gpkg", "ngii": "ngii_road_5186.gpkg", "silpok": "road_rw_5186.gpkg"}
TOL_M = 0.05         # 다시 얻은 폭과 발행 폭이 이만큼 안에서 맞으면 「재현」


def _ortho_crop(box, tifs):
    """상자(5186)를 덮는 도엽 하나에서 PX_M 해상도로 잘라 온다. 못 덮으면 None."""
    import rasterio
    from rasterio.windows import Window

    from firelane.ortho import SHEET_5179, sheet_origin_5186
    best = None
    for key in SHEET_5179:
        f = next((t for t in tifs if f"gj{key}" in Path(t).name), None)
        if f is None:
            continue
        with rasterio.open(f) as r:
            tr = sheet_origin_5186(key, r.width, r.height)
            c0, r0 = ~tr * (box[0], box[3])
            c1, r1 = ~tr * (box[2], box[1])
            inside = 0 <= c0 < c1 <= r.width and 0 <= r0 < r1 <= r.height
            dist = (c0 + c1 - r.width) ** 2 + (r0 + r1 - r.height) ** 2        # 도엽 중심에서 먼 정도
            if inside and (best is None or dist < best[0]):
                a = r.read(window=Window(int(c0), int(r0), int(c1) - int(c0), int(r1) - int(r0)))
                best = (dist, key, a, tr * (int(c0), int(r0)))
    if best is None:
        return None
    _d, key, a, (wx, wy) = best
    return key, np.moveaxis(a[:3], 0, -1), (wx, wy)


def _font(size):
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/mnt/c/Windows/Fonts/arial.ttf"):
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _rays(poly, pt, ux, uy):
    """법선을 poly 로 자른 뒤 pt 를 품은 구간의 (left, right). 못 구하면 None."""
    from shapely.geometry import LineString
    r = LineString([(pt.x - ux * RAY_M, pt.y - uy * RAY_M), (pt.x + ux * RAY_M, pt.y + uy * RAY_M)])
    sg = r.intersection(poly)
    pcs = [sg] if sg.geom_type == "LineString" else [q for q in getattr(sg, "geoms", []) if q.geom_type == "LineString" and not q.is_empty]
    if sg.geom_type == "LineString" and sg.is_empty:
        return None
    iv = sorted((min(((x - pt.x) * ux + (y - pt.y) * uy) for x, y in q.coords),
                 max(((x - pt.x) * ux + (y - pt.y) * uy) for x, y in q.coords)) for q in pcs)
    if not iv:
        return None
    merged = [list(iv[0])]
    for lo, hi in iv[1:]:
        if lo - merged[-1][1] <= 0.5:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    run = next((m for m in merged if m[0] <= 0.0 <= m[1]), None)
    return None if run is None else (-run[0], run[1])


def sheet(seg_id: str, margin: float, out_dir: Path, ortho: bool = True) -> Path | None:
    import geopandas as gpd
    from PIL import Image, ImageDraw

    from firelane.ledger import globs  # noqa: F401  (대장 조회기 — 아래 TIF 글롭에 쓴다)
    from firelane.ortho import _ortho_tifs
    from firelane.paths import PROCESSED

    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg")
    hit = seg[seg.seg_id == seg_id]
    if hit.empty:
        print(f"{seg_id}: 구간이 없다", file=sys.stderr)
        return None
    row = hit.iloc[0]
    g = row.geometry
    samples = []
    with (PROCESSED / "width_samples.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["seg_id"] == seg_id:
                samples.append((float(r["s_m"]), float(r["w_m"]) if r["w_m"] else None, r["src"], r["drop"]))
    b = g.bounds
    box = (b[0] - margin, b[1] - margin, b[2] + margin, b[3] + margin)
    if ortho:
        crop = _ortho_crop(box, _ortho_tifs())
    else:       # 배경 없음 — 영상을 안 연다(레이크가 느리거나 TIF 가 무거울 때). 어두운 빈 판 위에 선만 그린다
        wpx, hpx = int((box[2] - box[0]) / PX_M), int((box[3] - box[1]) / PX_M)
        crop = ("none", np.full((hpx, wpx, 3), 30, np.uint8), (box[0], box[3]))
    if crop is None:
        print(f"{seg_id}: 상자가 한 도엽에 안 든다(도엽 이음매)", file=sys.stderr)
        return None
    key, arr, (wx, wy) = crop
    h, w = arr.shape[:2]
    # 확대: 짧은 변이 900px 이 되게(최대 4배). 긴 구간은 1배로 둔다.
    k = int(min(4, max(1, 900 // max(1, min(h, w)))))
    img = Image.fromarray(arr).resize((w * k, h * k), Image.BILINEAR).convert("RGBA")
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)

    def px(x, y):
        return ((x - wx) / PX_M * k, (wy - y) / PX_M * k)

    src = row.width_src if isinstance(row.width_src, str) else None
    polys = {}
    for name, _c in SOURCES:
        lg = gpd.read_file(PROCESSED / LAYER_FILES[name], bbox=box)
        lg = lg[lg.intersects(g.buffer(margin))]
        polys[name] = lg.geometry.union_all() if len(lg) else None
    for name, colr in SOURCES:
        u = polys[name]
        if u is None or u.is_empty:
            continue
        wd = 4 if name == src else 1
        for pg in getattr(u, "geoms", [u]):
            if pg.geom_type != "Polygon":
                continue
            for ring in [pg.exterior, *pg.interiors]:
                d.line([px(x, y) for x, y in ring.coords], fill=colr + (255,), width=wd)
    d.line([px(x, y) for x, y in g.coords], fill=(255, 255, 255, 255), width=3)

    ok = [(s, wv) for s, wv, _sr, _dr in samples if wv is not None]
    # ★ 구간 폭은 **채택된 소스의 표본만**의 최솟값이다(`width.py` 의 구간 단위 소스 채택).
    #   표본마다 소스가 다르면(`src` 열) 다른 소스의 더 좁은 표본은 `width_min_m` 을 못 낸다.
    mine = [(s, wv) for s, wv, sr, _dr in samples if wv is not None and sr == src]
    smin = min(mine, key=lambda t: t[1]) if mine else None
    if smin and row.width_min_m == row.width_min_m and abs(smin[1] - float(row.width_min_m)) > 0.011:
        print(f"  ! 채택 소스 표본의 최솟값 {smin[1]:.2f} 이 발행된 width_min_m {row.width_min_m} 과 다르다"
              " (병합 구간이거나 표본 파일이 낡았다)", file=sys.stderr)
    wvals = [wv for _s, wv in ok]
    lo, hi = (min(wvals), max(wvals)) if wvals else (0, 1)
    others = sum(1 for _s, wv, sr, _d in samples if wv is not None and sr != src)
    nrep = 0
    for s, wv, sr, _dr in samples:
        ref = polys.get(sr) if sr else None
        pt = g.interpolate(s)
        a, bq = g.interpolate(max(s - .5, 0)), g.interpolate(min(s + .5, g.length))
        dx, dy = bq.x - a.x, bq.y - a.y
        ln = float(np.hypot(dx, dy))
        if ln == 0:
            continue
        ux, uy = -dy / ln, dx / ln
        if wv is None:
            x, y = px(pt.x, pt.y)
            d.line([(x - 5, y - 5), (x + 5, y + 5)], fill=(200, 200, 200, 255), width=2)
            d.line([(x - 5, y + 5), (x + 5, y - 5)], fill=(200, 200, 200, 255), width=2)
            continue
        t = 0.0 if hi == lo else (wv - lo) / (hi - lo)
        colr = (255, int(255 * min(1, t * 3)), 0, 230) if t < 0.34 else (255, 255, 255, 120)
        lr = _rays(ref, pt, ux, uy) if ref is not None and not ref.is_empty else None
        solid = False
        if lr is not None:
            left, right = lr
            for cand in (left + right, 2 * min(left, right)):
                if abs(cand - wv) <= TOL_M:
                    solid = True
        dash = not solid
        if solid:
            p1, p2 = (pt.x - ux * left, pt.y - uy * left), (pt.x + ux * right, pt.y + uy * right)
            nrep += 1
        else:
            p1, p2 = (pt.x - ux * wv / 2, pt.y - uy * wv / 2), (pt.x + ux * wv / 2, pt.y + uy * wv / 2)
        wd = 5 if smin and s == smin[0] else (2 if sr == src else 1)
        if smin and s == smin[0]:
            colr = (255, 0, 0, 255)
        if dash:
            for i in range(0, 10, 2):
                q0 = (p1[0] + (p2[0] - p1[0]) * i / 10, p1[1] + (p2[1] - p1[1]) * i / 10)
                q1 = (p1[0] + (p2[0] - p1[0]) * (i + 1) / 10, p1[1] + (p2[1] - p1[1]) * (i + 1) / 10)
                d.line([px(*q0), px(*q1)], fill=colr, width=wd)
        else:
            d.line([px(*p1), px(*p2)], fill=colr, width=wd)
        if smin and s == smin[0]:
            x, y = px(pt.x, pt.y)
            d.text((x + 8, y - 22), f"min {wv:.2f}m @s={s:.0f}" + ("" if solid else " ~"), fill=(255, 60, 60, 255), font=_font(20))
    img = Image.alpha_composite(img, over).convert("RGB")

    fnt = _font(18)
    n_try = row.n_try
    lines = [
        f"{seg_id}  verdict={row.verdict}"
        + (f"/{row.unknown_reason}" if isinstance(row.unknown_reason, str) else "")
        + f"   sheet gj{key}",
        f"width_min={row.width_min_m}  width_max={row.width_max_m}  ledger={row.road_bt_m}  src={src}",
        f"cov={row.width_cov}  n_try={n_try}  n_sample={row.n_sample}  length={row.length_m}m  samples drawn={len(samples)}"
        f" (adopted-src {len(mine)}, other-src {others})",
        f"transects redrawn from the adopted polygon (solid): {nrep}/{len(ok)}   dashed '~' = symmetric about centerline",
        "layers: blue=ngii1k  orange=ngii(1:5000)  green=road_rw ; adopted source is the thick one",
        "WARNING: ortho is georeferenced by sheet grid; per-sheet offset up to ~1.5 m (DECISIONS 543-5)",
    ]
    pad = 8 + 24 * len(lines)
    canvas = Image.new("RGB", (img.width, img.height + pad), (20, 20, 20))
    canvas.paste(img, (0, pad))
    cd = ImageDraw.Draw(canvas)
    for i, t in enumerate(lines):
        cd.text((8, 6 + 24 * i), t, fill=(240, 240, 240), font=fnt)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{seg_id}.png"
    canvas.save(dst)
    if smin:
        low = sorted(mine, key=lambda t: t[1])[:3]
        print(f"{seg_id}: min {smin[1]:.2f}m @s={smin[0]:.0f} (채택 소스 {src}) · 단면 {len(ok)}/{len(samples)} 유효 · 재현 {nrep} · 채택 소스에서 가장 좁은 셋 "
              + " ".join(f"{wv:.2f}@{s:.0f}" for s, wv in low) + f" → {dst}")
    else:
        print(f"{seg_id}: 유효 단면 0/{len(samples)} → {dst}")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("ids", nargs="+", help="구간 seg_id (예: DM01875)")
    ap.add_argument("--margin", type=float, default=25.0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-ortho", action="store_true", help="정사영상을 안 열고 폴리곤·단면만 그린다")
    a = ap.parse_args()
    from firelane.paths import PROCESSED
    out = a.out or PROCESSED / "contact"
    return 0 if all(sheet(i, a.margin, out, not a.no_ortho) for i in a.ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())

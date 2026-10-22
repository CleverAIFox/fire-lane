#!/usr/bin/env python3
"""
tools/ortho_register.py — 정사영상을 벡터 지도에 대어 정합 오차를 아핀으로 읽는다 (PLAN #10)

    uv run python tools/ortho_register.py             창별 어긋남 → 아핀 적합 → 잔차 판독
    uv run python tools/ortho_register.py --win 128   창 크기(픽셀 · 0.5m/px)

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 읽고 표를 낸다. `ortho.py` 를 건드리지 않는다.

── 왜 만들었나 ─────────────────────────────────────────────────
정사영상 TIF 에는 좌표가 없어서 `ortho.sheet_origin_5186` 이 도엽 격자로 좌표를 **역산**한다
(영상이 도엽보다 사방 같은 폭으로 크다는 가정). 그 가정이 미터로 맞는지 재 본 적이 없었다.
지상기준점은 필요 없다 — 좌표가 박힌 벡터 지도(juso 건물 외곽선)가 있다.

── 방법: 영상 ↔ 벡터 등록 ──────────────────────────────────────
  ① 건물 외곽선을 래스터로 굽고 영상의 에지 크기 지도와 창마다 정규화 상호상관한다.
     점 뽑기가 사람 손을 안 탄다 — 창 하나가 「대응점 하나」다 (창 중심 → 어긋남 벡터).
  ② 신뢰할 창(상관 ≥ 0.25 · 둘째 봉우리/첫 봉우리 ≤ 0.9)만 남기고 이상치를 깎는다.
  ③ 어긋남 벡터 d(p) 를 모형 넷에 적합한다 —
        전역 이동 · 전역 아핀 · 도엽별 이동 · 도엽별 이동 + 공통 선형
     아핀을 분해한다: 등방 축척(trace/2) · 회전(반대칭) · 이방(무트레이스 대칭).
  ④ 부트스트랩(시드 19980711)으로 신뢰구간을 낸다. 잔차의 공간 자기상관과 DEM 상관을 본다.

── 읽는 법 (PLAN #10 의 세 갈래) ───────────────────────────────
  등방 축척만 어긋남 → bbox+pad 가 비율만 틀렸다. 상수로 교정
  회전·전단이 나옴   → 가정이 구조적으로 틀렸다. 아핀으로 교정
  잔차가 공간적 쏠림 → 지형 기복. DEM 없이는 여기까지가 한계

★ 기준(벡터)이 정답은 아니다 — juso 건물 외곽선 자체의 절대 오차는 재지 못한다. 그래서 도엽 사이 **상대**
  어긋남(같은 벡터에 댄 두 도엽의 차)이 기준에 독립이고 가장 믿을 만하다.
★ 창이 50% 겹쳐 있어 부트스트랩 구간은 낙관적이다.

IN    $FIRE_LANE_DATA/raw/ngii/ngii_ortho_*.tif · data/processed/{scope_5186,building_5186}.gpkg · dem_scope.tif
OUT   없음 (표준출력)
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

SEED = 19980711
RES = 0.5           # 작업 해상도(m/px). 원본 0.25m 를 2배 줄여 읽는다
SEARCH_PX = 24      # 탐색 반경 ±12m
MIN_NCC, MAX_RATIO = 0.25, 0.9
SHEETS = ("037", "038", "047", "048")


def _box3(a):
    p = np.pad(a, 1, mode="edge")
    return sum(p[i:i + a.shape[0], j:j + a.shape[1]] for i in range(3) for j in range(3)) / 9


def _prepare():
    """벡터 외곽선 래스터와 도엽별 영상 에지 지도를 같은 캔버스에 올린다."""
    import geopandas as gpd
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.features import rasterize
    from rasterio.transform import Affine
    from rasterio.windows import Window

    from firelane.ortho import sheet_origin_5186
    from firelane.paths import PROCESSED, RAW

    scope = gpd.read_file(PROCESSED / "scope_5186.gpkg").to_crs(5186).geometry.iloc[0]
    sb, pad = scope.bounds, 40
    x0, y1 = sb[0] - pad, sb[3] + pad
    w, h = int((sb[2] - sb[0] + 2 * pad) / RES), int((sb[3] - sb[1] + 2 * pad) / RES)
    bld = gpd.read_file(PROCESSED / "building_5186.gpkg").to_crs(5186)
    bld = bld[bld.intersects(scope.buffer(pad))]
    vec = rasterize([(g.boundary, 1) for g in bld.geometry], out_shape=(h, w),
                    transform=Affine(RES, 0, x0, 0, -RES, y1), fill=0, all_touched=True, dtype="uint8")
    p = np.pad(vec.astype(np.float32), 1)
    vec = np.clip(sum(p[i:i + h, j:j + w] for i in range(3) for j in range(3)), 0, 1)

    dec = int(RES / 0.25)
    edges = {}
    for key in SHEETS:
        f = next(Path(RAW / "ngii").glob(f"*gj{key}.tif"))
        with rasterio.open(f) as r:
            tr = sheet_origin_5186(key, r.width, r.height)
            c0, r0 = ~tr * (x0, y1)
            c1, r1 = ~tr * (x0 + w * RES, y1 - h * RES)
            ci0, ri0 = max(int(c0), 0), max(int(r0), 0)
            ci1, ri1 = min(int(c1) + 1, r.width), min(int(r1) + 1, r.height)
            if ci1 <= ci0 or ri1 <= ri0:
                continue
            oh, ow = (ri1 - ri0) // dec, (ci1 - ci0) // dec
            a = r.read(window=Window(ci0, ri0, ci1 - ci0, ri1 - ri0), out_shape=(r.count, oh, ow),
                       resampling=Resampling.average).astype(np.float32)
        wx, wy = tr * (ci0, ri0)
        ci, ri = int(round((wx - x0) / RES)), int(round((y1 - wy) / RES))
        g, valid = np.zeros((h, w), np.float32), np.zeros((h, w), bool)
        cs, rs, ce, re = max(ci, 0), max(ri, 0), min(ci + ow, w), min(ri + oh, h)
        g[rs:re, cs:ce] = a[:3].mean(0)[rs - ri:re - ri, cs - ci:ce - ci]
        valid[rs:re, cs:ce] = (a[:3].max(0) > 0)[rs - ri:re - ri, cs - ci:ce - ci]
        g = _box3(g)
        gy, gx = np.gradient(g)
        edges[key] = (_box3(np.hypot(gx, gy) * valid), valid)
    return vec, edges, x0, y1


def _ncc(img, tpl, win):
    """정규화 상호상관 지도(유효 구간). FFT 로 분자를, 적분영상으로 분모를 센다."""
    tz = tpl - tpl.mean()
    tn = np.sqrt((tz ** 2).sum())
    if tn < 1e-6:
        return None
    s = (img.shape[0] + win, img.shape[1] + win)
    c = np.fft.irfft2(np.fft.rfft2(img, s=s) * np.fft.rfft2(tz[::-1, ::-1], s=s), s=s)[win - 1:img.shape[0], win - 1:img.shape[1]]
    c1 = np.pad(np.cumsum(np.cumsum(img, 0), 1), ((1, 0), (1, 0)))
    c2 = np.pad(np.cumsum(np.cumsum(img * img, 0), 1), ((1, 0), (1, 0)))

    def box(m):
        return m[win:, win:] - m[:-win, win:] - m[win:, :-win] + m[:-win, :-win]
    s1, s2 = box(c1), box(c2)
    return c / (tn * np.sqrt(np.maximum(s2 - s1 * s1 / tpl.size, 1e-6)))


def _sub(a, i):
    if 0 < i < len(a) - 1:
        d = a[i - 1] - 2 * a[i] + a[i + 1]
        return i + (0.5 * (a[i - 1] - a[i + 1]) / d if d else 0)
    return float(i)


def _pairs(vec, edges, x0, y1, win):
    """창마다 어긋남 벡터. (sheet, x, y, dx, dy, ncc, ratio) — 영상 특징이 벡터보다 (dx,dy) 만큼 간 것."""
    h, w = vec.shape
    sr, rows = SEARCH_PX, []
    for key, (e, valid) in edges.items():
        for r0 in range(sr, h - win - sr, win // 2):
            for c0 in range(sr, w - win - sr, win // 2):
                if valid[r0 - sr:r0 + win + sr, c0 - sr:c0 + win + sr].mean() < 0.98:
                    continue
                tpl = vec[r0:r0 + win, c0:c0 + win]
                if tpl.sum() < 120:
                    continue
                m = _ncc(e[r0 - sr:r0 + win + sr, c0 - sr:c0 + win + sr], tpl, win)
                if m is None:
                    continue
                k = np.unravel_index(m.argmax(), m.shape)
                mm = m.copy()
                mm[max(k[0] - 4, 0):k[0] + 5, max(k[1] - 4, 0):k[1] + 5] = -1
                pk = float(m[k])
                dr, dc = _sub(m[:, k[1]], k[0]) - sr, _sub(m[k[0], :], k[1]) - sr
                rows.append((key, x0 + (c0 + win / 2) * RES, y1 - (r0 + win / 2) * RES,
                             dc * RES, -dr * RES, pk, float(mm.max() / pk) if pk > 0 else 1.0))
    return rows


def _design(sheet, xk, yk, model):
    cols = []
    if model in ("t", "a"):
        cols.append(np.ones(len(sheet)))
    if model == "a":
        cols += [xk, yk]
    if model in ("s", "sa"):
        cols += [(sheet == s).astype(float) for s in SHEETS]
    if model == "sa":
        cols += [xk, yk]
    return np.c_[tuple(cols)]


def _fit(d, model):
    a = _design(d["sheet"], d["xk"], d["yk"], model)
    cx, cy = (np.linalg.lstsq(a, d[k], rcond=None)[0] for k in ("dx", "dy"))
    return cx, cy, np.hypot(d["dx"] - a @ cx, d["dy"] - a @ cy), a.shape[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--win", type=int, default=128, help="창 크기(px). 128 = 64m")
    a = ap.parse_args()

    from firelane.console import col
    vec, edges, x0, y1 = _prepare()
    rows = _pairs(vec, edges, x0, y1, a.win)
    sheet = np.array([r[0] for r in rows])
    x, y, dx, dy, ncc, ratio = (np.array([r[i] for r in rows], float) for i in range(1, 7))
    print(f"창 {len(rows)}  (벡터 외곽선이 충분한 창만 · 도엽 {', '.join(sorted(set(sheet)))})")

    keep = (ncc >= MIN_NCC) & (ratio <= MAX_RATIO)
    t = np.array([np.median(dx[keep]), np.median(dy[keep])])
    r = np.hypot(dx - t[0], dy - t[1])
    keep &= r < max(2.5 * 1.4826 * np.median(r[keep]), 0.5)
    d = {"sheet": sheet[keep], "x": x[keep], "y": y[keep], "dx": dx[keep], "dy": dy[keep]}
    d["xk"], d["yk"] = (d["x"] - d["x"].mean()) / 1000, (d["y"] - d["y"].mean()) / 1000
    n = len(d["x"])
    print(f"상관 ≥ {MIN_NCC} · 둘째/첫째 ≤ {MAX_RATIO} · 이상치 깎은 뒤 {n}창  "
          f"{ {s: int((d['sheet'] == s).sum()) for s in SHEETS} }\n")
    if n < 50 or any((d["sheet"] == s).sum() < 5 for s in SHEETS):
        print(col("대응점이 모자라 적합을 못 한다", "r"))
        return 1

    print(f"{col('모형', 'c')}                          모수   잔차 RMS     BIC")
    for model, lab in (("t", "전역 이동"), ("a", "전역 아핀"), ("s", "도엽별 이동"), ("sa", "도엽별 이동+공통 선형")):
        _, _, res, k = _fit(d, model)
        rss, m = float((res ** 2).sum()), 2 * n
        print(f"  {lab:24}{2 * k:>5}{np.sqrt((res ** 2).mean()):>10.3f}m{m * np.log(rss / m) + 2 * k * np.log(m):>10.1f}")

    rng = np.random.default_rng(SEED)
    ps, af = {s: [] for s in SHEETS}, []
    for _ in range(1000):
        b = rng.integers(0, n, n)
        db = {k: v[b] for k, v in d.items()}
        if len(set(db["sheet"])) < 4:
            continue
        cx, cy, _, _ = _fit(db, "s")
        for i, s in enumerate(SHEETS):
            ps[s].append((cx[i], cy[i]))
        cx, cy, _, _ = _fit(db, "a")
        af.append([cx[0], cy[0], cx[1], cx[2], cy[1], cy[2]])
    print(f"\n{col('도엽별 이동 (m · 영상이 벡터보다 간 양)', 'c')}")
    for s in SHEETS:
        v = np.array(ps[s])
        print(f"  {s}  ({v[:, 0].mean():+.2f} ± {v[:, 0].std():.2f}, {v[:, 1].mean():+.2f} ± {v[:, 1].std():.2f})")
    af = np.array(af)
    iso, rot = (af[:, 2] + af[:, 5]) / 2, (af[:, 4] - af[:, 3]) / 2
    aniso = np.hypot((af[:, 2] - af[:, 5]) / 2, (af[:, 3] + af[:, 4]) / 2)
    print(f"\n{col('전역 아핀 분해 (m/km · 95% 구간)', 'c')}")
    for lab, v in (("등방 축척", iso), ("회전", rot), ("이방(전단)", aniso)):
        print(f"  {lab:10}{v.mean():+.2f}  [{np.percentile(v, 2.5):+.2f}, {np.percentile(v, 97.5):+.2f}]")
    print(f"  이동        ({af[:, 0].mean():+.2f}, {af[:, 1].mean():+.2f}) m")

    cx, cy, res, _ = _fit(d, "s")
    a_s = _design(d["sheet"], d["xk"], d["yk"], "s")
    ex, ey = d["dx"] - a_s @ cx, d["dy"] - a_s @ cy
    pts = np.c_[d["x"], d["y"]]
    dist = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    nb = (dist < 150) & (dist > 0)
    mor = lambda e: float(((e - e.mean())[:, None] * (e - e.mean())[None, :] * nb).sum() / nb.sum() / e.var())  # noqa: E731
    null = [mor(ex[rng.permutation(n)]) for _ in range(300)]
    print(f"\n{col('잔차(도엽별 이동 뒤)', 'c')}  RMS {np.sqrt((res ** 2).mean()):.2f}m")
    print(f"  이웃(<150m) 상관  dx {mor(ex):+.2f}  dy {mor(ey):+.2f}   (뒤섞은 영가설 {np.mean(null):+.2f} ± {np.std(null):.2f})")
    try:
        import pyproj
        import rasterio

        from firelane.paths import PROCESSED
        with rasterio.open(PROCESSED / "dem_scope.tif") as ds:
            tf = pyproj.Transformer.from_crs(5186, ds.crs, always_xy=True)
            z = np.array([v[0] for v in ds.sample(zip(*tf.transform(d["x"], d["y"]), strict=True))], float)
        ok = np.isfinite(z) & (z > -1000)

        def rho(u, v):
            return float(np.corrcoef(np.argsort(np.argsort(u)), np.argsort(np.argsort(v)))[0, 1])
        print(f"  DEM 높이와 스피어만 ρ   dx {rho(ex[ok], z[ok]):+.2f}  dy {rho(ey[ok], z[ok]):+.2f}  |r| {rho(np.hypot(ex, ey)[ok], z[ok]):+.2f}")
    except Exception as ex_:  # DEM 이 없으면 이 줄만 빠진다
        print(f"  DEM 상관 생략 — {type(ex_).__name__}")
    print(col("\n★ 아무것도 안 바꿨다. 교정은 `ortho.py` 소관이고 사람이 고른다.", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

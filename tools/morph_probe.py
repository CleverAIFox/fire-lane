#!/usr/bin/env python3
"""
tools/morph_probe.py — 형태학 통과 판정 프로토타입 (opening 뒤 연결성분) — **숫자만 낸다**

    uv run python tools/morph_probe.py                       r=1.5 · 3.5 · 해상도 0.5 · 0.25 m/px 로 숫자 넷을 낸다
    uv run python tools/morph_probe.py --res 0.5             해상도 하나만(빠르다)
    uv run python tools/morph_probe.py --selftest            ★ EDT 방식 opening 이 디스크 방식과 맞나

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 판정 · 산출물 · 칸을 만들지 않고 화면에 숫자를 낸다. 판정 폐포 밖 · 읽기만 · 골든 무관(`clearance_probe.py` 와 같은 성격).

── 왜 ─────────────────────────────────────────────────────────
지금 판정은 1차원이다 — 법선 트랜섹트도 내접원도 좌우 분해도 「한 점에서 폭이 몇 m 냐」를 묻는다. 도로는 2차원 면이고 소방차 통과는 **경로 문제**인데 폭 문제로 바꿔 풀고 있다.
**원리** — `opening(도로면, 반지름 r)` 뒤 연결성분을 본다. 구간 양끝이 같은 성분이면 반지름 r 원이 굴러갈 수 있다 = 통과.
`TRUCK` · `CLEAR` 가 임계값이 아니라 **구조요소 반지름**이 된다: r = 1.5m(전폭 3.0m · 소방차) · r = 3.5m(7.0m · 양쪽 주차 상태). 같은 연산에서 두 판정이 나온다.
주차장 apron 이 좁은 목으로 붙어 있으면 opening 에서 저절로 끊긴다.

── 구현 ───────────────────────────────────────────────────────
디스크 구조요소를 안 쓴다 — 거리변환이 훨씬 빠르다:
    erode(A, r)  = distance_transform_edt(A) >= r
    dilate(B, r) = distance_transform_edt(~B) <= r
    opening      = dilate(erode(A)) & A
좌표계 EPSG:5186(미터 평면). 도로면 = `web/data/road_area.geojson`(WGS84 52폴리곤)을 5186 으로 옮겨 `unary_union` 한 뒤 래스터화한다.
★ 전역 연결성분은 도시 도로망이 우회로로 이어져 있어 **거의 다 「연결」** 로 나올 수 있다 — 그래서 **회랑 안 국소 라벨링**(구간 버퍼 `corridor` m 안에서만 라벨)을 같이 낸다.
  회랑 폭은 **상수가 아니라 민감도**다(4 · 6 · 10m).
★ 구간 끝점이 폴리곤 경계에 걸리면 라벨이 0 이다 → 끝점 주변 `k` 픽셀 창의 **최빈(0 아닌) 라벨**을 쓰고 k 를 바꿔 흔들림을 본다.

IN    web/data/road_area.geojson · data/processed/segments_5186.gpkg · segments.geojson(판정)
OUT   없음 (표준출력)
PARAM 없음
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
밖    **판정을 안 한다 · 칸을 안 만든다.** opening 이 「통과」의 옳은 정의인지는 안 정한다 — 해상도가 결과를 정하는지(민감도)를 보는 것이 이 판의 일이다. scipy 는 dev 그룹에만 있다(감사 N9 · Zm20 에서 core → dev. `uv sync --no-dev` 환경에는 없다 — 이 도구는 조사용이라 dev 환경에서 돈다 · `uv.lock` 이 움직였다 — 골든 코드 지문에 들어 있다).
"""
from __future__ import annotations

import argparse
import time
from collections import Counter

import numpy as np

from firelane.paths import PROCESSED, ROOT

CRS_M = "EPSG:5186"
PAD_M = 6.0


def opening_edt(area, r_m: float, res: float, strip_rows: int = 2400):
    """띠(strip)로 나눠 `opening_full` 을 돈다 — **메모리를 아끼려는 것이고 결과는 같다**(자기검사가 대조한다).

    opening 은 국소 연산이라 위아래로 `2r + 3px` 의 여유(halo)를 붙이면 띠 경계에서도 같은 값이 나온다. 0.25m/px(90M px)에서 버퍼가 720MB → 띠 하나 약 250MB.
    """
    H = area.shape[0]
    halo = int(np.ceil(2 * r_m / res)) + 3
    out = np.zeros_like(area)
    for r0 in range(0, H, strip_rows):
        r1 = min(r0 + strip_rows, H)
        a0, a1 = max(r0 - halo, 0), min(r1 + halo, H)
        out[r0:r1] = opening_full(area[a0:a1], r_m, res)[r0 - a0:r1 - a0]
    return out


def opening_full(area, r_m: float, res: float):
    """`dilate(erode(A, r), r) & A` — 거리변환 방식. `area` 는 bool 배열(True = 도로면).

    ★ scipy 의 거리변환 출력 버퍼는 **float64 만** 받는다(float32 를 주면 거부한다). 0.25m/px(90M px)면 버퍼 하나가 720MB 다 — 두 번의 변환이 **같은 버퍼를 재사용**한다.
    """
    from scipy.ndimage import distance_transform_edt as edt
    buf = np.empty(area.shape, np.float64)
    edt(area, sampling=res, distances=buf)
    eroded = buf >= r_m
    edt(~eroded, sampling=res, distances=buf)
    out = (buf <= r_m) & area
    del buf, eroded
    return out


def endpoint_label(labels, row: int, col: int, k: int) -> int:
    """끝점 주변 `(2k+1)²` 창에서 **0 이 아닌 최빈 라벨**. 전부 0 이면 0 — 끝점이 경계에 걸리면 0 이 나오기 때문이다."""
    r0, c0 = max(row - k, 0), max(col - k, 0)
    w = labels[r0:row + k + 1, c0:col + k + 1]
    nz = w[w > 0]
    if nz.size == 0:
        return 0
    v, n = np.unique(nz, return_counts=True)
    return int(v[np.argmax(n)])


def rasterize(geoms, shape, transform):
    import rasterio.features as rf
    return rf.rasterize(geoms, out_shape=shape, transform=transform, fill=0, default_value=1, dtype="uint8").astype(bool)


def load_inputs():
    import geopandas as gpd
    import shapely
    road = gpd.read_file(ROOT / "web" / "data" / "road_area.geojson").to_crs(CRS_M)
    g = shapely.make_valid(np.asarray(road.geometry.values, dtype=object))
    area_u = shapely.union_all(g)
    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg").set_index("seg_id")
    ver = gpd.read_file(PROCESSED / "segments.geojson", ignore_geometry=True).set_index("seg_id")["verdict"]
    seg["verdict"] = ver
    return area_u, seg


def run_resolution(area_u, seg, res: float, radii, ks, corridors):
    import rasterio.transform as rt
    from scipy.ndimage import label
    minx, miny, maxx, maxy = (min(area_u.bounds[0], seg.total_bounds[0]) - PAD_M, min(area_u.bounds[1], seg.total_bounds[1]) - PAD_M,
                              max(area_u.bounds[2], seg.total_bounds[2]) + PAD_M, max(area_u.bounds[3], seg.total_bounds[3]) + PAD_M)
    W, H = int(np.ceil((maxx - minx) / res)), int(np.ceil((maxy - miny) / res))
    tr = rt.from_origin(minx, maxy, res, res)
    t0 = time.time()
    A = rasterize([(area_u, 1)], (H, W), tr)
    print(f"\n━━ 해상도 {res} m/px · 격자 {W}×{H} = {W * H / 1e6:.1f}M px · 도로면 {A.sum() / 1e6:.2f}M px ({A.mean() * 100:.1f}%) · 래스터화 {time.time() - t0:.0f}s ━━")
    pix = lambda x, y: (int((maxy - y) / res), int((x - minx) / res))
    ends = {sid: (pix(*ln.coords[0]), pix(*ln.coords[-1])) for sid, ln in
            ((sid, (ln if ln.geom_type == "LineString" else max(ln.geoms, key=lambda g: g.length))) for sid, ln in seg.geometry.items())}
    result = {}
    for r in radii:
        t0 = time.time()
        O = opening_edt(A, r, res)
        lab, n = label(O, structure=np.ones((3, 3), int))
        sizes = np.bincount(lab.ravel())[1:]
        top = np.sort(sizes)[::-1][:3] * res * res
        print(f"\n① r={r} — opening 뒤 남은 도로면 {O.sum() / A.sum() * 100:.1f}% (원래 {A.sum() * res * res / 1e6:.2f}km² → {O.sum() * res * res / 1e6:.2f}km²) · "
              f"연결성분 {n:,}개 · 최대 성분이 남은 면적의 {sizes.max() / sizes.sum() * 100:.1f}% (상위 면적 m² {', '.join(f'{x:,.0f}' for x in top)}) · {time.time() - t0:.0f}s")
        # 전역 성분 — 끝점 최빈 라벨(k 를 바꿔 흔들림)
        for k in ks:
            same = {sid: (lambda a, b: a != 0 and a == b)(endpoint_label(lab, *ea, k), endpoint_label(lab, *eb, k)) for sid, (ea, eb) in ends.items()}
            zero = sum(1 for sid, (ea, eb) in ends.items() if endpoint_label(lab, *ea, k) == 0 or endpoint_label(lab, *eb, k) == 0)
            result[(r, "global", k, None)] = same
            print(f"   전역 · k={k}px: 같은 성분 {sum(same.values()):,}/{len(same):,} · 끝점 라벨 0 인 구간 {zero}")
        # 회랑 안 국소 라벨링
        for cw in corridors:
            for k in ks:
                same = {}
                for sid, ln in seg.geometry.items():
                    line = ln if ln.geom_type == "LineString" else max(ln.geoms, key=lambda g: g.length)
                    buf = line.buffer(cw)
                    b = buf.bounds
                    r0, c0 = pix(b[0], b[3])
                    r1, c1 = pix(b[2], b[1])
                    r0, c0, r1, c1 = max(r0 - 1, 0), max(c0 - 1, 0), min(r1 + 2, H), min(c1 + 2, W)
                    win_tr = rt.from_origin(minx + c0 * res, maxy - r0 * res, res, res)
                    cm = rasterize([(buf, 1)], (r1 - r0, c1 - c0), win_tr)
                    sub, _ = label(O[r0:r1, c0:c1] & cm, structure=np.ones((3, 3), int))
                    ea, eb = ends[sid]
                    la = endpoint_label(sub, ea[0] - r0, ea[1] - c0, k)
                    lb = endpoint_label(sub, eb[0] - r0, eb[1] - c0, k)
                    same[sid] = la != 0 and la == lb
                result[(r, "local", k, cw)] = same
            print(f"   회랑 {cw:>4}m · k=" + " · ".join(f"{k}px: {sum(result[(r, 'local', k, cw)].values()):,}" for k in ks) + f"   (/{len(seg):,})")
        del O, lab
    return result


def crosstab(seg, same, title):
    c = Counter((v, bool(same[sid])) for sid, v in seg["verdict"].items())
    print(f"\n② {title}")
    print(f"   {'판정':9s} {'이어진다':>8s} {'안 이어진다':>10s} {'합':>6s}")
    for v in ("clear", "needs_cv", "unknown", "blocked"):
        a, b = c[(v, True)], c[(v, False)]
        print(f"   {v:9s} {a:8,d} {b:10,d} {a + b:6,d}")


def lists(seg, same, tag):
    v = seg["verdict"]
    s3 = [sid for sid in seg.index if v[sid] == "clear" and not same[sid]]
    s4 = [sid for sid in seg.index if v[sid] == "blocked" and same[sid]]
    print(f"   {tag}  ③ clear 인데 안 이어진다 {len(s3)}  ④ blocked 인데 이어진다 {len(s4)}")
    return set(s3), set(s4)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--res", type=float, nargs="*", default=[0.5, 0.25], help="m/px (기본 0.5 0.25)")
    ap.add_argument("--radii", type=float, nargs="*", default=[1.5, 3.5], help="구조요소 반지름 m (1.5 = 소방차 · 3.5 = 양쪽 주차)")
    ap.add_argument("--k", type=int, nargs="*", default=[1, 3, 5], help="끝점 라벨 창 반경(px)")
    ap.add_argument("--corridor", type=float, nargs="*", default=[4.0, 6.0, 10.0], help="국소 라벨링 회랑 폭 m (민감도)")
    ap.add_argument("--show", type=int, default=30, help="③④ 목록에 낼 최대 줄")
    ap.add_argument("--selftest", action="store_true", help="판별식이 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    area_u, seg = load_inputs()
    print(f"구간 {len(seg):,} · 판정 {dict(seg['verdict'].value_counts())} · 도로면 폴리곤 {len(getattr(area_u, 'geoms', [area_u]))} (unary_union 뒤)")
    allres = {res: run_resolution(area_u, seg, res, a.radii, a.k, a.corridor) for res in a.res}

    print("\n" + "═" * 78 + "\n②③④ 교차표 — 국소(회랑 6m · k=3px)를 주표로, 전역(k=3px)을 대조로\n" + "═" * 78)
    keep = {}
    for res, result in allres.items():
        for r in a.radii:
            crosstab(seg, result[(r, "local", 3, 6.0)], f"해상도 {res} · r={r} · 회랑 6m 국소")
            crosstab(seg, result[(r, "global", 3, None)], f"해상도 {res} · r={r} · 전역 성분")
            for mode, key in (("국소 6m", (r, "local", 3, 6.0)), ("전역", (r, "global", 3, None))):
                keep[(res, r, mode)] = lists(seg, result[key], f"{res}m/px r={r} {mode}")

    print("\n" + "═" * 78 + "\n해상도 · k · 회랑 민감도 — ③④ 목록이 얼마나 흔들리나 (r=1.5 · 국소)\n" + "═" * 78)
    if len(a.res) >= 2 and 1.5 in a.radii:
        r0, r1 = a.res[0], a.res[1]
        for i, nm in ((0, "③"), (1, "④")):
            A_, B_ = keep[(r0, 1.5, "국소 6m")][i], keep[(r1, 1.5, "국소 6m")][i]
            u = len(A_ | B_)
            print(f"   {nm} 해상도 {r0} 대 {r1}: {len(A_)} 대 {len(B_)} · 공통 {len(A_ & B_)} · 합집합 {u} · 일치율 {(len(A_ & B_) / u * 100 if u else 100):.0f}%")
    for res, result in allres.items():
        if 1.5 not in a.radii:
            continue
        print(f"   해상도 {res} · r=1.5 국소 — k 별(회랑 6m) · 회랑 별(k=3):")
        for k in a.k:
            s3, s4 = lists(seg, result[(1.5, "local", k, 6.0)], f"   k={k}px")
        for cw in a.corridor:
            lists(seg, result[(1.5, "local", 3, cw)], f"   회랑 {cw}m")

    print("\n" + "═" * 78 + "\n③ clear 인데 r=1.5 원이 양끝을 안 잇는 구간 (국소 6m · k=3px · 해상도별)\n" + "═" * 78)
    for res in a.res:
        s3, s4 = keep[(res, 1.5, "국소 6m")] if 1.5 in a.radii else (set(), set())
        rows = seg.loc[sorted(s3)]
        print(f"\n[해상도 {res}] {len(s3)}개 — " + " ".join(rows.index[: a.show]) + (" …" if len(rows) > a.show else ""))
        print(f"[해상도 {res}] ④ blocked 인데 이어진다 {len(s4)}개 — " + " ".join(sorted(s4)[: a.show]) + (" …" if len(s4) > a.show else ""))
    print("\n★ 아무것도 안 바꿨다 — 판정 · 칸 · 산출물 없음. 결과가 쓸 만하면 그때 설계를 정한다.")
    return 0


def selftest() -> int:
    """EDT 방식 opening 이 디스크 구조요소 방식과 맞나, 끝점 최빈 라벨이 경계에서 0 을 피하나, 좁은 목이 opening 에서 끊기나."""
    from scipy.ndimage import binary_opening, label
    bad: list[str] = []
    res = 0.5
    A = np.zeros((120, 200), bool)
    A[10:50, 5:80] = True            # 넓은 도로(20m 폭)
    A[10:50, 120:195] = True         # 넓은 도로 둘째
    A[28:32, 80:120] = True          # 좁은 목(폭 2m · 길이 20m)
    r = 1.5
    got = opening_edt(A, r, res)
    n = round(r / res)
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
    ref = binary_opening(A, structure=(yy ** 2 + xx ** 2) <= n * n)
    diff = (got ^ ref).sum() / max(ref.sum(), 1)
    if diff > 0.03:
        bad.append(f"EDT opening 이 디스크 opening 과 {diff * 100:.1f}% 다르다")
    lab, ncomp = label(got, structure=np.ones((3, 3), int))
    if ncomp != 2:
        bad.append(f"폭 2m 목이 r=1.5(폭 3m)에서 안 끊긴다 — 성분 {ncomp}")
    if endpoint_label(lab, 30, 100, 1) != 0:
        bad.append("끊긴 목 안의 점이 라벨을 받았다")
    a, b = endpoint_label(lab, 30, 40, 1), endpoint_label(lab, 30, 150, 1)
    if a == 0 or b == 0 or a == b:
        bad.append(f"두 도로가 같은 성분이거나 라벨이 0 이다 — {a} {b}")
    # 경계에 걸린 끝점: 창이 0 이 아닌 라벨을 집어야 한다
    edge = endpoint_label(lab, 9, 40, 2)            # 도로 위 경계 바로 밖 한 줄
    if edge == 0:
        bad.append("경계에 걸린 끝점이 창에서도 라벨 0 이다")
    if not np.array_equal(opening_edt(A, r, res, strip_rows=17), got):
        bad.append("띠로 나눈 opening 이 전체 처리와 다르다 — halo 가 모자란다")
    if opening_edt(A, 0.4, res).sum() != A.sum():
        bad.append("반지름이 한 픽셀 미만이면 도로면이 그대로여야 한다")
    for x in bad:
        print("  ✗", x)
    print("✓ 살아 있다" if not bad else f"✗ {len(bad)}건")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
xsec_leak.py — 교차부 제외가 **폴리곤 밖에 남기는 오염**을 잰다. 읽고 표를 낸다.  (PLAN #247 · DECISIONS §791)

    uv run python tools/xsec_leak.py                  ① 판독 지점 · ② 등가반경 · ③ 최소폭 표본의 경계 거리 · ④ 폴리곤 없는 교차로
    uv run python tools/xsec_leak.py --grid 0,1,2,3,5  후보 상수 버퍼마다 「남는 표본으로 최소폭이 바뀌는 구간 · 표본 0 이 되는 구간」(판정은 안 돌린다)

── 왜 있나 ────────────────────────────────────────────────────
`seg/width.py` 의 교차부 제외는 폴리곤 **안** 표본만 뺀다. 폴리곤이 실제 벌어진 범위보다 작으면 그 차이만큼 오염이 남는다.
사람이 판독표(`data/field/roadview_hypo_2611.csv`)의 가설 「나」 12행을 읽었더니 5행이 「교차부」였다(DECISIONS §791).
전체 평균에는 안 보이고 최솟값에서만 터지므로 **전체 표본이 아니라 구간의 최소폭 표본**을 잰다.

── 표본점을 어떻게 되살리나 ──────────────────────────────────
`width_samples.csv` 에는 좌표가 없고 구간 시작에서 몇 m(`s_m`)만 있다. 구간선(`segments_5186.gpkg`)의 길이가 `length_m` 과
0.05m 안에서 같아(실측) 그 선을 `s_m` 만큼 따라간 점이 **엔진이 쟀던 그 점**이다(판독표의 보간과 달리 비율을 안 쓴다).

IN    `data/processed/` 의 `segments_5186.gpkg` · `width_samples.csv` · `ngii1k_xsec_5186.gpkg` · `data/field/roadview_hypo_2611.csv`
OUT   화면 표만. 파일을 안 쓴다 · 판정을 안 돌린다(후보 판정은 격리 사본에서 따로 — DECISIONS §791)
PARAM `NEAR_M` 5.0(오염 의심 문턱 · 폴리곤 밖 이 안) · `FALLBACK_M` 10.0(`width.py` 가 폴리곤을 믿는 거리 = `XSEC_EXCL`·2)
밖    **교차부 폴리곤이 맞는지는 안 본다**(원천 그대로) · 노드는 구간 끝점 차수 3 이상으로 근사한다(엔진은 그래프 노드 — 같지 않다)
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398 — 어느 관문에도 안 올렸다)
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
SHEET = ROOT / "data" / "field" / "roadview_hypo_2611.csv"
NEAR_M, FALLBACK_M, TOL_M = 5.0, 10.0, 0.011
BINS = ((0, 0.5), (0.5, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 1e9))


def load():
    seg = gpd.read_file(PROC / "segments_5186.gpkg").set_index("seg_uid")
    smp = pd.read_csv(PROC / "width_samples.csv", encoding="utf-8-sig")
    xs = gpd.read_file(PROC / "ngii1k_xsec_5186.gpkg", layer="ngii1k_xsec").to_crs(5186)
    polys = list(xs.geometry.buffer(0))
    return seg, smp, polys, unary_union(polys)


def nodes(seg) -> list[Point]:
    """구간 끝점(0.1m 반올림)이 세 번 이상 나오는 자리."""
    deg = Counter()
    for ln in seg.geometry:
        c = list(ln.coords)
        for q in (c[0], c[-1]):
            deg[(round(q[0], 1), round(q[1], 1))] += 1
    return [Point(k) for k, v in deg.items() if v >= 3]


def min_points(seg, smp, union) -> pd.DataFrame:
    """구간마다 **발행 최소폭을 낸** 표본점. 발행값(`width_min_m`)과 안 맞는 구간은 뺀다(중심선 가름이 다시 잰 구간)."""
    out = []
    for uid, gr in smp.groupby("seg_uid", sort=False):
        v = gr[gr.w_m.notna()]
        if v.empty:
            continue
        r = v.loc[v.w_m.idxmin()]
        if abs(r.w_m - seg.at[uid, "width_min_m"]) > TOL_M:
            continue
        p = seg.at[uid, "geometry"].interpolate(r.s_m)
        out.append({"seg_uid": uid, "seg_id": r.seg_id, "s_m": r.s_m, "w": r.w_m, "x": p.x, "y": p.y,
                    "out_m": union.distance(p), "road": seg.at[uid, "road_name"]})
    return pd.DataFrame(out)


def sheet_points() -> list[tuple[int, str, str]]:
    """판독표에서 가설 「나」 가 「교차부」 라고 답한 행 — (순번, seg_uid, 도로명)."""
    rows = [r for r in csv.DictReader(line for line in SHEET.open(encoding="utf-8-sig") if not line.startswith("#"))]
    return [(int(r["순번"]), r["seg_uid"], r["도로명"]) for r in rows if r["가설"] == "나" and r["답"] == "교차부"]


def part1(M, node_u) -> list[str]:
    out = ["① 판독표 「나」 교차부 답 — 최소폭 표본점이 폴리곤 경계 밖 몇 m 인가(표본 좌표 = width_samples 의 s_m 을 구간선 위에서 되살린 점)",
           "순번  seg_id   도로명            s_m   w(m)  폴리곤 밖(m)  구간 끝 노드까지(m)  경로"]
    byu = M.set_index("seg_uid")
    for n, uid, road in sheet_points():
        if uid not in byu.index:
            out.append(f"{n:>3}   {uid}  (발행 최소폭과 안 맞아 못 되살림)")
            continue
        r = byu.loc[uid]
        nd = node_u.distance(Point(r.x, r.y))
        how = "폴리곤 경계 밖" if r.out_m < FALLBACK_M else f"폴리곤 {FALLBACK_M:.0f}m 안에 없음 → 반경 폴백"
        out.append(f"{n:>3}   {r.seg_id}  {road:<14} {r.s_m:6.1f} {r.w:6.2f} {r.out_m:9.2f} {nd:14.2f}      {how}")
    return out


def part2(polys, seg) -> list[str]:
    allr = np.array([math.sqrt(p.area / math.pi) for p in polys])
    near = unary_union(list(seg.geometry)).buffer(1.0)
    r1 = np.array([math.sqrt(p.area / math.pi) for p in polys if p.intersects(near)])
    f = lambda a: f"n={len(a)} 중앙 {np.median(a):.2f} p90 {np.quantile(a, .9):.2f} 최대 {a.max():.2f}"
    return ["② 교차부 폴리곤 등가반경(√(면적/π), m)", f"  파일 전체   {f(allr)}", f"  구간선 1m 안에 닿는 것   {f(r1)}"]


def part3(M) -> list[str]:
    o = M.out_m.to_numpy()
    out = [f"③ 최소폭 표본(발행값과 맞는 {len(M)}구간)이 폴리곤 경계 밖 몇 m 인가 — 안(경계 안쪽)은 0(안이면 엔진이 이미 뺐다)"]
    for lo, hi in BINS:
        c = int(((o > lo) & (o <= hi)).sum()) if lo else int((o <= hi).sum())
        out.append(f"  밖 {lo:g}~{hi:g}m   {c:>5}" if hi < 1e8 else f"  밖 {lo:g}m 초과  {c:>5}")
    out.append(f"  ★ 오염 의심(밖 0~{NEAR_M:g}m) {int((o <= NEAR_M).sum())}구간 / {len(o)}  (의심일 뿐이다 — 길이 교차부 옆을 지나는 것일 수도 있다)")
    return out


def part4(M, nlist, union) -> list[str]:
    d = np.array([union.distance(p) for p in nlist])
    far = int((d >= FALLBACK_M).sum())
    nofb = int((M.out_m >= FALLBACK_M).sum())
    return ["④ 폴리곤이 없어 반경 5m 폴백을 타는 교차로",
            f"  노드(차수≥3 · 근사) {len(nlist)}개 중 폴리곤 {FALLBACK_M:g}m 안에 없는 것 {far}개 ({100 * far / len(nlist):.1f}%)",
            f"  최소폭 표본이 폴리곤 {FALLBACK_M:g}m 밖(=그 자리는 반경 폴백이 판정)인 구간 {nofb} / {len(M)}"]


def grid(M, smp, seg, polys, buffers) -> list[str]:
    """후보 상수 버퍼 b 마다 — 표본을 엔진처럼 다시 거른다(폴리곤 안 + 경계 b 이내 제외 · 폴리곤 10m 밖은 건드리지 않는다).
    남는 표본이 0 이면 `width_fail` 후보다. **판정은 못 낸다**(다른 소스 · 가름 규칙이 같이 움직인다)."""
    pts = {}
    for uid, gr in smp.groupby("seg_uid", sort=False):
        ln = seg.at[uid, "geometry"]
        v = gr[gr.w_m.notna()]
        pts[uid] = (v, [ln.interpolate(s) for s in v.s_m])
    union = unary_union(polys)
    out = ["후보 상수 버퍼(m) → 폭이 바뀌는 구간 · 표본이 0 이 되는 구간(정적 재거름 · 판정 아님)", "  b    wmin 바뀜  표본 0"]
    for b in buffers:
        ch = zero = 0
        for v, ps in pts.values():
            if v.empty:
                continue
            keep = [w for w, p in zip(v.w_m, ps, strict=True) if union.distance(p) > b or union.distance(p) >= FALLBACK_M]
            if not keep:
                zero += 1
            elif abs(min(keep) - v.w_m.min()) > 0.005:
                ch += 1
        out.append(f"  {b:<4g} {ch:>8} {zero:>9}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grid", help="쉼표로 가른 버퍼 후보(m)")
    a = ap.parse_args(argv)
    seg, smp, polys, union = load()
    M = min_points(seg, smp, union)
    nl = nodes(seg)
    blocks = [part1(M, unary_union(nl)), part2(polys, seg), part3(M), part4(M, nl, union)]
    if a.grid:
        blocks.append(grid(M, smp, seg, polys, [float(x) for x in a.grid.split(",")]))
    print("\n\n".join("\n".join(b) for b in blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main())

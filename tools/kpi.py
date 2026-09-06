#!/usr/bin/env python3
"""
tools/kpi.py — 이 프로젝트가 무엇을 막는지 숫자로 낸다.

    uv run python tools/kpi.py
    uv run python tools/kpi.py --csv data/processed/kpi_failed.csv

── 왜 생겼나 ───────────────────────────────────────────────────
발표에서 반드시 나오는 질문이 있다 — **"동명동은 차로 5분이면 다 가는데
내비가 왜 필요한가."** 맞는 지적이고, 시간 단축은 우리 KPI 가 아니다.

진짜 KPI 는 **진입 실패**다. 폭을 모르는 내비는 소방차가 못 지나가는
골목으로 안내하고, 그러면 후진해서 빠져나와 우회해야 한다. 8m 짜리
펌프차의 후진은 극도로 느리고 골든타임이 통째로 날아간다.

★ 이 숫자를 문서에 손으로 적지 마라. 판정이 바뀌면 같이 바뀐다.
  `MASTER §15`(발표용 숫자)에 넣을 때 이 도구를 근거로 적는다 —
  `docnum_check` 가 대조할 수 있게.

★ 계산 조건을 출력에 함께 낸다. 조건 없는 숫자는 인용될 때 반드시
  왜곡된다 — 어느 안전센터에서 어떤 필요폭으로 잰 것인지가 붙어야 한다.

IN    web/data/segments.geojson · seg/params.py (STATIONS · NODE_TOL)
OUT   stdout · --csv
PARAM --need 3.0 · --station · --csv
"""
from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from firelane.seg.params import NODE_TOL, STATIONS

WEB = ROOT / "web" / "data"
LAT0 = 35.151
MX = 111320 * math.cos(math.radians(LAT0))
MY = 110574


def _coords(g: dict) -> list:
    if g["type"] == "LineString":
        return g["coordinates"]
    return [p for part in g["coordinates"] for p in part]


def _node_index(feats: list, tol: float):
    """끝점을 tol 로 접합한다. `seg/graph.py` 와 같은 NODE_TOL 을 쓴다."""
    ends = []
    for f in feats:
        c = _coords(f["geometry"])
        ends.append((c[0][0] * MX, c[0][1] * MY))
        ends.append((c[-1][0] * MX, c[-1][1] * MY))
    parent = list(range(len(ends)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cells: dict = defaultdict(list)
    for i, (x, y) in enumerate(ends):
        cells[(int(x // tol), int(y // tol))].append(i)
    for i in range(len(ends)):
        x, y = ends[i]
        kx, ky = int(x // tol), int(y // tol)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cells.get((kx + dx, ky + dy), ()):
                    if j != i and math.dist(ends[i], ends[j]) <= tol:
                        a, b = find(i), find(j)
                        if a != b:
                            parent[a] = b
    return {i: find(i) for i in range(len(ends))}, ends


def _dijkstra(g: dict, s: int):
    d = {s: 0.0}
    prev: dict = {}
    pq = [(0.0, s)]
    seen: set = set()
    while pq:
        c, u = heapq.heappop(pq)
        if u in seen:
            continue
        seen.add(u)
        for v, w, i in g[u]:
            if c + w < d.get(v, math.inf):
                d[v] = c + w
                prev[v] = (u, i)
                heapq.heappush(pq, (c + w, v))
    return d, prev


def _path(prev: dict, s: int, t: int):
    out = []
    cur = t
    while cur != s:
        if cur not in prev:
            return None
        u, i = prev[cur]
        out.append(i)
        cur = u
    return out[::-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--need", type=float, default=3.0,
                    help="소방차 필요폭(m). 정본은 seg/params.py 다")
    ap.add_argument("--station", default=None, help="안전센터 이름. 미지정이면 전부")
    ap.add_argument("--csv", help="실패 목적지 목록을 파일로")
    a = ap.parse_args()

    src = WEB / "segments.geojson"
    if not src.exists():
        print(f"★ {src} 가 없다.  uv run fire-lane", file=sys.stderr)
        return 1
    feats = json.load(src.open(encoding="utf-8"))["features"]
    nid, _ = _node_index(feats, NODE_TOL)

    # 노드 대표 좌표
    pos: dict = {}
    for i, f in enumerate(feats):
        c = _coords(f["geometry"])
        pos.setdefault(nid[2 * i], (c[0][0] * MX, c[0][1] * MY))
        pos.setdefault(nid[2 * i + 1], (c[-1][0] * MX, c[-1][1] * MY))

    def build(width_aware: bool) -> dict:
        """width_aware=False 면 **폭을 모르는 내비**다 — 상용의 대역."""
        g: dict = defaultdict(list)
        for i, f in enumerate(feats):
            p = f["properties"]
            u, v = nid[2 * i], nid[2 * i + 1]
            if u == v:
                continue
            if width_aware:
                w = p.get("width_min_m")
                if p["verdict"] == "blocked" or w is None or w < a.need:
                    continue
            L = p.get("length_m") or 1.0
            g[u].append((v, L, i))
            g[v].append((u, L, i))
        return g

    naive = build(False)
    safe = build(True)

    names = [a.station] if a.station else list(STATIONS)
    rows: list[dict] = []
    ratios: list[float] = []
    per_route_bad: list[int] = []
    tot = tot_fail = 0

    for nm in names:
        lon, lat = STATIONS[nm]
        x, y = lon * MX, lat * MY
        s_n = min(naive, key=lambda n: (pos[n][0] - x) ** 2 + (pos[n][1] - y) ** 2)
        s_s = min(safe, key=lambda n: (pos[n][0] - x) ** 2 + (pos[n][1] - y) ** 2)
        _, pn = _dijkstra(naive, s_n)
        ds, ps = _dijkstra(safe, s_s)

        for t in ds:
            pnaive = _path(pn, s_n, t)
            if not pnaive:
                continue
            tot += 1
            bad = [i for i in pnaive
                   if feats[i]["properties"]["verdict"] == "blocked"
                   or (feats[i]["properties"].get("width_min_m") or 99) < a.need]
            if bad:
                tot_fail += 1
                per_route_bad.append(len(bad))
                w = feats[bad[0]]["properties"]
                rows.append({
                    "station": nm, "node": t, "blocked_count": len(bad),
                    "first_blocked_uid": w.get("seg_uid"),
                    "first_blocked_label": w.get("seg_label"),
                    "first_blocked_width_m": w.get("width_min_m"),
                    "first_blocked_verdict": w.get("verdict"),
                })
            psafe = _path(ps, s_s, t)
            if psafe:
                ln = sum(feats[i]["properties"].get("length_m") or 0 for i in pnaive)
                ls = sum(feats[i]["properties"].get("length_m") or 0 for i in psafe)
                if ln > 0:
                    ratios.append(ls / ln)

    ratios.sort()
    print("── 계산 조건 ──────────────────────────────────────")
    print(f"  안전센터        {', '.join(names)}")
    print(f"  필요폭          {a.need}m   (정본: seg/params.py)")
    print(f"  노드접합        {NODE_TOL}m")
    print(f"  구간            {len(feats)}")
    print()
    print("── KPI ────────────────────────────────────────────")
    print(f"  도달 목적지                        {tot}")
    print(f"  폭 미인지 내비가 통행불가를 지남    "
          f"{tot_fail} ({tot_fail / max(1, tot) * 100:.0f}%)")
    if per_route_bad:
        print(f"    경로당 통행불가 구간            "
              f"중앙 {st.median(per_route_bad):.0f} · 최대 {max(per_route_bad)}")
    if ratios:
        print(f"  우리 경로 / 그 경로 실거리비       "
              f"중앙 {st.median(ratios):.2f} · p90 {ratios[int(len(ratios) * .9)]:.2f}")
    print()
    print("  → 시간을 줄이는 앱이 아니라 **못 가는 길로 보내지 않는 앱**이다.")

    if a.csv and rows:
        out = Path(a.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n→ {out}  ({len(rows)}행)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

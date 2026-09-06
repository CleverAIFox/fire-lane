#!/usr/bin/env python3
"""
tools/bottleneck.py — 끊기면 뒤가 통째로 막히는 구간을 찾는다.

    uv run python tools/bottleneck.py                    표만
    uv run python tools/bottleneck.py --csv out.csv      좌표까지
    uv run python tools/bottleneck.py --min-lost 5       임계 조정

── 왜 생겼나 ───────────────────────────────────────────────────
실측 우선순위 축이 하나뿐이었다 — `width_disagree_m`·`width_cov` 는
**측정이 불확실한 곳**을 고른다. 그것과 별개로 **경로가 무너지는 곳**이
있고, 그쪽이 훨씬 적다.

    다리(bridge)          382 / 907 엣지 (42%)
      1개만 끊김           248   막다른 골목이다. 병목이 아니다
      2-4개                 90
      5개 이상              44   ← 이것이 진짜 병목
        그중 불확실          18   ← 실측 1순위

**1,101 구간 전수 실측은 불가능하지만 18곳은 하루면 된다.** 그 18곳을
내는 것이 이 도구의 전부다.

★ 다리의 42% 라는 수치를 그대로 인용하지 마라. 골목 동네에서 막다른
  길은 정의상 전부 다리다. 의미 있는 것은 `--min-lost` 이상만이다.

★ blocked 를 뺀 그래프에서 잰다. 이미 막힌 길은 끊을 것이 없다.
  안전센터에서 도달 가능한 성분만 본다 — 거기서만 출동이 시작된다.

IN    web/data/segments.geojson · src/firelane/seg/params.py (STATIONS · NODE_TOL)
OUT   stdout (표) · --csv 로 파일
PARAM --min-lost 5 · --csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from firelane.seg.params import NODE_TOL, STATIONS

WEB = ROOT / "web" / "data"

# 동명동 중심 위도 기준 등거리 근사. 3km 범위라 오차가 cm 급이다.
LAT0 = 35.151
MX = 111320 * math.cos(math.radians(LAT0))
MY = 110574


def _coords(geom: dict) -> list:
    if geom["type"] == "LineString":
        return geom["coordinates"]
    return [p for part in geom["coordinates"] for p in part]


def _build(feats: list, tol: float):
    """끝점을 tol 로 접합해 무향 그래프를 만든다.

    ★ `seg/graph.py` 와 같은 NODE_TOL 을 쓴다. 여기서 다른 값을 쓰면
      파이프라인이 낸 연결성과 이 도구가 보는 연결성이 갈린다.
    """
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
    for i, (x, y) in enumerate(ends):
        kx, ky = int(x // tol), int(y // tol)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cells.get((kx + dx, ky + dy), ()):
                    if j != i and math.dist(ends[i], ends[j]) <= tol:
                        a, b = find(i), find(j)
                        if a != b:
                            parent[a] = b

    nid: dict[int, int] = {}
    nodes: list[tuple[float, float]] = []
    groups: dict = defaultdict(list)
    for i in range(len(ends)):
        groups[find(i)].append(i)
    for members in groups.values():
        idx = len(nodes)
        nodes.append((sum(ends[k][0] for k in members) / len(members),
                      sum(ends[k][1] for k in members) / len(members)))
        for k in members:
            nid[k] = idx
    return nid, nodes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-lost", type=int, default=5,
                    help="이만큼 이상 끊는 것만 병목으로 본다 (기본 5)")
    ap.add_argument("--csv", help="좌표·구글맵 링크까지 파일로")
    a = ap.parse_args()

    try:
        import networkx as nx
    except ImportError:
        return _die("networkx 가 없다.  uv sync --all-extras")

    src = WEB / "segments.geojson"
    if not src.exists():
        return _die(f"{src} 가 없다.  uv run fire-lane")

    feats = json.load(src.open(encoding="utf-8"))["features"]
    nid, nodes = _build(feats, NODE_TOL)

    # blocked 를 뺀 그래프. 이미 막힌 길은 끊을 것이 없다.
    G = nx.Graph()
    for i, f in enumerate(feats):
        p = f["properties"]
        if p["verdict"] == "blocked":
            continue
        a_, b_ = nid[2 * i], nid[2 * i + 1]
        if a_ == b_ or G.has_edge(a_, b_):
            continue
        G.add_edge(a_, b_, idx=i, **{k: p.get(k) for k in (
            "seg_uid", "verdict", "width_min_m", "width_max_m", "width_cov",
            "width_disagree_m", "n_sample", "width_src", "length_m",
            "seg_label", "road_name", "in_emd", "cctv_dist_m")})

    # 안전센터에서 도달 가능한 성분만. 거기서만 출동이 시작된다.
    def nearest(lon: float, lat: float) -> int:
        x, y = lon * MX, lat * MY
        return min(G.nodes, key=lambda n: (nodes[n][0] - x) ** 2 + (nodes[n][1] - y) ** 2)

    src_nodes = [nearest(*v[:2]) if isinstance(v, (list, tuple)) else nearest(v["lon"], v["lat"])
                 for v in _station_coords()]
    reach: set = set()
    for s in src_nodes:
        if s in G:
            reach |= nx.node_connected_component(G, s)
    sub = G.subgraph(reach).copy()
    print(f"안전센터 도달 성분: 노드 {sub.number_of_nodes()} · 엣지 {sub.number_of_edges()}")

    bridges = list(nx.bridges(sub))
    print(f"다리(bridge): {len(bridges)} ({len(bridges) / max(1, sub.number_of_edges()) * 100:.0f}%)")

    rows = []
    hist = Counter()
    for u, v in bridges:
        d = sub[u][v]
        H = sub.copy()
        H.remove_edge(u, v)
        r: set = set()
        for s in src_nodes:
            if s in H:
                r |= nx.node_connected_component(H, s)
        lost = sub.number_of_nodes() - len(r)
        hist["1 (막다른길)" if lost == 1 else "2-4" if lost <= 4
             else "5-9" if lost <= 9 else "10+"] += 1
        if lost < a.min_lost:
            continue
        c = _coords(feats[d["idx"]]["geometry"])
        lon, lat = c[len(c) // 2]
        rows.append({
            "lost_nodes": lost,
            "uncertain": int(d["verdict"] in ("unknown", "needs_cv")),
            **{k: d.get(k) for k in (
                "seg_uid", "verdict", "width_min_m", "width_max_m", "width_cov",
                "width_disagree_m", "n_sample", "width_src", "length_m",
                "seg_label", "road_name", "in_emd", "cctv_dist_m")},
            "lon": round(lon, 6), "lat": round(lat, 6),
            "gmaps": f"https://maps.google.com/?q={lat:.6f},{lon:.6f}",
        })

    print("잃는 노드 수 분포:", dict(hist))
    rows.sort(key=lambda x: (-x["uncertain"], -x["lost_nodes"]))
    unc = [x for x in rows if x["uncertain"]]
    print(f"\n병목({a.min_lost}개 이상 차단) {len(rows)} · 그중 불확실 {len(unc)}")

    print(f"\n── 실측 1순위: 불확실 병목 {len(unc)}곳 ──")
    for x in unc:
        print(f"  {x['lost_nodes']:3d}노드  {x['verdict']:9s} "
              f"w={x['width_min_m']} cov={x['width_cov']} n={x['n_sample']}  "
              f"{x['seg_label']}")

    if a.csv:
        out = Path(a.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n→ {out}")
    return 0


def _station_coords() -> list:
    """params.STATIONS 의 형태가 무엇이든 (lon, lat) 목록으로 만든다."""
    out = []
    for v in (STATIONS.values() if isinstance(STATIONS, dict) else STATIONS):
        if isinstance(v, dict):
            out.append((v.get("lon") or v.get("x"), v.get("lat") or v.get("y")))
        else:
            out.append((v[0], v[1]))
    return out


def _die(msg: str) -> int:
    print(f"★ {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

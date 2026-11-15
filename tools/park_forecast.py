#!/usr/bin/env python3
"""
park_forecast.py — **단속이력 가중치의 예보.** 가중치를 켜면 경로가 얼마나 바뀌나(값은 사람이 고른다).  (PLAN #31 · #60 · DECISIONS §794)

    uv run python tools/park_forecast.py                       붙은 정도 · 영상판정 불가 구간의 근거 · 경로 예보 표
    uv run python tools/park_forecast.py --ks 0.05,0.1,0.4     가중치 후보(`parkPer1000`)를 바꿔 본다

── 왜 있나 ────────────────────────────────────────────────────
`web/navi/src/domain/pressure.ts` 의 `pressureFactor` 는 구간 비용에 `1 + park/1000 × parkPer1000` 을 곱한다. 계수 `parkPer1000` 은 지금 **0** 이다
(근거 없는 상수를 안 만든다는 뜻 — `tools/cost_inputs.py`). 사람이 **낮은 가중치로 쓰기로** 했고 값은 **예보를 보고 고른다**(PLAN #31 도착 ③).
이 도구가 그 예보다: 후보 값마다 센터에서 건물 쪽 노드까지 최단 경로(길이)가 가중 경로와 달라지는 비율 · 늘어나는 길이 · 비용 배수의 크기를 낸다.
같은 자료를 **CCTV 없는 구간의 추정**에도 쓴다(PLAN #60) — 영상판정 불가 구간 중 몇이 근거 있는 가중치를 받는지 센다.

── 무엇이 「근거 있는 가중치」인가 ────────────────────────────
`park` 는 **도로명 단위** 단속 건수다(`publish_navi._parking` — 도로명이 붙은 54,541행만 센다 · 나머지 87,015행은 지번 표기라 안 붙는다).
같은 도로의 모든 구간이 같은 수를 받는다 — 구간 단위가 아니다. 지번을 구간에 붙이는 지오코딩은 **동명동만** 된다(내비DB 가 동명동 한 법정동이다).
그래서 이 도구가 세는 「근거」는 「그 도로의 단속 건수가 0 보다 크다」이고 구간마다의 상습도가 아니다 — 한계로 같이 찍는다.

IN    `web/data/navi_graph.json`(구간 · 노드 · `park`) · `data/processed/segments.geojson`(판정 · 사유) · `data/processed/fire_station.geojson`
OUT   화면 표만. 파일을 안 쓴다 · 판정을 안 읽는다(`verdict` 는 영상판정 불가를 세는 데만 쓴다)
PARAM `KS` 0.05 · 0.1 · 0.2 · 0.4 · 1.0 · `N_DEST` 400 · `SEED` 20261115 · `STRONG` 100
밖    **실제 `edge_cost`**(폭 · 판정 · 회전 · 일방통행)를 안 부른다 — 길이에 단속 배수만 곱한 경로다. 실제 경로 변화는 이 예보보다 작거나 다를 수 있다.
      **단속 이력이 점유를 뜻하는지**는 안 본다(단속 시각은 순찰 시간이다 — §561-5). 값을 고르지 않는다(사람이 고른다).
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "web" / "data" / "navi_graph.json"
SEGS = ROOT / "data" / "processed" / "segments.geojson"
STATIONS = ROOT / "data" / "processed" / "fire_station.geojson"
KS = (0.05, 0.1, 0.2, 0.4, 1.0)
N_DEST, SEED, STRONG = 400, 20261115, 100


def build(edges: list[dict], k: float) -> nx.Graph:
    """무향 그래프. 평행 간선은 가장 싼 것만 둔다. 비용 = 길이 × (1 + park/1000 × k)."""
    g = nx.Graph()
    for i, e in enumerate(edges):
        w = float(e["length_m"]) * (1.0 + (e.get("park") or 0) / 1000.0 * k)
        a, b = e["a"], e["b"]
        if g.has_edge(a, b) and g[a][b]["w"] <= w:
            continue
        g.add_edge(a, b, w=w, L=float(e["length_m"]), i=i)
    return g


def path_edges(g: nx.Graph, path: list[int]) -> tuple[int, ...]:
    return tuple(g[u][v]["i"] for u, v in zip(path, path[1:], strict=False))


def forecast(edges: list[dict], origins: list[int], ks, n_dest: int = N_DEST, seed: int = SEED) -> list[dict]:
    """후보 `k` 마다: 경로가 바뀐 비율 · 늘어난 길이(%) 분포 · 최대 비용 배수. 쌍은 센터 노드가 닿는 성분 안에서 시드로 뽑는다."""
    base = build(edges, 0.0)
    rng = random.Random(seed)  # noqa: S311 — 씨앗을 박은 재현용 표집이다. 암호가 아니다
    pairs = []
    for o in origins:
        comp = sorted(nx.node_connected_component(base, o) - {o})
        pairs += [(o, d) for d in rng.sample(comp, min(n_dest, len(comp)))]
    base_path = {pr: nx.shortest_path(base, *pr, weight="w") for pr in pairs}
    out = []
    for k in ks:
        g = build(edges, k)
        changed, extra = 0, []
        for pr in pairs:
            p = nx.shortest_path(g, *pr, weight="w")
            L0 = sum(base[u][v]["L"] for u, v in zip(base_path[pr], base_path[pr][1:], strict=False))
            if path_edges(g, p) != path_edges(base, base_path[pr]):
                changed += 1
                extra.append(100.0 * (sum(g[u][v]["L"] for u, v in zip(p, p[1:], strict=False)) / L0 - 1.0) if L0 else 0.0)
        mult = [1.0 + (e.get("park") or 0) / 1000.0 * k for e in edges]
        out.append({"k": k, "pairs": len(pairs), "changed": changed,
                    "extra_med": statistics.median(extra) if extra else 0.0,
                    "extra_p90": sorted(extra)[int(0.9 * (len(extra) - 1))] if extra else 0.0,
                    "extra_max": max(extra) if extra else 0.0,
                    "mult_med": statistics.median(mult), "mult_max": max(mult)})
    return out


def grounding(edges_by_uid: dict[str, dict], seg_props: list[dict]) -> dict:
    """영상판정 불가 구간 중 단속 도로 가중치를 받는 수(PLAN #60 도착 ③)."""
    unk = [p for p in seg_props if p.get("verdict") == "unknown"]
    cctv = [p for p in unk if str(p.get("unknown_reason") or "").startswith("no_cctv")]
    def n_with(rows, th):
        return sum(1 for p in rows if ((edges_by_uid.get(p["seg_uid"]) or {}).get("park") or 0) >= th)
    return {"unknown": len(unk), "unknown_no_cctv": len(cctv),
            "unknown_park_pos": n_with(unk, 1), "unknown_park_strong": n_with(unk, STRONG),
            "no_cctv_park_pos": n_with(cctv, 1), "no_cctv_park_strong": n_with(cctv, STRONG),
            "reasons": dict(Counter(str(p.get("unknown_reason")) for p in unk))}


def nearest_node(nodes: list[list[float]], lon: float, lat: float) -> int:
    return min(range(len(nodes)), key=lambda i: (nodes[i][0] - lon) ** 2 + (nodes[i][1] - lat) ** 2)


def render(counts: dict, g: dict, fc: list[dict]) -> list[str]:
    out = [f"① 단속 `park` 가 붙은 정도 — 구간 {counts['edges']} 중 0 초과 {counts['pos']} · 0 {counts['zero']} · 결측 {counts['null']} · 단속 건수 도로 단위(같은 도로는 같은 수)",
           f"   미배치 행 {counts['unplaced']:,}(지번 표기 — 지오코딩은 동명동만 된다)", "",
           f"② 영상판정 불가 구간 {g['unknown']} 중 단속 도로 가중치(`park` > 0) {g['unknown_park_pos']} · 강한 것(≥ {STRONG}건) {g['unknown_park_strong']}",
           f"   그중 CCTV 없음 계열 {g['unknown_no_cctv']} 중 `park` > 0 {g['no_cctv_park_pos']} · 강한 것 {g['no_cctv_park_strong']}", "",
           "③ 경로 예보(길이 × (1 + park/1000 × k) 의 최단 경로 대 길이 최단 경로 · 센터 → 노드 쌍)",
           "   k       쌍   바뀐 경로   늘어난 길이(바뀐 것 중앙 · p90 · 최대 %)   비용 배수(중앙 · 최대)"]
    for r in fc:
        out.append(f"   {r['k']:<6g} {r['pairs']:>5} {r['changed']:>5} ({100 * r['changed'] / r['pairs']:4.1f}%)   "
                   f"{r['extra_med']:5.1f} · {r['extra_p90']:5.1f} · {r['extra_max']:5.1f}                 {r['mult_med']:.2f} · {r['mult_max']:.2f}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--ks", help="쉼표로 가른 후보(`parkPer1000`)")
    a = ap.parse_args(argv)
    gj = json.loads(GRAPH.read_text(encoding="utf-8"))
    edges = gj["edges"]
    props = [f["properties"] for f in json.loads(SEGS.read_text(encoding="utf-8"))["features"]]
    st = json.loads(STATIONS.read_text(encoding="utf-8"))["features"]
    origins = []
    for f in st:
        nm = f["properties"].get("소방서 및 안전센터명", "")
        if "안전센터" in nm:
            lon, lat = f["geometry"]["coordinates"][:2]
            origins.append(nearest_node(gj["nodes"], lon, lat))
    cnt = gj["counts"]
    park = [e.get("park") for e in edges]
    counts = {"edges": len(edges), "pos": sum(1 for p in park if p), "zero": sum(1 for p in park if p == 0),
              "null": sum(1 for p in park if p is None), "unplaced": cnt.get("park_unplaced_rows", 0)}
    ks = [float(x) for x in a.ks.split(",")] if a.ks else KS
    print("\n".join(render(counts, grounding({e["seg_uid"]: e for e in edges}, props),
                           forecast(edges, sorted(set(origins)), ks))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

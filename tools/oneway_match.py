#!/usr/bin/env python3
"""
tools/oneway_match.py — 일방통행 두 목록(동구청 표 · 동부경찰서 hwpx)을 우리 구간에 대고 **발행이 어떻게 바뀔지를 계산**한다.  (DECISIONS §652)

    uv run python tools/oneway_match.py                  매칭 · 사유별 수 · 발행 변화(계산만)
    uv run python tools/oneway_match.py --sensitivity    역주행 배수가 경로를 얼마나 바꾸나
    uv run python tools/oneway_match.py --csv data/interim/oneway_match.csv

── 왜 생겼나 ──────────────────────────────────────────────────
`ow`(일방통행)는 이미 `navi_graph.json` 에 있다 — 57구간 중 방향이 확정된 것은 1곳이고 나머지 56은 `ow=2`(방향 모름)다. 방향의 유일한 출처가 표준노드링크인데 그것이 골목을 안 든다
(`nl_none` 44 · `nl_twoway` 10 · `nl_split` 2). 두 목록이 그 빈칸을 메울 후보다. 표는 **도로명 · 길이 · 시점부/종점부 지번**이고 우리는 `seg_uid` 다 — #186 의 본선 번지와 같은 꼴이다.

── 무엇을 하나 ────────────────────────────────────────────────
 ① 두 목록을 행으로 읽는다(표는 `norm` CSV · 경찰은 hwpx 원문). 병합 머리 3줄은 **위치로** 건너뛰고 머리글 글자를 검사한다(바뀌면 죽는다).
 ② 끝점 지번 → 좌표. `jijeok_5186.gpkg` 의 (법정동 · 지번) 필지 중심. 행정동(`지산1동`)은 법정동(`지산동`)으로 옮긴다. 지번이 없는 끝점(교 · 교차로)과 지적도에 없는 지번은 **사유로 센다.**
 ③ 매칭. 표의 도로명과 **같은 도로명의 구간만**으로 부분 그래프를 만들고 두 끝점에서 가장 가까운 노드 사이의 최단경로를 구해 길이를 표와 댄다.
    **붙음** = 두 끝점 오차 ≤ END_TOL_M · 길이비가 RATIO 안. **부분** = 한 끝점만 붙음(구간의 일부만 우리 안). 나머지는 사유별로 센다.
    ★ 두 문턱은 **관측된 틈**에서 골랐다 — 붙는 셋은 끝점 오차 ≤ 23m · 길이비 0.93~1.06 이고 나머지는 어느 하나가 크게 벗어난다(가장 가까운 것이 61m · 1.38). 이론으로 낸 수가 아니다.
 ④ 방향. 경로를 시점 → 종점으로 따라가며 구간의 a→b 와 같으면 `+1`, 반대면 `−1`. **표의 시점부 → 종점부가 통행 방향이라는 것은 문서에 적혀 있지 않다** — 경찰 문서가 방향을 화살표(→)로
    적는 행은 5개뿐이고 나머지는 범위(～)다. 이 도구는 근거 등급을 같이 낸다(아래).
 ⑤ 발행 변화. `ow` 가 어떻게 바뀔지(2 → ±1 · 0 인 곳과의 충돌)를 **계산만** 한다 — `navi_graph.json` 을 안 쓴다.

★ 판정을 안 바꾼다. `segments.geojson` · 판정 폐포 파일 · `navi_graph.json` 을 쓰지 않는다 — 읽기만 한다(`route_probe.py` · `cost_vs_dispatch.py` 와 같은 구조).

IN    data/processed/segments_5186.gpkg · jijeok_5186.gpkg · web/data/navi_graph.json · $FIRE_LANE_DATA/norm/gjcity/…oneway….csv · raw/gjpolice/…oneway….hwpx · web/navi/src/domain/rules.ts
OUT   stdout · --csv
PARAM --csv · --sensitivity
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
밖    **시점부 → 종점부가 통행 방향인지는 못 가린다** — 근거는 우리 `ow=1` 한 구간의 일치와 경찰 화살표 행 둘의 일치뿐이다(n=3). 지번이 없는 끝점(교 · 교차로 · 장소명)과
      우리 도로명 구간이 없는 행은 안 붙인다(억지로 세우지 않는다). 표준노드링크와 충돌하는 곳(`nl_twoway`)을 누가 이기는지는 정하지 않는다.
"""
from __future__ import annotations

import argparse
import collections
import csv
import math
import re
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import Point

from firelane import ledger as _led
from firelane.paths import DATA, PROCESSED, ROOT
from firelane.seg import geom as seg_geom
from firelane.seg import vehicle as V
from firelane.seg.params import STATIONS

V.use(_led.vehicle_spec())

RULES_TS = ROOT / "web" / "navi" / "src" / "domain" / "rules.ts"
END_TOL_M = 30.0                  # 끝점 ↔ 부분 그래프 노드 오차. 붙는 셋은 ≤ 23m, 나머지는 가장 가까운 것이 61m
RATIO = (0.75, 1.25)              # 경로 길이 ÷ 표의 길이. 붙는 셋은 0.93~1.06, 나머지는 가장 가까운 것이 1.38
HEADER = ("연번", "관할", "도로명", "구간", "길이", "시점부", "종점부")       # 병합 머리 3줄에 있어야 하는 글자


# ── 순수 함수 ───────────────────────────────────────────────────
def legal_dong(name: str) -> str:
    """행정동 → 법정동(`지산1동` → `지산동`). 법정동명은 그대로(`금남로5가` · `동명동`)."""
    return re.sub(r"(\D+)\d동$", r"\1동", name)


_EP = re.compile(r"^([가-힣]+(?:\d[가동])?)\s*(\d+(?:-\d+)?)\s*$")


def parse_endpoint(text: str):
    """끝점 글자 → ((법정동, 지번), 정리한 글자). 지번이 없으면 (None, 글자). 접두(광주광역시 · 동구 · ～ · →)와 괄호 속 장소명은 뗀다."""
    t = re.sub(r"^[～→]\s*", "", (text or "").strip())
    t = re.sub(r"^광주광역시\s+", "", t)
    t = re.sub(r"^동구\s+", "", t)
    t = re.sub(r"\s*\(.*$", "", t).strip()
    m = _EP.match(t)
    return ((legal_dong(m.group(1)), m.group(2)), t) if m else (None, t)


def read_city_rows(path: Path) -> list[dict]:
    """동구청 표(norm CSV). 병합 머리 3줄은 **위치로** 건너뛰고 머리글 글자를 검사한다 — 병합을 해석하는 일은 이 읽는 쪽의 몫이다(변환기는 값 그대로)."""
    rows = list(csv.reader(path.open(encoding="utf-8")))
    head = " ".join(c for r in rows[:3] for c in r)
    missing = [h for h in HEADER if h not in head.replace(" ", "")]
    if missing:
        raise ValueError(f"머리글이 바뀌었다 — {missing} 이 병합 머리 3줄에 없다")
    out = []
    for r in rows[3:]:
        if len(r) < 6 or not r[0].strip().isdigit():
            continue
        out.append({"n": int(r[0]), "road": r[2].strip(), "len": int(r[3]), "s": r[4].strip(), "e": r[5].strip()})
    return out


def read_police_rows(path: Path) -> list[dict]:
    """동부경찰서 hwpx 원문 → 행. 기호(`～` 범위 · `→` 방향)와 비고를 든다. 표 구조가 아니라 **문단 순서**로 읽는다(연번 다음 줄이 `광주광역시` 로 시작하는 곳이 행의 머리다)."""
    x = zipfile.ZipFile(path).read("Contents/section0.xml").decode("utf-8")
    lines = []
    for p in re.findall(r"<hp:p\b.*?</hp:p>", x, re.S):
        t = re.sub(r"<[^>]+>", "", "".join(re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", p, re.S))).strip()
        if t:
            lines.append(t)
    heads = [k for k, t in enumerate(lines) if re.fullmatch(r"\d{1,2}", t) and k + 1 < len(lines) and lines[k + 1].startswith("광주광역시")]
    out = []
    for a, b in zip(heads, [*heads[1:], len(lines)], strict=True):
        seg = lines[a:b]
        end = next((t for t in seg[2:] if t[0] in "～→"), "")
        dist = next((t for t in seg[2:] if re.fullmatch(r"[\d,]+", t)), "")
        rest = [t for t in seg[2:] if t not in (end, dist) and t not in ("연번", "구간(장소)", "거리(m)", "비고")]
        out.append({"n": int(seg[0]), "s": seg[1], "e": end, "op": end[:1], "len": int(dist.replace(",", "")) if dist else None, "rest": rest})
    return out


def edge_signs(path_nodes: list, ab: dict) -> list[int]:
    """경로(노드 열)를 따라가는 방향이 구간의 a→b 와 같으면 +1, 반대면 −1. `ab` = {(u, v): (a, b)} 무향 키 → 구간의 (a, b)."""
    out = []
    for u, v in zip(path_nodes, path_nodes[1:], strict=False):
        a, _b = ab[frozenset((u, v))]
        out.append(1 if a == u else -1)
    return out


def classify(ds, de, ratio, tol=END_TOL_M, rr=RATIO) -> str:
    """끝점 오차 둘과 길이비 → `붙음` · `부분`(한 끝만) · `어긋남`(길이비가 안 맞는다) · `밖`(두 끝 다 멀다)."""
    near = [d is not None and d <= tol for d in (ds, de)]
    if all(near):
        return "붙음" if ratio is not None and rr[0] <= ratio <= rr[1] else "어긋남"
    return "부분" if any(near) else "밖"


def rule_consts(text: str) -> dict:
    """`rules.ts` 의 `WRONG_WAY` · `ONEWAY_UNKNOWN` 을 읽는다 — 사본을 두지 않는다."""
    out = {}
    for k in ("WRONG_WAY", "ONEWAY_UNKNOWN"):
        m = re.search(rf"export\s+const\s+{k}\s*=\s*([\d.]+)\s*;", text)
        if not m:
            raise ValueError(f"rules.ts 에서 {k} 를 못 찾았다")
        out[k] = float(m.group(1))
    return out


def direction_factor(ow: int, forward: bool, wrong: float, unknown: float) -> float:
    """`rules.ts::directionFactor` 와 같다 — ow 1 은 a→b 허용 · −1 은 b→a 허용 · 2 는 모름(양쪽 다) · 0 은 양방향."""
    if ow == 1:
        return 1.0 if forward else wrong
    if ow == -1:
        return wrong if forward else 1.0
    return unknown if ow == 2 else 1.0


# ── 입력 ───────────────────────────────────────────────────────
def parcel_index() -> tuple[dict, set]:
    """(법정동, 지번) → 필지 중심, 그리고 **같은 키가 둘 이상인 키 집합**(어느 필지인지 모르므로 중심을 안 낸다)."""
    g = gpd.read_file(PROCESSED / "jijeok_5186.gpkg")
    g["dong"] = g.A3.str.split().str[-1]
    g["jibun"] = g.A4.str.strip()
    cnt = g.groupby(["dong", "jibun"]).size()
    dup = {k for k, n in cnt.items() if n > 1}
    idx = {}
    for r in g.itertuples():
        k = (r.dong, r.jibun)
        if k not in dup:
            c = r.geometry.centroid
            idx[k] = (c.x, c.y)
    return idx, dup


def load_network():
    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg")
    import json
    g = json.loads((ROOT / "web" / "data" / "navi_graph.json").read_text(encoding="utf-8"))
    ed = {e["seg_uid"]: e for e in g["edges"]}
    seg["a"] = seg.seg_uid.map(lambda u: ed[u]["a"])
    seg["b"] = seg.seg_uid.map(lambda u: ed[u]["b"])
    seg["ow"] = seg.seg_uid.map(lambda u: ed[u].get("ow", 0))
    xy = {}
    for r in seg.itertuples():
        co = list(r.geometry.coords) if r.geometry.geom_type == "LineString" else list(max(r.geometry.geoms, key=lambda q: q.length).coords)
        xy[r.a], xy[r.b] = co[0], co[-1]
    return seg, xy, g


def match_row(row, seg, xy, idx, dup=frozenset()) -> dict:
    """한 행을 우리 구간에 댄다. 결과에 사유가 든다."""
    out = {"n": row["n"], "road": row["road"], "len": row["len"], "s": row["s"], "e": row["e"]}
    (ks, _), (ke, _) = parse_endpoint(row["s"]), parse_endpoint(row["e"])
    if ks is None or ke is None:
        return {**out, "status": "끝점 지번 없음", "why": "교 · 교차로 · 장소명이라 지번이 없다"}
    ps, pe = idx.get(ks), idx.get(ke)
    if ps is None or pe is None:
        bad = [(k, p) for k, p in ((ks, ps), (ke, pe)) if p is None]
        why = ", ".join(f"{k[0]} {k[1]}({'같은 지번이 둘' if k in dup else '지적도에 없음'})" for k, _ in bad)
        return {**out, "status": "끝점 좌표 없음(중복)" if all(k in dup for k, _ in bad) else "끝점 좌표 없음", "why": why}
    road = seg[seg.road_name == row["road"]]
    if road.empty:
        return {**out, "status": "도로명 구간 없음", "why": "우리 그래프에 그 도로명의 구간이 없다(발행 범위 밖)"}
    G = nx.Graph()
    ab = {}
    for s in road.itertuples():
        G.add_edge(s.a, s.b, w=float(s.length_m), uid=s.seg_uid, ow=int(s.ow))
        ab[frozenset((s.a, s.b))] = (s.a, s.b)

    def near(p):
        n = min(G.nodes, key=lambda k: math.dist(xy[k], p))
        return n, math.dist(xy[n], p)

    ns, ds = near(ps)
    ne, de = near(pe)
    path = nx.shortest_path(G, ns, ne, weight="w") if ns != ne and nx.has_path(G, ns, ne) else None
    ln = sum(G.edges[u, v]["w"] for u, v in zip(path, path[1:], strict=False)) if path else None
    ratio = ln / row["len"] if ln else None
    st = classify(ds, de, ratio)
    out.update(status=st, ds=round(ds), de=round(de), path_len=round(ln) if ln else None, ratio=round(ratio, 2) if ratio else None)
    if st == "붙음":
        sg = edge_signs(path, ab)
        edges = [G.edges[u, v] for u, v in zip(path, path[1:], strict=False)]
        out["edges"] = [{"seg_uid": e["uid"], "ow": e["ow"], "sheet": s} for e, s in zip(edges, sg, strict=True)]
    return out


def orientation_checks(rows: list[dict], seg, xy, idx) -> list[dict]:
    """우리 `ow=±1`(표준노드링크가 정한 방향)과 표의 시점부 → 종점부가 같은 방향인가. 도로명이 아니라 **끝점이 구간의 노드에 붙고 표의 길이가 그 구간 길이와 맞는가**로 짝짓는다(표는 `제봉로` · 경찰은 `제봉로110번길`). 교차로로 들어오는 다른 구간의 끝점은 길이로 거른다."""
    out = []
    for e in seg[seg.ow != 0].itertuples():
        if e.ow == 2:
            continue
        a, b = xy[e.a], xy[e.b]
        for r in rows:
            if not RATIO[0] <= r["len"] / float(e.length_m) <= RATIO[1]:
                continue                    # 교차로로 들어오는 다른 구간의 끝점이다 — 이 구간을 덮는 행이 아니다
            for side, k in (("s", parse_endpoint(r["s"])[0]), ("e", parse_endpoint(r["e"])[0])):
                p = idx.get(k) if k else None
                if p is None:
                    continue
                da, db = math.dist(p, a), math.dist(p, b)
                if min(da, db) > END_TOL_M:
                    continue
                # 시점부가 a 에 붙으면 시점 → 종점은 a 에서 나간다(= a→b = +1). 종점부가 b 에 붙어도 +1.
                sheet = (1 if da < db else -1) if side == "s" else (1 if db < da else -1)
                out.append({"seg_uid": e.seg_uid, "ow": int(e.ow), "row": r["n"], "side": side, "sheet": sheet, "same": sheet == int(e.ow), "near_m": round(min(da, db))})
    return out


def sensitivity(seg, consts, variants) -> list[dict]:
    """역주행 배수를 바꾸며 센터 → 모든 노드의 최단경로가 얼마나 바뀌나. 비용은 `edge_cost` × 방향 계수(`rules.ts` 와 같은 식), 막힌 구간은 뺀다.

    variants = [(이름, {seg_uid: ow})] — 이름 붙은 `ow` 덮어쓰기. 첫째는 보통 `{}`(지금 발행). 각 변형을 **지금 발행 · 지금 배수**의 경로와 댄다.
    """
    spts = {nm: gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(5186).iloc[0] for nm, (lon, lat) in STATIONS.items()}
    base = []
    for r in seg.itertuples():
        w = None if pd.isna(r.width_min_m) else float(r.width_min_m)
        c = V.edge_cost(float(r.length_m), w, r.verdict, seg_geom.curvature(r.geometry))
        if c != math.inf:
            base.append((r, c))
    src = {}
    for nm, p in spts.items():
        cand = min(base, key=lambda x: x[0].geometry.distance(p))[0]
        co = list(cand.geometry.coords) if cand.geometry.geom_type == "LineString" else list(max(cand.geometry.geoms, key=lambda q: q.length).coords)
        src[nm] = cand.a if Point(co[0]).distance(p) <= Point(co[-1]).distance(p) else cand.b

    def run(wrong, unknown, ows):
        D = nx.DiGraph()
        for r, c in base:
            ow = int(ows.get(r.seg_uid, r.ow))
            for u, v, fwd in ((r.a, r.b, True), (r.b, r.a, False)):
                w = c * direction_factor(ow, fwd, wrong, unknown)
                if not D.has_edge(u, v) or w < D[u][v]["w"]:
                    D.add_edge(u, v, w=w, uid=r.seg_uid, wrongway=(ow == 1 and not fwd) or (ow == -1 and fwd))
        res = {}
        for nm, s in src.items():
            dist, paths = nx.single_source_dijkstra(D, s, weight="w")
            res[nm] = {t: (tuple(D[u][v]["uid"] for u, v in zip(p, p[1:], strict=False)), any(D[u][v]["wrongway"] for u, v in zip(p, p[1:], strict=False))) for t, p in paths.items()}
        return res

    ref = run(consts["WRONG_WAY"], consts["ONEWAY_UNKNOWN"], {})
    out = []
    for name, ows in variants:
        for wrong in (1.0, 2.0, consts["WRONG_WAY"], 8.0, 1e6):
            cur = run(wrong, consts["ONEWAY_UNKNOWN"], ows)
            n = sum(len(v) for v in cur.values())
            chg = sum(1 for nm in cur for t, x in cur[nm].items() if ref[nm].get(t, (None,))[0] != x[0])
            ww = sum(1 for nm in cur for x in cur[nm].values() if x[1])
            out.append({"variant": name, "wrong": wrong, "nodes": n, "changed": chg, "uses_wrong_way": ww})
    return out


# ── 실행 ───────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--sensitivity", action="store_true")
    a = ap.parse_args(argv)

    city = read_city_rows(DATA / "norm" / "gjcity" / "gjcity_oneway_donggu_jngj-donggu_20261008.csv")
    police = read_police_rows(DATA / "raw" / "gjpolice" / "gjpolice_oneway_donggu_jngj-donggu_20261012.hwpx")
    seg, xy, g = load_network()
    idx, dups = parcel_index()
    consts = rule_consts(RULES_TS.read_text(encoding="utf-8"))
    ow = collections.Counter(int(x) for x in seg.ow)
    print(f"읽음  동구청 {len(city)}행 · 경찰 {len(police)}행(기호 {dict(collections.Counter(p['op'] or '없음' for p in police))}) · 지적도 {len(idx):,}키(같은 키 {len(dups)} 제외)")
    print(f"지금 발행: 일방통행 {ow[2] + ow[1] + ow[-1]}구간 — 방향 확정 {ow[1] + ow[-1]} · 방향 모름(ow=2) {ow[2]} · 양방향 {ow[0]}")

    res = [match_row(r, seg, xy, idx, dups) for r in city]
    matched = [r for r in res if r["status"] == "붙음"]
    to_pm = {e["seg_uid"]: e["sheet"] for r in matched for e in r["edges"] if e["ow"] == 2}
    plus_conflict = {**to_pm, **{e["seg_uid"]: e["sheet"] for r in matched for e in r["edges"] if e["ow"] == 0}}

    if a.sensitivity:
        print(f"\n역주행 배수 민감도 — rules.ts 의 WRONG_WAY {consts['WRONG_WAY']:g} · ONEWAY_UNKNOWN {consts['ONEWAY_UNKNOWN']:g} · 센터 {len(STATIONS)}곳 → 모든 노드. "
              "「다른 노드」는 **지금 발행 · 지금 배수**의 경로와 다른 것")
        for r in sensitivity(seg, consts, [("지금 발행(방향 확정 1)", {}), (f"+ 표 방향 2→±1 {len(to_pm)}구간", to_pm), (f"+ 충돌 포함 {len(plus_conflict)}구간", plus_conflict)]):
            print(f"  {r['variant']:28} WRONG_WAY {r['wrong']:>8g}  다른 노드 {r['changed']:3d} / {r['nodes']} · 역주행 간선을 쓰는 경로 {r['uses_wrong_way']}")
        return 0

    cnt = collections.Counter(r["status"] for r in res)
    print(f"\n③ 매칭 (동구청 표 {len(res)}행) — " + " · ".join(f"{k} {v}" for k, v in cnt.most_common()))
    for st in ("붙음", "부분", "어긋남", "밖", "도로명 구간 없음", "끝점 좌표 없음", "끝점 좌표 없음(중복)", "끝점 지번 없음"):
        rows = [r for r in res if r["status"] == st]
        if rows:
            print(f"  ── {st} {len(rows)}")
            for r in rows:
                extra = f" · 끝점 오차 {r.get('ds')}/{r.get('de')}m · 경로 {r.get('path_len')}m(비 {r.get('ratio')})" if "ds" in r else (f" · {r['why']}" if "why" in r else "")
                print(f"     #{r['n']:2d} {r['road']:10} {r['len']:4d}m  {r['s']} → {r['e']}{extra}")

    print("\n④ 방향 · 발행 변화(계산만 — navi_graph.json 을 안 쓴다)")
    chg = collections.Counter()
    for r in (x for x in res if x["status"] == "붙음"):
        for e in r["edges"]:
            kind = "2 → ±1(방향이 정해진다)" if e["ow"] == 2 else ("0 과 충돌(표는 일방 · 우리는 양방)" if e["ow"] == 0 else "이미 확정")
            chg[kind] += 1
        print(f"  #{r['n']} {r['road']}: " + " ".join(f"{e['seg_uid'][-4:]}[{e['ow']}→{e['sheet']:+d}]" for e in r["edges"]))
    print("  구간 수: " + " · ".join(f"{k} {v}" for k, v in chg.items()))
    # 방향 근거 — 시점부 → 종점부가 통행 방향이라는 것은 문서에 없다. 셋을 대 본다
    arrows = [p for p in police if p["op"] == "→"]
    pairs = []
    for p in police:
        kp = (parse_endpoint(p["s"])[0], parse_endpoint(p["e"])[0])
        for r in city:
            kr = (parse_endpoint(r["s"])[0], parse_endpoint(r["e"])[0])
            if None not in (*kp, *kr) and kp[0] != kp[1] and {*kp} == {*kr}:
                pairs.append((p["n"], r["n"], p["op"], kp == kr))
    print(f"  방향 근거 ① 경찰 문서가 방향을 **화살표(→)** 로 적는 행은 {len(arrows)}개 / {len(police)}행 — 나머지 {len(police) - len(arrows)}행은 범위(～) 또는 기호 없음이라 방향이 **안 적혀 있다**")
    print(f"           ② 두 목록에서 끝점쌍이 같은 행 {len(pairs)}개 중 시점/종점 순서가 같은 것 {sum(x[3] for x in pairs)}개 (화살표 행은 지번이 이름으로 적혀 이 짝짓기에 안 든다 — 본문에서 손으로 대었다)")
    oc = orientation_checks(city, seg, xy, idx)
    print(f"           ③ 우리 ow=±1(표준노드링크가 정한 방향) 구간과 표의 시점→종점: 짝 {len(oc)}개 중 같은 방향 {sum(x['same'] for x in oc)}개 · " + " · ".join(f"#{x['row']}{x['side']} 노드와 {x['near_m']}m" for x in oc))

    if a.csv:
        out = Path(a.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{k: v for k, v in r.items() if k != "edges"} for r in res]).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

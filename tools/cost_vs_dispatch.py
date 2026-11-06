#!/usr/bin/env python3
"""
tools/cost_vs_dispatch.py — 우리 cost 로 계산한 소요와 119 출동의 **실제 소요**를 구간 단위로 대조한다.  (DECISIONS §650)

    uv run python tools/cost_vs_dispatch.py
    uv run python tools/cost_vs_dispatch.py --csv data/interim/cost_vs_dispatch.csv

── 왜 생겼나 ──────────────────────────────────────────────────
지금까지 cost 의 검증은 전부 **거리-시간 집계** 관계였다(§635 rho +0.486 · §645 구급 57.4 초/km · §644 화재 55 초/km). 구간에 붙은 적이 없다.
`nfa_dispatch_119` 는 다르다 — 재해 좌표(`LOT`/`LAT` · 소수 10자리)가 있어 **구간 단위로 붙고**, `DSPT_DRTV_DT → GRNDS_ARVL_DT` 가 그 지점까지의 실제 소요다.

── 무엇을 어떻게 ──────────────────────────────────────────────
 ① 접는다  행 → 좌표 유효 행 → **사건**(`CNTR_NM` · 지령 · 도착 · 위치가 같은 행) → **위치**(센터 · 좌표). 신고접수 단위라 한 사건에 여러 행이 온다 —
    접지 않으면 「신고가 많이 들어온 사건」에 가중치가 붙는다. 같은 위치의 **다른 날 출동은 다른 관측**이라 사건으로는 접지 않고, 위치 안에서 중앙값을 낸다.
 ② 스냅    각 위치를 가장 가까운 구간에 붙인다. 상수는 `seg/params.py` 의 `SNAP_MAX` · `SNAP_TRUST` 를 그대로 쓴다(≤ TRUST 신뢰 · ≤ MAX 스냅 · 밖은 실패).
    ★ 이 두 상수는 폭 측정점을 **노면**으로 끌어오는 한계다 — 여기서는 점을 **구간 중심선**에 붙이는 문턱으로 같은 값을 빌린다. 뜻이 다르다(결과 절이 그 영향을 든다).
 ③ 계산    `segments._write_route` 와 **같은 그래프**(끝점 `snap_groups` · `vehicle.edge_cost` 기본값 · 막힌 구간 제거 · 센터는 `station_node`)에서 센터 → 지점 Dijkstra.
    시간은 `web/navi/src/domain/speed.ts` 의 `travelSeconds` 와 **같은 식** — Σ 길이/속도(폭) × (경로 cost ÷ 경로 길이). **속도표(`SPEED_TABLE`)는 그 파일에서 읽는다 — 사본을 안 둔다.**
    ★ `edge_cost` 에는 속도도 **고정분도 없다**(미터 × 배수). 새 상수를 만들지 않는다.
 ④ 대조    실제 소요 − 계산 소요의 치우침 · 순위상관 · 선형 적합(고정분 = 절편 · 기울기) · 연도 · 센터별 · 스냅 신뢰별.

★ 판정을 안 바꾼다. `segments.geojson` · 판정 폐포 파일을 안 고친다 — 읽기만 한다(`tools/route_probe.py` 와 같은 구조 · #187 의 F 판).

IN    data/processed/nfa_dispatch_119.csv · segments_5186.gpkg · building_5186.gpkg · fire_station.geojson · web/navi/src/domain/speed.ts · seg/params.py
OUT   stdout · --csv
PARAM --csv · --boot
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
밖    **차종과 실제 접근로를 못 가른다** — 119 신고접수에 차종 · 신고 유형 칸이 없고 점은 건물 위치다. **속도와 고정분을 가르지 못한다** — 지점이 센터에서 1.0~1.4km 에 몰려 거리에 레버리지가 없다.
      판정 · 폭 · `cost` · 앱의 `travelSeconds` 를 안 고친다(수만 낸다). 지령 → 도착이 주행 시간이 아니라는 것(지령 → 출발 · 현장 접근이 든다)은 이 도구가 안 나눈다.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import Point

from firelane import ledger as _led
from firelane.paths import PROCESSED, ROOT
from firelane.publish_context import _resp, _ts
from firelane.seg import geom as seg_geom
from firelane.seg import graph as seg_graph
from firelane.seg import vehicle as V
from firelane.seg.params import NODE_TOL, SNAP_MAX, SNAP_TRUST, STATIONS

V.use(_led.vehicle_spec())

SPEED_TS = ROOT / "web" / "navi" / "src" / "domain" / "speed.ts"
CRS_M = 5186


# ── 순수 함수 ───────────────────────────────────────────────────
def parse_speed_table(text: str) -> list[tuple[float, float]]:
    """`speed.ts` 의 `SPEED_TABLE` 을 읽는다 — 사본을 두지 않는다. 폭 문턱 큰 것부터 [(문턱 m, km/h)]."""
    m = re.search(r"SPEED_TABLE\s*:\s*\[number,\s*number\]\[\]\s*=\s*\[(.*?)\];", text, re.S)
    if not m:
        raise ValueError("speed.ts 에서 SPEED_TABLE 을 못 찾았다")
    rows = [(float(a), float(b)) for a, b in re.findall(r"\[\s*([\d.]+)\s*,\s*([\d.]+)\s*\]", m.group(1))]
    if not rows or rows != sorted(rows, reverse=True):
        raise ValueError(f"SPEED_TABLE 이 큰 문턱부터가 아니다: {rows}")
    return rows


def parse_fixed_s(text: str) -> float:
    """`speed.ts` 의 `DISPATCH_FIXED_S`(지령 → 현장도착 고정분 · 초)를 읽는다 — 사본을 두지 않는다."""
    m = re.search(r"export\s+const\s+DISPATCH_FIXED_S\s*=\s*([\d.]+)\s*;", text)
    if not m:
        raise ValueError("speed.ts 에서 DISPATCH_FIXED_S 를 못 찾았다")
    return float(m.group(1))


def speed_mps(width_m: float | None, road_bt_m: float | None, table: list[tuple[float, float]]) -> float:
    """`speed.ts::speedOf` 와 같다 — `width_min_m ?? road_bt_m ?? 0` 으로 표를 본다. 없으면 맨 아래 칸."""
    w = next((float(x) for x in (width_m, road_bt_m) if x is not None and not (isinstance(x, float) and math.isnan(x))), 0.0)
    for min_w, kmh in table:
        if w >= min_w:
            return kmh / 3.6
    return table[-1][1] / 3.6


def response_seconds(dispatch, arrive) -> int | None:
    """지령 → 도착 초. `publish_context._resp` 와 같은 규칙(0 < s ≤ MAX_RESP_S · 빈 값 · 공백은 None)."""
    return _resp(_ts(dispatch), _ts(arrive))


def fold(rows: pd.DataFrame) -> dict:
    """행 → 사건 → 위치로 접는다. 각 단계의 수와 위치 표를 낸다.

    rows  칸 `cntr` · `lon` · `lat`(float · NaN 은 좌표 없음) · `dspt` · `arrv`(원문) · `resp`(초 또는 None)
    사건  (센터 · 지령 · 도착 · 좌표)가 같은 행 — 한 번의 출동에 여러 신고접수가 온 것
    위치  (센터 · 좌표) — 같은 곳의 **다른 날 출동은 다른 관측**이라 사건으로 안 접고, 위치 안에서 중앙값을 낸다
    """
    ok = rows[rows["lon"].notna() & rows["lat"].notna() & (rows["lon"] > 0) & (rows["lat"] > 0)].copy()
    ok["ev"] = list(zip(ok["cntr"], ok["dspt"].str.strip(), ok["arrv"].str.strip(), ok["lon"], ok["lat"], strict=True))
    events = ok.drop_duplicates("ev")
    key = ["cntr", "lon", "lat"]
    loc = (events.groupby(key)
           .agg(n_events=("ev", "size"), n_resp=("resp", lambda x: int(x.notna().sum())),
                resp_s=("resp", lambda x: float(x.dropna().median()) if x.notna().any() else math.nan))
           .reset_index()
           .merge(ok.groupby(key).size().rename("n_rows").reset_index(), on=key))
    return {"rows": len(rows), "coord_rows": len(ok), "events": len(events), "locations": len(loc),
            "places": ok[["lon", "lat"]].drop_duplicates().shape[0], "table": loc, "event_table": events}


def classify_snap(dist_m: float, trust: float = SNAP_TRUST, mx: float = SNAP_MAX) -> str:
    """`trust`(≤ TRUST) · `snap`(≤ MAX) · `fail`(밖). 경계는 닫힌 구간이다(`width.py` 와 같다)."""
    return "trust" if dist_m <= trust else "snap" if dist_m <= mx else "fail"


def spearman(x, y) -> float:
    """순위상관. 동순위는 평균 순위."""
    a, b = pd.Series(x).rank(), pd.Series(y).rank()
    return float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 else math.nan


def ols(x, y) -> tuple[float, float]:
    """y = a + b·x 의 (a, b). 절편 a 가 「고정분」이다."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    b, a = np.polyfit(x, y, 1)
    return float(a), float(b)


def summarize(pred, actual, boot: int = 1000, seed: int = 0) -> dict:
    """계산 소요(pred) 대 실제 소요(actual). 치우침 · 순위상관 · 적합 · 부트스트랩 95% 구간(위치를 다시 뽑는다)."""
    p, a = np.asarray(pred, float), np.asarray(actual, float)
    n = len(p)
    if n < 3:
        return {"n": n}
    rng = np.random.default_rng(seed)
    idx = [rng.integers(0, n, n) for _ in range(boot)]
    rho_b = [spearman(p[i], a[i]) for i in idx]
    bias_b = [float(np.median(a[i] - p[i])) for i in idx]
    fa, fb = ols(p, a)
    return {"n": n, "pred_med": float(np.median(p)), "actual_med": float(np.median(a)),
            "bias_med": float(np.median(a - p)), "bias_ci": (float(np.percentile(bias_b, 2.5)), float(np.percentile(bias_b, 97.5))),
            "ratio_med": float(np.median(a / p)), "rho": spearman(p, a), "rho_ci": (float(np.nanpercentile(rho_b, 2.5)), float(np.nanpercentile(rho_b, 97.5))),
            "fit_fixed_s": fa, "fit_slope": fb, "actual_gt_pred": float((a > p).mean())}


# ── 그래프 · 경로 ───────────────────────────────────────────────
def build_graph(seg: gpd.GeoDataFrame, table):
    """`segments._write_route` 와 같은 그래프. 엣지에 길이 · cost · 초(길이/속도)를 단다. (H 전체, 막힌 것을 뺀 P, 구간별 메타, ends, rep)."""
    ends = []
    for r in seg.itertuples():
        g = r.geometry
        co = list(g.coords) if g.geom_type == "LineString" else list(max(g.geoms, key=lambda q: q.length).coords)
        ends.append((r, co[0], co[-1]))
    rep = seg_geom.snap_groups([Point(q) for _, a, b in ends for q in (a, b)], NODE_TOL)
    H, meta = nx.Graph(), {}
    for k, (r, _a, _b) in enumerate(ends):
        a, b = rep[2 * k], rep[2 * k + 1]
        if a == b:
            continue
        w = None if pd.isna(r.width_min_m) else float(r.width_min_m)
        c = V.edge_cost(float(r.length_m), w, r.verdict, seg_geom.curvature(r.geometry))
        bt = None if pd.isna(r.road_bt_m) else float(r.road_bt_m)
        spd = speed_mps(w, bt, table)
        d = {"cost": 1e7 if c == math.inf else c, "blocked": c == math.inf, "seg_id": r.seg_id, "length": float(r.length_m),
             "sec": float(r.length_m) / spd, "a": a, "b": b, "k": k}
        prev = H.get_edge_data(a, b)
        if prev is None or d["cost"] < prev["cost"]:
            H.add_edge(a, b, **d)
        meta[r.seg_id] = d
    P = H.copy()
    P.remove_edges_from([(u, v) for u, v, d in H.edges(data=True) if d["blocked"]])
    return H, P, meta, ends, rep


def predict(P, src, meta, seg_id, frac, paths, dist):
    """센터 노드 → 구간 위의 한 점(끝 a 에서 `frac`)의 (계산 소요 초, 경로 길이 m, cost). 못 가면 None.

    `speed.ts::travelSeconds` 와 같은 식이다 — Σ 길이/속도 × (경로 cost ÷ 경로 길이). 구간 안쪽은 비율로 나눈다.
    """
    m = meta.get(seg_id)
    if m is None or m["blocked"]:
        return None
    best = None
    for end, part in ((m["a"], frac), (m["b"], 1 - frac)):
        if end not in dist:
            continue
        pp = paths[end]
        sec = sum(P.edges[u, v]["sec"] for u, v in zip(pp, pp[1:], strict=False)) + part * m["sec"]
        ln = sum(P.edges[u, v]["length"] for u, v in zip(pp, pp[1:], strict=False)) + part * m["length"]
        cost = dist[end] + part * m["cost"]
        if best is None or cost < best[2]:
            best = (sec * (cost / ln if ln > 0 else 1.0), ln, cost)
    return best


def predict_to_end(P, meta, seg_id, paths, dist):
    """막힌 구간 위의 점 — 그 구간 안은 못 들어가므로 **닿는 끝까지**의 (소요 초, 길이 m, cost)다. 도착 지점이 골목 입구일 수 있어 하한이다.

    `predict` 와 같은 식이다(Σ 길이/속도 × cost/길이). 구간 안쪽 부분은 더하지 않는다. 두 끝 다 안 닿으면 None.
    """
    m = meta.get(seg_id)
    if m is None:
        return None
    best = None
    for end in (m["a"], m["b"]):
        if end not in dist or dist[end] <= 0:
            continue
        pp = paths[end]
        sec = sum(P.edges[u, v]["sec"] for u, v in zip(pp, pp[1:], strict=False))
        ln = sum(P.edges[u, v]["length"] for u, v in zip(pp, pp[1:], strict=False))
        if best is None or dist[end] < best[2]:
            best = (sec * (dist[end] / ln if ln > 0 else 1.0), ln, dist[end])
    return best


# ── 실행 ───────────────────────────────────────────────────────
def load_rows() -> pd.DataFrame:
    d = pd.read_csv(PROCESSED / "nfa_dispatch_119.csv", dtype=str, na_filter=False, encoding="utf-8-sig")
    lx, ly = _led.coords("nfa_dispatch_119", "site", use="위치 분석")           # 칸 이름은 대장이 말한다(§634) — 재해 위치
    return pd.DataFrame({"cntr": d["CNTR_NM"], "yr": d["DCLR_YR"], "lon": pd.to_numeric(d[lx], errors="coerce"), "lat": pd.to_numeric(d[ly], errors="coerce"), "dspt": d["DSPT_DRTV_DT"], "arrv": d["GRNDS_ARVL_DT"],
                         "resp": [response_seconds(a, b) for a, b in zip(d["DSPT_DRTV_DT"], d["GRNDS_ARVL_DT"], strict=True)]})


def fmt(s: dict) -> str:
    if s["n"] < 3:
        return f"n={s['n']} (적다)"
    return (f"n={s['n']:4d} · 실제 중앙 {s['actual_med']:.0f}s 대 계산 중앙 {s['pred_med']:.0f}s · 치우침(실제−계산) 중앙 {s['bias_med']:+.0f}s "
            f"[{s['bias_ci'][0]:+.0f},{s['bias_ci'][1]:+.0f}] · 비 {s['ratio_med']:.2f} · rho {s['rho']:+.3f} [{s['rho_ci'][0]:+.2f},{s['rho_ci'][1]:+.2f}] · "
            f"적합 실제 = {s['fit_fixed_s']:.0f}s + {s['fit_slope']:.2f}×계산 · 실제>계산 {s['actual_gt_pred'] * 100:.0f}%")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", help="위치별 표를 쓴다(보통 data/interim/)")
    ap.add_argument("--boot", type=int, default=1000, help="부트스트랩 표본 수(구간 추정용 · 모형 상수가 아니다)")
    a = ap.parse_args(argv)

    table = parse_speed_table(SPEED_TS.read_text(encoding="utf-8"))
    fixed = parse_fixed_s(SPEED_TS.read_text(encoding="utf-8"))
    print(f"속도표(speed.ts · 폭 문턱 m → km/h): {[(int(w), int(v)) for w, v in table]} · edge_cost 에는 고정분 없음 · 앱의 지령→도착 고정분 DISPATCH_FIXED_S {fixed:.0f}s(speed.ts) · SNAP_TRUST {SNAP_TRUST} · SNAP_MAX {SNAP_MAX} · NODE_TOL {NODE_TOL}")

    # 센터 좌표 — 대장의 안전센터 위치와 맞는가
    fs = gpd.read_file(PROCESSED / "fire_station.geojson").to_crs(CRS_M)
    for nm, (lon, lat) in STATIONS.items():
        core = nm.replace("119안전센터", "")
        hit = fs[fs["소방서 및 안전센터명"].astype(str).str.contains(f"-{core}-")]
        p = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(CRS_M).iloc[0]
        print(f"  STATIONS {nm}: fire_station.geojson 과 {', '.join(f'{p.distance(g):.1f} m' for g in hit.geometry) or '없음'}")

    rows = load_rows()
    f = fold(rows)
    print(f"\n① 접기  행 {f['rows']} → 좌표 유효 {f['coord_rows']} → 사건 {f['events']} → 위치(센터·좌표) {f['locations']} (센터 무시 {f['places']}곳)")
    loc = f["table"].copy()
    loc["n_rows"] = loc["n_rows"].astype(int)
    print(f"   위치당 사건 수: 1회 {int((loc.n_events == 1).sum())} · 2회 이상 {int((loc.n_events > 1).sum())} (최대 {int(loc.n_events.max())}) · 응답시간 있는 위치 {int(loc.resp_s.notna().sum())}")

    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg").reset_index(drop=True)
    pts = gpd.GeoSeries([Point(x, y) for x, y in zip(loc.lon, loc.lat, strict=True)], crs=4326).to_crs(CRS_M)
    nn = seg.sindex.nearest(pts.values, return_all=False, return_distance=True)
    loc["seg_i"], loc["snap_d"] = nn[0][1], nn[1]
    loc["snap"] = [classify_snap(d) for d in loc.snap_d]
    cnt = loc["snap"].value_counts().to_dict()
    q = loc.snap_d.quantile([0.5, 0.9]).round(1).to_dict()
    print(f"\n② 스냅  신뢰(≤{SNAP_TRUST}m) {cnt.get('trust', 0)} · 스냅(≤{SNAP_MAX}m) {cnt.get('snap', 0)} · 실패 {cnt.get('fail', 0)} / {len(loc)}"
          f" — 거리 중앙 {q[0.5]}m · 90분위 {q[0.9]}m · 최대 {loc.snap_d.max():.1f}m")
    bld = gpd.read_file(PROCESSED / "building_5186.gpkg")
    in_b = np.zeros(len(pts), bool)
    ii = bld.sindex.query(pts.values, predicate="within")
    in_b[ii[0]] = True
    loc["in_building"] = in_b
    fail = loc[loc.snap == "fail"]
    print(f"   실패 {len(fail)} 중 건물 안 {int(fail.in_building.sum())} · 건물 밖 {int((~fail.in_building).sum())} · 최근접 구간이 막힘 "
          f"{int((seg.loc[fail.seg_i, 'verdict'].values == 'blocked').sum())} · 성공 중 건물 안 {int(loc[loc.snap != 'fail'].in_building.sum())}/{int((loc.snap != 'fail').sum())}")
    loc["seg_id"] = seg.loc[loc.seg_i, "seg_id"].values
    loc["verdict"] = seg.loc[loc.seg_i, "verdict"].values
    geo = {r.seg_id: r.geometry for r in seg.itertuples()}
    loc["frac"] = [min(1.0, max(0.0, (g.project(pt) / g.length) if g.geom_type == "LineString" else
                              (lambda gg: gg.project(pt) / gg.length)(max(g.geoms, key=lambda q: q.length))))
                   for g, pt in zip((geo[s] for s in loc.seg_id), pts, strict=True)]

    H, P, meta, ends, rep = build_graph(seg, table)
    res = {}
    for nm, (lon, lat) in STATIONS.items():
        pt = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(CRS_M).iloc[0]
        s = seg_graph.station_node(pt, ends, meta, rep)
        res[nm] = (s, *nx.single_source_dijkstra(P, s, weight="cost")) if s is not None else None
    pred = []
    for r in loc.itertuples():
        x = res.get(r.cntr)
        if x is None:
            pred.append((math.nan, math.nan, math.nan))
            continue
        s, dist, paths = x
        pr = predict(P, s, meta, r.seg_id, r.frac, paths, dist)
        pred.append(pr if pr else (math.nan, math.nan, math.nan))
    loc["pred_s"], loc["route_m"], loc["pred_cost"] = zip(*pred, strict=True)
    loc["cost_blocked"] = [bool(meta.get(i, {}).get("blocked", False)) for i in loc.seg_id]
    mouth = []
    for r in loc.itertuples():
        x = res.get(r.cntr)
        pr = predict_to_end(P, meta, r.seg_id, x[2], x[1]) if x is not None and r.cost_blocked else None
        mouth.append(pr[0] if pr else math.nan)
    loc["pred_mouth_s"] = mouth    # 판정 어휘가 아니라 edge_cost 가 막은 것(필요폭 미만 · 회전 불가 포함)
    ok = loc[loc.snap != "fail"]
    print(f"\n③ 계산  스냅된 {len(ok)} 중 막힌 구간 위(edge_cost) {int(ok.cost_blocked.sum())} · 경로 없음(도달 불가) {int((ok.pred_s.isna() & ~ok.cost_blocked).sum())} · 계산됨 {int(ok.pred_s.notna().sum())}")

    use = ok[ok.pred_s.notna() & ok.resp_s.notna()]
    print(f"   응답시간까지 있는 위치 {len(use)} (센터 {use.cntr.value_counts().to_dict()})")
    print("\n④ 대조  (치우침 = 실제 − 계산 · [ ]는 위치를 다시 뽑은 부트스트랩 95%)")
    for label, sub in (("스냅된 전체", use), (f"신뢰만(≤{SNAP_TRUST}m)", use[use.snap == "trust"]), ("지산만", use[use.cntr == "지산119안전센터"])):
        print(f"  {label:14} {fmt(summarize(sub.pred_s, sub.resp_s, a.boot))}")
    for v in sorted(use.verdict.unique()):
        sub = use[use.verdict == v]
        print(f"  판정 {v:10} {fmt(summarize(sub.pred_s, sub.resp_s, a.boot))}")
    # 앱의 지령 → 현장도착 추정(고정분 + 주행)과의 치우침 — 0 에 가까워야 한다
    bm0 = ok[ok.cost_blocked & ok.pred_mouth_s.notna() & ok.resp_s.notna()]
    comb = pd.concat([use.assign(p=use.pred_s), bm0.assign(p=bm0.pred_mouth_s)])
    wide0 = loc[loc.pred_s.notna() & loc.resp_s.notna()]
    print(f"\n   ── 앱의 지령→도착 추정(주행 + 고정분 {fixed:.0f}s)과의 치우침 ──")
    for label, p_, r_ in (("스냅된 전체", use.pred_s, use.resp_s), ("합친 표본(막힌 구간 위는 입구까지)", comb.p, comb.resp_s), ("스냅 한계 없이", wide0.pred_s, wide0.resp_s)):
        sm = summarize(np.asarray(p_) + fixed, r_, a.boot)
        print(f"   {label:30} n={sm['n']:4d} · 치우침(실제−추정) 중앙 {sm['bias_med']:+.0f}s [{sm['bias_ci'][0]:+.0f},{sm['bias_ci'][1]:+.0f}] · 비 {sm['ratio_med']:.2f} · 실제>추정 {sm['actual_gt_pred'] * 100:.0f}%")
    # 해석에 필요한 점검 — 표본이 치우쳤는가 · 이 범위에서 거리가 시간을 설명할 수 있는가 · 스냅 한계가 결론을 만드는가
    print("\n   ── 점검 ──")
    snapped, failed = loc[loc.snap != "fail"], loc[loc.snap == "fail"]
    print(f"   표본 선택  실제 중앙 — 스냅됨 {snapped.resp_s.median():.0f}s(n={int(snapped.resp_s.notna().sum())}) · 실패 {failed.resp_s.median():.0f}s(n={int(failed.resp_s.notna().sum())})")
    spts = {nm: gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(CRS_M).iloc[0] for nm, (lon, lat) in STATIONS.items()}
    loc["straight_m"] = [pt.distance(spts[c]) for pt, c in zip(pts, loc.cntr, strict=True)]
    allr = loc[loc.resp_s.notna()]
    sfa, sfb = ols(allr.straight_m / 1000, allr.resp_s)
    print(f"   직선거리(센터→위치) 전체 {len(allr)}곳: 사분위 {allr.straight_m.quantile(.25):.0f}/{allr.straight_m.quantile(.5):.0f}/{allr.straight_m.quantile(.75):.0f} m · "
          f"rho {spearman(allr.straight_m, allr.resp_s):+.3f} · 적합 실제 = {sfa:.0f}s + {sfb:.1f}s/km")
    print(f"   경로 길이(스냅된 {len(use)}곳): 사분위 {use.route_m.quantile(.25):.0f}/{use.route_m.quantile(.5):.0f}/{use.route_m.quantile(.75):.0f} m · 계산 소요 사분위 "
          f"{use.pred_s.quantile(.25):.0f}/{use.pred_s.quantile(.5):.0f}/{use.pred_s.quantile(.75):.0f} s · 실제 사분위 {use.resp_s.quantile(.25):.0f}/{use.resp_s.quantile(.5):.0f}/{use.resp_s.quantile(.75):.0f} s")
    print(f"   치우침이 거리에 비례하는가(속도 탓이면 그렇다)  rho(실제−계산, 경로 길이) {spearman(use.resp_s - use.pred_s, use.route_m):+.3f}")
    wide = loc[loc.pred_s.notna() & loc.resp_s.notna()]
    print(f"   스냅 한계 없이(최근접 구간 · 거리 무시) {fmt(summarize(wide.pred_s, wide.resp_s, a.boot))}")
    nb = P.number_of_nodes()
    reach = sum(1 for _, d in meta.items() if not d["blocked"] and any(r_ is not None and d["a"] in r_[1] and d["b"] in r_[1] for r_ in res.values()))
    print(f"   도달성(구간 전체)  막히지 않은 {sum(1 for d in meta.values() if not d['blocked'])}구간 중 센터에서 닿는 {reach} (노드 {nb})")
    # 우리 판정으로는 못 가는 곳에 실제로 갔는가 — 막힌 구간 위 · 막힌 구간을 지나야만 닿는 곳
    grp = np.where(ok.cost_blocked, "막힌 구간 위", np.where(ok.pred_s.isna(), "막힌 구간 너머(도달 불가)", "도달 가능"))
    g = ok.assign(grp=grp).groupby("grp").agg(n=("snap", "size"), n_resp=("resp_s", lambda x: int(x.notna().sum())), actual_med=("resp_s", "median"))
    print("   ── 우리 판정으로 닿는가 ──  (스냅된 지점 기준 · 실제 소요는 도착한 사실이다)")
    for k, r in g.iterrows():
        print(f"   {k:16} 지점 {int(r.n):3d} (응답 {int(r.n_resp):3d}) · 실제 중앙 {r.actual_med:.0f}s")
    bm = ok[ok.cost_blocked & ok.pred_mouth_s.notna() & ok.resp_s.notna()]
    print(f"   막힌 구간 위 — 닿는 끝까지의 시간(하한) {fmt(summarize(bm.pred_mouth_s, bm.resp_s, a.boot))}")
    allp = pd.concat([use.assign(p=use.pred_s), bm.assign(p=bm.pred_mouth_s)])
    print(f"   위 둘을 합친 표본                  {fmt(summarize(allp.p, allp.resp_s, a.boot))}")
    nv = ok[ok.cost_blocked]
    print(f"   막힌 구간 위 {len(nv)}곳의 구간 판정: " + " · ".join(f"{k} {v}" for k, v in nv.verdict.value_counts().items())
          + f" — 폭 추정 중앙 {seg.set_index('seg_id').loc[nv.seg_id.unique(), 'width_min_m'].median():.2f}m(필요폭 미만이라 edge_cost 가 막는다)")
    # 거리만 — §644 · §645 와 같은 꼴(초/km · 고정분)
    fa, fb = ols(use.route_m / 1000, use.resp_s)
    print(f"\n   거리 적합(경로 m → 실제 s): 실제 = {fa:.0f}s + {fb:.1f}s/km · rho(경로 길이, 실제) {spearman(use.route_m, use.resp_s):+.3f} · rho(계산 cost, 실제) {spearman(use.pred_cost, use.resp_s):+.3f}")
    print("   (참고 §645 구급 2024~25 57.4 초/km · 고정분 294초 · §644 화재 55 초/km · 210초 · §635 rho +0.486 — 전부 집계 관계)")
    # 해 · 접기 전후
    ev = f["event_table"]
    ev = ev[ev["resp"].notna()]
    print(f"\n   접기 민감도  행 단위 응답 {int(rows.resp.notna().sum())}건 · 사건 단위 {len(ev)}건 · 위치 단위 {int(loc.resp_s.notna().sum())}곳 — 중앙 {rows.resp.median():.0f}s · {ev.resp.median():.0f}s · {loc.resp_s.median():.0f}s")
    yr = rows.assign(ok=rows.resp.notna()).groupby("yr").agg(n=("ok", "size"), resp_n=("ok", "sum"), resp_med=("resp", "median"))
    print("   연도별(행): " + " · ".join(f"{y} n={int(r.n)} 응답 {int(r.resp_n)} 중앙 {r.resp_med:.0f}s" for y, r in yr.iterrows()))

    if a.csv:
        out = Path(a.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        loc.drop(columns=["seg_i"]).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

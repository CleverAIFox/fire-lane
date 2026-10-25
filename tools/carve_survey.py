#!/usr/bin/env python3
"""
tools/carve_survey.py — 보도 차감(`carve`)이 1,281구간에서 **실제로 얼마나 작동했나**를 센다.  (Zm31 · DECISIONS §576)

    uv run python tools/carve_survey.py            표 + data/processed/carve_survey.json

── 왜 엔진을 두 번 돌리나 ────────────────────────────────────────
`w_rule == "carve"` 는 **보도면이 전역에 있으면 항상** 찍히는 꼬리표다(`seg/width.py`: `walk_u` 가 비어 있지 않으면 모든 표본이 그 분기를 탄다).
그 표시로는 「깎았다」를 셀 수 없다. 그래서 **같은 입력으로 `WidthEngine` 을 보도면 있이 · 없이 두 번** 돌려 표본마다 값을 댄다. 엔진 코드는 그대로 부른다 —
복제가 아니다. 입력만 가공 산출물에서 다시 짠다(`segments.main` 의 구성을 따르되, 판정 범위 `keep` 은 **발행본 구간 합집합 + 50m** 로 근사하고
교차 노드는 발행본 구간 끝점의 차수 ≥ 3 으로 근사한다).

★ **재현 관문.** 보도면 있는 쪽의 `wmin` 이 발행본 `width_min_m` 과 같아야(±0.015) 수를 낸다. 못 맞추면 아무 수도 안 내고 죽는다 — 입력 근사가 틀린 채 낸 수는 수가 아니다.

IN    data/processed/{segments,ngii1k,ngii_road,road_rw,building,ngii1k_walk,ngii1k_xsec}_5186.gpkg · 발행본
OUT   data/processed/carve_survey.json · 화면
PARAM 가까움 반경 5 · 10 · 20m (보도 폴리곤이 구간 중심선에서 이 안에 있는가 — 20m 는 `ESCAPE_M`)
밖    **판정을 안 바꾼다. carve 코드를 안 건드린다.** 수만 내고 판단은 사람이 한다.
      **「폭이 더 넓다」가 곧 과대측정은 아니다** — 보도가 없는 길이 원래 좁은 골목일 수 있다. 그래서 대장폭(`road_bt_m`)으로 층을 나눠 대고,
      과대측정의 **양**은 보도면이 실제로 깎인 구간의 감소량으로만 말한다(자료에 없는 보도는 재지 못한다).
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = PROCESSED / "carve_survey.json"
CRS = "EPSG:5186"
NEAR = (5.0, 10.0, 20.0)
REPRO_TOL = 0.015
REPRO_MIN = 0.95          # 이보다 못 맞추면 입력 근사가 틀린 것이다 — 수를 안 낸다
EPS = 1e-6


def build_engines():
    import geopandas as gpd
    import shapely
    from shapely.geometry import Point
    from shapely.ops import unary_union

    from firelane.seg.geom import _seal
    from firelane.seg.width import WidthEngine

    def load(k):
        return gpd.read_file(PROCESSED / f"{k}_5186.gpkg").to_crs(CRS)

    seg = load("segments")
    ng1, ng, rw, bld, wk = (load(k) for k in ("ngii1k", "ngii_road", "road_rw", "building", "ngii1k_walk"))
    xs = gpd.read_file(PROCESSED / "ngii1k_xsec_5186.gpkg", layer="ngii1k_xsec").to_crs(CRS)
    all_u = unary_union(list(seg.geometry))
    clip = all_u.buffer(50).buffer(20)
    ng1_u = _seal(ng1[ng1.intersects(clip)].geometry)
    ng_u = _seal(ng[ng.intersects(clip)].geometry)
    rw_u = _seal(rw[rw.intersects(clip)].geometry)
    bld_u = unary_union([shapely.make_valid(g) for g in bld[bld.intersects(all_u.buffer(80))].geometry])
    deg: Counter = Counter()
    for g in seg.geometry:
        cs = list(g.coords) if g.geom_type == "LineString" else list(max(g.geoms, key=lambda q: q.length).coords)
        for c in (cs[0], cs[-1]):
            deg[(round(c[0] * 2) / 2, round(c[1] * 2) / 2)] += 1
    xn = unary_union([Point(p) for p, d in deg.items() if d >= 3])
    xsec = unary_union(xs.geometry.buffer(0))
    walk = wk[wk.intersects(clip)]
    walk_u = unary_union([shapely.make_valid(q) for q in walk.geometry])
    a = WidthEngine(ng1_u, ng_u, rw_u, bld_u, xn, xsec, walk_u=walk_u)
    b = WidthEngine(ng1_u, ng_u, rw_u, bld_u, xn, xsec, walk_u=None)
    return seg, a, b, walk_u, len(walk), all_u.buffer(50).boundary


def survey() -> dict:
    seg, A, B, walk_u, n_walk, all_u_edge = build_engines()
    recs = []
    for r in seg.itertuples():
        g = r.geometry if r.geometry.geom_type == "LineString" else max(r.geometry.geoms, key=lambda q: q.length)
        a, b = A.widths(g), B.widths(g)
        ra = {round(float(x["s"]), 3): x["w"] for x in a[6][2]}
        rb = {round(float(x["s"]), 3): x["w"] for x in b[6][2]}
        diffs = []
        for s_, wa in ra.items():
            wb = rb.get(s_)
            if wa is None and wb is None:
                continue
            diffs.append(None if (wa is None) != (wb is None) else float(wb) - float(wa))
        real = [d for d in diffs if d is not None]
        recs.append({
            "seg_id": r.seg_id, "seg_uid": r.seg_uid, "road": r.road_name,
            "length_m": r.length_m, "merged_n": getattr(r, "merged_n", None), "inherited": bool(getattr(r, "inherited", False)),
            "midpoint_fallback": bool(getattr(r, "midpoint_fallback", False)), "n_sample": getattr(r, "n_sample", None),
            "width_cov": getattr(r, "width_cov", None), "in_emd": bool(getattr(r, "in_emd", False)),
            "edge_dist": float(all_u_edge.distance(g)),
            "src": r.width_src, "ledger": r.road_bt_m, "pub_wmin": r.width_min_m,
            "wmin_a": None if a[0] is None else float(a[0]), "wmin_b": None if b[0] is None else float(b[0]),
            "wmed_a": None if a[6][4] is None else float(a[6][4]), "wmed_b": None if b[6][4] is None else float(b[6][4]),
            "n_samples": len(real), "n_changed": sum(1 for d in real if abs(d) > EPS) + sum(1 for d in diffs if d is None),
            "walk_dist": float(walk_u.distance(g)) if not walk_u.is_empty else float("inf"),
        })
    return {"n": len(recs), "n_walk_polygons": n_walk, "recs": recs}


def _q(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    a = np.array(xs)
    return {"n": len(xs), "중앙": round(float(np.median(a)), 3), "평균": round(float(a.mean()), 3),
            "p90": round(float(np.percentile(a, 90)), 3), "최대": round(float(a.max()), 3)}


def _repro(r: dict) -> bool:
    return ((r["wmin_a"] is None and r["pub_wmin"] is None)
            or (r["wmin_a"] is not None and r["pub_wmin"] is not None and abs(r["wmin_a"] - r["pub_wmin"]) <= REPRO_TOL))


def repro_failures(allrecs: list[dict], good: list[dict]) -> dict:
    """못 맞춘 구간의 목록과 **공통점** — 재현한 구간과 같은 칸으로 대 본다. 고치지 않는다."""
    bad = [r for r in allrecs if not _repro(r)]

    def kind(r: dict) -> str:
        if r["wmin_a"] is None:
            return "엔진 wmin 없음 · 발행본 있음"
        if r["pub_wmin"] is None:
            return "엔진 wmin 있음 · 발행본 없음"
        return "둘 다 있고 값이 다르다"

    def stat(rs: list[dict], key: str, f=None) -> dict:
        v = [(f(r) if f else r[key]) for r in rs if (r.get(key) is not None or f)]
        v = [x for x in v if x is not None and x == x]
        return _q([float(x) for x in v]) if v else {"n": 0}

    def share(rs: list[dict], pred) -> str:
        return f"{sum(1 for r in rs if pred(r))}/{len(rs)} ({100 * sum(1 for r in rs if pred(r)) / max(len(rs), 1):.0f}%)"

    rows = [{"seg_id": r["seg_id"], "seg_uid": r["seg_uid"], "도로명": r["road"], "width_src": r["src"], "length_m": r["length_m"],
             "발행본 wmin": r["pub_wmin"], "엔진 wmin": None if r["wmin_a"] is None else round(r["wmin_a"], 3),
             "차(엔진 − 발행)": None if (r["wmin_a"] is None or r["pub_wmin"] is None) else round(r["wmin_a"] - r["pub_wmin"], 3),
             "유형": kind(r), "판정 범위 근사 가장자리까지 m": round(r["edge_dist"], 1), "병합 n": r["merged_n"], "inherited": r["inherited"],
             "midpoint_fallback": r["midpoint_fallback"], "n_sample": r["n_sample"], "width_cov": r["width_cov"]} for r in bad]
    cols = {
        "길이 m": lambda rs: stat(rs, "length_m"),
        "판정 범위 근사 가장자리까지 m": lambda rs: stat(rs, "edge_dist"),
        "n_sample": lambda rs: stat(rs, "n_sample"),
        "width_cov": lambda rs: stat(rs, "width_cov"),
    }
    common = {name: {"못 맞춤": f(bad), "맞춤": f(good)} for name, f in cols.items()}
    flags = {"구간 합집합의 바깥 가장자리(≤ 50.5m — 근사한 교차 노드가 틀릴 수 있는 곳)": lambda r: r["edge_dist"] <= 50.5, "병합 구간(병합 n > 1)": lambda r: (r["merged_n"] or 1) > 1,
             "inherited": lambda r: r["inherited"], "midpoint_fallback": lambda r: r["midpoint_fallback"],
             "동 경계 안(in_emd)": lambda r: r["in_emd"], "길이 < 6m": lambda r: (r["length_m"] or 0) < 6,
             "폭 소스 silpok": lambda r: r["src"] == "silpok", "폭 소스 ngii1k": lambda r: r["src"] == "ngii1k"}
    common["비율"] = {name: {"못 맞춤": share(bad, f), "맞춤": share(good, f)} for name, f in flags.items()}
    allr = bad + good
    bands = ((0, 50.5, "가장자리 ≤ 50.5m"), (50.5, 100, "50.5~100m"), (100, 150, "100~150m"), (150, 1e9, "150m 이상"))
    common["가장자리 거리 대별 못 맞춤 비율"] = {name: f"{sum(1 for r in bad if lo <= r['edge_dist'] < hi)}/{sum(1 for r in allr if lo <= r['edge_dist'] < hi)}" for lo, hi, name in bands}
    common["폭 소스별 못 맞춤 비율"] = {src: f"{sum(1 for r in bad if r['src'] == src)}/{sum(1 for r in allr if r['src'] == src)}" for src in ("ngii1k", "silpok")}
    common["도로명 집중(못 맞춤 상위)"] = dict(Counter(r["road"] for r in bad).most_common(4))
    common["유형"] = dict(Counter(kind(r) for r in bad))
    diffs = [r["wmin_a"] - r["pub_wmin"] for r in bad if r["wmin_a"] is not None and r["pub_wmin"] is not None]
    common["차(엔진 − 발행) 분포"] = _q(diffs) | ({"부호": f"엔진이 더 큼 {sum(1 for d in diffs if d > 0)} · 더 작음 {sum(1 for d in diffs if d < 0)}"} if diffs else {})
    small = sum(1 for d in diffs if abs(d) < 0.3)
    common["차 크기"] = {"|차| < 0.3m": small, "|차| ≥ 1m": sum(1 for d in diffs if abs(d) >= 1), "전체": len(diffs)}
    return {"n": len(bad), "목록": rows, "공통점": common}


def _none_if_nan(x):
    return None if (x is None or (isinstance(x, float) and x != x)) else x


def _clean(recs: list[dict]) -> list[dict]:
    """GeoPackage 의 빈 칸은 NaN 으로 온다 — `None` 과 같은 「없음」으로 접는다(안 접으면 둘 다 없는 구간이 어긋난 것으로 센다)."""
    keys = ("pub_wmin", "ledger", "width_cov", "n_sample", "merged_n", "src", "length_m", "road")
    return [{**r, **{k: _none_if_nan(r.get(k)) for k in keys}} for r in recs]


def summarize(raw: dict) -> dict:
    allrecs = _clean(raw["recs"])
    n_all = len(allrecs)
    recs = [r for r in allrecs if _repro(r)]
    n = len(recs)
    if n / n_all < REPRO_MIN:
        raise SystemExit(f"★ 재현 관문 실패 — 발행본 wmin 과 같은 구간 {n}/{n_all} ({100 * n / n_all:.1f}%) < {100 * REPRO_MIN:.0f}%. 입력 근사가 틀렸다. 못 쟀다.")
    bad = [r for r in allrecs if not _repro(r)]
    res: dict = {"구간(발행본)": n_all, "재현한 구간(이 표의 분모)": n, "보도 폴리곤(판정 범위 안)": raw["n_walk_polygons"],
                 "재현 관문": {"wmin 일치(±0.015)": n, "비율 %": round(100 * n / n_all, 2),
                           "못 맞춘 구간": len(bad), "못 맞춘 구간의 width_src": dict(Counter(r["src"] for r in bad)),
                           "읽는 법": f"못 맞춘 구간은 아래 모든 수에서 **뺐다**(근사한 입력 — 판정 범위 · 교차 노드 — 이 그 구간에서 달랐다). 하한 {int(100 * REPRO_MIN)}%"}}
    res["재현 못 한 구간"] = repro_failures(allrecs, recs)
    res["표본틀 — 재현한 구간 중 보도 20m 밖"] = [{"seg_id": r["seg_id"], "seg_uid": r["seg_uid"]} for r in recs if r["walk_dist"] > 20]
    changed = [r for r in recs if r["n_changed"] > 0]
    res["carve 가 한 표본이라도 바꾼 구간"] = {"n": len(changed), "%": round(100 * len(changed) / n, 1)}
    res["보도 폴리곤이 가까이 없어 못 깎은 구간"] = {f"{int(d)}m 안에 없음": sum(1 for r in recs if r["walk_dist"] > d) for d in NEAR}
    res["보도 폴리곤이 가까이 있는데 안 바뀐 구간"] = {f"{int(d)}m": sum(1 for r in recs if r["walk_dist"] <= d and r["n_changed"] == 0) for d in NEAR}
    by: dict = {}
    for src in ("ngii1k", "ngii", "silpok"):
        g = [r for r in recs if r["src"] == src]
        ch = [r for r in g if r["n_changed"] > 0]
        dmin = [r["wmin_b"] - r["wmin_a"] for r in ch if r["wmin_a"] is not None and r["wmin_b"] is not None]
        dmed = [r["wmed_b"] - r["wmed_a"] for r in ch if r["wmed_a"] is not None and r["wmed_b"] is not None]
        by[src] = {"구간": len(g),
                   **{f"보도 {int(d)}m 안": sum(1 for r in g if r["walk_dist"] <= d) for d in NEAR},
                   "carve 로 바뀐 구간": len(ch), "바뀐 비율 %": round(100 * len(ch) / len(g), 1) if g else None,
                   "wmin 감소량(깎기 전 − 후, 바뀐 구간)": _q([x for x in dmin if abs(x) > EPS]),
                   "wmed 감소량": _q([x for x in dmed if abs(x) > EPS])}
    res["width_src 별"] = by
    # 문턱을 넘긴 구간 — 깎기 전이면 판정이 달랐을 곳
    both = [r for r in recs if r["wmin_a"] is not None and r["wmin_b"] is not None]
    res["carve 가 문턱을 넘긴 구간(wmin)"] = {
        "깎기 전 ≥ 7.0 이고 깎은 뒤 < 7.0 (clear 에서 빠짐)": sum(1 for r in both if r["wmin_b"] >= 7.0 > r["wmin_a"]),
        "깎기 전 ≥ 3.0 이고 깎은 뒤 < 3.0 (통과 하한 아래로)": sum(1 for r in both if r["wmin_b"] >= 3.0 > r["wmin_a"])}
    # 체계적으로 넓은가 — 대장폭 층을 나눠 대조한다(폭 자체는 길 종류가 정한다)
    strata = (("대장 < 4", 0, 4), ("대장 4~7", 4, 7), ("대장 7~12", 7, 12), ("대장 ≥ 12", 12, 1e9))
    cmp_: dict = {}
    for name, lo, hi in strata:
        g = [r for r in recs if r["ledger"] is not None and lo <= r["ledger"] < hi and r["pub_wmin"] is not None and r["ledger"] > 0]
        far = [r["pub_wmin"] / r["ledger"] for r in g if r["walk_dist"] > 20]
        near = [r["pub_wmin"] / r["ledger"] for r in g if r["walk_dist"] <= 20]
        chg = [r["pub_wmin"] / r["ledger"] for r in g if r["n_changed"] > 0]
        row = {"보도 20m 안에 없음(wmin ÷ 대장)": _q(far), "보도 20m 안에 있음": _q(near), "carve 로 바뀜": _q(chg)}
        if len(far) >= 5 and len(near) >= 5:
            from scipy.stats import mannwhitneyu
            row["p(없음 대 있음)"] = round(float(mannwhitneyu(far, near).pvalue), 4)
            row["중앙 차(없음 − 있음)"] = round(statistics.median(far) - statistics.median(near), 3)
        cmp_[name] = row
    res["대장폭 층별 wmin ÷ 대장"] = cmp_
    return res


def main() -> int:
    # 계산이 오래 걸려(약 5분) `--save-raw` 로 구간별 원자료를 저장하고 `--load-raw` 로 다시 읽을 수 있다(요약 로직만 고칠 때).
    ap = argparse.ArgumentParser(description="carve 적용 범위 조사 — 수는 data/processed/carve_survey.json 에 쓴다")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--save-raw", type=Path, metavar="PATH", help="구간별 원자료를 저장한다")
    g.add_argument("--load-raw", type=Path, metavar="PATH", help="저장한 원자료로 요약만 다시 낸다")
    args = ap.parse_args()
    raw_path = args.load_raw or args.save_raw
    if args.load_raw is not None:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        raw = survey()
        if raw_path is not None:
            raw_path.write_text(json.dumps(raw, ensure_ascii=False) + "\n", encoding="utf-8")
    res = summarize(raw)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

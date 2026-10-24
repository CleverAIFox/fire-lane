#!/usr/bin/env python3
"""
tools/ledgercross.py — **도로대장 명목폭(`road_bt_m`)이 무엇인지**를 발행본으로 잰다.  (Zm21 · DECISIONS §567)

    uv run python tools/ledgercross.py            표를 찍고 data/processed/ledger_cross.json 을 쓴다
    uv run python tools/ledgercross.py --no-write 파일 없이 찍기만
    uv run python tools/ledgercross.py --selftest ★ 판별식이 살아 있나

── 무엇을 재나 ─────────────────────────────────────────────────
대장 값이 **측량값인가 등재 계단값인가**, 그리고 우리 측정과 어긋나는 구간이 **경향인가 개별 사건인가**.
판정은 건드리지 않는다. 대장은 폭의 입력(값을 섞는 대상)이 아니라 「불일치 신호」로만 쓴다(§567).

  a) 계단 집합 · 계단별 구간 수 · 정수값 비율 · 서로 다른 값 수
  b) 구간별 계단 차이 `d = idx(대장) − idx(올림(우리 width_min_m))`  (`d > 0` = 대장이 더 넓게 적었다)
  c) d 분포 · ±1칸 / ±2칸 누적 · `+1` 대 `−1` 비대칭비
  d) 대장 구간대(1-3 / 4-9 / 10-14 / 15+)별 비(우리/대장)의 중앙 · 사분위
  e) 대장 값별 우리 측정(법선) 중앙
  f) `|d| ≥ 5` 구간 명단 — 사람이 네이버 지도에 붙일 중앙점 위경도(WGS84 · 「위도, 경도」 · 소수 6자리)
  g) 그 명단을 ① 대장이 위(d>0) ② 대장이 아래(d<0) ③ `ecc_rel_med_m` 이 정상군 상위 사분위를 넘는 것 — 셋으로 가르고 겹침을 센다
  h) 모순군과 정상군(`|d| ≤ 1`)의 품질 칸 대조표
  i) 도로명별 모순 집계 — `|d| ≥ 5` 가 2구간 이상인 도로명과 d 부호 쏠림
  + 곁가지 셋(§567 이 인용): `nfa_designated` 판정 분포 · `occ_pressure` 판정별 · 동계천로 대장 15.0 의 `struct_kind`

── 규율 ───────────────────────────────────────────────────────
★ **ㄱ/ㄴ(측정이 약하냐 아니냐)로 가르지 않는다.** h) 가 보이듯 그 갈래는 비어 보인다. 그리고 커버율 1.0 · 표본 수는
  **측정이 수행됐다는 뜻이지 정확하다는 뜻이 아니다**(DECISIONS 기각 가설 14 「SE는 정밀도지 정확도가 아니다」와 같은 함정).
  이 도구는 내부 지표로 정확도를 주장하지 않는다.
★ ③ 의 문턱은 **상수가 아니다.** 정상군 `ecc_rel_med_m` 분포에서 백분위(`ECC_PCT` = 75, 「상위 사분위」)로 뽑고
  백분위와 실제 값을 json 에 같이 낸다.
★ 계단 집합은 **대장 값에서 유도한다**(손으로 적지 않는다). 올림은 `step ≥ 값` 인 첫 계단 — 값이 계단과 같으면 그 계단이다(동점은 자기 자신).
  최대 계단을 넘는 값은 최대 계단으로 접고 그 수를 `clamped` 에 센다.
★ 구간 집합은 **발행본(`web/data/segments.geojson`) 1,281구간 그대로**다. 스코프 폴리곤 · 경계 판정을 이 도구가 다시 하지 않는다 —
  발행본이 이미 `segments.py` 의 그것을 거쳤다. 결측(`road_bt_m` 또는 `width_min_m` 없음)은 빼고 그 수를 `excluded` 에 센다.
★ 사분위 · 분위수는 `statkit.quartiles` · `firelane.quantile` 이 든다 — 여기서 공식을 다시 짜지 않는다.

IN    web/data/segments.geojson · data/processed/segments_5186.gpkg(중앙점)
OUT   data/processed/ledger_cross.json (processed 산출물 — 커밋 안 한다)
PARAM `ECC_PCT` · `GAP_BIG` (|d| 문턱 5 — 감사가 정한 모순 문턱이다. 측정으로 도출한 값이 아니다)
밖    **판정 폐포 밖이다** — `segments.py` 가 부르지 않는다. **대장이 참인가는 안 정한다** — 어긋난 곳을 낼 뿐이다.
      **레이크(`data/norm`)는 안 읽는다** — 대장 값은 발행본 `road_bt_m` 에 이미 실려 있다. 우리 측정이 정확한지는 못 말한다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict

from statkit import num, quartiles

from firelane.paths import PROCESSED, WEB
from firelane.quantile import quantile

OUT = PROCESSED / "ledger_cross.json"
SEG = WEB / "segments.geojson"
SEG_5186 = PROCESSED / "segments_5186.gpkg"

ECC_PCT = 75          # 「정상군 상위 사분위」 — 백분위만 정하고 값은 분포에서 뽑는다
GAP_BIG = 5           # |d| ≥ 이 값이면 모순군. 감사가 정했다 — 측정으로 도출한 값이 아니다
NORMAL_GAP = 1        # |d| ≤ 이 값이 정상군
BANDS = (("1-3", 0.0, 4.0), ("4-9", 4.0, 10.0), ("10-14", 10.0, 15.0), ("15+", 15.0, float("inf")))
QUALITY = ("width_cov", "n_sample", "n_poly", "width_fail", "width_disagree_m",
           "width_source_conflict_m", "ecc_rel_med_m", "length_m")
LIST_COLS = ("seg_id", "road_name", "road_bt_m", "width_min_m", "clear_med_m", "verdict", "width_src",
             "width_cov", "n_sample", "n_poly", "width_disagree_m", "width_source_conflict_m",
             "ecc_rel_med_m", "length_m", "struct_kind", "nfa_designated", "occ_pressure")
KEYS = ("steps", "d_distribution", "bands", "by_ledger_value", "contradictions", "groups",
        "quality", "by_road", "extras", "params", "counts")


def _r(v: float) -> float:
    return round(float(v), 6)


def is_step(v: float) -> bool:
    """등재 계단은 **정수 미터**다. 소수 값(1.448 · 36.473 …)은 계단이 아니라 측량·계산에서 온 예외다."""
    return abs(v - round(v)) < 1e-9


def steps_of(ledger: list[float]) -> list[float]:
    """대장의 **정수값**에서 유도한 계단 집합(오름차순). 손으로 적지 않는다.

    ★ 소수 값까지 계단으로 세면 30종 중 열 몇이 소수 예외라 「한 칸」의 뜻이 흐려진다 — 정수만 계단이고
      소수 값을 가진 구간은 `d` 를 안 낸다(`counts.non_step` 으로 세고 `by_ledger_value` 에는 남긴다).
    """
    return sorted({_r(v) for v in ledger if is_step(v)})


def ceil_idx(value: float, steps: list[float]) -> tuple[int, bool]:
    """`step ≥ value` 인 첫 계단의 위치. 값이 계단과 같으면 그 계단이다. 최대를 넘으면 (최대, True)."""
    for i, s in enumerate(steps):
        if s >= value - 1e-9:
            return i, False
    return len(steps) - 1, True


def gap(ledger: float, ours: float, steps: list[float]) -> tuple[int, bool]:
    """`d = idx(대장) − idx(올림(우리))`. 대장이 위면 양수."""
    i, clamped = ceil_idx(ours, steps)
    return steps.index(_r(ledger)) - i, clamped


def _med(xs: list[float]) -> float | None:
    return None if not xs else float(statistics.median(xs))


def _pack(xs: list[float]) -> dict:
    q = quartiles(xs)
    return {k: (v if k == "n" else _r(v)) for k, v in q.items()} if xs else {"n": 0}


def analyse(rows: list[dict]) -> dict:
    """`rows` = 구간 속성 목록(+ `lat` · `lon`). 순수 함수 — 파일을 안 읽는다."""
    usable, excluded = [], 0
    for r in rows:
        lg, w = num(r.get("road_bt_m")), num(r.get("width_min_m"))
        if lg is None or w is None:
            excluded += 1
            continue
        usable.append({**r, "_lg": lg, "_w": w})
    steps = steps_of([r["_lg"] for r in usable])
    clamped = non_step = 0
    for r in usable:
        if not is_step(r["_lg"]):
            r["_d"] = None
            non_step += 1
            continue
        r["_d"], c = gap(r["_lg"], r["_w"], steps)
        clamped += c

    n_all = len(usable)
    usable_all = usable
    usable = [r for r in usable if r["_d"] is not None]      # d 를 낸 구간
    n = len(usable)
    by_step = Counter(_r(r["_lg"]) for r in usable)
    integer = n
    dist = Counter(r["_d"] for r in usable)
    cum = lambda k: sum(c for d, c in dist.items() if abs(d) <= k)  # noqa: E731
    up, down = dist.get(1, 0), dist.get(-1, 0)

    # ★ 비(우리/대장)는 계단이 필요 없다 — 소수 대장값 구간도 든다(`usable_all`). 같은 구간들에 대해
    #   「대장이 **정확히 우리 값의 올림**이라면」 나왔을 비(`quantization_baseline`)를 같이 낸다 — 비 0.87 이 계단 간격만으로 설명되는가를
    #   눈으로 대는 자다. 실제 중앙이 이 기준과 가까우면 양자화로 설명되고, 훨씬 낮으면 설명되지 않는다.
    bands = {}
    for name, lo, hi in BANDS:
        inb = [r for r in usable_all if lo <= r["_lg"] < hi and r["_lg"] > 0]
        pack = _pack([r["_w"] / r["_lg"] for r in inb])
        if steps and inb:
            base = [r["_w"] / steps[ceil_idx(r["_w"], steps)[0]] for r in inb if r["_w"] > 0]
            pack["quantization_baseline"] = _pack(base)
        bands[name] = pack
    by_val: dict[str, dict] = {}
    for v in steps:
        ws = [r["_w"] for r in usable_all if _r(r["_lg"]) == v]
        by_val[str(v)] = {"n": len(ws), "width_min_median": None if not ws else _r(_med(ws))}
    off = [r["_w"] for r in usable_all if r["_d"] is None]
    by_val["non_step"] = {"n": len(off), "width_min_median": None if not off else _r(_med(off))}

    normal = [r for r in usable if abs(r["_d"]) <= NORMAL_GAP]
    contra = [r for r in usable if abs(r["_d"]) >= GAP_BIG]
    eccs = [num(r.get("ecc_rel_med_m")) for r in normal]
    eccs = [e for e in eccs if e is not None]
    ecc_cut = quantile(eccs, ECC_PCT / 100) if eccs else None

    def listing(r: dict) -> dict:
        row = {k: r.get(k) for k in LIST_COLS}
        row.update(d=r["_d"], lat=r.get("lat"), lon=r.get("lon"),
                   latlon=None if r.get("lat") is None else f"{r['lat']:.6f}, {r['lon']:.6f}")
        return row

    ids = lambda rs: {r["seg_id"] for r in rs}  # noqa: E731
    g_up = [r for r in contra if r["_d"] > 0]
    g_dn = [r for r in contra if r["_d"] < 0]
    g_ecc = [r for r in contra if ecc_cut is not None and (num(r.get("ecc_rel_med_m")) or -1) > ecc_cut]

    quality = {}
    for col in QUALITY:
        def stat(rs, col=col):
            vals = [num(r.get(col)) for r in rs]
            have = [v for v in vals if v is not None]
            return {"n": len(have), "of": len(rs), "median": None if not have else _r(_med(have))}
        quality[col] = {"contradiction": stat(contra), "normal": stat(normal)}

    roads: dict[str, list[int]] = defaultdict(list)
    for r in contra:
        roads[r.get("road_name") or ""].append(r["_d"])
    by_road = {}
    for name, ds in sorted(roads.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(ds) < 2:
            continue
        pos, neg = sum(d > 0 for d in ds), sum(d < 0 for d in ds)
        by_road[name] = {"n": len(ds), "positive": pos, "negative": neg,
                         "one_sided": min(pos, neg) == 0, "d_median": _med(ds)}

    nfa = Counter(r.get("verdict") for r in rows if r.get("nfa_designated") is True)
    occ_all = {v: [num(r.get("occ_pressure")) for r in rows if r.get("verdict") == v] for v in
               ("clear", "needs_cv", "unknown", "blocked")}
    occ = {}
    for v, xs in occ_all.items():
        have = [x for x in xs if x is not None]
        occ[v] = {"n": len(have), "of": len(xs), "mean": None if not have else _r(statistics.fmean(have)),
                  "median": None if not have else _r(_med(have))}
    dgc = [r for r in rows if str(r.get("road_name") or "").startswith("동계천로") and num(r.get("road_bt_m")) == 15.0]

    return {
        "steps": {"values": steps, "n_distinct": len(steps), "per_step": {str(k): by_step[k] for k in steps},
                  "integer_share": None if not n_all else _r(integer / n_all),
                  "distinct_values_all": len({_r(r["_lg"]) for r in usable_all})},
        "d_distribution": {"counts": {str(k): dist[k] for k in sorted(dist)},
                           "within_1": _r(cum(1) / n) if n else None, "within_2": _r(cum(2) / n) if n else None,
                           "plus1": up, "minus1": down, "plus1_over_minus1": None if not down else _r(up / down)},
        "bands": bands,
        "by_ledger_value": by_val,
        "contradictions": [listing(r) for r in sorted(contra, key=lambda r: (-abs(r["_d"]), r["seg_id"]))],
        "groups": {
            "n_contradictions": len(contra),
            "ledger_above": {"n": len(g_up), "seg_ids": sorted(ids(g_up))},
            "ledger_below": {"n": len(g_dn), "seg_ids": sorted(ids(g_dn))},
            "ecc_high": {"n": len(g_ecc), "seg_ids": sorted(ids(g_ecc)), "threshold": None if ecc_cut is None else _r(ecc_cut),
                         "percentile": ECC_PCT, "of_normal_n": len(eccs)},
            "overlap": {"ecc_high_and_above": len(ids(g_ecc) & ids(g_up)), "ecc_high_and_below": len(ids(g_ecc) & ids(g_dn)),
                        "ecc_high_only": len(ids(g_ecc) - ids(g_up) - ids(g_dn)),
                        "ecc_high_share": None if not contra else _r(len(g_ecc) / len(contra))},
        },
        "quality": quality,
        "by_road": by_road,
        "extras": {
            "nfa_designated_verdicts": dict(sorted(nfa.items(), key=lambda kv: str(kv[0]))),
            "occ_pressure_by_verdict": occ,
            "dongyecheon_ledger_15": {"n": len(dgc), "struct_kind": dict(Counter(str(r.get("struct_kind")) for r in dgc))},
        },
        "params": {"ECC_PCT": ECC_PCT, "GAP_BIG": GAP_BIG, "NORMAL_GAP": NORMAL_GAP, "bands": [b[0] for b in BANDS]},
        "counts": {"segments": len(rows), "usable": n_all, "with_d": n, "non_step": non_step, "excluded": excluded, "clamped": clamped,
                   "normal": len(normal), "contradiction": len(contra)},
    }


def load() -> list[dict]:
    """발행본 속성 + 중앙점. 없으면 죽는다 — 빈 표를 내지 않는다."""
    if not SEG.exists():
        sys.exit(f"★ {SEG} 없음 — 먼저 publish 를 돌려라")
    feats = json.loads(SEG.read_text(encoding="utf-8"))["features"]
    rows = [dict(f["properties"]) for f in feats]
    mids = _midpoints()
    for r in rows:
        r["lat"], r["lon"] = mids.get(r["seg_id"], (None, None))
    return rows


def _midpoints() -> dict[str, tuple[float, float]]:
    if not SEG_5186.exists():
        return {}
    import geopandas as gpd

    g = gpd.read_file(SEG_5186)
    out: dict[str, tuple[float, float]] = {}
    for sid, ln in zip(g["seg_id"], g.geometry, strict=True):
        if ln.geom_type != "LineString":
            ln = max(ln.geoms, key=lambda x: x.length)
        pt = gpd.GeoSeries([ln.interpolate(ln.length / 2)], crs=g.crs).to_crs(4326).iloc[0]
        out[sid] = (round(pt.y, 6), round(pt.x, 6))
    return out


def show(res: dict) -> None:
    c, s, d = res["counts"], res["steps"], res["d_distribution"]
    print(f"구간 {c['segments']} · 쓸 수 있는 {c['usable']} (d 를 낸 {c['with_d']} · 소수 대장값 {c['non_step']}) · 결측 제외 {c['excluded']} · 최대 계단 초과 {c['clamped']}")
    print(f"계단(정수) {s['n_distinct']}종 {s['values']} · 서로 다른 대장 값 {s['distinct_values_all']}종 · 정수값 비율 {s['integer_share']}")
    print(f"d ±1 {d['within_1']} · ±2 {d['within_2']} · +1 {d['plus1']} 대 −1 {d['minus1']} (비 {d['plus1_over_minus1']})")
    for k, v in res["bands"].items():
        print(f"  대장 {k:<6} n={v['n']:<4} 비(우리/대장) 사분위 {v.get('q25')} / {v.get('median')} / {v.get('q75')}"
              f" · 올림 기준 중앙 {v.get('quantization_baseline', {}).get('median')}")
    g = res["groups"]
    print(f"모순 |d|≥{GAP_BIG}: {g['n_contradictions']} = ① 위 {g['ledger_above']['n']} + ② 아래 {g['ledger_below']['n']}"
          f" · ③ ecc 높음 {g['ecc_high']['n']} (문턱 {g['ecc_high']['threshold']} = 정상군 {ECC_PCT}백분위)")
    print(f"  겹침 {g['overlap']}")
    for col, q in res["quality"].items():
        print(f"  품질 {col:<24} 모순 {q['contradiction']['median']} (n {q['contradiction']['n']}) · 정상 {q['normal']['median']} (n {q['normal']['n']})")
    print(f"  도로명 2구간 이상: {len(res['by_road'])}종")


def selftest() -> int:
    bad: list[str] = []
    steps = [1.0, 2.0, 3.0, 6.0, 9.0]
    if ceil_idx(2.0, steps) != (1, False):
        bad.append("값이 계단과 같을 때 자기 자신이 아니다")
    if ceil_idx(2.01, steps) != (2, False):
        bad.append("올림이 다음 계단이 아니다")
    if ceil_idx(99.0, steps) != (4, True):
        bad.append("최대 초과를 접고 표시하지 않는다")
    if gap(9.0, 2.5, steps) != (2, False):
        bad.append("대장이 위일 때 d 가 양수가 아니다")
    if gap(1.0, 5.0, steps) != (-3, False):
        bad.append("대장이 아래일 때 d 가 음수가 아니다")
    rows = [{"seg_id": f"S{i}", "road_bt_m": lg, "width_min_m": w, "ecc_rel_med_m": 0.1 * i, "verdict": "clear"}
            for i, (lg, w) in enumerate([(2.0, 2.0), (3.0, 2.5), (9.0, 1.0), (1.0, 8.5), (9.0, 8.9), (30.0, 1.0), (4.0, 3.9), (5.0, 4.9), (6.0, 5.9), (7.0, 6.9)] * 2)]
    res = analyse(rows)
    if set(res) != set(KEYS):
        bad.append(f"키가 다르다 — {sorted(set(res) ^ set(KEYS))}")
    if res["counts"]["contradiction"] == 0:
        bad.append("합성 모순을 못 잡았다")
    for x in bad:
        print("  ✗", x)
    print("✓ 살아 있다" if not bad else f"✗ {len(bad)}건")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    res = analyse(load())
    show(res)
    if not a.no_write:
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
sensitivity.py — 폭 오차가 판정을 얼마나 흔드는지 **센다.** 판정은 건드리지 않는다.

    uv run python tools/sensitivity.py                 표 + data/processed/sensitivity.json
    uv run python tools/sensitivity.py --boot 1000     부트스트랩 횟수(기본 1000)

IN    data/processed/segments.geojson (판정 입력 전부를 든 열) ·
      `widthcross._load()` 가 다시 낸 측량 대조 오차 422개(§562)
OUT   data/processed/sensitivity.json · 화면 ·
      data/field/flip_2610.csv · data/field/flip_top_2610.csv · data/processed/flip_detail.json (Zm25 · Zm26 — 뒤집힘 명단)
PARAM 없다. 문턱은 전부 `seg/classify.py` · `seg/params.py` 에서 온다.
밖    **판정 폐포 밖이다. 아무것도 발행하지 않는다.**
      `params.py` · `classify.py` 를 고치지 않는다 — 시뮬레이션은 **프로세스 안에서만**
      모듈 전역(`classify.TRUCK/CLEAR_M/LEDGER_BLOCK_M` · `geom.TRUCK/PARK`)을 잠시
      바꿨다 되돌린다(`_consts`). `classify()` 를 그대로 부르므로 판정 문은 하나다(§303).
      **문턱을 제안하지 않는다.** 수를 내고 멈춘다. 채택은 사람이 정한다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)

── 정의 ────────────────────────────────────────────────────────
  뒤집힘   같은 구간의 판정(blocked/clear/needs_cv/unknown)이 시뮬레이션 전후에 다르다.
           사유(reason)만 바뀐 것은 세지 않는다.
  오차     `wmin − survey` (§562 · 422구간). 기본은 규격대로 **폭에 +d 를 더한다.**
           부호를 뒤집은 −d(측량 쪽으로 보정하는 방향)도 같이 낸다.
  폭 열    판정에 드는 다섯: wmin · wmax · wmin_any · wsym · clear_med.
           대장폭(road_bt)은 폭 측정이 아니라 대장이라 안 흔든다. 음수는 0 으로 자른다.
  시드     `evalgen.SEED`(기존 규약).
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
from evalgen import SEED

import firelane.seg.classify as C
import firelane.seg.geom as G
from firelane.seg.classify import SPREAD_MAX, classify

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "data" / "processed" / "segments.geojson"
OUT = ROOT / "data" / "processed" / "sensitivity.json"
FLIP_CSV = ROOT / "data" / "field" / "flip_2610.csv"
FLIP_TOP_CSV = ROOT / "data" / "field" / "flip_top_2610.csv"
FLIP_JSON = ROOT / "data" / "processed" / "flip_detail.json"
EVALSET = ROOT / "data" / "field" / "evalset_2610.csv"     # 표만 읽는다. `.key.json` 은 열지 않는다
LEDGER_CROSS = ROOT / "data" / "processed" / "ledger_cross.json"
ORDER = ("blocked", "clear", "needs_cv", "unknown")
BASE_TRUCK, BASE_PARK = C.TRUCK, G.PARK
BASE_CLEAR = C.CLEAR_M
WIDTH_COLS = ("width_min_m", "width_max_m", "width_min_any_m", "width_min_sym_m", "clear_med_m")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@contextlib.contextmanager
def _consts(*, truck: float | None = None, clear: float | None = None):
    """모듈 전역을 잠시 바꾼다. `truck` 만 주면 `CLEAR_M = truck + 2·PARK` 도 따라간다(코드의 유도식 그대로).

    `clear` 를 주면 `geom.PARK` 를 `(clear − truck)/2` 로 맞춘다 — `geom.verdict()` 가
    `TRUCK + 2*PARK` 로 문턱을 만들기 때문이다. 부동소수점으로 문턱이 한 ulp 어긋나면
    2자리 폭이 문턱에 걸린 구간이 거짓으로 갈리므로, 같아질 때까지 PARK 를 한 ulp 씩 민다.
    """
    saved = (C.TRUCK, C.CLEAR_M, C.LEDGER_BLOCK_M, G.TRUCK, G.PARK)
    t = BASE_TRUCK if truck is None else truck
    try:
        park = BASE_PARK
        if clear is not None:
            park = (clear - t) / 2
            for _ in range(64):
                s = t + 2 * park
                if s == clear:
                    break
                park = math.nextafter(park, math.inf if s < clear else -math.inf)
            else:
                raise SystemExit(f"★ 문턱 {clear} 를 부동소수점으로 못 맞췄다")
        c = clear if clear is not None else t + 2 * park
        C.TRUCK, C.CLEAR_M, C.LEDGER_BLOCK_M, G.TRUCK, G.PARK = t, c, t, t, park
        yield
    finally:
        C.TRUCK, C.CLEAR_M, C.LEDGER_BLOCK_M, G.TRUCK, G.PARK = saved


def _cls(p: dict, spread: float | None, d: float | None = None, only_wmin: bool = False) -> str:
    """`classify()` 한 번. `d` 가 있으면 폭 열에 더한다(None 은 None 그대로)."""
    def w(k: str) -> float | None:
        v = p.get(k)
        if v is None or d is None or (only_wmin and k != "width_min_m"):
            return v
        return max(0.0, v + d)
    return classify(
        wmin=w("width_min_m"), wmax=w("width_max_m"), nreg=p["n_sample"],
        road_bt=p["road_bt_m"], length_m=p["length_m"], cctv_dist=p["cctv_dist_m"],
        wmin_any=w("width_min_any_m"), wsym=w("width_min_sym_m"), clear_med=w("clear_med_m"),
        spread_max=spread,
    )[0]


def verdicts(rows: list[dict], *, truck=None, clear=None, spread=SPREAD_MAX) -> list[str]:
    with _consts(truck=truck, clear=clear):
        return [_cls(p, spread) for p in rows]


def counts(vs: list[str]) -> dict[str, int]:
    return {k: sum(1 for v in vs if v == k) for k in ORDER} | {"fragment": sum(1 for v in vs if v == "fragment")}


def load() -> list[dict]:
    return [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]


def survey_errors() -> list[float]:
    """§562 의 422개 오차 `wmin − survey`. `widthcross` 의 매칭을 그대로 다시 돈다."""
    import widthcross as W
    # ★ Zm29. §562 의 422개는 **띠 0.5m** 의 매칭이다. `widthcross` 의 기본 띠는 5m(947쌍)로 올랐다 — 이 모형은 옛 띠를 못 박는다.
    rows = W._load(band=0.5)
    if rows is None:
        raise SystemExit("★ segments_5186.gpkg 가 없다 — 측량 오차를 못 만든다. 못 쟀다.")
    d = [float(r["wmin"]) - float(r["survey"]) for r in rows
         if r["wmin"] is not None and r["survey"] is not None]
    q = np.percentile(d, [25, 50, 75])
    if len(d) != 422 or abs(q[1] - (-0.24)) > 0.005:
        raise SystemExit(f"★ 오차 재현이 §562 와 다르다: n={len(d)} 중앙={q[1]:.3f}. 못 쟀다.")
    return d


# ── 1. 문턱 근처 구간 수 ─────────────────────────────────────────
def near_threshold(rows: list[dict], vs: list[str]) -> dict:
    out = {}
    for col in ("width_min_m", "width_med_m"):
        have = [(p, v) for p, v in zip(rows, vs, strict=True) if p.get(col) is not None]
        res = {"값 있음": len(have), "값 없음": len(rows) - len(have), "띠": {}}
        for b in (0.25, 0.5, 1.0, 1.5):
            inb = [v for p, v in have if abs(p[col] - BASE_CLEAR) <= b + 1e-9]
            res["띠"][f"±{b}"] = {"n": len(inb), "판정": {k: inb.count(k) for k in ORDER}}
        res["정확히 7.00"] = sum(1 for p, _ in have if abs(p[col] - BASE_CLEAR) < 1e-9)
        out[col] = res
    return out


# ── 2. CLEAR_M 곡선 ──────────────────────────────────────────────
def clear_curve(rows: list[dict]) -> dict:
    grid = [round(6.0 + 0.1 * i, 1) for i in range(21)]
    tab = []
    for c in grid:
        k = counts(verdicts(rows, clear=c))
        tab.append({"clear_m": c, **{x: k[x] for x in ORDER}})
    steps = [{"from": a["clear_m"], "to": b["clear_m"],
              **{f"Δ{x}": b[x] - a[x] for x in ORDER}} for a, b in zip(tab, tab[1:], strict=False)]
    mag = [abs(s["Δclear"]) for s in steps]
    around = [s for s in steps if s["to"] in (7.0, 7.1) and s["from"] in (6.9, 7.0)]
    srt = sorted(mag, reverse=True)
    return {
        "표": tab, "단계": steps,
        "요약": {
            "단계당 |Δclear| 중앙": float(np.median(mag)), "최대": max(mag),
            "최대 단계": [(s["from"], s["to"]) for s in steps if abs(s["Δclear"]) == max(mag)],
            "7.0 인접 |Δclear|": {f"{s['from']}→{s['to']}": s["Δclear"] for s in around},
            "7.0 인접 단계의 순위(큰 순, 20단계 중)": {
                f"{s['from']}→{s['to']}": srt.index(abs(s["Δclear"])) + 1 for s in around},
            "7.0 에서 clear 변화율(±0.5 평균 기울기, 구간수/0.1m)":
                (next(t for t in tab if t["clear_m"] == 6.5)["clear"]
                 - next(t for t in tab if t["clear_m"] == 7.5)["clear"]) / 10,
        },
    }


# ── 3. 상수 민감도 ───────────────────────────────────────────────
def const_sens(rows: list[dict], base_v: list[str]) -> dict:
    out = {}
    specs = {
        "TRUCK(3.0) — 코드의 유도식대로 CLEAR_M=TRUCK+2·PARK 도 따라감": lambda f: dict(truck=BASE_TRUCK * f),
        "TRUCK(3.0) — CLEAR_M 은 7.0 에 고정(분리)": lambda f: dict(truck=BASE_TRUCK * f, clear=BASE_CLEAR),
        "SPREAD_MAX(2.5)": lambda f: dict(spread=SPREAD_MAX * f),
        "CLEAR_M(7.0) — 참고": lambda f: dict(clear=BASE_CLEAR * f),
    }
    bases = dict(zip(specs, (BASE_TRUCK, BASE_TRUCK, SPREAD_MAX, BASE_CLEAR), strict=True))
    for name, mk in specs.items():
        res = {}
        for f in (0.8, 0.9, 1.1, 1.2):
            vs = verdicts(rows, **mk(f))
            flips = sum(a != b for a, b in zip(base_v, vs, strict=True))
            res[f"{(f - 1) * 100:+.0f}%"] = {
                "값": round(bases[name] * f, 4),
                "판정 수": {k: counts(vs)[k] for k in ORDER},
                "뒤집힌 구간": flips, "뒤집힌 %": round(100 * flips / len(rows), 2),
            }
        res["최대 뒤집힘 %"] = max(v["뒤집힌 %"] for v in res.values() if isinstance(v, dict))
        out[name] = res
    rank = sorted(out, key=lambda k: -out[k]["최대 뒤집힘 %"])
    return {"상수별": out, "순위(최대 뒤집힘 % 큰 순)": [(k, out[k]["최대 뒤집힘 %"]) for k in rank]}


# ── 4 · 5. 오차를 먹인다 · 띠를 뺀다 ──────────────────────────────
def bootstrap(rows: list[dict], base_v: list[str], errs: list[float], n: int, *,
              sign: float, only_wmin: bool) -> tuple[np.ndarray, np.ndarray]:
    """(`n` × 구간 뒤집힘 행렬, 같은 모양의 행선 코드). 반복마다 422개를 복원추출해 풀을 만들고 구간마다 풀에서 하나를 뽑는다.

    행선 코드는 `ORDER` 의 색인이다. 난수열은 Zm24 와 같으므로 뒤집힘 수도 같다.
    """
    rng = random.Random(SEED)
    m = np.zeros((n, len(rows)), dtype=bool)
    dest = np.zeros((n, len(rows)), dtype=np.int8)
    for b in range(n):
        pool = [rng.choice(errs) for _ in errs]
        for j, p in enumerate(rows):
            v = _cls(p, SPREAD_MAX, sign * rng.choice(pool), only_wmin)
            m[b, j] = v != base_v[j]
            dest[b, j] = ORDER.index(v)
    return m, dest


def _ci(x: np.ndarray) -> dict:
    return {"중앙": float(np.median(x)), "평균": round(float(np.mean(x)), 2),
            "95%": [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]}


def transitions(rows, base_v, errs) -> dict:
    """뒤집힘의 행선 — 풀 전체에서 구간마다 풀에서 하나씩 뽑기를 200번 되풀이해 (전→후) 평균 구간 수를 센다."""
    rng = random.Random(SEED + 7)
    tally: dict[str, float] = {}
    k = 200
    for _ in range(k):
        for j, p in enumerate(rows):
            v = _cls(p, SPREAD_MAX, rng.choice(errs))
            if v != base_v[j]:
                key = f"{base_v[j]}→{v}"
                tally[key] = tally.get(key, 0) + 1
    return {a: round(b / k, 1) for a, b in sorted(tally.items(), key=lambda x: -x[1])}


def band_exclusion(rows: list[dict], base_v: list[str], flips: np.ndarray) -> dict:
    """밴드 안의 (blocked 아닌) 구간을 needs_survey 로 뺀다. 구현이 아니라 계수다.

    needs_survey 는 어휘상 `unknown` 의 사유다(`classify.REASONS`) — 판정은 unknown 으로 센다.
    """
    orig_clear = np.array([v == "clear" for v in base_v])
    f_all = flips[:, orig_clear].sum(1)
    res = {"4번 기준: 원래 clear 중 뒤집힘": {"clear": int(orig_clear.sum()), **_ci(f_all)}, "띠": {}}
    for b in (0.24, 0.25, 0.5):
        inb = np.array([p.get("width_min_m") is not None and abs(p["width_min_m"] - BASE_CLEAR) <= b + 1e-9
                        and v != "blocked" for p, v in zip(rows, base_v, strict=True)])
        new = ["unknown" if m else v for m, v in zip(inb, base_v, strict=True)]
        keep = np.array([v == "clear" for v in new])
        f_keep = flips[:, keep].sum(1)
        moved = {k: int(sum(1 for m, v in zip(inb, base_v, strict=True) if m and v == k)) for k in ORDER}
        res["띠"][f"±{b}  [{BASE_CLEAR - b:.2f}, {BASE_CLEAR + b:.2f}]"] = {
            "띠에 든 구간(blocked 제외)": int(inb.sum()), "이동 전 판정": moved,
            "판정 수": {k: counts(new)[k] for k in ORDER},
            "남은 clear 중 뒤집힘": {"clear": int(keep.sum()), **_ci(f_keep)},
            "4번 대비 줄어든 평균": round(float(np.mean(f_all) - np.mean(f_keep)), 2),
            "4번 대비 줄어든 %": round(100 * (1 - float(np.mean(f_keep)) / float(np.mean(f_all))), 1),
        }
    return res


# ── Zm25. 뒤집힘 명단 ────────────────────────────────────────────
HUMAN_COLS = ("w_full_m", "w_narrow_m", "narrow_s_m", "note")
CSV_COLS = ("seg_id", "seg_uid", "위도", "경도", "도로명", "length_m", "tier", "orig_verdict", "flip_n", "flip_to", "flip_to_pct",
            "thr_name", "thr_dist_m", "in_evalset", *HUMAN_COLS, "method")
CSV_HEAD = (
    "# 뒤집힘 우선순위 명단 (Zm25 · DECISIONS §570) — 이 머리는 읽는 쪽이 '#' 로 시작하는 줄을 건너뛴다",
    "# 1) 이것은 우선순위 명단이지 채점지가 아니다. 봉인하지 않는다 — orig_verdict 를 일부러 보여 준다",
    "# 2) 같은 데이터로 뽑았으므로 이 표로 규칙을 채점하면 순환이다. evalset_2610.csv 와 합치지 않는다(seg_uid 로 사람이 나란히 놓고 잰다)",
    "# 3) flip_n = 부트스트랩 1,000회 중 원래 판정과 다른 판정이 나온 횟수(폭 다섯 열에 +d · 구간 간 독립). flip_to = 가장 흔한 행선 · flip_to_pct = 뒤집힌 횟수 중 그 행선 비율(%)",
    "# 4) tier 1 = 원래 clear 인데 뒤집힘(틀리면 못 가는 길을 갈 수 있다) · 2 = 원래 blocked 인데 뒤집힘(틀리면 갈 수 있는 길을 막는다) · 3 = 나머지. 구획 안에서 flip_n 내림차순",
    "# 5) thr_name · thr_dist_m = 가장 가까운 문턱과 그 거리(m). CLEAR_M=7.0 · TRUCK=3.0 · SPREAD_MAX(wmax/2.5 선까지 wmin 이 움직일 거리) · CCTV=19.0(cctv_dist_m). 원인의 증명이 아니라 어디를 볼지의 단서다",
    "# 6) 구간의 키는 seg_uid 다(Zm27 · DECISIONS §572). seg_id 는 재발행하면 뒤가 밀리는 순번이라 옆에 둘 뿐이다. evalset_2610.csv 와 맞출 때도 seg_uid 로 맞춘다",
    "# 7) 위경도 = 구간 중점(WGS84 · 소수 6자리 · 「위도, 경도」). w_full_m 이하 칸은 사람이 채운다. 측정 규약은 evalset_2610.csv 머리 1)~4) 와 같다",
)


def _mids() -> dict[str, tuple[float, float]]:
    """구간 **중점**(길이의 절반 지점) — 공개본 지오메트리에서. 도 단위 선을 미터 척도로 보정해 잰다."""
    out = {}
    for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]:
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        line = max(parts, key=lambda c: sum(math.dist(a, b) for a, b in zip(c, c[1:], strict=False)))
        k = math.cos(math.radians(line[0][1]))
        seg = [math.hypot((b[0] - a[0]) * k, b[1] - a[1]) for a, b in zip(line, line[1:], strict=False)]
        half, acc = sum(seg) / 2, 0.0
        for a, b, d in zip(line, line[1:], seg, strict=False):
            if acc + d >= half and d > 0:
                t = (half - acc) / d
                out[f["properties"]["seg_id"]] = (a[1] + t * (b[1] - a[1]), a[0] + t * (b[0] - a[0]))
                break
            acc += d
        else:
            out[f["properties"]["seg_id"]] = (line[-1][1], line[-1][0])
    return out


def thresholds(p: dict) -> dict[str, float]:
    """문턱 넷까지의 거리(m). 이 구간에서 **살아 있는** 문턱만 든다.

    CLEAR_M   wmin · wmin_any · clear_med 중 7.0 에 가장 가까운 것(규칙 [2] · [8]~[10] 이 읽는 폭들)
    TRUCK     wmax · wmin · wmin_any · wsym · 대장폭 중 3.0 에 가장 가까운 것
    SPREAD_MAX  wmax 와 wmin 이 있고 wmin ≥ 7.0 일 때만. 비 2.5 선은 길이가 아니라 비라서, wmin 이 `wmax/2.5` 까지 움직일 거리로 바꾼다
    CCTV      |cctv_dist_m − 19.0| (폭 오차가 행선을 갈라 놓는 자리다. 폭 자체는 이 문턱에 안 걸린다)
    """
    def near(cols: tuple[str, ...], t: float) -> float | None:
        ds = [abs(p[c] - t) for c in cols if p.get(c) is not None]
        return min(ds) if ds else None
    out = {"CLEAR_M": near(("width_min_m", "width_min_any_m", "clear_med_m"), BASE_CLEAR),
           "TRUCK": near(("width_max_m", "width_min_m", "width_min_any_m", "width_min_sym_m", "road_bt_m"), BASE_TRUCK),
           "CCTV": abs(p["cctv_dist_m"] - C.CCTV_RANGE) if p.get("cctv_dist_m") is not None else None}
    if (p.get("width_max_m") is not None and p.get("width_min_m") is not None
            and p["width_min_m"] >= BASE_CLEAR and p["n_sample"] > 1):
        out["SPREAD_MAX"] = abs(p["width_min_m"] - p["width_max_m"] / SPREAD_MAX)
    return {k: v for k, v in out.items() if v is not None}


def _uids(path: Path) -> set[str]:
    """표가 가리키는 구간의 `seg_uid` 집합. seg_id 로 맞추지 않는다 — 번호는 재발행하면 밀린다(DECISIONS §571 · §572)."""
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["seg_uid"] for r in csv.DictReader(line for line in fh if not line.startswith("#"))}


def _write_csv(path: Path, recs: list[dict], rows: list[dict], mids: dict, head: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(head) + "\n")
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(CSV_COLS)
        for r in recs:
            p = rows[r["_j"]]
            lat, lon = mids.get(p["seg_id"], (None, None))
            w.writerow([p["seg_id"], p.get("seg_uid") or "", "" if lat is None else f"{lat:.6f}", "" if lon is None else f"{lon:.6f}",
                        p.get("road_name") or "", p["length_m"], r["tier"], r["orig_verdict"], r["flip_n"],
                        r["flip_to"], r["flip_to_pct"], r["thr_name"],
                        "" if r["thr_dist_m"] is None else f"{r['thr_dist_m']:.2f}",
                        "Y" if r["in_evalset"] else "", "", "", "", "", ""])


def flip_list(rows: list[dict], base_v: list[str], flips: np.ndarray, dest: np.ndarray) -> dict:
    n_boot = flips.shape[0]
    fn = flips.sum(0)
    mids = _mids()
    evalset = _uids(EVALSET)
    recs = []
    for j, p in enumerate(rows):
        if fn[j] == 0:
            continue
        d = np.bincount(dest[flips[:, j], j], minlength=len(ORDER))
        top = int(d.argmax())
        th = thresholds(p)
        name = min(th, key=th.get) if th else ""
        recs.append({
            "seg_id": p["seg_id"], "seg_uid": p.get("seg_uid"), "orig_verdict": base_v[j], "flip_n": int(fn[j]),
            "flip_to": ORDER[top], "flip_to_pct": round(100 * int(d[top]) / int(fn[j]), 1),
            "flip_to_counts": {ORDER[i]: int(c) for i, c in enumerate(d) if c},
            "tier": 1 if base_v[j] == "clear" else 2 if base_v[j] == "blocked" else 3,
            "thr_name": name, "thr_dist_m": round(th[name], 2) if name else None,
            "thr_all_m": {k: round(v, 2) for k, v in th.items()},
            "in_evalset": p.get("seg_uid") in evalset, "_j": j,
        })
    recs.sort(key=lambda r: (r["tier"], -r["flip_n"], r["seg_id"]))

    top_n = math.ceil(0.5 * n_boot)
    top = [r for r in recs if r["flip_n"] >= top_n]
    _write_csv(FLIP_CSV, recs, rows, mids, CSV_HEAD)
    _write_csv(FLIP_TOP_CSV, top, rows, mids, (
        f"# 사람이 잴 표 — flip_n ≥ {top_n}(부트스트랩 {n_boot:,}회 중 50% 이상)인 {len(top)}구간 (Zm26 · DECISIONS §571). 1,169행 전체 표는 flip_2610.csv",
        *CSV_HEAD[1:]))

    all_ids = [p["seg_id"] for p in rows]
    cuts = {"≥1회": 1, "≥5%": math.ceil(0.05 * n_boot), "≥50%": math.ceil(0.5 * n_boot)}
    sets = {k: {r["seg_id"] for r in recs if r["flip_n"] >= c} for k, c in cuts.items()}

    import rule12_sim
    r12 = {p["seg_id"] for p, (_, why) in zip(rows, rule12_sim.apply(rows), strict=True) if why == rule12_sim.REASON}
    contra = set(json.loads(LEDGER_CROSS.read_text(encoding="utf-8"))["median_basis"]["contradiction_ids"])
    # ★ 평가셋 55 중 34 는 공개본(어느 판이든)에 없는 seg_id 다. 못 찾는 것을 0 으로 세지 않고 따로 적는다.
    ev = {p["seg_id"] for p in rows if p.get("seg_uid") in evalset}        # 평가셋은 seg_uid 로 맞춘다
    missing_ev = sorted(evalset - {p.get("seg_uid") for p in rows})
    stray = (r12 | contra) - set(all_ids)
    if stray:
        raise SystemExit(f"★ 공개본에 없는 seg_id: {sorted(stray)[:5]}")

    def cover(group: set[str]) -> dict:
        return {"n": len(group), **{k: len(group & v) for k, v in sets.items()}}
    overlap = {"평가셋(공개본에서 찾은 것)": cover(ev), "평가셋 중 공개본에 없는 seg_uid": len(missing_ev), "규칙[12]": cover(r12), "모순군(중앙값 |d|≥5)": cover(contra),
               "전체(기저율)": {"n": len(all_ids), **{k: len(v) for k, v in sets.items()}},
               "세 집합 교집합": cover(ev & r12 & contra), "평가셋∩[12]": cover(ev & r12),
               "평가셋∩모순군": cover(ev & contra), "[12]∩모순군": cover(r12 & contra)}

    tier_n = {t: sum(1 for r in recs if r["tier"] == t) for t in (1, 2, 3)}
    thr = {t: {k: sum(1 for r in recs if r["tier"] == t and r["thr_name"] == k) for k in ("CLEAR_M", "TRUCK", "SPREAD_MAX", "CCTV")}
           for t in (1, 2, 3)}
    by_to = {t: {k: sum(1 for r in recs if r["tier"] == t and r["flip_to"] == k) for k in ORDER} for t in (1, 2, 3)}
    detail = {
        "n_boot": n_boot, "모형": "+d · 폭 다섯 열 · 구간 간 독립", "시드": SEED,
        "한 번이라도 뒤집힌 구간": len(recs), "전체": len(rows),
        "빈도 구획": {k: len(v) for k, v in sets.items()},
        "회차별 뒤집힘 중앙": float(np.median(flips.sum(1))),
        "상위표": {"기준": f"flip_n ≥ {top_n}", "n": len(top),
                 "tier": {t: sum(1 for r in top if r["tier"] == t) for t in (1, 2, 3)},
                 "행선": {t: {k: sum(1 for r in top if r["tier"] == t and r["flip_to"] == k) for k in ORDER} for t in (1, 2, 3)},
                 "최단 문턱": {t: {k: sum(1 for r in top if r["tier"] == t and r["thr_name"] == k)
                               for k in ("CLEAR_M", "TRUCK", "SPREAD_MAX", "CCTV")} for t in (1, 2, 3)},
                 "평가셋과 겹침": sorted(r["seg_id"] for r in top if r["in_evalset"])},
        "tier": tier_n, "tier별 최단 문턱": thr, "tier별 행선": by_to, "겹침": overlap,
        "구간": [{k: v for k, v in r.items() if k != "_j"} for r in recs],
    }
    FLIP_JSON.write_text(json.dumps(detail, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return detail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()

    seg_before = sha(SEG)
    rows = load()
    base_v = verdicts(rows)
    pub = [p["verdict"] for p in rows]
    if base_v != pub:
        bad = sum(x != y for x, y in zip(base_v, pub, strict=True))
        raise SystemExit(f"★ 재현이 깨졌다 — {bad}/{len(rows)} 건이 공개본과 다르다. 못 쟀다.")
    errs = survey_errors()
    base = counts(base_v)
    print(f"재현 {len(rows)}/{len(rows)} · 판정 {base}")

    res: dict = {"n": len(rows), "기준 판정": base, "오차": {
        "n": len(errs), **{k: round(float(v), 3) for k, v in zip(("q25", "median", "q75"), np.percentile(errs, [25, 50, 75]), strict=True)},
        "min": round(min(errs), 2), "max": round(max(errs), 2)}, "시드": SEED, "boot": a.boot}
    res["1_문턱근처"] = near_threshold(rows, base_v)
    res["2_CLEAR_M곡선"] = clear_curve(rows)
    res["3_상수민감도"] = const_sens(rows, base_v)

    boots = {}
    for label, sign, ow in (("+d · 폭 다섯 열", 1.0, False), ("−d · 폭 다섯 열", -1.0, False),
                            ("+d · wmin 만", 1.0, True)):
        m, dest = bootstrap(rows, base_v, errs, a.boot, sign=sign, only_wmin=ow)
        boots[label] = {"뒤집힌 구간 수": _ci(m.sum(1)),
                        "한 번이라도 뒤집힘": int(m.any(0).sum()),
                        "5% 이상 반복에서 뒤집힘": int((m.mean(0) >= 0.05).sum()),
                        "50% 이상": int((m.mean(0) >= 0.5).sum())}
        if label.startswith("+d · 폭"):
            main_m, main_dest = m, dest
    res["4_오차주입"] = {"모형": boots, "행선(+d · 폭 다섯 열, 반복당 평균 구간 수)": transitions(rows, base_v, errs)}
    res["5_띠제외_평가"] = band_exclusion(rows, base_v, main_m)
    detail = flip_list(rows, base_v, main_m, main_dest)

    seg_after = sha(SEG)
    res["segments.geojson"] = {"sha256": seg_after, "바이트 동일(실행 전후)": seg_before == seg_after}
    if seg_before != seg_after:
        raise SystemExit("★ segments.geojson 이 바뀌었다")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    flips = boots["+d · 폭 다섯 열"]["뒤집힌 구간 수"]
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in detail.items() if k != "구간"}, ensure_ascii=False, indent=1))
    print(f"\n폭 오차 때문에 판정이 틀릴 수 있는 구간은 {len(rows):,} 중 {flips['중앙']:.0f}개 "
          f"(부트스트랩 {a.boot:,}회 중앙 · 95% {flips['95%'][0]:.0f}~{flips['95%'][1]:.0f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

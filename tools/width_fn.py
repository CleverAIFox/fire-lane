#!/usr/bin/env python3
"""
tools/width_fn.py — 폭을 함수 w(s) 로 다룬다

    uv run python tools/width_fn.py             전체 비교표
    uv run python tools/width_fn.py --seg UID   한 구간의 w(s) 를 그대로 본다
    uv run python tools/width_fn.py --car 8.0   차 길이를 바꿔 본다
    uv run python tools/width_fn.py --aggregators   집계 함수 넷을 판정 넷·측량폭에 댄 표 (PLAN #17)

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다. 읽고 표를 낸다.
  `clearance_probe.py` · `jijeok_probe.py` 와 같은 성격이다.

── 왜 만들었나 ─────────────────────────────────────────────────
`width.py` 는 표본을 만들고 **`min` 만 뽑아 버렸다.** 그래서 폭을
함수로 다룰 수가 없었다.

**`min` 은 최악의 통계량이다.** 표본 하나가 틀리면 판정이 뒤집힌다.

    DM02647 구성로238번길   wmin 10.51m · 커버율 0.056
    DM02916 필문대로289번길  wmin 27.46m · 커버율 0.231

둘 다 `min` 이 이상치를 집은 것이고, 파이프라인이 커버율로 이미 지목하고
있었다. **커버율이 낮다는 건 표본이 적다는 뜻이고, 표본이 적으면 `min` 이
가장 먼저 무너진다.**

── 세 가지 통계량 ──────────────────────────────────────────────
    wmin        min{w(s)}                   지금 쓰는 것
    blocked_m   μ{s : w(s) < TRUCK}         3m 미만인 **길이**
    opening     차 길이만큼 연속으로 이어지는 폭

**`opening` 이 물리적으로 맞는 정의다.** 소방펌프차가 8m 인데 병목이
0.5m 길이면 그건 표본 노이즈일 가능성이 크다. 12m 길이면 확실히 못 간다.

형태학적으로는 **열림(opening)** 이고, 지금 `wmin` 은 `L_car = 0` 인
특수 경우다. 그것은 물리적으로 틀렸다.

★ 곡선은 상관없다. `s` 는 이미 중심선을 따라가는 호길이 매개변수라
  직선이든 곡선이든 같은 식이다.

── 아직 판정에 안 쓴다 ─────────────────────────────────────────
`wmin` 과 `opening` 이 얼마나 다른지 먼저 본다. 크게 다르면 그 구간들이
D-25 실측 1순위이고, 거의 같으면 `min` 을 계속 써도 된다.

**측정하고 대조한 뒤에 바꾼다.** 이 저장소가 08-22 clearance 를 `n=7` 로
기각했다가 08-23 에 근거를 다시 쓴 것이 그 교훈이다.

IN    data/processed/width_samples.csv   (segments 단계 산출)
      web/data/segments.geojson
      data/processed/segments_5186.gpkg · ngii1k_center_5186.gpkg   (--aggregators 만)
OUT   없음. --save 를 주면 data/processed/width_fn.csv
════════════════════════════════════════════════════════════════
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict

from firelane.console import col
from firelane.paths import PROCESSED, WEB
from firelane.seg.params import TRUCK

CAR_L = 8.0          # 소방펌프차 길이(m). 전장 7~9m 이고 8m 를 기준으로 둔다
STEP = 2.0           # width.py 의 표본 간격. 표본 사이는 선형으로 본다



def load() -> dict[str, list[tuple[float, float]]]:
    """seg_uid → [(s, w)] · 결측은 뺀다."""
    src = PROCESSED / "width_samples.csv"
    if not src.exists():
        print(col(f"{src} 가 없다.", "r"))
        print("  uv run fire-lane --from segments 를 먼저 돌려라.")
        raise SystemExit(1)
    d: dict[str, list[tuple[float, float]]] = defaultdict(list)
    with src.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["w_m"]:
                d[r["seg_uid"]].append((float(r["s_m"]), float(r["w_m"])))
    for v in d.values():
        v.sort()
    return dict(d)


def blocked_len(pts: list[tuple[float, float]], th: float) -> float:
    """w(s) < th 인 구간의 총 길이.

    ★ 표본 사이는 선형 보간한다. 2m 간격이라 그 안에서 폭이 크게 뛰지
      않는다는 가정이고, 그것이 트랜섹트 방식의 원래 전제다.
    """
    if len(pts) < 2:
        return STEP if (pts and pts[0][1] < th) else 0.0
    tot = 0.0
    for (s0, w0), (s1, w1) in zip(pts, pts[1:], strict=False):
        d = s1 - s0
        if d <= 0:
            continue
        b0, b1 = w0 < th, w1 < th
        if b0 and b1:
            tot += d
        elif b0 or b1:
            # 선형 보간으로 임계를 지나는 지점을 찾는다
            f = (th - w0) / (w1 - w0) if w1 != w0 else 0.5
            tot += d * (f if b0 else 1 - f)
    return tot


def opening(pts: list[tuple[float, float]], car: float) -> float | None:
    """구간을 **통과**할 수 있는 폭.

    ★ 2026-08-23. 처음에 "차 길이만큼 연속으로 이어지는 폭" 으로 짰다가
      되돌렸다. 그것은 **주차 가능 여부**지 통과가 아니다.

      합성 표본으로 걸렸다 — 40m 구간 가운데 12m 가 2m 로 막혔는데
      `opening` 이 5.0 을 줬다. 양쪽 14m 씩이 5m 로 넓어 "8m 차가 들어갈
      자리가 있다" 는 이유였다. **들어갈 수 있다와 통과한다는 다르다.**

    ── 맞는 정의 ────────────────────────────────────────────────
    구간 전체를 지나가야 하므로 병목이 하나라도 있으면 못 간다.
    다만 **병목이 차보다 짧으면** 넘어갈 수 있다 — 앞바퀴가 나가는 동안
    뒷바퀴가 아직 넓은 데 있으면 차체가 통과한다.

        통과폭 = max{ c : w(s) < c 인 모든 구간의 길이가 car 미만 }

    `car = 0` 이면 `wmin` 과 같아진다. 지금 판정이 그 특수 경우다.

    ★ 이것도 근사다. 실제로는 차체 형상과 회전이 들어가고, 짧은 병목이라도
      폭이 차폭(2.5m)보다 좁으면 물리적으로 못 지나간다. 그 하한은
      호출부에서 걸러야 한다.
    """
    if not pts:
        return None
    span = pts[-1][0] - pts[0][0]

    # ★ 2026-08-23 두 번째 정정. 구간이 차보다 짧으면 **병목이 car 를 넘을
    #   수가 없다.** 그래서 모든 후보가 통과로 판정되고 최댓값이 나왔다 —
    #   길이 5.8m 구간에서 `opening 49.30m` 가 그렇게 나왔다.
    #   49m 짜리 골목은 없다.
    #
    #   물리적으로도 맞지 않는다. 5.8m 구간은 그것만으로 통과 여부를 못
    #   정한다 — 차가 구간보다 길면 이웃까지 이어 봐야 한다.
    #   **낙관적으로 틀리느니 wmin 을 쓴다.** 보수적인 쪽이 안전하다.
    if span < car:
        return min(w for _, w in pts)

    # ★ 표본이 적으면 병목 **길이**를 잴 수 없다. 표본 간격이 2m 이므로
    #   4개는 있어야 그 사이를 논할 수 있다. 그 아래는 `min` 과 다를 게 없다.
    if len(pts) < 4:
        return min(w for _, w in pts)

    ws = sorted({w for _, w in pts}, reverse=True)
    for c in ws:
        # w(s) < c 인 구간들의 길이를 재서 가장 긴 것이 car 미만이면 통과
        worst, run = 0.0, 0.0
        for (s0, w0), (s1, w1) in zip(pts, pts[1:], strict=False):
            d = s1 - s0
            if w0 < c and w1 < c:
                run += d
            elif w0 < c or w1 < c:
                f = (c - w0) / (w1 - w0) if w1 != w0 else 0.5
                run += d * (f if w0 < c else 1 - f)
                worst = max(worst, run)
                run = 0.0
            else:
                worst = max(worst, run)
                run = 0.0
        worst = max(worst, run)
        if worst < car:
            return c
    return min(ws)


def cmd_one(uid: str, car: float) -> int:
    d = load()
    pts = d.get(uid)
    if not pts:
        print(col(f"{uid} 표본이 없다", "r"))
        return 1
    print(f"{uid} · 표본 {len(pts)}개 · 길이 {pts[-1][0]-pts[0][0]:.1f}m\n")
    for s, w in pts:
        bar = "█" * int(min(w, 20) * 2)
        mark = col(" ★", "r") if w < TRUCK else ""
        print(f"  s={s:6.1f}  w={w:6.2f}  {bar}{mark}")
    print(f"\n  wmin      {min(w for _, w in pts):6.2f}")
    print(f"  opening   {opening(pts, car):6.2f}  (차 {car}m)")
    print(f"  막힌 길이  {blocked_len(pts, TRUCK):6.2f} m")
    return 0


def cmd_aggregators() -> int:
    """`min` · 5퍼센타일 · 연속 N m 의 min 을 같은 표본에 대어 표를 낸다. **판정에 반영하지 않는다.**

    ★ 재기 전에 재현부터 증명한다(`verdictsim` 과 같은 규율). `classify()` 가 산출물의 판정을
      전 행 다시 못 내거나 `min` 행이 산출물의 판정 넷 수와 다르면 **아무 표도 안 낸다.**
    ★ 집계는 표본이 산출물의 `width_min_m` 을 재현하는 구간(표본의 min 을 소수 둘로 반올림한 값이
      같은 구간)에만 바꿔 넣는다. 나머지는 폭이 다른 원천·병합 경로에서 와서 표본으로 재현이 안 되므로
      산출물 폭 그대로 두고 그 수를 찍는다.
    ★ 「측량폭에 가깝다」는 이 표에서 **옳다는 뜻이 아니다.** 측량 `도로폭` 은 명목폭이라 최솟값보다
      큰 쪽으로 집계할수록 가까워지게 되어 있다. 같은 표의 「새로 clear」 칸이 그 반대 방향을 잰다.
    """
    import math
    import statistics

    import geopandas as gpd
    import numpy as np
    import widthcross

    from firelane.seg.classify import classify

    def nz(v):
        return None if v is None or (isinstance(v, float) and math.isnan(v)) else v

    def cls(r, w):
        # ★ 감사 N4 (Zm20). 판정 입력을 **전부** 넘긴다 — 바꿔 보는 것은 폭 집계 `w` 하나뿐이고 규칙 [8]~[11] 의
        #   입력은 산출물 그대로다. 안 넘기면 Zm19 이후 재현이 깨져 표가 안 나온다.
        ns = nz(r.n_sample)
        return classify(wmin=w, wmax=nz(r.width_max_m), nreg=None if ns is None else int(ns),
                        road_bt=nz(r.road_bt_m), length_m=r.length_m, cctv_dist=r.cctv_dist_m,
                        wmin_any=nz(r.width_min_any_m), wsym=nz(r.width_min_sym_m),
                        clear_med=nz(r.clear_med_m))[0]

    rows = widthcross._load()
    if rows is None:
        print(col("segments_5186.gpkg 가 없다 — 못 쟀다", "r"))
        return 1
    surv = {r["seg_uid"]: widthcross._num(r["survey"]) for r in rows}
    P = {r.seg_uid: r for r in gpd.read_file(PROCESSED / "segments_5186.gpkg").itertuples()}
    S = load()
    pub = {u: r.verdict for u, r in P.items()}

    bad = [u for u, r in P.items() if cls(r, nz(r.width_min_m)) != pub[u]]
    if bad:
        print(col(f"재현이 깨졌다 — {len(bad)}/{len(P)} 건이 산출물과 다르다. 이 상태의 표는 표가 아니다.", "r"))
        return 1
    ok = {u for u in P if u in S and S[u] and nz(P[u].width_min_m) is not None
          and round(min(w for _, w in S[u]), 2) == round(P[u].width_min_m, 2)}

    aggs = {
        "min": lambda p: min(w for _, w in p),
        "하위 5퍼센타일": lambda p: float(np.percentile([w for _, w in p], 5)),
        "연속 4m 의 min": lambda p: opening(p, 4.0),
        "연속 8m 의 min": lambda p: opening(p, 8.0),
        # ★ PLAN #4. 아래 넷은 「ngii 도로폭은 어떤 대푯값인가」를 가르는 후보다 — 판정 표에도 같이 낸다.
        "평균": lambda p: float(np.mean([w for _, w in p])),
        "중앙": lambda p: float(np.median([w for _, w in p])),
        "p75": lambda p: float(np.percentile([w for _, w in p], 75)),
        "max": lambda p: max(w for _, w in p),
    }
    clear_m = widthcross.CLEAR_M
    print(f"구간 {len(P)} · 집계를 바꿔 넣은 구간 {len(ok)} · 산출물 폭 그대로 {len(P) - len(ok)}"
          f" · 측량폭 짝(바꿔 넣은 구간 안) {sum(1 for u in ok if surv.get(u) is not None)}\n")
    print(f"{'집계':16}{'절대편차 중앙':>13}{'clear':>7}{'needs_cv':>9}{'blocked':>8}{'unknown':>8}"
          f"{'뒤집힘':>7}{'새 clear':>9}{'그중 대장<' + str(clear_m):>12}")
    for name, f in aggs.items():
        W = {u: (round(f(S[u]), 2) if u in ok else nz(P[u].width_min_m)) for u in P}
        V = {u: cls(P[u], W[u]) for u in P}
        cnt = {k: sum(1 for v in V.values() if v == k) for k in ("clear", "needs_cv", "blocked", "unknown")}
        if name == "min" and (cnt != {k: sum(1 for v in pub.values() if v == k) for k in cnt}):
            print(col("`min` 행이 산출물의 판정 수와 다르다 — 측정기가 틀렸다.", "r"))
            return 1
        dev = [abs(W[u] - surv[u]) for u in ok if surv.get(u) is not None]
        flips = sum(1 for u in P if V[u] != pub[u])
        up = [u for u in P if V[u] == "clear" and pub[u] != "clear"]
        soft = sum(1 for u in up if nz(P[u].road_bt_m) is not None and P[u].road_bt_m < clear_m)
        print(f"{name:16}{statistics.median(dev):>11.2f}m{cnt['clear']:>7}{cnt['needs_cv']:>9}"
              f"{cnt['blocked']:>8}{cnt['unknown']:>8}{flips:>7}{len(up):>9}{soft:>12}")
    print(col("\n★ 판정에 반영하지 않았다. 함수를 바꾸면 재잠금이고 그것은 사람이 고른다.", "d"))
    return _residual_panel(aggs, ok, S, P, surv)


def _rank(a):
    """평균 순위(동순위는 평균). scipy 없이 센다."""
    import numpy as np
    a = np.asarray(a, float)
    o = np.argsort(a, kind="mergesort")
    r = np.empty(len(a))
    sa = a[o]
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and sa[j + 1] == sa[i]:
            j += 1
        r[o[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return r


def _spearman(a, b):
    import numpy as np
    ra, rb = _rank(a), _rank(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def _wilcoxon_p(res):
    """부호순위 검정의 양측 p (정규근사 · 동순위 보정 · 0 은 뺀다)."""
    import math

    import numpy as np
    d = np.asarray([x for x in res if x != 0.0], float)
    n = len(d)
    if n < 10:
        return float("nan")
    r = _rank(np.abs(d))
    w = float(r[d > 0].sum())
    mu = n * (n + 1) / 4
    _, cnt = np.unique(np.abs(d), return_counts=True)
    var = n * (n + 1) * (2 * n + 1) / 24 - float((cnt ** 3 - cnt).sum()) / 48
    z = (w - mu) / math.sqrt(var)
    return math.erfc(abs(z) / math.sqrt(2))


def _residual_panel(aggs, ok, S, P, surv) -> int:
    """PLAN #4 — 측량 `도로폭` 이 우리 표본의 **어떤 대푯값**인지 역추정한다. 아무것도 안 쓴다.

    H0: ngii = T(우리 표본). 잔차 = 측량폭 − T(표본).
      ① 잔차 중앙이 0 인가 — Wilcoxon 부호순위
      ② 잔차 산포(MAD)가 최소인 T
      ③ 잔차가 구간 특성과 무상관인가 — 표본 수 · 곡률(굽이도) · 도로위계(도로명 끝글자)와의 스피어만 ρ
         ★ 핵심은 ③ 이다. 맞는 T 는 잔차에 구조가 안 남는다.
    ★ 집계를 바꿔 넣은 구간과 측량 짝이 둘 다 있는 구간에만 잰다. 판정 표와 같은 집합이다.
    """
    import numpy as np

    uids = [u for u in ok if surv.get(u) is not None]
    if len(uids) < 30:
        print(col("측량 짝이 너무 적어 잔차를 못 쟀다", "r"))
        return 1
    def hier(name):
        """도로명 끝글자로 위계를 센다 — 대로 3 · 로 2 · 길/번길 1 · 이름 없음 0."""
        n = (name or "").strip()
        if n.endswith("대로"):
            return 3
        if n.endswith("길"):
            return 1
        return 2 if n.endswith("로") else 0
    nsamp = np.asarray([len(S[u]) for u in uids], float)
    sinu = np.asarray([P[u].geometry.length / max(_chord(P[u].geometry), 1e-9) for u in uids], float)
    hv = np.asarray([hier(P[u].road_name) for u in uids], float)
    sv = np.asarray([surv[u] for u in uids], float)
    print(f"\n{col('잔차 = 측량폭 − T(표본)', 'c')}  구간 {len(uids)}  (PLAN #4 · 대푯값 역추정)")
    print(f"{'T':16}{'잔차 중앙':>9}{'Wilcoxon p':>12}{'MAD':>7}{'ρ(표본수)':>10}{'ρ(굽이도)':>10}{'ρ(위계)':>9}")
    for name, f in aggs.items():
        if name.startswith("연속"):
            continue
        T = np.asarray([f(S[u]) for u in uids], float)
        res = sv - T
        mad = float(np.median(np.abs(res - np.median(res))))
        print(f"{name:16}{np.median(res):>8.2f}m{_wilcoxon_p(res):>12.3g}{mad:>7.2f}"
              f"{_spearman(res, nsamp):>10.2f}{_spearman(res, sinu):>10.2f}{_spearman(res, hv):>9.2f}")
    print(col("★ 아무것도 안 썼다. 집계는 `min` 을 유지한다.", "d"))
    return 0


def _chord(g):
    from shapely.geometry import Point
    c = list(g.coords) if g.geom_type == "LineString" else list(g.geoms[0].coords)
    return Point(c[0]).distance(Point(c[-1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", help="한 구간만 본다")
    ap.add_argument("--car", type=float, default=CAR_L, help="차 길이(m)")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--aggregators", action="store_true", help="집계 함수 대조표 (PLAN #17)")
    a = ap.parse_args()
    if a.aggregators:
        return cmd_aggregators()
    if a.seg:
        return cmd_one(a.seg, a.car)

    d = load()
    seg = {f["properties"]["seg_uid"]: f["properties"]
           for f in json.loads((WEB / "segments.geojson").read_text(encoding="utf-8"))["features"]}
    print(f"표본이 있는 구간 {len(d):,} / 산출 {len(seg):,}\n")

    rows = []
    for uid, pts in d.items():
        p = seg.get(uid)
        if not p or p.get("width_min_m") is None:
            continue
        wm = float(p["width_min_m"])
        op = opening(pts, a.car)
        rows.append({
            "seg_uid": uid, "label": p.get("seg_label") or p.get("road_name") or "",
            "verdict": p["verdict"], "wmin": wm, "opening": op,
            "blocked_m": blocked_len(pts, TRUCK),
            "len": float(p["length_m"]), "n": len(pts),
            "cov": p.get("width_cov"),
        })

    if not rows:
        print(col("대조할 구간이 없다", "r"))
        return 1

    diff = [r for r in rows if abs(r["opening"] - r["wmin"]) > 0.5]
    flip = [r for r in rows if (r["wmin"] < TRUCK) != (r["opening"] < TRUCK)]

    print(f"{col('① min 과 opening 의 차이', 'c')}  (차 {a.car}m 기준)")
    print(f"   0.5m 초과로 다른 구간   {len(diff):4} / {len(rows)}")
    print(f"   {TRUCK}m 임계가 갈리는 구간  {col(str(len(flip)), 'y'):>4} / {len(rows)}")

    print(f"\n{col('② 임계가 갈리는 구간', 'c')} — min 이 이상치를 집은 곳")
    cols = f"   {'라벨':22}{'판정':10}{'wmin':>7}{'open':>7}{'막힘m':>7}{'길이':>7}{'표본':>5}"
    print(cols)
    for r in sorted(flip, key=lambda r: -abs(r["opening"] - r["wmin"]))[:14]:
        print(f"   {str(r['label'])[:20]:22}{r['verdict']:10}"
              f"{r['wmin']:>7.2f}{r['opening']:>7.2f}"
              f"{r['blocked_m']:>7.1f}{r['len']:>7.1f}{r['n']:>5}")

    print(f"\n{col('③ 막힌 길이가 짧은데 blocked 인 곳', 'c')} — 병목이 노이즈일 수 있다")
    noise = [r for r in rows if r["wmin"] < TRUCK and r["blocked_m"] < 2.0]
    print(f"   {len(noise)}구간 (3m 미만이 2m 미만만 이어진다)")
    for r in sorted(noise, key=lambda r: r["blocked_m"])[:10]:
        print(f"   {str(r['label'])[:20]:22}{r['verdict']:10}"
              f"{r['wmin']:>7.2f}{r['opening']:>7.2f}"
              f"{r['blocked_m']:>7.2f}{r['len']:>7.1f}{r['n']:>5}")

    if a.save:
        dst = PROCESSED / "width_fn.csv"
        with dst.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\n{col('→', 'g')} {dst}")

    print(col("\n★ 판정에 반영하지 않았다. 먼저 대조하고 실측으로 정한다.", "d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

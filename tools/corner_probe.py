#!/usr/bin/env python3
"""
corner_probe.py — 코너 기하를 재고 차량 회전 가능성과 대조한다. 아무것도 안 바꾼다.

    uv run python tools/corner_probe.py
    uv run python tools/corner_probe.py --csv        data/interim 에 표를 남긴다
    uv run python tools/corner_probe.py --radius 11.2  다른 회전반경으로

── 왜 필요한가 ─────────────────────────────────────────────────
`seg/vehicle.py` 는 내륜차를 정확식으로 계산한다(DECISIONS §50).

    Δ = R − √(R² − L²)        R = 회전반경 · L = 축거

그런데 **그 R 을 이 골목이 허용하는지를 아무도 재지 않았다.** 차량 쪽 계산만
있고 도로 쪽 기하가 없으니, 내륜차는 경로 비용에만 들어가고 판정에는 못 쓴다.
`D-08`(회전 반경·코너 판정)이 미결인 이유가 그것이다.

★ **도로 기하와 차량 기준은 분리된다.** 코너가 몇 도로 꺾이고 그 자리에 반경
  몇 m 원이 들어가는지는 **차량과 무관한 도로의 성질**이다. 지금 잴 수 있다.
  D-30 인터뷰가 막고 있는 것은 그 위에 얹을 **임계값**이지 측정이 아니다.

── 무엇을 재나 ─────────────────────────────────────────────────
1. 꺾임각 (deflection)   노드에서 두 구간이 이루는 각. 0°=직진, 90°=직각
                         새 데이터가 필요 없다. 중심선에서 나온다
2. 스윕 통과 판정        차량이 그 코너를 실제로 돌 수 있는가.
                         내륜차만이 아니라 **바깥 스윙**까지 본다
3. 교차부 크기           평면교차점 폴리곤(A0080000)의 최대내접원.
                         ★ 서술용이다. 회전 판정 기준이 아니다 — 아래 참조

★ 판정에 반영하지 않는다. 읽고 표를 낼 뿐이라 golden 지문에 영향이 없다.
  `width_fn` · `lanes_probe` · `jijeok_probe` 와 같은 성격이다(MASTER §14-5).

★ **여기서 나온 값을 그대로 상수에 박지 않는다.** 그러면 근거 없는 상수가
  하나 더 생긴다(MASTER §16-2). 분포를 보고 나서 필드로 승격할지 정한다.

★ 2026-08-25 정정. 첫 판은 **내륜차만** 보고 "필요폭 = 전폭 + 여유 + Δ" 로
  쟀다. Δ 는 R 이 커질수록 **작아지므로** 대형 물탱크차가 중형보다 유리하게
  나왔다 — 2026-08-24 인터뷰("물탱크차는 커서 진입이 불가능할 때가 있다")와
  정반대다. **모델이 틀렸다는 신호였다.**
  빠진 것은 바깥 스윙이다. R 이 커지면 차가 그리는 원이 커져서 더 넓은 코너가
  필요하다. 두 가장자리를 다 봐야 방향이 맞는다.

      Δ  = R − √(R² − L²)          내륜차. R 이 크면 작아진다
      Ro = R + W/2                 바깥 가장자리 궤적. R 이 크면 커진다
      Ri = R − W/2 − Δ − C         안쪽 가장자리 궤적
      통과 조건 — 안쪽 모서리가 Ri 안에 들어간다

  90° 코너 대칭 폭 기준 하한 — R 8.0m 5.59m · R 11.2m 6.29m. 방향이 맞다.

★ 최대내접원을 회전 가능성 판정에 쓰지 않는다. 3m 도로 둘이 만나면 그 폴리곤
  자체가 작아 반경 1.5m 가 나온다. **도로 폭을 다시 잰 것이지 회전이 아니다.**
  차량은 교차부 안에 원을 그려 넣는 것이 아니라 두 도로의 폭을 써서 스쳐 간다.

IN    data/processed/segments.geojson · (선택) processed/ngii1k_xsec_5186.gpkg
      sources.yaml 의 vehicle_spec
OUT   없음 (표). --csv 를 주면 data/interim/corner_probe.csv
PARAM DEG_STRAIGHT · SAMPLE_M
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml
from shapely.geometry import LineString

from firelane.paths import PROCESSED
from firelane.seg.params import NODE_TOL

ROOT = Path(__file__).resolve().parent.parent

CRS_M = "EPSG:5186"

# 이 각 이하는 직진으로 본다. 노딩 파편이 만드는 1~2° 흔들림을 코너로 세면
# 코너가 수천 개가 되어 분포가 무의미해진다.
DEG_STRAIGHT = 15.0

# 이 각 이상은 **코너가 아니라 나란함**이다. 꺾임 180° 는 두 바깥벡터가
# 같은 방향을 본다는 뜻 — 노드에서 두 팔이 겹쳐 나간다. 물리적 U턴이
# 아니라 기하 파편이다.
#
# ★ 2026-08-25. `지호로 × 지산로` 가 폭 11.7m · 9.2m 인데 32.65m 가
#   모자란다고 나왔다. 꺾임 176.7° 였다 — 바깥벡터가 3.3° 밖에 안 벌어졌다.
#   cos(Δ/2) 가 0 으로 가면서 필요폭이 Ro 전체로 밀려 올라간 것이다.
#
#   `_node_key` 가 격자 반올림이라(segments.py 는 union-find 다) 나란한
#   두 구간이 한 칸에 들어가면 이렇게 잡힌다.
#
# ★ 새 상수를 박지 않는다(§16-2). DEG_STRAIGHT 의 거울이다 —
#   "15° 미만은 직진 잡음" 이면 "165° 초과는 나란함 잡음" 이다.
#   같은 관용을 반대편에 쓴다.
DEG_PARALLEL = 180.0 - DEG_STRAIGHT

# 방향을 재는 구간 길이(m). 끝점 두 점만 쓰면 노딩 잡음에 각이 튄다.
SAMPLE_M = 5.0


def _dir_at_end(ls: LineString, at_start: bool) -> tuple[float, float]:
    """끝점에서 **바깥으로 나가는** 방향 단위벡터.

    ★ 끝의 두 좌표만 쓰지 않는다. 노딩이 만든 밀리미터 파편에서 각이 튄다.
      SAMPLE_M 만큼 들어간 지점과 끝점을 잇는다.
    """
    n = ls.length
    d = min(SAMPLE_M, n) if n > 0 else 0.0
    if at_start:
        p0, p1 = ls.interpolate(d), ls.interpolate(0.0)
    else:
        p0, p1 = ls.interpolate(max(n - d, 0.0)), ls.interpolate(n)
    vx, vy = p1.x - p0.x, p1.y - p0.y
    h = math.hypot(vx, vy)
    return (0.0, 0.0) if h == 0 else (vx / h, vy / h)


def _deflection(a: tuple[float, float], b: tuple[float, float]) -> float:
    """노드에서 두 구간의 **진행 방향 변화각**(도).

    a · b 는 둘 다 노드에서 바깥으로 나가는 벡터다. 한 구간으로 들어와
    다른 구간으로 나가려면 a 의 반대 방향으로 진입하므로, 꺾임각은
    두 바깥벡터가 이루는 각의 **보각**이다.

        두 벡터가 정반대(180°)  → 꺾임 0°   직진
        두 벡터가 직각(90°)     → 꺾임 90°  직각 코너
    """
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
    return 180.0 - math.degrees(math.acos(dot))


def _node_key(x: float, y: float) -> tuple[int, int]:
    """NODE_TOL 격자로 끝점을 묶는다. segments 노딩과 같은 관용."""
    return (round(x / NODE_TOL), round(y / NODE_TOL))


def _perp(v: tuple[float, float]) -> tuple[float, float]:
    return (-v[1], v[0])


def sweep_margin(u1: tuple[float, float], u2: tuple[float, float],
                 w1: float, w2: float,
                 R: float, L: float, W: float, C: float) -> float:
    """코너 여유(m). 음수면 통과, 양수면 그만큼 모자란다.

    ★ 내륜차만 보면 방향이 뒤집힌다. 바깥 스윙까지 봐야 한다.

        Ro = R + W/2                 바깥 가장자리 궤적
        Ri = R − W/2 − Δ − C         안쪽 가장자리 궤적
        O                            두 도로의 **바깥 가장자리**에 Ro 로 접하는 중심
        V                            두 도로의 **안쪽 가장자리**가 만나는 모서리
        통과 조건                     |O − V| ≤ Ri

    폭이 좌우로 다른 코너도 그대로 푼다. 대칭 근사를 쓰지 않는다 —
    3m 골목이 12m 대로로 나가는 코너가 실제로 많다.
    """
    if R <= L:
        return math.inf                      # 기하적으로 성립하지 않는다
    off = R - math.sqrt(R * R - L * L)
    ro, ri = R + W / 2, R - W / 2 - off - C
    if ri <= 0:
        return math.inf

    def _outward(ua, ub):
        n = _perp(ua)
        return (-n[0], -n[1]) if n[0] * ub[0] + n[1] * ub[1] > 0 else n

    n1, n2 = _outward(u1, u2), _outward(u2, u1)
    det = n1[0] * n2[1] - n1[1] * n2[0]
    if abs(det) < 1e-9:                      # 직진. 코너가 아니다
        return -math.inf

    def _solve(c1, c2):
        return ((c1 * n2[1] - c2 * n1[1]) / det,
                (n1[0] * c2 - n2[0] * c1) / det)

    vx, vy = _solve(-w1 / 2, -w2 / 2)        # 안쪽 모서리

    # ★ 회전 중심은 **바깥 가장자리에 붙어야 하는 것이 아니다.** 도로 안
    #   어디든 설 수 있고, 제약은 "바깥 궤적이 도로 밖으로 안 나간다" 뿐이다.
    #      dot(O, n_i) <= w_i/2 − Ro
    #   그래서 O 를 안쪽 모서리 V 에 최대한 붙인다. 넓은 도로는 V 자체가
    #   제약을 만족하므로 여유가 0 이다 — 넓을수록 쉬워야 맞는다.
    #   ★ 첫 판은 두 바깥선에 동시 접하도록 강제해서, 52m 대로가 39m 모자라는
    #     것으로 나왔다. 넓을수록 불리해지는 결과는 그 자체가 오류 신호다.
    c1, c2 = w1 / 2 - ro, w2 / 2 - ro
    cands = []
    if -w1 / 2 <= c1 + 1e-9 and -w2 / 2 <= c2 + 1e-9:
        cands.append((vx, vy))               # V 가 이미 가능. 여유 최대
    if -w2 / 2 <= c2 + 1e-9:                 # 1번만 활성
        t = c1 - (-w1 / 2)
        cands.append((vx + t * n1[0], vy + t * n1[1]))
    if -w1 / 2 <= c1 + 1e-9:                 # 2번만 활성
        t = c2 - (-w2 / 2)
        cands.append((vx + t * n2[0], vy + t * n2[1]))
    cands.append(_solve(c1, c2))             # 둘 다 활성

    best = math.inf
    for ox, oy in cands:
        if (ox * n1[0] + oy * n1[1] > c1 + 1e-6
                or ox * n2[0] + oy * n2[1] > c2 + 1e-6):
            continue                         # 바깥 궤적이 도로를 넘는다
        best = min(best, math.hypot(ox - vx, oy - vy))
    return best - ri


def corner_min_width(theta_deg: float, R: float, L: float,
                     W: float, C: float) -> float:
    """대칭 폭 코너에서 통과 가능한 최소 폭. 표를 내기 위한 해석해."""
    if R <= L:
        return math.inf
    off = R - math.sqrt(R * R - L * L)
    ro, ri = R + W / 2, R - W / 2 - off - C
    if ri <= 0:
        return math.inf
    return ro - ri * math.sin(math.radians(180.0 - theta_deg) / 2)


def load_vehicle() -> dict:
    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    v = y.get("vehicle_spec") or {}
    if not v:
        sys.exit("★ sources.yaml 에 vehicle_spec 이 없다. 기본값을 두지 않는다.")
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=None,
                    help="회전반경(m). 기본은 vehicle_spec")
    ap.add_argument("--csv", action="store_true", help="data/interim 에 표를 남긴다")
    a = ap.parse_args()

    seg_p = PROCESSED / "segments.geojson"
    if not seg_p.exists():
        sys.exit(f"★ {seg_p} 없음 — uv run fire-lane --from segments")

    V = load_vehicle()
    R = a.radius if a.radius is not None else float(V["turn_radius_m"])
    L = float(V["wheelbase_m"])
    W = float(V["width_m"])
    C = float(V["clearance_m"])
    # ★ 2026-08-25. 종전에는 `wheelbase_verified` 하나로 축거와 회전반경을
    #   **둘 다** 판단했다. 회전반경은 자동차규칙 제9조① 12m 로 근거가 생겼고
    #   대장이 `turn_radius_verified` 로 그것을 말한다. 둘을 갈라야 화면이
    #   사실을 말한다 — 지금 미확정인 것은 축거뿐이다.
    wb_ok = bool(V.get("wheelbase_verified"))
    tr_ok = bool(V.get("turn_radius_verified"))
    unsure = [n for n, ok in (("축거", wb_ok), ("회전반경", tr_ok)) if not ok]

    print(f"차량  전폭 {W} · 축거 {L} · 회전반경 {R}"
          + ("" if not unsure
             else f"   ★ {'·'.join(unsure)} 미확정. 참고값이지 판정이 아니다"))
    if tr_ok:
        print("      회전반경 근거 — 자동차규칙 제9조① 법정 상한(전 차종 공통)")
    print("      대칭 코너 통과 하한 폭 — "
          + " · ".join(f"{d}° {corner_min_width(d, R, L, W, C):.2f}m"
                       for d in (60, 90, 120)))
    print("      ★ 회전반경이 클수록 하한이 올라간다. 바깥 스윙이 지배한다\n")

    g = gpd.read_file(seg_p).to_crs(CRS_M)
    print(f"구간 {len(g):,} · 좌표계 {CRS_M}")

    # ── 1. 노드별 꺾임각 ──────────────────────────────────────
    ends: dict[tuple[int, int], list[tuple[int, tuple[float, float]]]] = defaultdict(list)
    for i, geom in enumerate(g.geometry):
        if geom is None or geom.is_empty:
            continue
        ls = geom if isinstance(geom, LineString) else max(geom.geoms, key=lambda q: q.length)
        for at_start in (True, False):
            pt = ls.interpolate(0.0 if at_start else ls.length)
            ends[_node_key(pt.x, pt.y)].append((i, _dir_at_end(ls, at_start)))

    # 구간별 최대 꺾임각 — 이 구간을 드나들 때 만나는 가장 급한 코너
    worst = [0.0] * len(g)
    turns: list[tuple[float, int, int]] = []
    parallel: list[tuple[float, int, int]] = []   # 나란함(노딩 파편). 진단용
    corners: list[tuple[float, int, int, tuple[float, float], tuple[float, float]]] = []
    for members in ends.values():
        if len(members) < 2:
            continue
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                i, va = members[x]
                j, vb = members[y]
                if i == j:                    # 자기 자신(루프)은 코너가 아니다
                    continue
                d = _deflection(va, vb)
                if d < DEG_STRAIGHT:
                    continue
                if d > DEG_PARALLEL:
                    # 코너가 아니라 겹친 기하다. 세되 판정에는 안 넣는다.
                    parallel.append((d, i, j))
                    continue
                turns.append((d, i, j))
                corners.append((d, i, j, va, vb))
                worst[i] = max(worst[i], d)
                worst[j] = max(worst[j], d)

    g["turn_deflection_deg"] = [round(v, 1) for v in worst]
    tdf = pd.Series([t[0] for t in turns])
    print(f"\n[꺾임각] 코너 {len(turns):,}개 (직진 {DEG_STRAIGHT}° 미만 제외)")
    if len(tdf):
        print(f"  중앙 {tdf.median():.0f}° · p75 {tdf.quantile(.75):.0f}° "
              f"· p90 {tdf.quantile(.90):.0f}° · 최대 {tdf.max():.0f}°")
        for lo, hi in ((15, 30), (30, 60), (60, 90), (90, 120), (120, 166)):
            n = int(((tdf >= lo) & (tdf < hi)).sum())
            print(f"  {lo:3d}~{hi:3d}°  {n:5,}  {'█' * min(40, n * 40 // max(1, len(tdf)))}")
    print(f"  꺾임 있는 구간 {sum(1 for v in worst if v >= DEG_STRAIGHT):,} / {len(g):,}")
    if parallel:
        print(f"  ★ 나란함 {len(parallel):,}개 제외 ({DEG_PARALLEL:.0f}° 초과) — "
              f"코너가 아니라 겹친 기하다")
        print("     노드 격자 반올림이 만든 것이다. segments.py 는 union-find 로")
        print("     묶는다 — 두 곳의 노딩 규칙이 다르다는 뜻이므로 점검 대상이다")

    # ── 2. 코너 반경 (평면교차점 폴리곤) ──────────────────────
    xsec_p = PROCESSED / "ngii1k_xsec_5186.gpkg"
    g["corner_radius_m"] = pd.NA
    if not xsec_p.exists():
        print(f"\n[코너 반경] {xsec_p.name} 없음 — 생략")
        print("  uv run fire-lane --only ingest 로 만들 수 있다")
    else:
        from shapely import maximum_inscribed_circle

        x = gpd.read_file(xsec_p).to_crs(CRS_M)
        x = x[x.geometry.notna() & ~x.geometry.is_empty]
        print(f"\n[교차부 크기] 평면교차점 폴리곤 {len(x):,}  ★ 서술용. 판정 기준이 아니다")
        tiny = int((x.geometry.area < 1.0).sum())
        if tiny:
            print(f"  ★ 면적 1m² 미만 파편 {tiny:,}개 — 한 교차로가 여러 조각이다")
        rad = []
        for geom in x.geometry:
            try:
                seg = maximum_inscribed_circle(geom)
                rad.append(seg.length)          # 중심 → 경계 거리 = 내접원 반경
            except Exception:                   # noqa: BLE001
                rad.append(float("nan"))
        x["r_m"] = rad
        rs = x["r_m"].dropna()
        if len(rs):
            print(f"  최대내접원 반경 — 중앙 {rs.median():.2f}m · p10 {rs.quantile(.10):.2f}m "
                  f"· p90 {rs.quantile(.90):.2f}m · 최대 {rs.max():.2f}m")

        # 각 구간 끝점에 가장 가까운 교차부 폴리곤의 반경을 붙인다
        sj = gpd.sjoin_nearest(
            gpd.GeoDataFrame(geometry=[gg.interpolate(gg.length / 2) if False else gg
                                       for gg in g.geometry], crs=CRS_M),
            x[["r_m", "geometry"]], how="left", max_distance=10.0)
        g["corner_radius_m"] = sj.groupby(level=0)["r_m"].max().round(2)

    # ── 3. 스윕 통과 판정 ─────────────────────────────────────
    print("\n[스윕 통과 판정]")
    w = pd.to_numeric(g.get("width_min_m"), errors="coerce")
    verdicts = g.get("verdict")

    # ★ 판정 단위는 **구간이 아니라 코너**다. 격자 도로에서는 거의 모든
    #   구간이 한쪽 끝에서 직각 교차로를 만나므로, 구간별 최대 꺾임각으로
    #   세면 1,101 중 1,070 이 걸려 변별력이 없다.
    fail = unknown_w = 0
    hard = 0
    tight: list[tuple[float, int, int]] = []
    for d, i, j, va, vb in corners:
        if d < 60.0:
            continue
        hard += 1
        w1, w2 = w.iloc[i], w.iloc[j]
        if pd.isna(w1) or pd.isna(w2):
            unknown_w += 1
            continue
        # 진입 방향은 노드로 **들어오는** 쪽이므로 한쪽을 뒤집는다.
        m = sweep_margin((-va[0], -va[1]), vb, float(w1), float(w2), R, L, W, C)
        if m > 0:
            fail += 1
            tight.append((m, i, j))

    print(f"  60° 이상 코너                     {hard:,}")
    print(f"    폭을 모르는 쪽이 있어 판정 보류   {unknown_w:,}")
    print(f"    ★ 스윕이 안 되는 코너            {fail:,}"
          f"  ({fail / max(1, hard - unknown_w):.0%})")
    if verdicts is not None and tight:
        known = sum(1 for _, i, j in tight
                    if verdicts.iloc[i] == "blocked" or verdicts.iloc[j] == "blocked")
        print(f"      이미 통행 불가가 끼어 있는 것  {known:,}")
        print(f"      ★ 폭 판정은 통과인데 못 도는 것 {len(tight) - known:,}")
        tight.sort(reverse=True)
        print("      모자란 폭 상위")
        for m, i, j in tight[:8]:
            print(f"        {m:5.2f}m  {g['road_name'].iloc[i]} × "
                  f"{g['road_name'].iloc[j]}  "
                  f"({w.iloc[i]:.1f} × {w.iloc[j]:.1f}m)")

    # 참고 — 구간 단위 집계. 변별력이 낮다는 것을 함께 보인다.
    cor = g["turn_deflection_deg"] >= 60.0
    print(f"  (참고) 60° 이상 코너에 닿는 구간 {int(cor.sum()):,} / {len(g):,}"
          "  — 격자라 대부분이 걸린다. 구간 단위로 세지 말 것")

    if a.csv:
        out = ROOT / "data" / "interim"
        out.mkdir(parents=True, exist_ok=True)
        cols = ["seg_uid", "road_name", "seg_label", "verdict", "width_min_m",
                "turn_deflection_deg", "corner_radius_m"]
        f = out / "corner_probe.csv"
        g[[c for c in cols if c in g.columns]].to_csv(f, index=False,
                                                      encoding="utf-8-sig")
        print(f"\n→ {f}")

    print("\n★ 이 값은 판정에 반영되지 않는다. 필드로 승격할지는 분포를 보고 정한다.")
    print("  회전반경이 미확정인 채로 임계를 박으면 근거 없는 상수가 하나 더 생긴다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

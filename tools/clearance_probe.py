#!/usr/bin/env python3
"""
tools/clearance_probe.py — 최대내접원(clearance) 방식 폭 산출 프로토타입

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다.
  segments.py 를 건드리지 않고, data/processed 에 쓰지 않는다.
  읽기만 하고 화면에 표를 낸다. golden 지문은 그대로다.

── 왜 만들었나 ─────────────────────────────────────────────────
현재 width.py 는 **법선 트랜섹트** 방식이다. 표본점에서 중심선에 수직인
선을 긋고 도로 폴리곤과의 교차 길이를 폭으로 본다.

문제는 법선 방향이 1m 베이스라인(±0.5m 접선)에서 나온다는 것이다.
디지타이징 정점 오차 0.15m 면 각도 오차가 약 8도다. 그 8도가 거리에
비례해 벌어진다.

    도로 경계(wmin)   1~3m  앞  →  0.1~0.4m 편차   무시 가능
    건물 벽(wmax)    10~20m 앞  →  1.4~2.8m 편차   빗나감

wmin 은 멀쩡한데 wmax 만 273구간에서 죽는 이유가 이것으로 설명된다.
(2026-08-22 실측: 결손 273구간 중 40m 안에 건물 0개인 구간은 0개.
 10m 안 건물 중앙 8개. 데이터 공백이 아니라 측정 방식 문제다.)

── clearance 방식 ──────────────────────────────────────────────
점 p 에서 도로 경계까지의 거리 r(p) 를 재면, 그 자리에 들어가는 최대
내접원 지름이 2r 이다. **소방차 통과 = 반지름 1.5m 원이 이어지는가** 이므로
이것이 곧 통행 조건이다.

    · 법선 방향이 필요 없다        ← 각도 오차가 원천 소멸
    · 교차로에서 옆길로 새지 않는다  ← 표본 폐기가 없다
    · 건물을 장애물로 넣으면 wmax 가 같은 식으로 나온다
    · 코너 유효폭이 자연히 나온다    ← 트랜섹트로는 불가능
    · A* 비용이 clearance 자체다     ← 폭→판정→비용 2단 변환 불필요

★ 중심선 보정.
  도로명주소 중심선은 위상용이라 실제 노면 중앙이 아니다. r(p) 를 그대로
  쓰면 중심선이 치우친 만큼 폭이 과소평가된다. 그래서 p 주변 반경 R 안에서
  clearance 의 **최댓값**을 찾는다 — 국소 중심축(medial axis)을 집는 것이다.
  최댓값은 방향에 둔감하므로 법선 오차가 개입하지 않는다.
  R 을 크게 잡으면 교차로의 넓은 데로 새므로 기본 2.5m 로 둔다.

★ 래스터를 쓰지 않는다.
  distance_transform_edt 는 격자 크기가 곧 해상도라, 0.25m 격자면 폭
  해상도가 0.5m 다. 판정 임계값이 3.0m 인데 그 양자화는 판정을 뒤집는다.
  shapely 2 의 벡터화 distance 로 **정확한 거리**를 계산한다.

── 사용 ────────────────────────────────────────────────────────
    uv run python tools/clearance_probe.py
    uv run python tools/clearance_probe.py --step 1.0 --radius 3.0
    uv run python tools/clearance_probe.py --only DM01611 DM01498
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from firelane.paths import PROCESSED
from firelane.seg.params import TRUCK

CRS_M = "EPSG:5186"


def robust_union(geoms, label=""):
    """무효 도형을 단계적으로 정리하고 union 한다.

    ★ 유효성을 union **전에** 확인한다. 무효 도형을 그대로 넣으면 예외가
      아니라 **틀린 답**이 나온다. 실측: 나비넥타이 폴리곤을 그냥 union 하면
      면적 100 이 나온다(정답 150). 조용한 오답이 예외보다 나쁘다.

    ★ road_rw(실폭도로)가 이걸로 터졌다. sources.yaml 이 이미 경고해 뒀다 —
      "winding order 오류 폴리곤 포함. make_valid + buffer(0) 없이
      unary_union 하면 …". ingest 는 shp_zip_multi 에만 make_valid 를 걸고
      road_rw(shp_zip)에는 안 건다.

    ★ grid_size 는 마지막 수단이다. 좌표를 양자화해 위상 충돌을 없애지만
      그만큼 기하가 바뀐다. 여기까지 왔다는 것 자체를 화면에 남긴다.
    """
    g = np.asarray(geoms, dtype=object)
    g = g[~shapely.is_empty(g) & ~shapely.is_missing(g)]
    n_bad = int((~shapely.is_valid(g)).sum())
    stage = "그대로"
    if n_bad:
        g = shapely.make_valid(g)
        stage = f"make_valid {n_bad}건"
        still = int((~shapely.is_valid(g)).sum())
        if still:
            g = shapely.buffer(g, 0)
            stage = f"buffer0 {still}건"
    g = g[~shapely.is_empty(g)]
    try:
        return shapely.union_all(g), stage
    except Exception:
        pass
    for gs in (1e-4, 1e-3, 1e-2):
        try:
            return shapely.union_all(g, grid_size=gs), f"{stage} + grid_size {gs}"
        except Exception:
            continue
    raise RuntimeError(f"{label}: union 실패. 이 소스를 빼고 돌려라")


def load_union(name: str):
    """processed gpkg 하나를 읽어 폴리곤 union 을 만든다. 없으면 None."""
    p = PROCESSED / f"{name}_5186.gpkg"
    if not p.exists():
        print(f"  · {name} 없음 — 건너뛴다")
        return None
    g = gpd.read_file(p).to_crs(CRS_M)
    g = g[~g.geometry.is_empty & g.geometry.notna()]
    poly = g[g.geom_type.isin(("Polygon", "MultiPolygon"))]
    if not len(poly):
        print(f"  · {name} 폴리곤 없음 ({g.geom_type.unique()})")
        return None
    u, how = robust_union(poly.geometry.values, name)
    mark = "" if how == "그대로" else f"   ★ {how}"
    print(f"  · {name:16s} {len(poly):6d} 폴리곤{mark}")
    return u


def disk(radius, cstep):
    """반경 radius 원판 안의 오프셋 격자. 한 번만 만들어 재사용한다."""
    n = int(radius / cstep)
    offs = np.arange(-n, n + 1) * cstep
    gx, gy = np.meshgrid(offs, offs)
    m = (gx ** 2 + gy ** 2) <= radius ** 2
    return gx[m], gy[m]


def clearance_profile(line, area_u, step, radius, dx, dy):
    """구간을 따라 clearance 프로파일을 낸다.

    ★ 성능. 처음에는 표본마다 **전역** 경계에 distance 를 걸었다.
      도로 union 의 경계 정점이 7만 개라 질의 하나가 그 전부를 훑는다.
      실측 30구간 581.8초 → 1,101구간 6시간. 못 쓴다.

      둘을 고쳤다(합성 규모 실측 348배):
        1. 구간 주변만 잘라낸다. 국소 경계는 정점이 수백 개다.
        2. 전 표본의 후보점을 한 배열로 모아 벡터 연산 한 번에 끝낸다.

    ★ 반환의 gain 은 '중심선 그 자리의 clearance 대비 원판 최댓값이 얼마나
      커졌나' 다. 누수 진단용이다.

      처음에는 최적점까지의 거리(off)가 radius 에 붙으면 샌 것으로 봤는데
      그게 틀렸다. 폭이 일정한 직선 도로에서는 원판 가장자리에도 같은
      최댓값이 있어 argmax 가 거기를 집는다 — 실측 누수율 0.94 가 나왔다.
      **동률을 누수로 오독한 것이다.** 값이 실제로 커졌는지를 봐야 한다.
        gain ≈ 0    중심선이 이미 중심축 위. 정상
        gain > 0    중심선이 치우쳤다(보정이 일한 것) 또는 넓은 데로 샜다
    """
    if line.length < 1e-6:
        return np.array([]), np.array([]), np.array([])
    ts = np.arange(0.0, line.length + 1e-9, step)
    if len(ts) == 0:
        ts = np.array([line.length / 2])

    # ① 국소 클립. 구간에서 radius + 여유만큼만 남긴다.
    local = shapely.intersection(area_u, line.buffer(radius + 40))
    if local.is_empty:
        n = len(ts)
        return ts, np.full(n, np.nan), np.full(n, np.nan)
    local_b = local.boundary

    # ② 전 표본 후보를 한 배열로
    P = shapely.get_coordinates(
        shapely.points([line.interpolate(t) for t in ts])) \
        if False else np.array([[line.interpolate(t).x, line.interpolate(t).y]
                                for t in ts])
    ax = (P[:, 0][:, None] + dx[None, :]).ravel()
    ay = (P[:, 1][:, None] + dy[None, :]).ravel()
    pts = shapely.points(ax, ay)

    inside = shapely.contains(local, pts)
    d = np.full(len(pts), np.nan)
    if inside.any():
        d[inside] = shapely.distance(local_b, pts[inside])

    D = d.reshape(len(ts), -1)
    # 중심선 그 자리(오프셋 0)의 clearance. 원판 최댓값과 비교할 기준이다.
    c0 = int(np.argmin(dx ** 2 + dy ** 2))
    with np.errstate(invalid="ignore"):
        allnan = np.all(np.isnan(D), axis=1)
        r = np.where(allnan, np.nan, np.nanmax(np.where(np.isnan(D), -np.inf, D), axis=1))
        base = D[:, c0]
        gain = np.where(np.isnan(base) | allnan, np.nan, r - base)
    return ts, 2.0 * r, 2.0 * gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=2.0, help="중심선 표본 간격 m")
    ap.add_argument("--radius", type=float, default=2.5, help="중심축 탐색 반경 m")
    ap.add_argument("--cstep", type=float, default=0.25, help="후보 격자 간격 m")
    ap.add_argument("--only", nargs="*", help="이 seg_id 만")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N구간만 (시험용)")
    a = ap.parse_args()

    print("── 소스 적재 ──────────────────────────────────────")
    seg = gpd.read_file(PROCESSED / "segments_5186.gpkg").to_crs(CRS_M)
    print(f"  · segments        {len(seg):6d} 구간")

    # 도로면: wmin 과 같은 3소스를 합친다. 어느 하나가 비어도 나머지로 간다.
    parts = [u for u in (load_union("ngii1k"), load_union("ngii_road"),
                         load_union("road_rw")) if u is not None]
    if not parts:
        raise SystemExit("★ 도로 폴리곤 소스가 하나도 없다. ingest 를 먼저 통과시켜라.")
    road_u, _how = robust_union(parts, "road")

    bld_u = load_union("building")
    # ★ wmax(담~담)는 '건물이 아닌 공간'의 clearance 다. 좌우 동시 검출이
    #   필요 없다 — 그것이 273구간을 죽인 조건이었다.
    bld_b = bld_u.boundary if bld_u is not None else None

    rows = []
    tgt = seg
    if a.only:
        tgt = seg[seg.seg_id.isin(a.only)]
    elif a.limit:
        tgt = seg.head(a.limit)
    DX, DY = disk(a.radius, a.cstep)
    print(f"\n── 계산 {len(tgt)}구간 (step {a.step}m · radius {a.radius}m "
          f"· 표본당 후보 {len(DX)}점) ──")

    t0 = time.time()
    for k, r in enumerate(tgt.itertuples(), 1):
        line = r.geometry
        if line.geom_type != "LineString":
            line = max(line.geoms, key=lambda g: g.length)

        _, w, gain = clearance_profile(line, road_u, a.step, a.radius, DX, DY)
        ok = ~np.isnan(w)

        rec = {
            "seg_id": getattr(r, "seg_id", ""),
            "road": getattr(r, "road_name", ""),
            "len_m": round(line.length, 1),
            "n": len(w),
            "cov": round(ok.mean(), 3) if len(w) else 0.0,
            # 통행 가능 여부를 정하는 것은 최솟값이다. 한 곳이라도 막히면 못 간다.
            "cl_min": round(float(np.nanmin(w)), 2) if ok.any() else None,
            "cl_p10": round(float(np.nanpercentile(w, 10)), 2) if ok.any() else None,
            "cl_med": round(float(np.nanmedian(w)), 2) if ok.any() else None,
            # ★ 적분값. 구간 길이 중 소방차(TRUCK)가 못 지나는 비율.
            #   스칼라 하나가 아니라 분포를 낸다.
            "blk_frac": round(float((w[ok] < TRUCK).mean()), 3) if ok.any() else None,
            # ★ 중심선 자리 대비 얼마나 넓어졌나. 중심선 치우침 보정량이고,
            #   과하면 넓은 데로 샌 것이다.
            "gain_med": round(float(np.nanmedian(gain)), 2) if ok.any() else None,
            "gain_max": round(float(np.nanmax(gain)), 2) if ok.any() else None,
            "wmin_now": getattr(r, "width_min_m", None),
            "wmax_now": getattr(r, "width_max_m", None),
            "verdict_now": getattr(r, "verdict", None),
        }

        if bld_b is not None:
            # 담~담 = '건물이 아닌 공간' 의 clearance. 좌우 동시 검출이
            # 필요 없다 — 그 조건이 273구간을 죽였다.
            free = shapely.difference(line.buffer(80), bld_u)
            _, wb, _ = clearance_profile(line, free, a.step, a.radius, DX, DY)
            okb = ~np.isnan(wb)
            rec["bl_min"] = round(float(np.nanmin(wb)), 2) if okb.any() else None
            rec["bl_cov"] = round(okb.mean(), 3) if len(wb) else 0.0

        rows.append(rec)
        if k % 50 == 0:
            print(f"    {k}/{len(tgt)}  {time.time()-t0:.0f}s")

    df = pd.DataFrame(rows)
    print(f"\n계산 완료 {time.time()-t0:.1f}s\n")

    # ── 1. 현재 wmin 과의 일치 ─────────────────────────────
    d = df.dropna(subset=["cl_min", "wmin_now"]).copy()
    if len(d):
        d["diff"] = pd.to_numeric(d.cl_min) - pd.to_numeric(d.wmin_now)
        print("── 1. 현재 wmin 대비 (일치할수록 방법이 옳다는 증거) ──")
        print(f"  대상 {len(d)}구간")
        print(f"  차이  중앙 {d['diff'].median():+.2f}m · "
              f"평균 {d['diff'].mean():+.2f}m · 표준편차 {d['diff'].std():.2f}m")
        for th in (0.3, 0.5, 1.0):
            print(f"    |차이| < {th}m : {(d['diff'].abs()<th).mean()*100:5.1f}%")

        # ★ 큰 차이가 탐색 누수 때문인지 본다
        big = d[d["diff"].abs() >= 1.0]
        if len(big):
            sm = d[d["diff"].abs() < 0.3]
            print(f"\n  |차이| >= 1.0m : {len(big)}구간 · gain 중앙 {big.gain_med.median():.2f}m")
            if len(sm):
                print(f"  |차이| <  0.3m : {len(sm)}구간 · gain 중앙 {sm.gain_med.median():.2f}m")
                print("    ★ 앞쪽 gain 이 확연히 크면 탐색 원판이 넓은 데로 샌 것 → radius 축소")
            print(big.nlargest(8, "diff")[
                ["seg_id", "road", "len_m", "cl_min", "wmin_now",
                 "diff", "gain_med", "gain_max"]].to_string(index=False))

    # ── 2. 현재 실패한 구간에서 값이 나오나 ────────────────
    fail = df[df.wmax_now.isna() | (df.wmax_now == "")]
    print(f"\n── 2. 현재 wmax 결손 {len(fail)}구간에서 clearance ──")
    if len(fail):
        got = fail.cl_min.notna().sum()
        print(f"  도로 clearance 산출 {got}/{len(fail)} ({got/len(fail)*100:.0f}%)")
        if "bl_min" in fail:
            gotb = fail.bl_min.notna().sum()
            print(f"  담~담 clearance 산출 {gotb}/{len(fail)} ({gotb/len(fail)*100:.0f}%)"
                  "   ★ 이게 크면 273구간이 복구된다")

    # ── 3. 판정이 바뀌는가 ────────────────────────────────
    print("\n── 3. clearance 기준 판정 분포 (참고) ──")
    v = df.dropna(subset=["cl_min"]).copy()
    if len(v):
        v["cl_verdict"] = np.where(pd.to_numeric(v.cl_min) < TRUCK, "blocked", "passable")
        print(v.groupby(["verdict_now", "cl_verdict"]).size().to_string())

    out = PROCESSED / "clearance_probe.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n→ {out}  ({len(df)}행)")
    print("  ★ processed 산출물이지만 파이프라인 대장에 없다. 참고용이며 커밋하지 않는다.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
tools/jijeok_probe.py — 연속지적도 도로 필지로 폭을 재고 우리 값과 대조한다

    uv run python tools/jijeok_probe.py --extract   # zip → 스코프 필지 (한 번)
    uv run python tools/jijeok_probe.py             # 대조 표

════════════════════════════════════════════════════════════════
★ 이 스크립트는 아무것도 안 바꾼다.
  `segments.py` 를 건드리지 않고 `data/processed` 에 쓰지 않는다.
  읽고 화면에 표를 낸다. golden 지문은 그대로다.
  (`clearance_probe.py` 와 같은 성격이다)

── 왜 만들었나 ─────────────────────────────────────────────────
2026-08-23. 폭 판정에 쓰는 소스가 셋인데 계보가 둘뿐이었다.

    ngii1k · ngii_road · ortho · dem     국토정보플랫폼(NGII)
    road_rw(실폭도로) · road_link        행안부 도로명주소

네이버 지도로 대조하려다 하단 표기가 `국토지리정보원` 인 것을 보고 접었다.
네이버 위성은 우리 `ortho` 와 **같은 항공사진**이다. 같은 것을 두 번 보는
것이라 독립 검증이 아니다. DECISIONS 가 미리 적어둔 그대로다.

연속지적도(LX/국가공간정보포털)는 **세 번째 계보**다. 만드는 기관도,
측량 근거도, 갱신 주기도 다르다.

── 무엇을 알아냈나 ─────────────────────────────────────────────
여섯 번 틀리고 원인 둘을 찾았다. 기록해 둔다. 같은 함정이 또 온다.

  ① `boundary` 가 구멍 테두리를 포함한다
       도로를 union 하면 그물이 되고 그물 구멍 = 가구(街區)다.
       그 테두리는 정상적인 반대편 경계라 지우면 안 된다.
  ② sliver 가설                 틀림. 얇은 구멍 416개 면적 합이 432㎡뿐
  ③ union 미결합 가설           틀림. 최대 조각이 전체의 98.6%
  ④ **중심선이 지적 중앙이 아니다**   ★ 맞음
       최대내접원은 점 위치에 극도로 민감하다. 중앙에서 1cm 벗어나면
       값이 무너진다. `동명로 29-59`(wmin 19.17m)에서 0.009m 가 나왔다.
       → 법선 트랜섹트로 바꿨다. 중심선이 치우쳐도 폭은 안 변한다.
       (`clearance_probe.py` 가 이미 "중심선은 위상용" 이라 적어놨다.
        08-22 에 그 보정을 넣고도 졌던 이유가 ⑤⑥ 였을 수 있다)
  ⑤ 법선 포화                   맞음. 법선이 도로를 못 빠져나가면 폭이
       아니라 상한값(2×HALF)이 그대로 나온다
  ⑥ **거대 도로구역 필지**       ★ 진짜 원인
       `대인동 329 도` 필지 하나가 **85,598㎡** 다. 8.5헥타르에 골목·
       광장·교차로가 통째로 들어 있다. `wmin 0.70m` 골목이 그 안에 있으면
       법선 80m 가 어느 방향으로도 안 빠져나간다.
       **지적 도로 필지는 '도로구역' 이지 '노면' 이 아니다.**

★ 교차부 제외는 효과가 없었다(std 6.33 → 6.37). 다만 `width.py` 와 같은
  규칙(결정 81)을 적용해야 비교가 공정하므로 남긴다.
  ★ 법선을 `difference(xsec)` 로 자르면 **안 된다.** 폭이 토막나거나
    늘어난다. std 6.33 → 10.54 로 악화됐다. 표본 위치만 거른다.

── 결과 (2026-08-23) ───────────────────────────────────────────
    대역     n    중앙편차    표준편차
    <3     181    +0.62      3.99
    3~7    133    +0.45      1.09     ★ 판정 임계가 걸리는 대역
    7~12   133    +0.51      4.19
    12+     80    +0.02      7.34     도로구역 필지가 남아 오염

**중앙 편차가 여덟 판 내내 +0.45~0.50 에서 안 움직였다.** 계통값이 그것이고,
지적 도로가 우리보다 0.5m 넓은 것은 측구·법면 포함으로 설명된다.

3~7m 대역 std 1.09m 는 **쓸 수 있는 값이다.** 대로(12+)는 못 쓰지만
대로는 어차피 `clear` 라 폭이 필요 없다.

IN    $FIRE_LANE_DATA/_quarantine/nsdi/AL_D002_*.zip  (또는 raw/nsdi/)
      data/processed/segments_5186.gpkg
      data/processed/ngii1k_xsec_5186.gpkg
OUT   없음. 화면 표만. --save 를 주면 $FIRE_LANE_DATA/../jijeok_width.gpkg
PARAM 아래 상수
════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyogrio
from pyproj import Transformer
from shapely import set_precision
from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree

from firelane.paths import INTERIM, PROCESSED, QUARANTINE, RAW

# ── 상수 ───────────────────────────────────────────────────────
CRS = 5186                  # 연속지적도 .prj = Korea_2000_Korea_Central_Belt_2010
                            # ngii1k 과 같다. 변환 없이 겹친다
ENC = "cp949"               # .cpg = EUC-KR

# ★ 지목 '도' 만 쓰면 안 된다. 2026-08-23 확정:
#   `동계천로` · `동계로` 는 복개도로라 지목이 '천'(하천) · '구'(구거)로 남고
#   `계림로` 는 '철'(철도용지) — 폐선 부지가 도로화됐다.
#   법정 도로 밖 82구간을 지목별로 가르니 구 57 · 천 18 · 철 9 였다.
#   '대' 98필지는 진짜 미불용지(사유지)라 넣으면 건물 대지까지 딸려온다.
JIMOK = {"도", "구", "천", "철"}

STEP = 5.0                  # 표본 간격(m)
HALF = 40.0                 # 법선 편측 길이(m). 2×HALF 가 폭 상한
SAT = 0.99                  # 법선 길이의 이 비율 넘으면 포화 — 버린다
MAX_PARCEL = 5000.0         # 필지가 이보다 크면 도로구역이다. 폭 못 준다
SNAP = 0.01                 # 좌표 격자(m). 지적 필지 공유 경계 어긋남 보정
COV_MIN = 0.5               # 유효 표본이 이 비율 미만이면 산출하지 않는다

SCOPE_GPKG = "jijeok_scope.gpkg"
OUT_GPKG = "jijeok_width.gpkg"

C = {"r": "\033[31m", "g": "\033[32m", "y": "\033[33m",
     "c": "\033[36m", "d": "\033[90m", "z": "\033[0m"}


def col(s: str, k: str) -> str:
    return f"{C[k]}{s}{C['z']}" if sys.stdout.isatty() else s


def _side() -> Path:
    """탐색 산출물 자리. `interim` 계층이다(MASTER §18-1).

    ★ 2026-08-24. 종전에는 `RAW.parent.parent` — 프로젝트 루트였다.
      "아직 대장에 없는 탐색 산출물이라 여기 둔다" 고 적어놓았는데,
      그 결과 SSD 루트에 jijeok_*.gpkg 11.7MB 가 널렸다. 갈 계층이
      없으면 파일은 아무 데나 떨어진다.
    """
    INTERIM.mkdir(parents=True, exist_ok=True)
    return INTERIM


def find_zip() -> Path | None:
    for base in (QUARANTINE / "nsdi", RAW / "nsdi"):
        if base.is_dir():
            hit = sorted(base.glob("AL_D002_*.zip"))
            if hit:
                return hit[0]
    return None


def cmd_extract() -> int:
    """zip → 스코프 필지 gpkg. 압축을 풀지 않는다.

    ★ `/vsizip/` 으로 직접 읽고 **읽는 시점에** bbox 를 건다.
      조각 하나가 100만 필지이고 조각이 7개다. `shp_zip_multi` 핸들러는
      전량을 메모리에 올린 뒤 `.cx[]` 로 자르므로 여기서 죽는다.
    """
    z = find_zip()
    if z is None:
        print(col("AL_D002_*.zip 을 못 찾았다.", "r"))
        print(f"  {QUARANTINE / 'nsdi'} 또는 {RAW / 'nsdi'} 를 확인하라.")
        return 1
    print(f"{col('원본', 'd')}  {z}")

    names = sorted(n for n in zipfile.ZipFile(z).namelist() if n.endswith(".shp"))
    t = Transformer.from_crs(4326, CRS, always_xy=True)
    import yaml
    bb = yaml.safe_load((Path(__file__).resolve().parents[1] / "sources.yaml")
                        .read_text(encoding="utf-8"))["bbox_4326"]
    x0, y0 = t.transform(bb[0], bb[1])
    x1, y1 = t.transform(bb[2], bb[3])
    print(f"{col('스코프', 'd')}  {x0:.0f},{y0:.0f} ~ {x1:.0f},{y1:.0f}  (EPSG:{CRS})\n")

    parts = []
    for n in names:
        g = pyogrio.read_dataframe(f"/vsizip/{z}/{n}", bbox=(x0, y0, x1, y1),
                                   encoding=ENC)
        print(f"  {n[-14:]:16} {len(g):>7,}필지")
        if len(g):
            parts.append(g)
    if not parts:
        print(col("\n스코프 안에 필지가 없다. CRS 를 확인하라.", "r"))
        return 1

    import pandas as pd
    g = pd.concat(parts).pipe(gpd.GeoDataFrame, crs=f"EPSG:{CRS}")
    dst = _side() / SCOPE_GPKG
    g.to_file(dst, layer="jijeok", driver="GPKG")
    print(f"\n{col('→', 'g')} {dst}  ({len(g):,}필지)")
    return 0


def load_road(g: gpd.GeoDataFrame):
    """도로 폴리곤 본체 + 필지 인덱스."""
    # ★ 지목은 A5 끝의 한글 한 글자다. 공백 split 은 '1-3대' 를 놓친다.
    g = g.copy()
    g["지목"] = g.A5.astype(str).str.extract(r"([가-힣])\s*$")[0]
    do = g[g.지목.isin(JIMOK)].copy()
    do["geometry"] = set_precision(do.geometry.buffer(0).values, SNAP)
    print(f"채택 지목 {do.지목.value_counts().to_dict()}")

    u = unary_union(do.geometry.values)
    polys = list(getattr(u, "geoms", [u]))
    main = max(polys, key=lambda p: p.area)
    print(f"조각 {len(polys)} · 본체가 전체의 {main.area / u.area * 100:.1f}%")
    return main, do


def widths(line, main, tree, areas, geoms, xsec):
    """법선 트랜섹트. 우리 width.py 와 같은 방식이라 비교가 공정하다."""
    n = max(int(line.length // STEP), 1)
    ws = {"ok": [], "xsec": 0, "big": 0, "sat": 0, "out": 0}
    for i in range(n + 1):
        s = i / n
        p = line.interpolate(s, normalized=True)

        # 교차부는 **표본 위치만** 거른다(결정 81).
        if xsec is not None and xsec.contains(p):
            ws["xsec"] += 1
            continue

        hits = [j for j in tree.query(p) if geoms[j].contains(p)]
        if not hits:
            ws["out"] += 1
            continue
        # 도로구역 필지 안이면 폭 개념이 없다(⑥).
        if min(areas[j] for j in hits) > MAX_PARCEL:
            ws["big"] += 1
            continue

        d = 0.5 / line.length
        a = line.interpolate(max(s - d, 0), normalized=True)
        b = line.interpolate(min(s + d, 1), normalized=True)
        dx, dy = b.x - a.x, b.y - a.y
        L = float(np.hypot(dx, dy))
        if L < 1e-9:
            continue
        nx, ny = -dy / L, dx / L
        cut = LineString([(p.x - nx * HALF, p.y - ny * HALF),
                          (p.x + nx * HALF, p.y + ny * HALF)])
        inter = cut.intersection(main)
        if inter.is_empty:
            ws["out"] += 1
            continue
        parts = list(getattr(inter, "geoms", [inter]))
        near = min(parts, key=lambda q: q.distance(p))
        # 고른 조각이 점을 품지 않으면 **다른 도로**를 재고 있는 것이다.
        if near.distance(p) > 0.01:
            ws["out"] += 1
            continue
        if near.length >= 2 * HALF * SAT:
            ws["sat"] += 1
            continue
        ws["ok"].append(near.length)
    return ws, n + 1


def cmd_probe(save: bool) -> int:
    src = _side() / SCOPE_GPKG
    if not src.exists():
        print(col(f"{src} 가 없다. --extract 를 먼저 돌려라.", "r"))
        return 1
    g = gpd.read_file(src, layer="jijeok").to_crs(CRS)
    main, do = load_road(g)

    xp = PROCESSED / "ngii1k_xsec_5186.gpkg"
    xsec = None
    if xp.exists():
        xs = gpd.read_file(xp, layer="ngii1k_xsec").to_crs(CRS)
        xsec = unary_union(xs.geometry.buffer(0).values)
        print(f"교차부 {len(xs):,}건 제외 (결정 81)")

    sp = PROCESSED / "segments_5186.gpkg"
    if not sp.exists():
        print(col(f"{sp} 가 없다. uv run fire-lane --from segments", "r"))
        return 1
    seg = gpd.read_file(sp).to_crs(CRS)

    geoms = do.geometry.values
    tree = STRtree(geoms)
    areas = do.geometry.area.values

    rows = [widths(x, main, tree, areas, geoms, xsec) for x in seg.geometry]
    seg["jj_w"] = [min(w["ok"]) if w["ok"] else np.nan for w, _ in rows]
    seg["jj_cov"] = [len(w["ok"]) / t for w, t in rows]
    for k in ("xsec", "big", "sat", "out"):
        seg[f"jj_{k}"] = [w[k] for w, _ in rows]

    print(f"\n{col('버린 표본', 'd')}  교차부 {seg.jj_xsec.sum():,} · "
          f"도로구역 {seg.jj_big.sum():,} · 포화 {seg.jj_sat.sum():,} · "
          f"도로밖 {seg.jj_out.sum():,}")

    ok = seg[seg.jj_cov >= COV_MIN].dropna(subset=["jj_w", "width_min_m"]).copy()
    ok["dev"] = ok.jj_w - ok.width_min_m
    print(f"\n산출 {len(ok):,}/{len(seg):,}  (커버 {COV_MIN:.0%} 이상)")
    print(f"jj_w  최소 {ok.jj_w.min():.2f} · 중앙 {ok.jj_w.median():.2f} · "
          f"최대 {ok.jj_w.max():.2f}")
    print(f"편차  중앙 {ok.dev.median():+.2f}m · 표준편차 {ok.dev.std():.2f}m")
    for t in (0.5, 1.0, 2.0):
        print(f"   |편차| < {t}m : {(ok.dev.abs() < t).mean() * 100:5.1f}%")

    band = np.select([ok.width_min_m < 3, ok.width_min_m < 7, ok.width_min_m < 12],
                     ["<3", "3~7", "7~12"], "12+")
    tab = ok.assign(band=band).groupby("band").dev.agg(["count", "median", "std"])
    print("\n대역별")
    print(tab.round(2).to_string())
    print(col("   ★ 3~7 이 판정 임계(3.0m)가 걸리는 대역이다.", "d"))
    print(col("     12+ 는 도로구역 필지가 남아 오염된다. 대로는 어차피 clear.", "d"))

    f = ok[((ok.width_min_m >= 3) & (ok.jj_w < 3)) |
           ((ok.width_min_m < 3) & (ok.jj_w >= 3))]
    print(f"\n{col('★ 3.0m 임계에서 갈리는 구간', 'y')} {len(f)} — 실측 우선순위")
    cols = ["seg_label", "verdict", "width_min_m", "jj_w", "jj_cov"]
    print(f.reindex(f.dev.abs().sort_values(ascending=False).index)[cols]
          .head(12).to_string(index=False))

    if save:
        dst = _side() / OUT_GPKG
        ok.to_file(dst, layer="seg", driver="GPKG")
        print(f"\n{col('→', 'g')} {dst}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true",
                    help="zip → 스코프 필지 gpkg (한 번만)")
    ap.add_argument("--save", action="store_true",
                    help="대조 결과를 gpkg 로 남긴다")
    a = ap.parse_args()
    return cmd_extract() if a.extract else cmd_probe(a.save)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
tools/skeleton_compare.py — 판정 뼈대 후보(NGII 1:1,000 하이브리드)를 세우고 현행 1,281 구간과 대조한다 (R1)

    uv run python tools/skeleton_compare.py            대조 · 요약
    uv run python tools/skeleton_compare.py --top 40   의심 구간 상위 40

★ 판정을 안 바꾼다. `segments` · `web/data` · golden 을 건드리지 않는다. 표를 낸다.
  사람이 이 표를 보고 R3(뼈대 교체 · golden 재잠금)를 판정한다(DECISIONS §184).

── 무엇을 보나 ─────────────────────────────────────────────────
현행 구간은 도로명주소 `road_link` 위에 서고 폭은 NGII 도로경계에서 잰다. 2026-09-17 실측에서
NGII 1:1,000 건물을 관통하는 선이 현행 17 · NGII 중심선 0 이었다 — 뼈대만 다른 측량 위에 있다.
구간마다 하이브리드 엣지에 매칭하고 네 가지 사유를 붙인다.

    멀리      매칭 엣지까지 거리 중앙이 3m 를 넘는다 — 엉뚱한 자리에서 폭을 쟀다는 쪽의 증거
    짝없음    표본점 60% 이상이 한 엣지로 모이지 않는다(8m · 25°)
    폭불일치  매칭 엣지의 NGII 측량 도로폭과 현재 width_min_m 이 2m 이상 다르다
    건물관통  현행 선이 NGII 건물을 1m 넘게 지나는데 매칭 엣지는 안 지난다
    쌍선      매칭 엣지가 폭 6m 이상 평행 쌍선이다(간선 이중 판정 후보)

IN    data/processed/road_link_5186.gpkg · ngii1k_center_5186.gpkg · segments_5186.gpkg ·
      building_5186.gpkg · corridor_5186.gpkg · boundary_emd.geojson · fire_station.geojson ·
      $FIRE_LANE_DATA/raw — V-WORLD 1:1,000 묶음의 B0010000(건물) 레이어
OUT   data/desk/r1/compare.csv · data/desk/r1/skeleton_5186.gpkg · data/desk/r1/summary.json
PARAM firelane.skeleton 의 상수(COVER_D · GAP · MATCH_*)
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from firelane import ledger, paths
from firelane import skeleton as S
from firelane.seg.scope import judgment_scope

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
OUT = ROOT / "data" / "desk" / "r1"
WORK = ROOT / ".work" / "r1"
EMD_CD = "12210108"


def ngii_buildings(keep) -> gpd.GeoDataFrame:
    """V-WORLD 묶음(바깥 zip → 도엽 zip) 안의 N1A_B0010000 을 판정 범위로 모은다. .work/r1 에만 푼다."""
    e = ledger.load_sources()["datasets"]["ngii1k"]
    parts = []
    for outer in ledger.paths_of(e, paths.RAW):
        with zipfile.ZipFile(outer) as z:
            for n in z.namelist():
                if not n.lower().endswith(".zip"):
                    continue
                with zipfile.ZipFile(io.BytesIO(z.read(n))) as iz:
                    shp = [m for m in iz.namelist() if m.upper().endswith("N1A_B0010000.SHP")]
                    if not shp:
                        continue
                    d = WORK / Path(n).stem
                    d.mkdir(parents=True, exist_ok=True)
                    stem = shp[0][:-4]
                    for m in iz.namelist():
                        if m[:-4] == stem:
                            (d / Path(m).name).write_bytes(iz.read(m))
                    f = d / Path(shp[0]).name
                    try:
                        g = gpd.read_file(f)
                    except Exception:                       # noqa: BLE001 — .cpg 없는 cp949
                        g = gpd.read_file(f, encoding="cp949")
                    g = g.set_crs(5186, allow_override=True)
                    parts.append(g[g.intersects(keep)])
    if not parts:
        raise SystemExit("★ NGII 건물 레이어(B0010000)를 하나도 못 읽었다 — raw V-WORLD 묶음을 확인한다")
    b = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=5186)
    return b[b.geom_type.isin(["Polygon", "MultiPolygon"])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    emd = gpd.read_file(P / "boundary_emd.geojson").to_crs(5186)
    emd = emd[emd["EMD_CD"] == EMD_CD]
    corr = gpd.read_file(P / "corridor_5186.gpkg").to_crs(5186)
    st = gpd.read_file(P / "fire_station.geojson").to_crs(5186)
    keep = judgment_scope(emd.geometry.iloc[0], list(corr.geometry), st.geometry)

    ngii = gpd.read_file(P / "ngii1k_center_5186.gpkg").to_crs(5186)
    rl = gpd.read_file(P / "road_link_5186.gpkg").to_crs(5186)
    seg = gpd.read_file(P / "segments_5186.gpkg").to_crs(5186)
    juso = gpd.read_file(P / "building_5186.gpkg").to_crs(5186)
    juso = juso[juso.intersects(keep)]
    nb = ngii_buildings(keep)
    print(f"판정 범위 {keep.area/1e6:.3f}km² · 현행 구간 {len(seg):,} · NGII 건물 {len(nb):,} · 도로명주소 건물 {len(juso):,}")

    edges = S.build(ngii, rl, keep)
    by = edges.groupby("src")["length_m"].agg(["size", "sum"])
    print(f"하이브리드 엣지 {len(edges):,} · {edges.length_m.sum()/1e3:.1f}km · 중앙 {edges.length_m.median():.1f}m — "
          + " · ".join(f"{k} {int(r['size']):,}({r['sum']/1e3:.1f}km)" for k, r in by.iterrows()))
    print(f"  폭≥6 쌍선 후보 {int(edges['pair'].sum())} · 3m 미만 {int((edges.length_m < 3).sum())}")

    t = S.compare(seg, edges, ngii_bldg=nb, juso_bldg=juso)
    matched = t.share >= S.MATCH_SHARE
    print(f"\n매칭 {int(matched.sum()):,}/{len(t):,} ({100*matched.mean():.1f}%) · 이동 중앙 {t.loc[matched, 'offset_m'].median():.2f}m · "
          f"p90 {t.loc[matched, 'offset_m'].quantile(.9):.2f}m")
    print(f"건물 관통 >1m — 현행: NGII 건물 {int((t.bldg_ngii_m > 1).sum())} · 도로명주소 건물 {int((t.bldg_juso_m > 1).sum())} · "
          f"매칭 엣지: NGII 건물 {int((t.edge_bldg_ngii_m > 1).sum())}")

    reasons = ["멀리", "건물관통", "폭불일치", "짝없음", "쌍선"]
    tab = pd.DataFrame({r: t[t.suspect.str.contains(r)].groupby("verdict").size() for r in reasons}).fillna(0).astype(int)
    tab.loc["합"] = tab.sum()
    print("\n의심 사유 × 현행 판정 (한 구간이 여러 사유를 가질 수 있다)\n" + tab.to_string())
    any_s = t.suspect.ne("")
    print(f"의심 구간 {int(any_s.sum())} / {len(t)} — 판정별 " + json.dumps(t[any_s].groupby("verdict").size().to_dict(), ensure_ascii=False))

    t["_w"] = (pd.to_numeric(t.edge_width, errors="coerce") - pd.to_numeric(t.width_min_m, errors="coerce")).abs()
    # ★ 위치 증거(멀리 · 건물관통)가 앞 — 폭 차이는 좁아지는 골목마다 나서 혼자서는 약하다(skeleton.priority)
    top = t[any_s].sort_values(["priority", "_w", "bldg_ngii_m"], ascending=False).head(a.top)
    cols = ["seg_uid", "road_name", "verdict", "width_min_m", "edge_width", "offset_m", "share", "bldg_ngii_m", "edge_src",
            "priority", "suspect"]
    print(f"\n의심 상위 {a.top}\n" + top[cols].to_string(index=False))

    OUT.mkdir(parents=True, exist_ok=True)
    t.drop(columns="_w").to_csv(OUT / "compare.csv", index=False, encoding="utf-8-sig")
    edges.to_file(OUT / "skeleton_5186.gpkg", driver="GPKG", layer="skeleton")
    summary = {
        "segments": len(t), "matched": int(matched.sum()), "edges": len(edges),
        "edges_by_src": {k: int(v) for k, v in by["size"].items()},
        "suspect": int(any_s.sum()), "suspect_by_reason": {r: int(t.suspect.str.contains(r).sum()) for r in reasons},
        "suspect_by_verdict": {k: int(v) for k, v in t[any_s].groupby("verdict").size().items()},
        "params": {"COVER_D": S.COVER_D, "GAP": S.GAP, "MATCH_R": S.MATCH_R,
                   "MATCH_ANGLE": S.MATCH_ANGLE, "MATCH_SHARE": S.MATCH_SHARE},
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n→ {OUT.relative_to(ROOT)}/compare.csv · skeleton_5186.gpkg · summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
ingest.py — data/raw 원본을 동명동 범위 표준 산출물로 변환한다.

원칙
  1. data/raw 는 불변. 어떤 코드도 여기에 쓰지 않는다.
  2. 모든 입력에 SHA-256을 찍는다. 원본이 바뀌면 즉시 드러난다.
  3. 좌표계는 sources.yaml 값으로 '정의'한 뒤 표준으로 '변환'한다.
     set_crs(정의) → to_crs(변환). 순서 바뀌면 전부 어긋난다.
  4. 산출물은 두 벌. *_5186.gpkg(계산용) + *.geojson(표출용).
  5. 실행 기록 전체가 data/processed/_manifest.json 에 남는다.

사용
    python src/etl/ingest.py
    python src/etl/ingest.py --only road_link ngii_road
    python src/etl/ingest.py --check          # 체크섬만 검증
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml
from pyproj import Transformer
from shapely import make_valid

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
sys.path.insert(0, str(Path(__file__).parent))

CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"
# 동명동 + 여유. 행정구역경계(전자지도 승인 대기) 확보 시 정식 폴리곤으로 교체할 것.
BBOX_4326 = (126.907, 35.140, 126.940, 35.162)


def sha256(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def bbox_in(crs: str):
    t = Transformer.from_crs(CRS_W, crs, always_xy=True)
    x0, y0 = t.transform(BBOX_4326[0], BBOX_4326[1])
    x1, y1 = t.transform(BBOX_4326[2], BBOX_4326[3])
    return (x0, y0, x1, y1)


def save(gdf: gpd.GeoDataFrame, key: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    gdf.to_crs(CRS_M).to_file(OUT / f"{key}_5186.gpkg", driver="GPKG", layer=key)
    gdf.to_crs(CRS_W).to_file(OUT / f"{key}.geojson", driver="GeoJSON")
    return {"features": len(gdf), "geom": sorted(set(gdf.geom_type)),
            "columns": [c for c in gdf.columns if c != "geometry"]}


# ── 소스별 로더 ───────────────────────────────────────────────
def load_shp_in_zip(zp: Path, inner: str, crs: str, enc: str, tmp: Path):
    with zipfile.ZipFile(zp) as z:
        z.extractall(tmp)
    p = next(tmp.rglob(inner))
    g = gpd.read_file(p, bbox=bbox_in(crs), encoding=enc)
    return g.set_crs(crs, allow_override=True)


def load_csv_points(p: Path, xcol: str, ycol: str, enc: str, filt=None):
    df = pd.read_csv(p, encoding=enc, dtype=str, low_memory=False)
    if filt:
        df = filt(df)
    df = df.dropna(subset=[xcol, ycol])
    df[xcol] = pd.to_numeric(df[xcol], errors="coerce")
    df[ycol] = pd.to_numeric(df[ycol], errors="coerce")
    df = df.dropna(subset=[xcol, ycol])
    df = df[df[xcol].between(BBOX_4326[0], BBOX_4326[2])
            & df[ycol].between(BBOX_4326[1], BBOX_4326[3])]
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[xcol], df[ycol]),
                            crs=CRS_W)


def build(key: str, e: dict, tmp: Path) -> dict:
    hits = sorted(RAW.glob(e["file"]))
    if not hits:
        return {"key": key, "status": "MISSING", "file": e["file"]}
    src = hits[0]
    rec = {"key": key, "source_file": e["file"], "source_sha256": sha256(src),
           "source_crs": e["crs"], "license": e.get("license", ""),
           "url": e.get("url", "")}
    kind = e["kind"]

    if kind == "shp_zip":
        g = load_shp_in_zip(src, e["layer"], e["crs"], e.get("encoding", "cp949"), tmp)

    elif kind == "shp_zip_multi":            # 수치지도 4도엽 병합
        parts = []
        for z in sorted(RAW.glob(e["file"])):
            with zipfile.ZipFile(z) as zf:
                zf.extractall(tmp / z.stem)
            p = tmp / z.stem / e["layer"]
            parts.append(gpd.read_file(p, encoding=e.get("encoding", "utf-8")))
        g = pd.concat(parts).pipe(gpd.GeoDataFrame, crs=parts[0].crs)
        g = g.set_crs(e["crs"], allow_override=True)
        b = bbox_in(e["crs"])
        g = g.cx[b[0]:b[2], b[1]:b[3]].copy()
        g["geometry"] = g.geometry.apply(make_valid).buffer(0)
        rec["source_sha256"] = ",".join(sha256(z)[:16] for z in sorted(RAW.glob(e["file"])))

    elif kind == "csv_points":
        g = load_csv_points(src, e["x_col"], e["y_col"], e.get("encoding", "utf-8"))

    elif kind == "csv_points_in_zip":
        with zipfile.ZipFile(src) as z:
            name = [n for n in z.namelist() if e["inner_contains"] in n][0]
            parts = []
            for c in pd.read_csv(io.TextIOWrapper(z.open(name), encoding="utf-8"),
                                 chunksize=200_000, dtype=str, low_memory=False):
                c[e["x_col"]] = pd.to_numeric(c[e["x_col"]], errors="coerce")
                c[e["y_col"]] = pd.to_numeric(c[e["y_col"]], errors="coerce")
                c = c[c[e["x_col"]].between(BBOX_4326[0], BBOX_4326[2])
                      & c[e["y_col"]].between(BBOX_4326[1], BBOX_4326[3])]
                if len(c):
                    parts.append(c)
        df = pd.concat(parts)
        g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[e["x_col"]], df[e["y_col"]]),
                             crs=CRS_W)

    elif kind == "dbf_in_zip":               # 회전제한 — 지오메트리 없음
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        p = next(tmp.rglob(e["layer"]))
        t = gpd.read_file(p).drop(columns="geometry", errors="ignore")
        # 동명동 노드로 한정 (node_point가 먼저 만들어져 있어야 함)
        np_path = OUT / "node_point_5186.gpkg"
        if np_path.exists() and "NODE_ID" in t.columns:
            ids = set(gpd.read_file(np_path)["NODE_ID"])
            t = t[t["NODE_ID"].isin(ids)]
        t.to_csv(
            OUT / f"{key}.csv", index=False, encoding="utf-8-sig")
        rec |= {"status": "OK", "features": len(t), "geom": [],
                "columns": list(t.columns), "outputs": [f"{key}.csv"]}
        return rec

    elif kind == "csv_table":                # 좌표 없는 표 — 그대로 복사
        d = pd.read_csv(src, encoding=e.get("encoding", "cp949"), dtype=str)
        d.to_csv(OUT / f"{key}.csv", index=False, encoding="utf-8-sig")
        rec |= {"status": "OK", "features": len(d), "geom": [],
                "columns": list(d.columns), "outputs": [f"{key}.csv"]}
        return rec

    else:
        raise ValueError(f"unknown kind: {kind}")

    rec |= {"status": "OK"} | save(g, key)
    rec["outputs"] = [f"{key}.geojson", f"{key}_5186.gpkg"]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    tmp = ROOT / ".work"
    tmp.mkdir(exist_ok=True)
    results = []

    for key, e in cfg["datasets"].items():
        if a.only and key not in a.only:
            continue
        if a.check:
            hits = sorted(RAW.glob(e["file"]))
            results.append({"key": key, "found": len(hits),
                            "sha256": [sha256(h)[:16] for h in hits]})
            print(f"[{'OK ' if hits else 'MISS'}] {key:20} {len(hits)}개")
            continue
        try:
            r = build(key, e, tmp)
        except Exception as ex:                             # noqa: BLE001
            r = {"key": key, "status": "FAIL", "error": f"{type(ex).__name__}: {ex}"}
        print(f"[{r.get('status','-'):7}] {key:20} {r.get('features',''):>8} feat")
        results.append(r)

    shutil.rmtree(tmp, ignore_errors=True)   # 압축 해제 잔여물 정리

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_manifest.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "bbox_4326": BBOX_4326,
        "standard_crs": {"metric": CRS_M, "display": CRS_W},
        "datasets": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT/'_manifest.json'}")


if __name__ == "__main__":
    main()

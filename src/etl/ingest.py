#!/usr/bin/env python3
"""
ingest.py — data/raw 원본을 동명동 범위 표준 산출물로 변환한다.


IN    sources.yaml (대장) · $FIRE_LANE_DATA/raw/**  (불변)
OUT   data/processed/<key>_5186.gpkg + <key>.geojson  (19종)
      data/processed/_manifest.json                    실행 기록 · 계보 정본
PARAM sources.yaml 의 datasets.<key>.contract 블록

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
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW, PROCESSED, WEB  # noqa: E402
OUT = PROCESSED


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


def sha_of(p: Path) -> str:
    """파일이면 그 해시, 디렉터리면 하위 파일 해시들의 해시.

    도엽 디렉터리(ngii1k)처럼 '여러 파일이 한 데이터셋'인 경우가 있다.
    도엽 한 장이 빠지거나 연도가 바뀌면 여기서 드러나야 한다.
    """
    if p.is_file():
        return sha256(p)
    files = sorted(x for x in p.rglob("*") if x.is_file() and not x.name.startswith("_"))
    h = hashlib.sha256()
    for f in files:
        h.update(f.relative_to(p).as_posix().encode())
        h.update(sha256(f).encode())
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


def read_csv_any(p: Path, enc: str | None = None, **kw):
    """인코딩을 자동 판별해 읽는다.

    ★ 같은 데이터셋도 다운로드 시점에 따라 인코딩이 바뀐다.
      공공데이터포털 CSV 가 UTF-8 이었다가 CP949 로 내려오는 일이 흔하다.
      sources.yaml 의 encoding 을 우선 시도하고, 실패하면 순서대로 넘어간다.
    """
    cands = [enc] if enc else []
    cands += ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last = None
    for c in dict.fromkeys(x for x in cands if x):
        try:
            return pd.read_csv(p, encoding=c, **kw)
        except (UnicodeDecodeError, LookupError) as ex:
            last = ex
    raise last


def load_csv_points(p: Path, xcol: str, ycol: str, enc: str, filt=None):
    df = read_csv_any(p, enc=enc, dtype=str, low_memory=False)
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
    rec = {"key": key, "source_file": e["file"], "source_sha256": sha_of(src),
           # csv_table / raw_only 는 좌표가 없다. crs 를 필수로 두면 거기서 죽는다.
           "source_crs": e.get("crs", ""), "license": e.get("license", ""),
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
        # ★ buffer(0) 은 폴리곤 자기교차 정리용이다. LineString 에 걸면
        #   빈 폴리곤이 되어 전멸한다. ngii_road_center(선)가 0건이던 원인이다.
        g["geometry"] = g.geometry.apply(make_valid)
        if g.geom_type.isin(("Polygon", "MultiPolygon")).any():
            g["geometry"] = g.geometry.buffer(0)
        rec["source_sha256"] = ",".join(sha256(z)[:16] for z in sorted(RAW.glob(e["file"])))

    elif kind in ("ngii1k", "ngii_1k", "shp_dir"):                  # 수치지형도 1:1,000 도엽 묶음
        # NGI(텍스트) / SHP 혼재라 GDAL 로 못 읽는다. ngii1k.py 가 파싱한다.
        # 여기서 호출하는 이유: 손으로 따로 돌리면 파이프라인이 재현되지 않는다.
        # ★ 2026-08-17. 여기가 두 가지로 깨져 있었다.
        #   1) read_sheet 는 (geom, attrs) 튜플을 내는데 geom 으로 받아
        #      'tuple' object has no attribute 'geom_type' 로 매 실행 FAIL 했다.
        #      _manifest.json 에 FAIL 이 적힌 채 파이프라인은 OK 를 찍었다.
        #   2) 설령 통과해도 src 컬럼만 만들어 도로폭·일방통행을 통째로 버렸다.
        #      그래서 사람이 ngii1k.py 를 손으로 돌려야 했고, 폭 주 소스가
        #      파이프라인 밖에서 만들어지고 있었다("파이프라인은 한 명령이다"가
        #      폭에 대해서는 거짓이었다).
        #   프레임 조립을 ngii1k.build 하나로 합쳐 두 곳에서 만들지 않는다.
        from ngii1k import collect, read_sheet, build, LAYERS
        want = list(LAYERS)
        # ★ 2026-08-18. src = hits[0] 라 글롭이 여러 zip 을 찾아도 첫 개만 썼다.
        #   SHP 판(74도엽)만 들어가고 NGI 보완분(북부 12도엽)이 통째로 무시됐다.
        #   대장이 글롭이면 글롭 전체가 소스다.
        sheets = collect(hits if len(hits) > 1 else src)
        if not sheets:
            raise FileNotFoundError(f"도엽 없음: {src}")
        acc = {k: [] for k in want}
        per_sheet = {}
        for sh, (year, sk, path) in sorted(sheets.items()):
            got = read_sheet(sk, path, want)
            for k, v in got.items():
                acc[k] += v
            per_sheet[sh] = {"year": year, "kind": sk,
                             **{k: len(got[k]) for k in want}}
        # ★ 도엽별 0건은 오류가 아니다(2026-08-17 정정). ngii1k.main() 주석 참조.
        #   V-WORLD 74도엽은 동구 전역이라 빈 도엽이 정상적으로 섞인다.
        #   합계 0 만 오류로 본다. 도엽 목록은 대장에 남긴다.
        empty = [sh for sh, v in per_sheet.items() if v["A0010000"] == 0]
        rec["empty_sheets"] = empty
        if not acc["A0010000"]:
            raise ValueError("도로경계 총 0건 — 레이어 코드/압축 구조 확인")
        rec["sheets"] = per_sheet
        outs = []
        made = []
        for lay in want:
            gg = build(lay, acc[lay])       # 타입 필터로 전멸하면 여기서 세운다
            if gg is None:
                continue
            k2 = LAYERS[lay][0]
            info = save(gg, k2)
            outs += [f"{k2}.geojson", f"{k2}_5186.gpkg"]
            made.append(k2)
            if k2 == key:
                rec |= info
        # 폭 주 소스와 속성 소스는 반드시 나와야 한다.
        for must in ("ngii1k", "ngii1k_center"):
            if must not in made:
                raise ValueError(f"{must} 산출 0건 — GEOM_OF / 레이어 코드 확인")
        rec |= {"status": "OK", "outputs": outs, "layers": made}
        return rec

    elif kind in ("csv_points", "csv_point"):
        g = load_csv_points(src, e["x_col"], e["y_col"], e.get("encoding", "utf-8"))

    elif kind == "csv_points_in_zip":
        with zipfile.ZipFile(src) as z:
            # zip 내부 한글 파일명이 CP437 로 깨져 들어온다.
            # 원래 CP949 이므로 되돌려서 매칭한다.
            def _kr(n: str) -> str:
                try:
                    return n.encode("cp437").decode("cp949")
                except Exception:
                    return n
            want = e["inner_contains"]
            hits = [n for n in z.namelist() if want in n or want in _kr(n)]
            if not hits:
                raise FileNotFoundError(
                    f"zip 안에 '{want}' 를 포함한 파일이 없다. "
                    f"내부: {[_kr(n) for n in z.namelist()[:5]]}")
            name = hits[0]
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

    elif kind == "json_points":              # 공공데이터포털 표준데이터 JSON
        # 같은 데이터셋이 CSV 로 오다가 JSON 으로 바뀌기도 한다.
        # {"fields":[...], "records":[...]} 구조다.
        import json as _json
        raw = _json.loads(src.read_text(encoding="utf-8"))
        rows = raw.get("records", raw if isinstance(raw, list) else [])
        df = pd.DataFrame(rows).astype(str)
        xc, yc = e["x_col"], e["y_col"]
        df[xc] = pd.to_numeric(df[xc], errors="coerce")
        df[yc] = pd.to_numeric(df[yc], errors="coerce")
        df = df.dropna(subset=[xc, yc])
        df = df[df[xc].between(BBOX_4326[0], BBOX_4326[2])
                & df[yc].between(BBOX_4326[1], BBOX_4326[3])]
        g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[xc], df[yc]), crs=CRS_W)

    elif kind == "csv_table":                # 좌표 없는 표 — 그대로 복사
        d = read_csv_any(src, e.get("encoding"), dtype=str)
        d.to_csv(OUT / f"{key}.csv", index=False, encoding="utf-8-sig")
        rec |= {"status": "OK", "features": len(d), "geom": [],
                "columns": list(d.columns), "outputs": [f"{key}.csv"]}
        return rec

    elif kind == "raw_only":                 # 읽지 않는다. 존재만 기록한다.
        # 다른 스크립트가 raw 를 직접 읽는 경우다(예: terrain.py 의 DEM).
        # 여기서 변환하지 않으므로 SKIP 으로 남긴다. FAIL 이 아니다.
        rec |= {"status": "SKIP", "features": "", "geom": [],
                "note": "raw_only — 별도 스크립트가 직접 읽는다", "outputs": []}
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
            # ★ FAIL 이면 이 key 의 기존 산출물을 개명해 하류에서 떼어낸다.
            #   2026-08-17 ngii1k FAIL 때 8/13 gpkg 가 남아 segments 가 그것으로
            #   판정을 냈고(1093), 다음 날 진짜 실행(1091)과 갈려 "기계 간
            #   재현성 붕괴"로 오인해 반나절을 태웠다. 로직은 guards.py 정본.
            from guards import quarantine_stale
            staled = quarantine_stale(OUT, key)
            if staled:
                r["staled"] = staled
                print(f"          ★ 옛 산출물 {len(staled)}개 격리(.stale_) — 하류가 못 읽는다")
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

#!/usr/bin/env python3
"""
ingest.py — data/raw 원본을 동명동 범위 표준 산출물로 변환한다.


IN    sources.yaml (대장) · $FIRE_LANE_DATA/raw/**  (불변)
OUT   data/processed/<key>_5186.gpkg + <key>.geojson  (20종)
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
    python -m firelane.ingest
    python -m firelane.ingest --only road_link ngii_road
    python -m firelane.ingest --check          # 체크섬만 검증
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml
from pyproj import Transformer
from shapely import make_valid

from firelane import manifest
from firelane.paths import PROCESSED, RAW, ROOT

OUT = PROCESSED



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
    # ★ 2026-08-18. 쓰기 전에 파일을 지운다.
    #   GPKG 는 컨테이너다. to_file(layer=key) 는 그 **레이어**를 덮어쓸 뿐
    #   파일 안의 다른 레이어는 건드리지 않는다. layer= 를 안 쓰던 시절의
    #   레이어가 남아 있었고, GeoPandas 는 레이어를 지정하지 않으면 첫
    #   레이어를 읽는다. 그래서 segments 가 08-17 판 ngii1k_5186(6,675개)을
    #   읽었고, 08-18 산출 14,336 개는 옆 레이어로 놀고 있었다.
    #
    #     More than one layer found in 'ngii1k_5186.gpkg':
    #       'ngii1k_5186' (default), 'ngii1k'
    #
    #   결과: 스코프 북부 미커버 13.4%. 파일은 갱신됐고 mtime 은 새것이고
    #   status 는 OK 라 어떤 가드도 보지 못했다. 근거는 DECISIONS 08-18.
    #
    #   한 파일 = 한 레이어를 불변식으로 세운다. 컨테이너에 누적하지 않는다.
    # ★ 2026-08-22. 무효 기하를 여기서 한 번에 잡는다.
    #   sources.yaml 의 road_rw 에 이미 경고가 적혀 있었다 —
    #   "winding order 오류 폴리곤 포함. make_valid + buffer(0) 없이
    #    unary_union 하면 …". 그런데 make_valid 는 shp_zip_multi 분기에만
    #   걸려 있었고 road_rw(shp_zip)는 그냥 통과했다. **대장의 note 는
    #   사람이 읽는 글이지 강제자가 아니다**(§5-6 과 같은 계열).
    #
    #   실제로 터졌다: road_rw 를 union 하면
    #   TopologyException: side location conflict.
    #   더 나쁜 것은 예외가 아니라 조용한 오답이 나오는 경우다 —
    #   나비넥타이 폴리곤을 그냥 union 하면 면적이 정답의 2/3 로 나온다.
    #
    #   kind 별로 배선하지 않고 save() 에 건다. 모든 소스의 공통 관문이다.
    _inv = ~gdf.geometry.is_valid & gdf.geometry.notna()
    if _inv.any():
        gdf = gdf.copy()
        gdf.loc[_inv, "geometry"] = gdf.loc[_inv, "geometry"].apply(make_valid)
        _still = int((~gdf.geometry.is_valid & gdf.geometry.notna()).sum())
        print(f"          · 무효 기하 {int(_inv.sum())}건 make_valid"
              + (f" · 잔여 {_still}건 ★" if _still else ""))

    _gpkg = OUT / f"{key}_5186.gpkg"
    _gpkg.unlink(missing_ok=True)
    gdf.to_crs(CRS_M).to_file(_gpkg, driver="GPKG", layer=key)
    gdf.to_crs(CRS_W).to_file(OUT / f"{key}.geojson", driver="GeoJSON")
    return {"features": len(gdf), "geom": sorted(set(gdf.geom_type)),
            # ★ 대장에 남긴다. 어떤 소스가 얼마나 깨져 있었는지가
            #   다음 사람에게 필요한 정보다.
            "invalid_fixed": int(_inv.sum()),
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
    # ★ 2026-08-23. glob 이 여러 개를 잡으면 **정렬 첫 번째**가 쓰인다.
    #   날짜가 파일명에 있으므로 그것은 대개 **옛 판**이다.
    #   2026-08-23 에 `gjcity_parking_enforce_dongu_20250226.csv` 를 새로
    #   편입했는데 파이프라인은 계속 20240108 을 읽었고 아무도 몰랐다.
    #
    #   여기서 자동으로 최신을 고르지 않는다. 그러면 raw 에 파일 하나를
    #   떨구는 것만으로 산출물이 조용히 바뀐다 — 대장이 정본이라는 원칙이
    #   깨진다(§18-3). 대신 **시끄럽게 알리고** 사람이 대장을 고치게 한다.
    # ★ 2026-08-23 정정. 처음엔 `hits > 1` 이면 무조건 경고했다. 오탐이었다.
    #   kind 마다 여러 파일이 **정상**인 것이 있다.
    #
    #     shp_zip_multi   도엽 여러 zip 을 병합한다. 여러 개가 정상
    #     shp_dir         ngii1k.py 가 묶음 전체를 편다. 여러 개가 정상
    #     raw_only        읽지 않는다. ortho.py 가 4도엽을 직접 읽는다
    #
    #   실전에서 5종이 경고를 냈고 그중 4종이 오탐이었다.
    #   **매번 뜨는 경고는 아무도 안 읽는다** — 그러면 진짜 하나를 놓친다.
    #   `hits[0]` 만 쓰는 kind 에서만 말한다.
    SINGLE_PICK = {"shp_zip", "csv_points", "csv_point", "csv_points_in_zip",
                   "dbf_in_zip", "json_points", "csv_table"}
    if len(hits) > 1 and e["kind"] in SINGLE_PICK:
        rest = ", ".join(x.name for x in hits[1:])
        print(f"  ★ {key}: 대장 glob 이 {len(hits)}개를 잡는데 "
              f"kind={e['kind']} 는 하나만 쓴다 → {src.name}")
        print(f"     쓰이지 않는 것: {rest}")
        print("     날짜가 파일명에 있으므로 정렬 첫 번째는 대개 **옛 판**이다.")
        print("     sources.yaml 의 file 을 하나로 좁혀라.")

    # ── FL_EXT_COLLISION ─────────────────────────────────────
    # 줄기가 같고 확장자만 다른 파일이 raw 에 함께 있으면, 어느 것을
    # 읽는지가 **사전순 우연**으로 정해진다. kind 와 무관하다.
    #
    # 2026-08-25 에 KFS 규격서를 PDF 판으로 다시 읽고 결론을 뒤집었는데,
    # 대장이 `..._20251224.*` 라 두 판을 한 항목으로 보고 있었다.
    # raw_only 는 위 SINGLE_PICK 경고 밖이라 아무 말도 안 났을 것이다.
    _stems = {}
    for h in hits:
        _stems.setdefault(h.name.rsplit(".", 1)[0], []).append(h.name)
    for _st, _fs in _stems.items():
        if len(_fs) > 1:
            print(f"  ★ {key}: 확장자만 다른 동명 파일 {len(_fs)}개 — "
                  f"{', '.join(sorted(_fs))}")
            print(f"     지금 읽는 것은 {src.name} 이고, 그 선택은 사전순이다.")
            print("     포맷이 다르면 다른 자산이다. 대장을 files: + primary:")
            print("     로 적어 못박아라(firelane.ledger 가 강제한다).")
    rec = {"key": key, "source_file": e["file"], "source_sha256": sha_of(src),
           "resolved": src.name,
           **({"ambiguous": [x.name for x in hits]} if len(hits) > 1 else {}),
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
        from firelane.ngii1k import LAYERS, build, collect, read_sheet
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

    elif kind == "csv_table_multi":          # 좌표 없는 표 여러 판 — 이어붙인다
        # ★ 2026-08-25. `csv_table` 은 hits[0] 하나만 읽는다. 같은 데이터셋이
        #   기간별로 나뉘어 오는 소스는 그 규칙에서 **옛 판만 읽힌다.**
        #   대장 note 와 contract 는 두 판을 전제하고 있었는데 파이프라인만
        #   한 판을 읽었다(DECISIONS §71).
        # ★ 판마다 없을 수 있는 컬럼은 **대장에 선언한다.** 코드에서 조용히
        #   봐주면 다음 판이 왔을 때 "이건 원래 없는 거였나" 를 다시 조사하게
        #   된다. 선언에 없는 컬럼이 다르면 여전히 세운다.
        optional = list((e.get("contract") or {}).get("optional_cols") or [])
        parts, filled = [], []
        cols = None
        for q in hits:
            d1 = read_csv_any(q, e.get("encoding"), dtype=str, low_memory=False)
            if cols is None:
                cols = list(d1.columns)
            elif list(d1.columns) != cols:
                only_new = [c for c in d1.columns if c not in cols]
                only_old = [c for c in cols if c not in d1.columns]
                # 선언된 것만 결손을 허용한다. 그것도 조용히는 아니다.
                undeclared = [c for c in only_new + only_old if c not in optional]
                if undeclared:
                    rec |= {"status": "FAIL", "features": "", "geom": [],
                            "note": f"{q.name} 컬럼 불일치 — 신규 {only_new} · 소실 {only_old}",
                            "outputs": []}
                    print(f"  ★ {key}: {q.name} 의 컬럼이 {hits[0].name} 과 다르다")
                    print(f"     신규 {only_new} · 소실 {only_old}")
                    print(f"     선언되지 않은 것: {undeclared}")
                    print("     이어붙이면 판이 섞인 채로 통과한다. 대장을 먼저 고쳐라.")
                    print("     없어도 되는 컬럼이면 contract.optional_cols 에 적어라.")
                    return rec
                for c2 in only_old:
                    # ★ NaN 이 아니라 빈 문자열. 이 표는 dtype=str 이라
                    #   결측 표현이 섞이면 하류에서 판별이 안 된다.
                    d1[c2] = ""
                    filled.append(f"{q.name}:{c2}")
                for c2 in only_new:
                    cols.append(c2)
                    for x in parts:
                        x[c2] = ""
                        filled.append(f"{x['_src'].iloc[0]}:{c2}")
                d1 = d1[cols]
            # 어느 판에서 온 행인지 산출물에 남긴다.
            d1["_src"] = q.name
            parts.append(d1)
        if filled:
            # R6 — 대체가 일어났다는 사실이 산출물에 남아야 한다.
            print(f"  · {key}: 선언된 결손 컬럼을 빈 값으로 채웠다 — "
                  + " · ".join(filled))
            rec["note"] = "optional_cols 결손 보정: " + ", ".join(filled)
        d = pd.concat(parts, ignore_index=True)
        d.to_csv(OUT / f"{key}.csv", index=False, encoding="utf-8-sig")
        rec["source_sha256"] = ",".join(sha256(q)[:16] for q in hits)
        rec["resolved"] = " + ".join(q.name for q in hits)
        rec.pop("ambiguous", None)          # 여러 개가 정상이다. 모호하지 않다
        print(f"  · {key}: {len(hits)}판 이어붙임 — "
              + " · ".join(f"{q.name} {len(x):,}행" for q, x in zip(hits, parts, strict=True)))
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
    # ★ 2026-08-23. 실패한 것만 다시 돌린다.
    #
    #   19종을 한 덩어리로 돌아서 **하나가 FAIL 하면 전체가 무효**였다.
    #   그리고 그 실패가 비결정적이다(PLAN §1-19) — 같은 입력·같은 코드로
    #   1회차 `turn_restriction`·`cctv`, 2회차 통과, 3회차 `ngii_road`,
    #   4회차 `node_link`. 하루에 세 번 났고 매번 다른 소스였다.
    #
    #   그때마다 200초를 다시 태웠다. 성공한 18종은 산출물이 멀쩡한데도.
    #   `_manifest.json` 에 소스별 status 가 이미 있으므로 읽어서 고르면 된다.
    ap.add_argument("--retry-failed", action="store_true",
                    help="지난 실행에서 FAIL·MISSING 인 소스만 다시 돌린다")
    ap.add_argument("--keep-work", action="store_true",
                    help=".work 압축 해제분을 남긴다 (다음 실행이 빨라진다)")
    a = ap.parse_args()

    if a.retry_failed:
        man0 = OUT / "_manifest.json"
        if not man0.exists():
            sys.exit("★ _manifest.json 이 없다. 전량을 한 번 돌려라.")
        prev0 = json.loads(man0.read_text(encoding="utf-8")).get("datasets", [])
        bad = [r["key"] for r in prev0
               if isinstance(r, dict) and r.get("status") in ("FAIL", "MISSING")]
        if not bad:
            print("실패한 소스가 없다. 할 일이 없다.")
            return 0
        print(f"지난 실행 실패 {len(bad)}종만 다시 돌린다: {', '.join(bad)}")
        a.only = bad

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
            from firelane.guards import quarantine_stale
            staled = quarantine_stale(OUT, key)
            if staled:
                r["staled"] = staled
                print(f"          ★ 옛 산출물 {len(staled)}개 격리(.stale_) — 하류가 못 읽는다")
        print(f"[{r.get('status','-'):7}] {key:20} {r.get('features',''):>8} feat")
        results.append(r)

    # ★ 2026-08-23. 매 실행 지웠더니 `캐시 0` 이 매번 떴다.
    #   `ngii1k` 묶음만 도엽 74장 + NGI 143장을 다시 푼다 — ingest 180초의
    #   대부분이 여기다. 그리고 `--retry-failed` 로 한 소스만 돌릴 때도
    #   그 소스가 쓰는 zip 을 통째로 다시 풀어야 했다.
    #
    #   ★ 지우는 것이 안전한 이유는 있었다 — 2026-08-13 에 `_unz_*` 8폴더
    #     1,570파일이 raw 옆에 풀려 raw 파일 수가 40배로 보였다. 그래서
    #     `.work` 가 생겼다. **지금은 raw 밖이라 그 사고가 안 난다.**
    #     `tidy.py` 가 `.work` 를 정리 대상으로 알고 있으므로 쌓이지도 않는다.
    #
    #   실패했을 때는 지운다. 반쯤 풀린 것이 다음 실행을 오염시킨다.
    _failed = any(r.get("status") == "FAIL" for r in results)
    if _failed or not a.keep_work:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        _n = sum(1 for _ in tmp.rglob("*") if _.is_file())
        print(f"  · .work 유지 {_n:,}파일 — 다음 실행이 빨라진다 "
              f"(정리: uv run python tools/tidy.py --yes)")

    OUT.mkdir(parents=True, exist_ok=True)
    man = OUT / "_manifest.json"

    # ★ 2026-08-22. --only 가 대장을 통째로 덮어쓰고 있었다.
    #   `--only ngii_road` 한 번에 27개 기록이 1개로 줄었고, 그 다음
    #   segments 의 계보 검사가 ngii1k=None · road_link=None ... 을 보고
    #   정당하게 거부했다. 디스크에 gpkg 는 멀쩡히 있는데 대장만 사라진 것이다.
    #
    #   §7 의 OOM 우회법(--only 로 실패분만 → 그 다음 전량)이 굴러간 이유는
    #   **뒤에 전량을 다시 돌려 대장을 재구축했기 때문**이다. 중간 상태는
    #   파괴적이었고 아무도 몰랐다. OOM 이 잦은 5GB 환경에서 --only 는
    #   우회로가 아니라 함정이다.
    #
    #   이제 기존 대장을 읽어 이번에 처리한 key 만 갈아끼운다.
    #   ★ 순서는 sources.yaml 을 따른다. 갱신 순서로 쓰면 같은 내용인데도
    #     datasets 블록의 sha 가 달라져 계보가 오탐한다(§5-4 와 같은 함정).
    if a.only and man.exists():
        try:
            prev = json.loads(man.read_text(encoding="utf-8")).get("datasets", [])
        except Exception:                                   # noqa: BLE001
            prev = []
        merged = {r["key"]: r for r in prev if isinstance(r, dict) and "key" in r}
        merged.update({r["key"]: r for r in results})
        order = list(cfg["datasets"].keys())
        results = ([merged[k] for k in order if k in merged]
                   + [v for k, v in merged.items() if k not in order])
        print(f"  · 대장 병합: 기존 {len(prev)}종 중 {len(a.only)}종 갱신 "
              f"→ {len(results)}종 유지")

    # ★ 2026-08-25. 자기 것이 아닌 최상위 키를 보존한다.
    #   종전에는 대장을 통째로 덮어써 terrain · ortho 기록을 지웠다.
    #   전량 실행에서는 뒤 단계가 다시 넣어주므로 안 보였지만
    #   `--only ingest` 는 그 기록을 날린다.
    doc = {k: v for k, v in manifest.read(man).items()
           if k not in ("generated_at", "bbox_4326", "standard_crs", "datasets")}
    doc.update({
        "generated_at": datetime.now(UTC).astimezone().isoformat(),
        "bbox_4326": BBOX_4326,
        "standard_crs": {"metric": CRS_M, "display": CRS_W},
        "datasets": results,
    })
    # ★ 내용이 같으면 쓰지 않는다. 시각만 바뀌는 diff 가 커밋을 막았다.
    wrote = manifest.write_stable(man, doc)
    print(f"\n→ {man}" + ("" if wrote else "  (내용 동일 — 갱신 없음)"))

    # ★ FAIL 이 있으면 종료코드로 알린다. 종전에는 대장에만 적고 0 을
    #   반환해서 pipeline 의 `if r.returncode:` 가 안 걸렸다 — 실패가
    #   기록되는데 파이프라인은 초록불이었다(§5-2 와 같은 계열).
    #   2026-08-21 에 ngii_road 가 FAIL 한 채 ingest 가 OK 로 끝났고,
    #   계보 검사가 우연히 막아줬을 뿐이다.
    failed = [r["key"] for r in results if r.get("status") == "FAIL"]
    if failed:
        print(f"\n★ FAIL {len(failed)}종: {' · '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

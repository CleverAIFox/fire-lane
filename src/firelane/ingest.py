#!/usr/bin/env python3
"""
ingest.py — data/raw 원본을 동명동 범위 표준 산출물로 변환한다.


IN    sources.yaml (대장) · $FIRE_LANE_DATA/raw/**  (불변)
OUT   data/processed/<key>_5186.gpkg + <key>.geojson  (20종) — 예: building.geojson
      data/processed/_manifest.json
      ★ 하류가 이름으로 읽는 것 — boundary_emd.geojson · fire_station.geojson ·
        hydrant_point.geojson · cctv.geojson · poi_store.geojson ·
        road_intrvl.geojson · navi_build.csv · navi_jibun.csv · civil_office.geojson ·
        turn_restriction.csv · speedbump.csv · speed_cam.csv · nfa_dispatch_119.csv ·
        nfa_rescue.csv · nfa_fire_incident.csv · parking_enforce.csv.
        `pipeline.Step` 이 그 열여섯을 명시한다(목적지 색인 셋 2026-09-17 §181 ·
        회전제한 표 2026-09-22 §215-1 · 주변 사정 · 출동 이력 · 단속 여섯 §216-3)
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
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import yaml
from pyproj import Transformer
from shapely import make_valid

from firelane import ledger, manifest, prep
from firelane.encoding import CANDIDATES_CSV_READ
from firelane.paths import PROCESSED, RAW, ROOT

OUT = PROCESSED



CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"
# 동명동 + 여유. 행정구역경계(전자지도 승인 대기) 확보 시 정식 폴리곤으로 교체할 것.
# ★ 2026-09-16. 대장에서 읽는다(DECISIONS §169). 종전에는 여기 튜플이 박혀 있었고
#   `sources.yaml` 의 `bbox_4326` 과 **두 벌**이었다. 샤드 봉인지 cfg 칸은 대장 값을
#   재는데 실제 거르기는 이 튜플이 했다 — 대장만 고치면 샤드가 찢어져 다시 빌드하고도
#   산출은 그대로인, 근거와 실물이 갈린 상태였다.
BBOX_4326 = tuple(ledger.load()["bbox_4326"])


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
    # ★ 2026-09-17 (§182-6). `GeoSeries.notna()` 는 geopandas 가 빈 도형 의미를 바꾸면서 매 실행 경고를 낸다.
    #   뜻은 "없거나 비었으면 뺀다" 하나다 — shapely 로 직접 묻는다. 매번 뜨는 경고는 진짜 경고를 죽인다.
    _g = np.asarray(gdf.geometry.values, dtype=object)
    gdf = gdf[~(shapely.is_missing(_g) | shapely.is_empty(_g))].copy()
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
def unzip_own(zp: Path, tmp: Path) -> Path:
    """zip 을 **그 zip 만의 빈 폴더**에 푼다. 돌려준 폴더 안에서만 찾는다.

    ★ 2026-09-17 (DECISIONS §181-4 · G-22). 종전에는 모든 소스가 `.work` 한 곳에
      풀고 `tmp.rglob(layer)` 로 찾았다. 앞 소스가 푼 같은 이름의 shp · dbf 가 남아
      있으면 **엉뚱한 판을 조용히 읽는다** — `next()` 가 첫 것을 집기 때문이다.
      글롭 레이어(`*.shp`)는 앞 소스의 shp 전부와 겹친다.
    """
    d = tmp / "_zip" / zp.stem
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    with zipfile.ZipFile(zp) as z:
        z.extractall(d)
    return d


def load_shp_in_zip(zp: Path, inner: str, crs: str, enc: str, tmp: Path):
    tmp = unzip_own(zp, tmp)
    # ★ 2026-09-17 (DECISIONS §181-3). `layer` 가 글롭이면 **정확히 하나**여야 한다.
    #   민원행정기관 전자지도는 zip 안 한글 파일명이 CP437 로 깨져 이름으로 못 가리킨다.
    #   `next()` 로 첫 것을 집으면 둘째 shp 가 생겨도 조용히 하나만 읽는다.
    hits = sorted(tmp.rglob(inner))
    if len(hits) != 1:
        raise ValueError(f"{zp.name} 안 {inner} 가 {len(hits)}개다 — 하나여야 한다: "
                         f"{[h.name for h in hits][:6]}")
    p = hits[0]
    g = gpd.read_file(p, bbox=bbox_in(crs), encoding=enc)
    return g.set_crs(crs, allow_override=True)


def read_csv_any(p: Path, enc: str | None = None, **kw):
    """인코딩을 자동 판별해 읽는다.

    ★ 같은 데이터셋도 다운로드 시점에 따라 인코딩이 바뀐다.
      공공데이터포털 CSV 가 UTF-8 이었다가 CP949 로 내려오는 일이 흔하다.
      sources.yaml 의 encoding 을 우선 시도하고, 실패하면 순서대로 넘어간다.
    """
    cands = [enc] if enc else []
    cands += list(CANDIDATES_CSV_READ)
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


def paths_for(key: str, e: dict) -> list[Path]:
    """이 소스의 실물 경로. **입력 계층을 여기 한 곳에서 가른다.**

    ★ 2026-08-31. 종전에는 raw 하드코딩이 두 곳에 박혀 있었다.
      `layers.norm.migrated` 를 채워도 아무 일이 안 났고, `golden.py check` 는
      `segments.geojson` 하나만 보므로 **통과했다**(DECISIONS §77).
      선언이 실물보다 앞선 것이다. `tests/test_norm_wiring.py` 가 그 상태를
      이제 빨간불로 만든다.

    글롭은 raw 에서 푼다. raw 는 절대 수정하지 않으므로 항상 전량이 있고,
    norm 은 같은 상대 경로에 정규화 사본을 둔다. 상대 경로를
    `prep.source_path()` 에 넘기면 이관 여부에 따라 갈린다 — 선언은 됐는데
    실물이 없으면 거기서 `FileNotFoundError` 로 죽는다. **조용히 raw 로
    떨어지지 않는 것**이 이 함수의 요점이다.
    """
    if key not in prep.migrated():
        return ledger.paths_of(e, RAW)
    rels = [q.relative_to(RAW).as_posix() for q in ledger.paths_of(e, RAW)]
    if not rels:
        rels = [g for g in ledger.globs(e) if not any(c in g for c in "*?[")]
    return sorted({prep.source_path(key, r) for r in rels})


def build(key: str, e: dict, tmp: Path) -> dict:
    pats = ledger.globs(e)
    hits = paths_for(key, e)
    if not hits:
        return {"key": key, "status": "MISSING", "files": pats}
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
    SINGLE_PICK = ledger.SINGLE_PICK      # 정본은 ledger. 사본을 두지 않는다
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
    # ★ 2026-08-30. `.xml` `.prj` `.tfw` 등은 사이드카다 — 본체와 함께
    #   오는 부속이지 "포맷이 다른 별개 자산" 이 아니다. 종전에는
    #   ortho 가 매 실행 4건을 오탐했고, 매번 뜨는 경고는 진짜 하나를
    #   죽인다(바로 위 SINGLE_PICK 주석이 같은 이유로 적혀 있다).
    SIDECAR = {".xml", ".prj", ".tfw", ".cpg", ".aux", ".ovr", ".meta"}
    _stems = {}
    for h in hits:
        if h.suffix.lower() in SIDECAR:
            continue
        _stems.setdefault(h.name.rsplit(".", 1)[0], []).append(h.name)
    # ★ 2026-09-17 (§182-5). 대장이 `primary` 로 이미 못박았으면 판단이 끝난 것이다(kfs · mas 3건이
    #   `primary: hwp` 인데 매 실행 경고했다). 파일 이름이든 확장자든 그중 하나를 가리키면 조용히 한다.
    _pri = str(e.get("primary") or "").lower().lstrip(".")
    for _st, _fs in _stems.items():
        if len(_fs) > 1 and _pri and any(f.lower() == _pri or f.lower().endswith("." + _pri) for f in _fs):
            continue
        if len(_fs) > 1:
            print(f"  ★ {key}: 확장자만 다른 동명 파일 {len(_fs)}개 — "
                  f"{', '.join(sorted(_fs))}")
            print(f"     사전순 첫 번째는 {sorted(_fs)[0]} 다.")
            print("     포맷이 다르면 다른 자산이다. 대장을 files: + primary:")
            print("     로 적어 못박아라(firelane.ledger 가 강제한다).")
    crs = ledger.crs_of(e)
    rec = {"key": key, "source_files": pats, "source_sha256": sha_of(src),
           "resolved": src.name,
           **({"ambiguous": [x.name for x in hits]} if len(hits) > 1 else {}),
           # csv_table / raw_only 는 좌표가 없다. crs 를 필수로 두면 거기서 죽는다.
           # ★ license · url 은 대장에서 제거됐다. 빈 칸을 계보에 박으면
           #   "출처 불명" 과 "출처를 안 적는 정책" 이 같은 모양이 된다.
           "source_crs": crs}
    kind = e["kind"]

    if kind == "shp_zip":
        g = load_shp_in_zip(src, e["layer"], crs, e.get("encoding", "cp949"), tmp)

    elif kind == "shp_zip_multi":            # 수치지도 4도엽 병합
        # ★ 2026-08-30. 종전에는 zip 하나당 shp 하나를 가정하고
        #   `tmp/z.stem/e["layer"]` 한 장만 읽었다. `jijeok` 은 zip 하나
        #   안에 shp 7장이 들어 있고 — 대장이 `parts` 로 그것을 이미
        #   적고 있었다 — 첫 장만 읽혔다. 그 장이 BBOX 밖이라 0건이
        #   나왔고 status 는 OK 였다. **970MB 를 읽고 초록불이 났다.**
        #
        #   선언이 있는데 읽는 곳이 없으면 그 선언은 주석이다.
        #   여기서는 **실물을 세고 대장과 대조한다** — 이름 규칙을
        #   코드에 박으면(`f"{stem}({n}).shp"`) 원본 명명이 바뀔 때
        #   또 조용히 0건이 된다. 실물이 근거이고 대장이 기대치다.
        # ★ 2026-09-16. **읽는 시점에** bbox 를 건다(DECISIONS §168).
        #   종전에는 조각 7장 × 100만 필지를 전부 메모리에 올린 뒤 아래
        #   `.cx` 로 24,183건을 잘랐다 — `jijeok` OOM 의 진짜 자리가 여기다.
        #   `tools/jijeok_probe.py --extract` 가 같은 zip 을 bbox 로 읽어
        #   이미 살아 있었다. `shp_zip`(load_shp_in_zip)도 처음부터 이렇게 읽는다.
        #   bbox 필터는 GDAL 빌드에 따라 외곽 사각형 기준이라(GEOS 없으면)
        #   결과가 넓거나 같다. 정확한 교차는 아래 `.cx` 가 그대로 자른다 —
        #   산출 행 집합은 같다. `.cx` 를 지우면 테스트 카나리아가 운다.
        _want = e["layer"]
        _base = _want.rsplit(".", 1)[0]
        _bb = bbox_in(crs)
        parts, _read = [], []
        for z in hits:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(tmp / z.stem)
            found = sorted(x for x in (tmp / z.stem).rglob("*")
                           if x.suffix.lower() == ".shp"
                           and x.name.rsplit(".", 1)[0].startswith(_base))
            if not found:
                raise FileNotFoundError(
                    f"{z.name} 안에 {_want} 계열 shp 가 없다")
            for p in found:
                parts.append(gpd.read_file(
                    p, bbox=_bb, encoding=e.get("encoding", "utf-8")))
                _read.append(p.name)
        # ★ 2026-08-31. 종전에는 **zip 하나마다** `len(found) != len(parts)`
        #   를 봤다. `parts` 가 두 뜻으로 쓰이는 것을 못 본 것이다 —
        #
        #     jijeok      ['', '2'..'7']       zip 1개 **안의** shp 7장
        #     ngii_road   ['gj9708','gj9712']  zip 2개의 **도엽 토큰**
        #     ortho/dem   ['gj037'...]         같은 파일명 토큰(naming.part)
        #
        #   파일명 토큰이 다수이고 `naming.py` 가 `part` 를 그렇게 정의한다.
        #   zip 단위로 대조하면 도엽이 여럿인 소스는 **구조적으로 항상**
        #   실패한다(zip 2개 × 각 1장 → 1 != 2). 실제로 ngii_road ·
        #   ngii_road_center 가 그렇게 죽었고 소비자가 11곳이다.
        #
        #   대조는 유지하되 **합계로** 본다. 조용히 덜 읽는 것을 막는다는
        #   목적은 그대로고, 세는 단위만 zip → 전체로 옮긴다.
        _decl = e.get("parts")
        if _decl is not None and len(_read) != len(_decl):
            raise ValueError(
                f"{key}: 실물 shp 합계 {len(_read)}장 · 대장 parts "
                f"{len(_decl)}개. 어느 쪽이 맞는지 사람이 정해야 한다 — "
                f"수가 다르면 조용히 덜 읽는다 (zip {len(hits)}개: "
                f"{', '.join(z.name for z in hits)})")
        rec["parts_read"] = _read
        print(f"  · {key}: zip {len(hits)} · shp {len(_read)}장 "
              f"{sum(len(x) for x in parts):,}행")
        g = pd.concat(parts).pipe(gpd.GeoDataFrame, crs=parts[0].crs)
        g = g.set_crs(crs, allow_override=True)
        g = g.cx[_bb[0]:_bb[2], _bb[1]:_bb[3]].copy()
        # ★ buffer(0) 은 폴리곤 자기교차 정리용이다. LineString 에 걸면
        #   빈 폴리곤이 되어 전멸한다. ngii_road_center(선)가 0건이던 원인이다.
        g["geometry"] = g.geometry.apply(make_valid)
        if g.geom_type.isin(("Polygon", "MultiPolygon")).any():
            g["geometry"] = g.geometry.buffer(0)
        rec["source_sha256"] = ",".join(sha256(z)[:16] for z in hits)

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
            for c in pd.read_csv(io.TextIOWrapper(z.open(name),
                                     # ★ 대장의 encoding 을 읽는다.
                                     #   종전 utf-8 하드코딩은 대장에
                                     #   무엇을 적든 무시했다.
                                     encoding=e.get("encoding", "utf-8")),
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
        p = next(unzip_own(src, tmp).rglob(e["layer"]))      # §181-4 — 그 zip 폴더 안에서만
        t = gpd.read_file(p).drop(columns="geometry", errors="ignore")
        # 동명동 노드로 한정 — node_point 산출물을 읽는다.
        # ★ 2026-09-22 (DECISIONS §217-1 · PLAN §13 W11-1 닫음). 종전에는 산출물이 **없으면
        #   거르지 않고** 전국 44,125행을 냈다. 대장 순서상 node_point 가 앞이지만 그것이 FAIL 로
        #   격리(.stale_)되면 조용히 전국분이 나왔다 — 파이프라인 행수 관문(`pipeline` 의 87)이
        #   늦게 잡을 뿐이었다. 원인 자리에서 멈춘다.
        np_path = OUT / "node_point_5186.gpkg"
        if "NODE_ID" in t.columns:
            if not np_path.exists():
                raise FileNotFoundError(
                    f"{key}: node_point_5186.gpkg 가 없다 — 회전제한을 동명동 노드로 못 거른다. "
                    "node_point 를 먼저 ingest 한다(대장 순서 · --retry-failed)")
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

    elif kind == "json_table":               # 좌표 없는 JSON 표
        # ★ `json_points` 와 읽는 법이 같고 좌표만 없다. 건축물대장 표제부는
        #   {"Description": {…}, "Data": [...]} 라 래퍼 이름이 다르다.
        #   `records`(표준데이터) · `Data`(건축행정시스템) 둘 다 받는다.
        import json as _json
        raw = _json.loads(src.read_text(encoding=e.get("encoding", "utf-8")))
        rows = raw if isinstance(raw, list) else (
            raw.get("records") or raw.get("Data") or [])
        d = pd.DataFrame(rows).astype(str)
        d.to_csv(OUT / f"{key}.csv", index=False, encoding="utf-8-sig")
        rec |= {"status": "OK", "features": len(d), "geom": [],
                "columns": list(d.columns), "outputs": [f"{key}.csv"]}
        return rec

    elif kind == "text_table":               # 구분자 텍스트 — 헤더 없음
        # ★ **첫 행이 데이터다.** csv 로 읽으면 컬럼명으로 먹고 1행을 잃는다.
        #   컬럼명은 파일에 없고 제공처 활용가이드에만 있으므로 대장의
        #   `contract.columns` 를 쓴다. 없으면 c00·c01… 로 둔다 —
        #   **이름을 지어내지 않는다.**
        # ★ zip 안 어느 파일인지는 `inner_contains` 로 고른다. 전국 전체분이
        #   시도별로 나뉘어 있어 전부 읽으면 메모리가 터진다.
        # ★ `select` 는 **우리가 무엇을 취할지**다. `schema`(실물이 이렇게
        #   생겼다) 도 `contract`(이래야 한다) 도 아니라서 별도 필드다.
        #     select: {col: 0, prefix: "1221010800"}
        #
        # ★ 2026-09-07. 이 절단이 없으면 전국 132만 행이 processed 로
        #   통째로 들어간다. 실제로 쓰는 것은 동명동 2,078행이다.
        #   `its_nodelink`(258MB)가 "raw 는 원본 보존이 원칙이므로 여기서
        #   자르지 않는다 — 절단은 뒤 단계에서" 라고 적은 그 뒤 단계가
        #   여기다.
        #
        # ★ **법정동코드로 자른다. 동 이름으로 자르지 마라.**
        #   `c[3] == '동명동'` 으로 거르면 2,701 이 나오고 그중 623 이
        #   목포시 동명동이다(전남+광주 통합 파일). 행정동명까지 합치면
        #   5,683 이 된다. `select` 를 선언으로 두면 이 규칙이 주석이
        #   아니라 **실행되는 것**이 된다.
        con = e.get("contract") or {}
        sel = e.get("select") or {}
        delim = con.get("delimiter", "|")
        enc = e.get("encoding", "cp949")
        inner_key = e.get("inner_contains", "")
        cols = con.get("columns")

        def _read(fh):
            """청크로 읽으며 select 로 거른다.

            ★ 205MB · 1,327,372행을 한 번에 올리면 메모리가 튄다.
              `csv_points_in_zip` 이 "zip 안 대용량 CSV. 청크로 읽는다" 로
              같은 문제를 이미 겪었다.
            """
            it = pd.read_csv(fh, sep=delim, header=None, dtype=str,
                             encoding=enc, engine="python",
                             on_bad_lines="error", chunksize=200_000)
            keep, seen = [], 0
            for ch in it:
                seen += len(ch)
                if sel:
                    c = int(sel["col"])
                    if c >= ch.shape[1]:
                        raise ValueError(
                            f"{key}: select.col={c} 인데 실물은 {ch.shape[1]}열이다")
                    s = ch[c].astype(str)
                    if "prefix" in sel:
                        ch = ch[s.str.startswith(str(sel["prefix"]))]
                    elif "equals" in sel:
                        ch = ch[s == str(sel["equals"])]
                    else:
                        raise ValueError(
                            f"{key}: select 에 prefix 도 equals 도 없다")
                if len(ch):
                    keep.append(ch)
            out = (pd.concat(keep, ignore_index=True) if keep
                   else pd.DataFrame(columns=range(len(cols or []) or 1)))
            return out, seen

        if src.suffix.lower() == ".zip":
            with zipfile.ZipFile(src) as z:
                inner = [n for n in z.namelist()
                         if not n.endswith("/") and inner_key in n]
                if not inner:
                    raise ValueError(
                        f"{key}: zip 안에 inner_contains={inner_key!r} 가 없다")
                if len(inner) > 1:
                    raise ValueError(
                        f"{key}: inner_contains={inner_key!r} 가 {len(inner)}개에 "
                        f"걸린다 — 하나만 읽는 kind 다. 더 좁혀라\n"
                        f"  후보: {', '.join(sorted(inner)[:5])}"
                        + (" …" if len(inner) > 5 else ""))
                with z.open(inner[0]) as f:
                    d, seen = _read(f)
        else:
            with src.open("rb") as f:
                d, seen = _read(f)

        if sel:
            # ★ 0건은 조용히 통과시키지 않는다. 코드 체계가 바뀌면(2026-07-01
            #   개편처럼) 선언이 맞는데도 0건이 나오고, 그것이 초록불로
            #   지나가면 다음 단계가 빈 표를 쓴다.
            if not len(d):
                raise ValueError(
                    f"{key}: select {sel} 로 0건이다. {seen:,}행을 읽었다.\n"
                    "  법정동코드 개편(2026-07-01, 광주 29→12)을 확인하라 —\n"
                    "  같은 기관 자료라도 파일마다 신·구 코드가 섞여 있다.")
            print(f"  · {key}: {seen:,}행 → select {sel} → {len(d):,}행")

        if cols and len(cols) == d.shape[1]:
            d.columns = cols
        else:
            if cols:
                raise ValueError(
                    f"{key}: contract.columns 가 {len(cols)}개인데 실물은 "
                    f"{d.shape[1]}열이다")
            d.columns = [f"c{i:02d}" for i in range(d.shape[1])]
        d.to_csv(OUT / f"{key}.csv", index=False, encoding="utf-8-sig")
        rec |= {"status": "OK", "features": len(d), "geom": [],
                "columns": list(d.columns), "outputs": [f"{key}.csv"]}
        return rec

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

    info = save(g, key)
    # ★ 2026-08-30. 종전에는 0건도 status: OK 였다. `jijeok` 이 970MB 를
    #   읽고 0건을 내면서 초록불이었다 — 파일은 생겼고 mtime 은 새것이고
    #   어떤 가드도 보지 못한다. 2026-08-18 gpkg 레이어 사고와 같은 형태다.
    #
    #   **조용히 덜 하는 것이 시끄럽게 죽는 것보다 나쁘다.** 0건이
    #   정상인 소스가 있다면 대장에 선언하게 한다 — 코드가 봐주지 않는다.
    _min = int((e.get("contract") or {}).get("scope_min", 1))
    if info["features"] < _min:
        rec |= {"status": "FAIL", **info,
                "error": f"산출 {info['features']}건 < scope_min {_min}. "
                         "좌표계·BBOX·필터를 확인하라. 0건이 정상이면 "
                         "contract.scope_min 에 선언해라",
                "outputs": []}
        print(f"  ★ {key}: 산출 {info['features']}건 — scope_min {_min} 미달")
        print(f"     source_crs={crs} · 읽은 것 {src.name}")
        return rec
    rec |= {"status": "OK"} | info
    rec["outputs"] = [f"{key}.geojson", f"{key}_5186.gpkg"]
    return rec


# ★ 부모가 자식에게 결과를 받는 표식. 자식의 화면 출력을 그대로
#   흘리면서도 결과 한 줄만 골라내야 한다.
_MARK = "@@ingest-result@@ "


def _spawn(key: str) -> dict:
    """소스 하나를 **자식 프로세스**로 돌리고 결과 dict 를 받는다.

    ── 왜 자식인가 (PLAN #15) ─────────────────────────────────────
    `geopandas` 가 놓은 메모리를 OS 에 안 돌려줘 한 프로세스로 66종을
    돌면 RSS 가 단조증가한다. 뒤쪽 무거운 소스가 `Errno 12` 로 죽는다.
    종료 시 OS 가 회수하게 하면 누적이 0 으로 리셋된다.

    ★ **"무거운 것만" 이 아니라 전부 자식으로 돌린다.** 2026-09-14 에
      `jijeok`(1.0GB · 630만 행)을 `on_demand` 로 뺐더니 OOM 이
      `ngii_road` 로 **옮겨갔다.** 문제는 개별 크기가 아니라 누적이므로,
      무거운 것을 고르는 일 자체가 답이 아니다. `_manifest` 에 시간도
      없어서 고를 근거도 없다.

    ★ `--keep-work` 를 준다. 자식마다 `.work` 를 지우면 `ngii1k` 가
      도엽 74장 + NGI 143장을 매번 다시 푼다 — ingest 시간의 대부분이
      거기다(아래 2026-08-23 주석). **OOM 을 고치고 시간을 폭발시키면
      안 바꾼 것만 못하다.** `.work` 는 부모가 마지막에 한 번 판단한다.

    ★ `--emit-json` 을 준다. 자식은 대장을 쓰지 않는다. 40번 쓰면 I/O 도
      낭비고, 중간에 죽으면 대장이 반쯤 갱신된 채 남는다 — `--check` 가
      "조회는 아무것도 쓰지 않는다" 로 세운 선과 같은 이유다(2026-08-31).

    ★ `python -m firelane.ingest` 가 아니라 `main()` 을 직접 부른다.
      전자는 `warn_direct_call` 이 자식마다 경고를 찍어 화면이 40줄
      늘어난다. 그 경고는 **사람**이 단계를 직접 부를 때를 위한 것이고
      부모가 부르는 것은 그 경우가 아니다.

    실패는 예외로 낸다. 호출부의 `except` 가 `quarantine_stale` 까지
    이미 처리하므로 새 경로를 만들지 않는다.
    """
    cmd = [sys.executable, "-c",
           "from firelane.ingest import main; main()",
           "--only", key, "--keep-work", "--emit-json"]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, check=False)
    # ★ 자식의 진행 줄은 삼킨다. 부모가 같은 내용을 `[OK ]` 로 다시
    #   찍으므로 안 삼키면 **한 소스가 두 줄**이 된다. `.work 유지` 도
    #   자식 것은 거짓이다 — 정리 판단은 부모 몫이고 자식은 항상 남긴다.
    #   부모가 못 내는 것(원본 행수·select 내역)만 흘린다.
    for line in p.stdout.splitlines():
        if line.startswith(_MARK) or line.startswith(("[", "  · .work")):
            continue
        print(line)
    if p.stderr.strip():
        print(p.stderr.rstrip(), file=sys.stderr)
    for line in reversed(p.stdout.splitlines()):
        if line.startswith(_MARK):
            return json.loads(line[len(_MARK):])
    # ★ 결과가 없다 = 자식이 중간에 죽었다. OOM 이면 rc 가 -9(SIGKILL) 다.
    #   그것을 그대로 사유로 적는다 — "실패했다" 만 적으면 다음 사람이
    #   또 추측한다(2026-09-14 오진 넷).
    raise RuntimeError(
        f"자식이 결과를 안 냈다 (rc={p.returncode}"
        + (" · SIGKILL — 메모리일 가능성이 높다" if p.returncode in (-9, 137) else "")
        + ")")


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
    # ★ PLAN #15. 소스마다 자식 프로세스로 돌려 메모리를 OS 에 반납한다.
    #   사유는 `_spawn` 에 있다. 기본값은 실측 뒤에 정한다.
    ap.add_argument("--split", action="store_true",
                    help="소스마다 자식 프로세스로 돌린다 (메모리 반납)")
    # ★ 자식 전용. 대장을 쓰지 않고 결과 한 줄만 낸다.
    ap.add_argument("--emit-json", action="store_true",
                    help=argparse.SUPPRESS)
    ap.add_argument("--rebuild", action="store_true",
                    help="샤드 봉인을 무시하고 전부 다시 빌드한다")
    ap.add_argument("--reseal-out", action="store_true",
                    help="하류가 덧쓴 산출물로 샤드 봉인지의 out 칸만 고친다 (파이프라인이 terrain 뒤에 부른다)")
    # ★ 2026-09-23 (DECISIONS §224-2a). 사유는 `shardseal.reseal_code` 머리말.
    ap.add_argument("--reseal-code", action="store_true",
                    help="raw · 산출물이 봉인과 같은 샤드의 code 칸만 지금 코드 지문으로 고친다")
    ap.add_argument("--stamp", action="store_true",
                    help="빌드 없이, 지금 산출물에 샤드 봉인지를 붙인다 (사람이 판단해서 부른다)")
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

    # ★ 2026-09-16. 샤드(소스 하나) 봉인 — shardseal.py 머리말. 봉인지 네 칸
    #   (raw · cfg · code · out)이 전부 같으면 다시 빌드하지 않는다. 이 8GB
    #   기계에서 `ngii_road` 는 다시 빌드하면 거의 반드시 죽는다(DECISIONS §165).
    from firelane import shardseal
    _code = shardseal.code_print()
    _man0 = OUT / "_manifest.json"
    _prev = {}
    if _man0.exists():
        try:
            _prev = {r["key"]: r for r in json.loads(_man0.read_text(encoding="utf-8"))
                     .get("datasets", []) if isinstance(r, dict) and "key" in r}
        except Exception:                                   # noqa: BLE001
            _prev = {}

    if a.reseal_out:
        return shardseal.reseal_out_cli(_man0, OUT, manifest)

    if a.reseal_code:
        return shardseal.reseal_code_cli(_man0, cfg, OUT, _code, paths_for, manifest)

    if a.stamp:
        # 빌드하지 않는다. 지금 디스크의 산출물이 지금 코드 · raw 로 만든 것이라는
        # 판단은 **사람이** 한다(직전 전량 성공 · golden 불변). 여기서는 잴 수 있는
        # 것만 잰다 — 산출물이 대장에 적힌 대로 다 있는가.
        if a.only:
            sys.exit("★ --stamp 는 --only 와 같이 쓰지 않는다. 대장 전체에 붙인다.")
        stamped, left = 0, []
        for key, e in cfg["datasets"].items():
            r = _prev.get(key)
            if not r or r.get("status") != "OK":
                continue
            try:
                _h = paths_for(key, e)
            except Exception:                               # noqa: BLE001
                _h = []
            s = shardseal.make(cfg, key, _h, OUT, r.get("outputs", []), _code)
            if s is None:
                left.append(key)
                continue
            r["seal"] = s
            stamped += 1
        results = [_prev[k] for k in cfg["datasets"] if k in _prev] + \
                  [v for k, v in _prev.items() if k not in cfg["datasets"]]
        print(f"샤드 봉인지 {stamped}종 · 못 붙인 것 {len(left)}종"
              + (f": {', '.join(left)}" if left else ""))
        if left:
            print("  못 붙인 샤드는 산출물이 없거나 raw 를 못 쟀다. 다음 실행에서 다시 빌드된다.")
        doc = {k: v for k, v in manifest.read(_man0).items()
               if k not in ("generated_at", "bbox_4326", "standard_crs", "datasets")}
        doc.update({"generated_at": datetime.now(UTC).astimezone().isoformat(),
                    "bbox_4326": BBOX_4326,
                    "standard_crs": {"metric": CRS_M, "display": CRS_W},
                    "datasets": results})
        wrote = manifest.write_stable(_man0, doc)
        print(f"→ {_man0}" + ("" if wrote else "  (내용 동일 — 갱신 없음)"))
        return 0

    tmp = ROOT / ".work"
    tmp.mkdir(exist_ok=True)
    results = []
    _done = False

    # ★ 2026-09-13. `finally` 로 감쌌다. 아래의 "실패했을 때는 지운다" 는
    #   맞는 규율인데 **그 줄까지 도달해야 돈다.** Ctrl-C 는 루프 한가운데서
    #   스택을 걷어내므로 반쯤 풀린 `.work` 가 그대로 남고, 다음 실행이
    #   그것을 캐시로 믿는다.
    # ★ 2026-09-14 재정정. `ngii_road` · `jijeok` 이 죽은 진짜 원인은
    #   **메모리**였다(`Errno 12`). `.work` 오염도 stdin 누락도 아니었다.
    #   같은 증상을 두 번 오진했다 — 증상이 맞아떨어진다고 원인이 아니다.
    #   이 `finally` 자체는 옳으므로 남긴다. 중단된 실행이 반쯤 풀린
    #   `.work` 를 남기는 것은 사실이고, 막는 것이 맞다.
    # ★ 아래 옛 사유는 틀렸다. 지우지 않고 남겨 둔다 — 무엇을 잘못
    #   짚었는지가 다음 사람에게 정보다.
    # ☓ 2026-09-14 (틀림). 그날 `ngii_road` 가 죽은 원인은 이것이 아니었다.
    #   진범은 `verify.sh` 의 `step()` 이 자식에게 파이프 stdin 을 물려준
    #   것이었다(`</dev/null` 누락). 같은 자리에서 같은 증상이 두 번 났으면
    #   공통 원인을 먼저 의심했어야 했다. 이 `finally` 자체는 옳으므로
    #   남기되, **사유를 고쳐 적는다** — 틀린 사유는 침묵보다 나쁘다.
    try:
      for key, e in cfg["datasets"].items():
        if a.only and key not in a.only:
            continue
        # ★ 2026-09-14. 요청할 때만 읽는다. `jijeok` 은 1.0GB 를 풀어
        #   630만 행을 파싱해 24,183건을 내는데 **판정도 화면도 안 읽는다** —
        #   소비자가 `tools/jijeok_probe.py` · `jijeok_review.py` 둘뿐이다.
        #   8GB 기계에서 `verify.sh` 안의 전량이 그것 때문에 OOM 으로
        #   죽었다(Errno 12). 2026-09-03 에도 같은 일이 있었다.
        # ★ `raw_only` 로 안 바꾼다. 그것은 "읽지 않는다" 이고 이쪽은
        #   **읽을 수는 있어야** 한다 — 탐색 도구가 산출물을 쓴다.
        if e.get("on_demand") and not a.only:
            results.append({"key": key, "status": "SKIP", "features": "",
                            "geom": [], "outputs": [],
                            "note": "on_demand — --only 로 지목할 때만 읽는다"})
            print(f"[SKIP   ] {key:22} on_demand")
            continue
        if a.check:
            hits = paths_for(key, e)
            results.append({"key": key, "found": len(hits),
                            "sha256": [sha256(h)[:16] for h in hits]})
            print(f"[{'OK ' if hits else 'MISS'}] {key:20} {len(hits)}개")
            continue
        # ★ 샤드 재사용. 지목(--only)·조회·자식·--rebuild 에서는 안 한다.
        if not (a.only or a.emit_json or a.rebuild):
            try:
                _hits = paths_for(key, e)
            except Exception:                               # noqa: BLE001
                _hits = []                                  # 못 재면 재사용 안 한다
            _ok, _why = shardseal.check(_prev.get(key), cfg, key, _hits, OUT, _code)
            if _ok:
                results.append(_prev[key])
                print(f"[SEALED ] {key:20} 봉인 일치 — 다시 빌드하지 않는다")
                continue
            if _prev.get(key, {}).get("status") == "OK":
                print(f"          {key}: 봉인지 찢어짐 — {_why}")
        try:
            r = _spawn(key) if a.split else build(key, e, tmp)
            if r.get("status") == "OK" and not a.emit_json:
                _s = shardseal.make(cfg, key, paths_for(key, e), OUT, r.get("outputs", []), _code)
                if _s:
                    r["seal"] = _s
        except Exception as ex:                             # noqa: BLE001
            r = {"key": key, "status": "FAIL", "error": f"{type(ex).__name__}: {ex}"}
            # ★ FAIL 이면 이 key 의 기존 산출물을 개명해 하류에서 떼어낸다.
            #   2026-08-17 ngii1k FAIL 때 8/13 gpkg 가 남아 segments 가 그것으로
            #   판정을 냈고(1093), 다음 날 진짜 실행(1091)과 갈려 "기계 간
            #   재현성 붕괴"로 오인해 반나절을 태웠다. 로직은 guards.py 정본.
            from firelane.guards import quarantine_stale
            staled = quarantine_stale(OUT, key, keys=list(cfg["datasets"]))
            if staled:
                r["staled"] = staled
                print(f"          ★ 옛 산출물 {len(staled)}개 격리(.stale_) — 하류가 못 읽는다")
        # ★ 2026-09-10. 종전에는 status 와 건수만 찍고 error 는
        #   _manifest.json 에만 적었다. 실패 사유를 보려면 JSON 을
        #   손으로 파싱해야 했고, 그 바람에 juso 3종 FAIL 의 원인을
        #   **세 번 추측**했다(vector → shp_zip_multi → raw_only).
        #   339행이 같은 병을 이미 적어놨다. 화면에 낸다.
        _st = r.get("status", "-")
        _msg = f"{r.get('features', ''):>8} feat"
        if _st in ("FAIL", "MISSING") and r.get("error"):
            _msg = str(r["error"])[:78]
        print(f"[{_st:7}] {key:20} {_msg}")
        results.append(r)
      _done = True
    finally:
        if not _done:
            # 끊겼거나 터졌다. 압축 해제분을 남기지 않는다.
            shutil.rmtree(tmp, ignore_errors=True)

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

    # ★ 자식 모드. **대장을 쓰지 않는다.** `--check` 와 같은 선이고 같은
    #   이유다 — 부분 실행이 전체 상태를 파괴하는 것을 막는다(아래 08-31).
    #   결과는 부모가 모아서 한 번에 쓴다.
    # ★ `--check` **앞**에 둔다. `--check --emit-json` 이면 raw 실물의
    #   sha256 이 나오고 `dms.py` 가 그것을 봉인 지문으로 쓴다(PLAN #68).
    #   대장의 `source_sha256` 을 쓰면 안 된다 — 그것은 ingest 가 돌 때
    #   찍힌 값이라 **raw 가 바뀌어도 ingest 전까지 안 바뀐다.** 그 값으로
    #   대조하면 "같다" 가 항상 참인 죽은 검사가 된다.
    if a.emit_json:
        for r in results:
            print(_MARK + json.dumps(r, ensure_ascii=False, sort_keys=True))
        return 0

    # ★ 2026-08-31. **`--check` 는 조회다. 아무것도 쓰지 않는다.**
    #
    #   종전에는 `if a.check:` 가 루프를 `continue` 로 건너뛸 뿐이었고,
    #   아래 쓰기 경로로 그대로 떨어졌다. `--check` 의 레코드는
    #   `key·found·sha256` 셋뿐이라 **계보 27건을 얕은 판으로 덮었다.**
    #   그날 커밋에 `rewrite _manifest.json (95%)` 가 찍혔고 `golden` 은
    #   L1·L2·L3 전부 OK 를 냈다 — `segments.geojson` 하나만 읽으니
    #   입력 계보가 죽은 것을 모른다. 복구에 전량 재실행 317초를 태웠다.
    #
    #   같은 형태를 이 파일이 이미 두 번 겪었다 — `--only` 가 대장을
    #   통째로 덮은 것(08-22), 최상위 키를 날린 것(08-25). 셋 다
    #   **조회·부분실행이 전체 상태를 파괴**한 것이다.
    #   강제자 — `tests/test_ledger_outputs.py::test_check_does_not_write`
    if a.check:
        _miss = [r["key"] for r in results if not r["found"]]
        print(f"\n조회만 했다 — {len(results)}종 · 없음 {len(_miss)}종"
              + (f": {', '.join(_miss)}" if _miss else ""))
        print("  대장은 건드리지 않았다. 갱신하려면 --check 없이 돌린다.")
        return 0

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
    from firelane.guards import warn_direct_call

    warn_direct_call(__name__)
    # ★ 메모리로 죽은 것을 메모리로 죽었다고 말한다(stagerun.py 머리말 · §224-3a).
    from firelane.stagerun import run_stage

    run_stage(main)

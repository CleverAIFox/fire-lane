"""
_io.py — 갈래들이 함께 쓰는 **읽기 연장**과 절단 상자.  (PLAN §1 #132 · DECISIONS §274)

── 왜 생겼나 ──────────────────────────────────────────────────
이 넷은 `ingest.py` 안에 있었고 **분기만 쓰고 있었다.** 분기를 `read/` 로 옮기면
`read` → `ingest` → `read` 로 임포트가 돈다. 연장을 아래로 내리면 고리가 끊긴다.

★ **상수를 함께 내린 이유.** `BBOX_4326` 은 `bbox_in` 이 쓰고 `bbox_in` 은
  `load_shp_in_zip` 이 쓴다. 상수만 `ingest` 에 두면 같은 고리가 남는다.
  정본은 여전히 대장(`sources.yaml` 의 `bbox_4326`)이고 여기는 그것을 읽을 뿐이다.

IN    대장의 `bbox_4326` · zip · CSV 실물
OUT   GeoDataFrame · DataFrame · 푼 폴더 경로
밖    **어느 갈래가 어느 연장을 쓰는지는 안 본다.** 그것은 각 갈래 모듈이 든다.
      그리고 **쓰지 않는다** — 저장은 `ingest.save` 하나다.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import Transformer

from firelane.encoding import CANDIDATES_CSV_READ
from firelane.ledger import bbox_4326

CRS_M, CRS_W = "EPSG:5186", "EPSG:4326"
# 동명동 + 여유. 행정구역경계(전자지도 승인 대기) 확보 시 정식 폴리곤으로 교체할 것.
# ★ 값의 정본은 대장이고, 그 칸은 **대장이 내준다**(DECISIONS §169 · §274-4).
#   여기서 대장을 직접 열면 문이 하나 더 는다 — `test_lake` 의 래칫이 그것을 센다.
BBOX_4326 = bbox_4326()


def bbox_in(crs: str):
    t = Transformer.from_crs(CRS_W, crs, always_xy=True)
    x0, y0 = t.transform(BBOX_4326[0], BBOX_4326[1])
    x1, y1 = t.transform(BBOX_4326[2], BBOX_4326[3])
    return (x0, y0, x1, y1)


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

"""
jsondoc.py — JSON 문서를 읽는 갈래.  (PLAN §1 #132)

IN    표준데이터 JSON(`records`) · 건축행정시스템 JSON(`Data`)
OUT   GeoDataFrame (`json_points`) 또는 완성된 계보 조각 (`json_table`)
밖   **래퍼 이름을 새로 늘리지 않는다.** `records` · `Data` 둘만 받는다 —
      셋째가 나오면 그때 대장에 선언하게 하지 코드가 추측하지 않는다.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from firelane.read._io import BBOX_4326, CRS_W
from firelane.read.ctx import Ctx


def read_json_points(c: Ctx):
    """kind "json_points" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    e = c.e
    src = c.src
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
    return g


def read_json_table(c: Ctx):
    """kind "json_table" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    key = c.key
    e = c.e
    src = c.src
    out = c.out
    rec = c.rec
    # ★ `json_points` 와 읽는 법이 같고 좌표만 없다. 건축물대장 표제부는
    #   {"Description": {…}, "Data": [...]} 라 래퍼 이름이 다르다.
    #   `records`(표준데이터) · `Data`(건축행정시스템) 둘 다 받는다.
    import json as _json
    raw = _json.loads(src.read_text(encoding=e.get("encoding", "utf-8")))
    rows = raw if isinstance(raw, list) else (
        raw.get("records") or raw.get("Data") or [])
    d = pd.DataFrame(rows).astype(str)
    d.to_csv(out / f"{key}.csv", index=False, encoding="utf-8-sig")
    rec |= {"status": "OK", "features": len(d), "geom": [],
            "columns": list(d.columns), "outputs": [f"{key}.csv"]}
    return rec

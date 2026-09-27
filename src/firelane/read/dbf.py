"""
dbf.py — 지오메트리 없는 DBF 를 읽는 갈래. 회전제한 하나뿐이다.  (PLAN §1 #132)

IN    zip 안 DBF · `data/processed/node_point_5186.gpkg` (노드로 한정)
OUT   완성된 계보 조각 + `data/processed/<key>.csv`
밖   **노드 거르기가 조용히 사라지는 것**은 `guards.subset_by_nodes` 가 든다.
      여기서 다시 세지 않는다(PLAN §1 #13 · DECISIONS §273-7).
"""
from __future__ import annotations

import geopandas as gpd

from firelane.read._io import unzip_own
from firelane.read.ctx import Ctx


def read_dbf_in_zip(c: Ctx):
    """kind "dbf_in_zip" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    key = c.key
    e = c.e
    src = c.src
    tmp = c.tmp
    out = c.out
    rec = c.rec
    p = next(unzip_own(src, tmp).rglob(e["layer"]))      # §181-4 — 그 zip 폴더 안에서만
    t = gpd.read_file(p).drop(columns="geometry", errors="ignore")
    # 동명동 노드로 한정 — node_point 산출물을 읽는다.
    # ★ 2026-09-22 (DECISIONS §217-1 · PLAN §13 W11-1 닫음). 종전에는 산출물이 **없으면
    #   거르지 않고** 전국 44,125행을 냈다. 대장 순서상 node_point 가 앞이지만 그것이 FAIL 로
    #   격리(.stale_)되면 조용히 전국분이 나왔다 — 파이프라인 행수 관문(`pipeline` 의 87)이
    #   늦게 잡을 뿐이었다. 원인 자리에서 멈춘다.
    # ★ 관문은 `guards.subset_by_nodes` 가 든다 — 「필터가 조용히 사라지는데
    #   status 는 OK」 네 갈래를 한 자리에서 막는다(PLAN §1 #13 · DECISIONS §273-7).
    from firelane.guards import subset_by_nodes
    t = subset_by_nodes(t, out / "node_point_5186.gpkg", key)
    t.to_csv(
        out / f"{key}.csv", index=False, encoding="utf-8-sig")
    rec |= {"status": "OK", "features": len(t), "geom": [],
            "columns": list(t.columns), "outputs": [f"{key}.csv"]}
    return rec

"""
read — `kind` 별 **읽기**의 정본.  (PLAN §1 #132 · DECISIONS §274)

── 왜 생겼나 (2026-09-27 실측) ────────────────────────────────
`ingest.build()` 가 1101줄이었고 그중 389줄(35%)이 `kind` 분기 열둘이었다.
그 하나가 **72개 데이터셋 전부의 샤드 `seal.code`** 를 들고 있었다 —
`text_table` 한 줄을 고치면 `raw_only` 26개까지 같이 재도장됐다.

실측이 갈래를 다섯으로 갈랐다:

    갈래          줄    데이터셋
    delimited    207    29  (40%)
    shapefile    128    13  (18%)
    jsondoc       29     3  ( 4%)
    dbf           18     1  ( 1%)
    passthrough    7    26  (36%)   ← 7줄이 36% 를 든다

★ **열둘로 쪼개지 않았다.** `shp_zip` 3줄 · `csv_points` 3줄이다 —
  평균 32줄짜리 파일 열둘은 표 하나보다 나쁘다. 가른 기준은 **무엇을 읽는가**고,
  그것이 그대로 샤드 축이 된다(DECISIONS §274-2).

IN    `Ctx` (대장 항목 · 실물 · 작업 폴더)
OUT   GeoDataFrame — `ingest.build` 가 `save()` 로 넘긴다
      또는 완성된 계보 조각(dict) — 그대로 돌려준다
밖    **어느 실물을 읽을지는 안 고른다** — `ingest.paths_for` 가 고른다.
      **저장도 안 한다** — `ngii1k` 만 주입받은 `save` 로 도엽별로 쓴다.
      **대장이 옳은지도 안 본다** — `firelane.ledger` 가 든다.
"""
from __future__ import annotations

from firelane.read.ctx import Ctx
from firelane.read.dbf import read_dbf_in_zip
from firelane.read.delimited import (
    read_csv_points,
    read_csv_points_in_zip,
    read_csv_table,
    read_csv_table_multi,
    read_text_table,
)
from firelane.read.jsondoc import read_json_points, read_json_table
from firelane.read.passthrough import read_raw_only
from firelane.read.shapefile import read_ngii1k, read_shp_zip, read_shp_zip_multi

#: `kind` → 갈래 함수. **정본은 이 표 하나다.**
#: 새 kind 는 ① `firelane.kinds.KINDS` ② 갈래 모듈의 함수 ③ 이 표 — 셋이다.
READERS = {
    'shp_zip': read_shp_zip,
    'shp_zip_multi': read_shp_zip_multi,
    'ngii1k': read_ngii1k,
    'ngii_1k': read_ngii1k,
    'shp_dir': read_ngii1k,
    'csv_points': read_csv_points,
    'csv_point': read_csv_points,
    'csv_points_in_zip': read_csv_points_in_zip,
    'dbf_in_zip': read_dbf_in_zip,
    'json_points': read_json_points,
    'json_table': read_json_table,
    'text_table': read_text_table,
    'csv_table': read_csv_table,
    'csv_table_multi': read_csv_table_multi,
    'raw_only': read_raw_only,
}

#: 도형을 내는 갈래. 나머지는 완성된 계보 조각을 돌려준다.
#: ★ 시험(`test_read_dispatch`)이 이 집합과 실제 반환형을 대조한다 —
#:   선언만 있고 안 맞으면 `save()` 에 dict 가 들어가 엉뚱한 데서 죽는다.
GEOM_KINDS = frozenset({
    "shp_zip", "shp_zip_multi", "csv_points", "csv_point",
    "csv_points_in_zip", "json_points",
})

__all__ = ["GEOM_KINDS", "READERS", "Ctx", "reader"]


def reader(kind: str):
    """`kind` 의 갈래 함수. 없으면 **세운다** — 조용히 건너뛰지 않는다."""
    try:
        return READERS[kind]
    except KeyError:
        raise ValueError(
            f"unknown kind: {kind}\n"
            f"  아는 것 {len(READERS)}종: {' · '.join(sorted(READERS))}\n"
            f"  새로 넣으려면 셋이다 — firelane.kinds.KINDS · "
            f"read/<갈래>.py 의 함수 · read.READERS"
        ) from None

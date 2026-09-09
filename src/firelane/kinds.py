"""
kinds.py — `kind` 분류의 **정본**. 여섯 곳에 흩어져 있던 것을 모았다.

── 왜 생겼나 ──────────────────────────────────────────────────
`kind` 하나를 추가하려면 여섯 자리를 고쳐야 했다.

    src/firelane/ledger.py:73    NO_SCHEMA_KINDS
    src/firelane/ledger.py:76    TEXT_KINDS
    src/firelane/ledger.py:82    SINGLE_PICK        (위에서 파생)
    src/firelane/ingest.py       build() 분기 13종
    src/firelane/inventory.py    PROBES
    tools/ledger_schema.py:59    CSV_KINDS · SHP_KINDS
    tools/ledger_stem.py:80      BUNDLE_KINDS

`json_points` 를 넣을 때 **넷 중 둘만 고쳤다.** `ledger` 와 `ingest` 에는
들어갔고 `ledger_schema` 와 `inventory` 에는 안 들어갔다. 그 결과

    ledger_schema --check   json_points 소스의 실물 변경을 못 잡는다
    inventory               "kind 미지원" 을 status 에 적고 조용히 넘어간다

둘 다 **실패하지 않는다.** 초록불인데 검사가 안 돌고 있었다.
`test_pr_body_check` 가 적은 그 형태다 — *초록불의 뜻이 "검사가 안 걸렸다"
가 아니라 "아무도 검사 대상이 되는 일을 안 했다"였다.*

`params.py` ↔ `config.js` 에서 세운 규칙 그대로다 —
**정본은 하나고 나머지는 사본이거나 없어야 한다.**

── 무엇을 옮겼고 무엇을 안 옮겼나 ─────────────────────────────
★ **읽기 함수는 안 옮긴다.** zip 을 풀고 좌표를 만드는 것은 `ingest` 의
  일이고 여기로 가져오면 `ledger` 가 `geopandas` 에 매인다. 계층이
  거꾸로 선다(`params.py` 가 `publish_web` 에서 상수만 올린 것과 같은 이유).

  옮기는 것은 **분류**다 — 텍스트인가 · 도형이 나오나 · 하나만 읽나 ·
  구조 선언이 필요한가 · 무엇으로 실물을 재나.

── 새 kind 를 추가하는 법 ─────────────────────────────────────
    1. 여기 KINDS 에 한 줄 추가한다
    2. `ingest.build()` 에 분기를 만든다
    3. `inventory` 에 probe 가 없으면 만들고 PROBE_FN 에 잇는다

`test_kind_registry_is_the_single_source` 가 셋을 **양방향**으로 대조한다.
하나만 하면 운다. 정적 목록에는 반드시 역방향 검사를 붙인다(2026-09-04).

IN    없음 (선언)
OUT   없음
PARAM 없음
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Kind:
    """`kind` 하나의 분류.

    text       텍스트 소스인가. 참이면 대장에 `encoding` 선언이 필수다
    geom       좌표가 나오는가. 거짓이면 표(csv)로만 떨어진다
    single     `hits[0]` 하나만 읽는가. 여러 파일이 걸리면 조용히 뒤집힌다
    schema     `ledger_schema` 가 무엇으로 읽나. None 이면 schema 선언 면제
    probe      `inventory` 가 실물을 무엇으로 재나
    container  원본이 어떻게 담겨 있나. "dir" 는 도엽 묶음이라 stem 이 여럿 허용
    """

    text: bool
    geom: bool
    single: bool
    schema: str | None
    probe: str
    container: str = "file"


KINDS: dict[str, Kind] = {
    # ── 도형 ─────────────────────────────────────────────────
    "shp_zip":       Kind(text=False, geom=True,  single=True,
                          schema="shp", probe="shp", container="zip"),
    "shp_zip_multi": Kind(text=False, geom=True,  single=False,
                          schema="shp", probe="shp", container="zip"),
    "shp_dir":       Kind(text=False, geom=True,  single=False,
                          schema="shp", probe="ngi_dir", container="dir"),
    # ★ 옛 이름 둘. 파일명·대장에 아직 살아 있어 지우면 깨진다.
    #   `shp_dir` 로 모으는 것은 개명 배치의 일이다(B2-14).
    "ngii1k":        Kind(text=False, geom=True,  single=False,
                          schema="shp", probe="ngi_dir", container="dir"),
    "ngii_1k":       Kind(text=False, geom=True,  single=False,
                          schema="shp", probe="ngi_dir", container="dir"),
    # ★ dbf 는 도형이 없다. 회전제한 표다. 그런데 shp 계열 도구로 읽는다.
    "dbf_in_zip":    Kind(text=False, geom=False, single=True,
                          schema="shp", probe="shp", container="zip"),

    # ── 표 ───────────────────────────────────────────────────
    "csv_points":       Kind(text=True, geom=True,  single=True,
                             schema="csv", probe="csv"),
    "csv_point":        Kind(text=True, geom=True,  single=True,
                             schema="csv", probe="csv"),
    "csv_points_in_zip": Kind(text=True, geom=True, single=True,
                              schema="csv", probe="csv_in_zip", container="zip"),
    "csv_table":        Kind(text=True, geom=False, single=True,
                             schema="csv", probe="csv"),
    # ★ multi 만 hits 전부를 이어붙인다. single 로 두면 "하나만 읽는데
    #   files 가 2개다" 를 매번 오탐한다.
    "csv_table_multi":  Kind(text=True, geom=False, single=False,
                             schema="csv", probe="csv"),

    # ── JSON ─────────────────────────────────────────────────
    # 공공데이터포털 표준데이터. {"fields": [...], "records": [...]}
    "json_points":   Kind(text=True, geom=True,  single=True,
                          schema="json", probe="json"),
    # 좌표가 없는 JSON 표. 건축물대장 표제부 {"Description":…, "Data":[…]}
    "json_table":    Kind(text=True, geom=False, single=True,
                          schema="json", probe="json"),

    # ── 구분자 텍스트 ────────────────────────────────────────
    # 도로명주소 DB 계열. `|` 구분 · **헤더 없음** · cp949 · zip 안.
    # ★ csv 계열로 밀어넣으면 첫 행을 헤더로 먹고 조용히 1행을 잃는다.
    #   컬럼명이 파일에 없고 활용가이드 PDF 에만 있어서 `contract` 에
    #   사람이 적어야 한다 — `ledger_schema` 가 대신 못 읽는다.
    "text_table":    Kind(text=True, geom=False, single=True,
                          schema="delim", probe="delim", container="zip"),

    # ── 읽지 않는 것 ─────────────────────────────────────────
    "raw_only":      Kind(text=False, geom=False, single=False,
                          schema=None, probe="raw_only"),
}


def _pick(**kw) -> set[str]:
    return {k for k, v in KINDS.items()
            if all(getattr(v, a) == b for a, b in kw.items())}


# ── 파생 집합. 소비자는 이것을 import 한다 ──────────────────────
# ★ 손으로 나열하지 않는다. 나열하는 순간 사본이 하나 더 생긴다.
TEXT_KINDS = {k for k, v in KINDS.items() if v.text}
NO_SCHEMA_KINDS = {k for k, v in KINDS.items() if v.schema is None}
SINGLE_PICK = {k for k, v in KINDS.items() if v.single}
BUNDLE_KINDS = _pick(container="dir")

CSV_KINDS = _pick(schema="csv")
SHP_KINDS = _pick(schema="shp")
JSON_KINDS = _pick(schema="json")
DELIM_KINDS = _pick(schema="delim")

ALL = frozenset(KINDS)

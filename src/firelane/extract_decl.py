"""
extract_decl.py — 추출 단계(`normalize_columns` · `filter`) **선언의 모양과 이름**.  (DECISIONS §646)

읽는 쪽(`read/extract.py`)과 정적 검사(`ledger_check`)가 **같은 판별식**을 쓰도록 가벼운 자리에 둔다 — `ledger_check` 가 읽기 갈래 전부(`geopandas` 등)를 들이지 않는다.
레이크 없이 돈다. 값은 안 읽는다.

IN    대장 항목(`contract` · `kind` · `schema.columns`)
OUT   `declared` · `problems` · `normalize`
밖    **실물이 맞는지는 안 본다**(그것은 `read/extract.py` 가 읽을 때 죽는다).
"""
from __future__ import annotations

KINDS = ("csv_table", "csv_table_multi")
NORMALIZERS = {"lower_strip": lambda c: str(c).strip().strip('"').lower()}
FILTER_KEYS = {"column", "equals"}


def declared(e: dict) -> bool:
    """이 항목이 추출 단계를 쓰는가 — `normalize_columns` 나 `filter` 중 하나라도 적혔다."""
    con = (e or {}).get("contract") or {}
    return bool(con.get("normalize_columns") or con.get("filter"))


def normalize(cols, mode: str) -> list[str]:
    """칸 이름을 정규화한다. 정규화 뒤 겹치면 세운다 — 조용히 한 칸이 다른 칸을 덮으면 안 된다."""
    out = [NORMALIZERS[mode](c) for c in cols]
    dup = sorted({c for c in out if out.count(c) > 1})
    if dup:
        raise ValueError(f"칸 이름이 정규화 뒤 겹친다 — {dup}")
    return out


def problems(key: str, e: dict) -> list[str]:
    """대장 선언의 **모양과 이름**. 레이크 없이 돈다(`ledger_check` 가 부른다).

    ★ 오타 하나로 필터가 조용히 안 걸리면 그것이 139행 사고의 재발이다 — 그래서 모양 · 갈래 · 칸 이름까지 본다.
    """
    con = (e or {}).get("contract") or {}
    if not declared(e):
        return []
    out = []
    if e.get("kind") not in KINDS:
        out.append(f"갈래 `{e.get('kind')}` 는 normalize_columns · filter 를 안 읽는다 — 조용히 안 걸린다(읽는 갈래: {list(KINDS)})")
    mode, flt = con.get("normalize_columns"), con.get("filter")
    if mode is not None and mode not in NORMALIZERS:
        out.append(f"normalize_columns `{mode}` — 어휘는 {sorted(NORMALIZERS)}")
    if flt is None:
        return out
    if not isinstance(flt, dict) or set(flt) != FILTER_KEYS:
        return out + [f"filter 는 {{column, equals}} 둘뿐이다(다른 연산자는 안 만든다) — 지금 {sorted(flt) if isinstance(flt, dict) else flt!r}"]
    col, eq = flt["column"], flt["equals"]
    if not isinstance(col, str) or not col.strip():
        out.append("filter.column 이 비었다")
    if eq is None or isinstance(eq, (dict, list, bool)) or str(eq).strip() == "":
        out.append("filter.equals 는 비지 않은 값 하나다(빈 값으로 거르면 칸이 빈 행을 고른다)")
    if isinstance(col, str) and col.strip() and mode in NORMALIZERS and NORMALIZERS[mode](col) != col:
        out.append(f"filter.column `{col}` — 정규화 **뒤** 이름으로 적는다(`{NORMALIZERS[mode](col)}`)")
    cols = [str(c) for c in ((e.get("schema") or {}).get("columns") or [])]
    if cols and isinstance(col, str):
        have = normalize(cols, mode) if mode in NORMALIZERS else cols
        if col not in have:
            out.append(f"filter.column `{col}` 이 schema.columns{' (정규화 뒤)' if mode else ''} 에 없다 — 필터가 조용히 안 걸린다")
    return out

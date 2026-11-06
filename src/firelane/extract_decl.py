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
# ★ 둘이다. **출력 칸 이름이 하류의 이름과 같은 쪽**을 고른다 — `nfa_ems` 는 소비자가 없어 소문자(`lower_strip`) ·
#   `nfa_dispatch_119` 는 `publish_context`(`r.DSPT_DRTV_DT`) · 대장 `coords` · `schema.columns` 가 전부 대문자라 `upper_strip`(DECISIONS §648).
NORMALIZERS = {"lower_strip": lambda c: str(c).strip().strip('"').lower(),
               "upper_strip": lambda c: str(c).strip().strip('"').upper()}
FILTER_KEYS = {"column", "equals"}
#: ★ `one_of` — 한 칸이 **이름이 바뀐 값**을 갖는 경우다. 소방대상물 2024 파일은 같은 광주 동구를 `광주광역시` 와 `전남광주통합특별시` 로 둘 다 적는다(통합 뒤 갱신된 대장 · §649).
#:   `equals` 하나로 걸면 그 행을 **조용히 잃는다**(139행 사고의 같은 종류 · §644-3). 조건끼리는 여전히 AND 이고 시도 조건을 **빼지** 않는다 — 값 하나가 값 여럿이 될 뿐이다.
FILTER_KEYS_ONE_OF = {"column", "one_of"}


def conditions(flt) -> list[dict]:
    """`filter` 는 {column, equals} 하나이거나 그 목록이다(모두 맞는 행 — AND). 하나로 못 가르는 이름(여러 시도에 같은 「동구」)이 있어서 연다."""
    if flt is None:
        return []
    return list(flt) if isinstance(flt, list) else [flt]


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
    if (hi := con.get("scope_max")) is not None:
        lo = con.get("scope_min", 1 if flt else 0)
        if isinstance(hi, bool) or not isinstance(hi, int) or hi < 1:
            out.append(f"scope_max `{hi!r}` 는 1 이상의 정수다")
        elif isinstance(lo, int) and hi < lo:
            out.append(f"scope_max {hi} < scope_min {lo} — 통과할 수 있는 행 수가 없다")
    if mode is not None and mode not in NORMALIZERS:
        out.append(f"normalize_columns `{mode}` — 어휘는 {sorted(NORMALIZERS)}")
    if flt is None:
        return out
    conds = conditions(flt)
    if not conds or any(not isinstance(f, dict) or set(f) not in (FILTER_KEYS, FILTER_KEYS_ONE_OF) for f in conds):
        return out + [f"filter 는 {{column, equals}} 또는 {{column, one_of}} 둘뿐이다(다른 연산자는 안 만든다 · 여럿이면 목록 = AND) — 지금 {flt!r}"]
    cols = [str(c) for c in ((e.get("schema") or {}).get("columns") or [])]
    for f in conds:
        col = f["column"]
        if not isinstance(col, str) or not col.strip():
            out.append("filter.column 이 비었다")
        if "one_of" in f:
            vs = f["one_of"]
            if not isinstance(vs, list) or len(vs) < 2 or any(v is None or isinstance(v, (dict, list, bool)) or str(v).strip() == "" for v in vs):
                out.append("filter.one_of 는 비지 않은 값 둘 이상의 목록이다(하나면 equals 다 · 빈 값으로 거르면 칸이 빈 행을 고른다)")
            elif len({str(v) for v in vs}) != len(vs):
                out.append("filter.one_of 에 같은 값이 겹친다")
        elif (eq := f["equals"]) is None or isinstance(eq, (dict, list, bool)) or str(eq).strip() == "":
            out.append("filter.equals 는 비지 않은 값 하나다(빈 값으로 거르면 칸이 빈 행을 고른다)")
        if isinstance(col, str) and col.strip() and mode in NORMALIZERS and NORMALIZERS[mode](col) != col:
            out.append(f"filter.column `{col}` — 정규화 **뒤** 이름으로 적는다(`{NORMALIZERS[mode](col)}`)")
        if cols and isinstance(col, str):
            have = normalize(cols, mode) if mode in NORMALIZERS else cols
            if col not in have:
                out.append(f"filter.column `{col}` 이 schema.columns{' (정규화 뒤)' if mode else ''} 에 없다 — 필터가 조용히 안 걸린다")
    return out

"""
extract.py — 전국 원본에서 **지역 파생본을 만드는 추출 단계**.  (DECISIONS §646)

── 왜 있나 ────────────────────────────────────────────────────
「전국 원본 + 지역 파생본」을 대장이 한 항목으로밖에 못 써서 `nfa_*` 셋이 막혀 있었다. 추출이 일어날 자리가 없어서 2026-09 에 수동 스크립트로 걸렀고,
**대문자 필터가 2024년 이후(소문자 헤더)를 0행으로 만들어 139행을 잃었다**(§644-3). `prep` 은 「형식만 통일 · 값은 안 바꾼다」로 경계를 그었고 값 보정은 `ingest` 의
몫이라 그 사실이 계보에 남아야 한다 — 그 자리가 여기다.

── 대장의 `contract` 키 둘 ────────────────────────────────────
    normalize_columns: lower_strip      칸 이름을 `strip().strip('"').lower()` 로 맞춘다 — **값은 안 건드린다**
    filter: {column: clmty_emd_nm, equals: 동명동}     (`one_of: [a, b]` 는 값 여럿 중 하나 · 목록이면 AND — 「동구」는 여섯 시도에 있다) 정규화한 **뒤의** 칸 이름으로 적는다 · `equals` · `one_of` 외의 연산은 안 만든다
    scope_max: 60000                    거른 뒤 행 수 **상한**(추출 전용) — 하한은 과소를 잡고 상한은 과다를 잡는다. 「동구」가 여섯 광역시에 있어 단일 조건이 406,168행을 냈고 하한 40000 이 통과시켰다(§647)
    scope_min: 100                      (기존 키) 거른 뒤 행 수 하한 — 필터가 있으면 기본 1(0행은 조용히 통과시키지 않는다)

★ **여러 파일**(연도별 일곱 등)을 `hits` 전부 읽어 하나로 잇는다. 청크로 읽는다(가장 큰 파일이 3.7GB) — 거른 행만 메모리에 둔다.
★ 값은 한 글자도 안 고친다 — `na_filter=False` 로 읽어 빈 셀 · `N/A` · 공백이 원문 그대로 나간다. 필터 비교만 **양끝 공백을 걷은 값**으로 하고 **걷어야만 맞은 행 수**를
  계보에 남긴다(공백 문자열 방언이 필터 밖으로 새는 것을 숨기지 않는다).
★ 계보(`rec["extract"]`): 입력 파일별 `sha256` · 필터 전 · 후 행 수 · 공백을 걷어야 맞은 수. 「어떤 조건으로 몇 행이 몇 행이 됐나」가 재현의 전부다.

IN    대장 `contract` · `hits`(csv 여럿)
OUT   `<key>.csv`(utf-8-sig) · `rec` 의 계보 조각
밖    **`equals` 외의 연산자는 없다.** 값 보정 · 형 변환은 안 한다. **대장의 `scope` 를 바꾸지 않는다** — 그것은 이 단계가 선 뒤의 사람 판단이다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from firelane import ledger
from firelane.encoding import CANDIDATES_CSV_READ
from firelane.extract_decl import KINDS, NORMALIZERS, conditions, declared, normalize, problems  # noqa: F401  이 모듈이 다시 내보낸다(읽는 쪽 · 시험)
from firelane.hashing import sha256
from firelane.read.ctx import Ctx

CHUNK = 200_000


def _pass(path, enc, mode, flt):
    """한 인코딩으로 파일 하나를 청크로 읽는다. → (거른 표, 칸, 읽은 행, 공백을 걷어야 맞은 행)."""
    parts, cols, n_in, n_strip = [], None, 0, 0
    for ch in pd.read_csv(path, encoding=enc, dtype=str, chunksize=CHUNK, na_filter=False):
        if cols is None:
            cols = normalize(ch.columns, mode) if mode else [str(c) for c in ch.columns]
            for f in conditions(flt):
                if f["column"] not in cols:
                    raise ValueError(f"{path.name}: filter.column `{f['column']}` 이 헤더에 없다 — 헤더 {cols[:8]}{' …' if len(cols) > 8 else ''}")
        ch.columns = cols
        n_in += len(ch)
        if flt:
            hit, exact = True, True
            for f in conditions(flt):
                raw = ch[f["column"]]
                want = [str(v) for v in f["one_of"]] if "one_of" in f else [str(f["equals"])]
                hit &= raw.str.strip().isin(want)
                exact &= raw.isin(want)
            n_strip += int((hit & ~exact).sum())
            ch = ch[hit]
        if len(ch):
            parts.append(ch)
    if cols is None:
        raise ValueError(f"{path.name}: 빈 파일이다(헤더가 없다)")
    return (pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)), cols, n_in, n_strip


def _read_one(path, enc, mode, flt):
    last = None
    for cand in dict.fromkeys(x for x in ([enc] if enc else []) + list(CANDIDATES_CSV_READ) if x):
        try:
            return _pass(path, cand, mode, flt)
        except (UnicodeDecodeError, LookupError) as ex:
            last = ex
    raise last


def paths(e: dict, base: Path) -> list[Path]:
    """`--extract-from` 의 입력. 대장의 이름(glob)을 폴더 하나에서 **이름으로만** 맞춘다 — `landing/_hold` 는 provider 폴더가 없는 평평한 곳이다.

    ★ 추출을 선언한 항목에만 부른다(ingest 가 가른다). 전국본을 raw 에 올리지 않고 제자리에서 읽는 길이다(DECISIONS §647-4).
    """
    return sorted({q for pat in ledger.globs(e) for q in base.glob(Path(pat).name) if not ledger.is_acquisition_meta(q)})


def source_dir(arg: str, only) -> Path:
    """`--extract-from` 인자를 폴더로 받는다. `--only` 없이는 안 받는다 — 어느 항목이 그 폴더를 읽는지 지목해야 한다."""
    d = Path(arg).expanduser().resolve()
    if not d.is_dir():
        sys.exit(f"★ --extract-from {d} 가 폴더가 아니다")
    if not only:
        sys.exit("★ --extract-from 는 --only 와 같이 쓴다 — 추출을 선언한 항목만 그 폴더를 읽는다")
    return d


def kept(prev: dict | None, e: dict, out: Path, hits) -> dict | None:
    """**원본을 내린 추출 항목의 지난 기록.** 보존할 때만 그 레코드를, 아니면 None.

    전국본을 `status: missing` 으로 내리면 실물이 없어 `build()` 가 `MISSING` 레코드를 내고, 그것이 `_manifest.json` 의 계보(`extract`)와
    산출물 항목을 **덮어쓴다** — 원본을 내릴 근거가 그 계보인데 내리는 순간 계보가 사라진다. 산출물이 실물로 있을 때만 보존한다(DECISIONS §647-3).
    """
    if hits or ledger.absence(e)[0] != "missing" or not declared(e) or not prev:
        return None
    if prev.get("status") != "OK" or not prev.get("extract") or not all((out / o).exists() for o in prev.get("outputs", [])):
        return None
    return prev


def read_extracted(c: Ctx):
    """`csv_table` · `csv_table_multi` 의 추출 경로 — `hits` 전부를 읽어 거르고 하나로 잇는다."""
    key, e, out, rec = c.key, c.e, c.out, c.rec
    con = e.get("contract") or {}
    if bad := problems(key, e):
        raise ValueError(f"{key}: 추출 선언이 틀렸다 — " + " · ".join(bad))
    mode, flt = con.get("normalize_columns"), con.get("filter")
    optional = list(con.get("optional_cols") or [])
    floor = int(con.get("scope_min", 1 if flt else 0))
    ceil = con.get("scope_max")
    parts, files, ref = [], [], None
    for q in sorted(c.hits):
        d, cols, n_in, n_strip = _read_one(q, e.get("encoding"), mode, flt)
        if ref is None:
            ref = list(cols)
        elif cols != ref:
            new, old = [x for x in cols if x not in ref], [x for x in ref if x not in cols]
            if (bad := [x for x in new + old if x not in optional]):
                raise ValueError(f"{key}: {q.name} 의 칸이 {c.hits[0].name} 과 다르다 — 신규 {new} · 소실 {old} · 선언 안 된 것 {bad}(없어도 되는 칸은 contract.optional_cols)")
            for x in old:
                d[x] = ""
            ref += new
            for p in parts:
                for x in new:
                    p[x] = ""
        d = d[ref] if list(d.columns) != ref else d
        parts.append(d)
        files.append({"name": q.name, "sha256": sha256(q), "bytes": q.stat().st_size, "rows_in": n_in, "rows_out": len(d), "stripped_matches": n_strip})
    df = pd.concat(parts, ignore_index=True)[ref]
    n_in, n_out = sum(f["rows_in"] for f in files), len(df)
    lineage = {"normalize_columns": mode, "filter": flt, "rows_in": n_in, "rows_out": n_out, "files": files}
    print(f"  · {key}: 파일 {len(files)}개 · {n_in:,}행" + (f" → filter {' & '.join(f'{f['column']}={"|".join(map(str, f["one_of"])) if "one_of" in f else f["equals"]}' for f in conditions(flt))} → {n_out:,}행" if flt else " (필터 없음)")
          + (f" · 공백을 걷어야 맞은 행 {sum(f['stripped_matches'] for f in files):,}" if flt and any(f["stripped_matches"] for f in files) else ""))
    rec |= {"source_sha256": ",".join(f["sha256"][:16] for f in files), "resolved": " + ".join(f["name"] for f in files), "extract": lineage}
    rec.pop("ambiguous", None)                 # 여럿을 읽는 것이 정상이다. 모호하지 않다
    if ceil is not None and n_out > int(ceil):
        rec |= {"status": "FAIL", "features": n_out, "geom": [], "outputs": [],
                "error": f"거른 뒤 {n_out:,}행 > scope_max {int(ceil):,}(읽은 {n_in:,}행). 조건이 너무 넓다 — 같은 이름이 다른 지역에도 있나(필터를 AND 로 좁혀라)"}
        print(f"  ★ {key}: {rec['error']}")
        return rec
    if n_out < floor:
        rec |= {"status": "FAIL", "features": n_out, "geom": [], "outputs": [],
                "error": f"거른 뒤 {n_out}행 < scope_min {floor}(읽은 {n_in:,}행). 0행은 조용히 통과시키지 않는다 — 칸 이름 · 값 · 헤더 케이스를 확인하라"}
        print(f"  ★ {key}: {rec['error']}")
        return rec
    df.to_csv(out / f"{key}.csv", index=False, encoding="utf-8-sig")
    return rec | {"status": "OK", "features": n_out, "geom": [], "columns": list(df.columns), "outputs": [f"{key}.csv"]}

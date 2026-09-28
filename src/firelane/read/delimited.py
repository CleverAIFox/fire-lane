"""
delimited.py — 구분자 텍스트를 읽는 갈래. CSV 와 `|` 구분 텍스트.  (PLAN §1 #132)

IN    좌표 있는 CSV · zip 안 대용량 CSV · 헤더 없는 구분자 텍스트 · 좌표 없는 표
OUT   GeoDataFrame (좌표 있는 것) 또는 완성된 계보 조각 (표)
밖   **인코딩 판별은 `_io.read_csv_any` 가 든다.** 여기서 인코딩을 다시
      고르지 않는다 — 두 벌이 되면 대장의 `encoding` 이 어디서 먹는지 모르게 된다.
"""
from __future__ import annotations

import io
import zipfile

import geopandas as gpd
import pandas as pd

from firelane.hashing import sha256
from firelane.read._io import BBOX_4326, CRS_W, load_csv_points, read_csv_any
from firelane.read.ctx import Ctx


def read_csv_points(c: Ctx):
    """kind ("csv_points", "csv_point") 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    e = c.e
    src = c.src
    g = load_csv_points(src, e["x_col"], e["y_col"], e.get("encoding", "utf-8"))
    return g


def read_csv_points_in_zip(c: Ctx):
    """kind "csv_points_in_zip" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    e = c.e
    src = c.src
    hits = c.hits
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
    return g


def read_text_table(c: Ctx):
    """kind "text_table" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    key = c.key
    e = c.e
    src = c.src
    out = c.out
    rec = c.rec
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
    # ★ 기본값의 정본은 `ledger.delimiter_of` 하나다(§284-4).
    from firelane import ledger as _led
    delim = _led.delimiter_of(e)
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
    d.to_csv(out / f"{key}.csv", index=False, encoding="utf-8-sig")
    rec |= {"status": "OK", "features": len(d), "geom": [],
            "columns": list(d.columns), "outputs": [f"{key}.csv"]}
    return rec


def read_csv_table(c: Ctx):
    """kind "csv_table" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    key = c.key
    e = c.e
    src = c.src
    out = c.out
    rec = c.rec
    d = read_csv_any(src, e.get("encoding"), dtype=str)
    d.to_csv(out / f"{key}.csv", index=False, encoding="utf-8-sig")
    rec |= {"status": "OK", "features": len(d), "geom": [],
            "columns": list(d.columns), "outputs": [f"{key}.csv"]}
    return rec


def read_csv_table_multi(c: Ctx):
    """kind "csv_table_multi" 를 읽는다. ingest.build() 에서 그대로 옮겼다."""
    key = c.key
    e = c.e
    hits = c.hits
    out = c.out
    rec = c.rec
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
    d.to_csv(out / f"{key}.csv", index=False, encoding="utf-8-sig")
    rec["source_sha256"] = ",".join(sha256(q)[:16] for q in hits)
    rec["resolved"] = " + ".join(q.name for q in hits)
    rec.pop("ambiguous", None)          # 여러 개가 정상이다. 모호하지 않다
    print(f"  · {key}: {len(hits)}판 이어붙임 — "
          + " · ".join(f"{q.name} {len(x):,}행" for q, x in zip(hits, parts, strict=True)))
    rec |= {"status": "OK", "features": len(d), "geom": [],
            "columns": list(d.columns), "outputs": [f"{key}.csv"]}
    return rec

#!/usr/bin/env python3
"""
contract.py — 대장이 선언한 것과 raw 실물이 같은지 본다. ingest 앞에 선다.

    python -m firelane.contract              전체 — ★ 레이크 필요
    python -m firelane.contract hydrant_point cctv
    python -m firelane.contract --strict     경고도 실패로 본다
    python -m firelane.contract --declared   ★ 대장 **선언만** 본다. 레이크 불필요

── 왜 필요한가 ────────────────────────────────────────────────
MASTER 18-3 은 게이트를 이렇게 정해 두었다.

    계약 일치             통과
    컬럼 추가             통과 + 알림
    컬럼 소실 · 타입 변경   ★ 중단
    건수 ±30% 초과        ★ 중단
    CRS 변경             ★ 중단

**설계는 있었고 구현이 없었다.** 그래서 2026-08-15 소스 교체 때 넷이 새어
2026-08-17 실행 시점까지 살아남았다.

    ngii1k         kind: shp_dir 인데 ingest 에 분기가 없다      → 실행 중 ValueError
    ngii_road      layer NF_A_A01000 인데 실물은 N3A_A0010000   → 실행 중 파일 없음
    fire_station   x_col Y좌표 인데 그런 컬럼이 없다             → 실행 중 KeyError
    hydrant_point  파싱은 됐는데 광주가 0건이라 스코프에서 전멸  → ★ OK 0건 으로 통과

앞의 셋은 시끄럽게 죽어서 그나마 나았다. 넷째가 이 도구를 만든 이유다.
**조용한 0건이 제일 나쁘다.** OK 를 찍고 다음 단계로 넘어가면 segments 가
낡은 산출물을 집어 판정이 나오고, 그 숫자가 어디서 왔는지 아무도 모른다.

── 계약 선언 ──────────────────────────────────────────────────
sources.yaml 의 각 데이터셋에 contract 블록을 둔다. 전부 선택 항목이며
적힌 것만 검사한다. **어휘의 정본은 `firelane.ledger.CONTRACT_KEYS` 하나다**
— 여기 목록을 손으로 또 적지 않는다(2026-09-28 · §284-1).

★ 2026-09-28. 이 자리에 `crs: EPSG:4326 — 선언 CRS 와 실물 .prj 대조` 가
  적혀 있었다. **그런 키는 대장에 0건이고 이 파일은 그 키를 안 읽는다.**
  좌표계 선언은 항목 수준 `crs_native` 로 개명됐고(`ledger.crs_of()`),
  개명 때 이 머리말만 옛 이름을 들고 남았다. 낡은 참조 한 줄이 「대조를
  한다」는 약속으로 읽혔고 **아무도 안 하고 있었다**(§284-2).

★ 이 도구는 raw 를 읽기만 한다. 아무것도 쓰지 않는다.

── 두 갈래 (2026-09-28 · §284-3) ──────────────────────────────
    기본        대장 ↔ **실물** 대조.  ★ 레이크 필요 → CI 에서 못 돈다
    --declared  대장 **선언 자체**만 본다. 레이크 불필요 → CI·verify 에서 돈다

★ 왜 갈랐나. 이 도구는 MASTER §18-3b 가 취입 관문이라 이름까지 적어 둔
  것인데 **어디서도 안 불렸다**(§280). 레이크 없는 곳에서 돌리면 72종 중
  36종이 「파일 없음」으로 실패하므로 CI 에 붙일 수가 없었다. 그런데
  나머지 절반 — 무계약 · 모르는 키 · 미선언 좌표계 — 는 **실물이 필요
  없다.** 그 절반을 CI 로 올린다. 관문이 절반이라도 상설인 것이,
  전체가 아무 데서도 안 도는 것보다 세다.

── 판정기는 Pandera 다 (2026-09-24 · PLAN §13 W6-1 닫힘 · DECISIONS §227) ──
`required_cols` · `rows`(±허용폭) · `scope_min` 셋의 **판정**은
`pandera.DataFrameSchema` 가 한다. 종전에는 셋 다 손으로 `if` 를 짰다.

    손으로 짜면 무엇이 문제인가 — 이 저장소의 4족(직접 구현)이다.
    표준이 이미 가진 것을 다시 짜면 **그 재구현만의 버그**를 혼자 갖고,
    그 버그를 잡는 검사는 아무도 안 만든다. 실제로 손판은 `rows` 경계를
    `lo <= n <= hi` 닫힌 구간으로 쓰면서 그것을 어디에도 안 적었다.

    스키마로 적으면 **선언이 곧 판정**이다. 사람이 읽는 규칙과 기계가
    도는 규칙이 같은 객체이고, 그것이 이 절이 노리는 전부다.

★ 경계는 **한 글자도 안 바꿨다.** 닫힌 구간 · 허용폭 기본 0.30 ·
  컬럼 추가는 경고 · 스코프 하한은 미만일 때만 실패 — 전부 종전 그대로다.
  `tests/test_contract.py` 가 전후를 같은 입력으로 대조한다.

IN    sources.yaml · raw/**
OUT   없음 (검사). 종료코드 = 실패 수
밖    **Pandera 가 안 보는 것 셋을 이 파일이 손으로 본다** —
      ① 파일 인코딩(`encoding`) — 데이터프레임이 되기 **전**의 성질이라
         스키마에 못 적는다. `decode_ok()` 가 전량 디코딩으로 본다.
      ② zip 안 레이어 존재(`layer_must_exist`) — 파일시스템 물음이다.
      ③ 컬럼 **추가**(경고) — Pandera 의 `strict` 는 추가를 실패로만 다룰 수
         있고 경고가 없다. 추가는 실패가 아니므로 `strict=False` 로 두고
         여기서 센다.
      그리고 CSV·TXT 가 아닌 원본(shp·gpkg·tif)의 **내용**은 안 본다 —
      존재와 레이어만 본다. 기하 검증은 `firelane.guards` 소관이다.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
import zipfile
from pathlib import Path

from firelane.encoding import CANDIDATES_REPORT
from firelane.paths import ROOT

OK, WARN, FAIL = "OK", "경고", "★실패"


class Report:
    def __init__(self, key: str):
        self.key = key
        self.lines: list[tuple[str, str]] = []

    def add(self, level: str, msg: str) -> None:
        self.lines.append((level, msg))

    @property
    def worst(self) -> str:
        if any(l == FAIL for l, _ in self.lines):
            return FAIL
        if any(l == WARN for l, _ in self.lines):
            return WARN
        return OK

    def show(self) -> None:
        print(f"[{self.worst:4s}] {self.key}")
        for level, msg in self.lines:
            if level != OK:
                print(f"         {level}  {msg}")


def decode_ok(path: Path, enc: str) -> bool:
    """파일 전체를 디코딩해 본다. 앞부분만 읽으면 멀티바이트가 잘려 오판한다."""
    try:
        path.read_bytes().decode(enc)
        return True
    except Exception:
        return False


def read_csv(path: Path, enc: str, delim: str = ","):
    """구분자를 **대장에서 받는다.**

    ★ 2026-09-28 지뢰 제거. 종전에는 pandas 기본 쉼표로만 읽었다. 대장에는
      `delimiter: "|"` 인 `text_table` 이 둘(`navi_build` · `navi_jibun`)
      있고 그 `.txt` 는 이 도구가 CSV 로 세는 대상이다. 지금은 그 둘이
      `required_cols` 를 안 적어서 실제로 읽히지 않아 **안 터졌을 뿐**이다.
      누가 `required_cols` 를 하나 추가하면 파이프 파일을 쉼표로 읽어
      「컬럼 소실」을 오탐한다 — 대장을 고친 사람이 제 컬럼 이름을
      의심하게 되는 자리다. `read/delimited.py` 는 이미 옳게 읽고 있었다.
    """
    import pandas as pd
    return pd.read_csv(path, encoding=enc, sep=delim, dtype=str, low_memory=False)


def frame_schema(c: dict, scope_n: int | None = None):
    """대장 `contract:` 블록 → `pandera.DataFrameSchema`.

    ★ 컬럼은 전부 `str`·nullable 이다. `read_csv(dtype=str)` 로 읽으므로
      타입 판정은 이 층의 일이 아니다 — 여기가 보는 것은 **있는가**다.
    ★ `scope_n` 은 이미 센 값이다. 세는 일은 좌표 컬럼·bbox 를 알아야 해서
      스키마 밖이고, **판정**만 스키마가 든다. 세기와 판정을 갈라 두면
      「몇 건이었나」를 메시지에 담으면서도 통과·실패는 한 곳에서 난다.
    """
    import pandera.pandas as pa

    cols = {name: pa.Column(str, nullable=True, required=True, coerce=False)
            for name in (c.get("required_cols") or [])}
    checks = []

    want = c.get("rows")
    if want is not None:
        want = int(want)
        tol = float(c.get("rows_tolerance", 0.30))
        lo, hi = want * (1 - tol), want * (1 + tol)
        checks.append(pa.Check(
            lambda d, lo=lo, hi=hi: lo <= len(d) <= hi,
            name="rows",
            error=f"건수 선언 {want:,} ±{tol:.0%} 밖 ({lo:,.0f}~{hi:,.0f})"))

    smin = c.get("scope_min")
    if smin is not None and scope_n is not None:
        smin = int(smin)
        checks.append(pa.Check(
            lambda _d, n=scope_n, m=smin: n >= m,
            name="scope_min",
            error=f"스코프 안 {scope_n}건 — 하한 {smin}. 파싱은 됐으나 대상 지역이 없다"))

    return pa.DataFrameSchema(cols, checks=checks, strict=False, coerce=False)


def schema_failures(schema, d) -> list[str]:
    """스키마를 태우고 **사람이 읽는 줄**로 돌려준다. 통과면 빈 목록."""
    import pandera.pandas as pa

    try:
        schema.validate(d, lazy=True)
        return []
    except pa.errors.SchemaErrors as e:
        out, miss = [], []
        for rec in e.failure_cases.to_dict("records"):
            chk, case = rec.get("check"), rec.get("failure_case")
            if chk == "column_in_dataframe":
                miss.append(str(case))
            else:
                out.append(str(rec.get("check") or case))
        if miss:
            out.insert(0, f"컬럼 소실 {miss}")
        return out


# ── 좌표계 대조 — MASTER §18-3 의 「CRS 변경 → ★중단」 (2026-09-28) ──
# ★ 이 관문은 **선언만 있고 구현이 없었다.** `krgis/crs.py` 는 자기 래퍼 셋을
#   지우면서 그 근거로 「contract.py 가 선언과 실물을 대조하며」 를 들었고,
#   `contract.py` 머리말은 「선언 CRS 와 실물 .prj 대조」 를 적어 두었다.
#   **둘이 서로를 가리키고 실제로 하는 쪽이 없었다**(§284-2).
#
# ★ 두 판정을 나눈다. `krgis` 의 첫 원칙이 「추측하지 말고 측정한다」다 —
#     ① 선언 ↔ `.prj`      메타데이터끼리. 국내 SHP 는 이것이 없거나 틀리다
#     ② 선언 ↔ 좌표 실측    좌표 한 점을 후보 전부로 역변환해 본다
#   ②가 ①보다 세다. `.prj` 가 틀렸을 때 ①만 있으면 틀린 것끼리 맞는다.
#
# ★ **②의 한계를 적어 둔다.** 좌표 실측은 bbox 안에 떨어지는가로 본다.
#   `5181`(중부 y+50만) 과 `5174`(보정중부 Bessel) 는 지상 300m 차이라
#   광주 bbox 안에 나란히 떨어진다 — **좌표만으로는 못 가른다.** 실측으로
#   확인했고 그 쌍이 유일하다. 그래서 ②는 그 경우 경고를 내고 ①에게
#   넘긴다. 둘이 서로의 사각지대를 덮는다.
#
# ★ 순수 함수로 둔다. 레이크가 없는 곳에서도 **판정 자체**는 시험할 수 있어야
#   한다 — 합성 `.prj` 와 합성 좌표로 문다(`tests/test_crs_gate.py`).
#: `.prj` → EPSG 되찾기 문턱. **기본값 70 으로는 안 된다.**
#: ★ 실측 2026-09-28. 실물 `.prj` 는 GDAL 이 쓴 WKT1 이고, 그 글을 다시
#:   읽으면 `to_epsg()` 가 한국 좌표계 전부에서 `None` 을 낸다 —
#:   5186 · 5181 · 5174 · 5179 · 5187 다. 문턱을 25 로 내리면 전부 되찾는다.
#:   이것을 안 쓰면 **옳은 `.prj` 를 틀렸다고 우는 관문**이 되고, 그러면
#:   사람이 관문을 끈다. 우는 관문은 없는 관문보다 나쁘다.
EPSG_CONFIDENCE = 25


def prj_verdict(declared: str, prj_text: str) -> tuple[str, str] | None:
    """선언 좌표계 ↔ 실물 `.prj`. (수준, 메시지) 또는 None(일치)."""
    from pyproj import CRS as _CRS
    from pyproj.exceptions import CRSError as _CRSError

    if not declared:
        return None
    if not (prj_text or "").strip():
        return (WARN, "`.prj` 가 없다 — 선언을 믿고 간다. 국내 SHP 의 흔한 꼴이다")
    try:
        want, got = _CRS.from_user_input(declared), _CRS.from_wkt(prj_text)
    except (_CRSError, ValueError) as ex:
        return (WARN, f"`.prj` 를 못 읽었다 — {type(ex).__name__}")
    w_epsg = want.to_epsg(min_confidence=EPSG_CONFIDENCE)
    g_epsg = got.to_epsg(min_confidence=EPSG_CONFIDENCE)
    if w_epsg is not None and w_epsg == g_epsg:
        return None
    if want.equals(got, ignore_axis_order=True):
        return None
    return (FAIL, f"좌표계 선언 {declared} 인데 `.prj` 는 "
                  f"{f'EPSG:{g_epsg}' if g_epsg else got.name} 다")


def coord_verdict(declared: str, x: float, y: float) -> tuple[str, str] | None:
    """★ **측정한다.** 좌표 한 점이 선언 좌표계로 광주 안에 떨어지나."""
    from firelane.krgis.crs import offset_between, probe_crs

    if not declared:
        return None
    hits = [r.epsg for r in probe_crs(x, y) if r.inside_target]
    if not hits:
        return (WARN, f"좌표 ({x:,.1f}, {y:,.1f}) 가 어느 후보로도 광주 안에 "
                      f"안 떨어진다 — 대상 지역 밖 데이터일 수 있다")
    if declared in hits:
        # ★ 실측 2026-09-28. 후보가 둘 이상 맞는 경우는 **정확히 하나** —
        #   `5181`(중부 y+50만) 과 `5174`(보정중부 Bessel) 쌍이다. 둘은
        #   지상 300m 차이라 광주 bbox 안에 나란히 떨어진다. 나머지 아홉은
        #   전부 후보 하나만 맞는다. 그래서 이 경고는 **위험한 그 쌍에서만**
        #   울고 잡음이 없다. 좌표로는 여기까지고, 가르는 것은 `.prj` 다.
        if len(hits) > 1:
            return (WARN, f"좌표만으로는 {' · '.join(hits)} 를 못 가른다 "
                          f"(지상 {offset_between(x, y, *hits[:2]):,.0f}m 차이) — "
                          f"`.prj` 가 판정한다. 선언은 {declared}")
        return None
    try:
        gap = offset_between(x, y, declared, hits[0])
    except Exception:
        gap = float("nan")
    return (FAIL, f"좌표계 선언 {declared} 인데 실측은 {' · '.join(hits[:3])} 다 — "
                  f"{gap:,.0f}m 어긋난다")


def prj_in(path: Path, layer: str | None = None) -> str:
    """zip 또는 폴더에서 `.prj` 글을 꺼낸다. 없으면 빈 글."""
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as z:
                prjs = [n for n in z.namelist() if n.lower().endswith(".prj")]
                if layer:
                    stem = Path(layer).stem.lower()
                    prjs = [n for n in prjs
                            if Path(n).stem.lower() == stem] or prjs
                return z.read(prjs[0]).decode("utf-8", "replace") if prjs else ""
        except (zipfile.BadZipFile, KeyError, OSError):
            return ""
    sib = path.with_suffix(".prj")
    return sib.read_text(encoding="utf-8", errors="replace") if sib.is_file() else ""


def zip_names(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as z:
            return z.namelist()
    except zipfile.BadZipFile:
        return []


def check_one(key: str, e: dict, raw: Path, bbox: tuple | None) -> Report:
    r = Report(key)
    c = e.get("contract") or {}
    if e.get("status") == "missing":
        r.add(WARN, f"결손 선언됨 — {e.get('missing_why', '사유 미기재')}")
        return r
    # ★ 2026-10-07 (§427). `awaiting` — **아직 안 들어왔다.** §424 가 이 어휘를
    #   만들고 `refcheck.py` **하나만** 고쳐서 이 자리가 머지를 막았다. 규율은
    #   저쪽과 글자까지 같다: 사유를 적으면 경고, 비면 실패.
    if (why := str(e.get("awaiting") or "").strip()):
        r.add(WARN, f"아직 raw 에 없다 — {why}")
        return r
    if "awaiting" in e:
        r.add(FAIL, "`awaiting` 칸이 비었다 — 사유 없는 유예는 받지 않는다(§424)")
        return r
    if not c:
        r.add(WARN, "contract 블록 없음 — 검사할 수 없다")
        return r

    # ★ 2026-08-30. `e.get("file")` 단수를 읽고 있었다. 대장에서 그
    #   필드가 사라지자 42종 전부 "file 선언 없음" 이 됐다 — 계약 검사가
    #   실물을 한 번도 안 보고 끝난다. 조회기는 ledger 하나다.
    from firelane import ledger as _led
    pats = _led.globs(e)
    if not pats:
        r.add(FAIL, "files 선언 없음")
        return r
    hits = _led.paths_of(e, raw)
    if not hits:
        r.add(FAIL, f"파일 없음: {' · '.join(pats)}")
        return r

    # ── 인코딩 ────────────────────────────────────────────
    enc = c.get("encoding") or e.get("encoding")
    csvs = [p for p in hits if p.suffix.lower() in (".csv", ".txt")]
    if enc and csvs:
        for p in csvs:
            if not decode_ok(p, enc):
                got = [x for x in CANDIDATES_REPORT if decode_ok(p, x)]
                r.add(FAIL, f"{p.name} 인코딩 {enc} 아님. 실제 {got or '판별 실패'}")

    # ── zip 안 레이어 ─────────────────────────────────────
    layer = e.get("layer")
    if layer and c.get("layer_must_exist", True):
        for p in hits:
            if p.suffix.lower() != ".zip":
                continue
            names = [Path(n).name for n in zip_names(p)]
            if not names:
                r.add(FAIL, f"{p.name} zip 을 열 수 없다")
            # ★ 2026-09-17 (§181-3). 글롭이면 맞는 것이 정확히 하나여야 한다 — ingest 와 같은 규칙.
            elif any(ch in layer for ch in "*?["):
                got = [n for n in names if fnmatch.fnmatch(n, layer)]
                if len(got) != 1:
                    r.add(FAIL, f"{p.name} 안 {layer} 가 {len(got)}개다 — 하나여야 한다 {got[:6]}")
            elif layer not in names:
                near = [n for n in names if n.lower().endswith(".shp")][:6]
                r.add(FAIL, f"{p.name} 안에 {layer} 없음. shp 목록 {near}")

    # ── 좌표계 ① 선언 ↔ 실물 .prj ─────────────────────────
    declared_crs = _led.crs_of(e)
    if declared_crs:
        for p in hits:
            if p.suffix.lower() not in (".zip", ".shp"):
                continue
            if (v := prj_verdict(declared_crs, prj_in(p, layer))):
                r.add(v[0], f"{p.name} {v[1]}")

    # ── CSV 컬럼 · 건수 · 스코프 ──────────────────────────
    need = c.get("required_cols") or []
    want_rows = c.get("rows")
    # ★ 2026-09-24. `tol` 을 여기서 또 읽던 줄을 지웠다 — W6-1 에서 건수 판정이
    #   `frame_schema()` 안으로 들어가면서 **쓰이지 않는 사본**이 됐다.
    #   같은 값이 두 곳에 있으면 한쪽만 고쳐도 아무도 모른다(2족).
    smin = c.get("scope_min")

    if csvs and (need or want_rows is not None or smin is not None):
        try:
            import pandas as pd
            # ★ 구분자 기본값의 정본은 `ledger.delimiter_of` 하나다(§284-4).
            _delim = _led.delimiter_of(e)
            d = pd.concat([read_csv(p, enc or "cp949", _delim) for p in csvs],
                          ignore_index=True)
        except Exception as ex:
            r.add(FAIL, f"CSV 읽기 실패: {type(ex).__name__}: {ex}")
            return r

        # ── 컬럼 **추가**는 경고다. Pandera 의 strict 는 실패만 낼 수 있어
        #    여기서 센다(머리말 `밖` ③).
        extra = [c2 for c2 in d.columns if need and c2 not in need]
        if extra and need:
            r.add(WARN, f"컬럼 추가 {extra[:8]}{'…' if len(extra) > 8 else ''}")

        # ── 스코프 안 유효 건수를 **센다.** 판정은 스키마가 한다.
        #    hydrant_point 0건이 여기서 걸린다.
        scope_n = None
        if smin is not None and bbox:
            xc, yc = e.get("x_col"), e.get("y_col")
            if not (xc and yc):
                r.add(WARN, "scope_min 선언됐으나 x_col/y_col 이 없다")
            elif xc not in d.columns or yc not in d.columns:
                r.add(FAIL, f"좌표 컬럼 없음: {xc} / {yc}")
            else:
                x = pd.to_numeric(d[xc], errors="coerce")
                y = pd.to_numeric(d[yc], errors="coerce")
                nbad = int(x.isna().sum() + y.isna().sum())
                if nbad:
                    r.add(WARN, f"좌표 파싱 실패 {nbad}건")
                x0, y0, x1, y1 = bbox
                scope_n = int(((x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)).sum())

        # ── 좌표계 ② 선언 ↔ 좌표 **실측** ─────────────────
        # ★ `.prj` 가 없는 표 소스는 이쪽이 유일한 대조다. 한 점만 본다 —
        #   전량을 재는 것은 이 층의 일이 아니고, 좌표계가 파일 안에서
        #   섞이는 경우는 `guards` 가 본다.
        if declared_crs and (xc := e.get("x_col")) and (yc := e.get("y_col")):
            if xc in d.columns and yc in d.columns:
                _x = pd.to_numeric(d[xc], errors="coerce").dropna()
                _y = pd.to_numeric(d[yc], errors="coerce").dropna()
                if len(_x) and len(_y):
                    if (v := coord_verdict(declared_crs,
                                           float(_x.iloc[0]), float(_y.iloc[0]))):
                        r.add(v[0], v[1])

        # ── 판정 — 컬럼 소실 · 건수 · 스코프 하한 (Pandera)
        for line in schema_failures(frame_schema(c, scope_n), d):
            r.add(FAIL, line)
        if scope_n is not None and smin is not None and scope_n >= int(smin):
            r.add(OK, f"스코프 안 {scope_n}건")
        if want_rows is not None:
            r.add(OK, f"건수 {len(d):,}")
    return r


# ── 선언만 보는 갈래 — 레이크 불필요 ──────────────────────────
# ★ 2026-10-08 (DECISIONS §431 · PLAN #157). 래칫 넷과 `real_verdict` ·
#   `declared_issues` 를 `firelane/contract_verdict.py` 로 떼어 냈다.
#   이 파일은 **정확히 상한 600 에서 살다가** §427·§429 가 기능을 더해
#   621 이 됐고, §431 의 import 한 줄에 **622** 가 됐다. 행이 미리 적어 둔
#   쪼갤 자리가 여기다 — 「수를 세고 래칫과 댄다」 한 묶음이다.
from firelane.contract_verdict import (
    CRS_DECLARED_RATCHET,
    NO_CONTRACT_RATCHET,
    declared_issues,
    real_verdict,
)


def cmd_declared(ds: dict) -> int:
    from firelane import ledger as _led

    bad, warn, no_contract, crs_n = declared_issues(ds)
    print(f"── 대장 계약 선언  ({len(ds)}종 · 어휘 {len(_led.CONTRACT_KEYS)}개)")
    for w in warn:
        print(f"  ⚠ {w}")
    for b in bad:
        print(f"  ✗ {b}")

    rc = 1 if bad else 0
    print(f"\n  무계약 {no_contract}  래칫 {NO_CONTRACT_RATCHET}")
    if no_contract > NO_CONTRACT_RATCHET:
        print(f"  ✗ 무계약이 {no_contract} — 기록 {NO_CONTRACT_RATCHET} 보다 늘었다")
        rc = 1
    elif no_contract < NO_CONTRACT_RATCHET:
        print(f"  ✗ 무계약이 {no_contract} 로 줄었다 — "
              f"`NO_CONTRACT_RATCHET` 을 {no_contract} 으로 조여라")
        rc = 1

    print(f"  crs_native 선언 {crs_n}  래칫 {CRS_DECLARED_RATCHET}")
    if crs_n < CRS_DECLARED_RATCHET:
        print(f"  ✗ 좌표계 선언이 {crs_n} 로 줄었다 — 기록 {CRS_DECLARED_RATCHET}")
        rc = 1
    elif crs_n > CRS_DECLARED_RATCHET:
        print(f"  ✗ 좌표계 선언이 {crs_n} 로 늘었다 — "
              f"`CRS_DECLARED_RATCHET` 을 {crs_n} 로 올려라. 좋은 방향이다")
        rc = 1

    print("\n✓ 대장 선언이 기록과 같다" if not rc else
          "\n★ 대장 선언을 고쳐라. **실물은 안 봤다** — 그쪽은 레이크가 붙은 곳에서 본다")
    return rc


def main() -> int:
    import yaml
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--declared", action="store_true",
                    help="대장 선언만 본다 (레이크 불필요 · CI 가 이것을 돌린다)")
    a = ap.parse_args()

    from firelane.paths import RAW
    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    ds = y.get("datasets", {})
    bbox = y.get("bbox_4326")
    bbox = tuple(bbox) if bbox and len(bbox) == 4 else None

    if a.declared:
        if a.keys:
            ap.error("--declared 는 대장 전체를 본다 — 키를 같이 주지 않는다")
        return cmd_declared(ds)

    keys = a.keys or sorted(ds)
    unknown = [k for k in keys if k not in ds]
    for k in unknown:
        print(f"[{FAIL}] {k}  대장에 없다")
    keys = [k for k in keys if k in ds]

    reports = [check_one(k, ds[k] or {}, Path(RAW), bbox) for k in keys]
    for r in reports:
        r.show()

    nf = sum(1 for r in reports if r.worst == FAIL) + len(unknown)
    nw = sum(1 for r in reports if r.worst == WARN)
    print(f"\n{len(reports)}종 · 실패 {nf} · 경고 {nw}")
    if nf:
        print("★ 대장과 실물이 다르다. ingest 를 돌리기 전에 맞춰라.")
        print("  실물이 옳으면 대장을 고친다 — 코드가 대장을 따르는 것이지")
        print("  대장이 무조건 맞다는 뜻이 아니다.")

    # ★ 키를 짚어 부른 것은 **정확히 그 종의 판정**이다. 래칫을 끼우면
    #   「내가 고친 그 한 종이 여전히 깨졌다」가 초록으로 나온다.
    if a.keys or a.strict:
        return 1 if (nf or (a.strict and nw)) else 0
    rc, say = real_verdict(nf, nw)
    print()
    for line in say:
        print(line)
    return rc


if __name__ == "__main__":
    sys.exit(main())

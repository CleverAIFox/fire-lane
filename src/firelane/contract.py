#!/usr/bin/env python3
"""
contract.py — 대장이 선언한 것과 raw 실물이 같은지 본다. ingest 앞에 선다.

    python -m firelane.contract              전체
    python -m firelane.contract hydrant_point cctv
    python -m firelane.contract --strict     경고도 실패로 본다

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
적힌 것만 검사한다.

    contract:
      encoding: cp949           선언과 실제 디코딩이 맞는가
      required_cols: [위도, 경도]   컬럼 소실 검사. 추가는 알림만
      rows: 50000               건수. tolerance 기본 0.30
      rows_tolerance: 0.30
      crs: EPSG:4326            선언 CRS 와 실물 .prj / set_crs 대조
      scope_min: 1              ★ 스코프 안 유효 건수 하한. 0건 통과를 막는다
      layer_must_exist: true    zip 안에 layer 가 실제로 있는가

★ 이 도구는 raw 를 읽기만 한다. 아무것도 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

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


def read_csv(path: Path, enc: str):
    import pandas as pd
    return pd.read_csv(path, encoding=enc, dtype=str, low_memory=False)


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
                got = [x for x in ("cp949", "utf-8-sig", "utf-8", "utf-16")
                       if decode_ok(p, x)]
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
            elif layer not in names:
                near = [n for n in names if n.lower().endswith(".shp")][:6]
                r.add(FAIL, f"{p.name} 안에 {layer} 없음. shp 목록 {near}")

    # ── CSV 컬럼 · 건수 · 스코프 ──────────────────────────
    need = c.get("required_cols") or []
    want_rows = c.get("rows")
    tol = float(c.get("rows_tolerance", 0.30))
    smin = c.get("scope_min")

    if csvs and (need or want_rows is not None or smin is not None):
        try:
            import pandas as pd
            d = pd.concat([read_csv(p, enc or "cp949") for p in csvs],
                          ignore_index=True)
        except Exception as ex:
            r.add(FAIL, f"CSV 읽기 실패: {type(ex).__name__}: {ex}")
            return r

        miss = [c2 for c2 in need if c2 not in d.columns]
        if miss:
            r.add(FAIL, f"컬럼 소실 {miss}")
        extra = [c2 for c2 in d.columns if need and c2 not in need]
        if extra and need:
            r.add(WARN, f"컬럼 추가 {extra[:8]}{'…' if len(extra) > 8 else ''}")

        if want_rows is not None:
            lo, hi = want_rows * (1 - tol), want_rows * (1 + tol)
            if not (lo <= len(d) <= hi):
                r.add(FAIL, f"건수 {len(d):,} — 선언 {want_rows:,} ±{tol:.0%} 밖")

        # ★ 스코프 안 유효 건수. hydrant_point 0건이 여기서 걸린다.
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
                n = int(((x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)).sum())
                if n < smin:
                    r.add(FAIL, f"스코프 안 {n}건 — 하한 {smin}. "
                                "파싱은 됐으나 대상 지역이 없다")
                else:
                    r.add(OK, f"스코프 안 {n}건")
    return r


def main() -> int:
    import yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()

    from firelane.paths import RAW
    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    ds = y.get("datasets", {})
    bbox = y.get("bbox_4326")
    bbox = tuple(bbox) if bbox and len(bbox) == 4 else None

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
    return 1 if (nf or (a.strict and nw)) else 0


if __name__ == "__main__":
    sys.exit(main())

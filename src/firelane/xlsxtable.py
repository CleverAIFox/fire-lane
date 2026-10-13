#!/usr/bin/env python3
"""
xlsxtable.py — 엑셀 통합문서(.xlsx) 시트 하나 → 표 그대로의 CSV.

    python -m firelane.xlsxtable <표.xlsx>      옮긴 결과를 찍는다 (아무것도 안 쓴다)

`prep` 이 raw → norm 에서 부른다(DECISIONS §172 · §515). **형식만 바꾼다. 값은 안
바꾼다.** 머리글을 해석하지 않고, 병합을 채우지 않고, 쉼표를 털지 않는다 — 그 일은
전부 ingest 의 것이다(prep 머리말의 경계).

── 왜 `csv_table` 이 아니고 변환기인가 ────────────────────────
소급 실측(2026-10-13) — 기존 대장 80종이 기계로 읽는 형식은 **넷뿐**이다:
csv 27 · zip 24(shp/dbf) · json 3 · txt 2. 그 밖의 34종(pdf·hwp·hwpx·tif·xml)은
전부 `raw_only` 고 schema 가 0/34 다. **xlsx 는 80종에 0번 나온다.**
`kind: csv_table` + `ext: [xlsx]` 로 적으면 그 네 형식의 불변식이 깨지고,
`ledger_schema.probe` 가 xlsx 를 텍스트로 열어 인코딩을 묻는다.

집의 답은 이미 있었다 — `gjfire_vehicle_card` 가 `raw_only` + `norm_convert:
vehiclecard` 로 PDF 서식을 norm CSV 로 옮긴다. 엑셀도 같은 자리다.

── 값의 규율 ──────────────────────────────────────────────────
글자 칸은 글자 그대로. 숫자 칸은 **저장된 값**이다 — 시트의 `#,##0` 서식이
`3000` 을 `3,000` 으로 **보여주는** 것은 화면이고, 파일이 적은 것은 `3000` 이다.
서식을 되살려 쓰면 변환기가 값을 **만드는** 것이 된다.

★ 그래서 **속이는 서식에서는 운다.** 백분율(`0.15` → 화면 `15%`)과 날짜 일련수는
  저장값과 화면이 서로 다른 수다. 골라 주지 않고 멈춘다 — 고르는 것은 사람이다.
★ 수식 칸도 운다. `data_only` 는 엑셀이 **마지막에 저장한 캐시**를 읽고, 캐시가
  없으면 조용히 빈 칸이 된다. 조용한 NULL 이 가장 나쁘다.
★ 반대로 **원문에 없는 글자는 뺀다** — `_x000D_`(엑셀의 CR 벗어남)가 글자로
  남는다. `_unescape` 가 든다.

IN    .xlsx 1개 (raw) — 시트 **하나**
OUT   CSV 1개 (norm) — 시트 행 수만큼 · UTF-8 · LF
PARAM VERSION — 옮기는 규칙이 바뀌면 올린다. `_prep.json` 이 기록한다
밖    머리글이 몇 줄인가 · 병합이 무엇을 뜻하는가 · 수를 수로 읽을 것인가는
      **안 본다.** 그것은 읽는 쪽(ingest · 분석)의 일이다. 여기는 칸의 자리와
      글자만 옮기고, 병합 범위는 `_prep.json` 에 적어 **지식을 안 버린다**.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import sys
from pathlib import Path

VERSION = "2026-10-13.1"

#: 저장값과 화면이 **다른 수**가 되는 서식. 여기서는 고르지 않고 운다.
DECEIVING_FMT = ("%",)


class SheetError(ValueError):
    pass


def _unescape(s: str) -> str:
    """`_x000D_` → CR, 그다음 칸 안의 줄바꿈을 LF 로. **원문에 없는 글자를 뺀다.**

    ★ 2026-10-13. 화재 표의 `발화개요` 가 `…화재발생_x000D_\\n- 지붕…` 으로
      나왔다. 셀의 실제 내용은 CR+LF 고 `_x000D_` 는 엑셀이 CR 을 XML 에 적은
      **벗어남**인데 `load_workbook` 이 그것을 안 되돌린다. 글자 일곱이 원문에
      없다 — `vehiclecard` 가 pypdf 의 끼운 공백을 빼는 것과 같은 자리다.
    ★ 되돌리는 일은 **openpyxl 이 한다**(`utils.escape.unescape`). 손으로 짜면
      `tests/test_handrolled.py` 가 드는 사본이 하나 더 생긴다 — 그 함수는
      같은 정규식을 이미 들고 있고, 벗어남의 문법은 엑셀의 것이다.
    ★ 되돌린 뒤 셀 안의 CRLF·CR 을 LF 로 맞춘다. `_prep.json` 이 적는
      `dst_newline: lf` 는 **파일 전체**의 선언이고 칸 안도 그 파일이다.
    """
    from openpyxl.utils.escape import unescape
    return unescape(s).replace("\r\n", "\n").replace("\r", "\n")


def cell_text(value, number_format: str = "General") -> str:
    """칸 하나의 글자. 순수하다 — 파일을 안 읽는다."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        # 날짜 서식이 붙은 칸은 저장값이 일련수(44604)다. 그 수를 쓰면 사람이
        # 못 읽고, 서식을 되살리면 변환기가 값을 만든다. 둘 다 안 한다.
        raise SheetError(
            f"날짜/시각 칸이다 — 저장값은 일련수고 화면은 `{value}` 다. "
            "어느 쪽이 실물인지는 변환기가 고를 일이 아니다")
    if isinstance(value, (int, float)):
        if any(m in (number_format or "") for m in DECEIVING_FMT):
            raise SheetError(
                f"서식 `{number_format}` 이 저장값 {value!r} 과 **다른 수**를 "
                "보여준다 — 고르지 않고 멈춘다")
        return str(value)
    if isinstance(value, str):
        if value.startswith("="):
            raise SheetError(f"수식 칸이다 — `{value}`. 캐시가 없으면 조용히 빈다")
        return _unescape(value)
    raise SheetError(f"옮길 규칙이 없는 칸 — {type(value).__name__} {value!r}")


def _trim(rows: list[list[str]]) -> list[list[str]]:
    """꼬리의 완전 빈 행·열을 뗀다.

    ★ **사이의 빈 행은 남긴다.** 화재 표의 빈 행 셋은 연도 구분자고, 그것을
      지우면 파일이 적은 것을 바꾼다. 꼬리의 빈 것만 엑셀 `dimension` 기록의
      산물이다(일방통행 표는 33행인데 60행으로 적혀 있다).
    """
    while rows and not any(c.strip() for c in rows[-1]):
        rows.pop()
    if not rows:
        return rows
    width = max(len(r) for r in rows)
    while width > 1 and all(not r[width - 1].strip() for r in rows if len(r) >= width):
        width -= 1
    return [r[:width] for r in rows]


def sheet_rows(ws, raw_ws=None) -> list[list[str]]:
    """시트 → 글자표. `raw_ws` 는 수식을 보려고 받는 같은 시트의 비캐시 판이다."""
    rows: list[list[str]] = []
    for r in range(1, ws.max_row + 1):
        row = []
        for c in range(1, ws.max_column + 1):
            cell = ws.cell(r, c)
            try:
                row.append(cell_text(cell.value, cell.number_format))
                if raw_ws is not None:
                    cell_text(raw_ws.cell(r, c).value)
            except SheetError as e:
                raise SheetError(f"{ws.title}!{cell.coordinate}: {e}") from None
        rows.append(row)
    return _trim(rows)


def read(src: Path) -> tuple[list[list[str]], dict]:
    """.xlsx → (글자표, 메타). 시트가 둘 이상이면 운다."""
    from openpyxl import load_workbook
    wb = load_workbook(src, data_only=True, read_only=False)
    if len(wb.sheetnames) != 1:
        raise SheetError(
            f"시트가 {len(wb.sheetnames)}개다 — {wb.sheetnames}. 어느 것이 "
            "실물인지는 변환기가 고를 일이 아니다")
    name = wb.sheetnames[0]
    ws = wb[name]
    merged = [str(m) for m in ws.merged_cells.ranges]
    raw_ws = load_workbook(src, data_only=False, read_only=False)[name]
    rows = sheet_rows(ws, raw_ws)
    return rows, {"sheet": name,
                  "sheet_rows": len(rows),
                  "sheet_cols": max((len(r) for r in rows), default=0),
                  # ★ 병합은 채우지 않고 **적는다** — 지식을 버리지 않는다
                  "merged": sorted(merged)}


def to_csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def convert(src: Path, dst: Path) -> dict:
    """raw xlsx → norm CSV. `_prep.json` 에 남길 메타를 돌려준다."""
    rows, meta = read(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(to_csv_bytes(rows))
    return {"converter": "xlsxtable", "converter_version": VERSION,
            "src_encoding": "xlsx", "dst_encoding": "utf-8",
            "dst_newline": "lf", **meta}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("경로", help="엑셀 통합문서")
    rows, meta = read(Path(ap.parse_args().경로))
    # ★ 셈은 stderr 로. stdout 은 **CSV 하나**여야 넘겨 쓸 수 있다.
    print(f"  시트 {meta['sheet']} · {meta['sheet_rows']}행 × "
          f"{meta['sheet_cols']}열 · 병합 {len(meta['merged'])}", file=sys.stderr)
    sys.stdout.write(to_csv_bytes(rows).decode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

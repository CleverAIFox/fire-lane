#!/usr/bin/env python3
"""
ledger_schema.py — 실물에서 스키마를 읽어 대장에 적는다.

FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다
  `test_no_source_patching_scripts` 의 예외 마커. 이 도구는 대장(데이터)만
  고치고 소스 코드는 건드리지 않는다. 대장 값은 저장소 밖 raw 실물에서
  나오므로 diff 로 담을 수 없다.

    uv run python tools/ledger_schema.py            계획만
    uv run python tools/ledger_schema.py --apply     대장에 기록
    uv run python tools/ledger_schema.py --check     대장과 실물이 어긋났나

── schema 와 contract 는 다르다 ───────────────────────────────
    schema     **실물이 이렇게 생겼다**. 기술(descriptive). 자동 생성
    contract   **이래야 한다**. 규범(normative). 사람이 고른다

대장에 이미 `contract:` 가 20건 있고 거기 `required_cols` · `rows` 가 들어
있다. 그것을 대체하지 않는다. `contract` 는 "이 컬럼이 없으면 파이프라인을
세운다" 는 약속이고, `schema` 는 "지금 실물에 이런 컬럼이 있다" 는 사실이다.

★ 둘을 합치면 안 되는 이유 — 실물이 바뀌었을 때 **약속이 함께 바뀌면
  아무도 못 알아챈다.** 지금 이 저장소에서 제일 비싼 사고가 전부 그
  형태였다(선언과 실물이 어긋난 채 조용히 통과).

  그래서 `--check` 가 존재한다. 실물이 대장과 달라지면 시끄럽게 센다.

── 무엇을 읽나 ────────────────────────────────────────────────
    csv_points · csv_table · csv_table_multi   헤더 · 행수 · 인코딩
    csv_points_in_zip                          zip 안 CSV
    shp_zip · shp_zip_multi · dbf_in_zip       레이어 목록 · 속성 컬럼
    raw_only                                   ★ 읽지 않는다(문서·래스터)

★ 값은 안 읽는다. 컬럼 이름과 개수만 본다. 개인정보가 섞인 소스가 있고
  (`enforcement` 의 위반장소명), 스키마에 표본값을 넣으면 그것이 저장소로
  들어온다.

IN    $FIRE_LANE_DATA/raw · sources.yaml
OUT   sources.yaml (datasets[*].schema)
PARAM 없음
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "sources.yaml"

CSV_KINDS = {"csv_points", "csv_point", "csv_table", "csv_table_multi",
             "csv_points_in_zip"}
SHP_KINDS = {"shp_zip", "shp_zip_multi", "dbf_in_zip", "shp_dir"}

MAX_COLS = 60          # 이보다 많으면 접는다. 대장이 읽을 수 없게 된다


def _raw() -> Path:
    from firelane.paths import RAW
    return RAW


def _decode(b: bytes, declared: str | None) -> tuple[str, str]:
    """선언을 먼저 믿되, 안 되면 후보를 순서대로 시도한다.

    ★ `firelane.encoding.detect()` 를 안 쓴다. 그것은 **파일 경로**를 받고
      여기는 zip 안 바이트 조각을 다룬다. 조각은 멀티바이트 경계에서
      잘려 있어 strict 디코드가 실패할 수 있고, 그것은 인코딩이 틀린
      것이 아니다. 판정이 아니라 헤더 한 줄을 읽는 것이 목적이다.
    """
    if declared:
        try:
            return b.decode(declared), declared
        except UnicodeDecodeError:
            pass
    for c in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return b.decode(c), c
        except UnicodeDecodeError:
            continue
    return b.decode("cp949", errors="replace"), "cp949?"


def _csv_header(data: bytes, declared: str | None) -> dict:
    text, used = _decode(data, declared)
    head = text.splitlines()[:2]
    if not head:
        return {"error": "빈 파일"}
    cols = next(csv.reader(io.StringIO(head[0])), [])
    return {"columns": [c.strip().lstrip("\ufeff") for c in cols if c.strip()],
            "encoding_seen": used}


def probe(key: str, e: dict) -> dict | None:
    """대장 항목 하나의 스키마. 못 읽으면 None."""
    kind = e.get("kind")
    if kind in (None, "raw_only"):
        return None
    files = e.get("files") or ([e["file"]] if "file" in e else [])
    if not files:
        return None
    pat = str(files[0])
    hits = sorted(_raw().glob(pat)) if any(c in pat for c in "*?[") else (
        [_raw() / pat] if (_raw() / pat).exists() else [])
    if not hits:
        return {"error": f"실물 없음: {pat}"}
    src = hits[0]
    declared = e.get("encoding")

    try:
        if kind in CSV_KINDS:
            if src.suffix.lower() == ".zip":
                with zipfile.ZipFile(src) as z:
                    inner = [n for n in z.namelist()
                             if n.lower().endswith(".csv")
                             and (e.get("inner_contains", "") in n)]
                    if not inner:
                        return {"error": "zip 안에 CSV 가 없다"}
                    with z.open(sorted(inner)[0]) as f:
                        out = _csv_header(f.read(1 << 18), declared)
                out["source"] = sorted(inner)[0]
                return out
            return _csv_header(src.read_bytes()[:1 << 18], declared)

        if kind in SHP_KINDS:
            with zipfile.ZipFile(src) as z:
                names = z.namelist()
            layers = sorted({Path(n).stem for n in names
                             if n.lower().endswith((".shp", ".dbf"))})
            out = {"layers": layers[:MAX_COLS]}
            if len(layers) > MAX_COLS:
                out["layers_total"] = len(layers)
            lay = e.get("layer")
            if lay:
                out["layer_used"] = lay
                try:
                    import pyogrio
                    info = pyogrio.read_info(f"/vsizip/{src}/{lay}")
                    out["columns"] = list(info["fields"])[:MAX_COLS]
                    out["features"] = int(info["features"])
                except Exception as ex:            # noqa: BLE001
                    out["columns_error"] = f"{type(ex).__name__}: {ex}"[:90]
            return out
    except Exception as ex:                        # noqa: BLE001
        return {"error": f"{type(ex).__name__}: {ex}"[:110]}
    return None


def _q(v) -> str:
    """YAML 안전 스칼라. 작은따옴표로 감싸고 내부 따옴표는 두 번 쓴다."""
    return "'" + str(v).replace("'", "''") + "'"


def _fmt(sch: dict) -> str:
    """YAML 블록. 손으로 고치지 말라는 표시를 단다."""
    lines = ["    schema:                       # AUTO — ledger_schema.py 가 쓴다"]
    for k in ("layers", "layer_used", "columns", "features",
              "encoding_seen", "source", "error", "columns_error",
              "layers_total"):
        if k not in sch:
            continue
        v = sch[k]
        # ★ 전부 따옴표로 감싼다. 컬럼명에 `높이(m)` 처럼 괄호가 있고
        #   에러 메시지에는 콜론이 들어간다 — 맨값으로 쓰면 YAML 이 깨진다.
        #   실증했다(2026-08-26, DataSourceError 의 콜론).
        if isinstance(v, list):
            inner = ", ".join(_q(x) for x in v)
            lines.append(f"      {k}: [{inner}]")
        elif isinstance(v, int):
            lines.append(f"      {k}: {v}")
        else:
            lines.append(f"      {k}: {_q(v)}")
    return "\n".join(lines) + "\n"


def _span(s: str, key: str) -> tuple[int, int, str]:
    m = re.search(rf"^  {re.escape(key)}:\n", s, re.MULTILINE)
    if not m:
        return -1, -1, ""
    b = re.search(rf"^  {re.escape(key)}:\n((?:    .*\n|      .*\n|\n)*)",
                  s, re.MULTILINE)
    return m.end(), m.end() + len(b.group(1)), b.group(1)


def _drop_schema(body: str) -> str:
    return re.sub(r"^    schema:.*\n(?:      .*\n)*", "", body,
                  count=1, flags=re.MULTILINE)


def run(*, apply: bool, check: bool) -> int:
    s = YAML.read_text(encoding="utf-8")
    d = yaml.safe_load(s) or {}
    ds = d.get("datasets") or {}
    ok = err = skip = drift = 0

    for key, e in ds.items():
        sch = probe(key, e)
        if sch is None:
            skip += 1
            continue
        if "error" in sch:
            print(f"  ! {key:22} {sch['error']}")
            err += 1
            continue
        cols = sch.get("columns") or sch.get("layers") or []
        print(f"  {key:22} {len(cols):3}개  {', '.join(map(str, cols[:6]))}"
              f"{' …' if len(cols) > 6 else ''}")
        ok += 1

        if check:
            old = (e.get("schema") or {})
            for f in ("columns", "layers"):
                if f in old and f in sch and list(old[f]) != list(sch[f]):
                    a, b = set(map(str, old[f])), set(map(str, sch[f]))
                    print(f"      ★ {f} 가 대장과 다르다 — "
                          f"사라짐 {sorted(a - b)[:4]} · 새로 {sorted(b - a)[:4]}")
                    drift += 1
            continue

        if apply:
            st, en, body = _span(s, key)
            if st < 0:
                continue
            nb = _drop_schema(body) + _fmt(sch)
            s = s[:st] + nb + s[en:]

    if apply:
        yaml.safe_load(s)
        YAML.write_text(s, encoding="utf-8")
        print("\n적용 · YAML 파싱 OK")
    print(f"\n읽음 {ok} · 실패 {err} · 대상아님 {skip}"
          + (f" · ★ 드리프트 {drift}" if check else ""))
    if not (apply or check):
        print("아무것도 바꾸지 않았다.  --apply 로 기록한다.")
    return 1 if (err or drift) else 0


def main() -> int:
    # ★ 관문. 레이크가 없으면 여기서 멈춘다 — 판정만 하고 안 막으면
    #   엉뚱한 곳에 계층을 만든다(2026-08-27).
    from firelane.paths import require_lake
    require_lake(need=("raw",))

    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="대장과 실물이 어긋났나. CI 가 아니라 사람이 돌린다")
    a = ap.parse_args()
    return run(apply=a.apply, check=a.check)


if __name__ == "__main__":
    sys.exit(main())

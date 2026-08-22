#!/usr/bin/env python3
"""
ngi.py — NGI/NDA 포맷 단일 리더. 기하와 속성을 함께 읽는다.

    from firelane.ngi import read_ngi, layer_index

── 왜 이 파일이 생겼나 ────────────────────────────────────────
ngii1k.py 의 parse_ngi 가 기하만 읽고 .nda(속성)를 통째로 버리고 있었다.
그래서 아래 속성들이 원본에 있는데도 없는 것으로 취급됐다.

    A0020000 도로중심선  도로폭 · 차로수 · 일방통행 · 분리대유무 · 도로구분
    A0033320 보도        폭 · 재질 · 자전거도로유무 · 종류

도로폭과 일방통행은 폭 판정과 네비 라우팅의 핵심 입력이다.
버리고 있던 걸 다른 소스에서 다시 구하려 하고 있었다.

── 포맷 ───────────────────────────────────────────────────────
.ngi 와 .nda 는 짝이다. 같은 레이어, 같은 $RECORD 번호로 정렬된다.

    .ngi                        .nda
    <LAYER_START>               <LAYER_START>
    $LAYER_NAME "A0020000"      $LAYER_NAME "A0020000"
    <DATA>                      $ASPATIAL_FIELD_DEF
    $RECORD 1                     ATTRIB("도로폭",NUMERIC,9,3,TRUE)
    LINESTRING                  <DATA>
    12                          $RECORD 1
    192740.1 283600.2 ...         1, "동명로25번길", 6.0, ...

★ 레코드 순서로 짝짓는다. 어느 한쪽에서 파싱 실패로 레코드를 건너뛰면
  그 뒤가 전부 밀린다. 그래서 실패한 레코드도 None 으로 자리를 지킨다.
  기존 코드는 except 에서 continue 라 조용히 밀렸다.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon

LAYER_NAME_RE = re.compile(r'\$LAYER_NAME\n"([^"]+)"')
ATTRIB_RE = re.compile(r'ATTRIB\("([^"]+)"\s*,\s*(\w+)')


def _split_layers(txt: str):
    """<LAYER_START> 단위로 자르고 (레이어명, 블록) 을 낸다."""
    for block in txt.split("<LAYER_START>")[1:]:
        m = LAYER_NAME_RE.search(block)
        if m:
            yield m.group(1), block


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("cp949", "replace").replace("\r", "")


# ──────────────────────────────────────────────────────────────
# 기하 (.ngi)
# ──────────────────────────────────────────────────────────────
def _parse_geom_record(lines: list[str]):
    """레코드 한 건의 기하. 실패하면 None 을 낸다(자리는 지킨다)."""
    if len(lines) < 3:
        return None
    typ, i = lines[1].strip(), 2
    try:
        if typ == "POINT":
            return Point(*map(float, lines[i].split()[:2]))
        if typ == "LINESTRING":
            n = int(lines[i]); i += 1
            pts = [tuple(map(float, lines[i + k].split()[:2])) for k in range(n)]
            return LineString(pts) if len(pts) >= 2 else None
        if typ == "POLYGON":
            nparts = int(lines[i].split()[1]); i += 1
            rings = []
            for _ in range(nparts):
                n = int(lines[i]); i += 1
                pts = [tuple(map(float, lines[i + k].split()[:2])) for k in range(n)]
                i += n
                if len(pts) >= 3:
                    rings.append(pts)
            return Polygon(rings[0], rings[1:] or None) if rings else None
    except (ValueError, IndexError):
        return None
    return None


def parse_ngi(path: Path, want=None) -> dict[str, list]:
    """레이어명 → 기하 리스트. 실패 레코드는 None 으로 자리를 지킨다."""
    out: dict[str, list] = {}
    for lay, block in _split_layers(_read_text(path)):
        if want is not None and lay not in want:
            continue
        if "<DATA>" not in block:
            out.setdefault(lay, [])
            continue
        recs = block.split("<DATA>", 1)[1].split("$RECORD ")[1:]
        out[lay] = [_parse_geom_record(r.split("\n")) for r in recs]
    return out


# ──────────────────────────────────────────────────────────────
# 속성 (.nda)
# ──────────────────────────────────────────────────────────────
def parse_nda(path: Path, want=None) -> dict[str, dict]:
    """
    레이어명 → {"fields": [(이름, 형)], "rows": [dict, ...]}

    값 줄은 CSV 형식이다. 문자열에 쉼표가 들어갈 수 있으므로
    split(",") 대신 csv 모듈로 읽는다.
    """
    out: dict[str, dict] = {}
    for lay, block in _split_layers(_read_text(path)):
        if want is not None and lay not in want:
            continue
        fields = ATTRIB_RE.findall(block)
        names = [n for n, _ in fields]
        rows = []
        if "<DATA>" in block:
            for rec in block.split("<DATA>", 1)[1].split("$RECORD ")[1:]:
                ln = rec.split("\n")
                # 첫 줄은 레코드 번호, 다음 줄부터가 값이다.
                # 값이 여러 줄로 접히는 경우가 있어 <END> 전까지 이어붙인다.
                buf = []
                for s in ln[1:]:
                    t = s.strip()
                    if not t or t.startswith("<") or t.startswith("$"):
                        break
                    buf.append(t)
                if not buf:
                    rows.append(None)
                    continue
                try:
                    vals = next(csv.reader(io.StringIO(" ".join(buf)),
                                           skipinitialspace=True))
                except Exception:
                    rows.append(None)
                    continue
                # ★ 필드명 수와 값 수가 다르면 레코드가 조용히 잘린다.
                #   DBF 파싱이 어긋난 것이므로 죽는 편이 낫다.
                rows.append(dict(zip(names, vals, strict=True)))
        out[lay] = {"fields": fields, "rows": rows}
    return out


# ──────────────────────────────────────────────────────────────
def read_ngi(ngi_path: Path, want=None) -> dict[str, dict]:
    """
    기하 + 속성을 합쳐서 낸다.

        {"A0020000": {"fields": [("도로폭","NUMERIC"), ...],
                      "records": [{"geom": <LineString>, "도로폭": "6.0", ...}]}}

    .nda 가 없으면 속성 없이 기하만 낸다(경고 없이 조용히 넘기지 않는다).
    """
    ngi_path = Path(ngi_path)
    geom = parse_ngi(ngi_path, want)
    nda_path = ngi_path.with_suffix(".nda")
    attr = parse_nda(nda_path, want) if nda_path.exists() else {}

    out = {}
    for lay, geoms in geom.items():
        a = attr.get(lay, {})
        rows = a.get("rows", [])
        if rows and len(rows) != len(geoms):
            # 짝이 안 맞으면 속성을 붙이지 않는다. 밀린 채로 붙이면
            # 엉뚱한 도로에 엉뚱한 폭이 들어가고 아무도 눈치채지 못한다.
            print(f"  ! {ngi_path.name} {lay}: 기하 {len(geoms)} / 속성 {len(rows)} 불일치 — 속성 생략")
            rows = []
        recs = []
        for i, g in enumerate(geoms):
            if g is None:
                continue
            r = {"geom": g}
            if rows and i < len(rows) and rows[i]:
                r.update(rows[i])
            recs.append(r)
        out[lay] = {"fields": a.get("fields", []), "records": recs,
                    "n_geom": len(geoms),
                    "n_geom_failed": sum(1 for g in geoms if g is None),
                    "has_attr": bool(rows)}
    return out


def layer_index(ngi_path: Path) -> dict[str, dict]:
    """
    인벤토리용 요약. 기하를 전부 만들지 않고 헤더와 건수만 훑는다.
    도엽 3,102 파일을 매번 전부 파싱하면 인벤토리가 몇 분씩 걸린다.
    """
    out = {}
    txt = _read_text(Path(ngi_path))
    for lay, block in _split_layers(txt):
        n = block.count("$RECORD ") if "<DATA>" in block else 0
        typ = None
        if "<DATA>" in block:
            first = block.split("<DATA>", 1)[1].split("$RECORD ")[1:2]
            if first:
                ln = first[0].split("\n")
                typ = ln[1].strip() if len(ln) > 1 else None
        out[lay] = {"n": n, "geom_type": typ}

    nda = Path(ngi_path).with_suffix(".nda")
    if nda.exists():
        for lay, block in _split_layers(_read_text(nda)):
            if lay in out:
                out[lay]["fields"] = [n for n, _ in ATTRIB_RE.findall(block)]
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    for lay, info in sorted(layer_index(Path(sys.argv[1])).items()):
        f = info.get("fields", [])
        print(f"{lay}  {info['geom_type'] or '-':<11} {info['n']:>5}건  {', '.join(f)}")

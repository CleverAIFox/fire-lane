#!/usr/bin/env python3
"""
inventory.py — 원본에 실제로 무엇이 들어 있는지 훑어 대장에 박는다.

    python -m firelane.inventory            훑고 sources.yaml 갱신
    python -m firelane.inventory --dry      갱신 없이 출력만
    python -m firelane.inventory --only ngii1k

── 왜 만드나 ──────────────────────────────────────────────────
같은 EDA를 세 번 반복했다. "이 원본에 어떤 레이어가 있고 어떤 속성이 있나"를
그때그때 캐냈고, 그 결과가 어디에도 남지 않아 다음에 또 캤다.
그러다 A0020000 의 도로폭·일방통행, A0033320 의 보도폭을 통째로 버리고 있던 걸
뒤늦게 발견했다. 버린 줄도 몰랐던 이유는 무엇이 있는지 적힌 곳이 없어서다.

이 스크립트는 원본을 훑어 sources.yaml 하단의 AUTO 블록에 적는다.
사람이 쓰는 datasets: 섹션은 건드리지 않는다. 주석도 보존된다.

    sources.yaml
      datasets:        ← 사람이 쓴다. 의도·근거·주의사항
      # === AUTO ===   ← 이 스크립트가 쓴다. 사실만
      inventory:

── 핵심 출력: unused ─────────────────────────────────────────
원본에 있는데 src/ 어디서도 참조되지 않는 속성을 표시한다.
"쓸 수 있는데 안 쓰는 것"이 한눈에 보이는 게 이 도구의 존재 이유다.
"""
from __future__ import annotations

import csv
import glob as _glob
import io
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from firelane.paths import RAW, ROOT
from firelane import ngi

KST = timezone(timedelta(hours=9))
SOURCES = ROOT / "sources.yaml"
BEGIN = "# ===== AUTO: inventory — inventory.py 가 쓴다. 손으로 고치지 말 것 ====="
END = "# ===== /AUTO ====="

# NGI 도엽은 3,000개가 넘는다. 전수 파싱은 몇 분씩 걸리고 매번 같은 결과다.
# 도엽 스키마는 도엽마다 같으므로 표본만 훑는다.
NGI_SAMPLE = 3
CSV_ENCODINGS = ("utf-8-sig", "cp949", "utf-8")


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _resolve(pattern: str) -> list[Path]:
    """sources.yaml 의 file: 글롭을 실제 경로로. 디렉터리면 그대로 낸다."""
    p = RAW / pattern
    if pattern.endswith("/"):
        return [p] if p.is_dir() else []
    hits = [Path(x) for x in _glob.glob(str(p))]
    return sorted(hits)


def _code_text() -> str:
    """src/ 전체를 한 덩어리로. 속성 사용 여부 판정에 쓴다."""
    buf = []
    for f in (ROOT / "src").rglob("*.py"):
        buf.append(f.read_text(encoding="utf-8", errors="ignore"))
    for f in (ROOT / "web").glob("*.js"):
        buf.append(f.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(buf)


def _mark_unused(fields: list[str], code: str) -> list[str]:
    """코드 어디서도 문자열로 등장하지 않는 속성명."""
    return [f for f in fields if f and f not in ("ID",) and f'"{f}"' not in code
            and f"'{f}'" not in code]


# ──────────────────────────────────────────────────────────────
# kind 별 훑기
# ──────────────────────────────────────────────────────────────
def probe_ngi_dir(d: Path) -> dict:
    """수치지형도 도엽 묶음. 표본 도엽의 레이어 스키마를 낸다."""
    ngis = sorted(d.rglob("*.ngi"))
    shps = sorted(d.rglob("*.shp"))
    layers: dict[str, dict] = {}
    for f in ngis[:NGI_SAMPLE]:
        for lay, info in ngi.layer_index(f).items():
            cur = layers.setdefault(lay, {"geom_type": info["geom_type"],
                                          "fields": info.get("fields", []),
                                          "n_sample": 0, "sheets": 0})
            cur["n_sample"] += info["n"]
            cur["sheets"] += 1
            if not cur["fields"] and info.get("fields"):
                cur["fields"] = info["fields"]
    return {"file_count": {"ngi": len(ngis), "shp": len(shps)},
            "sampled_sheets": min(len(ngis), NGI_SAMPLE),
            "layers": layers}


def probe_shp_zip(paths: list[Path], layer: str | None = None) -> dict:
    import geopandas as gpd
    out = {"archives": [], "layers": {}}
    for z in paths:
        try:
            with zipfile.ZipFile(z) as zf:
                names = [n for n in zf.namelist() if n.lower().endswith(".shp")]
                # sources.yaml 의 layer: 가 정본이다. 없으면 전부 훑는다.
                # 이걸 안 보면 같은 zip 을 쓰는 5개 데이터셋이 전부 같은
                # 54개 속성을 보고해서 "무엇을 안 쓰는가"가 무의미해진다.
                if layer:
                    names = [n for n in names if n.endswith(layer)] or names
        except Exception as e:
            out["archives"].append({"file": z.name, "error": str(e)[:80]})
            continue
        out["archives"].append({"file": z.name, "shp": len(names)})
        for n in names:
            key = Path(n).stem
            if key in out["layers"]:
                continue
            try:
                g = gpd.read_file(f"zip://{z}!{n}", rows=50)
                out["layers"][key] = {
                    "geom_type": str(g.geom_type.iloc[0]) if len(g) else None,
                    "crs": str(g.crs) if g.crs else None,
                    "fields": [c for c in g.columns if c != "geometry"],
                }
            except Exception as e:
                out["layers"][key] = {"error": str(e)[:80]}
    return out


def probe_csv(paths: list[Path]) -> dict:
    out = {"files": []}
    for p in paths:
        rec = {"file": p.name, "bytes": p.stat().st_size}
        for enc in CSV_ENCODINGS:
            try:
                with p.open(encoding=enc) as f:
                    rd = csv.reader(f)
                    head = next(rd)
                    n = sum(1 for _ in rd)
                rec.update(encoding=enc, rows=n, fields=head)
                break
            except (UnicodeDecodeError, StopIteration):
                continue
        else:
            rec["error"] = "인코딩 판별 실패"
        out["files"].append(rec)
    return out


def probe_csv_in_zip(paths: list[Path]) -> dict:
    out = {"files": []}
    for z in paths:
        try:
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    if not n.lower().endswith((".csv", ".txt")):
                        continue
                    raw = zf.read(n)[:200000]
                    for enc in CSV_ENCODINGS:
                        try:
                            head = next(csv.reader(io.StringIO(raw.decode(enc))))
                            out["files"].append({"file": f"{z.name}!{n}",
                                                 "encoding": enc, "fields": head})
                            break
                        except (UnicodeDecodeError, StopIteration):
                            continue
        except Exception as e:
            out["files"].append({"file": z.name, "error": str(e)[:80]})
    return out


def probe_raw_only(paths: list[Path]) -> dict:
    out = {"files": []}
    for p in paths:
        rec = {"file": p.name, "bytes": p.stat().st_size}
        if p.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(p) as zf:
                    inner = zf.namelist()
                rec["entries"] = len(inner)
                rec["sample"] = inner[:8]
            except Exception as e:
                rec["error"] = str(e)[:80]
        out["files"].append(rec)
    return out


PROBES = {
    "ngii1k": lambda ps: probe_ngi_dir(ps[0]),
    "ngii_1k": lambda ps: probe_ngi_dir(ps[0]),
    "shp_zip": probe_shp_zip,
    "shp_zip_multi": probe_shp_zip,
    "dbf_in_zip": probe_shp_zip,
    "csv_points": probe_csv,
    "csv_point": probe_csv,
    "csv_table": probe_csv,
    "csv_points_in_zip": probe_csv_in_zip,
    "raw_only": probe_raw_only,
}


# ──────────────────────────────────────────────────────────────
def collect(only: str | None = None) -> dict:
    src = yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}
    ds = src.get("datasets", {}) or {}
    code = _code_text()
    inv: dict[str, dict] = {}

    for key, meta in ds.items():
        if only and key != only:
            continue
        kind = meta.get("kind", "")
        pattern = meta.get("file", "")
        if not pattern:
            inv[key] = {"status": "file 미지정"}
            continue
        paths = _resolve(pattern)
        if not paths:
            # ★ 조용히 넘기지 않는다. 대장에 있는데 원본이 없으면 사고다.
            inv[key] = {"status": "원본 없음", "pattern": pattern}
            print(f"  ! {key}: 원본 없음 ({pattern})")
            continue

        fn = PROBES.get(kind)
        if fn is None:
            inv[key] = {"status": f"kind 미지원: {kind}"}
            continue
        try:
            if kind in ("shp_zip", "shp_zip_multi", "dbf_in_zip"):
                got = fn(paths, meta.get("layer"))
            else:
                got = fn(paths)
        except Exception as e:
            inv[key] = {"status": f"오류: {type(e).__name__}: {str(e)[:80]}"}
            print(f"  ! {key}: {e}")
            continue

        # 코드에서 참조되지 않는 속성 표시
        allf: list[str] = []
        for lay in (got.get("layers") or {}).values():
            allf += lay.get("fields", []) or []
        for f in (got.get("files") or []):
            if isinstance(f, dict):
                allf += f.get("fields", []) or []
        unused = _mark_unused(sorted(set(allf)), code)

        got["kind"] = kind
        got["unused_fields"] = unused
        inv[key] = got
        n = len(got.get("layers") or got.get("files") or [])
        print(f"  {key:<20} {kind:<18} {n:>3}  미사용속성 {len(unused)}")

    return {"at": _now(), "raw": str(RAW), "datasets": inv}


def write_block(inv: dict) -> None:
    """sources.yaml 하단 AUTO 블록만 교체한다. 위쪽 주석은 그대로 둔다."""
    body = yaml.safe_dump({"inventory": inv}, allow_unicode=True,
                          sort_keys=False, width=100)
    txt = SOURCES.read_text(encoding="utf-8")
    block = f"{BEGIN}\n{body}{END}\n"
    if BEGIN in txt:
        pre = txt.split(BEGIN)[0]
        post = txt.split(END, 1)[1] if END in txt else "\n"
        txt = pre + block + post.lstrip("\n")
    else:
        txt = txt.rstrip() + "\n\n" + block
    SOURCES.write_text(txt, encoding="utf-8")
    print(f"\n→ {SOURCES} AUTO 블록 갱신")


if __name__ == "__main__":
    args = sys.argv[1:]
    only = args[args.index("--only") + 1] if "--only" in args else None
    inv = collect(only)

    tot = sum(len(v.get("unused_fields", [])) for v in inv["datasets"].values())
    print(f"\n미사용 속성 총 {tot}개 — 원본에 있는데 코드가 안 보는 것들이다")
    for k, v in inv["datasets"].items():
        if v.get("unused_fields"):
            print(f"  {k}: {', '.join(v['unused_fields'][:12])}")

    if "--dry" not in args:
        write_block(inv)

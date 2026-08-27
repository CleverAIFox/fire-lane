#!/usr/bin/env python3
"""
refcheck.py — **선언이 가리키는 모든 것이 실재하는가.**

    uv run python tools/refcheck.py            전수 검사
    uv run python tools/refcheck.py --gc       선언 밖 파일 목록(지우진 않는다)

FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다
  (읽기 전용이지만 raw 를 본다. 마커는 가드 통과용이 아니라 분류다)

── 왜 ─────────────────────────────────────────────────────────
이 저장소의 사고는 한 형태를 반복한다 — **A 가 B 를 가리키는데 B 가 없고,
아무도 그 사실을 모른다.** 이름만 다르지 전부 같은 문제다.

    2026-08-24  계층 선언에 interim 이 없어 도구가 SSD 루트에 떨궜다
    2026-08-25  대장이 `.hwpx|.pdf` 를 한 항목으로 봐 hits[0] 이 뒤집혔다
    2026-08-26  대장 consumers 가 `web/app.js` 를 가리켰다(실물은 js/data.js)
    2026-08-26  개명 뒤 대장 글롭 넷이 0건이 됐다. 조용했다
    PLAN #36    MASTER 가 추적되지 않는 nfa_compare.json 을 가리킨다

각각을 그때그때 잡았다. **하나로 묶어 매번 돌리는 것이 맞다.**
참조는 종류가 달라도 검사는 하나다 — 가리키는 쪽과 가리켜지는 쪽을
대조한다.

── 검사하는 참조 ──────────────────────────────────────────────
    ① 대장 file/files      → raw 실물        (글롭 0건 = 죽음)
    ② 대장 outputs.path    → processed
    ③ 대장 outputs.consumers → 저장소 파일
    ④ 대장 produced_by     → 저장소 파일
    ⑤ 대장 outputs.inputs  → datasets 키
    ⑥ retired.file         → raw 에 **없어야** 한다(되살아났나)
    ⑦ 문서의 경로 표기     → 저장소 파일
    ⑧ layers 선언          → 실제 디렉터리

★ ⑥ 이 역방향이다. 폐기한 것이 landing 에서 다시 올라온 전례가 있다
  (2026-08-23, acquire.py 머리말). "있어야 한다" 만 검사하면 못 잡는다.

IN    sources.yaml · docs/ · raw
OUT   없음 (검사 전용)
PARAM 없음
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "sources.yaml"
LEDGER = ROOT / "data" / "_acquire.json"

# 문서에서 경로처럼 보이는 것. 확장자가 있어야 경로로 친다.
DOC_PATH = re.compile(
    r"`((?:src|tools|tests|docs|web|data)/[\w./-]+\.\w{1,6})`")

FAIL, WARN = "✗", "!"


def _led() -> dict:
    if not LEDGER.exists():
        return {}
    return json.loads(LEDGER.read_text(encoding="utf-8"))["files"]


def check() -> list[tuple[str, str, str]]:
    d = yaml.safe_load(YAML.read_text(encoding="utf-8")) or {}
    ds = d.get("datasets") or {}
    led = _led()
    out: list[tuple[str, str, str]] = []

    # ① 대장 → raw
    for k, e in ds.items():
        for pat in (e.get("files") or ([e["file"]] if "file" in e else [])):
            pat = str(pat)
            hit = ([r for r in led if fnmatch.fnmatch(r, pat)]
                   if any(c in pat for c in "*?[") else
                   [r for r in led if r == pat])
            if not hit:
                out.append((FAIL, f"datasets.{k}.file",
                            f"{pat} — raw 대장에 0건"))

    # ⑤ outputs.inputs → datasets 키
    outs = d.get("outputs") or {}
    for k, o in outs.items():
        for inp in (o.get("inputs") or []):
            if inp not in ds and inp not in outs:
                out.append((FAIL, f"outputs.{k}.inputs", f"{inp} — 대장에 없다"))

        # ② path → 실물
        pth = o.get("path")
        if pth and not (ROOT / pth).exists():
            out.append((WARN, f"outputs.{k}.path",
                        f"{pth} — 없다(재생성 전일 수 있다)"))

        # ③④ consumers · produced_by → 저장소 파일
        for f in ([o.get("produced_by")] if o.get("produced_by") else []) \
                + list(o.get("consumers") or []):
            f = str(f).split("::")[0]
            if not (ROOT / f).exists():
                out.append((FAIL, f"outputs.{k}", f"{f} — 저장소에 없다"))

    # ⑥ retired 가 되살아났나 (역방향)
    for k, r in (d.get("retired") or {}).items():
        f = r.get("file")
        if f and any(x == f for x in led):
            out.append((FAIL, f"retired.{k}",
                        f"{f} — 폐기했는데 raw 에 다시 있다"))

    # ⑦ 문서의 경로 표기
    for doc in sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"]:
        if not doc.exists():
            continue
        for m in sorted(set(DOC_PATH.findall(doc.read_text(encoding="utf-8")))):
            if not (ROOT / m).exists():
                out.append((WARN, doc.name, f"{m} — 없다"))

    # ⑨ ★ 코드가 하드코딩한 raw 경로 — 대장을 안 거치는 것들
    #
    #   개명은 대장·sha대장·실물 셋을 맞추는데, **코드가 대장을 안 보고
    #   raw 경로를 직접 조립하면** 그 셋 밖에 있어 조용히 깨진다.
    #   2026-08-26 실증 — terrain.py 와 report.py 가 옛 이름을 하드코딩하고
    #   있었고, 개명 뒤 `[SKIP] 없음` 과 0건으로 넘어갔다. 예외가 안 난다.
    #
    #   `sources.yaml` 의 `fire_access.feeds` 는 그 사실을 이미 적고 있었다 —
    #   "★ report.py 가 raw CSV 를 직접 읽는다". 선언은 있고 검사가 없었다.
    HARD = re.compile(
        r'RAW\s*/\s*"([^"]+)"\s*/\s*"([^"]+)"|'
        r'RAW\s*/\s*"([\w-]+/[^"]+)"')
    for py in sorted((ROOT / "src").rglob("*.py")) + \
            sorted((ROOT / "tools").glob("*.py")):
        txt = py.read_text(encoding="utf-8", errors="ignore")
        for m in HARD.finditer(txt):
            rel = (f"{m.group(1)}/{m.group(2)}" if m.group(1)
                   else m.group(3))
            if rel.startswith("_") or "*" in rel:
                continue
            if not any(r == rel for r in led):
                out.append((FAIL, str(py.relative_to(ROOT)),
                            f"{rel} — raw 대장에 없다(하드코딩 경로)"))

    # ⑧ layers 선언 → 디렉터리
    try:
        from firelane import layers as L
        for n in L.names():
            pol = L.policy(n)
            if pol.get("required") and not L.path(n).is_dir():
                out.append((FAIL, f"layers.{n}",
                            f"{L.path(n)} — required 인데 없다"))
    except Exception as ex:                        # noqa: BLE001
        out.append((WARN, "layers", f"{type(ex).__name__}: {ex}"[:70]))

    return out


def gc() -> None:
    """선언 밖 파일. **지우지 않는다.** 판단은 사람이 한다."""
    from firelane.paths import RAW
    from firelane.paths import ROOT as R
    d = yaml.safe_load(YAML.read_text(encoding="utf-8")) or {}
    pats = []
    for e in (d.get("datasets") or {}).values():
        pats += [str(p) for p in
                 (e.get("files") or ([e["file"]] if "file" in e else []))]
    if RAW.is_dir():
        stray = [str(p.relative_to(RAW)) for p in sorted(RAW.rglob("*"))
                 if p.is_file()
                 and not any(fnmatch.fnmatch(str(p.relative_to(RAW)), q)
                             for q in pats)]
        print(f"── raw 에서 대장 밖 {len(stray)}건 ──")
        for s in stray[:20]:
            print(f"  {s}")
        if stray:
            print("  → acquire.py --quarantine 이 격리한다")
    junk = [p for p in R.rglob("*")
            if p.is_file() and (p.name.endswith((".bak_enc", ".orig", ".rej"))
                                or (p.name.startswith("apply")
                                and p.suffix == ".sh"))]
    print(f"\n── 저장소 작업 잔재 {len(junk)}건 ──")
    for p in junk[:20]:
        print(f"  {p.relative_to(R)}")
    if junk:
        print("  → 일회성이다. 판단이 끝났으면 지워라(README R8)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gc", action="store_true")
    if ap.parse_args().gc:
        gc()
        return 0
    rows = check()
    for lv, where, msg in rows:
        print(f"  {lv} [{where}] {msg}")
    nf = sum(1 for lv, _, _ in rows if lv == FAIL)
    print(f"\n죽은 참조 {nf} · 경고 {len(rows) - nf}")
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())

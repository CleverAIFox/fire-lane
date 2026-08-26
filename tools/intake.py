#!/usr/bin/env python3
"""
intake.py — 출발지 게이트. **윈도우 다운로드 폴더에서 시작한다.**

    uv run python tools/intake.py                 관측만 (아무것도 안 옮긴다)
    uv run python tools/intake.py --plan          정규명 제안 + 대장 매칭
    uv run python tools/intake.py --stage --yes   landing 으로 복사 + sha 기록

── 왜 만들었나 ────────────────────────────────────────────────
파이프라인의 머리가 `landing` 이었다. 그런데 `paths.LANDING` 은 외장 SSD 이고,
브라우저는 `C:\\Users\\...\\Downloads` 로 떨군다. **그 사이 한 칸이 선언
밖이었다.**

`landing` 은 "규칙 없음" 이지만 관측은 된다 — `acquire.py` 가 스캔하고 세
판정을 낸다. 다운로드 폴더는 규칙도 없고 관측도 안 된다. 그래서 2026-08-25 에
KFS PDF 두 판을 열어보고 `sources.yaml` 의 결론을 뒤집었는데, **그 PDF 가
raw 에 편입되지 않았고 아무 도구도 그 사실을 몰랐다.** 대장은 근거를
인용하고 근거 파일은 그물 밖에 있었다.

이 저장소가 반복해 배운 것과 같은 형태다 —
**선언 밖에 있으면 그물에 안 걸린다**(interim 신설 · golden/baseline 등재).

── 설계 ───────────────────────────────────────────────────────
    ① 다운로드 폴더는 **읽기 전용**으로 취급한다
       사용자의 폴더지 파이프라인의 것이 아니다. 복사만 하고 지우지 않는다.
       정리는 사람이 한다. 도구가 남의 다운로드 폴더를 비우면 안 된다.

    ② 원본 파일명을 **대장에 보존**한다
       `6. 소방차 도장 및 표기(KFS-1-0006-2024-00).pdf` 가 정규명이 되면
       제공기관에 문의할 때 대조가 안 된다(MASTER §18 R1). raw 에는
       정규명으로 두고 원본명은 `origin_name` 으로 남긴다.

    ③ 개명은 **제안까지만** 한다
       한글 원본명을 기계가 영문으로 옮기면 `소방펌프차` 가
       `sobangpeompeuca` 가 되고 대장의 `kfs_pumptruck` 과 무관한 이름이
       생긴다. `--plan` 이 후보를 내고 사람이 정한다.

    ④ 멱등하다
       sha256 으로 판정한다. 크기가 아니다 — `normalize_raw` 의 크기 비교가
       313MB 정사영상이 잘려도 통과시키던 것이 2026-08-23 의 교훈이다.

── 계층 ───────────────────────────────────────────────────────
    Downloads (읽기 전용)          ← 여기가 출발지다
        │  intake.py --stage       원본명 보존 · sha 기록
        ▼
    landing (SSD)                  규칙 없음
        │  acquire.py --stage      대장 매칭 · 세 판정
        ▼
    raw                            불변
        │  prep.py                 인코딩·개행 통일
        ▼
    norm                           값은 안 바꾼다

IN    $FIRE_LANE_INBOX (기본값 자동탐색) · sources.yaml
OUT   $FIRE_LANE_DATA/landing · data/_intake.json (커밋한다)
PARAM 없음
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from firelane import naming as nm
from firelane.paths import LANDING, ROOT

KST = timezone(timedelta(hours=9))
LEDGER = ROOT / "data" / "_intake.json"

# 브라우저가 실제로 떨구는 부산물. landing 으로 올리지 않는다.
JUNK = re.compile(r"\.(crdownload|part|tmp|partial)$|^~\$|^\.DS_Store$")


def inbox() -> Path:
    """출발지. 정적이다.

    ★ WSL 에서 윈도우 다운로드는 `/mnt/c/Users/<user>/Downloads` 다.
      사용자명이 기계마다 다르므로 자동탐색하되, **찾은 결과를 출력**한다.
      조용히 다른 폴더를 보는 것이 제일 나쁘다.
    """
    env = os.environ.get("FIRE_LANE_INBOX")
    if env:
        return Path(env).expanduser()
    # 이름으로 거르지 않는다. `Default User` 를 빼먹어 빈 폴더를 출발지로
    # 잡은 적이 있다(2026-08-26). 시스템 계정 이름은 기계·로케일마다 달라
    # 목록으로는 못 막는다. **파일이 실제로 있는 곳**을 고르고, 후보가
    # 여럿이면 말한다.
    cands = []
    for base in (Path("/mnt/c/Users"), Path("/c/Users")):
        if not base.is_dir():
            continue
        for u in sorted(base.iterdir()):
            d = u / "Downloads"
            try:
                n = sum(1 for x in d.iterdir() if x.is_file())
            except OSError:
                continue
            if n:
                cands.append((n, d))
    if not cands:
        return Path.home() / "Downloads"
    cands.sort(reverse=True)
    if len(cands) > 1:
        print("★ 다운로드 후보가 여럿이다. FIRE_LANE_INBOX 로 못박아라 —")
        for n, d in cands:
            print(f"    {n:5}개  {d}")
    return cands[0][1]


def sha256(p: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"files": {}, "at": None}


def ledger_shas() -> set[str]:
    return {v["sha256"] for v in load_ledger()["files"].values()}


def sources_index() -> dict[str, dict]:
    f = ROOT / "sources.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return d.get("datasets", {})


# ── 원본명 → 정규명 제안 ──────────────────────────────────────
DOC_NO = re.compile(r"(KFS-\d-\d{4}-\d{4}(?:-\d{2})?)", re.I)


def propose(src: Path, ds: dict) -> dict:
    """정규명 후보를 낸다. **채택하지 않는다.**"""
    stem, ext = nm.split_ext(src.name)
    out = {"origin_name": src.name, "ext": ext, "doc_no": None,
           "matched_key": None, "suggest": None, "why": []}

    m = DOC_NO.search(stem)
    if m:
        out["doc_no"] = m.group(1).upper()

    # 대장에 이미 있는 항목인가 — 문서번호가 제일 강한 단서다.
    if out["doc_no"]:
        for k, v in ds.items():
            blob = json.dumps(v, ensure_ascii=False)
            if out["doc_no"] in blob.upper():
                out["matched_key"] = k
                pat = v.get("file", "")
                base = pat.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if "*" not in base:
                    out["suggest"] = f"{v.get('file','').split('/')[0]}/{base}.{ext}"
                    out["why"].append(
                        f"문서번호 {out['doc_no']} 가 대장 {k} 에 있다")
                break

    if out["suggest"] is None:
        slug = nm.slugify(stem)
        out["why"].append(
            f"대장 매칭 실패. 후보 토큰 — {slug!r} (사람이 정한다)")
    return out


# ── 명령 ──────────────────────────────────────────────────────
def cmd_observe(inb: Path) -> int:
    """무엇이 있고 무엇이 이미 편입됐나. **아무것도 안 옮긴다.**"""
    print(f"출발지  {inb}")
    if not inb.is_dir():
        print("  ★ 없다. FIRE_LANE_INBOX 로 지정하라.")
        return 1
    known = ledger_shas()
    files = [p for p in sorted(inb.iterdir())
             if p.is_file() and not JUNK.search(p.name)]
    if not files:
        print("  비어 있다.")
        return 0
    new = stale = 0
    print(f"\n{'상태':6} {'MB':>8}  파일")
    for p in files:
        s = sha256(p)
        seen = s in known
        new += not seen
        stale += seen
        print(f"{'편입됨' if seen else '★ 신규':6} "
              f"{p.stat().st_size/1e6:8.1f}  {p.name}")
    print(f"\n신규 {new} · 이미 편입 {stale}")
    if new:
        print("  → `--plan` 으로 정규명 후보를 본다")
    return 0


def cmd_plan(inb: Path) -> int:
    ds = sources_index()
    known = ledger_shas()
    n = 0
    for p in sorted(inb.iterdir()):
        if not p.is_file() or JUNK.search(p.name):
            continue
        if sha256(p) in known:
            continue
        n += 1
        pr = propose(p, ds)
        print(f"\n── {p.name}")
        if pr["doc_no"]:
            print(f"   문서번호   {pr['doc_no']}")
        print(f"   대장 매칭   {pr['matched_key'] or '★ 없음 — 신규 항목이다'}")
        print(f"   제안 경로   {pr['suggest'] or '★ 사람이 정한다'}")
        for w in pr["why"]:
            print(f"   근거       {w}")
        if pr["matched_key"] is None:
            print("   ★ 대장에 없는 문서다. 편입 전에 datasets 또는 retired 에\n"
                  "     항목을 만든다. 안 열어보고 두면 3개월 뒤 또 받는다(§18-3c).")
    if not n:
        print("신규 없음.")
    return 0


def cmd_stage(inb: Path, *, apply: bool) -> int:
    """다운로드 → landing. **원본은 지우지 않는다.**"""
    L = load_ledger()
    known = {v["sha256"] for v in L["files"].values()}
    LANDING.mkdir(parents=True, exist_ok=True)
    moved = skipped = 0
    for p in sorted(inb.iterdir()):
        if not p.is_file() or JUNK.search(p.name):
            continue
        s = sha256(p)
        if s in known:
            skipped += 1
            continue
        dst = LANDING / p.name          # ★ landing 은 원본명 그대로다
        if dst.exists() and sha256(dst) == s:
            skipped += 1
            continue
        print(f"{'복사' if apply else '복사예정'}  {p.name}  → {dst}")
        if apply:
            shutil.copyfile(p, dst)
            if sha256(dst) != s:
                print("  ★ 복사 후 sha 불일치. 중단한다.")
                return 1
            L["files"][p.name] = {
                "sha256": s, "bytes": p.stat().st_size,
                "origin_name": p.name,
                "seen_at": datetime.now(KST).isoformat(timespec="seconds"),
                "from": str(inb),
            }
        moved += 1
    if apply:
        L["at"] = datetime.now(KST).isoformat(timespec="seconds")
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(
            json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'편입' if apply else '편입 예정'} {moved} · 건너뜀 {skipped}")
    if not apply and moved:
        print("  실제로 옮기려면 --yes")
    print("\n★ 다운로드 폴더의 원본은 지우지 않았다. 정리는 사람이 한다.")
    if apply and moved:
        print("★ 다음 — uv run python tools/acquire.py   (landing → raw 판정)")
    return 0


def cmd_audit() -> int:
    """raw 실물 이름과 대장 패턴을 문법으로 심사한다."""
    ds = sources_index()
    bad = 0
    print("═══ 대장 file 패턴 ═══")
    for k, v in ds.items():
        for msg in nm.audit_pattern(v.get("file", "")):
            bad += 1
            print(f"  [{k}] {msg}")
    acq = ROOT / "data" / "_acquire.json"
    if acq.exists():
        print("\n═══ raw 파일명 문법 ═══")
        f = json.loads(acq.read_text(encoding="utf-8"))["files"]
        for rel in sorted(f):
            folder, _, fn = rel.partition("/")
            ok, msgs = nm.check(fn, folder=folder)
            for m in msgs:
                bad += 1
                print(f"  {rel}\n      {m.splitlines()[0]}")
    print(f"\n지적 {bad}건")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="정규명 후보 + 대장 매칭")
    ap.add_argument("--stage", action="store_true", help="다운로드 → landing")
    ap.add_argument("--audit", action="store_true", help="raw·대장 문법 심사")
    ap.add_argument("--yes", action="store_true", help="실제로 복사한다")
    a = ap.parse_args()
    if a.audit:
        return cmd_audit()
    inb = inbox()
    if a.plan:
        return cmd_plan(inb)
    if a.stage:
        return cmd_stage(inb, apply=a.yes)
    return cmd_observe(inb)


if __name__ == "__main__":
    sys.exit(main())

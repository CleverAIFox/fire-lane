#!/usr/bin/env python3
"""
b2_sweep.py — **스캔 → 검증 → 정리.** 근거 있는 것만 지운다.

    uv run python tools/b2_sweep.py               스캔·판정만 (아무것도 안 지운다)
    uv run python tools/b2_sweep.py --sweep       지울 것을 보여준다
    uv run python tools/b2_sweep.py --sweep --yes 실제로 지운다

환경변수는 **이미 쓰던 것**을 그대로 쓴다. 새로 만들지 않는다.

    FIRE_LANE_DATA    레이크 (raw · norm · landing · _quarantine · interim)
    FIRE_LANE_INBOX   윈도우 다운로드 폴더

★ 왜 필요한가. `intake` 가 자기 출력에 이렇게 적는다 —

      ★ 다운로드 폴더의 원본은 지우지 않았다. **정리는 사람이 한다.**

  그게 결함이다. 파이프라인이 반입까지만 하고 뒷정리를 떠넘기니 원본이
  쌓이고, 다음 도구가 그걸 또 옮기려 하고, 그러다 죽는다(cross-device).
  **삭제도 파이프라인의 일이다.** 단 근거 없이는 안 지운다.

판정 넷. 근거가 대장에 있는 것만 지운다.

    반입 완료   sha 가 레이크에 있다        → 지운다
    판단 완료   retired 대장에 있다          → 지운다
    보류        landing_disposition held     → 남긴다
    미판단      어디에도 없다                → 남긴다. 먼저 대장에 적어라

레이크 안도 같은 원리로 본다 —

    landing     raw 에 sha 가 있으면 반입 끝났다 → 지운다
    interim     재생성 가능(layers 선언) → 오래된 것 보고만 한다
    _quarantine lakecheck L2 소관이라 여기서 안 건드린다
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
JUNK = {".tmp", ".crdownload", ".part", ".partial"}

# ★ 데이터 확장자만 판정한다. 다운로드 폴더에는 스크립트·설정 파일도
#   섞이는데 그것까지 "미판단" 으로 내면 목록이 시끄러워지고, 시끄러우면
#   사람이 검사를 끈다. lakecheck L3 와 같은 어휘를 쓴다.
DATA_EXT = {".zip", ".7z", ".csv", ".json", ".shp", ".gpkg", ".tif",
            ".hwp", ".hwpx", ".xls", ".xlsx", ".txt", ".dbf", ".pdf", ".xml"}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def led() -> dict:
    return yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8")) or {}


def retired_names(y: dict) -> dict[str, str]:
    """폐기 대장이 지목하는 이름 → 항목 키.

    ★ `origin_name`(취득처가 준 이름) · `stem`(우리가 정한 이름) ·
      `file`/`files`(경로) 셋 다 본다. 하나만 보면 못 잡는 것이 생긴다 —
      2026-09-10 에 `intake` 가 정확히 그래서 retired 를 통째로 놓쳤다.
    """
    out: dict[str, str] = {}
    for k, v in (y.get("retired") or {}).items():
        if not isinstance(v, dict):
            continue
        if v.get("origin_name"):
            out[str(v["origin_name"])] = k
        for f in ([v["file"]] if v.get("file") else []) + (v.get("files") or []):
            out[Path(str(f)).name] = k
        if v.get("stem"):
            out[f"stem::{v['stem']}"] = k
    return out


def held_names(y: dict) -> dict[str, str]:
    """`landing_disposition` 에 적힌 처분. **보류도 처분이다.**"""
    out: dict[str, str] = {}
    for it in ((y.get("landing_disposition") or {}).get("items") or []):
        if isinstance(it, dict) and it.get("file"):
            out[str(it["file"])] = str(it.get("action", "?"))
    return out


def judge(p: Path, lake_sha: dict[str, Path], ret: dict[str, str],
          held: dict[str, str]) -> tuple[str, str, bool]:
    """(판정, 근거, 지워도 되나)"""
    if p.suffix.lower() in JUNK:
        return "찌꺼기", "다운로드 중단 파일", True
    h = sha(p)
    if h in lake_sha:
        return "반입 완료", f"sha 일치 — {lake_sha[h]}", True
    if p.name in ret:
        return "판단 완료", f"retired.{ret[p.name]}", True
    stem = p.stem
    for key, k in ret.items():
        if key.startswith("stem::") and stem.startswith(key[6:]):
            return "판단 완료", f"retired.{k} (stem)", True
    if p.name in held:
        a = held[p.name]
        return ("보류", f"landing_disposition action={a}", False) if a == "held" \
            else (f"처분 {a}", f"landing_disposition action={a}", a == "retired")
    return "미판단", "대장 어디에도 없다 — 먼저 적어라", False


def scan(label: str, d: Path, lake_sha: dict[str, Path], ret, held,
         *, min_mb: float = 0.0) -> list[tuple[Path, str, str]]:
    print(f"\n══ {label}  {d}")
    if not d.is_dir():
        print("   ✗ 폴더가 없다 — 스캔 못 한다")
        return []
    files = [p for p in sorted(d.iterdir())
             if p.is_file() and p.stat().st_size >= min_mb * 1e6
             and (p.suffix.lower() in DATA_EXT
                  or p.suffix.lower() in JUNK)]
    if not files:
        print("   비어 있다")
        return []
    dele: list[tuple[Path, str, str]] = []
    tally: dict[str, int] = defaultdict(int)
    for p in files:
        verdict, why, can = judge(p, lake_sha, ret, held)
        tally[verdict] += 1
        mark = "🗑" if can else "  "
        print(f"   {mark} [{verdict:9s}] {p.name[:44]:46s} {p.stat().st_size / 1e6:7.1f}MB")
        print(f"        {why}")
        if can:
            dele.append((p, verdict, why))
    print(f"   ── {len(files)}건 · " + " · ".join(f"{k} {v}" for k, v in tally.items()))
    return dele


MASTER_OLD = """```bash
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"      # 리눅스
setx FIRE_LANE_DATA "<raw 상위 폴더 경로>"        # 윈도우
```

미설정 시 `<repo>/data/raw` 를 쓴다. 단일 머신이면 그걸로 충분하다."""

MASTER_NEW = """```bash
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"          # 리눅스
export FIRE_LANE_INBOX="/mnt/c/Users/<사용자명>/Downloads"
setx FIRE_LANE_DATA "<raw 상위 폴더 경로>"            # 윈도우
```

미설정 시 `<repo>/data/raw` 를 쓴다. 단일 머신이면 그걸로 충분하다.

★ **`FIRE_LANE_INBOX` 는 파이프라인의 머리다.** `tools/intake.py` 가
브라우저 다운로드 폴더를 관측하는 자리이고, `tools/lakecheck.py` L3 와
`tools/b2_sweep.py` 가 기본 스캔 대상으로 쓴다. 없으면 **레이크 밖을
아무도 안 본다** — 2026-08-25 에 KFS PDF 두 판을 열어보고 대장 결론을
뒤집었는데 그 PDF 가 raw 에 편입되지 않았고 아무 도구도 그 사실을 몰랐다.

★ 2026-09-10 정정. 이 줄이 **`web/playbook.html` 에는 있는데 여기 없었다.**
그 HTML 은 `render_workflow.py` 가 이 문서에서 생성하는 것이라 정본에
없는 내용이 생성물에만 있던 셈이다. 협업자가 보는 문서와 대장이 갈렸다."""


def fix_docs(apply: bool) -> int:
    """★ 환경변수 선언이 생성물에만 있고 정본에 없었다."""
    print("\n══ ④ 문서 정합 — FIRE_LANE_INBOX")
    n = 0
    m = ROOT / "docs" / "MASTER.md"
    s = m.read_text(encoding="utf-8")
    if "FIRE_LANE_INBOX" in s:
        print("   = MASTER.md 이미 있다")
    elif s.count(MASTER_OLD) != 1:
        print("   ✗ MASTER.md 앵커를 못 찾았다")
        return 1
    else:
        print(f"   {'→' if apply else '·'} MASTER.md 환경변수 절에 INBOX")
        if apply:
            m.write_text(s.replace(MASTER_OLD, MASTER_NEW), encoding="utf-8")
        n += 1
    e = ROOT / ".env.example"
    if e.exists():
        t = e.read_text(encoding="utf-8")
        if "FIRE_LANE_INBOX" in t:
            print("   = .env.example 이미 있다")
        else:
            print(f"   {'→' if apply else '·'} .env.example 에 INBOX")
            if apply:
                e.write_text(t.replace(
                    "FIRE_LANE_DATA=",
                    "FIRE_LANE_DATA=\n"
                    "# 브라우저 다운로드 폴더. intake·lakecheck·b2_sweep 이 관측한다\n"
                    "FIRE_LANE_INBOX=", 1), encoding="utf-8")
            n += 1
    if n and apply:
        print("   ★ web/playbook.html 은 render_workflow.py 가 다시 만든다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep", action="store_true", help="지울 것을 판정한다")
    ap.add_argument("--yes", action="store_true", help="실제로 지운다")
    a = ap.parse_args()

    D = os.environ.get("FIRE_LANE_DATA")
    IN = os.environ.get("FIRE_LANE_INBOX")
    if not D or not Path(D).is_dir():
        print("✗ FIRE_LANE_DATA 가 없거나 폴더가 아니다")
        print("  ★ 0건이 아니라 실패다 — 스캔을 못 했는데 깨끗하다고 하면 안 된다")
        return 1
    if not IN or not Path(IN).is_dir():
        print("✗ FIRE_LANE_INBOX 가 없거나 폴더가 아니다")
        print("  ★ 다운로드 폴더를 못 보면 '레이크 밖' 을 아무도 안 본다")
        return 1
    D, IN = Path(D), Path(IN)
    y = led()
    ret, held = retired_names(y), held_names(y)

    # 레이크 지문 — raw·norm 이 정본이다
    print("레이크 지문화 중…", end="", flush=True)
    lake: dict[str, Path] = {}
    for zone in ("raw", "norm"):
        for p in (D / zone).rglob("*"):
            if p.is_file():
                lake.setdefault(sha(p), p.relative_to(D))
    print(f" {len(lake)}건")

    dele = scan("① 다운로드 폴더", IN, lake, ret, held, min_mb=0.0)

    # landing — raw 에 들어갔으면 여기 남을 이유가 없다
    land = scan("② landing (레이크 입구)", D / "landing", lake, ret, held)

    print("\n══ ③ 레이크 나머지")
    for zone, note in (("_quarantine", "lakecheck L2 소관 — 여기서 안 건드린다"),
                       ("interim", "재생성 가능(layers 선언) — 보고만 한다"),
                       ("norm", "raw 의 파생 — lakecheck L5 소관")):
        z = D / zone
        n = sum(1 for p in z.rglob("*") if p.is_file()) if z.is_dir() else 0
        sz = sum(p.stat().st_size for p in z.rglob("*") if p.is_file()) if z.is_dir() else 0
        print(f"   {zone:12s} {n:3d}건 {sz / 1e6:8.1f}MB   {note}")

    fix_docs(a.yes)

    todo = dele + land
    total = sum(p.stat().st_size for p, _, _ in todo)
    print(f"\n══ 정리 대상 {len(todo)}건 · {total / 1e6:.0f}MB")
    if not todo:
        print("   없다")
        return 0
    if not a.sweep:
        print("   `--sweep` 으로 지울 목록을 확정한다")
        return 0
    if not a.yes:
        for p, v, _w in todo:
            print(f"   지울 것  {p.name[:50]:52s} [{v}]")
        print("\n   실제로 지우려면 --sweep --yes")
        return 0
    n = 0
    for p, v, w in todo:
        p.unlink()
        print(f"   지움  {p.name[:50]:52s} [{v}] {w}")
        n += 1
    print(f"\n   {n}건 삭제 · {total / 1e6:.0f}MB 확보")
    print("   ★ 근거가 대장에 있는 것만 지웠다. 보류·미판단은 남아 있다")
    return 0


if __name__ == "__main__":
    sys.exit(main())

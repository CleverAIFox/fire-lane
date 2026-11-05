#!/usr/bin/env python3
"""
fix_vintage_8digit.py — landing 의 연도 vintage(YYYY)를 8자리(YYYY1231)로 맞춘다.

    uv run python fix_vintage_8digit.py            계획만
    uv run python fix_vintage_8digit.py --apply    실행

── 왜 ─────────────────────────────────────────────────────────
`naming.py` 는 vintage 를 YYYYMMDD|YYYYMM|YYYY 로 받는데
`normalize_raw.py` 의 provider 규칙은 `\\d{8}` 만 받는다.

    (rf"^{o}_[a-z0-9_-]+_\\d{{8}}(?:_[a-z0-9-]+)?\\.({ext})$", o, None)

그래서 `nfa_ems_kr_2019.csv` 가 규칙에 안 걸려 --stage 가 0건을 복사했다.
그 함수 머리말이 같은 일을 세 번 적어 뒀다(하이픈 · json · _part) —
"대장이 정본인데 코드가 더 좁았다". 이것이 네 번째다.

**그래도 정규식을 안 고친다.** 8자리 전제가 거기 하나가 아니다 —
`ledger_fields.py:25` 가 "정규명의 8자리가 대장 updated 의 정본이다"로 유도한다.
정규식만 넓히면 그 유도가 조용히 깨진다.

연도 단위 자료를 `YYYY1231` 로 적는 관례는 이미 있다 —
`nfa_bldgcomm_guide_kr_20231231.pdf` · `safety_hydrant_type_jngj_20251231.csv`.
파일명을 그 꼴로 맞추는 쪽이 건드릴 곳이 적다.

── 하는 일 ────────────────────────────────────────────────────
  ① landing 의 `<stem>_<scope>_<YYYY>.<ext>` 를 `..._<YYYY>1231.<ext>` 로 rename
  ② sources.yaml 의 `files:` 줄에서 같은 치환

멱등하다. 이미 8자리면 건너뛴다. 대상이 0건이면 아무것도 안 한다.

IN    $FIRE_LANE_DATA/landing · sources.yaml
OUT   같은 둘 (--apply 일 때만)
PARAM 없음
부류  생산   파일명과 대장을 고친다 (DECISIONS §398 의 「산출물·대장·그림」 중 대장)
밖    이름이 **규칙에 맞는지**는 안 본다 — `naming.parse` · `naming.check` 가 묻는다.
      raw 는 안 건드린다. landing 과 대장 `files:` 줄만 본다.
      vintage 가 **옳은 날짜인지**도 안 본다 — YYYY 를 YYYY1231 로 늘릴 뿐이고,
      그 1231 이 데이터 기준일로 맞는지는 사람이 판단한다.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "sources.yaml"
DATA = os.environ.get("FIRE_LANE_DATA")
LANDING = (Path(DATA) / "landing") if DATA else (ROOT / "data" / "landing")

# <provider>_<dataset>_<scope>_<YYYY>.<ext>   — YYYY 가 딱 4자리인 것만
PAT = re.compile(r"^([a-z][a-z0-9]*_[a-z0-9_]+_[a-z0-9-]+)_(\d{4})(\.[a-z0-9.]+)$")


def plan() -> list[tuple[Path, Path, str, str]]:
    out = []
    if not LANDING.is_dir():
        return out
    for p in sorted(LANDING.rglob("*")):
        if not p.is_file():
            continue
        m = PAT.match(p.name)
        if not m:
            continue
        head, yyyy, ext = m.groups()
        if not ("1900" <= yyyy <= "2100"):
            continue
        new = f"{head}_{yyyy}1231{ext}"
        out.append((p, p.with_name(new), p.name, new))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    print(f"landing  {LANDING}")
    if not LANDING.is_dir():
        print("✗ landing 이 없다", file=sys.stderr)
        return 2

    jobs = plan()
    if not jobs:
        print("대상 0건 — 이미 전부 8자리다 (멱등)")
        return 0

    print(f"\n── 파일 {len(jobs)}건")
    for _, dst, old, new in jobs:
        mark = " ★이미있음" if dst.exists() else ""
        print(f"   {old}  →  {new}{mark}")

    clash = [d for _, d, _, _ in jobs if d.exists()]
    if clash:
        print(f"\n✗ 대상 이름이 이미 {len(clash)}건 있다 — 덮어쓰지 않는다", file=sys.stderr)
        return 1

    text = LEDGER.read_text(encoding="utf-8") if LEDGER.is_file() else ""
    hits = [(o, n) for _, _, o, n in jobs if o in text]
    print(f"\n── 대장 files: 줄 {len(hits)}건")
    for o, n in hits:
        print(f"   {o}  →  {n}")

    if not a.apply:
        print("\n계획만 했다. 쓰려면 --apply")
        return 0

    for src, dst, _, _ in jobs:
        src.rename(dst)
    print(f"\n✓ 파일 {len(jobs)}건 rename")

    if hits:
        for o, n in hits:
            text = text.replace(o, n)
        LEDGER.write_text(text, encoding="utf-8")
        print(f"✓ 대장 {len(hits)}건 치환")

    print()
    print("다음 —")
    print("    uv run python tools/acquire.py --stage")
    print("    uv run python tools/acquire.py --verify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

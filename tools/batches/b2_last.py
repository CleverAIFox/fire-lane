#!/usr/bin/env python3
"""
b2_last.py — B2 **잔여 5건.** 내가 남긴 것만 닫는다.

    uv run python tools/b2_last.py            무엇을 할지만
    uv run python tools/b2_last.py --apply    실제로

★ `verify.sh` 실패 8 → 6 으로 줄었고, 남은 여섯 중 **넷이 내 탓**이다.

    내 탓   pytest 3건 · 트리 전수 대조 1건
    기존    문서↔문서 기한 3건(F-090) · 그림↔정본(F-128)
    미상    파이프라인 juso 3종 — ★ 이 스크립트가 안 건드린다

★ 파이프라인 3종은 **여기서 안 고친다.** `kind` 를 `shp_zip_multi` 로 바꿨는데도
  여전히 FAIL 이다. 그 종류는 ingest 주석에 "도엽 여러 zip 을 병합한다" 로
  적혀 있는데 승인분은 **zip 하나에 SHP 여럿**이라 성격이 다르다.
  실제 오류를 안 보고 또 추정하면 그것이 다음 결함이 된다.

      uv run python -m firelane.ingest --retry-failed 2>&1 | tail -40

  그 출력을 보고 고친다.

닫는 것 다섯 —

  ㊳ §122 의 §125~§127 참조   문서명을 붙인다. bare §N 은 MASTER 소관이다
  ㊴ §122 에 `> 날짜`          절 본문 첫 줄 규약(PLAN §0-0)
  ㊵ b2_settle.py → batches/  일회성이다. b2_wrap 이 돌 때는 없었다
  ㊶ 문서 숫자 4건             docnum 이 짚은 줄만 정밀 치환
  ㊷ 재계산 문서 보관          받은 md 를 레이크에 둘지 결정한다 (안내만)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(p: Path, old: str, new: str, why: str, apply: bool) -> int:
    if not p.exists():
        print(f"  ✗ {p} 없음")
        return 1
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n == 0:
        print(f"  = {why} (이미 적용)")
        return 0
    if n > 1:
        print(f"  ✗ {why} — {n}건이다. 모호하면 안 바꾼다")
        return 1
    print(f"  {'→' if apply else '·'} {why}")
    if apply:
        p.write_text(s.replace(old, new, 1), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    A = a.apply
    print(f"{'적용' if A else 'dry-run — --apply 로 실행'}\n")
    f = 0
    D = ROOT / "docs" / "DECISIONS.md"

    print("── ㊳ §122 의 §125~§127 — 문서명을 붙인다")
    # ★ 문서명 없는 `§N` 은 MASTER 를 가리킨다(MASTER §0-2). §125·§127 은
    #   **팀 쪽 문서의 절 번호**이고 이 저장소에는 없다. 그대로 두면
    #   test_master_and_decisions_bare_refs_resolve 가 영구히 운다.
    f += edit(D,
              "코드를 받게 되면 그때 §125~§127 로\n들어온 판단을 여기 흡수한다.",
              "코드를 받게 되면 그때 팀 문서의 §125~§127(범위·건물 확대 ·\n"
              "오매칭 진단 · 중심선 보정)로 들어온 판단을 여기 흡수한다.\n"
              "★ 그 번호는 **팀 쪽 문서의 절**이고 이 저장소에는 없다.",
              "§122 — 팀 문서 절임을 명시", A)

    print("\n── ㊴ §122 에 `> 날짜`")
    f += edit(D,
              "## 122. 팀 GIS 재계산(2026-09-09)은 이 저장소에 반영하지 않는다\n\n"
              "  결정  오창준 · 2026-09-10\n",
              "## 122. 팀 GIS 재계산(2026-09-09)은 이 저장소에 반영하지 않는다\n\n"
              "> 2026-09-10 · 오창준\n",
              "§122 — 절 본문 첫 줄에 `> 날짜` (PLAN §0-0)", A)

    print("\n── ㊵ b2_settle.py → tools/batches/")
    # ★ b2_wrap 이 돌 때 이 파일은 아직 없었다. 판별식은 같다 —
    #   "내년에도 돌릴 일이 있나" 에 아니오면 batches/ 다.
    src = ROOT / "tools" / "b2_settle.py"
    dst = ROOT / "tools" / "batches" / "b2_settle.py"
    if dst.exists():
        print("  = 이미 옮겨졌다")
    elif not src.exists():
        print("  = tools/b2_settle.py 없다")
    else:
        print(f"  {'→' if A else '·'} b2_settle.py  →  tools/batches/")
        if A:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

    print("\n── ㊶ 문서 숫자 — docnum 이 짚은 줄만")
    # ★ 일괄 치환을 안 한다. `61` · `10` 은 다른 맥락에도 있다
    #   (MASTER:2997 `차종 10종 15대`). 문맥까지 포함해 정확히 짚는다.
    f += edit(ROOT / "README.md",
              "대장        `datasets` 61종 · `retired` 10종",
              "대장        `datasets` 65종 · `retired` 16종",
              "README:401 — datasets 65 · retired 16", A)
    f += edit(ROOT / "docs" / "MASTER.md",
              "대장은 `sources.yaml` 하나다. `datasets` 61종 · `retired` 10종.",
              "대장은 `sources.yaml` 하나다. `datasets` 65종 · `retired` 16종.",
              "MASTER:632 — datasets 65 · retired 16", A)
    f += edit(ROOT / "docs" / "MASTER.md",
              "data/processed/    대장 61종",
              "data/processed/    대장 65종",
              "MASTER:546 — 대장 65종", A)
    f += edit(ROOT / "docs" / "MASTER.md",
              "현재 `retired` 10종이 있다.",
              "현재 `retired` 16종이 있다.",
              "MASTER:2392 — retired 16종", A)

    print("\n── ㊷ 받은 재계산 문서를 어디에 둘 것인가")
    print("  ★ 이 스크립트가 안 정한다. 선택지 둘 —")
    print("     ① 안 둔다        §122 가 요지를 담았다. 원문은 팀 쪽에 있다")
    print("     ② landing 에 둔다  landing_disposition 에 held 로 적는다")
    print("     `test_no_fifth_doc` 이 저장소 안 md 를 넷으로 제한하므로")
    print("     docs/ 에는 못 둔다. 그것이 규약이다")

    print(f"\n{'실패 ' + str(f) + '건' if f else '전부 통과'}")
    if A and not f:
        print("\n남은 것 —")
        print("  ★ 파이프라인 juso 3종   실제 오류를 보고 고친다")
        print("     uv run python -m firelane.ingest --retry-failed 2>&1 | tail -40")
        print("  · 기한 초과 3건        F-090. PLAN 의 DEFERRED 를 사람이 정한다")
        print("  · 그림 ↔ 정본          F-128. render_figures 후 기획서에 사람이 넣는다")
        print("\n검증 —")
        print("  uv run pytest tests/ -q")
        print("  bash tools/verify.sh")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())

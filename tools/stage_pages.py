#!/usr/bin/env python3
"""
stage_pages.py — 배포 직전에 web/ 을 완성한다.

    uv run python tools/stage_pages.py
    uv run python tools/stage_pages.py --check   빠졌으면 종료코드 1

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-02. `web/proposal.html` 이 `./proposal.docx` 를 부르는데 그 파일은
`docs/` 에 있다. **로컬에서도 배포에서도 404 였다** — Pages 는 `web/` 만
올린다.

정본은 `docs/proposal.docx` 다. 사본을 커밋하지 않고 배포 직전에 옮긴다 —
`workflow.html` 이 `MASTER §12` 에서 생성되는 것과 같은 관계다(R2).

★ 준비를 워크플로마다 인라인으로 쓰지 않는다. 지금 셋이 같은 `web/` 을
  올리는데(`pages` · `협업 방침` · `기획서`) 준비가 세 벌이면 하나만
  고치는 날이 온다. 이 파일이 그 한 벌이다.

IN    docs/proposal.docx
OUT   web/proposal.docx  (생성물. .gitignore)
PARAM --check
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (정본, 배포 위치). 늘어나면 여기 한 줄이다.
STAGED = [("docs/proposal.docx", "web/proposal.docx")]


def main() -> int:
    check = "--check" in sys.argv
    bad = 0
    for src_rel, dst_rel in STAGED:
        src, dst = ROOT / src_rel, ROOT / dst_rel
        if not src.exists():
            print(f"★ 정본이 없다 — {src_rel}")
            bad += 1
            continue
        same = dst.exists() and dst.stat().st_size == src.stat().st_size
        if check:
            if not same:
                print(f"! {dst_rel} 이 {src_rel} 과 다르다 — stage_pages 를 돌려라")
                bad += 1
            continue
        if same:
            print(f"  {dst_rel}  이미 최신")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  {src_rel} → {dst_rel}  ({dst.stat().st_size // 1024}KB)")
    if not bad:
        print("배포 준비 OK" if check else "배포 준비 완료")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

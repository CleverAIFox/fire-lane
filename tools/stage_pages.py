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

import os
import shutil
import sys
from pathlib import Path

from firelane import paths  # noqa: F401  ★ import 만으로 .env 를 환경에 얹는다

ROOT = Path(__file__).resolve().parents[1]

# (정본, 배포 위치). 늘어나면 여기 한 줄이다.
STAGED = [("docs/proposal.docx", "web/proposal.docx")]


def _write_key_js() -> None:
    """`web/key.js` 를 환경에서 만든다. **생성물이고 커밋하지 않는다.**

    ★ 2026-09-12 (B5). 종전에는 `web/config.js` 에 키가 평문으로 커밋돼
      있었다. 공개 저장소라 이력에 그대로 남는다 — 지금 지워도 옛 커밋에
      남으므로 **재발급이 유일한 복구다.** 이 함수는 앞으로를 막는다.

    ★ 로컬은 `.env`(paths._load_dotenv 가 환경에 얹는다), CI 는
      GitHub Secrets 가 같은 이름으로 넣는다. **경로가 하나다.**

    ★ 값이 없으면 빈 문자열을 쓰되 화면에 적는다. 조용히 빈 지도를 주면
      "왜 배경이 안 뜨지" 로 한 시간을 쓴다(원칙 ⑥ — 모르면 모른다고 적는다).
    """
    key = os.environ.get("VWORLD_KEY", "")
    if not key:
        print("  ★ VWORLD_KEY 가 없다 — 배경지도 없이 나간다.\n"
              "    로컬:  .env 에 VWORLD_KEY=... 를 적는다\n"
              "    배포:  GitHub Secrets 에 VWORLD_KEY 를 넣는다")
    out = ROOT / "web/key.js"
    out.write_text(
        "/* 생성물. 커밋하지 않는다 — tools/stage_pages.py 가 만든다.\n"
        "   ★ 이 키는 브라우저가 쓴다. 숨길 수 없다. 여기 두는 목적은\n"
        "     git 이력에 안 쌓이게 하고 재발급을 값싸게 만드는 것이다.\n"
        "     실효 방어는 V-World 도메인 잠금 하나다(만료 2027-02-04). */\n"
        f'window.__VWORLD_KEY__ = "{key}";\n', encoding="utf-8")
    print(f"  web/key.js   {'생성' if key else '빈 값으로 생성'}")


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
        _write_key_js()
        print("배포 준비 OK" if check else "배포 준비 완료")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

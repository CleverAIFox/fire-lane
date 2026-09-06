#!/usr/bin/env python3
"""
tools/install_navi.py — 내비 소스를 web/navi/src 에 앉힌다.

    uv run python tools/install_navi.py --from ~/Downloads/navi
    uv run python tools/install_navi.py --from ~/Downloads/navi --apply

── 왜 도구인가 ─────────────────────────────────────────────────
2026-09-05 에 루트에 일회성 스크립트를 놓았다가 `commit_policy` R8 에
걸렸다. 이것은 그 반복을 막는다 — **멱등이고, 기본이 dry-run 이고,
무엇을 왜 하는지 출력한다.**

★ 텍스트 치환을 하지 않는다. 파일을 통째로 놓는다. 치환은 재현이 아니다.

IN    --from 이 가리키는 트리
OUT   web/navi/src/**  (--apply 일 때만)
PARAM --from · --apply
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DST = ROOT / "web" / "navi" / "src"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True, help="내려받은 navi 트리")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    src = Path(a.src).expanduser()
    if (src / "src").is_dir():
        src = src / "src"
    if not src.is_dir():
        print(f"★ {src} 가 없다"); return 1
    if not DST.parent.is_dir():
        print(f"★ {DST.parent} 가 없다. scaffold 를 먼저 돌려라"); return 1

    files = sorted(p for p in src.rglob("*") if p.is_file())
    if not files:
        print(f"★ {src} 에 파일이 없다"); return 1

    new = same = upd = 0
    for p in files:
        rel = p.relative_to(src)
        t = DST / rel
        if not t.exists():
            print(f"  신규  {rel}"); new += 1
        elif filecmp.cmp(p, t, shallow=False):
            same += 1
            continue
        else:
            print(f"  갱신  {rel}"); upd += 1
        if a.apply:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, t)

    print(f"\n신규 {new} · 갱신 {upd} · 동일 {same}"
          + ("" if a.apply else "  (dry-run — --apply 로 실행)"))
    if a.apply and (new or upd):
        print("\n다음:")
        print("  cd web/navi && npm run dev")
        print("  ★ 옛 파일이 남아 있으면 지워라:")
        print("     rm -f web/navi/src/lib/*.ts web/navi/src/App.tsx.bak")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

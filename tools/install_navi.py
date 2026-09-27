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



# ── 앉힌 것이 그대로 있는가 ─────────────────────────────────────
# ★ 2026-09-27 (§262). 종전 이 자리는 「내용은 안 본다 — 지문은 golden 이 이미
#   한다」였고 출력도 「내용 대조는 golden 소관」이었다. **둘 다 거짓이었다.**
#   `golden.judgment_files()` 는 `code_closure("firelane.segments")` + `uv.lock`
#   이라 내비 파일을 **하나도** 안 잠근다. 76파일이 「누가 든다」를 잘못 적은 채
#   서 있었고, 그런 문장은 다음 사람에게 「저기서 봤겠지」를 판다.
#
# ★ golden 에 넣지 않는다. golden 은 **판정 지문**이라 UI 한 줄에도 재잠금을
#   부른다 — 판정과 무관한 변경이 판정 잠금을 흔든다.
# ★ 지문 파일을 새로 두지도 않는다. 내비 소스의 변화감지는 **git 이 이미** 한다.
#   하나 더 만들면 UI 를 고칠 때마다 갱신해야 하고, 잊으면 영구 빨간불이 된다 —
#   사람이 검사를 끄게 만드는 그 형태다(§69).
#
# 내비 **내용**을 실제로 드는 것은 아래 넷이고, 여기는 **목록**만 책임진다.
GUARDS = ("tsc", "vitest", "style-spec 검증기", "git")


def check() -> int:
    dst = ROOT / "web" / "navi" / "src"
    if not dst.is_dir():
        print("\u2717 web/navi/src 가 없다 — 내비 소스가 앉지 않았다")
        return 1
    n = sum(1 for p in dst.rglob("*") if p.is_file())
    if not n:
        print("\u2717 web/navi/src 가 비었다")
        return 1
    print(f"\u2713 web/navi/src {n}파일 (목록) — 내용은 " + " · ".join(GUARDS) + " 가 든다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", help="내려받은 navi 트리")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="상태만 본다. 아무것도 안 바꾼다")
    a = ap.parse_args()
    # ★ --check 는 아무것도 안 바꾼다. verify.sh 전용
    if a.check:
        return check()

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

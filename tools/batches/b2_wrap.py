#!/usr/bin/env python3
"""
b2_wrap.py — B2 **마지막 일회성 배치.** 도구를 제자리에 놓는다.

    uv run python tools/b2_wrap.py            무엇을 할지만
    uv run python tools/b2_wrap.py --apply    실제로

★ 이 스크립트 자신도 일회성이고, 마지막 일로 **자기를 tools/batches/ 로
  옮긴다.** 그러면 `tools/` 에는 재현적 도구만 남는다.

── 판별식 ─────────────────────────────────────────────────────
      "내년에도 이걸 돌릴 일이 있나"
        있다  →  tools/           이름에 배치 번호를 안 단다
        없다  →  tools/batches/   b2_ 처럼 배치 번호를 단다

  `test_tools_are_wired` 는 `tools/*.py` 만 보므로 하위 폴더는 안 본다 —
  EXEMPT 를 늘릴 필요가 없어진다. 목록을 안 늘리는 것이 목록에 사유를
  적는 것보다 낫다(navi_setup.EXEMPT_ADD 의 유령 `bottleneck` 이 그 예다).

하는 일 여섯 —

  ㉓ b2_close ⑨ 제거      intake·sweep 이 그 일이다. 세 번 죽었다
  ㉔ verify.sh 배선        lakecheck 스텝. ⑨ 가 죽어서 한 번도 실행 못 됐다
  ㉕ sweep 판정 범위        데이터 확장자만 본다. .py·desktop.ini 를 "미판단"
                          으로 내면 시끄럽고, 시끄러우면 사람이 끈다
  ㉖ b2_sweep → sweep      재현적 도구는 배치 번호를 달지 않는다
  ㉗ 일회성 넷을 batches/   tools/ 를 더럽히지 않는다
  ㉘ .gitignore            LAKELIST.json · sources.yaml.b2* · REDLIST.json
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
BATCH = TOOLS / "batches"

ONESHOT = ["b2_lake.py", "b2_close.py", "b2_final.py", "b2_intake.py", "b2_wrap.py"]

BATCH_README = """# tools/batches — 한 번 돌고 끝난 배치

여기 있는 것은 **일회성**이다. 이미 돌았고 다시 안 돈다.

## 지우지 않는 이유

무엇을 왜 바꿨는지가 git 로그보다 여기 잘 적혀 있다. 각 스크립트의
머리말이 그 배치의 판단 근거를 담고 있고, 다음에 비슷한 상황이 오면
그것부터 읽는다.

전부 멱등이라 다시 돌려도 안전하지만 돌 이유가 없다 — 이미 적용된
상태를 감지하고 "변경 없음" 을 낸다.

## 여기 있으면 안 되는 것

**유지 검사는 여기 두지 않는다.** 배치가 세운 상태가 유지되는지는
`tools/` 의 재현적 도구가 본다.

| 배치가 세운 것 | 유지를 보는 도구 |
|---|---|
| 제공기관 state · norm 명명 규칙 | `lakecheck` L1 · L6 |
| 격리 잔재 · landing 우회 · norm 계보 | `lakecheck` L2 · L3 · L5 |
| 대장 ↔ 취득 규칙 매칭 | `intake --plan` |
| 폐기 대장 관문 | `intake` 자체 |
| 다운로드·레이크 정리 | `sweep` |

검사를 두 벌 만들지 않는다. 그것이 이 저장소가 232번 당한 형태다.

## 판별식

    "내년에도 이걸 돌릴 일이 있나"
      있다  →  tools/           이름에 배치 번호를 안 단다
      없다  →  tools/batches/   b2_ 처럼 배치 번호를 단다
"""

GITIGNORE = """
# ── 검사 도구의 출력 (2026-09-10) ───────────────────────────────
# 실행할 때마다 바뀌고 정본은 도구 코드지 그 출력이 아니다.
LAKELIST.json
REDLIST.json
BATCH_MAP.json
# b2_* 배치가 뜬 sources.yaml 백업. git 이 이력을 갖는다
sources.yaml.b2*
"""

VERIFY = """
# ── 데이터 레이크 정합 ──────────────────────────────────────────
# ★ 선언과 실물이 갈리는 것을 fsck 가 다 보지 못했다 — 제공기관 state ·
#   격리 잔재 · landing 우회 · ext 어휘 · norm 계보 다섯 축이 밖에 있었다.
#   lakecheck 이 그 축을 든다. FIRE_LANE_INBOX 를 기본 스캔 대상으로 쓴다.
step "레이크 선언↔실물" uv run python tools/lakecheck.py
"""

SWEEP_EXT = '''JUNK = {".tmp", ".crdownload", ".part", ".partial"}

# ★ 데이터 확장자만 판정한다. 다운로드 폴더에는 스크립트·설정 파일도
#   섞이는데 그것까지 "미판단" 으로 내면 목록이 시끄러워지고, 시끄러우면
#   사람이 검사를 끈다. lakecheck L3 와 같은 어휘를 쓴다.
DATA_EXT = {".zip", ".7z", ".csv", ".json", ".shp", ".gpkg", ".tif",
            ".hwp", ".hwpx", ".xls", ".xlsx", ".txt", ".dbf", ".pdf", ".xml"}'''


def move(src: Path, dst: Path, apply: bool, why: str) -> bool:
    if not src.exists():
        print(f"  = {src.name}  없다 ({why})")
        return False
    if dst.exists():
        print(f"  = {dst.relative_to(ROOT)}  이미 있다")
        return False
    print(f"  {'→' if apply else '·'} {src.name}  →  {dst.relative_to(ROOT)}")
    print(f"      {why}")
    if apply:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    print(f"{'적용' if a.apply else 'dry-run — --apply 로 실행'}\n")
    fail = 0

    print("── ㉓ b2_close ⑨ 제거 — intake·sweep 이 그 일이다")
    p = TOOLS / "b2_close.py"
    if not p.exists():
        print("  = 이미 옮겨졌거나 없다")
    else:
        s = p.read_text(encoding="utf-8")
        if "shutil.move(str(s), str(d))" not in s:
            print("  = 이미 제거됨")
        else:
            m = re.search(r'    print\("\\n── ⑨ landing 이관"\)\n(?:.*\n)*?    return 0\n',
                          s)
            if not m:
                print("  ✗ ⑨ 블록 앵커를 못 찾았다")
                fail += 1
            else:
                new = ('    print("\\n── ⑨ landing 이관")\n'
                       '    # ★ 이 스크립트가 안 한다. tools/intake.py 가 그 일이다 —\n'
                       '    #   다운로드→landing 은 sha 기록과 정규명 제안이 붙어야 하고,\n'
                       '    #   원본 정리는 sweep 이 근거를 대고 지운다. 여기서 shutil.move\n'
                       '    #   를 직접 부르다 cross-device 로 **세 번** 죽었고, 그 바람에\n'
                       '    #   뒤에 있던 ⑫(verify.sh 배선)가 한 번도 실행되지 못했다.\n'
                       '    print("  = intake --stage / sweep --sweep 소관. 여기서 안 한다")\n'
                       '    return 0\n')
                out = s[:m.start()] + new + s[m.end():]
                import ast
                try:
                    ast.parse(out)
                except SyntaxError as e:
                    print(f"  ✗ 구문 오류 {e.lineno}행")
                    fail += 1
                else:
                    print(f"  {'→' if a.apply else '·'} ⑨ 를 안내로 교체")
                    if a.apply:
                        p.write_text(out, encoding="utf-8")

    print("\n── ㉔ verify.sh 배선 — ⑨ 가 죽어서 한 번도 실행 못 됐다")
    v = TOOLS / "verify.sh"
    if not v.exists():
        print("  ✗ tools/verify.sh 없음")
        fail += 1
    else:
        s = v.read_text(encoding="utf-8")
        if "레이크 선언↔실물" in s:
            print("  = 이미 있다")
        else:
            m = re.search(r"^printf .*통과", s, re.M)
            at = m.start() if m else len(s)
            print(f"  {'→' if a.apply else '·'} lakecheck 스텝 추가")
            if a.apply:
                v.write_text(s[:at] + VERIFY.strip("\n") + "\n\n" + s[at:],
                             encoding="utf-8")

    print("\n── ㉕ sweep 이 데이터 확장자만 판정하게")
    sw = TOOLS / "b2_sweep.py"
    sw = sw if sw.exists() else TOOLS / "sweep.py"
    if not sw.exists():
        print("  ✗ sweep 스크립트가 없다")
        fail += 1
    else:
        s = sw.read_text(encoding="utf-8")
        if "DATA_EXT" in s:
            print("  = 이미 적용")
        else:
            s = s.replace('JUNK = {".tmp", ".crdownload", ".part", ".partial"}',
                          SWEEP_EXT, 1)
            s = s.replace(
                '    files = [p for p in sorted(d.iterdir())\n'
                '             if p.is_file() and p.stat().st_size >= min_mb * 1e6]',
                '    files = [p for p in sorted(d.iterdir())\n'
                '             if p.is_file() and p.stat().st_size >= min_mb * 1e6\n'
                '             and (p.suffix.lower() in DATA_EXT\n'
                '                  or p.suffix.lower() in JUNK)]')
            if "DATA_EXT" not in s:
                print("  ✗ 앵커를 못 찾았다")
                fail += 1
            else:
                print(f"  {'→' if a.apply else '·'} DATA_EXT 필터 (.py·desktop.ini 제외)")
                if a.apply:
                    sw.write_text(s, encoding="utf-8")

    print("\n── ㉖ b2_sweep.py → sweep.py — 재현적 도구는 배치 번호를 안 단다")
    move(TOOLS / "b2_sweep.py", TOOLS / "sweep.py", a.apply,
         "매번 쓴다 — 새 자료를 받을 때마다 스캔·검증·정리한다")

    print("\n── ㉗ 일회성 배치를 tools/batches/ 로")
    for n in ONESHOT:
        if n == "b2_wrap.py":
            continue
        move(TOOLS / n, BATCH / n, a.apply, "한 번 돌고 끝났다")
    rd = BATCH / "README.md"
    if rd.exists():
        print("  = batches/README.md 이미 있다")
    else:
        print(f"  {'→' if a.apply else '·'} batches/README.md — 판별식과 유지 검사 표")
        if a.apply:
            BATCH.mkdir(parents=True, exist_ok=True)
            rd.write_text(BATCH_README, encoding="utf-8")

    print("\n── ㉘ .gitignore — 검사 출력과 백업")
    g = ROOT / ".gitignore"
    s = g.read_text(encoding="utf-8") if g.exists() else ""
    if "LAKELIST.json" in s:
        print("  = 이미 있다")
    else:
        print(f"  {'→' if a.apply else '·'} LAKELIST · REDLIST · BATCH_MAP · b2 백업")
        if a.apply:
            g.write_text(s.rstrip("\n") + "\n" + GITIGNORE, encoding="utf-8")

    print(f"\n{'실패 ' + str(fail) + '건' if fail else '전부 통과'}")
    if a.apply and not fail:
        me = Path(__file__).resolve()
        if me.parent == TOOLS:
            BATCH.mkdir(parents=True, exist_ok=True)
            shutil.move(str(me), str(BATCH / me.name))
            print("\n  → b2_wrap.py  →  tools/batches/b2_wrap.py  (자기 자신)")
        print("\ntools/ 에 남는 재현적 도구 —")
        for x in sorted(TOOLS.glob("*.py")):
            if x.stem in ("lakecheck", "sweep", "codepatch", "deadcheck", "widen"):
                print(f"  {x.name}")
        print("\n다음 —")
        print("  uv run python tools/sweep.py")
        print("  bash tools/verify.sh")
        print("  git add -A && git status --short")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())

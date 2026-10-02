#!/usr/bin/env python3
"""
selftests.py — 선언된 `--selftest` 를 **전부** 돌린다. 문 하나.

    uv run python tools/selftests.py            전부 (레이크 필요한 것은 건너뛴다)
    uv run python tools/selftests.py --list     무엇이 있고 무엇을 건너뛰나
    uv run python tools/selftests.py --selftest ★ 수집이 살아 있나

── 왜 생겼나 (2026-09-28 실측 · DECISIONS §286) ────────────────
`--selftest` 를 선언한 도구 25개를 세고, 그중 **몇 개가 실제로 불리나**를
쟀다. **16개가 아무도 안 부른다** — `docseal` · `gate_parity` · `tonecheck` ·
`suppress` · `argcheck` 가 그 안에 있다.

★ 이것이 §285 보다 한 겹 깊다. 거기서는 **검사기**가 안 불렸다. 여기서는
  **검사기가 살아 있는지 보는 것**이 안 불린다. `--selftest` 가 존재하는
  이유는 하나다 — 그물이 비었는데 초록을 내는 것을 잡는 것. 그것을 안
  돌리면 그물이 빈 날 아무도 모른다.

★ 16개를 한 줄씩 `verify.sh` 에 붙이지 않는다. 그러면 17번째 도구가
  생기는 날 또 빠진다. **수집이 정본**이고 부르는 자리는 하나다.
  이 저장소가 `ledger.REQUIRED`(§285-2) · `kinds.KINDS`(§284-4) 에서
  세 번 배운 것과 같은 꼴이다.

── 건너뛰는 것 ────────────────────────────────────────────────
레이크가 있어야 도는 자기검사는 레이크 없는 곳에서 건너뛴다. **건너뛴
것은 이름과 사유를 낸다** — 말없이 빠지면 「전부 돌았다」가 거짓이 된다.
사유는 `SKIP` 에 적히고, 죽은 선언은 `--selftest` 가 잡는다.

IN    tools/**/*.py · src/firelane/**/*.py
OUT   없음 (검사). 종료코드 = 빨간 자기검사 수
PARAM SKIP · TIMEOUT
밖    **자기검사가 옳은 것을 보는가는 안 본다.** `docseal --selftest` 가
      제대로 된 물음을 던지는지는 그 도구가 안다. 여기가 드는 것은
      「선언된 것이 전부 돌았는가」와 「돈 것이 초록인가」 둘이다.
      **`--selftest` 가 없는 도구를 나무라지 않는다** — 자기검사가 필요한
      도구인가는 `tools/deadcheck.py` 소관이다.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 120
WORKERS = 6

#: 레이크가 있어야만 도는 자기검사 → 사유. **사유 없이 늘리지 않는다.**
#: 죽은 선언(여기 있는데 `--selftest` 가 없는 것)은 아래 자기검사가 잡는다.
SKIP: dict[str, str] = {
    "lakecheck": "프로브가 레이크 실물에서 0건인지를 본다. 레이크가 없으면 물음이 성립하지 않는다",
    "vintage_check": "레이크를 직접 훑어 파일명 날짜를 본다. 대장 글롭으로는 안 보인다",
    "freshcheck": "레이크의 raw 갱신일과 대장을 대조한다. CI 에 레이크가 없다",
    "fixture_recut": "레이크 원본에서 고정본을 다시 자른다. 원본이 있어야 한다",
    "navi_env": "`npm` 과 `web/navi/node_modules` 가 있어야 한다. 설치 안 된 기계에서는 못 돈다",
    "cv_queue": "CV 대기열은 실측 사진 폴더를 본다. 레이크 밖 기기에 있다",
}


def _has_selftest(p: Path) -> bool:
    """`--selftest` 를 받는가. 글자가 아니라 AST 로 본다.

    ★ 글자로 보면 머리말에 적힌 사용 예시가 선언으로 세어진다(§283-3).
      그래서 **독스트링 안의 상수는 뺀다** — 그것이 §283-3 이 막은 전부다.

    ★ 2026-10-03 (DECISIONS §359). 종전에는 `add_argument("--selftest")`
      **하나만** 셌다. 그런데 이 저장소의 도구 절반은 `sys.argv` 를 손으로
      가른다(`if rest == ["--selftest"]`) — argparse 를 안 쓴다. 그 꼴은
      선언으로 안 세어져서, **자기검사가 있는데 아무도 안 돌리는 도구가
      셋 있었다**: `docnum_check` · `unusedcheck` · `verdict_tally`.
      셋 다 지금 돌리면 통과한다 — 그래서 더 나쁘다. **살아 있는데 안
      불리는 검사는 죽은 검사와 구별이 안 된다**(1족 · 무음 통과).

      이 함수가 넓어지면 `jsonkeys` · `localgeo` · `svg_fit` 도 들어온다.
      셋은 **인자 없이** 자기검사를 돌던 도구라 플래그를 같이 받게 했다.
    """
    try:
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (SyntaxError, OSError):
        return False
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef))
            and ast.get_docstring(n) is not None}
    return any(isinstance(n, ast.Constant) and n.value == "--selftest"
               and id(n) not in docs
               for n in ast.walk(tree))


def tools() -> list[Path]:
    return [p for p in sorted([*(ROOT / "tools").rglob("*.py"),
                               *(ROOT / "src" / "firelane").rglob("*.py")])
            if "__pycache__" not in p.parts and _has_selftest(p)]


def _run(p: Path) -> tuple[Path, int, str]:
    try:
        r = subprocess.run([sys.executable, str(p), "--selftest"], check=False,
                           capture_output=True, text=True, timeout=TIMEOUT,
                           cwd=ROOT)
    except subprocess.TimeoutExpired:
        return p, 124, f"★ {TIMEOUT}초 안에 안 끝났다"
    return p, r.returncode, (r.stdout + r.stderr).strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    found = tools()
    run = [p for p in found if p.stem not in SKIP]
    skipped = [p for p in found if p.stem in SKIP]

    if a.list:
        print(f"── 선언된 자기검사 {len(found)}")
        for p in run:
            print(f"  돈다    {p.relative_to(ROOT).as_posix()}")
        for p in skipped:
            print(f"  건너뜀  {p.relative_to(ROOT).as_posix()}  — {SKIP[p.stem]}")
        return 0

    print(f"── 자기검사 {len(run)}개 (건너뜀 {len(skipped)})")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        res = list(ex.map(_run, run))
    bad = []
    for p, rc, out in sorted(res, key=lambda x: x[0].name):
        rel = p.relative_to(ROOT).as_posix()
        if rc == 0:
            print(f"  ✓ {rel}")
        else:
            bad.append(rel)
            print(f"  ✗ {rel}  (종료 {rc})")
            for line in out.splitlines()[-6:]:
                print(f"      {line}")
    for p in skipped:
        print(f"  · {p.relative_to(ROOT).as_posix()} 건너뜀 — {SKIP[p.stem]}")
    if bad:
        print(f"\n★ 자기검사 {len(bad)}개가 빨갛다 — {', '.join(bad)}")
        print("  자기검사가 빨갛다는 것은 **그 도구의 판정을 믿을 수 없다**는 뜻이다.")
        return len(bad)
    print(f"\n✓ 자기검사 {len(run)}개 전부 초록 · 건너뜀 {len(skipped)}")
    return 0


def selftest() -> int:
    """★ 수집이 살아 있나. 0개를 모으면 전부 통과로 보인다."""
    bad = []
    found = tools()
    if len(found) < 20:
        bad.append(f"자기검사를 {len(found)}개만 찾았다 — 수집이 죽었다")
    # 죽은 건너뜀 선언 — 그 도구에 `--selftest` 가 없다
    names = {p.stem for p in found}
    for k in SKIP:
        if k not in names:
            bad.append(f"`SKIP` 의 `{k}` 에는 `--selftest` 가 없다 — 죽은 선언이다")
    # ★ 머리말의 예시를 선언으로 세면 안 된다(§283-3). 합성 파일로 문다.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        prose = Path(d) / "산문만.py"
        prose.write_text('"""도구.\n\n    python 도구.py --selftest\n"""\n',
                         encoding="utf-8")
        if _has_selftest(prose):
            bad.append("머리말에 적힌 `--selftest` 를 선언으로 셌다")
        real = Path(d) / "진짜.py"
        real.write_text("import argparse\n"
                        "ap = argparse.ArgumentParser()\n"
                        'ap.add_argument("--selftest", action="store_true")\n',
                        encoding="utf-8")
        if not _has_selftest(real):
            bad.append("실제 선언을 못 읽는다 — 수집이 죽었다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 도구 {len(found)}개를 AST 로 모으고 "
          f"건너뜀 {len(SKIP)}개가 전부 실재한다")
    return 0


if __name__ == "__main__":
    sys.exit(main())

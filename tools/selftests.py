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
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from firelane import gitq

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 120
WORKERS = 6

#: 제한의 **몇 할**을 넘으면 말하나. 넘어도 **종료코드는 안 건드린다** —
#: 동시에 여섯을 돌리므로 벽시계는 그 기계의 부하를 탄다. 판정이 아니라 눈이다.
#:
#: ★ 2026-10-11 (DECISIONS §463-5). `sealcov` 가 제한을 넘어 **종료 124** 로
#:   빨개져서야 느린 것이 보였다. 재 보니 그 전부터 78초였다 — 제한의 65% 를
#:   쓰고 있었고 **아무도 몰랐다.** 넘는 날과 넘기 전날 사이에 말이 없으면
#:   그 관문은 늘 「갑자기」 빨개진다.
SLOW_FRAC = 0.5

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


def _run(p: Path) -> tuple[Path, int, str, float]:
    t = time.time()
    try:
        r = subprocess.run([sys.executable, str(p), "--selftest"], check=False,
                           capture_output=True, text=True, timeout=TIMEOUT,
                           cwd=ROOT)
    except subprocess.TimeoutExpired:
        return p, 124, f"★ {TIMEOUT}초 안에 안 끝났다", time.time() - t
    return p, r.returncode, (r.stdout + r.stderr).strip(), time.time() - t


def slow_ones(res: list[tuple[Path, int, str, float]]) -> list[tuple[float, Path]]:
    """제한의 `SLOW_FRAC` 이상을 쓴 것들. 느린 순.

    ★ 제한에 **걸린** 것(124)은 안 센다 — 그쪽은 이미 빨갛고, 여기 또 적으면
      같은 사실을 두 번 말한다. 여기가 드는 것은 **아직 안 빨간 것**이다.
    """
    return sorted(((s, p) for p, rc, _o, s in res
                   if rc != 124 and s >= SLOW_FRAC * TIMEOUT), reverse=True)


def green(rc: int) -> bool:
    """그 종료 수가 **초록인가.** 0 하나다.

    ★ 2026-10-11 (DECISIONS §478-1). 이 한 줄이 보고문 안의 `if rc == 0` 이었고
      **돌연변이가 `!=` 로 밀어도 조용했다** — 그러면 빨간 자기검사에 ✓ 가
      붙고 초록에 ✗ 가 붙는다. 보고가 뒤집히는 것은 결함이 없는 것보다 나쁘다.
      순수 함수로 빼서 판별식이 **양쪽을 민다.**

    ★ 0 만 초록이다. 124(제한 초과)도 1 도 빨강이고, 그 둘을 가르는 것은
      느린 것 보고의 일이다(`slow_ones` 가 124 를 뺀다).
    """
    return rc == 0


def _dirty() -> list[str] | None:
    """더러운 파일 목록. **못 물으면 `None`** — 빈 목록과 다른 사실이다.

    ★ `firelane.gitq` 를 쓴다. 처음에는 여기서 `subprocess` 를 직접 부르고
      실패를 `""` 로 바꿨는데, `deadcheck ③`(조용한 통과)이 그 자리를 잡았다 —
      **빈 우주가 초록이 된다**(§372). 회색 = NULL 은 판정에서만이 아니라
      도구에서도 지킨다.
    """
    return gitq.dirty(ROOT)


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
    # ★ 2026-10-09 (DECISIONS §443-6). **자기검사는 트리를 안 흔든다.**
    #   하룻밤에 두 번 같은 실수를 했다 — 판별식을 밀려고 실물 파일을 고쳤다
    #   되돌리는 꼴이다. 되돌려도 **그 사이**가 있다. 위 `ThreadPoolExecutor`
    #   가 도구를 **동시에** 돌리므로 그 사이에 남이 그 파일을 읽고, 배달
    #   기계는 「추적 파일에 변경이 있다」를 본다.
    #   ★ 기억으로 막는 규율은 두 번째에 깨진다. 그래서 **센다.**
    was = _dirty()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        res = list(ex.map(_run, run))
    now = _dirty()
    if was is None or now is None:
        print("   (트리 대조 건너뜀 — git 에게 못 물었다. **깨끗하다는 뜻이 아니다**)")
    bad = []
    for p, rc, out, _s in sorted(res, key=lambda x: x[0].name):
        rel = p.relative_to(ROOT).as_posix()
        if green(rc):
            print(f"  ✓ {rel}")
        else:
            bad.append(rel)
            print(f"  ✗ {rel}  (종료 {rc})")
            for line in out.splitlines()[-6:]:
                print(f"      {line}")
    # ★ 2026-10-11 (DECISIONS §463-5). **넘기 전에 말한다.** 판정이 아니다.
    slow = slow_ones(res)
    if slow:
        print(f"\n★ 제한({TIMEOUT}초)의 {SLOW_FRAC:.0%} 를 넘게 쓴 자기검사 {len(slow)}개 — "
              "**빨개지는 날은 결함이 아니라 제한이 든다**")
        for s, p in slow:
            print(f"      {s:6.1f}초  {p.relative_to(ROOT).as_posix()}")
        print("   벽시계는 부하를 탄다 — 그래서 종료코드는 안 건드린다. 재 보고 가려라.")
    for p in skipped:
        print(f"  · {p.relative_to(ROOT).as_posix()} 건너뜀 — {SKIP[p.stem]}")
    if was is not None and now is not None and was != now:
        moved = sorted(set(now) ^ set(was))
        print("\n★ **자기검사가 트리를 흔들었다** — 돌기 전과 뒤가 다르다")
        for x in moved[:12]:
            print(f"      {x}")
        print("   자기검사는 **읽기만** 한다. 판별식을 순수 함수로 떼고 합성 입력으로 밀어라 —")
        print("   되돌리더라도 그 사이에 남이 그 파일을 읽는다(동시에 돈다).")
        return 1 + len(bad)
    if bad:
        print(f"\n★ 자기검사 {len(bad)}개가 빨갛다 — {', '.join(bad)}")
        print("  자기검사가 빨갛다는 것은 **그 도구의 판정을 믿을 수 없다**는 뜻이다.")
        return len(bad)
    print(f"\n✓ 자기검사 {len(run)}개 전부 초록 · 건너뜀 {len(skipped)}")
    return 0


#: 이 러너의 **우주 밖**에서 도는 자기검사 — 이름 → 어디서 도나.
#:
#: ── 왜 적나 (2026-10-11 · DECISIONS §478) ──────────────────────
#: `tools/scopedecl.py` 의 `SELFTEST_MIN` 은 **76** 을 세고 이 러너는 **70** 을
#: 모은다. 그 여섯이 안 도는 것이 아니라 **다른 자리에서 돈다** — 그런데 그
#: 사실을 적은 데가 없어서, 두 수를 나란히 본 사람은 「자기검사 여섯이 죽었다」로
#: 읽는다. **수가 둘이면 그 차이를 적는다**(§456 이 「105 가 전부 필요한가」에서
#: 배운 그것이다 — 세는 단위가 다르면 그 단위를 적어야 수가 말이 된다).
#:
#: ★ 아래 자기검사가 이 목록이 **정확히** 그 차집합인지 든다 — 일곱째가
#:   생기면 운다. 고치는 길은 둘이다: 이 러너가 보게 만들거나, 여기 적는다.
OUTSIDE: dict[str, str] = {
    # 셸 도구 — 이 러너는 `tools/*.py` 만 모은다(파이썬 하위프로세스로 돈다)
    "ci_wait.sh": "tests/test_batch_tools.py · tests/test_seal_survives_squash.py",
    "treescan.sh": "tools/verify.sh · .github/workflows (제 단계로 돈다)",
    # 깃발 없이 **인자 없으면 자기검사**인 도구 — 제 단계로 돈다
    "localgeo.py": "tools/verify.sh (제 단계 · 인자 없이 치면 자기검사다)",
    "svg_fit.py": "tools/verify.sh · .github/workflows (제 단계)",
    # 옆집 판별식 — 주인의 `--selftest` 가 끌어온다(§445 · §449-2)
    "docnumtest.py": "tools/docnum_check.py --selftest 가 끌어온다",
    "uichecktest.py": "tools/uicheck.py --selftest 가 끌어온다",
    # 진입점 없는 몸통 — pytest 가 **함수를 직접** 부른다(§509)
    "widthlr.py": "tests/test_widthlr.py::test_the_tool_passes_its_own_selftest",
}


def outside_faults(root: Path = ROOT) -> list[str]:
    """`scopedecl` 이 세는 우주 − 이 러너의 우주 = `OUTSIDE` 인가. **비면 산다.**"""
    import scopedecl  # noqa: PLC0415  맞물림을 끊는다 (scopedecl 은 이 파일을 안 든다)

    # ★ 2026-10-12 (DECISIONS §482). 종전에는 `tools` 하나만 훑었고
    #   `deadcheck` ⑤가 그것을 **좁은 범위**로 집었다. 넓혀도 **결과는 같다** —
    #   `src/firelane` 쪽은 이 러너가 이미 다 모으므로 차집합이 비기 때문이다.
    #   그래도 넓힌다: 그 쪽 수집이 깨지는 날 이 자가 **그때** 울어야 하고,
    #   「지금 비어 있으니 안 본다」가 바로 1족(무음 통과)이 자라는 자리다.
    counted = {q.name
               for d in (root / "tools", root / "src" / "firelane")
               if d.is_dir()
               for q in sorted(d.iterdir())
               if q.is_file() and scopedecl.has_selftest(q)}
    mine = {p.name for p in tools()}
    gap, listed = counted - mine, set(OUTSIDE)
    bad = []
    for n in sorted(gap - listed):
        bad.append(f"{n} — `scopedecl` 은 세는데 이 러너가 안 돌리고 어디서 도는지"
                   " 적힌 데도 없다. 러너가 보게 하거나 `OUTSIDE` 에 적어라")
    for n in sorted(listed - gap):
        bad.append(f"{n} — `OUTSIDE` 에 있는데 차집합에 없다. 죽은 선언이다(§370)")
    return bad


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
    # ── §463-5 · 느린 것을 고르는 자가 산다 ──────────────────────
    if not 0 < SLOW_FRAC < 1:
        bad.append(f"SLOW_FRAC {SLOW_FRAC} 이 (0,1) 밖이다 — 0 이면 전부, 1 이면 아무것도 안 든다")
    _c = TIMEOUT * SLOW_FRAC
    _fake = [(Path("빠름.py"), 0, "", _c - 1), (Path("느림.py"), 0, "", _c + 1),
             (Path("더느림.py"), 0, "", TIMEOUT - 0.5),
             (Path("걸림.py"), 124, "", TIMEOUT)]
    got = [p.name for _s, p in slow_ones(_fake)]
    if got != ["더느림.py", "느림.py"]:
        bad.append(f"느린 것 고르기가 틀렸다 — {got}")
    # ── §478-1 · 돌리는 자를 **실제로** 돌려 본다 ─────────────────
    #   ★ 위 판별식들은 `_fake` 튜플로 `slow_ones` 만 밀었다. 그래서 `_run`
    #     자신은 **한 번도 안 돌았고**, 돌연변이가 `text=True` 를 `False` 로
    #     밀어도 조용했다 — 그러면 모든 출력이 바이트가 되고 보고가 깨진다.
    #     합성 도구 둘(초록 · 빨강)로 양쪽을 민다.
    with tempfile.TemporaryDirectory() as d:
        ok_t = Path(d) / "초록.py"
        ok_t.write_text("import sys\nprint('ok')\nsys.exit(0)\n", encoding="utf-8")
        ng_t = Path(d) / "빨강.py"
        ng_t.write_text("import sys\nprint('ng')\nsys.exit(1)\n", encoding="utf-8")
        gp, grc, gout, gs = _run(ok_t)
        bp, brc, bout, bs = _run(ng_t)
        if (grc, brc) != (0, 1):
            bad.append(f"종료 수를 안 돌려준다 — 초록 {grc} · 빨강 {brc}")
        if not isinstance(gout, str) or "ok" not in gout:
            bad.append(f"출력이 글자가 아니다 — {type(gout).__name__} {gout!r:.40}")
        if "ng" not in bout:
            bad.append("빨간 도구의 출력을 안 담는다")
        if not (gs >= 0 and bs >= 0):
            bad.append(f"걸린 시간이 음수다 — {gs} · {bs}")

    # ── §478-1 · 보고의 초록/빨강을 가르는 자 ─────────────────────
    if not green(0):
        bad.append("종료 0 을 빨강으로 센다")
    if any(green(rc) for rc in (1, 2, 124, -1)):
        bad.append("0 이 아닌 종료 수를 초록으로 센다")

    # ── §478 · 두 수의 차이가 적혀 있나 ─────────────────────────
    bad += outside_faults()
    # ★ **양방향.** 거짓 이름을 심으면 「죽은 선언」으로 울어야 한다.
    if not any("죽은 선언" in m for m in _fake_outside_faults()):
        bad.append("`OUTSIDE` 의 죽은 선언을 안 댄다 — 자가 죽었다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 도구 {len(found)}개를 AST 로 모으고 "
          f"건너뜀 {len(SKIP)}개가 전부 실재한다 · 우주 밖 {len(OUTSIDE)}개가 "
          f"`scopedecl` 과 맞는다")
    return 0


def _fake_outside_faults() -> list[str]:
    """★ 카나리아 — `OUTSIDE` 에 없는 이름을 심어 그 자가 우는지 본다."""
    saved = dict(OUTSIDE)
    try:
        OUTSIDE["없는도구.py"] = "없다"
        return outside_faults()
    finally:
        OUTSIDE.clear()
        OUTSIDE.update(saved)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
argcheck.py — 관문이 도구를 **부를 수 있는 인자로** 부르는가.  (§258-8 · PLAN #133 닫힘)

    uv run python tools/argcheck.py              대조
    uv run python tools/argcheck.py --selftest   ★ 판별식이 살아 있나

★ 왜 생겼나 (2026-09-25 · DECISIONS §257-2). `verify.sh:530` 이
  `docx_figs.py --check` 로 부르는데 §243 이 그 도구를 `sys.argv` 손파싱에서
  argparse 로 옮기면서 **`--check` 를 안 받게 했다.** 뜻은 같았지만 argparse 는
  모르는 인자에 죽는다. 그리고 그것이 **전수 verify 를 돌린 뒤에야** 드러났다 —
  `test_tools_are_wired` 는 도구 **이름**이 관문에 있는지만 본다.

  §243 이 고친 결함이 「오타가 조용히 무시된다」였다. 좁히는 쪽으로 고치면서
  부르는 자리를 안 봤다 — **좁힌 쪽이 부르는 쪽보다 좁아졌다**(W3-8 족).

── 어떻게 묻나 ────────────────────────────────────────────────
`verify.sh` 의 `step` 줄에서 `tools/*.py ...` 호출을 뽑아, 그 도구를
`--help` 로 한 번 돌려 **받는 인자 목록**을 얻고 대조한다.

★ **실행해서 묻는다.** 소스를 정규식으로 읽으면 `add_argument` 를 루프나
  함수로 부르는 도구를 놓치고, 놓친 것은 조용하다. `-h` 는 argparse 가
  rc=0 으로 내므로 기계로 물을 수 있는 유일한 정본이다.

★ 위치 인자(`dms verify` · `golden check`)는 **이름만** 본다. 값의 참을 묻는 것은
  그 도구 소관이고, 여기서 하면 판별식이 도구마다 갈린다.

IN    tools/verify.sh · tools/*.py (각자의 `--help`)
OUT   표준출력 (판정) · rc
PARAM SKIP
밖    `.sh` · `.mjs` 도구는 범위 밖이다 — `--help` 를 rc=0 으로 내는 규약이 없다.
      값이 맞는지도 안 본다(`--min 40` 의 40 이 옳은 수인가). 여기서 보는 것은
      **「그 인자를 받는가」** 하나다. 그리고 관문 밖(README · CI)의 호출은 안 본다.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify.sh"

#: 돌리면 일이 일어나는 도구는 `--help` 도 안 태운다. **사유와 함께** 적는다.
SKIP: dict[str, str] = {}

CALL = re.compile(r"tools/(?P<tool>[\w_]+\.py)(?P<rest>(?:\s+[^\s\\\"';|&]+)*)")


def calls(text: str) -> dict[str, set[str]]:
    """`step` 줄에서 뽑은 도구 → 그 도구에 주는 대시 인자들."""
    out: dict[str, set[str]] = {}
    for ln in text.splitlines():
        if "step " not in ln or "tools/" not in ln:
            continue
        for m in CALL.finditer(ln):
            flags = {w for w in m.group("rest").split() if w.startswith("-")}
            out.setdefault(m.group("tool"), set()).update(flags)
    return out


def accepted(tool: Path) -> set[str] | None:
    """그 도구가 받는 대시 인자. `--help` 가 안 되면 None."""
    try:
        r = subprocess.run([sys.executable, str(tool), "--help"],
                           capture_output=True, text=True, timeout=90, cwd=ROOT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return set(re.findall(r"(--[\w-]+|(?<![\w-])-\w)(?![\w-])", r.stdout))


def check() -> list[str]:
    if not VERIFY.is_file():
        return ["tools/verify.sh 가 없다 — 이 검사가 아무것도 못 본다"]
    got = calls(VERIFY.read_text(encoding="utf-8"))
    if not got:
        return ["★ `step` 줄에서 도구 호출을 0건 뽑았다 — 판별식을 의심하라"]
    bad, seen = [], 0
    for tool, flags in sorted(got.items()):
        if tool in SKIP:
            continue
        p = ROOT / "tools" / tool
        if not p.is_file():
            bad.append(f"{tool} — 관문이 부르는데 파일이 없다")
            continue
        if not flags:
            continue
        ok = accepted(p)
        if ok is None:
            continue          # `--help` 규약이 없는 도구는 범위 밖(머리말 `밖`)
        seen += 1
        for f in sorted(flags - ok):
            bad.append(f"tools/{tool} 가 `{f}` 를 안 받는다 — "
                       f"verify.sh 가 그렇게 부른다. 받게 하거나 호출을 고쳐라")
    if seen == 0:
        bad.append("★ `--help` 로 물을 수 있는 도구가 0건이다 — 판별식을 의심하라")
    print(f"     관문 호출 {len(got)}종 · 인자 있는 것 {seen}종 대조")
    return bad


def selftest() -> int:
    """판별식이 **빈 그물이 아닌가.**"""
    bad = []
    got = calls('step "x" uv run python tools/a.py --check --min 40\n'
                'step "y" uv run python tools/b.py verify\n'
                '# step "z" uv run python tools/c.py --nope\n'
                'uv run python tools/d.py --notastep\n')
    if got.get("a.py") != {"--check", "--min"}:
        bad.append(f"대시 인자만 뽑지 않는다: {got.get('a.py')}")
    if got.get("b.py") != set():
        bad.append("위치 인자를 대시 인자로 센다")
    if "c.py" not in got:
        bad.append("주석 처리된 step 을 안 본다 — 그것도 되살아날 호출이다")
    if "d.py" in got:
        bad.append("`step` 이 아닌 줄을 센다")
    # 실물로 한 번 — `--help` 를 태워 실제 인자를 읽는가
    got = accepted(ROOT / "tools" / "argcheck.py")
    if not got or "--selftest" not in got:
        bad.append(f"제 `--help` 에서 인자를 못 읽는다: {got}")
    if accepted(ROOT / "tools" / "__없는도구__.py") is not None:
        bad.append("없는 도구를 조용히 통과시킨다")
    if bad:
        print("selftest 빨강")
        for b in bad:
            print(f"  ✗ {b}")
        return 1
    print("selftest 초록")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="관문의 도구 호출 인자 ↔ 도구가 받는 인자")
    ap.add_argument("--selftest", action="store_true", help="판별식 자기검사")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    bad = check()
    if bad:
        print(f"\n✗ 인자 어긋남 {len(bad)}건")
        for b in bad:
            print(f"  {b}")
        return 1
    print("✓ 관문이 부르는 인자를 도구가 전부 받는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())

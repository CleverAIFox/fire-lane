#!/usr/bin/env python3
"""
suppress.py — **사유 없이 검사를 끄는 주석**을 센다. 양방향 래칫.  (DECISIONS §279-6)

    uv run python tools/suppress.py              검사 (양방향 래칫)
    uv run python tools/suppress.py --list       어디에 있는지 전부
    uv run python tools/suppress.py --selftest   ★ 판별식이 살아 있나

── 왜 생겼나 (2026-09-28 실측) ────────────────────────────────
SKIP 전수를 냈더니 이 저장소는 **사유 딸린 면제 쪽은 이미 매우 조여 있었다** —
`pytest` skip 39 · `verify.sh` note 9 · CI `if:` 6 · `# ci-exempt:` 12 ·
면제표 94항목, **사유 없는 것 0**. 형식으로 사유를 강제하고 죽은 면제까지
잡는 강제자가 세 방향으로 붙어 있다.

★ 남은 빚은 전부 **주석 한 줄짜리 억제**에 몰려 있었다. 표에 안 들어가고
  사유를 안 적어도 되고 아무도 안 세는 자리다 —

    noqa                        59   ★ **전부 죽은 억제였다** — 아래
    eslint-disable-line          28   ★ **eslint 가 저장소에 아예 없었다**(§279-4)
    <!--voice-ok-->              15
    <!--stale-ok-->              12
    # type: ignore                5
                                ───
                                119

★ 「사유를 적게 강제」하는 쪽이 더 낫지만 119개를 하루에 못 적는다. **세는 것이
  먼저다** — 세지 않으면 120이 되어도 아무도 모른다. 래칫은 양방향이다: 늘면
  울고, 줄여도 기록을 안 내리면 운다(느슨해진 래칫은 초록으로 위장한다).

★ **사유가 붙은 억제는 안 센다.** 「noqa 뒤에 말이 붙어 있다」 처럼
  코드 뒤에 말이 붙어 있으면 그것은 사유다. 세는 것은 **말 없이 끈 것**이다.

IN    src/** · tools/** · tests/** · web/navi/src/** · web/navi/test/** · docs/**
OUT   갈래별 수 · 종료코드
PARAM RATCHET · FAMILIES
밖    **억제가 정당한가는 안 본다.** `# noqa: BLE001` 이 옳은 자리인지, 그
      `<!--stale-ok-->` 가 진짜 옛 인용인지는 사람이 본다. 여기가 드는 것은
      「몇 개인가」와 「늘었는가」 둘뿐이다.
      **사유 딸린 면제표(`EXEMPT` · `ci-exempt` · pytest skip)는 안 센다** —
      그쪽은 각자의 강제자가 사유를 형식으로 강제하고 죽은 면제까지 잡는다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 2026-09-28 실측 119 → **57**. 같은 날 `noqa` 59개를 지우고 시작한다.
#:
#: ★ 지운 59개는 **어느 룰셋에도 없는 규칙 이름**을 적고 있었다(`ruff --extend-select
#:   RUF100` 을 기본·엄격 두 설정으로 돌려 교집합을 냈다). 아무것도 안 막으면서
#:   「검사를 통과시켰다」고 보이는 주석이고, `eslint` 가 없는데 있던
#:   `eslint-disable-line` 28개와 **같은 병**이다(§279-4).
#:
#: ★ **사유가 붙은 12개는 남겼다.** 규칙이 꺼져 있어도 「이 blind except 는
#:   일부러다」라는 말은 값이 있다. 지우면 그 말이 사라진다.
#:
#: ★ 규칙을 **켜는 쪽**이 더 낫다. 실측 — `BLE001` 28 · `PLC0415` 526 ·
#:   `S603` 83 · `E402` 39 · `ARG001` 23 · `E731` 4 가 억제 없이 걸린다.
#:   526 짜리를 오늘 켤 수는 없다. 수를 여기 적어 두는 것이 다음 배치의 입구다.
#: **줄기만 한다.**
RATCHET = 57

#: `tools/ratchet.py` 가 **줄었을 때만** 이 수를 고쳐 적는다(§309).
#: **느는** 쪽은 안 쓴다 — 그것은 받아적을 일이 아니라 결함이다.
RATCHETS = {"RATCHET": "down"}


def ratchet_values() -> dict[str, int]:
    """사유 없는 억제의 지금 수. **판정은 `check()` 소관**이다."""
    return {"RATCHET": sum(len(v) for v in tally().values())}


#: 갈래 → (무엇을 보나, 어디를 보나, 사유가 붙었는지 가르는 패턴)
#: 사유 = 억제 뒤에 오는 **말**. 있으면 안 센다.
FAMILIES: dict[str, tuple[re.Pattern, tuple[str, ...], tuple[str, ...]]] = {
    # 「noqa: RULE」 뒤에 아무 말도 없으면 사유가 없는 것이다.
    "noqa": (re.compile(r"#\s*noqa(?::\s*[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)?(?P<why>.*)$"),
             ("src", "tools", "tests"), ("*.py",)),
    # `# type: ignore[code]` — 같은 규칙.
    "type-ignore": (re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(?P<why>.*)$"),
                    ("src", "tools", "tests"), ("*.py",)),
    # `// eslint-disable-next-line rule -- 사유` — `--` 뒤가 eslint 의 사유 규약이다.
    "eslint": (re.compile(r"eslint-disable(?:-next-line|-line)?\s+\S+(?P<why>.*)$"),
               ("web/navi/src", "web/navi/test"), ("*.ts", "*.tsx")),
    # 문서 표기 둘. 줄 끝 표기라 뒤에 말이 붙을 자리가 없다 — 전부 센다.
    "voice-ok": (re.compile(r"<!--voice-ok-->(?P<why>)"), ("docs", "."), ("*.md", "*.py")),
    "stale-ok": (re.compile(r"<!--stale-ok-->(?P<why>)"), ("docs", "."), ("*.md",)),
}

#: 사유로 안 치는 꼬리 — 규칙 이름을 한 번 더 적은 것 따위.
_NOISE = re.compile(r"^[\s:,\-]*$")


def _files(roots: tuple[str, ...], globs: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for r in roots:
        base = ROOT / r
        if not base.is_dir():
            continue
        for g in globs:
            it = base.glob(g) if r == "." else base.rglob(g)
            out += [p for p in it
                    if "node_modules" not in p.parts and ".venv" not in p.parts]
    return sorted(set(out))


def hits(name: str) -> list[tuple[str, int, str]]:
    """그 갈래에서 **사유 없이** 끈 자리 (경로, 줄, 글)."""
    rx, roots, globs = FAMILIES[name]
    out = []
    for p in _files(roots, globs):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = rx.search(line)
            if m and _NOISE.match(m.group("why") or ""):
                out.append((p.relative_to(ROOT).as_posix(), i, line.strip()[:90]))
    return out


def tally() -> dict[str, list]:
    return {k: hits(k) for k in FAMILIES}


def check() -> int:
    t = tally()
    n = sum(len(v) for v in t.values())
    wide = max(len(k) for k in FAMILIES)
    for k, v in t.items():
        print(f"  {k:<{wide}}  {len(v):>4}")
    print(f"  {'합계':<{wide}}  {n:>4}   래칫 {RATCHET}")
    if n > RATCHET:
        print(f"\n✗ 사유 없는 억제가 {n} — 기록 {RATCHET} 보다 늘었다")
        print("  억제는 **검사를 끄는 것**이다. 끈 이유를 안 적으면 다음 사람은")
        print("  그것이 옳은지 알 수가 없고, 그러면 영영 안 지워진다.")
        print("  둘 중 하나를 해라 — ① 억제를 지우고 코드를 고친다")
        print("                      ② 억제 뒤에 사유를 한 줄 적는다")
        return 1
    if n < RATCHET:
        print(f"\n✗ 사유 없는 억제가 {n} 으로 줄었다 — "
              f"{__file__} 의 RATCHET 을 {n} 으로 조여라")
        print("  느슨해진 래칫은 초록으로 위장한다(`sizecheck` 머리말과 같은 사유).")
        return 1
    print(f"\n✓ 사유 없는 억제 {n} = 래칫 {RATCHET}")
    return 0


def selftest() -> int:
    """★ 사유가 있는 것과 없는 것을 실제로 가르는가. 빈 그물이 아닌가."""
    bad = []
    if not FAMILIES:
        bad.append("`FAMILIES` 가 비었다 — 볼 것이 없으면 통과가 아니다")

    def one(name: str, line: str) -> bool:
        rx = FAMILIES[name][0]
        m = rx.search(line)
        return bool(m) and bool(_NOISE.match(m.group("why") or ""))

    cases = [
        ("noqa", "x = 1  # noqa: BLE001", True, "사유 없는 noqa 를 안 센다"),
        ("noqa", "x = 1  # noqa: BLE001  아래에서 보고한다", False, "사유 붙은 noqa 를 센다"),
        ("noqa", "x = 1  # noqa", True, "규칙 없는 맨 noqa 를 안 센다"),
        ("noqa", "x = 1  # 평범한 주석", False, "평범한 주석을 억제로 센다"),
        ("type-ignore", "y: int = z  # type: ignore[assignment]", True, "사유 없는 type:ignore 를 안 센다"),
        ("type-ignore", "y: int = z  # type: ignore -- 상류 스텁이 틀렸다", False,
         "사유 붙은 type:ignore 를 센다"),
        ("eslint", "// eslint-disable-next-line react-hooks/exhaustive-deps", True,
         "사유 없는 eslint 억제를 안 센다"),
        ("eslint", "// eslint-disable-next-line react-hooks/exhaustive-deps -- ref 다", False,
         "사유 붙은 eslint 억제를 센다"),
        ("voice-ok", "<!--voice-ok-->", True, "voice-ok 를 안 센다"),
        ("stale-ok", "| 21 | 266/1,101 | <!--stale-ok-->", True, "stale-ok 를 안 센다"),
    ]
    for fam, line, want, why in cases:
        if one(fam, line) is not want:
            bad.append(why + f" — {line!r}")
    # ★ 실물에서 한 갈래라도 0 이면 그 패턴이 죽었을 수 있다. 0 자체는 결함이
    #   아니지만 **전부 0 이면** 그물이 비었다는 뜻이다.
    if sum(len(v) for v in tally().values()) == 0:
        bad.append("실물에서 하나도 안 잡힌다 — 패턴이 실물과 갈렸다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 갈래 {len(FAMILIES)}개가 사유 있는 것과 없는 것을 가른다")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사유 없는 억제 래칫")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.list:
        for k, v in tally().items():
            print(f"\n── {k}  {len(v)}")
            for f, ln, s in v:
                print(f"    {f}:{ln}  {s}")
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())

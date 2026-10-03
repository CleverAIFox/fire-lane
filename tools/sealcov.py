#!/usr/bin/env python3
"""
sealcov.py — 봉인이 **코드의 몇 할**을 덮는가. 덮임의 분모.

    uv run python tools/sealcov.py            덮임
    uv run python tools/sealcov.py --list     아직 아무 절도 안 지목한 파일
    uv run python tools/sealcov.py --selftest 분모 셈이 살아 있나

── 왜 생겼나 (DECISIONS §384) ──────────────────────────────────
`docseal` 은 **절**을 센다 — 「250/250 유효」. 그런데 그 수가 답하는 물음은
「찍은 절이 그대로인가」이고, 사람이 묻고 싶은 것은 **「코드의 어디까지
감사됐나」**다. 둘은 분모가 다르다.

절 하나가 파일 스물을 지목할 수도, 하나도 안 지목할 수도 있다. 절을 아무리
채워도 **아무 절도 안 쳐다본 파일**은 그대로 남고, `docseal` 은 그것을 모른다 —
모르는 것이 아니라 **그 물음을 안 든다.**

★ 「감사됨」을 이렇게 정의한다: **손으로 쓴 코드 파일 중, 어떤 절의 본문이
  그 경로를 지목한 것.** 강제자 칸은 안 센다 — 그 칸은 「누가 지킨다」를
  적는 자리지 「읽고 판단했다」가 아니다(§348 이 도장에서 든 같은 구분).

IN    docs/*.md 의 절 본문 · git 추적 목록
OUT   없음 (검사)
PARAM SEALED_FILES (래칫 · 올라가는 쪽)
밖    **절이 옳은가는 안 본다.** 그 파일을 지목한 절이 그 파일을 제대로
      설명하는지는 이 도구가 모른다 — `docseal` 이 「찍은 뒤로 안 바뀌었나」를,
      `dms verify` 가 「죽은 참조가 없나」를 따로 든다. 여기가 드는 것은
      **덮임 하나**다. 그리고 **생성물과 자료는 분모가 아니다** — 사람이
      읽고 판단할 대상이 아니기 때문이다.
"""
from __future__ import annotations

import argparse
import functools
import sys
from pathlib import Path

import docseal as D  # 정본은 docseal 이다 — 두 번째 파서를 안 만든다

ROOT = Path(__file__).resolve().parents[1]

#: 분모에 드는 확장자. 사람이 **읽고 판단할** 코드다.
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".sh")

#: 어떤 절의 본문도 안 지목한 코드 파일 수가 분모에서 빠진 뒤의 **덮인 수**.
#: **올라가는 쪽** — 덮임은 늘어나야 한다.
SEALED_FILES = 354

RATCHETS = {"SEALED_FILES": "up"}


@functools.lru_cache(maxsize=1)
def denominator() -> tuple[str, ...]:
    """손으로 쓴 코드 파일 전수. 생성물은 뺀다 — 읽고 판단할 대상이 아니다."""
    return tuple(sorted(p for p in D._tracked()
                        if p.endswith(CODE_EXT) and not D._generated(p)))


@functools.lru_cache(maxsize=1)
def covered() -> frozenset[str]:
    """어떤 절의 **본문**이 지목한 파일. 강제자 칸은 `body(strip=True)` 가 뺀다."""
    rows = D._sections()
    out: set[str] = set()
    for i in range(len(rows)):
        out.update(D.refs(D.body(rows, i)))
    return frozenset(out)


@functools.lru_cache(maxsize=1)
def survey() -> dict:
    """분모 · 덮임 · 빈 곳. **판정은 안 한다**(`show()` 소관)."""
    den = denominator()
    cov = covered() & set(den)
    gap = sorted(set(den) - cov)
    by: dict[str, int] = {}
    for p in gap:
        key = str(Path(p).parent) if "/" in p else "(루트)"
        by[key] = by.get(key, 0) + 1
    return {"분모": len(den), "덮임": len(cov), "빈 곳": gap,
            "묶음별 빈 곳": dict(sorted(by.items(), key=lambda kv: -kv[1]))}


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. **0 을 내지 않는다.**

    분모가 비면 `RuntimeError` 다 — 0 은 「덮인 것이 없다」는 뜻이고, 그것을
    선언에 적으면 올라가는 쪽 래칫이 **영원히 통과**한다(§313-1 과 반대 방향의
    같은 족).
    """
    s = survey()
    if not s["분모"]:
        raise RuntimeError("분모가 0 이다 — 추적 목록을 못 물었다(§372)")
    return {"SEALED_FILES": s["덮임"]}


def show(s: dict, listing: bool) -> int:
    den, cov = s["분모"], s["덮임"]
    pct = cov / den * 100 if den else 0.0
    print(f"── 봉인 덮임  **{cov} / {den}**  ({pct:.1f}%) · 래칫 {SEALED_FILES}")
    print("   「감사됨」 = 손으로 쓴 코드 파일 중 **어떤 절의 본문이 지목한 것**")
    print("   강제자 칸은 안 센다 — 「누가 지킨다」지 「읽고 판단했다」가 아니다")

    print(f"\n  아직 아무 절도 안 쳐다본 곳 {len(s['빈 곳'])} — 묶음별")
    for k, n in s["묶음별 빈 곳"].items():
        print(f"    {k:<28} {n:>4}")
    if listing:
        print("\n  목록")
        for p in s["빈 곳"]:
            print(f"    {p}")
    else:
        print("\n  (`--list` 로 전부)")

    print("\n★ **절이 옳은가는 안 본다.** 덮임 하나를 든다.")
    if cov < SEALED_FILES:
        print(f"\n✗ 덮임 {cov} < 래칫 {SEALED_FILES} — **땅이 줄었다.**")
        print("  절을 지웠거나 파일을 늘렸다. 둘 다 덮임을 되돌린다.")
        return 1
    if cov > SEALED_FILES:
        print(f"\n✗ 덮임 {cov} > 래칫 {SEALED_FILES} — "
              f"**래칫을 {cov} 로 올려라.** 안 올리면 되돌아간다.")
        return 1
    return 0


def selftest() -> int:
    """★ 분모와 덮임이 **양방향으로** 맞는가."""
    bad = []
    den = denominator()
    if not den:
        bad.append("분모가 비었다 — 추적 목록을 못 물었다")
    if any(not p.endswith(CODE_EXT) for p in den):
        bad.append("분모에 코드가 아닌 것이 들었다")
    if any(D._generated(p) for p in den):
        bad.append("분모에 생성물이 들었다 — 읽고 판단할 대상이 아니다")
    # 이 파일 자신은 코드이고 추적되므로 분모에 있어야 한다.
    me = "tools/sealcov.py"
    if (ROOT / me).is_file() and me not in den and me in D._tracked():
        bad.append(f"{me} 가 분모에 없다 — 분모 규칙이 제 파일을 뺀다")

    s = survey()
    if s["덮임"] + len(s["빈 곳"]) != s["분모"]:
        bad.append(f"덮임 + 빈 곳 ≠ 분모 — {s['덮임']} + {len(s['빈 곳'])} "
                   f"≠ {s['분모']}")
    if not 0 <= s["덮임"] <= s["분모"]:
        bad.append("덮임이 분모 밖이다")
    if sum(s["묶음별 빈 곳"].values()) != len(s["빈 곳"]):
        bad.append("묶음별 합이 빈 곳 수와 다르다")
    # 덮인 것 중 하나는 실제로 추적되는 파일이어야 한다.
    if s["덮임"] and not (set(denominator()) & covered()):
        bad.append("덮였다는데 교집합이 비었다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 분모 {s['분모']} · 덮임 + 빈 곳 = 분모 · 생성물 제외")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="빈 곳 전부")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return show(survey(), a.list)


if __name__ == "__main__":
    sys.exit(main())

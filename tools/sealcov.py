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
# ★ 2026-10-05. 360 → 359. `tools/mutate.py` 를 이 배치에서 뺐다 — §396-4 가 지목하던 파일 하나가 같이 빠졌다
# ★ 2026-10-05. 359 → 362 (DECISIONS §398 · §399). 이 배치가 새로 덮은 것들이다.
# #   중간에 363 을 거쳤는데 그 하나는 새로 짰다 지운 모듈이었다 — **이미 있는
#   도구를 다시 짰다가 지운 파일**이고(§399-2), 지우면서 덮임도 같이 돌아왔다.
#   받아적지 않고 손으로 내린다: 느슨해진 것이 아니라 **세던 것이 없어졌다.**
# ★ 2026-10-06 (DECISIONS §411 · PLAN #154). 363 → 383. **내비 도메인 스무 파일**이다.
#   안 쳐다본 129칸 중 과반이 화면 쪽이었고, 그 안에 경로를 고르는 판단이 있었다 —
#   §407 이 그 자리에서 결함을 하나 꺼냈다(라우터가 모르는 구간을 싸게 쳤다).
# ★ 2026-10-08 (DECISIONS §432 · §431-6). 393 → 428. **검사·도구·기반 27**을
#   읽어 절로 적었고(§432), 쪼개서 생긴 새 집 여덟도 같은 판에서 덮었다(§431-6).
#   ★ 분모가 498 → 506 으로 는 것은 그 여덟이다. 그리고 `docseal.PATH` 가
#     선두 `.` 을 못 읽어 `.devcontainer/` · `.githooks/` 는 **덮일 수 없다** —
#     분모에 앉아 있는데 길이 없다. 고치면 **지문 공식이 바뀌어 120절이**
#     **무효**가 되므로 이 판에서 안 고쳤다. `PLAN #163` 이 든다.
#   ★ 2026-10-08 (DECISIONS §433). 426 → **430.** 새 집 둘(`contract_crs` ·
#     `rawcache`)과 머리말을 받은 0바이트 둘(`seg/__init__` · `krgis/__init__`)이다.
#     분모도 506 → 508 로 는다 — 새 집 둘이 거기 들어간다.
SEALED_FILES = 492

RATCHETS = {"SEALED_FILES": "up"}


@functools.lru_cache(maxsize=1)
def denominator() -> tuple[str, ...]:
    """손으로 쓴 코드 파일 전수. 생성물은 뺀다 — 읽고 판단할 대상이 아니다."""
    return tuple(sorted(p for p in D._tracked()
                        if p.endswith(CODE_EXT) and not D._generated(p)))


@functools.lru_cache(maxsize=1)
def covered() -> frozenset[str]:
    """어떤 절의 **본문**이 지목한 파일.

    ★ 2026-10-08 (DECISIONS §438-6 · PLAN #165). 종전 이 한 줄은 「강제자 칸은
      `body(strip=True)` 가 뺀다」고 적었다. **거짓이다** — `strip` 은 끝의 빈
      줄을 떼는 깃발이고(§273-10 의 `_body_v1`) 강제자 칸과 아무 상관이 없다.
      실측: 강제자 칸이 경로를 적는 절 778 중 **761 에서 그 글자가 본문 안에
      있다.** 그러니 칸에 적힌 도구가 **읽힌 것으로 세어진다.**

    ★ 아무도 안 울었다. 그 전제를 지킨다는 시험은 「덮임 < 분모 × 0.95」라는
      **비율**을 봤고, 비율은 전제를 안 묻는다. 오늘 `#154` 가 덮임을 95.1% 로
      올리자 그 줄이 **좋은 일에** 울었다 — 그때 읽고 알았다.

    ★ **이 판은 수를 안 바꾼다.** 고치면 덮임이 489 → 450 으로 내려가고 그것은
      래칫의 「오르는 쪽」을 거스르는 큰 이사다. 부풀림 39 를
      `tests/test_sealcov.py` 가 **래칫으로 들고** `PLAN #165` 가 닫는다 —
      수를 아는 채로 두는 쪽이 모르고 초록인 쪽보다 낫다(§286).
    """
    rows = D._sections()
    out: set[str] = set()
    for i in range(len(rows)):
        out.update(D.refs(D.body(rows, i)))
    return frozenset(out)


def prose_only() -> frozenset[str]:
    """**산문만**이 지목한 파일 — 강제자 칸을 뺀다. `covered()` 의 짝이다.

    ★ 칸 글자를 본문에서 빼고 다시 긁는다. 칸을 **따로 긁어 차집합**하는 쪽은
      안 쓴다 — 같은 파일을 산문과 칸이 둘 다 적은 절이 있고, 그 파일은
      **산문이 들었으므로** 산문 쪽에 남아야 한다.
    """
    rows = D._sections()
    out: set[str] = set()
    for i, r in enumerate(rows):
        b, f = D.body(rows, i), (r.get("field") or "")
        out.update(D.refs(b.replace(f, " ") if f and f in b else b))
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

    # ── 아래 둘은 **돌연변이 측정이 시킨 문**이다 (DECISIONS §438-6)
    # ★ `붙잡이` 가 이 도구에서 **자기검사 하나**다(§435 가 그 약함을 선언했다).
    #   그래서 pytest 에 시험을 세워도 돌연변이는 안 죽는다 — 문은 **여기** 달아야
    #   한다. §435-9 가 `segcontract` 에 같은 문을 달았고 같은 사유다.
    if ratchet_values()["SEALED_FILES"] != SEALED_FILES:
        bad.append(f"래칫 선언 {SEALED_FILES} ≠ 실측 "
                   f"{ratchet_values()['SEALED_FILES']} — 선언이 낡았다")

    # ★ 찍는 백분율은 **찍는 두 수에서 유도된다.** `cov/den*100` 의 `100` 을
    #   흔들어도 아무도 안 울었다 — 사람이 읽는 유일한 수가 그것이고, 1% 틀린
    #   백분율은 「넘었다」와 「안 넘었다」를 뒤집는다(이 절의 사고가 그 자리다).
    import contextlib  # noqa: PLC0415  자기검사 전용
    import io  # noqa: PLC0415  자기검사 전용

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        show(s, listing=False)
    shown = buf.getvalue()
    want = s["덮임"] / s["분모"] * 100 if s["분모"] else 0.0
    if f"({want:.1f}%)" not in shown:
        bad.append(f"찍힌 백분율이 {want:.1f}% 가 아니다 — 두 수와 유도가 갈렸다")
    if f"**{s['덮임']} / {s['분모']}**" not in shown:
        bad.append("두 수를 그대로 안 찍는다")

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

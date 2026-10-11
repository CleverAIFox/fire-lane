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
#   ★ 2026-10-09 (DECISIONS §444 · PLAN #142). 494 → **488.** 내려가는 쪽이고,
#     사유는 **파일이 은퇴한 것**이다 — docx·pdf 를 들어내며 도구 일곱과 시험
#     셋이 지워졌고 **그 열 중 여섯이 감사돼 있었다.** 분모도 519 → 513 으로
#     같이 줄었다 — 실측 덮임률 95.2% → **95.1%** 다. 거의 같다: 지운 것이
#     분자와 분모에 나란히 들어 있었다는 뜻이고, 그래서 이 하락은 **땅을
#     잃은 것이 아니다.**
#     ★ `ratchet --write` 는 이 수를 **안 쓴다** — 느슨해지는 쪽을 자동으로
#       받아적으면 관문이 죽는다. 사람이 사유를 적고 내린다. 지운 파일이
#       아니라 **안 읽은 파일**이 생겨 줄었다면 그것은 결함이다.
#     ★ 남은 25는 전부 `web/navi/src/ui` · `components` · `src` 다 — `#143`
#       (관제 화면이 너무 많이 보여준다)이 그 층을 읽는 판에서 같이 간다.
#     ★ 2026-10-09 (DECISIONS §445 · PLAN #143). 490 → 489 → 495. 먼저 손으로
#       내렸고(`Manual.tsx` 은퇴) 그다음 이 판이 건드린 파일을 절이 지목해 올랐다.
#     ★ 2026-10-10 (DECISIONS §446 · PLAN #165 · #154 닫힘). 495 → **519 = 분모.**
#       두 움직임이 **한 판에서 같이** 났다 — ① 세는 법을 고쳐 강제자 칸을
#       뺐다(495 → 458. 칸은 「누가 지킨다」지 「읽었다」가 아니다) ② 그 짝으로
#       빈 곳 61 을 `MASTER §22` · `§23` 이 **읽고 적어** 덮었다(458 → 519).
#       `#165` 가 「안 그러면 수만 내려가고 덮임은 그대로다」라고 미리 적었고
#       그 둘을 같이 한 판이 이 판이다.
#     ★ 이제 **분모와 같다.** 파일이 하나 늘면 그날 빨갛다 — 그것이 옳은 빨강이다.
#     ★ 2026-10-10 (DECISIONS §449-3). 519 → **521.** 쪼개며 생긴 두 집
#       (`docnumtest` · `docnumtable`)을 `§449` 가 **읽고 적었다.** 분모와 같다.
#     ★ 2026-10-11 (DECISIONS §465 · PLAN #71 닫힘). 526 → **528 = 분모.** 새 집
#       둘(`tools/figures/route.py` · `web/navi/test/astarbench.test.ts`)이 들어왔고
#       `§465` 와 `MASTER §20-4` 가 **산문으로** 그 둘을 지목한다. 분모도 같이 는다.
#     ★ 2026-10-11 (DECISIONS §469). 528 → **529 = 분모.** 새 집 하나
#       (`src/firelane/localplane.py`)가 들어왔고 `§469` 가 **산문으로** 지목한다.
#     ★ 2026-10-11 (DECISIONS §470 · PLAN #168). 529 → **530 = 분모.** 새 집 하나
#       (`tests/test_handrolled.py` — 손으로 짠 자리의 분모)가 들어왔고 `§470` 이
#       **산문으로** 지목한다.
#     ★ 2026-10-11 (DECISIONS §471). 530 → **532 = 분모.** 새 집 둘 —
#       `src/firelane/quantile.py`(분위수 정본)와 `tests/test_quantile.py`
#       (그 정본이 pandas 와 같은가 · 옛 손 색인을 심어 자를 민다). `§471` 이
#       **산문으로** 둘을 지목한다.
#     ★ 2026-10-11 (DECISIONS §472). 532 → **533 = 분모.** 새 집 하나
#       (`src/firelane/emwidth.py` — 글자 폭 어림의 집)이 들어왔고 `§472` 가
#       **산문으로** 지목한다.
#     ★ 2026-10-11 (DECISIONS §473). 533 → **534 = 분모.** 새 집 하나
#       (`tests/test_localplane.py` — 국소 평면 상수를 `pyproj` 로 재는 자리)가
#       들어왔고 `§473` 이 **산문으로** 지목한다.
#     ★ 2026-10-11 (DECISIONS §474). 534 → **535 = 분모.** 새 집 하나
#       (`tools/srgb.py` — sRGB 감마·휘도·Lab·ΔE 공식의 집)이 들어왔고
#       `§474` 가 **산문으로** 지목한다.
#     ★ 2026-10-12 (DECISIONS §481). 535 → **538 = 분모.** 새 집 셋 —
#       `tests/test_docpatch.py` · `tests/test_pages_navi.py` ·
#       `tests/test_build_proposal.py`. **아무도 안 미는 관문** 다섯 중 셋을
#       갚은 자리이고 `§481` 이 셋을 **산문으로** 지목한다.
SEALED_FILES = 550

#: **강제자 칸만으로** 덮인 파일 수. 내려가는 쪽. 2026-10-10 실측 37 → **0**.
#: 늘면 「산문 없이 칸만 적었다」는 뜻이고 그것은 한 번 속은 자리다(PLAN #165).
ENFORCER_INFLATION = 0

RATCHETS = {"SEALED_FILES": "up", "ENFORCER_INFLATION": "down"}


@functools.lru_cache(maxsize=1)
def denominator() -> tuple[str, ...]:
    """손으로 쓴 코드 파일 전수. 생성물은 뺀다 — 읽고 판단할 대상이 아니다."""
    return tuple(sorted(p for p in D._tracked()
                        if p.endswith(CODE_EXT) and not D._generated(p)))


@functools.lru_cache(maxsize=1)
def covered() -> frozenset[str]:
    """어떤 절의 **산문**이 지목한 파일. 강제자 칸은 안 센다.

    ★ 2026-10-10 (DECISIONS §446 · PLAN #165 닫힘). 종전에는 본문 전체를
      긁었고 **강제자 칸이 본문 안에 있다.** 그래서 칸에 이름이 적힌 도구가
      「읽고 판단했다」로 세어졌다 — 실측 37 파일이 그 꼴이었다. 칸의 뜻은
      「누가 지킨다」이고 이 수가 묻는 것은 「누가 **읽었다**」다. 둘은 다르다.

    ★ **재는 자리를 하나로 둔다**(§445). 이 함수는 `prose_only()` 를 그대로
      돌려준다 — 둘을 따로 구현하면 같은 물음에 두 답이 생긴다(족 2).

    ★ 고치자 덮임이 495 → **458** 로 내려갔다. 래칫의 「오르는 쪽」을 거스르는
      이사라 `#165` 가 「사유를 적고 한 판을 따로 받는다」고 미리 적어 두었다.
      그 판이 이 판이고, **짝으로 61 파일을 산문으로 덮는다** — 안 그러면
      수만 내려가고 읽힌 것은 그대로다.
    """
    return prose_only()


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
def body_refs() -> frozenset[str]:
    """본문 **전체**(강제자 칸 포함)가 지목한 파일. 부풀림을 재는 데만 쓴다."""
    rows = D._sections()
    out: set[str] = set()
    for i in range(len(rows)):
        out.update(D.refs(D.body(rows, i)))
    return frozenset(out)


def inflation() -> frozenset[str]:
    """**강제자 칸만으로** 덮인 파일 — 산문은 그 파일을 한 번도 안 지목했다.

    ★ 2026-10-10 (DECISIONS §446 · PLAN #165 닫힘). 종전에는 이것이 덮임에
      섞여 있었다. 칸의 뜻은 「누가 지킨다」이고 이 수가 묻는 것은 「누가
      **읽었다**」다 — 섞으면 읽히지 않은 파일이 감사된 것으로 세어진다.
      실측 37 이었고 이 판이 **0 으로** 내렸다(§22 · §23 이 산문으로 덮었다).

    ★ **내려가는 쪽.** 늘면 「산문 없이 칸만 적었다」는 뜻이고, 그것은 이
      저장소가 한 번 속은 자리다.
    """
    den = set(denominator())
    return frozenset((body_refs() & den) - (covered() & den))


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
    return {"SEALED_FILES": s["덮임"], "ENFORCER_INFLATION": len(inflation())}


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

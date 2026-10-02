#!/usr/bin/env python3
"""
toolindex.py — **도구 목록의 정본은 도구 자신이다.**

    uv run python tools/toolindex.py            전수 색인 (사람이 읽는다)
    uv run python tools/toolindex.py --check    판정 (verify.sh · CI)
    uv run python tools/toolindex.py --missing  한 줄 머리말이 없는 것만
    uv run python tools/toolindex.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-10-02 (DECISIONS §352). `README.md` 가 도구 목록을 **네 블록**으로
  들고 있었고 합쳐 689줄 중 240줄이었다. 그 목록의 강제자는
  `test_every_tool_is_named_in_readme` 하나였는데, 그것이 문는 것은
  「`tools/` 의 파일 이름이 README **문자열 안에** 있는가」뿐이다 —
  **설명이 맞는지는 아무도 안 봤다.** 그래서 설명은 자유롭게 낡았다.

  그리고 같은 사실이 두 벌이었다. 2026-09-24 (§243) 에 그 사본이 아홉 갈려
  있는 것을 잡고 「목록의 집은 README 하나」로 정했는데, **집을 하나로 정한
  것이지 사본을 없앤 것이 아니다.** 도구가 111개면 설명도 111벌이고,
  그중 110벌이 이미 **도구 자신의 머리말 첫 줄**에 있었다.

      tools/sizecheck.py — **파일이 얼마나 긴가.** 양방향 래칫이다.
      ─────────────────   ───────────────────────────────────────
      이름                 설명

  문서가 그것을 베낄 이유가 없다. **베끼면 갈린다**(2족).

★ 그래서 이 도구는 목록을 **만들지 않는다. 읽는다.** 정본은 파일이고
  여기는 렌더러다 — `tools/render_workflow.py` 가 MASTER §12 에 대해 하는
  일과 같은 자리다.

── 꼴 ────────────────────────────────────────────────────────
머리말의 **첫 비어 있지 않은 줄**이 아래여야 한다.

    <파일이름> — <한 줄>          `tools/` 접두사는 붙여도 된다

`.py` 는 모듈 독스트링, `.sh` · `.mjs` 는 `#!` 뒤 첫 주석 덩어리의 첫 줄이다.

── 판정 ──────────────────────────────────────────────────────
    한 줄 머리말이 없거나 꼴이 틀렸다      실패 — 그 도구가 제 이름을 안 댄다
    이름이 파일 이름과 다르다              실패 — **복사해 만든 자국이다**
    설명이 비거나 너무 짧다                실패
    도구가 0개다                           실패 — 빈 그물(MASTER §17-0 ③)
    설명이 다른 도구와 글자 그대로 같다     실패 — 둘 중 하나가 남의 설명이다

★ 마지막이 이 도구가 **README 보다 강한** 자리다. 종전 강제자는 이름이
  문자열 안에 있기만 하면 통과했으므로, 설명이 틀려도 · 비어도 · 남의 것을
  복사해도 초록이었다.

IN    tools/*.py · *.sh · *.mjs
OUT   표준출력 (색인 또는 판정)
PARAM MIN_DESC
밖    **설명이 참인지는 안 본다.** 기계가 읽을 수 없다 — 그 자리는 도장
      (`tools/docseal.py`)과 사람이 든다. 여기가 드는 것은 「도구마다 제
      설명이 **한 벌** 있는가」다.
      **배선은 안 본다**(`tests/test_tools_are_wired.py` 소관) ·
      **인자도 안 본다**(`tools/argcheck.py` 소관) ·
      `src/firelane/` 의 모듈도 안 본다(`tools/` 만이 우주다).
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SUFFIX = (".py", ".sh", ".mjs")

#: 설명이 이보다 짧으면 설명이 아니다. 「임시」 · 「도구」 같은 한 낱말을 막는다.
MIN_DESC = 8

#: 머리말 첫 줄의 꼴. 긴 대시 · 짧은 대시 · 하이픈을 다 받는다.
HEAD = re.compile(r"^(?:tools/)?(?P<name>[\w.\-]+\.(?:py|sh|mjs))\s*[—–-]\s*(?P<desc>\S.*)$")


def tools() -> list[Path]:
    """우주 — `tools/` 의 실행물. **`src/` 는 안 본다**(머리말 `밖`)."""
    return [p for p in sorted(TOOLS.iterdir()) if p.is_file() and p.suffix in SUFFIX]


def head_line(p: Path) -> str:
    """그 파일이 제 머리에 적은 **첫 줄**. 못 읽으면 빈 문자열."""
    text = p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix == ".py":
        try:
            doc = ast.get_docstring(ast.parse(text))
        except SyntaxError:
            return ""
        return next((x.strip() for x in (doc or "").splitlines() if x.strip()), "")
    for line in text.splitlines()[:12]:
        if line.startswith("#!"):
            continue
        got = line.lstrip("#").strip()
        if got:
            return got
        if line.strip():          # 주석이 아닌 줄을 만났다 — 머리말이 끝났다
            break
    return ""


def entry(p: Path) -> tuple[str, str] | None:
    """`(이름, 설명)`. 꼴이 틀리면 None — **판정은 `judge` 가 한다**."""
    m = HEAD.match(head_line(p))
    if not m or m.group("name") != p.name or len(m.group("desc")) < MIN_DESC:
        return None
    return p.name, m.group("desc")


def registry() -> dict[str, str]:
    """이름 → 한 줄. 꼴이 틀린 것은 빠진다(`judge` 가 그것을 센다)."""
    out = {}
    for p in tools():
        if e := entry(p):
            out[e[0]] = e[1]
    return out


def _plain(s: str) -> str:
    """굵기·백틱을 벗긴 비교용 꼴. 꾸밈만 다른 사본을 같게 본다."""
    return re.sub(r"[\s*`★]+", " ", s).strip().lower()


def judge(all_tools: list[Path] | None = None) -> list[str]:
    """실패 사유들. 빈 리스트면 초록."""
    ts = tools() if all_tools is None else all_tools
    if not ts:
        return ["`tools/` 에서 도구를 하나도 못 찾았다 — **빈 그물**(MASTER §17-0 ③)"]

    bad, seen = [], {}
    for p in ts:
        got = head_line(p)
        m = HEAD.match(got)
        if not got:
            bad.append(f"{p.name}: 머리말 첫 줄이 없다")
        elif not m:
            bad.append(f"{p.name}: 머리말 첫 줄이 「<이름> — <한 줄>」 꼴이 아니다 — {got[:50]!r}")
        elif m.group("name") != p.name:
            bad.append(f"{p.name}: 머리말이 제 이름이 아니라 `{m.group('name')}` 을 댄다 "
                       "— **복사해 만든 자국이다**")
        elif len(m.group("desc")) < MIN_DESC:
            bad.append(f"{p.name}: 설명이 {len(m.group('desc'))}자뿐이다 (최소 {MIN_DESC})")
        else:
            key = _plain(m.group("desc"))
            if key in seen:
                bad.append(f"{p.name}: 설명이 `{seen[key]}` 과 글자 그대로 같다 "
                           "— 둘 중 하나가 남의 설명이다")
            seen[key] = p.name
    return bad


# ── 색인 ────────────────────────────────────────────────────────
def show() -> None:
    reg = registry()
    print(f"도구 {len(tools())} · 한 줄 머리말 {len(reg)}\n")
    for name, desc in reg.items():
        print(f"  {name:<24} {desc}")


def show_missing() -> None:
    gaps = [p.name for p in tools() if entry(p) is None]
    print(f"한 줄 머리말이 없거나 꼴이 틀린 것 {len(gaps)}")
    for n in gaps:
        print(f"   {n}")


# ── 자기검사 ────────────────────────────────────────────────────
def selftest(tmp=None) -> int:
    """판별식 — 합성 트리로 잰다. 실물 수에 안 매인다."""
    import tempfile
    d = Path(tmp or tempfile.mkdtemp())

    def put(name: str, head: str) -> Path:
        q = d / name
        q.write_text(f'"""{head}\n\n본문\n"""\n' if name.endswith(".py")
                     else f"#!/usr/bin/env bash\n# {head}\n", encoding="utf-8")
        return q

    ok_p = put("good.py", "good.py — 제 이름을 제대로 댄다")
    sh_p = put("good.sh", "good.sh — 셸도 같은 꼴이다")
    pre_p = put("pre.py", "tools/pre.py — 접두사를 붙여도 된다")
    no_p = d / "nohead.py"
    no_p.write_text("x = 1\n", encoding="utf-8")          # 독스트링이 아예 없다
    wrong_p = put("wrong.py", "other.py — 남의 이름을 댄다")
    short_p = put("short.py", "short.py — 짧다")
    dup_p = put("dup.py", "dup.py — 제 이름을 제대로 댄다")

    ok: list[tuple[str, bool]] = [
        ("바른 꼴을 받는다", judge([ok_p]) == []),
        ("셸도 같은 꼴이다", judge([sh_p]) == []),
        ("`tools/` 접두사를 받는다", judge([pre_p]) == []),
        ("머리말이 없으면 빨강", any("첫 줄이 없다" in b for b in judge([no_p]))),
        ("꼴이 틀리면 빨강", any("꼴이 아니라" in b or "꼴이 아니다" in b
                              for b in judge([put("shape.py", "제 이름을 안 댄다 그냥 산문")]))),
        ("남의 이름을 대면 빨강", any("복사해 만든" in b for b in judge([wrong_p]))),
        ("설명이 짧으면 빨강", any("설명이" in b for b in judge([short_p]))),
        ("같은 설명 둘이면 빨강", any("남의 설명" in b for b in judge([ok_p, dup_p]))),
        ("빈 그물이면 빨강", judge([]) != []),
        ("꾸밈만 다른 사본도 잡는다",
         any("남의 설명" in b for b in judge([ok_p, put("deco.py", "deco.py — **제 이름을** 제대로 댄다")]))),
        ("entry 가 꼴 틀린 것을 안 센다", entry(no_p) is None and entry(ok_p) is not None),
        # ★ 실물 — 여기가 죽으면 위 전부가 합성에서만 돈다
        ("실물 도구가 10개 이상이다", len(tools()) >= 10),
        ("실물 색인이 비지 않았다", len(registry()) >= 10),
        ("실물이 전부 제 이름을 댄다", judge() == []),
    ]
    for what, good in ok:
        print(f"   {'OK ' if good else '✗  '} {what}")
    fail = [w for w, g in ok if not g]
    print(f"\n판별식 {len(ok)} · 실패 {len(fail)}")
    return 1 if fail else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="도구 목록의 정본은 도구 자신이다")
    ap.add_argument("--check", action="store_true", help="판정 (verify.sh · CI)")
    ap.add_argument("--missing", action="store_true", help="한 줄 머리말이 없는 것만")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.missing:
        show_missing()
        return 0
    if not a.check:
        show()
        return 0

    bad = judge()
    print(f"도구 {len(tools())} · 한 줄 머리말 {len(registry())}")
    if bad:
        print("\n✗ 도구 색인")
        for b in bad:
            print(f"   {b}")
        print("\n  머리말 **첫 줄**을 이 꼴로 적어라 —")
        print("      <파일이름> — <한 줄>")
        print("  문서에 베껴 적지 마라. 목록의 정본은 도구 자신이다(DECISIONS §352).")
        return 1
    print("✓ 도구 색인")
    return 0


if __name__ == "__main__":
    sys.exit(main())

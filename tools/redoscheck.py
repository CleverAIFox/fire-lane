#!/usr/bin/env python3
r"""
redoscheck.py — 되짚기 폭발이 **구조로** 가능한 정규식을 센다.

    uv run python tools/redoscheck.py            전수
    uv run python tools/redoscheck.py --list     걸린 것의 자리
    uv run python tools/redoscheck.py --time     ★ 시간으로 재본다 (관문 아님)
    uv run python tools/redoscheck.py --selftest 판별식이 살아 있나

── 왜 생겼나 (DECISIONS §385) ──────────────────────────────────
§360 · §377 이 되짚기 폭발 넷을 **손으로** 찾아 고쳤다. 네 번째는 이렇게 쟀다 —

    ((?:[\\w.\\-\\[\\]]+ ?)+)   n=6 0.3ms · n=10 66ms · n=14 **16.9초** · n=18 안 끝남

그리고 §377 이 「정규식 스물넷 중 스물셋을 손으로 걸렀다. 구조로 좁히고
시간으로 판정하는 도구는 다음 배치다」라고 적고 끝났다. 그 다음 배치다.

★ **시간으로 판정하지 않는다.** 시간은 기계마다 다르고 CI 러너는 더 흔들린다.
  흔들리는 관문은 사람이 끄게 되고, 끄는 습관이 진짜 경보를 죽인다(§73).
  그래서 관문은 **구조**만 본다 — 되짚기가 폭발할 수 있는 모양인가.
  `--time` 은 사람이 눈으로 볼 때만 쓰는 곁가지이고 종료코드에 안 든다.

── 무엇을 폭발 가능한 모양으로 치나 (셋) ───────────────────────
    ① 모호한 겹친 수량자
       `( X+ 선택들 ) +` — 묶음 선두가 수량자 원자이고 **나머지가 전부 선택**인 꼴.
       그러면 한 입력을 여러 갈래로 나눌 수 있고 밖의 수량자가 그것을 전부 되짚는다.
       `(_[a-z0-9]+)*` 처럼 **반드시 먹는 구분자**가 있으면 갈래가 하나라 안 센다 —
       넓게 잡으면 멀쩡한 패턴이 열대여섯 걸리고 그러면 아무도 안 읽는다(§73).
    ② 겹치는 선택   `(a|a…)+` 꼴 — 같은 글자로 시작하는 선택지가 반복된다

★ 둘 다 **필요조건이지 충분조건이 아니다.** 이 모양이면 폭발할 수 **있고**,
  입력이 안 닿으면 안 터진다. 그래서 수를 **래칫**으로 잡고 「전부 고쳐라」라고
  하지 않는다 — 고칠 것인가는 사람이 그 자리를 보고 정한다.

IN    src/**/*.py · tools/**/*.py · tests/**/*.py 의 정규식 문자열
OUT   없음 (검사)
PARAM REDOS_SHAPES (래칫 · 내려가는 쪽)
밖    **안전한가는 안 말한다.** 걸리지 않은 정규식이 안전하다는 뜻이 아니다 —
      셋 밖의 모양으로도 폭발할 수 있다. 그리고 **입력이 닿는가도 안 본다**
      (그것은 사람이 그 호출부를 읽어야 안다).
      JS·TS 쪽은 분모가 아니다 — `web/navi` 는 `eslint` 가 따로 든다.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 분모. 파이썬 쪽만 본다 — JS·TS 는 `eslint` 가 든다.
ROOTS = ("src", "tools", "tests")

#: 되짚기가 폭발할 수 있는 구조 수. **문턱이 아니라 지금 수다.**
REDOS_SHAPES = 0

RATCHETS = {"REDOS_SHAPES": "down"}

#: 괄호를 안 품은 묶음 하나와 그 뒤의 수량자. `( BODY ) +` 꼴을 집는다.
# ★ `\)` 와 수량자 사이에 공백을 허용하면 안 된다. 정규식 안의 공백은
#   **리터럴**이라 `( … ) *` 의 `*` 는 묶음이 아니라 그 공백에 붙는다 —
#   허용했더니 멀쩡한 표 파서 둘이 걸렸다.
_GROUP_Q = re.compile(r"\((\?:)?([^()]*)\)([+*])")
#: 수량자가 붙은 원자 하나 — 문자군 · 이스케이프군 · 점.
_ATOM_Q = re.compile(r"^(?:\[(?:\\.|[^\]])*\]|\\[wWdDsS]|\.)[+*]")
#: 선택이어서 **건너뛸 수 있는** 조각.
_OPTIONAL = re.compile(r"^(?:\[(?:\\.|[^\]])*\]|\\[wWdDsS]|\\.|[^\\\[\]])[?*]")
#: ③ 겹치는 선택 — 같은 글자로 시작하는 선택지가 반복된다.
_ALT = re.compile(r"\(([^()|]{1,8})\|\1[^()]*\)[+*]")


def _ambiguous(body: str) -> bool:
    r"""묶음 본문이 **되짚기를 나눠 가질 수 있는가**.

    ★ 겹친 수량자가 전부 위험한 것이 아니다. `(_[a-z0-9]+)*` 는 반복마다
      `_` 를 **반드시** 먹어야 해서 한 입력을 나눌 길이 하나뿐이다 — 모호하지
      않고 폭발하지 않는다. 저장소의 멀쩡한 패턴 대부분이 이 꼴이라, 넓게
      잡으면 열일곱 건 중 열대여섯이 오탐이 되고 그러면 아무도 안 읽는다(§73).

    ★ 위험한 것은 **선두가 수량자 원자이고 나머지가 전부 선택인** 꼴이다.
      `[\w.\-\[\]]+ ?` 가 그것이다 — 공백이 선택이라 `aaaa` 를 `a|aaa` ·
      `aa|aa` · … 로 **여러 갈래로** 나눌 수 있고, 밖의 `+` 가 그 갈래를 전부
      되짚는다. §377 이 16.9초를 잰 바로 그 모양이다.
    """
    m = _ATOM_Q.match(body)
    if not m:
        return False                      # 선두가 반드시 먹는 글자다 — 구분자가 있다
    rest = body[m.end():]
    while rest:
        o = _OPTIONAL.match(rest)
        if not o:
            return False                  # 뒤에 **반드시** 먹는 것이 남아 있다
        rest = rest[o.end():]
    return True


def shapes(pat: str) -> list[str]:
    """그 패턴이 가진 폭발 가능 모양. 없으면 빈 목록."""
    out = []
    for m in _GROUP_Q.finditer(pat):
        if _ambiguous(m.group(2)):
            out.append("모호한 겹친 수량자")
            break
    if _ALT.search(pat):
        out.append("겹치는 선택")
    return out


def _patterns(path: Path) -> list[tuple[int, str]]:
    """그 파일이 **정규식으로 쓰는** 문자열 리터럴. AST 로 본다.

    ★ 글자로 긁지 않는다 — 주석과 서술에 적힌 예시까지 세면 수가 뜻을 잃고,
      이 저장소는 주석에 정규식을 자주 적는다(§377 이 그 자리를 적어뒀다).
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = (f.attr if isinstance(f, ast.Attribute) else
                f.id if isinstance(f, ast.Name) else "")
        if name not in ("compile", "match", "fullmatch", "search", "findall",
                        "finditer", "sub", "subn", "split"):
            continue
        mod = getattr(getattr(f, "value", None), "id", None)
        if isinstance(f, ast.Attribute) and mod not in ("re", None):
            continue
        if not node.args:
            continue
        a = node.args[0]
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            out.append((a.lineno, a.value))
    return out


def survey() -> list[dict]:
    """전수. 걸린 자리만 돌려준다."""
    hits = []
    for r in ROOTS:
        for p in sorted((ROOT / r).rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            for lineno, pat in _patterns(p):
                sh = shapes(pat)
                if sh:
                    hits.append({"file": p.relative_to(ROOT).as_posix(),
                                 "line": lineno, "shapes": sh, "pat": pat})
    return hits


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. 분모가 비면 `RuntimeError`."""
    if not any((ROOT / r).is_dir() for r in ROOTS):
        raise RuntimeError(f"분모가 없다 — {ROOTS} 중 아무 디렉터리도 없다")
    return {"REDOS_SHAPES": len(survey())}


def timings(pat: str, ns: tuple[int, ...] = (6, 10, 14)) -> list[tuple[int, float]]:
    """★ 관문이 아니다. 사람이 눈으로 볼 때만 쓴다 — 기계마다 다르다."""
    out = []
    for n in ns:
        s = "a" * n + "!"
        t0 = time.perf_counter()
        try:
            re.compile(pat).fullmatch(s)
        except re.error:
            return out
        out.append((n, (time.perf_counter() - t0) * 1000))
    return out


def show(hits: list[dict], listing: bool, timed: bool) -> int:
    print(f"── 되짚기 폭발 가능 구조  **{len(hits)}건** · 래칫 {REDOS_SHAPES}")
    print("   ① 모호한 겹친 수량자  ② 겹치는 선택")
    print("   둘 다 **필요조건**이다 — 이 모양이면 터질 수 있고, 입력이 안 닿으면 안 터진다")
    for h in (hits if listing or len(hits) <= 12 else hits[:12]):
        print(f"    {h['file']}:{h['line']}  {' · '.join(h['shapes'])}")
        print(f"        {h['pat'][:72]}")
        if timed:
            for n, ms in timings(h["pat"]):
                print(f"          n={n:<3} {ms:9.3f} ms")
    if not hits:
        print("    없음")

    print("\n★ **안전한가는 안 말한다.** 안 걸린 것이 안전하다는 뜻이 아니다.")
    if len(hits) > REDOS_SHAPES:
        print(f"\n✗ {len(hits)} > 래칫 {REDOS_SHAPES} — **늘었다.**")
        print("  §360 · §377 이 손으로 넷을 고쳤다. 다시 들이지 않는다.")
        return 1
    if len(hits) < REDOS_SHAPES:
        print(f"\n✗ {len(hits)} < 래칫 {REDOS_SHAPES} — **래칫을 그 수로 내려라.**")
        return 1
    return 0


def selftest() -> int:
    """★ 판별식이 **양방향으로** 무는가. §377 이 실제로 고친 꼴로 문다."""
    bad = []
    # ① §377 넷째가 실제로 쓰던 꼴. 16.9초가 걸렸던 그것이다.
    if not shapes(r"((?:[\w.\-\[\]]+ ?)+)"):
        bad.append("§377 이 고친 그 꼴을 못 잡는다")
    # ② 그 고침(평평한 문자군)은 안 걸려야 한다.
    if shapes(r"pip install ([\w.\-\[\] ]*)"):
        bad.append("평평한 문자군을 폭발 모양이라 한다")
    # ③ 겹친 수량자 두 꼴.
    for p in (r"(\w+ ?)+", r"([a-z]* ?)*"):
        if "모호한 겹친 수량자" not in shapes(p):
            bad.append(f"모호한 겹친 수량자를 못 잡는다 — {p}")
    # 구분자가 있으면 갈래가 하나다 — 안 걸려야 한다.
    for p in (r"^[a-z0-9]+(_[a-z0-9]+)*$", r"([\w_]+(?:\.[\w_]+)*)",
              r"(?:\s+[^\s]+)*", r"`([\w.-]+(?:/[\w.@-]+)+/?)`"):
        if shapes(p):
            bad.append(f"구분자가 있는 꼴을 잡는다 — {p} → {shapes(p)}")
    # ④ 겹치는 선택.
    if "겹치는 선택" not in shapes(r"(ab|ab?)+"):
        bad.append("겹치는 선택을 못 잡는다")
    # ⑤ 멀쩡한 것들은 안 걸린다.
    for p in (r"^[a-z][a-z0-9_]*$", r"\d{4}-\d{2}-\d{2}", r"(foo|bar)",
              r"[A-Z_][A-Z0-9_]*", r"§\s*\d+"):
        if shapes(p):
            bad.append(f"멀쩡한 패턴을 잡는다 — {p} → {shapes(p)}")
    # ⑥ 분모가 비면 안 된다.
    if not any((ROOT / r).is_dir() for r in ROOTS):
        bad.append("분모 디렉터리가 하나도 없다")
    # ⑦ AST 가 주석 속 정규식을 안 센다.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "x.py"
        f.write_text('# re.compile(r"(a+)+")\ns = "(a+)+"\n', encoding="utf-8")
        if _patterns(f):
            bad.append("주석이나 맨 문자열을 정규식으로 센다")
        f.write_text('import re\nre.compile(r"(a+)+")\n', encoding="utf-8")
        if len(_patterns(f)) != 1:
            bad.append("실제 호출의 패턴을 못 읽는다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — §377 의 꼴과 그 고침 · 모양 셋 · 음성 다섯 · AST 범위")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--time", action="store_true", help="★ 관문이 아니다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return show(survey(), a.list, a.time)


if __name__ == "__main__":
    sys.exit(main())

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
_ATOM_Q = re.compile(r"^(?:\[(?:\\.|[^\]\\])*\]|\\[wWdDsS]|\.)[+*]")
#: 선택이어서 **건너뛸 수 있는** 조각.
_OPTIONAL = re.compile(r"^(?:\[(?:\\.|[^\]\\])*\]|\\[wWdDsS]|\\.|[^\\\[\]])[?*]")
#: ③ 겹치는 선택 — 같은 글자로 시작하는 선택지가 반복된다.
_ALT = re.compile(r"\(([^()|]{1,8})\|\1[^()]*\)[+*]")
#: ④ **먹는 것이 겹치는** 선택. 글자는 달라도 같은 한 글자를 둘 다 먹을 수 있다.
# ★ 2026-10-04 (§392). CodeQL 이 이 파일의 68 · 70 행을 들었다 —
#   `(?:\\.|[^\]])*` 다. `\\.` 는 역슬래시+아무거나, `[^\]]` 는 `]` 빼고 전부라
#   **역슬래시를 둘 다 먹는다.** `_ALT` 는 역참조(`\1`)라 **글자가 같은** 선택만
#   보고 이것을 못 봤다 — 되짚기를 재는 도구가 제 되짚기를 못 본 자리다.
_QGROUP = re.compile(r"\((\?:)?([^()]*\|[^()]*)\)[+*]")


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


def _first_set(branch: str) -> tuple[bool, set[str]] | None:
    """그 가지가 **처음 먹을 수 있는 글자**. `(부정인가, 글자들)`.

    모르면 `None` 을 돌려준다 — **모른다는 「없다」가 아니다.** 빈 집합으로
    바꾸면 겹침이 0 으로 나오고 그 순간 이 판별식이 빈 그물이 된다(§372).
    """
    if not branch:
        return None
    if branch[0] == "\\" and len(branch) > 1:
        c = branch[1]
        if c in "wWdDsS":                       # `\w` 류는 넓다 — 모른다고 한다
            return None
        if c == "\\":                           # `\\` 는 역슬래시 **하나**를 먹는다
            return (False, {"\\"})
        # ★ `\n` 은 글자 `n` 이 아니다. 그대로 읽었더니 `(?:.|\n)*?` 가
        #   「`.` 과 `n` 이 겹친다」로 걸렸다 — 오탐이다.
        return (False, {{"n": "\n", "t": "\t", "r": "\r", "f": "\f",
                         "v": "\v", "0": "\0"}.get(c, c)})
    if branch[0] == "[":
        # ★ **이스케이프된 `]` 는 끝이 아니다.** `find` 로 찾았더니 `[^\]]` 의
        #   안쪽을 `^\` 로 읽어 부정 집합이 통째로 틀렸고, 그래서 68행이
        #   안 잡혔다 — 고치는 패치가 제 판별식에서 같은 실수를 했다.
        i, end = (2 if branch[1:2] == "^" else 1), -1
        while i < len(branch):
            if branch[i] == "\\":
                i += 2
                continue
            if branch[i] == "]":
                end = i
                break
            i += 1
        if end < 0:
            return None
        inner = branch[1:end]
        neg = inner.startswith("^")
        if neg:
            inner = inner[1:]
        # ★ 범위(`a-z`)나 군(`\\w` 류)이 섞이면 **모른다**. 종전에 `or` 와 `and` 를
        #   괄호 없이 섞어 적었고 엄격 린트(`--select B,RUF,…`)가 그것을 들었다 —
        #   평이한 `ruff` 는 안 울어서 로컬에서 안 보였다. 뜻도 같이 좁혔다.
        if "-" in inner[1:-1] or any(f"\\{c}" in inner for c in "wWdDsS"):
            return None
        chars = set()
        i = 0
        while i < len(inner):
            if inner[i] == "\\" and i + 1 < len(inner):
                chars.add(inner[i + 1]); i += 2
            else:
                chars.add(inner[i]); i += 1
        return (neg, chars)
    if branch[0] == ".":
        # ★ 점은 **모르는 것이 아니라 거의 전부**다. 「모른다」로 두면 `\\.` 가 든
        #   가지가 통째로 판정 불가가 되어 68 · 70 행이 다시 빠진다 — 한 번 그랬다.
        # ★ 그런데 **줄바꿈은 안 먹는다**(DOTALL 이 아니면). 전부로 뒀더니
        #   `(?:.|\n)*?` 가 걸렸다 — 그 둘은 갈린다.
        return (True, {"\n"})
    return (False, {branch[0]})


def _overlaps(a: tuple[bool, set[str]], b: tuple[bool, set[str]]) -> bool:
    """두 첫 글자 집합이 **같은 글자를 먹을 수 있는가.**"""
    na, sa = a
    nb, sb = b
    if not na and not nb:
        return bool(sa & sb)
    if na and nb:
        return True                             # 둘 다 부정이면 거의 언제나 겹친다
    pos, neg = (sa, sb) if not na else (sb, sa)
    return bool(pos - neg)


def _atoms(branch: str) -> list[tuple[bool, set[str]]] | None:
    r"""가지를 **원자 차례**로 쪼갠다. 뒤에 붙은 수량자는 떼고 바탕만 본다.

    ★ 첫 글자만 보면 안 된다. `(?:-a\s+|-f\s+)*` 는 둘 다 `-` 로 시작하지만
      **둘째 자리에서 갈린다** — 한 입력을 두 갈래로 나눌 수 없다. 첫 글자만
      보던 판이 이것을 오탐으로 들었고, 그러면 아무도 안 읽는다(§73).
    """
    out, i = [], 0
    while i < len(branch) and len(out) < 8:
        if branch[i] == "\\" and i + 1 < len(branch):
            piece, i = branch[i:i + 2], i + 2
        elif branch[i] == "[":
            j, end = (i + 2 if branch[i + 1:i + 2] == "^" else i + 1), -1
            while j < len(branch):
                if branch[j] == "\\":
                    j += 2
                    continue
                if branch[j] == "]":
                    end = j
                    break
                j += 1
            if end < 0:
                return None
            piece, i = branch[i:end + 1], end + 1
        elif branch[i] in "()?":
            return None                         # 묶음이 중첩됐다 — 모른다
        else:
            piece, i = branch[i], i + 1
        if i < len(branch) and branch[i] in "+*?{":
            while i < len(branch) and branch[i] not in "\\[":
                if branch[i] in "+*?":
                    i += 1
                elif branch[i] == "{":
                    k = branch.find("}", i)
                    if k < 0:
                        return None
                    i = k + 1
                else:
                    break
        got = _first_set(piece)
        if got is None:
            return None
        out.append(got)
    return out or None


def _branch_overlap(a: str, b: str) -> bool:
    """두 가지가 **같은 글자열을 먹을 수 있는가.**

    자리마다 집합이 겹쳐야 한다 — 한 자리라도 어긋나면 그 가지들은 갈린다.
    짧은 쪽이 끝나면 그것이 긴 쪽의 앞머리이므로 길이가 달라져 **나눌 수 있다.**
    """
    xa, xb = _atoms(a), _atoms(b)
    if not xa or not xb:
        return False                            # 모르면 안 든다 — 오탐이 더 비싸다
    return all(_overlaps(xa[i], xb[i]) for i in range(min(len(xa), len(xb))))


def _alt_overlap(pat: str) -> bool:
    """수량자가 붙은 묶음 안의 선택지 중 **먹는 것이 겹치는** 짝이 있나."""
    for m in _QGROUP.finditer(pat):
        branches = m.group(2).split("|")
        for i in range(len(branches)):
            for j in range(i + 1, len(branches)):
                if _branch_overlap(branches[i], branches[j]):
                    return True
    return False


def shapes(pat: str) -> list[str]:
    """그 패턴이 가진 폭발 가능 모양. 없으면 빈 목록."""
    out = []
    for m in _GROUP_Q.finditer(pat):
        if _ambiguous(m.group(2)):
            out.append("모호한 겹친 수량자")
            break
    if _ALT.search(pat):
        out.append("겹치는 선택")
    elif _alt_overlap(pat):
        out.append("먹는 것이 겹치는 선택")
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

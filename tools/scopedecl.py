#!/usr/bin/env python3
"""
scopedecl.py — **강제자가 자기 범위를 선언하는가.** 메타 강제자다.

    uv run python tools/scopedecl.py             판정 (verify.sh · CI)
    uv run python tools/scopedecl.py --table     선언 없는 강제자 전부를 표로
    uv run python tools/scopedecl.py --gaps      좁은 범위만 (자동 탐지 결과)
    uv run python tools/scopedecl.py --selftest  ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-24 (DECISIONS §226). 이 저장소가 **여섯 번** 같은 결함을 냈다 —
  `PLAN §13` W3-8 · W4-8 · W3-16 · W3-18 · W4-9 · `DECISIONS §197-1`.
  형태가 매번 같다:

      **범위가 이름보다 좁고, 그것이 어디에도 선언돼 있지 않다.**

  `test_tools_are_wired` 는 이름이 `every_tool` 인데 `tools/*.py` 만 봤고
  `tools/*.sh` 다섯이 검사 밖이었다. `janitor.sh` 는 아무도 안 불렀다.
  커버리지 래칫은 14 인데 실물이 24% 였고 나흘간 아무도 몰랐다.

  세 번째까지는 「검사를 하나 더 만든다」로 대응했다. 그래서 강제자가
  마흔아홉이 됐고, **그 마흔아홉이 각자 같은 결함을 새로 낳았다.**
  검사를 더 만드는 것으로는 이 족이 안 죽는다 — 족을 **보이게** 해야 죽는다.

★ 2026-09-23 밤. 대장 조사 도구 셋이 **거짓 발견 셋**을 냈다. 하나는
  `stem` 칸을 안 읽었고(대장 밖 일곱 → 실제 둘), 하나는 §183-1 의 범위
  결정을 몰랐고(검색 1,587 누락 → 결함 아님), 하나는 대장을 아예 안 읽었다
  (ITS 노드링크 「최우선 발견」 → 이미 적재 완료). 셋 다 같은 형태다.
  **도구가 거짓말을 하면 사람이 도구를 못 믿고, 그러면 도구가 없는 것과 같다.**

── 무엇을 보는가 ───────────────────────────────────────────────
① **선언** — 강제자 머리에 `밖` 칸이 있는가.

       밖    <이름이 시사하지만 이 강제자가 안 보는 것>

   없으면 센다. `NO_DECL` 이 오늘 값이고 **줄어드는 쪽으로만** 움직인다.

② **자동 탐지** — 디렉터리를 훑으면서 접미사로 거르는 자리를 AST 로 찾고,
   그 디렉터리에 **실제로 있는 다른 접미사**와 대조한다. 좁은데 `밖` 이
   그것을 안 적으면 운다. ①과 달리 이쪽은 **래칫이 아니라 실측**이다 —
   저장소에 파일이 하나 생기면 그날 바로 걸린다.

③ **자기검사** — 강제자가 `--selftest` 를 갖는가. 오늘 값보다 줄면 운다.
   빈 그물은 초록으로 위장한다(`sizecheck` 머리말과 같은 이유).

── 왜 래칫 둘과 실측 하나인가 ─────────────────────────────────
①③ 은 **오늘 못 채운 것을 오늘 빨간불로 만들지 않는다.** 강제자가 백 몇
개고 한 배치에 다 못 적는다. ② 는 다르다 — 새 파일 하나로 조용히 생기는
사각지대라서 래칫으로 두면 **래칫이 사각지대를 덮는다.**

IN    tools/*.py · tools/*.sh · tests/test_*.py
OUT   표준출력 (판정)
PARAM NO_DECL · SELFTEST_MIN · GAP_EXEMPT
밖    **선언이 참인가는 못 본다.** `밖` 칸에 아무 말이나 적어도 통과한다 —
      이 검사가 강제하는 것은 「적혀 있는가」뿐이다. 내용의 참은 ② 가
      기계로 잡는 만큼만 보장된다. 그리고 ② 는 **접미사 축 하나만** 본다 —
      디렉터리 깊이·파일명 규칙·내용 필터로 좁아진 범위는 못 잡는다.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 훑는 대상이 될 수 있는 저장소 디렉터리. 여기 없는 이름은 ② 가 안 본다.
WALKABLE = ("src", "tools", "tests", "docs", "web", ".github")

# 실물 접미사를 셀 때 빼는 것. 생성물·캐시는 강제자의 범위가 아니다.
IGNORE_DIR = {"__pycache__", ".venv", "node_modules", "dist", "fixtures",
              ".git", ".pytest_cache", ".ruff_cache", "coverage", "egg-info"}

# ★ 세는 접미사는 **사람이 쓰는 텍스트**만이다. 자료·그림·봉인값은 강제자가
#   안 봐도 정상이고, 그것까지 세면 이 도구가 거짓 발견을 낸다.
#   2026-09-24 실측 — 넓게 셌을 때 43건 중 28건이 `src/*.txt` 같은 곁다리였다.
TEXT_SUFFIX = {".py", ".sh", ".mjs", ".yml", ".yaml",
               ".ts", ".tsx", ".js", ".html", ".css", ".md"}

# ★ 한 디렉터리에서 **세 개 미만**인 접미사는 안 센다. 하나짜리 곁다리
#   (`src/py.typed` 옆의 `.md` 한 장)를 범위 결함으로 부르면 안 된다.
MIN_FILES = 3

# ── ② 면제. **사유를 함께 적는다.** 비우는 것이 목표가 아니다.
# ★ 지금은 비어 있다. 여섯을 실제로 고치거나 `밖` 칸으로 선언해서 0 이 됐다 —
#   면제는 **고칠 수도 선언할 수도 없을 때**만 쓴다. `test_scopedecl` 이
#   죽은 면제를 운다(사각지대가 되므로).
GAP_EXEMPT: dict[tuple[str, str, str], str] = {}

# ── ① 래칫. 오늘 값. **내려가는 쪽으로만.**
NO_DECL = 150

# ── ③ 래칫. 오늘 값. **올라가는 쪽으로만.**
# ★ 2026-09-25. 15 → 16. `tools/cost_inputs.py` 가 `--selftest` 를 갖고 왔다
#   (경로 비용 입력의 결측·0 구분 · 압력 계수). 계수가 전부 0 이라 그 도구는
#   **빈 그물이 되기 쉬운** 꼴이다 — 자기검사가 없으면 영원히 초록이다.
# ★ 2026-09-25 (§258). 16 → 17. `tools/fixture_recut.py` 가 `--selftest` 를 든다 —
#   사본 픽스처가 갈렸을 때 ㉠ 재현 불가와 ㉡ 판 변경을 가르는 판별식이라,
#   그 판별식이 빈 그물이면 진단이 조용히 거짓말한다.
# ★ 2026-09-25 (§258-8). 17 → 18. `tools/argcheck.py` — 관문 호출 인자 대조.
# ★ 2026-09-28 (DECISIONS §278-1). 23 → 24. **수가 는 것이 아니라 세는 법이 고쳐졌다** —
#   문자열 검사가 `localgeo` · `svg_fit`(하위명령으로 받는다)을 **놓치고**,
#   `verify.sh`(남의 도구에 붙여 부른다)를 **잘못 세고** 있었다. 양방향으로 틀렸다.
# ★ 2026-09-28 (DECISIONS §286). 28 → 29. `tools/selftests.py` — 선언된
#   자기검사를 전부 도는 문 하나다. 그 도구 자신도 자기검사를 갖는다
#   (수집이 0개를 모으면 「전부 초록」이 거짓말이 된다).
# ★ 2026-09-28 (PLAN W13-7 · DECISIONS §288). 29 → 30. `tools/fieldseal.py` —
#   재취득 불가 층의 무결성 지문. 판별식이 바뀜·사라짐·새로 생김 셋을
#   실제로 가르는지 자기검사가 문다.
# ★ 2026-09-29 (DECISIONS §309). 33 → 34. `tools/ratchet.py` — 래칫을 조이는
#   쪽으로만 고쳐 적는 문 하나다. 그 도구의 값어치가 **느슨해지는 쪽을
#   막는 것**에 전부 걸려 있으므로, 방향 판정이 살아 있는지를 판별식이 문다.
#   ★ 이 줄은 그 도구가 스스로 써 넣었다 — 사람이 34 를 받아적지 않았다.
# ★ 2026-09-29 (DECISIONS §310). 34 → 36. `tools/uicheck.py` · `tools/mergecheck.py` —
#   사람 눈이 마지막 관문이던 두 자리다. 둘 다 **0건이 청결인지 죽음인지**가
#   특히 흐린 꼴이라(화면은 늘 무언가 그려지고, 머지는 늘 되어 있다) 판별식이
#   빈 그물이 아닌지 자기검사가 문다.
#   ★ 이 수도 `ratchet.py` 가 스스로 써 넣었다(§309).
# ★ 2026-09-30 (DECISIONS §324). 40 → 41. `tools/actionpin.py` — 워크플로 액션이
#   지문으로 고정돼 있는가. **판정이 「없음」쪽으로 죽으면 조용히 초록**이라
#   (워크플로를 하나도 못 찾으면 위반도 0이다) 빈 그물인지 자기검사가 문다.
#   ★ 이 수도 `ratchet.py` 가 스스로 써 넣었다.
# ★ 2026-09-30 (DECISIONS §330). 41 → 42. `tools/docnum_check.py` — 폐기목록이
#   **지금 값**을 폐기라고 적는가. 같은 축은 2026-08-24 부터 봤는데 축 사이를
#   안 봐서, `clear` 의 폐기값 400 이 `unknown` 의 현재값이 된 날 **맞는 문서가
#   빨개졌다.** 판별식을 순수 함수로 뽑아 자기검사가 그 모양을 직접 문다.
#   ★ 이 수도 `ratchet.py` 가 스스로 써 넣었다.
SELFTEST_MIN = 53

#: `tools/ratchet.py` 가 이 둘을 **조이는 쪽으로만** 고쳐 적는다(§309).
#: 사람이 위 두 수를 받아적지 않는다 — 판정은 여전히 `judge()` 가 한다.
RATCHETS = {"NO_DECL": "down", "SELFTEST_MIN": "up"}


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. **판정은 안 한다**(`judge()` 소관)."""
    _, missing, st, _ = measure()
    return {"NO_DECL": len(missing), "SELFTEST_MIN": len(st)}


DECL_RE = re.compile(r"^\s*밖\s{2,}(\S.*)$", re.M)

#: 셸 도구가 `--selftest` 를 **제 인자로 받는** 자리. 남을 그렇게 부르는 것은 아니다.
SH_SELF = re.compile(r'(?m)^\s*(?:--selftest\)|.*?\$\{?[\w@#]+\}?"?\s*(?:==?)\s*"?--selftest)')
WALK_FN = {"glob", "rglob", "iterdir", "walk"}


# ── 수집 ────────────────────────────────────────────────────────
def enforcers() -> list[Path]:
    """강제자 — 검사·도구로 실제 도는 것들."""
    out = [p for p in sorted((ROOT / "tools").iterdir())
           if p.is_file() and p.suffix in (".py", ".sh")]
    out += sorted((ROOT / "tests").glob("test_*.py"))
    return out


def header(p: Path) -> str:
    """머리말. `.py` 는 모듈 독스트링, `.sh` 는 첫 주석 덩어리."""
    txt = p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix == ".py":
        try:
            doc = ast.get_docstring(ast.parse(txt))
        except SyntaxError:
            return ""
        return doc or ""
    lines, buf = txt.splitlines(), []
    for ln in lines[:80]:
        if ln.startswith("#!"):
            continue
        if ln.startswith("#"):
            buf.append(ln.lstrip("#"))
        elif buf:
            break
    return "\n".join(buf)


def declares(p: Path) -> str | None:
    """`밖` 칸의 내용. 없으면 None."""
    m = DECL_RE.search(header(p))
    return m.group(1).strip() if m else None


def has_selftest(p: Path) -> bool:
    """★ `tools/` 만 센다. 시험은 자기가 곧 자기검사라 세면 수가 부풀고,
    부푼 수는 「자기검사가 늘었다」는 거짓 신호를 낸다.

    ★ 2026-09-28 (DECISIONS §278-1). 종전에는 파일 **본문에 `--selftest` 라는
      글자가 있는가**만 봤다. 그래서 머리말에 「`--selftest` 가 재는 것이…」라고
      **설명만 적어도** 자기검사 하나로 세어졌다 — 실제로 그렇게 늘었고,
      래칫을 그 수로 올렸으면 **진짜 자기검사가 하나 사라져도 안 운다.**

    ★ 실행되는 자리만 센다 — 최상위 `def selftest(` 이 있거나, 문자열
      `"--selftest"` 가 **호출의 인자**로 들어간다(`add_argument` 따위).
      주석 · 독스트링은 어느 쪽도 아니다.
    """
    if p.parent.name != "tools":
        return False
    if p.suffix != ".py":
        # ★ 셸 도구는 **제 인자로 받는 자리**만 센다. `verify.sh` 는 남의 도구에
        #   `--selftest` 를 붙여 부를 뿐인데 종전 문자열 검사는 그것을 제 자기검사로
        #   셌다 — 거짓 양성이 래칫에 앉으면 그만큼이 사각지대다.
        return bool(SH_SELF.search(p.read_text(encoding="utf-8", errors="ignore")))
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return False
    if any(isinstance(n, ast.FunctionDef) and n.name == "selftest" for n in tree.body):
        return True
    return any(isinstance(n, ast.Call)
               and any(isinstance(a, ast.Constant) and a.value == "--selftest"
                       for a in n.args)
               for n in ast.walk(tree))


# ── ② 자동 탐지 ─────────────────────────────────────────────────
def _suffix_literals(node: ast.AST) -> set[str]:
    """이 구문 조각 안에서 **접미사 필터로 쓰인** 문자열들."""
    got: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Compare) and _is_suffix_attr(n.left):
            for c in n.comparators:
                got |= _strings(c)
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "endswith"):
            for a in n.args:
                got |= _strings(a)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in ("glob", "rglob"):
            for a in n.args:
                for s in _strings(a):
                    m = re.search(r"(\.[A-Za-z0-9]{1,6})$", s)
                    if m:
                        got.add(m.group(1))
    return {s for s in got if re.fullmatch(r"\.[A-Za-z0-9]{1,6}", s)}


def _is_suffix_attr(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr in ("suffix", "ext")


def _strings(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def _walked_dirs(node: ast.AST) -> set[str]:
    """이 조각이 **훑는** 저장소 디렉터리들. `ROOT / "tools"` · `glob("tools/…")`."""
    got: set[str] = set()
    for n in ast.walk(node):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in WALK_FN):
            continue
        blob = ast.unparse(n.func.value) + " " + " ".join(
            ast.unparse(a) for a in n.args)
        for d in WALKABLE:
            if re.search(rf'["\']{re.escape(d)}(["\'/])', blob):
                got.add(d)
    return got


def scopes(p: Path) -> set[tuple[str, str]]:
    """`(디렉터리, 접미사)` — 이 강제자가 **훑으면서 거른** 짝들."""
    if p.suffix != ".py":
        return set()
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()
    # ★ 단위는 **함수 하나**다. 모듈 전체를 한 단위로 보면 A 함수가 훑은
    #   디렉터리와 B 함수가 건 접미사가 짝지어져 **거짓 발견**이 난다
    #   (2026-09-24 — `doc_fsck` 가 `tools/*.sh` 를 안 본다는 거짓 1건).
    #   모듈 단위는 함수 밖 구문만 본다.
    fns = [n for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    inner = {id(x) for f in fns for x in ast.walk(f)} - {id(f) for f in fns}
    top = ast.Module(body=[s for s in tree.body if id(s) not in inner
                           and not isinstance(s, (ast.FunctionDef,
                                                  ast.AsyncFunctionDef,
                                                  ast.ClassDef))],
                     type_ignores=[])
    units: list[ast.AST] = [top, *fns]
    out: set[tuple[str, str]] = set()
    for u in units:
        dirs, sufs = _walked_dirs(u), _suffix_literals(u)
        if not dirs or not sufs:
            continue
        for d in dirs:
            for s in sufs:
                out.add((d, s))
    return out


def real_suffixes(d: str) -> set[str]:
    """`d` 아래에 **실제로 있는** 텍스트 접미사들. `MIN_FILES` 미만은 안 센다."""
    base = ROOT / d
    if not base.is_dir():
        return set()
    tally: dict[str, int] = {}
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.relative_to(base).parts)
        if IGNORE_DIR & parts or any(x.endswith(".egg-info") for x in parts):
            continue
        s = p.suffix.lower()
        if s in TEXT_SUFFIX:
            tally[s] = tally.get(s, 0) + 1
    return {s for s, n in tally.items() if n >= MIN_FILES}


def gaps(files: list[Path] | None = None) -> list[tuple[str, str, str]]:
    """`(강제자, 디렉터리, 안 보는 접미사)` — 좁은데 선언 안 된 것.

    ★ **어디서도 그 접미사를 입에 올리지 않을 때만** 운다. 함수 하나에서
      디렉터리를 훑고 다른 함수에서 거르는 것은 흔한 꼴이고, 그것까지 세면
      `doc_fsck` 가 `docs/*.md` 를 안 본다는 **거짓 발견**이 나온다
      (2026-09-24 실측 — 그 한 규칙이 거짓 5건을 없앴다).
    """
    out = []
    for p in (files if files is not None else enforcers()):
        pairs = scopes(p)
        if not pairs:
            continue
        rel = str(p.relative_to(ROOT))
        decl = declares(p) or ""
        body = p.read_text(encoding="utf-8", errors="ignore")
        for d in sorted({d for d, _ in pairs}):
            for miss in sorted(real_suffixes(d)):
                if miss in body or (rel, d, miss) in GAP_EXEMPT or miss in decl:
                    continue
                out.append((rel, d, miss))
    return out


# ── 판정 ────────────────────────────────────────────────────────
def judge(no_decl: int, selftest: int, gap: list) -> list[str]:
    """빨간불 사유들. 비면 초록."""
    bad = []
    if no_decl > NO_DECL:
        bad.append(f"`밖` 칸 없는 강제자가 늘었다 — 선언 {NO_DECL} · 실측 {no_decl}")
    if no_decl < NO_DECL:
        bad.append(f"`밖` 칸을 채웠으면 `NO_DECL` 도 {no_decl} 로 내려라 "
                   f"(선언 {NO_DECL}) — 안 내리면 다시 는다")
    if selftest < SELFTEST_MIN:
        bad.append(f"`--selftest` 가 줄었다 — 선언 {SELFTEST_MIN} · 실측 {selftest}")
    if selftest > SELFTEST_MIN:
        bad.append(f"`--selftest` 를 늘렸으면 `SELFTEST_MIN` 도 {selftest} 로 올려라 "
                   f"(선언 {SELFTEST_MIN})")
    for rel, d, miss in gap:
        bad.append(f"{rel} — `{d}/` 를 훑는데 `{miss}` 를 안 본다. "
                   f"`밖` 칸에 적거나 범위를 넓혀라")
    return bad


def measure() -> tuple[list[Path], list[Path], list[Path], list]:
    ens = enforcers()
    return (ens,
            [p for p in ens if declares(p) is None],
            [p for p in ens if has_selftest(p)],
            gaps(ens))


# ── 자기검사 ────────────────────────────────────────────────────
def selftest() -> int:
    """★ 빈 그물인가. 다섯 갈래를 합성 입력으로 본다."""
    dead = []
    if not judge(NO_DECL + 1, SELFTEST_MIN, []):
        dead.append("선언 없는 것이 늘어도 안 운다")
    if not judge(NO_DECL - 1, SELFTEST_MIN, []):
        dead.append("선언을 채웠는데 래칫을 안 내린 것을 안 운다")
    if not judge(NO_DECL, SELFTEST_MIN - 1, []):
        dead.append("selftest 가 줄어도 안 운다")
    if not judge(NO_DECL, SELFTEST_MIN, [("t/x.py", "tools", ".sh")]):
        dead.append("좁은 범위를 안 운다")
    if judge(NO_DECL, SELFTEST_MIN, []):
        dead.append("정상 입력에서 운다")

    src = "\n".join([
        "def go():",
        '    for p in (ROOT / "tools").rglob("*"):',
        '        if p.suffix == ".py":',
        "            yield p",
        "",
        "def split_units():",
        '    for p in (ROOT / "web").rglob("*"):',
        "        yield p",
        "",
        "def other():",
        '    return ".tsx"',
    ])
    tmp = ROOT / "data" / "_scopedecl_selftest.py"
    try:
        tmp.write_text(src, encoding="utf-8")
        got = scopes(tmp)
        if ("tools", ".py") not in got:
            dead.append("AST 수집기가 `rglob` + `suffix ==` 짝을 못 찾는다")
        if ("web", ".py") in got or ("web", ".tsx") in got:
            dead.append("단위가 함수별이 아니다 — 남의 함수 접미사를 끌어다 짝짓는다")
    finally:
        tmp.unlink(missing_ok=True)

    if not real_suffixes("tools") >= {".py", ".sh"}:
        dead.append("실물 접미사 수집기가 죽었다 — tools/ 에서 .py·.sh 를 못 봤다")
    if len(enforcers()) < 50:
        dead.append(f"강제자를 {len(enforcers())}개밖에 못 모았다 — 수집기가 죽었다")

    if dead:
        print("✗ 판정기 자기검사 실패 — " + ", ".join(dead))
        return 1
    print("✓ 판정기 자기검사 — 다섯 갈래 전부 운다")
    return 0


# ── 표 ──────────────────────────────────────────────────────────
def table(missing: list[Path]) -> None:
    print(f"\n`밖` 칸 없는 강제자 {len(missing)}")
    for p in missing:
        print(f"   {p.relative_to(ROOT)}")


def show_gaps(gap: list) -> None:
    print(f"\n이름보다 좁은 범위 {len(gap)}")
    for rel, d, miss in gap:
        print(f"   {rel:42} {d}/ 안의 {miss} 를 안 본다")


def main() -> int:
    ap = argparse.ArgumentParser(description="강제자가 자기 범위를 선언하는가")
    ap.add_argument("--table", action="store_true", help="선언 없는 강제자 전부")
    ap.add_argument("--gaps", action="store_true", help="자동 탐지 결과만")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    ens, missing, st, gap = measure()
    print(f"강제자 {len(ens)}   `밖` 선언 {len(ens) - len(missing)}"
          f"   자기검사 {len(st)}   좁은 범위 {len(gap)}")
    if a.table:
        table(missing)
    if a.gaps:
        show_gaps(gap)

    bad = judge(len(missing), len(st), gap)
    if bad:
        print("\n✗ 범위 선언")
        for b in bad:
            print(f"   {b}")
        print("\n  `밖` 칸은 머리말에 두 칸 들여 적는다 —")
        print("      밖    <이름이 시사하지만 이 강제자가 안 보는 것>")
        return 1
    print("✓ 범위 선언")
    return 0


if __name__ == "__main__":
    sys.exit(main())

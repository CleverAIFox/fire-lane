#!/usr/bin/env python3
"""
canaryshape.py — **무엇이 「양방향으로 밀었다」인가.** 꼴 판별만 산다.

── 왜 갈라졌나 (2026-10-12 · DECISIONS §489) ───────────────────
`tools/canary.py` 가 상한(600)을 넘었다. 넘긴 것은 관문이 아니라 **꼴
판별**이다 — §480 · §485 · §486 · §487 · §489 가 다섯 번에 걸쳐 「세는
꼴이 실물과 다르다」를 고쳤고, 그 다섯 번이 전부 이 부분을 키웠다.

★ **금이 어디인가** — 「무엇이 쌍인가」와 「쌍이 몇이고 늘었나」다. 앞은
  **정적**이다(트리를 읽고 이름을 낸다). 뒤는 **래칫**이다(수를 세고
  선언과 댄다). 다섯 판이 다 앞에서 났고, 뒤는 §445 이후 안 움직였다 —
  같이 두면 관문을 읽으러 온 사람이 판별식 스물넷을 먼저 지난다.

★ 꼴은 앞으로도 는다. 「판정이 불린이 아닌 꼴」이 이 저장소에 더 있고
  (§486 이 그 족을 적는다), 그때마다 이 파일이 자란다. **자랄 자리를
  따로 둔다**는 것이 이 가름의 뜻이다.

IN    tests/test_*.py 의 글자와 AST · tools/*.py (이름과 함수 이름)
OUT   없음 (이름 집합과 참·거짓)
PARAM 없음
밖    **수를 안 센다** — 분모·분자와 래칫은 `canary.py` 가 든다.
      **고치지 않는다** — 쌍이 없는 자리에 무엇을 넣을지는 사람이 고른다.
      **도구 쪽 자기검사는 안 본다** — `mutate` 가 흔들어서 잰다.
부류  몸통   진입점이 **아니다.** `canary.py` 가 import 한다  (DECISIONS §398)
"""
from __future__ import annotations

import ast
import builtins
import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


#: 경로로 도구를 집는 꼴. `importlib` 로 여는 시험이 이 꼴을 쓴다.
#:
#: ★ 2026-10-12 (DECISIONS §484). 종전에는 `\.py` 였고 **`.sh` 를 못 봤다.**
#:   §481 이 그 한계를 적으면서 「아무도 안 미는 관문」 둘을 남겼는데, 그 둘이
#:   `verify.sh` · `treescan.sh` **둘 다 셸**이었다 — 즉 남은 빚이 전부 이 눈먼
#:   자리였다. 넓혀서 재니 시험 넷이 분모에 들어왔고(`test_deptry_config` ·
#:   `test_gitleaks_allowlist` · `test_toolchain_declarations` ·
#:   `test_verify_evidence`) **넷 다 그 셸을 실제로 읽는다** — 머리말에 이름만
#:   적은 거짓 양성이 아니다. §481 이 걱정한 쪽은 「푸시로 세는 것」이고,
#:   그 걱정은 자리마다 열어 보고서야 가라앉는다.
_EXT = r"(?:py|sh)"
_BYPATH = (re.compile(rf'tools/([\w]+)\.{_EXT}'),
           re.compile(rf'"tools"\s*/\s*"([\w]+)\.{_EXT}"'))


def tool_names(root: Path = ROOT) -> set[str]:
    """`tools/` 의 도구 이름. **셸도 도구다**(§484)."""
    return {p.stem for p in (root / "tools").rglob("*")
            if p.suffix in (".py", ".sh") and "__pycache__" not in p.parts}


def _called(node: ast.AST) -> set[str]:
    """그 식 안에서 **불린 이름** 전부. `a.b(…)` 는 `b` 로 센다."""
    out: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name):
            out.add(f.id)
        elif isinstance(f, ast.Attribute):
            out.add(f.attr)
    return out


def code_only(src: str) -> str:
    """주석과 **문서열**을 뺀 글자.

    ── 왜 (2026-10-12 · DECISIONS §487) ────────────────────────
    경로 꼴(`tools/x.py`)을 글자에서 찾으므로 **머리말에 이름만 적은 것**이
    푸시로 세어졌다 — 실측 112 중 **열하나**가 그랬다. 그 열하나는 그 도구를
    부르지도 열지도 않는다. §481 이 「분모를 넓히면 머리말에 이름만 적은 것을
    푸시로 센다」고 걱정한 바로 그 자리이고, 그 걱정이 **실측으로 참이었다.**

    ★ `naviweight.hosts()` 가 같은 규율을 든다 — 「주석의 주소는 호출이
      아니다」. 같은 저장소에서 같은 판단을 두 번 하지 않는다.
    """
    out: list[str] = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return src          # 못 쪼개면 넓은 쪽으로 — 분모를 놓치지 않는다
    prev: int | None = None
    for tok in toks:
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and prev in (
                None, tokenize.NEWLINE, tokenize.NL, tokenize.INDENT,
                tokenize.DEDENT):
            continue        # 문장 자리에 홀로 선 글자 = 문서열
        out.append(tok.string)
        prev = tok.type
    return " ".join(out)


def touches(src: str, tree: ast.AST, tools: set[str]) -> set[str]:
    """그 시험이 미는 **도구 이름.** import 와 경로 둘 다 본다.

    ★ 경로는 **코드에 적힌 것**만 센다(§487) — 머리말의 이름은 푸시가 아니다.
    """
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
        elif isinstance(n, ast.Import):
            mods.update(a.name.split(".")[0] for a in n.names)
    code = code_only(src)
    for rx in _BYPATH:
        mods |= set(rx.findall(code))
    return mods & tools


#: 내장 함수 이름. **쌍으로 세지 않는다**(§485).
_BUILTINS = frozenset(dir(builtins))

#: 같은 꼴로 비교하는 연산자. `==` · `is` 와 그 부정.
_EQ_OPS = (ast.Eq, ast.Is, ast.NotEq, ast.IsNot)


#: 「아무것도 안 나왔다」를 뜻하는 상수들. `assert f(…) == []` 꼴이 음성이다.
_FALSY = frozenset({"[]", "{}", "''", '""', "0", "None", "set()", "()", "0.0",
                    "False", "frozenset()"})


def _is_silent(test: ast.expr) -> bool:
    """단정 **전체**가 `f(…) == <빈 상수>` 꼴인가."""
    if not isinstance(test, ast.Compare):
        return False
    if not all(isinstance(o, (ast.Eq, ast.Is)) for o in test.ops):
        return False
    try:
        vals = {ast.unparse(x) for x in test.comparators}
    except Exception:       # noqa: BLE001 — 못 풀면 음성이 아니다
        return False
    return bool(vals) and vals <= _FALSY


def _classifier(tree: ast.AST) -> set[str]:
    """**분류기 꼴**로 양방향을 민 이름.

    ── 왜 이 꼴을 따로 세나 (2026-10-12 · DECISIONS §485) ───────
    판정이 불린이 아니라 **낱말**을 내는 자가 많다(`grade()` → reference ·
    unused · wired). 그 자를 미는 옳은 꼴은

        assert grade({…}) == "reference"
        assert grade({…}) == "unused"

    이고, 이것은 **두 갈래를 다 민 것**이다. 그런데 종전 셈은 「`assert not
    f(…)` 와 그 밖」으로만 갈라서 이 꼴을 **한쪽(양성)으로만** 셌다 —
    그래서 열한 시험이 「카나리아 없음」으로 세어졌다. 이쪽은 **깎는**
    방향의 같은 병이다(§436-6).

    ★ 상수 **둘 이상**과 대야 한다. 하나면 한 갈래만 민 것이다.
    """
    #: 이름 → {(단정 자리, 댄 값)}. **단정이 둘 이상**이어야 한다 —
    #: 한 단정 안의 사슬(`a == b == c`)은 한 자리에서 민 것이다.
    seen: dict[str, set[tuple[int, str]]] = {}
    for fn in _funcs(tree):
        for n in ast.walk(fn):
            if not isinstance(n, ast.Assert):
                continue
            for c in ast.walk(n.test):
                if not isinstance(c, ast.Compare):
                    continue
                if not all(isinstance(o, _EQ_OPS) for o in c.ops):
                    continue
                called = _called(c.left) - _BUILTINS
                if not called:
                    continue
                for f in called:
                    for cmpn in c.comparators:
                        seen.setdefault(f, set()).add((id(n), ast.dump(cmpn)))
    return {f for f, v in seen.items()
            if len({val for _, val in v}) >= 2 and len({at for at, _ in v}) >= 2}


def pairs(tree: ast.AST) -> tuple[set[str], set[str]]:
    """(**음성**으로 민 이름, **양성**으로 민 이름).

    ★ 음성 = `assert not f(…)` — 「정상 입력에서 조용하다」.
      양성 = 그 밖의 단정 안에서 불린 것 — `assert f(…)` · `assert len(f(…)) == 1` ·
      `assert any("x" in b for b in f(…))`. **식 전체를 훑는다**: 양성 쪽을
      `assert f(…)` 꼴로만 좁히면 실측에서 넷이 빠졌다(세는 꼴이 실물과 달라지면
      그 검사는 제 그물이 아니라 내 손을 잰다 · §436-6).

    ★ 2026-10-12 (DECISIONS §480). **음성 쪽에 같은 구멍이 남아 있었다.**
      `bad = f(x)` 뒤에 `assert not bad` 로 쓰는 꼴이 실물의 흔한 꼴인데
      (오류 메시지가 `bad` 를 쓰므로 그렇게 쓸 수밖에 없다) 그 꼴을 안 봤다.
      §436-6 을 양성 쪽에서만 배우고 **음성 쪽에는 안 적용했다** — 그래서
      「카나리아 없음」이 거짓으로 부풀어 있었다. 한 함수 안의 지역 묶음을
      따라간다.
    """
    neg: set[str] = set()
    pos: set[str] = set()
    for fn in _funcs(tree):
        # ★ 2026-10-12 (DECISIONS §480). 한 함수 안의 **`이름 = f(…)`** 를 모은다.
        #   `assert not 이름` 이 그 이름을 쓰면 **`f` 를 음성으로 민 것**이다.
        bound: dict[str, set[str]] = {}
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign):
                got = _called(n.value)
                if not got:
                    continue
                # ★ 2026-10-12 (DECISIONS §489). **묶는 꼴을 다 본다** —
                #   종전에는 `이름 = f(…)` 하나만 봤고, 판정이 **짝을 내면**
                #   (`bad, none = judge(…)`) 그 묶음이 안 보였다. 실측 셋이
                #   그 꼴이었다. 짝의 두 이름 다 같은 호출에서 왔으므로
                #   둘 다 그 호출을 민 것이다.
                for tgt in n.targets:
                    if isinstance(tgt, ast.Name):
                        bound.setdefault(tgt.id, set()).update(got)
                    elif isinstance(tgt, (ast.Tuple, ast.List)):
                        for e in tgt.elts:
                            if isinstance(e, ast.Name):
                                bound.setdefault(e.id, set()).update(got)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) \
                    and n.value is not None:
                got = _called(n.value)
                if got:
                    bound.setdefault(n.target.id, set()).update(got)
        for n in ast.walk(fn):
            if not isinstance(n, ast.Assert):
                continue
            t = n.test
            if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
                neg |= _called(t.operand)
                neg |= _bound_names(t.operand, bound)
            elif _is_silent(t):
                # ★ 2026-10-12 (DECISIONS §485). `assert f(…) == []` 은
                #   **「조용하다」의 또 한 꼴**이다. 판정이 목록·표·글자를
                #   내면 불린으로 못 쓰므로 그렇게 적을 수밖에 없다.
                #   ★ 이 단정은 **음성으로만** 센다 — 양성에도 넣으면 그
                #     한 줄이 혼자 쌍을 이뤄 거짓으로 초록이 된다.
                neg |= _called(t.left) - _BUILTINS
                neg |= _bound_names(t.left, bound)
            else:
                pos |= _called(t)
                pos |= _bound_names(t, bound)
    # ★ 2026-10-12 (DECISIONS §485). **내장 함수를 뺀다.** `len` · `set` ·
    #   `any` 가 양쪽 꼴에 다 나오므로, 그것만으로 쌍이 성립해 **다섯 시험이
    #   거짓으로 초록**이었다. 세는 꼴이 실물과 다르면 그 수는 그물이 아니라
    #   손을 잰다(§436-6) — 이쪽은 **부풀리는** 방향이었다.
    return neg - _BUILTINS, pos - _BUILTINS


def _funcs(tree: ast.AST) -> list[ast.AST]:
    """함수 하나하나. **묶음이 함수다** — 묶음을 파일로 하면 다른 시험의 이름이
    섞이고, 그러면 한 자리에서 민 것을 다른 자리의 증거로 센다."""
    out = [n for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return out or [tree]


def _bound_names(node: ast.AST, bound: dict[str, set[str]]) -> set[str]:
    """그 식이 **참조하는 지역 이름**에 묶인 호출들."""
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in bound:
            out |= bound[n.id]
    return out


def _defs(tree: ast.AST) -> set[str]:
    """그 트리가 **정의한** 함수 이름."""
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def judge_names(src: str, tree: ast.AST, tools: set[str],
                root: Path = ROOT) -> set[str]:
    """이 시험이 **판정으로 부를 수 있는** 이름.

    ── 왜 이 문이 필요한가 (2026-10-12 · DECISIONS §486) ────────
    §485 가 내장 함수를 쌍에서 뺐다. **그것으로 끝이 아니었다** —
    `subprocess.run` · `read_text` · `items` · `get` · `search` 같은
    표준 라이브러리·메서드 이름이 음성 꼴과 양성 꼴에 **둘 다** 나와서
    아홉 시험이 거짓으로 초록이었다. 내장은 그 족의 한 조각이었다.

    옳은 물음은 「같은 **판정**을 양쪽으로 밀었나」다. 그래서 허용 집합을
    **이름의 출처**로 만든다 —

        · 그 시험 파일이 정의한 함수 (지역 보조자 · `_run` 따위)
        · 그 시험이 미는 **도구**의 함수
        · 그 시험이 글에 든 `firelane.*` 모듈의 함수

    ★ 넓게 잡는다. 좁히면 「정말 판정을 밀었나」까지 가려 해야 하고 그것은
      정적으로 알 수 없다 — 여기가 막는 것은 **우연한 쌍** 하나다.
    """
    out = _defs(tree)
    for stem in tools:
        q = root / "tools" / f"{stem}.py"
        if not q.is_file():
            continue
        try:
            out |= _defs(ast.parse(q.read_text(encoding="utf-8")))
        except (OSError, SyntaxError):
            continue
    fl = root / "src" / "firelane"
    if fl.is_dir():
        for q in sorted(fl.rglob("*.py")):
            if q.stem in src:
                try:
                    out |= _defs(ast.parse(q.read_text(encoding="utf-8")))
                except (OSError, SyntaxError):
                    continue
    return out


def has_canary(tree: ast.AST, allowed: set[str] | None = None) -> bool:
    """쌍이 있는가. `allowed` 를 주면 **그 이름들 안에서만** 센다(§486).

    ★ 기본값이 `None` 이다 — 자기검사의 합성 트리는 어디에도 정의가 없는
      이름(`f` · `g`)을 쓰므로, 거르면 그 판별식들이 전부 죽는다. 실물을
      세는 자리(`findings`)가 `allowed` 를 준다.
    """
    neg, pos = pairs(tree)
    both = (neg & pos) | _classifier(tree)
    return bool(both if allowed is None else both & allowed)



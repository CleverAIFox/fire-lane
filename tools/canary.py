#!/usr/bin/env python3
"""
canary.py — 강제자가 제 판별식을 **합성 결함으로 밀어 봤는가.**

    uv run python tools/canary.py            판정 (verify.sh · CI)
    uv run python tools/canary.py --table    카나리아 없는 강제자 전부
    uv run python tools/canary.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 (2026-10-09 · DECISIONS §445 · PLAN #56 ① 닫힘) ───
이 저장소는 「카나리아를 같이 만든다」를 §159 부터 규약으로 적고 실제로 여러 번
만들었다(`test_plan_status_probe_is_alive` · `test_rules_table_probe_is_alive` ·
`test_code_change_alone_forces_full_run` · `test_that_guard_would_catch_the_old_text`).
**그런데 세는 자리가 없었다.** 새 강제자에 카나리아가 빠져도 아무도 안 울고,
그 강제자는 **실물에서만 초록인** 검사가 된다.

`#56 ①` 이 「판별식을 먼저 정해야 셀 수 있다. 정의 없이 세면 재현되지 않는
분모다」라고 적었다. 그 정의를 여기 둔다 —

    카나리아 = **같은 파일에서 같은 함수를 양쪽으로 미는 단정 쌍**
               `assert not f(…)`  (정상 입력에서 조용하다)
               `assert … f(…) …`  (합성 입력에서 운다)

이름(`*_is_alive` · `*_bites`)으로 세지 않는다 — 이름은 규약이 아니고, 낱말로
세면 ① 이 영영 0건이 되는 그 병에 걸린다(§444-1 과 같은 자리). **문법으로 센다.**

── 왜 `deadcheck` 의 프로브가 아닌가 ─────────────────────────
`#56 ①` 은 「`deadcheck` 가 래칫으로 센다」고 적었다. **그 자리에 못 둔다** —
`tests/test_deadcheck_probes.py::test_every_ceiling_is_zero` 가 「천장이 전부
0」을 단정하고 그 사유가 **「분류가 끝난 프로브를 0 보다 높은 래칫으로 두면
다시 들어와도 천장 안이라 안 운다 — 그 천장이 곧 미분류의 다른 이름이었다」**다.
카나리아 57 은 **분류가 끝나지 않은 빚**이라 그 불변식과 성질이 다르다.
행이 적은 자리와 저장소의 불변식이 부딪혔고 **불변식을 지켰다**(§445).

── 판정 (양방향) ──────────────────────────────────────────────
    카나리아 없는 강제자가 늘었다    실패 — 새 강제자가 그물 없이 들어왔다
    줄었다                           실패 — **`NO_CANARY` 를 그 수로 내려라**
    분모가 0 이다                    실패 — 수집기가 죽었다(빈 그물)

IN    tests/test_*.py · tools/*.py (이름)
OUT   표준출력 (판정)
PARAM NO_CANARY · EXEMPT
밖    **카나리아가 옳은가는 안 본다** — 합성 입력이 실물과 같은 꼴인지는 사람이
      본다(§436-6). 여기는 **쌍이 있는가**만 센다. **도구 쪽 자기검사는 안 센다**
      — 그쪽은 `mutate` 가 흔들어서 잰다.
"""
from __future__ import annotations

import ast
import builtins
import re
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


def touches(src: str, tree: ast.AST, tools: set[str]) -> set[str]:
    """그 시험이 미는 **도구 이름.** import 와 경로 둘 다 본다."""
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
        elif isinstance(n, ast.Import):
            mods.update(a.name.split(".")[0] for a in n.names)
    for rx in _BYPATH:
        mods |= set(rx.findall(src))
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
            if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                    and isinstance(n.targets[0], ast.Name):
                got = _called(n.value)
                if got:
                    bound.setdefault(n.targets[0].id, set()).update(got)
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


def findings(root: Path = ROOT) -> list[tuple[Path, int, str, str]]:
    """(파일, 줄, 이름, 무엇이 없나). **판정은 안 한다.**"""
    tools = tool_names(root)
    out: list[tuple[Path, int, str, str]] = []
    for p in sorted((root / "tests").rglob("test_*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        hit = touches(src, tree, tools)
        if not hit or has_canary(tree, judge_names(src, tree, hit, root)):
            continue
        out.append((p, 1, p.stem,
                    f"{', '.join(sorted(hit)[:3])} 를 미는데 **합성 결함을 넣어"
                    " 우는 것을 본 자리가 없다** — 같은 판별식을 "
                    "`assert not f(…)` 와 `assert … f(…)` 둘로 밀어라"))
    return out


def denominator(root: Path = ROOT) -> int:
    """도구를 미는 시험 수. **분모를 세는 자리도 하나여야 한다.**"""
    tools = tool_names(root)
    n = 0
    for p in sorted((root / "tests").rglob("test_*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        if touches(src, tree, tools):
            n += 1
    return n


#: 카나리아를 **못 만드는** 강제자. `"파일::이름"` → 사유.
#: ★ 비었다. 오늘 29 은 면제가 아니라 **빚**이고 그것은 아래 래칫이 든다.
#:   면제가 생기면 사유와 함께 여기 한 줄이다(§69).
EXEMPT: dict[str, str] = {}

#: 카나리아 없는 강제자 수. **내려가는 쪽.** 2026-10-12 실측 29 / 분모 104.
# ★ 2026-10-12 — 56 → **30** (DECISIONS §480). **스물여섯은 거짓이었다.**
#   코드를 하나도 안 고치고 내려간 수다 — 이 파일의 음성 판별이
#   `assert not f(…)` **한 줄 꼴만** 보고 있었고, 실물의 흔한 꼴은
#   `bad = f(…)` 뒤의 `assert not bad` 다(오류 메시지가 `bad` 를 쓰므로
#   그렇게 쓸 수밖에 없다). §436-6 을 **양성 쪽에서만** 배우고 음성 쪽에는
#   안 적용한 자리다.
#   ★ **고친 것은 세는 꼴이고 약해진 것은 없다** — 양성·음성 둘 다 같은
#     호출이어야 하고, 묶음은 **함수**다(다른 함수의 이름을 제 증거로 안
#     센다 · 자기검사가 그 셋을 양방향으로 든다).
#   ★ 남은 30 은 **빚이다.** 거짓으로 부풀어 있던 수를 내렸으니 이제 그
#     30 이 실제로 민 적 없는 자리다.
# ★ 2026-10-12 — 30 → **29** (DECISIONS §480-1). 그 빚에서 하나를 갚았다 —
#   `tools/colorsim.py` 의 판정이 `show()` 의 **찍는 루프 안**에 있어 시험이
#   부를 수가 없었다. `faults()` 로 빼고 `tests/test_colorsim.py` 가 양방향으로
#   민다(같은 색 둘 · 밝기만 붙은 쌍). **지적이 맞았던 자리다.**
# ★ 2026-10-12 — 29 → **16** (DECISIONS §485). **또 코드를 하나도 안 고치고
#   움직인 수다.** 세는 꼴이 **두 군데**서 실물과 달랐고, 하나는 부풀리고
#   하나는 깎고 있었다 —
#
#     ① 내장 함수로 쌍이 성립했다 (**부풀림**)
#        `len` · `set` · `any` 가 음성·양성 꼴에 다 나와서, 공유하는 것이
#        **내장뿐인** 다섯 시험이 거짓으로 초록이었다. 29 → 34.
#     ② 분류기 꼴을 한쪽으로만 셌다 (**깎음**)
#        판정이 불린이 아니라 낱말을 내면(`grade()` → reference · unused)
#        미는 옳은 꼴이 `== "reference"` 와 `== "unused"` 둘이다. 그것이
#        **두 갈래를 다 민 것**인데 종전 셈은 양성으로만 봤다. 34 → 23.
#     ③ 「조용하다」의 또 한 꼴을 못 봤다 (**깎음**)
#        판정이 목록·표·글자를 내면 `assert f(…) == []` 로 쓸 수밖에 없다.
#        그 꼴을 음성으로 센다 — 단, **그 단정은 음성으로만** 센다(양성에도
#        넣으면 그 한 줄이 혼자 쌍을 이뤄 거짓으로 초록이 된다). 23 → **16**.
#
#   ★ 셋 다 자기검사가 **양방향으로** 든다 — 내장만으로는 쌍이 안 되고,
#     안쪽 진짜 이름은 세고, 낱말 하나나 한 단정 안의 사슬로는 안 된다.
#   ★ 남은 16 은 빚이다.
# ★ 2026-10-12 — 16 → **25** (DECISIONS §486). **올라간다 — 거짓 초록을
#   걷은 수다.** §485 가 내장 함수를 쌍에서 뺐는데 그것은 그 족의 한 조각이었다:
#   `subprocess.run` · `read_text` · `read_bytes` · `items` · `get` · `search` ·
#   `exists` · `startswith` 같은 **표준 라이브러리·메서드 이름**이 음성 꼴과
#   양성 꼴에 둘 다 나와서 아홉 시험이 거짓으로 초록이었다.
#
#   옳은 물음은 「같은 **판정**을 양쪽으로 밀었나」다. 그래서 쌍을 **이름의
#   출처**로 거른다(`judge_names`) — 그 시험이 정의한 함수 · 그 시험이 미는
#   도구의 함수 · 글에 든 `firelane.*` 모듈의 함수. 넓게 잡는다: 좁히면
#   「정말 판정을 밀었나」까지 가려야 하고 그것은 정적으로 알 수 없다.
#
#   ★ 이 판에서 **둘을 같이 갚았다** —
#     `tests/test_commit_policy.py` 는 규칙 여섯을 각각 양쪽으로 밀면서
#       **그것들을 모으는 자**(`check_paths`)를 안 밀고 있었고, 쌍은
#       `subprocess.run` 으로 성립해 있었다. 규칙이 다 맞아도 모으는 쪽이
#       비면 훅은 조용하다. 규칙 여섯을 **하나씩** 섞어 넣어 이름·사유·
#       파일을 다 말하는지 보고, 자르는 자리의 「외 N건」까지 든다.
#     `tests/test_cost_inputs.py` 는 도구를 하위프로세스로 **부르기만**
#       했다. 초록은 「검사했다」가 아니다(§199) — `judge()` 를 합성
#       입력으로 민다: 빈 발행물 · 0 을 뺀 발행 · 거짓 자기신고 ·
#       대장 없이 켠 압력 계수, 그리고 **꺼진 계수에는 안 우는가**.
#   ★ 남은 24 가 **처음으로 뜻이 있는 수다** — 내장도, 라이브러리도,
#     우연한 메서드도 아닌 **판정 이름으로 센** 빚이다.
NO_CANARY = 24

RATCHETS = {"NO_CANARY": "down"}


def ratchet_values() -> dict[str, int]:
    """지금 수. **재기만 한다** — 판정은 `faults()` 가 든다."""
    return {"NO_CANARY": len(rows())}


def rows(root: Path = ROOT) -> list[tuple[Path, str]]:
    """(파일, 무엇이 없나). 면제를 뺀 뒤의 목록이다."""
    out = []
    for p, _ln, name, what in findings(root):
        rel = p.relative_to(root).as_posix()
        if f"{rel}::{name}" in EXEMPT:
            continue
        out.append((p, what))
    return out


def faults(n: int, limit: int = NO_CANARY, denom: int = 1) -> list[str]:
    """양방향 래칫 + 빈 그물. **순수 함수**다."""
    if denom <= 0:
        return ["분모가 0 이다 — 도구를 미는 시험을 하나도 못 찾았다. 수집기가 죽었다"]
    if n > limit:
        return [f"카나리아 없는 강제자 {n} > 기록 {limit} — 새 강제자가 "
                "**합성 결함을 넣어 우는 것을 본 자리** 없이 들어왔다"]
    if n < limit:
        return [f"카나리아 없는 강제자 {n} 으로 줄었다 — "
                f"tools/canary.py 의 `NO_CANARY` 를 {n} 으로 내려라"]
    return []


def selftest() -> int:
    bad: list[str] = []
    import ast as _a
    # ★ 쌍을 가르는가 — 양방향
    pair = _a.parse("def t():\n    assert not f(1)\ndef c():\n    assert f(2)\n")
    one = _a.parse("def t():\n    assert not f(1)\n")
    if not has_canary(pair):
        bad.append("양방향 쌍을 못 본다")
    if has_canary(one):
        bad.append("음성만 있는데 카나리아로 센다")
    # ★ 식 안쪽까지 훑는가 — `assert len(f(…)) == 1` 꼴이 실물의 과반이다
    deep = _a.parse("def t():\n    assert not f(1)\ndef c():\n    assert len(f(2)) == 1\n")
    if not has_canary(deep):
        bad.append("단정 식 안쪽의 호출을 못 본다")
    # ★ 2026-10-12 (§480). **두 줄 꼴**을 보는가 — 양방향
    two = _a.parse("def t():\n    bad = f(1)\n    assert not bad\n"
                   "def c():\n    assert f(2)\n")
    if not has_canary(two):
        bad.append("`bad = f(…)` 뒤의 `assert not bad` 를 못 본다")
    two_one = _a.parse("def t():\n    bad = f(1)\n    assert not bad\n")
    if has_canary(two_one):
        bad.append("두 줄 꼴 음성만 있는데 카나리아로 센다")
    # ★ 묶음이 **함수**다 — 다른 함수의 이름을 끌어오면 안 된다
    cross = _a.parse("def t():\n    bad = f(1)\n"
                     "def u():\n    assert not bad\n"
                     "def c():\n    assert f(2)\n")
    if has_canary(cross):
        bad.append("다른 함수에 묶인 이름을 제 증거로 센다")

    # ★ 분모 — 도구를 미는 시험만
    tools = tool_names()
    if not tools:
        bad.append("도구 이름을 0개 셌다")
    if touches("import json", _a.parse("import json"), tools):
        bad.append("표준 꾸러미를 도구로 센다")
    if not touches('p = ROOT / "tools" / "golden.py"',
                   _a.parse('p = 1'), tools):
        bad.append("경로로 집는 꼴을 못 본다")
    # ★ 2026-10-12 (DECISIONS §485) — **내장 함수로는 쌍이 안 된다**
    #   ★ 안쪽 이름을 **다르게** 둔다 — 같으면 그 이름으로 쌍이 성립하고
    #     그것은 옳은 쌍이다. 거짓 쌍은 **공유하는 것이 내장뿐**일 때 생긴다.
    blt = _a.parse('def t():\n    assert not len(f(1))\n'
                   'def c():\n    assert len(g(2)) == 3\n')
    if has_canary(blt):
        bad.append("`len` 하나로 쌍을 세운다 — 다섯 시험이 그렇게 거짓으로 초록이었다")
    # ★ 그런데 **그 안의 진짜 이름**은 세어야 한다 — 내장만 빼는 것이다
    inner = _a.parse('def t():\n    assert not len(f(1))\n'
                     'def c():\n    assert f(2) == 3\n'
                     'def d():\n    assert f(3) == 4\n')
    if not has_canary(inner):
        bad.append("내장을 빼면서 안쪽 이름까지 버렸다")

    # ★ **분류기 꼴** — 같은 자를 서로 다른 낱말 둘과 댄 것
    cls2 = _a.parse('def t():\n    assert g(1) == "a"\n'
                    'def c():\n    assert g(2) == "b"\n')
    if not has_canary(cls2):
        bad.append("분류기를 낱말 둘로 밀었는데 안 센다 — 열한 시험이 그렇게 깎였다")
    cls1 = _a.parse('def t():\n    assert g(1) == "a"\n'
                    'def c():\n    assert g(2) == "a"\n')
    if has_canary(cls1):
        bad.append("같은 낱말만 둘인데 양방향으로 센다 — 한 갈래만 민 것이다")
    if has_canary(_a.parse('def t():\n    assert g(1) == "a"\n')):
        bad.append("낱말 하나로 양방향을 센다")

    # ★ 2026-10-12 (§485) — **「조용하다」 꼴**과 그 자기쌍 방어
    sil = _a.parse('def t():\n    assert f(1) == []\n'
                   'def c():\n    assert f(2)\n')
    if not has_canary(sil):
        bad.append("`assert f(…) == []` 을 음성으로 안 센다 — 목록을 내는 판정이"
                   " 그렇게 적을 수밖에 없다(일곱 시험이 그 꼴이었다)")
    alone = _a.parse('def t():\n    assert f(1) == []\n')
    if has_canary(alone):
        bad.append("`assert f(…) == []` **한 줄이 혼자 쌍을 이룬다** — 같은 단정을"
                   " 음성과 양성에 둘 다 넣으면 그 줄 하나로 초록이 된다")
    chain = _a.parse('def t():\n    assert g(1) == "a" == "b"\n')
    if has_canary(chain):
        bad.append("한 단정 안의 사슬을 두 자리로 센다 — 한 자리에서 민 것이다")

    # ★ 2026-10-12 (§486) — **판정 이름 안에서만** 센다
    lib = _a.parse('def t():\n    assert not p.read_text()\n'
                   'def c():\n    assert q.read_text()\n')
    if has_canary(lib, allowed={"판정"}):
        bad.append("표준 라이브러리 이름으로 쌍을 세운다 — 아홉 시험이 그렇게"
                   " 거짓으로 초록이었다")
    if not has_canary(lib):
        bad.append("허용 집합을 안 주면 거르지 말아야 한다 — 합성 판별식이 죽는다")
    mine = _a.parse('def 판정(x):\n    return []\n'
                    'def t():\n    assert not 판정(1)\n'
                    'def c():\n    assert 판정(2)\n')
    if not has_canary(mine, allowed=_defs(mine)):
        bad.append("그 파일이 정의한 판정으로 민 쌍을 안 센다")
    # ★ 허용 집합이 **어디서 오는가** — 미는 도구의 함수가 들어야 한다
    nm = judge_names("import canary", _a.parse("import canary"), {"canary"})
    if "has_canary" not in nm or "judge_names" not in nm:
        bad.append("미는 도구의 함수 이름을 허용 집합에 안 넣는다")
    if judge_names("", _a.parse(""), {"없는도구"}):
        bad.append("없는 도구에서 이름을 만든다")

    # ★ 판정 — 양방향 · 빈 그물
    if not faults(NO_CANARY + 1, denom=98):
        bad.append("늘었는데 안 운다")
    if not faults(NO_CANARY - 1, denom=98):
        bad.append("줄었는데 안 운다 — 느슨한 래칫은 지난 기록이다")
    if faults(NO_CANARY, denom=98):
        bad.append("기록과 같은데 운다")
    if not faults(0, limit=0, denom=0):
        bad.append("분모 0 에서 통과한다 — 빈 그물")
    if denominator() <= 0:
        bad.append("실물에서 분모를 0 으로 셌다")

    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 쌍 가름 · 식 안쪽 · **두 줄 꼴** · 함수 경계 · **내장 제외** · **분류기 꼴** · 분모 · 양방향 · 빈 그물")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="강제자의 카나리아 래칫")
    ap.add_argument("--table", action="store_true", help="카나리아 없는 강제자 전부")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    got = rows()
    denom = denominator()
    if a.table:
        for p, what in got:
            print(f"  {p.relative_to(ROOT).as_posix():<46} {what[:60]}")
    bad = faults(len(got), denom=denom)
    if bad:
        print(f"✗ 카나리아 {len(bad)}건")
        for b in bad:
            print(f"    {b}")
        print("  정의 — 같은 파일에서 같은 함수를 `assert not f(…)` 와 "
              "`assert … f(…)` 둘로 민다. 이름으로 세지 않는다(§445).")
        return 1
    print(f"✓ 카나리아 — 도구를 미는 시험 {denom} · 없음 {len(got)} = 래칫 {NO_CANARY}"
          f" · 면제 {len(EXEMPT)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

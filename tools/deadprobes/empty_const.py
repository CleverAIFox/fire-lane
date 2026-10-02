"""`deadcheck ①(상수)` — 모듈 상수가 **빈 모음**인데 검사가 그것을 도는가.

★ 2026-10-03 (DECISIONS §359). ① 의 우주가 **대장 키**뿐이었다 —
  `sources.yaml` 의 `datasets`·`retired`·`outputs` 를 `.get("X")` 로 읽는
  자리만 봤다. 그래서 **모듈 상수를 도는 검사**는 통째로 사각이었고,
  `doc_fsck.DEFERRED = ()` 가 열흘 가까이 `[]` 만 돌려줬다. 그 도구의 머리말이
  바로 그 병을 경고하고 있었는데(「해제만 검사하면 항상 통과하는 검사가
  된다(§69)」) 정작 자기가 걸렸다.

  **좁은 우주에 천장 0 을 얹으면 가장 조용한 거짓이 된다** — 「천장이 전부
  0 이다」가 「볼 수 있는 데는 깨끗하다」가 아니라 「다 깨끗하다」로 읽힌다.

IN    tools/ · tests/ · src/ 의 파이썬
OUT   결함 (`hit` 으로 올린다)
★ **그릇과 그물을 가른다.** 모듈 상수여도 어딘가가 거기에 **넣으면**(`X[k] = v` ·
  `X.append` · `X.update` …) 그것은 런타임에 차는 **그릇**이다. 실측에서
  `firelane.segments._SAMPLES` 가 그 꼴이었다 — 비어 선언되고 판정 중에 찬다.
  넣는 자리가 하나라도 있으면 안 센다.

★ **채워야 할 것과 비어야 할 것도 다르다.** 빈 **면제표**는 안전하다 —
  아무것도 면제 안 한다는 뜻이다. 빈 **감시 목록**은 위험하다 — 아무것도
  안 본다는 뜻이다. 이 프로브는 둘을 글로 못 가르므로 **전부 올리고**,
  안전한 쪽은 `EXEMPT_EMPTY_CONST` 에 사유와 함께 적는다.

IN    tools/ · tests/ · src/ 의 파이썬
OUT   결함 (`hit` 으로 올린다)
밖    **함수 안의 빈 모음은 안 본다.** 그것은 쌓는 그릇이지 그물이 아니다.
      **소문자 이름도 안 본다.** 상수가 아니면 런타임에 채워질 수 있다.
      **빈 것이 옳은가는 안 본다** — 옳다면 면제표에 사유와 함께 적는다.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_EMPTY = (ast.Tuple, ast.List, ast.Set, ast.Dict)
#: `for x in sorted(NAME)` 처럼 한 겹 감싼 것까지 본다.
_WRAP = ("sorted", "list", "tuple", "set", "reversed", "enumerate")


def empty_consts(tree: ast.Module) -> dict[str, int]:
    """모듈 최상위의 **대문자 상수** 중 빈 모음 → 줄 번호."""
    out: dict[str, int] = {}
    for n in tree.body:
        tgt = val = None
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            tgt, val = n.targets[0].id, n.value
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value:
            tgt, val = n.target.id, n.value
        if not tgt or not tgt.isupper() or not isinstance(val, _EMPTY):
            continue
        elts = val.keys if isinstance(val, ast.Dict) else val.elts
        if not elts:
            out[tgt] = n.lineno
    return out


#: 그릇을 만드는 쓰기. 하나라도 있으면 그 이름은 런타임에 찬다.
_FILL = ("append", "add", "update", "extend", "insert", "setdefault", "append_many")


def filled_names(tree: ast.Module) -> set[str]:
    """모듈 어딘가가 **넣는** 이름. `X[k] = v` · `X.append(...)` · `X += ...`."""
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in _FILL and isinstance(n.func.value, ast.Name):
            out.add(n.func.value.id)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    out.add(t.value.id)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Subscript) \
                and isinstance(n.target.value, ast.Name):
            out.add(n.target.value.id)
    return out


def _iterated_name(it: ast.expr) -> str | None:
    """`for x in <it>` 의 <it> 이 **어떤 이름을 도는가**."""
    if isinstance(it, ast.Name):
        return it.id
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) \
            and it.func.id in _WRAP and it.args and isinstance(it.args[0], ast.Name):
        return it.args[0].id
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) \
            and it.func.attr in ("items", "values", "keys") \
            and isinstance(it.func.value, ast.Name):
        return it.func.value.id
    return None


def findings(root: Path = ROOT) -> list[tuple[Path, int, str, str]]:
    """(파일, 줄, 상수 이름, 그것을 도는 함수). **판정은 안 한다.**"""
    out: list[tuple[Path, int, str, str]] = []
    for p in sorted((root / "tools").rglob("*.py")) \
            + sorted((root / "tests").rglob("*.py")) \
            + sorted((root / "src").rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        consts = empty_consts(tree)
        if not consts:
            continue
        # ★ 넣는 자리가 있으면 **그릇**이다. 런타임에 찬다 — 빈 그물이 아니다.
        for nm in filled_names(tree):
            consts.pop(nm, None)
        if not consts:
            continue
        seen: set[str] = set()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for n in ast.walk(fn):
                if not isinstance(n, ast.For):
                    continue
                nm = _iterated_name(n.iter)
                if nm in consts and nm not in seen:
                    seen.add(nm)
                    out.append((p, consts[nm], nm, fn.name))
    return out

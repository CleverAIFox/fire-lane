"""
test_static.py — 실행하지 않고 잡을 수 있는 것을 잡는다

★ 왜 생겼나 (2026-08-18 Stage 4)

`segments.py` 는 `sys.exit(...)` 를 세 곳에서 쓰는데 `import sys` 가 없었다.
`import sys as _sys` 만 있었고, 그것은 경로 삽입용이다. 즉 계보 검사와
공간 커버리지 검사가 **실패하면 안내 메시지 대신 NameError 로 죽는다.**

두 검사 다 08-17/18 사고를 막으려고 넣은 방어였고, 한 번도 실패한 적이 없어서
드러나지 않았다. 방어의 실패 경로 자체가 고장 나 있었던 것이다.
(출처는 `tools/stale_guard_20260818.py` 의 주입 코드다. 그 패처는 실행해서
붙이기만 하고 붙인 결과를 아무도 실행해보지 않았다 — R9 가 금지하는 방식의
전형적인 결과다.)

계약 테스트도 golden 도 이런 것을 못 잡는다. 둘 다 **성공 경로의 산출물**만
본다. 여기서는 코드를 읽어서 잡는다.
"""
import ast
import builtins
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# 모듈 실행 시 항상 존재하는 이름.
IMPLICIT = {"__file__", "__name__", "__doc__", "__package__", "__spec__"}


def _bound_in(node) -> set[str]:
    """이 스코프에서 이름이 묶이는 모든 경로를 모은다."""
    out: set[str] = set()
    args = getattr(node, "args", None)
    if args is not None:
        out |= {a.arg for a in list(args.args) + list(args.kwonlyargs)
                + list(getattr(args, "posonlyargs", []))}
        if args.vararg:
            out.add(args.vararg.arg)
        if args.kwarg:
            out.add(args.kwarg.arg)
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {a.asname or a.name.split(".")[0] for a in n.names}
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(n.name)
            out |= _bound_in_args(n)
        elif isinstance(n, ast.Lambda):
            out |= _bound_in_args(n)
        elif isinstance(n, ast.ClassDef):
            out.add(n.name)
        elif isinstance(n, ast.comprehension):
            for x in ast.walk(n.target):
                if isinstance(x, ast.Name):
                    out.add(x.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.Global):
            out |= set(n.names)
    return out


def _bound_in_args(node) -> set[str]:
    a = node.args
    s = {x.arg for x in list(a.args) + list(a.kwonlyargs)
         + list(getattr(a, "posonlyargs", []))}
    if a.vararg:
        s.add(a.vararg.arg)
    if a.kwarg:
        s.add(a.kwarg.arg)
    return s


def undefined_names(path: Path) -> list[str]:
    """함수 안에서 읽히는데 어디서도 묶이지 않는 이름.

    보수적으로 본다 — 애매하면 통과시킨다. 거짓 경보가 나면 아무도 안 믿는다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    scope = set(dir(builtins)) | IMPLICIT | _bound_in(tree)
    bad: set[str] = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        own = _bound_in(fn)
        read = {n.id for n in ast.walk(fn)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        bad |= read - own - scope
    return sorted(bad)


PY_FILES = sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in str(p))


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: str(p.relative_to(SRC)))
def test_no_undefined_names(path):
    """
    실패 경로에만 있는 NameError 를 잡는다.

    `sys.exit(...)` 을 쓰면서 `import sys` 를 안 한 것이 실제 사례다.
    성공할 때는 그 줄에 닿지 않으므로 파이프라인이 80초 내내 멀쩡히 돈다.
    """
    bad = undefined_names(path)
    assert not bad, f"{path.relative_to(ROOT)}: 정의되지 않은 이름 {bad}"


def test_guard_exit_paths_are_reachable():
    """
    ★ 방어의 실패 경로가 실제로 메시지를 낼 수 있어야 한다.

    guards 는 GuardFailure 를 던지고, 호출부가 그것을 받아 sys.exit 로 바꾼다.
    그 sys 가 없으면 방어는 '조용히 잘못된 예외로' 죽는다.
    """
    src = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    if "sys.exit" in src:
        assert "import sys\n" in src or "import json, hashlib, sys\n" in src, (
            "sys.exit 를 쓰면서 sys 를 import 하지 않았다 "
            "(import sys as _sys 는 경로 삽입용이라 별개다)")

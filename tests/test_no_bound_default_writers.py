"""경로를 **기본 인자**로 받아 파일을 **쓰는** 함수가 없다.  (Zm27 · DECISIONS §572)

IN    tools/ · src/ 의 파이썬 소스
OUT   없음 (검사)
PARAM 없음
밖    읽기만 하는 함수는 안 본다(`root=ROOT` 로 트리를 훑는 프로브 서른 남짓은 틀려도 잘못 **읽을** 뿐이다). `subprocess` 는 안 본다.

★ 왜 — 기본 인자는 **정의 시점**에 묶인다. 시험이 `module.OUT = tmp` 로 바꿔도 `def write(p=OUT)` 는 진짜 경로로 간다.
  `tools/evalset.py` 의 `write()` 가 그랬고, 합성 데이터가 실제 평가셋 자리에 박혔다(§571). 같은 꼴이 쓰는 함수에 있으면 시험이 돌 때마다
  진짜 산출물을 덮을 수 있다. 쓰는 함수는 `p: Path | None = None` 으로 받고 **호출 시점에** 모듈 전역을 읽는다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRITES = {"write_text", "write_bytes", "unlink", "rename", "replace", "mkdir", "touch", "to_csv", "to_file", "dump",
          "rmtree", "copy", "copy2", "move", "rmdir", "remove", "symlink_to", "chmod"}
FILES = sorted(p for d in ("tools", "src") for p in (ROOT / d).rglob("*.py"))


def _path_names(tree: ast.Module) -> set[str]:
    """모듈 전역에서 경로로 묶인 이름. `firelane.paths` 에서 들여온 것 · `Path(...)`/`a / b`/`__file__` 에서 만든 것."""
    env: set[str] = set()
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module and n.module.endswith("paths"):
            env |= {a.asname or a.name for a in n.names}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            u = ast.unparse(n.value)
            if ("Path(" in u or "__file__" in u or isinstance(n.value, ast.BinOp) and isinstance(n.value.op, ast.Div)
                    or isinstance(n.value, ast.Name) and n.value.id in env):
                env.add(n.targets[0].id)
    return env


def _is_pathish(d: ast.AST, env: set[str]) -> bool:
    if isinstance(d, ast.Name):
        return d.id in env
    if isinstance(d, ast.BinOp):
        return isinstance(d.op, ast.Div)
    return isinstance(d, ast.Call) and getattr(d.func, "id", getattr(d.func, "attr", "")) in ("Path", "PurePath")


def _writes(fn: ast.AST) -> set[str]:
    out = set()
    for c in ast.walk(fn):
        if isinstance(c, ast.Call):
            f = c.func
            nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if nm in WRITES:
                out.add(nm)
            if nm == "open" and len(c.args) > 1 and isinstance(c.args[1], ast.Constant) and any(x in str(c.args[1].value) for x in "wax"):
                out.add("open(w)")
    return out


def offenders(source: str) -> list[tuple[str, str, list[str]]]:
    tree = ast.parse(source)
    env = _path_names(tree)
    out = []
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            a = fn.args
            pos = a.posonlyargs + a.args
            ds = list(zip(pos[len(pos) - len(a.defaults):], a.defaults, strict=True)) + [(k, d) for k, d in zip(a.kwonlyargs, a.kw_defaults, strict=True) if d is not None]
            bound = [arg.arg for arg, d in ds if _is_pathish(d, env)]
            w = _writes(fn)
            if bound and w:
                out.append((fn.name, ",".join(bound), sorted(w)))
    return out


def test_the_detector_sees_the_evalset_bug_shape() -> None:
    """판별식이 살아 있다 — Zm26 이전 `evalset.write()` 꼴을 잡는다."""
    bad = "from pathlib import Path\nOUT = Path('x') / 'y'\ndef write(t, csv_path: Path = OUT):\n    csv_path.write_text(t)\n"
    good = "from pathlib import Path\nOUT = Path('x') / 'y'\ndef write(t, csv_path=None):\n    (OUT if csv_path is None else csv_path).write_text(t)\n"
    ro = "from pathlib import Path\nROOT = Path('x')\ndef scan(root: Path = ROOT):\n    return list(root.glob('*'))\n"
    assert offenders(bad) and not offenders(good) and not offenders(ro)


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_function_writes_through_a_path_bound_at_definition_time(path: Path) -> None:
    found = offenders(path.read_text(encoding="utf-8"))
    assert not found, f"{path.relative_to(ROOT)}: 기본 인자로 묶인 경로에 쓰는 함수 — {found}. `None` 으로 받고 호출 시점에 읽어라(§571)"


def test_restore_stale_reads_its_root_at_call_time() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import inspect

    import tidy
    assert inspect.signature(tidy.restore_stale).parameters["root"].default is None, "restore_stale 이 ROOT 를 정의 시점에 묶었다"

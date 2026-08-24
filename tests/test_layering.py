#!/usr/bin/env python3
"""
test_layering.py — 계층 방향을 import 로 강제한다.

★ 왜 테스트인가.
  이 저장소는 계보·판정·문서·인코딩을 전부 테스트로 강제하면서
  **구조만 강제자가 없었다.** 그래서 `seg/graph.py` 가 `paths.PROCESSED` 를
  그냥 import 했고(2026-08-21 제거), 아무도 몰랐다. 규약을 README 에
  적어두는 것은 강제가 아니다 — 다음 사람은 README 를 안 읽고 import 를 친다.

계층 (위가 아래를 안다. 역방향 금지)

    pipeline        DAG · 계보 · 단계 호출
    stage           ingest · segments · streetlight · terrain · ortho · publish_web
    adapter         seg/report · krgis · ngi · ngii1k · quiet_gdal · segkey
    domain          seg/params · seg/geom · seg/width · seg/roadname
                    seg/basisno · seg/graph          ← 순수. I/O 없음
    infra           paths                            ← 아무도 의존받지 않는다

`seg/report.py` 가 domain 이 아닌 이유: 하는 일이 산출물 쓰기다. 이름이
`seg/` 아래 있을 뿐 어댑터다. 옮기는 것은 별건이고, 지금은 예외로 명시한다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "firelane"

# 순수해야 하는 모듈. I/O 도 경로도 몰라야 한다.
DOMAIN = [
    "seg/params.py", "seg/geom.py", "seg/width.py",
    "seg/roadname.py", "seg/basisno.py", "seg/graph.py",
]

# domain 이 절대 import 하면 안 되는 것
FORBIDDEN = {"firelane.paths", "firelane.guards", "firelane.lineage",
             "firelane.pipeline", "firelane.contract", "firelane.datalog"}


def _imports(path: Path) -> set[str]:
    """최상위·함수 안을 가리지 않고 이 파일이 하는 모든 import."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


@pytest.mark.parametrize("rel", DOMAIN)
def test_domain_모듈은_인프라를_모른다(rel):
    got = _imports(PKG / rel)
    bad = sorted(m for m in got if m in FORBIDDEN
                 or any(m.startswith(f + ".") for f in FORBIDDEN))
    assert not bad, (
        f"{rel} 가 상위 계층을 import 한다: {bad}\n"
        f"  순수 모듈은 경로를 모른다. 쓸 곳은 호출자가 인자로 준다.\n"
        f"  (예: access_corridor(..., out_dir=OUT) — 2026-08-21)"
    )


@pytest.mark.parametrize("rel", DOMAIN)
def test_domain_모듈은_파일을_쓰지_않는다(rel):
    """`to_file` · `write_text` · `open(...,'w')` 이 domain 에 있으면 계층 붕괴다."""
    src = (PKG / rel).read_text(encoding="utf-8")
    tree = ast.parse(src)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("to_file", "write_text", "write_bytes", "to_csv"):
                # out_dir 를 인자로 받아 쓰는 것은 허용 — 경로를 아는 게 아니다
                if not any(
                    isinstance(a, ast.Name) and "dir" in a.id
                    or isinstance(a, ast.BinOp)
                    and isinstance(a.left, ast.Name) and "dir" in a.left.id
                    for a in node.args
                ):
                    bad.append(f"{node.func.attr}() @ line {node.lineno}")
    assert not bad, f"{rel} 가 자기가 정한 경로에 쓴다: {bad}"


def test_sys_path_해킹이_없다():
    """★ 2026-08-21 이전에는 17군데였다. 되돌아가면 여기서 죽는다."""
    hits = []
    for p in sorted(list(PKG.rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
                    + list((ROOT / "tools").rglob("*.py"))):
        if p.name == "test_layering.py":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            # ★ 2026-08-23. 주석은 뺀다. 이 규칙을 **왜 만들었는지** 설명하려면
            #   그 이름을 써야 하는데, 그것까지 잡으면 자기 문서를 자기가 막는다.
            #   같은 문제를 `markers.js` 팝업 검사에서도 겪었다.
            code = line.split("#", 1)[0]
            if "sys.path.insert" in code or "sys.path.append" in code:
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    assert not hits, (
        "sys.path 조작이 돌아왔다:\n  " + "\n  ".join(hits) +
        "\n  패키지이므로 필요 없다. `uv pip install -e .` 한 번이면 된다."
    )


def test_순환_의존이_없다():
    """firelane 안에서 서로를 import 하는 사이클을 찾는다."""
    graph: dict[str, set[str]] = {}
    for p in sorted(PKG.rglob("*.py")):
        mod = "firelane." + str(p.relative_to(PKG).with_suffix("")).replace("/", ".")
        mod = mod.removesuffix(".__init__")
        graph[mod] = {m for m in _imports(p) if m.startswith("firelane")}

    seen, stack, cycles = set(), [], []

    def walk(node):
        if node in stack:
            cycles.append(" → ".join(stack[stack.index(node):] + [node]))
            return
        if node in seen:
            return
        seen.add(node)
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            walk(nxt)
        stack.pop()

    for m in sorted(graph):
        walk(m)
    assert not cycles, "순환 의존:\n  " + "\n  ".join(sorted(set(cycles)))

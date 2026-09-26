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

IN    src/firelane/**.py · tests/**.py · tools/**.py
OUT   없음 (검사)
밖    **`tools/*.sh` 여섯은 안 본다.** 계층은 `import` 방향으로만 정의돼 있고
      셸에는 import 가 없다. 셸이 파이썬 단계를 **호출**하는 것은 배선이지
      계층 위반이 아니며, 그 배선은 `test_tools_are_wired` 소관이다.
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
    """최상위·함수 안을 가리지 않고 이 파일이 하는 모든 import.

    ★ 2026-09-24 (DECISIONS §244). 종전에는 `from firelane import paths` 를
      **`firelane` 하나로만** 기록했다. `FORBIDDEN` 에 든 것은
      `firelane.paths` 라서 **영영 안 걸린다** — 이 시험 열넷이 초록인 채로
      판정 도메인 전체가 `paths` 에 매여 있었다. `seg/params.py:24` 가
      정확히 그 꼴이다.

    ★ **같은 저장소가 같은 문제를 이미 올바르게 풀어놨다** —
      `src/firelane/shardseal.py::code_closure` 는 `from X import Y` 를
      `X.Y` 로 푼다. AST 순회기가 두 벌인데 봉인용은 맞고 계층 강제용은
      틀렸던 것이다. 2족(정본이 둘)이 **도구 안에서** 난 자리다.

    ★ 상대 import(`from . import x`)는 `node.level > 0` 이라 `node.module`
      만으로는 대상을 모른다. 이 저장소의 `src/firelane` 은 상대 import 를
      안 쓰지만, 쓰기 시작하면 조용히 빠져나가므로 **모르면 적어 둔다**.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:                      # `from . import x` — 대상 불명
                out.add(f"<relative level={node.level}>")
                continue
            if not node.module:
                continue
            out.add(node.module)
            # `from firelane import paths` → `firelane.paths` 도 센다
            out |= {f"{node.module}.{a.name}" for a in node.names}
    return out


def test_the_import_collector_reads_from_x_import_y():
    """**판별식이 살아 있는가.** 합성 소스로 직접 문다.

    ★ 위 시험들은 지금 초록이다. 초록인 검사는 제가 보고 있다는 것을 스스로
      증명하지 못한다 — 그 상태로 이 수집기가 석 달을 살았다.
    """
    import tempfile
    cases = {
        "from firelane import paths": "firelane.paths",
        "from firelane.seg import params": "firelane.seg.params",
        "import firelane.paths": "firelane.paths",
        "from firelane import paths as p": "firelane.paths",
    }
    with tempfile.TemporaryDirectory() as d:
        for src, want in cases.items():
            f = Path(d) / "x.py"
            f.write_text(src + "\n", encoding="utf-8")
            assert want in _imports(f), f"{src!r} 에서 {want} 를 못 읽는다"
        f = Path(d) / "y.py"
        f.write_text("from . import sibling\n", encoding="utf-8")
        assert any(s.startswith("<relative") for s in _imports(f)), \
            "상대 import 를 모른다고 적지 않는다 — 조용히 빠져나간다"


#: 아직 못 걷은 위반. **늘리지 마라.** 사유와 닫는 조건을 같이 적는다.
#: ★ 2026-09-24 (DECISIONS §244). 수집기의 구멍을 막자마자 `seg/params.py` 가
#:   드러났다 — 환경 스위치 다섯을 import 시점에 읽고 있었다. 그 배치는
#:   「폐포 안이라 산출물 불변을 증명할 수 없다」며 면제로 적었다.
#: ★ **2026-09-25 (DECISIONS §249). 비었다.** 그 전제가 틀렸다 — `segments`
#:   단계는 `data/raw` 를 안 읽으므로 레이크 없이도 재실행된다. 다섯을
#:   단계층으로 올리고 판정 산출물 다섯이 바이트 동일함을 확인했다.
#:   비어 있는 것이 정상이다. 채우려거든 사유와 **닫는 조건**을 같이 적어라.
EXEMPT: dict[str, str] = {}


@pytest.mark.parametrize("rel", DOMAIN)
def test_domain_모듈은_인프라를_모른다(rel):
    got = _imports(PKG / rel)
    bad = sorted(m for m in got if m in FORBIDDEN
                 or any(m.startswith(f + ".") for f in FORBIDDEN))
    if rel in EXEMPT:
        assert bad, (
            f"{rel} 이 EXEMPT 에 있는데 **이미 깨끗하다** — 줄을 지워라.\n"
            f"  면제가 낡으면 그 자리가 사각지대가 된다"
        )
        return
    assert not bad, (
        f"{rel} 가 상위 계층을 import 한다: {bad}\n"
        f"  순수 모듈은 경로를 모른다. 쓸 곳은 호출자가 인자로 준다.\n"
        f"  (예: access_corridor(..., out_dir=OUT) — 2026-08-21)"
    )


def test_exempt_entries_are_real_and_reasoned():
    """면제가 실재하는 모듈을 가리키고 사유를 갖는가."""
    ghost = sorted(r for r in EXEMPT if r not in DOMAIN)
    blank = sorted(r for r, why in EXEMPT.items() if len(why.strip()) < 40)
    assert not ghost and not blank, f"DOMAIN 밖 {ghost} · 사유가 빈약함 {blank}"


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
                    (isinstance(a, ast.Name) and "dir" in a.id)
                    or (isinstance(a, ast.BinOp)
                    and isinstance(a.left, ast.Name) and "dir" in a.left.id)
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

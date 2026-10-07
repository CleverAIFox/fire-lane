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
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "firelane"

# 순수해야 하는 모듈. I/O 도 경로도 몰라야 한다.
# ★ 2026-09-28 (DECISIONS §279-8 · PLAN #122). 판정 모듈 셋이 **조용히 빠져
#   있었다** — `seg/vehicle.py` · `seg/scope.py` · `seg/centerline_correction.py`.
#   `report.py` 는 제외 사유가 적혀 있었는데 이 셋은 사유도 없이 없었다.
#   목록에 없으면 위반해도 아무도 모른다 — 실제로 하나가 위반 중이었다.
DOMAIN = [
    "seg/params.py", "seg/geom.py", "seg/width.py",
    "seg/roadname.py", "seg/basisno.py", "seg/graph.py",
    "seg/vehicle.py", "seg/scope.py", "seg/centerline_correction.py",
    # ★ 2026-10-03 (DECISIONS §370-4). `seg/classify.py` 가 **또 빠져 있었다.**
    #   §303 이 2026-09-29 에 만들고 판정 폐포에 넣었는데 이 목록에는 안 들어왔다 —
    #   §279-8 이 나흘 전 똑같이 셋을 잡았고, **같은 일이 다시 났다.** 손목록이라
    #   아무도 안 세는 것이 원인이고, 그래서 아래
    #   `test_domain_목록이_판정_폐포를_다_덮는다` 가 분모를 **유도**로 바꿨다.
    #   실측하면 이 파일은 순수하다 — 두 도메인 모듈만 import 하고 I/O 가 0 이다.
    "seg/classify.py",
    # ★ 2026-10-01 (DECISIONS §342). 중개자의 명부. 소켓도 시계도 몰라야
    #   하고, 그래야 시험이 서버 없이 돈다 — 실제로 `tests/test_ops_roster.py` 의
    #   판별식 열셋이 서버를 안 띄우고 돈다.
    "ops/roster.py",
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


# ── 도메인이 **저장소를 직접 읽는가** (2026-09-28 · DECISIONS §279-8) ──────
# ★ 위 검사는 **import 만** 본다. `seg/vehicle.py` 는 `firelane.paths` 를 안
#   부르고도 계층을 깬다 — `Path(__file__).resolve().parents[3]` 으로 **제
#   루트를 손수 계산해** `sources.yaml` 을 읽는다. import 가 없으니 조용히
#   통과했고, PLAN #122 가 그것을 두 달 들고 있었다.
#
# ★ 금지는 import 가 아니라 **행위**다. 도메인은 파일을 안 읽는다 — 값은
#   인자로 받는다. TS 쪽이 이미 그 모양이다(`domain/vehicle.ts` 는 `spec` 을
#   받는다).
def _code(src: str) -> str:
    """주석과 **문자열 리터럴**을 지운 소스. 자리는 그대로 둔다.

    ★ 2026-10-08 (DECISIONS §431). 이 판별식들은 **글자로** 센다. 그래서
      「종전에는 `Path(__file__).resolve().parents[3]` 로 읽었다」라고 적은
      **설명 주석 한 줄**이 그 파일을 영원히 위반으로 만든다 — 고쳤는데도.

      같은 병의 네 번째다: §398-3(`# ci-exempt:` 주석) · §425-6(`scope` 줄) ·
      §430-4(래칫이 제 설명문을 셌다). 그때마다 **그 자리만** 고쳤다.
      여기서는 줄 단위가 아니라 **토큰 단위**로 지운다 — 여러 줄 문자열도
      먹으므로 머리말 안의 코드 예시가 더는 안 걸린다.
    """
    import io
    import tokenize

    rows = src.splitlines(keepends=True)

    def blank(start: tuple[int, int], end: tuple[int, int]) -> None:
        (r1, c1), (r2, c2) = start, end
        for r in range(r1, r2 + 1):
            line = rows[r - 1]
            s = c1 if r == r1 else 0
            e = c2 if r == r2 else len(line.rstrip("\n"))
            rows[r - 1] = line[:s] + " " * max(0, e - s) + line[e:]

    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                blank(tok.start, tok.end)
    except (tokenize.TokenError, IndentationError):
        return src          # ★ 못 읽으면 **안 봐준다** — 원문 그대로 본다
    return "".join(rows)


_OWN_ROOT = re.compile(r"Path\(__file__\)\.resolve\(\)\.parents\[")
# ★ 읽기 호출만 본다. 파서 이름()은 안 적는다 — 「대장 직접 로드」
#   래칫이 **글자로** 세는 탐지기라 이 파일이 그 목록에 들어가 버린다.
_READS = re.compile(r"\.read_text\(|\.read_bytes\(|\bopen\(")

#: 사유를 적으면 면제. **빈 사유는 금지**이고, 깨끗해지면 「낡았다」로 운다.
#: ★ 2026-10-08 (DECISIONS §431). **비었다.** `seg/vehicle.py` 를 고쳤다 —
#:   도메인이 더는 파일을 안 읽고 `use()` 로 주입받는다(PLAN #122 닫힘).
#:   비어 있는 것이 정상이고, 채우려면 **사유를 적어야** 한다.
READS_EXEMPT: dict[str, str] = {}


@pytest.mark.parametrize("rel", DOMAIN)
def test_domain_모듈은_저장소를_직접_안_읽는다(rel):
    src = _code((PKG / rel).read_text(encoding="utf-8"))
    bad = []
    if _OWN_ROOT.search(src):
        bad.append("제 루트를 손수 계산한다 (`parents[...]`)")
    if _READS.search(src):
        bad.append("파일을 읽는다")
    if rel in READS_EXEMPT:
        assert bad, (f"{rel} 이 READS_EXEMPT 에 있는데 **이미 깨끗하다** — 줄을 지워라.\n"
                     "  면제가 낡으면 그 자리가 사각지대가 된다")
        assert READS_EXEMPT[rel].strip(), f"{rel} 의 면제에 사유가 없다"
        return
    assert not bad, (
        f"{rel} 이 도메인인데 {' · '.join(bad)}.\n"
        "  도메인은 값을 **인자로 받는다** — 읽는 것은 인프라의 일이다.\n"
        "  못 고치면 READS_EXEMPT 에 **사유와 함께** 적어라.")


def test_reads_exempt_has_no_ghost():
    """없는 파일을 면제하고 있으면 목록이 낡은 것이다. 양방향이다."""
    ghost = sorted(r for r in READS_EXEMPT if r not in DOMAIN)
    assert not ghost, f"DOMAIN 에 없는 것을 면제한다 — {ghost}"


#: `DOMAIN` 이 아닌 것의 사유. **판정 폐포 안인데 순수가 아닌 자리**다.
#: ★ 빈 사유는 금지다. 그리고 아래 검사가 **양방향**이다 — 깨끗해지면 운다.
NOT_DOMAIN: dict[str, str] = {
    "segments.py":
        "stage 다. 파일을 읽고 쓰고 단계로 돈다 — 계층표의 그 자리이고 "
        "조립부가 순수할 수는 없다",
    "segkey.py":
        "adapter 다. seg_uid 를 만들려면 좌표계와 자리수 규약을 알아야 하고 "
        "그것은 바깥 약속이다(계층표에 그렇게 적혀 있다)",
    "seg/report.py":
        "adapter 다. 하는 일이 **산출물 쓰기**이고 이름이 `seg/` 아래 있을 뿐이다 "
        "— 이 파일 머리말이 그 사유를 이미 적는다. 옮기는 것은 별건이다",
    "paths.py":
        "infra 다. 계층표의 맨 아래이고 **아무도 의존받지 않는다** — 도메인이 "
        "이것을 모르는 것이 규칙의 내용이다(`FORBIDDEN`)",
    "guards.py":
        "infra 다. 직접 호출 경고 · 환경 점검을 들고 `FORBIDDEN` 에 들어 있다 "
        "— 도메인이 알면 안 되는 쪽이다",
    "__init__.py":
        "꾸러미 선언이다. 값을 안 내보내고 import 도 없다 — 순수할 것도 "
        "안 순수할 것도 없다",
    "seg/__init__.py":
        "같은 사유다. 꾸러미 선언이고 비어 있다 — 폐포가 꾸러미를 타고 들어오니 "
        "여기 뜨는 것이 맞고, 뜨는 것과 순수한 것은 다른 물음이다",
}


def _judgment_closure() -> list[str]:
    """판정 폐포를 **유도로** 낸다. 손으로 안 적는다."""
    from firelane.shardseal import code_closure
    clo = {q.resolve() for q in code_closure("firelane.segments")}
    return sorted(q.relative_to(PKG).as_posix()
                  for q in PKG.rglob("*.py") if q.resolve() in clo)


def test_domain_목록이_판정_폐포를_다_덮는다():
    """★ **분모를 유도로 바꾼다.** (DECISIONS §370-4)

    ── 왜 생겼나 ───────────────────────────────────────────────
    `DOMAIN` 은 손목록이다. §279-8(2026-09-28)이 「판정 모듈 셋이 **조용히
    빠져 있었다**」를 잡고 사유까지 적었는데, **나흘 뒤 같은 일이 또 났다** —
    §303 이 `seg/classify.py` 를 만들어 판정 폐포에 넣었고 이 목록에는 안
    들어왔다. 그 파일은 순수하므로 위반은 아니었지만, **위반이어도 아무도
    몰랐다.** 손목록의 결함은 틀린 항목이 아니라 **빠진 항목**이다.

    ★ 그래서 분모를 `code_closure("firelane.segments")` 로 **유도한다.**
      폐포에 새 파일이 들어오면 `DOMAIN` 이든 `NOT_DOMAIN` 이든 **어느
      한쪽에 적어야** 통과한다 — 결정이 조용히 미뤄지는 길이 닫힌다.
      `deadcheck` 의 ② 손목록 프로브가 무는 그 병이다.

    ★ **양방향이다.** `NOT_DOMAIN` 이 폐포 밖 파일을 들고 있으면 그것도 운다 —
      낡은 면제는 사각지대이고, 그 사실을 §259-2 가 이미 적었다.
    """
    clo = _judgment_closure()
    assert len(clo) > 10, f"폐포를 {len(clo)}개밖에 못 셌다 — 분모가 죽었다"
    miss = [r for r in clo if r not in DOMAIN and r not in NOT_DOMAIN]
    assert not miss, (
        "판정 폐포 안인데 `DOMAIN` 도 `NOT_DOMAIN` 도 아닌 파일:\n  "
        + "\n  ".join(miss)
        + "\n  ★ 순수하면 `DOMAIN` 에, 아니면 `NOT_DOMAIN` 에 **사유와 함께** 적어라."
        + "\n    적지 않으면 그 파일은 계층 검사 **밖**에서 산다 — §303 이 만든"
        + "\n    `seg/classify.py` 가 나흘을 그렇게 살았다(§370-4).")
    ghost = [r for r in NOT_DOMAIN if r not in clo]
    assert not ghost, (
        f"`NOT_DOMAIN` 이 판정 폐포 밖 파일을 든다: {ghost}\n"
        "  낡은 면제는 사각지대다 — 지워라(§259-2).")
    thin = [r for r, w in NOT_DOMAIN.items() if len(w.strip()) < 30]
    assert not thin, f"사유가 너무 짧다 — 왜 순수가 아닌가: {thin}"


def test_the_reader_detector_does_not_read_its_own_explanation():
    """★ **카나리아.** 주석·머리말 속 코드 예시는 위반이 아니다.  (DECISIONS §431)

    고친 모듈은 「종전에는 `parents[3]` 으로 읽었다」를 머리말에 들고 있다.
    그것이 위반으로 잡히면 이 판별식은 **제 설명문을 세는** 것이다 —
    §398-3 · §425-6 · §430-4 에 이은 네 번째가 된다.
    """
    src = '''"""머리말 — 종전에는 Path(__file__).resolve().parents[3] 로 읽었다."""
# 주석에서도 p.read_text() 를 말할 수 있다
X = 1
'''
    out = _code(src)
    assert not _OWN_ROOT.search(out), "머리말의 코드 예시를 셌다"
    assert not _READS.search(out), "주석의 읽기 언급을 셌다"
    # ★ 반대 방향 — 진짜 코드는 여전히 잡는다
    assert _READS.search(_code("v = p.read_text()\n")), "진짜 읽기를 놓친다"
    assert _OWN_ROOT.search(_code("R = Path(__file__).resolve().parents[3]\n")), \
        "진짜 루트 계산을 놓친다"

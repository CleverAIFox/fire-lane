"""시험 안에서 **파일이 없으면 조용히 넘어가는 갈래**를 정적으로 센다 — 그런 시험은 통과한 채 아무것도 안 잰다.  (PLAN #215)

★ 왜 생겼나. skip 그물(`tests/skip_policy.py`)은 **사유 어휘**만 덮는다. 시험 함수 안 `if not p.exists(): continue` 는 skip 도 아니고 사유도 없다 — 추적 파일을 지우거나 이름을 바꿔도
  시험이 초록인 채 그 파일을 안 본다(2026-11-11 읽어 보니 PLAN 이 센 12곳 중 **9곳이 그랬다** · 전부 추적 파일이었다. 이 검사가 헬퍼까지 훑자 **다섯이 더** 나왔다 — 넷은 같은 결함이라 고쳤고 하나는 `rglob` 결과의 디렉터리를 거르는 것이라 사유를 적었다). 나머지 셋은 「있다」가 통과 조건인 `if … exists(): continue` 라 조용한 갈래가 아니다.
  고친 것: 추적 파일이면 `assert` 로 시끄럽게 · 정당한 조용한 갈래(생성물이 없는 기계가 정상이다 등)는 그 줄에 `# silent-ok: <사유>` 를 적는다.

IN    `tests/test_*.py` 전부(AST) · `if not <경로>.exists()/is_file()/is_dir():` 이고 몸통이 `continue` · `pass` · 값 없는 `return` 뿐이며 `else` 가 없는 것
OUT   없음 (검사)
PARAM `SILENT_OK_MARK` — 면제 표식. 사유는 다섯 글자 이상(`gate_parity` 의 `ci-exempt` 와 같은 규율)
밖    **다른 모양의 조용한 갈래는 못 센다** — `try/except OSError: pass` · `if not text: return` · `glob` 이 빈 목록을 돌려 루프가 0번 도는 것 · 헬퍼(`_read()` 가 없으면 빈 문자열)가 삼키는 것.
      「부정 존재 검사 + 조용한 몸통」 한 모양이다 — 하한이다. 시험 함수가 아닌 모듈 수준 코드와 `tests/` 밖(`tools/`)의 검사기는 안 본다.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SILENT_OK_MARK = "# silent-ok:"
_EXISTS = {"exists", "is_file", "is_dir"}


def _negated_exists(test: ast.expr) -> bool:
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        c = test.operand
        return isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in _EXISTS
    return False


def _silent(body: list[ast.stmt]) -> bool:
    return all(isinstance(b, (ast.Continue, ast.Pass)) or (isinstance(b, ast.Return) and b.value is None) for b in body)


def silent_branches(source: str) -> list[int]:
    """순수 함수 — 조용한 갈래의 줄 번호. `# silent-ok: 사유`(다섯 글자 이상)가 그 줄이나 몸통 첫 줄에 있으면 센 것에서 뺀다."""
    lines = source.splitlines()
    out: list[int] = []
    for fn in ast.walk(ast.parse(source)):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.If) and _negated_exists(node.test) and _silent(node.body) and not node.orelse:
                tails = [ln.split(SILENT_OK_MARK, 1)[1].strip() for ln in lines[node.lineno - 1:node.body[0].lineno] if SILENT_OK_MARK in ln]
                if not any(len(t) >= 5 for t in tails):
                    out.append(node.lineno)
    return sorted(set(out))


def test_a_quiet_missing_file_branch_is_counted_and_a_loud_or_declared_one_is_not():
    quiet = "def test_x(p):\n    if not p.exists():\n        continue\n"
    assert silent_branches(quiet) == [2]
    assert silent_branches("def test_x(p):\n    if not p.is_file():\n        return\n") == [2]
    assert silent_branches("def test_x(p):\n    assert p.exists(), 'x'\n") == []
    assert silent_branches("def test_x(p):\n    if not p.exists():\n        pytest.skip('x')\n") == []        # skip 은 그물이 문다
    assert silent_branches("def test_x(p):\n    if p.exists():\n        continue\n") == []                    # 「있다」가 통과 조건
    assert silent_branches("def test_x(p):\n    if not p.exists():  # silent-ok: 생성물이 없는 기계가 정상이다\n        continue\n") == []
    assert silent_branches("def test_x(p):\n    if not p.exists():  # silent-ok: 네\n        continue\n") == [2], "사유가 짧으면 면제가 아니다"
    assert silent_branches("def test_x(p):\n    if not p.exists():\n        continue\n    else:\n        pass\n") == []


def test_no_test_silently_passes_when_a_file_it_reads_is_missing():
    """이 저장소 전수 — 조용한 갈래는 **0** 이다(고치기 전 시험 함수 9 · 헬퍼까지 14). 새로 생기면 여기서 빨개진다."""
    bad = [f"{p.name}:{n}" for p in sorted(TESTS.glob("test_*.py")) for n in silent_branches(p.read_text(encoding="utf-8"))]
    assert not bad, ("파일이 없으면 조용히 넘어가는 갈래가 있다 — 추적 파일이면 `assert p.exists(), …` 로 시끄럽게, 정당하면 줄에 `# silent-ok: 사유` 를 적어라:\n  "
                     + "\n  ".join(bad))

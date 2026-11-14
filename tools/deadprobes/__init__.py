"""`deadcheck` 의 프로브 중 **본체가 큰 것**. 진입점은 `tools/deadcheck.py` 하나다.

★ 2026-10-03 (DECISIONS §359). `deadcheck.py` 는 1,101줄 예외를 들고 있고 그
  사유가 「면제표는 사유가 본체다」였다. 그 사유는 **표**를 두고 한 말이지
  프로브 몸통을 두고 한 말이 아니다. 그래서 몸통은 여기로 내린다 —
  `tools/docfsck/` 가 먼저 쓴 꼴이다(프로브 하나가 파일 하나).

★ 면제표와 양성 대조는 `deadcheck.py` 에 남는다. 그 둘은 **프로브 목록 옆에
  있어야** 「면제했는데 실은 안 걸리는 것」을 한눈에 본다.

밖    판정은 안 한다 — 이 묶음은 자리이지 검사가 아니다.
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
"""
from __future__ import annotations

import ast

_BIG = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_WALKED: dict[int, tuple[ast.AST, list[ast.AST]]] = {}


def walk(n: ast.AST):
    """`ast.walk` 와 **같은 결과·같은 순서** — 노드마다 한 번 펼쳐 기억한다.

    ★ 2026-11-14 (PLAN ㉕ B-③). 프로브 다섯이 같은 나무를 제각기 다시 걸었다 — 단독 8.7초 중 `ast.walk` 가 절반이었다.
      함수 노드(`_entry_reads` 3,102번 · `_scans` 678번)는 모듈 뿌리 캐시를 못 탔다. 노드를 강한 참조로 붙들어
      `id` 재사용이 없다(`[0] is n`). 걸리는 것이 같으니 **검사는 그대로고 걷는 값만 준다.**
    """
    if not isinstance(n, _BIG):
        return ast.walk(n)      # 작은 노드는 기억해도 되돌려 받는 일이 드물다 — 실측에서 기억이 더 느렸다(git 프로브 1.1 → 1.8초)
    hit = _WALKED.get(id(n))
    if hit is None or hit[0] is not n:
        hit = _WALKED[id(n)] = (n, list(ast.walk(n)))
    return iter(hit[1])

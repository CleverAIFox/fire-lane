#!/usr/bin/env python3
"""
dupcheck.py — **같은 것이 몇 벌인가.** 232 감사가 못 센 축.

    uv run python tools/dupcheck.py              전수
    uv run python tools/dupcheck.py --min 40     더 큰 함수만
    uv run python tools/dupcheck.py --json       기계용
    uv run python tools/dupcheck.py --selftest   ★ 프로브가 살아 있나

── 왜 ─────────────────────────────────────────────────────────
원칙 ⑥ — **감사 건수는 하한이다.** 232 는 사람이 눈으로 센 값이고
B3 에서 이미 어긋났다. 규칙 조립이 3벌이 아니라 4벌이었고, 색 사본
5벌 중 둘은 사본이 아니었다.

사본 찾기를 사람 눈에 맡기면 그 오차가 매번 난다. 이름이 다르면
안 보이고(`sha` · `sha256` · `_sha`), 파일이 멀면 안 보인다.

★ **이름이 아니라 구조를 본다.** 함수 본문을 AST 로 파싱해 식별자와
  인자 이름을 전부 `_` 로 지우고 정규화한 뒤 지문을 낸다. 그래서
  `def sha(p)` 와 `def _sha(path)` 가 같은 군으로 묶인다.

★ 도크스트링은 빼고 센다. 설명이 다르다고 다른 구현이 아니다.

★ **작은 함수는 안 센다.** 세 줄짜리 래퍼는 어디나 같게 생겼고
  합치면 오히려 읽기 나빠진다. 기본 문턱은 AST 노드 25개다.

── 이 도구가 하는 판정 ────────────────────────────────────────
★ **아무 판정도 안 한다.** 같은 구조가 몇 벌 있는지만 센다.
  합칠 것인가는 사람이 정한다 — 우연히 같은 것이 있고(§144 등거리 근사),
  일부러 갈라 둔 것이 있다(계층 경계를 넘지 않으려고 벌린 복사).
  분모를 세는 것이 이 도구의 일이고, 분자를 줄이는 것은 사람의 일이다.

IN    src/**/*.py · tools/*.py
OUT   종료코드 = 사본군 수
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"batches", "__pycache__", ".venv", "node_modules"}


class _Blank(ast.NodeTransformer):
    """식별자·인자 이름을 지운다. **상수는 남긴다** — 값이 다르면 다른 것이다."""

    def visit_Name(self, node: ast.Name) -> ast.Name:
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg, node.annotation = "_", None
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
        self.generic_visit(node)
        return node


def _fingerprint(fn: ast.FunctionDef) -> tuple[str, int] | None:
    body = [x for x in fn.body
            if not (isinstance(x, ast.Expr) and isinstance(x.value, ast.Constant))]
    if not body:
        return None
    size = sum(1 for _ in ast.walk(ast.Module(body=body, type_ignores=[])))
    try:
        norm = [_Blank().visit(ast.parse(ast.unparse(x)).body[0]) for x in body]
        text = ast.unparse(ast.Module(body=norm, type_ignores=[]))
    except (SyntaxError, ValueError, RecursionError):
        return None
    return hashlib.md5(text.encode()).hexdigest(), size


def sources() -> list[Path]:
    out = []
    for pat in ("src/**/*.py", "tools/*.py"):
        out += [p for p in ROOT.glob(pat) if not SKIP & set(p.parts)]
    return sorted(out)


def groups(min_size: int) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for p in sources():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            fp = _fingerprint(node)
            if fp is None or fp[1] < min_size:
                continue
            buckets[fp[0]].append({"file": str(p.relative_to(ROOT)),
                                   "line": node.lineno, "name": node.name,
                                   "size": fp[1]})
    out = [{"n": len(v), "size": v[0]["size"], "members": v}
           for v in buckets.values() if len(v) > 1]
    return sorted(out, key=lambda g: (-g["n"], -g["size"]))


def selftest() -> int:
    """★ 0건은 저장소가 깨끗할 때도 나오고 프로브가 죽었을 때도 나온다."""
    bad = []
    src = ("def a(x):\n    t = 0\n    for i in x:\n        if i > 1:\n"
           "            t += i * 2\n        else:\n            t -= 1\n    return t\n"
           "def b(y):\n    s = 0\n    for j in y:\n        if j > 1:\n"
           "            s += j * 2\n        else:\n            s -= 1\n    return s\n"
           "def c(y):\n    s = 0\n    for j in y:\n        if j > 9:\n"
           "            s += j * 2\n        else:\n            s -= 1\n    return s\n")
    tree = ast.parse(src)
    fps = {f.name: _fingerprint(f) for f in tree.body
           if isinstance(f, ast.FunctionDef)}
    if fps["a"][0] != fps["b"][0]:
        bad.append("이름만 다른 같은 구현을 못 묶었다")
    if fps["a"][0] == fps["c"][0]:
        bad.append("상수가 다른데 같다고 했다 — 값을 지우고 있다")
    if not sources():
        bad.append("소스를 하나도 못 읽었다")
    for line in bad:
        print(f"  {line}")
    print("selftest " + ("빨강" if bad else "초록"))
    return len(bad)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=25, help="AST 노드 문턱")
    ap.add_argument("--max", type=int, default=None,
                    help="허용 상한. 넘으면 빨강. ★ 지금 값에서 시작해 내린다")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    gs = groups(a.min)
    if a.json:
        print(json.dumps(gs, ensure_ascii=False, indent=2))
        return min(len(gs), 255)

    dup_fns = sum(g["n"] for g in gs)
    print(f"사본군 {len(gs)} · 함수 {dup_fns} · 문턱 {a.min}노드\n")
    for g in gs:
        print(f"  ×{g['n']}  {g['size']}노드")
        for m in g["members"]:
            print(f"       {m['file']}:{m['line']}  {m['name']}")
    print("\n★ 합칠 것인가는 사람이 정한다. 이 도구는 분모만 센다(원칙 ⑥).")
    print("  계층을 넘지 않으려고 일부러 벌린 것이 있다 — 그것은 사본이 아니다.")
    if a.max is None:
        return min(len(gs), 255)
    # ★ 래칫. 지금 값을 상한으로 걸고 내려간다. 늘면 운다.
    #   0 을 요구하면 검사를 못 건다. 못 거는 검사는 없는 검사다.
    if len(gs) > a.max:
        print(f"\n✗ 사본군이 상한 {a.max} 을 넘었다 ({len(gs)}). 늘었다.")
        return min(len(gs) - a.max, 255)
    if len(gs) < a.max:
        print(f"\n★ 상한 {a.max} 보다 {a.max - len(gs)} 적다. "
              f"`--max {len(gs)}` 로 조여라 — 안 조이면 되돌아간다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

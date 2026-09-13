#!/usr/bin/env python3
"""
codepatch.py — 파이썬 소스 **멱등 편집기**. `docpatch` 의 코드판이다.

★ 왜 만들었나. B1 을 일회성 `python3 - <<PY` 정규식 치환으로 적용하다가
  `install_navi.py` 와 `pages_add_navi.py` 의 `main()` 본문을 통째로 날렸다.
  두 도구는 호출부가 0이라 테스트도 CI 도 그 파괴를 못 봤다.
  `docpatch` 머리말이 같은 병을 적는다 — "`docfix_20260817.py` 계열이
  일회성이라 **아홉 번 다시 만들어졌다**".

원칙 넷.
  ① 멱등        두 번 돌려도 같은 결과. 이미 있으면 건너뛴다
  ② dry-run 기본 `--apply` 없이는 아무것도 안 바꾼다
  ③ AST 로 판단  정규식으로 "어디에" 를 정하지 않는다
  ④ 손실 금지    편집 전후로 정의된 이름 집합을 대조한다.
                 하나라도 사라지면 **되돌리고 실패**한다

  ★ ④ 가 핵심이다. 정규식 치환의 위험은 "잘못 넣는 것" 이 아니라
    "조용히 지우는 것" 이다.

쓰는 쪽 예
    from codepatch import Patch
    p = Patch("tools/foo.py")
    p.add_function("check", SRC)              # main 앞에 넣는다
    p.add_flag("--check", "상태만 본다")       # argparse 에 넣는다
    p.route_flag("check", "return check()")   # parse_args 뒤에 분기
    p.commit(apply=True)
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PatchError(RuntimeError):
    pass


def _names(src: str) -> set[str]:
    """모듈이 정의하는 최상위 이름. 손실 대조의 기준이다."""
    t = ast.parse(src)
    out: set[str] = set()
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name):
                    out.add(tg.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
    return out


def _bodies(src: str) -> dict[str, int]:
    """함수별 본문 줄 수. **줄어든 것**만 손실이다.

    ★ 처음에는 이름 집합에 `main#41` 처럼 길이를 섞었다. 그러면 본문이
      **늘어난 것**도 손실로 잡혀 정상 편집이 전부 막혔다. 늘어남과
      줄어듦을 가른다 — 검사가 시끄러우면 사람이 끈다(DECISIONS §73).
    """
    t = ast.parse(src)
    return {n.name: (n.end_lineno or n.lineno) - n.lineno
            for n in ast.walk(t)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


class Patch:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path) if Path(path).is_absolute() else ROOT / path
        if not self.path.exists():
            raise PatchError(f"{self.path} 가 없다")
        self.orig = self.path.read_text(encoding="utf-8")
        self.text = self.orig
        self.log: list[str] = []
        self.skipped: list[str] = []

    # ── 판단 ────────────────────────────────────────────────────
    def has(self, name: str) -> bool:
        try:
            t = ast.parse(self.text)
        except SyntaxError:
            return False
        return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                   and n.name == name for n in t.body)

    def _anchor_main(self) -> int:
        """`def main` 의 시작 오프셋. 없으면 `if __name__`, 그것도 없으면 끝."""
        t = ast.parse(self.text)
        lines = self.text.splitlines(keepends=True)
        for n in t.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "main":
                # 데코레이터·주석 위까지 올라가지 않는다. def 줄이 앵커다
                return sum(len(x) for x in lines[:n.lineno - 1])
        m = re.search(r'^if __name__', self.text, re.M)
        return m.start() if m else len(self.text)

    # ── 편집 ────────────────────────────────────────────────────
    def add_function(self, name: str, source: str) -> Patch:
        """최상위 함수를 `main` 앞에 넣는다. 이미 있으면 건너뛴다(멱등)."""
        if self.has(name):
            self.skipped.append(f"{name}() 이미 있다")
            return self
        at = self._anchor_main()
        body = source if source.endswith("\n\n\n") else source.rstrip("\n") + "\n\n\n"
        self.text = self.text[:at] + body + self.text[at:]
        self.log.append(f"{name}() 추가 — {body.count(chr(10))}줄")
        return self

    def add_flag(self, flag: str, help_: str, *, after: str = "--apply") -> Patch:
        """argparse 인자를 넣는다. 이미 있으면 건너뛴다."""
        if f'"{flag}"' in self.text:
            self.skipped.append(f"{flag} 이미 있다")
            return self
        m = re.search(rf'^([ \t]*)[\w.]*\.add_argument\(\s*"{re.escape(after)}".*?\)\s*\n',
                      self.text, re.M | re.S)
        if not m:
            m = re.search(r'^([ \t]*)[\w.]*\.add_argument\(.*?\)\s*\n', self.text, re.M | re.S)
        if not m:
            raise PatchError(f"{self.path.name}: add_argument 앵커를 못 찾았다")
        ind, ap = m.group(1), re.search(r'(\w+)\.add_argument', m.group(0)).group(1)
        ins = (f'{ind}{ap}.add_argument("{flag}", action="store_true",\n'
               f'{ind}{" " * (len(ap) + 14)}help="{help_}")\n')
        self.text = self.text[:m.end()] + ins + self.text[m.end():]
        self.log.append(f"{flag} 인자 추가")
        return self

    def route_flag(self, attr: str, stmt: str, *, comment: str = "") -> Patch:
        """`parse_args()` 바로 뒤에 `if <ns>.<attr>: <stmt>` 를 넣는다."""
        m = re.search(r'^([ \t]*)(\w+)\s*=\s*[\w.]*\.parse_args\(\).*\n', self.text, re.M)
        if not m:
            raise PatchError(f"{self.path.name}: parse_args 앵커를 못 찾았다 "
                             f"— 인라인 호출이면 먼저 변수로 뺀다")
        ind, ns = m.group(1), m.group(2)
        if re.search(rf'if\s+{ns}\.{attr}\b', self.text):
            self.skipped.append(f"{attr} 분기 이미 있다")
            return self
        c = f"{ind}# {comment}\n" if comment else ""
        ins = f"{c}{ind}if {ns}.{attr}:\n{ind}    {stmt}\n"
        self.text = self.text[:m.end()] + ins + self.text[m.end():]
        self.log.append(f"{attr} 분기 추가")
        return self

    def hoist_parse_args(self) -> Patch:
        """`return run(apply=ap.parse_args().apply)` 처럼 인라인으로 쓰는 것을
        변수로 뺀다. 분기를 넣으려면 이름이 있어야 한다."""
        # ★ 줄머리 대입문만 인정한다. `run(apply=ap.parse_args().apply)` 의
        #   키워드 인자를 대입으로 오인해 호이스트를 건너뛰었다.
        if re.search(r'^[ \t]*\w+\s*=\s*[\w.]*\.parse_args\(\)\s*$',
                     self.text, re.M):
            return self
        m = re.search(r'^([ \t]*)(.*?)(\w+)\.parse_args\(\)\.(\w+)(.*)$',
                      self.text, re.M)
        if not m:
            raise PatchError(f"{self.path.name}: parse_args 를 못 찾았다")
        ind, pre, ns, attr, post = m.groups()
        new = (f"{ind}a = {ns}.parse_args()\n"
               f"{ind}{pre}a.{attr}{post}")
        self.text = self.text[:m.start()] + new + self.text[m.end():]
        self.log.append("parse_args() 를 변수로 뺐다")
        return self

    def sub_once(self, old: str, new: str, *, why: str) -> Patch:
        """정확 일치 1건만 바꾼다. 0건이면 건너뛰고, 2건 이상이면 죽는다."""
        n = self.text.count(old)
        if n == 0:
            self.skipped.append(f"{why} — 대상 없음(이미 적용?)")
            return self
        if n > 1:
            raise PatchError(f"{self.path.name}: `{old[:40]}` 가 {n}건이다. "
                             f"모호하면 안 바꾼다")
        self.text = self.text.replace(old, new, 1)
        self.log.append(why)
        return self

    # ── 확정 ────────────────────────────────────────────────────
    def commit(self, *, apply: bool) -> bool:
        rel = self.path.relative_to(ROOT)
        if self.text == self.orig:
            print(f"  = {rel}  변경 없음  {'· '.join(self.skipped) or ''}")
            return True
        # ③ 문법
        try:
            ast.parse(self.text)
        except SyntaxError as e:
            print(f"  ✗ {rel}  편집 결과가 구문 오류다 — {e.lineno}행")
            return False
        # ④ 손실 대조. 이것이 main() 본문을 날린 사고를 막는 자리다
        lost = _names(self.orig) - _names(self.text)
        if lost:
            print(f"  ✗ {rel}  **정의가 사라졌다** — {sorted(lost)[:6]}")
            print("     되돌린다. 정규식이 아니라 AST 로 앵커를 잡아라")
            return False
        b0, b1 = _bodies(self.orig), _bodies(self.text)
        shrunk = {k: (v, b1[k]) for k, v in b0.items() if k in b1 and b1[k] < v}
        if shrunk:
            print(f"  ✗ {rel}  **본문이 줄었다** — "
                  + " · ".join(f"{k}() {a}→{b}줄" for k, (a, b) in shrunk.items()))
            print("     되돌린다. 편집이 기존 코드를 먹었다")
            return False
        gained = sorted(x for x in _names(self.text) - _names(self.orig) if "#" not in x)
        mark = "→" if apply else "·"
        print(f"  {mark} {rel}")
        for x in self.log:
            print(f"      + {x}")
        for x in self.skipped:
            print(f"      = {x}")
        if gained:
            print(f"      새 정의 {gained}")
        if apply:
            self.path.write_text(self.text, encoding="utf-8")
        return True


def add_shell_step(path: str | Path, marker: str, block: str, *, apply: bool) -> bool:
    """셸 스크립트에 스텝 블록을 넣는다. 마커가 있으면 건너뛴다(멱등)."""
    p = Path(path) if Path(path).is_absolute() else ROOT / path
    s = p.read_text(encoding="utf-8")
    rel = p.relative_to(ROOT)
    if marker in s:
        print(f"  = {rel}  `{marker}` 이미 있다")
        return True
    # 마지막 요약 출력 앞에 넣는다
    m = re.search(r"^printf .*통과", s, re.M)
    at = m.start() if m else len(s)
    out = s[:at] + block.rstrip("\n") + "\n\n" + s[at:]
    mark = "→" if apply else "·"
    print(f"  {mark} {rel}  스텝 {block.count('step ')}개 추가")
    if apply:
        p.write_text(out, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="손실 감지가 실제로 도는지 본다")
    a = ap.parse_args()
    if a.selftest:
        # ★ 양성 대조. 손실 감지가 안 돌면 이 도구는 정규식 치환과 같다.
        before = "def keep():\n    return 1\n\n\ndef main():\n    return keep()\n"
        after = "def main():\n    return 0\n"
        if _names(before) - _names(after):
            print("✓ 손실 감지 살아 있다 — keep() 소실을 잡는다")
            return 0
        print("✗ 손실 감지가 죽었다. 이 도구를 믿지 마라")
        return 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

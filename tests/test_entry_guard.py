"""도구의 **진입 관문**이 제 꼴인가 — `if __name__ == "__main__":`.

★ 2026-10-14 (DECISIONS 532). 장부가 `tools/sizecheck.py` 의 그 줄에서
  `== → !=` 를 **생존**시켰다. 뒤집으면 `uv run python tools/sizecheck.py` 가
  **아무것도 안 하고 rc=0** 으로 끝난다 — 관문이 조용히 꺼진다. 그런데
  시험이 전부 모듈을 임포트해 함수를 직접 부르므로 아무 자도 안 울었다.

  그 꼴을 가진 도구가 **125개**다. 하나가 생존했으면 125개가 생존한다 —
  장부는 `--stale` 로 **바뀐 도구만** 재므로 그 사실이 한 번에 안 보인다.

★ **왜 AST 인가.** 글자로 찾으면(`'if __name__ == "__main__":' in src`)
  공백 하나에 빨개지고, 530-2 가 비판한 그 꼴이 된다. 여기서는 **구조**를
  본다 — 비교 연산자 노드가 `Eq` 인가. 돌연변이가 바꾸는 바로 그 노드다.

★ 둘째로 **관문 밖 실행**을 본다. 527 에서 `app = create_app()` 이 모듈
  꼬리에 있어 **임포트만으로 터졌다.** 최상위에서 `main()`·`sys.exit()` 을
  부르는 것은 같은 병이다.

IN    tools/**/*.py
OUT   없음 (검사)
PARAM 없음
밖    「관문이 **있어야** 하는가」는 안 본다 — 라이브러리 모듈(25개)에는 없고
      그것이 옳다. 있는 것만 꼴을 본다.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 최상위에서 부르면 **임포트가 곧 실행**이 되는 이름들.
FORBIDDEN_TOP_CALLS = ("main", "exit")


def _tools() -> list[Path]:
    out = sorted(ROOT.glob("tools/**/*.py"))
    assert len(out) > 100, f"도구를 {len(out)}개밖에 못 찾았다 — 자가 눈이 멀었다"
    return out


def _guard(tree: ast.Module) -> tuple[str, int] | None:
    """`__name__` 을 왼쪽에 둔 최상위 `if` 의 (연산자 이름, 줄). 없으면 None."""
    for n in tree.body:
        if not isinstance(n, ast.If):
            continue
        c = n.test
        if (isinstance(c, ast.Compare) and isinstance(c.left, ast.Name)
                and c.left.id == "__name__" and len(c.ops) == 1):
            return type(c.ops[0]).__name__, n.lineno
    return None


def test_every_entry_guard_compares_with_equality():
    """★ **이 판의 머리다.** 관문의 비교가 `==` 인가.

    `!=` 면 임포트할 때 돌고 직접 실행할 때 **안 돈다.** 관문이 뒤집힌다.
    """
    bad: list[str] = []
    seen = 0
    for f in _tools():
        g = _guard(ast.parse(f.read_text(encoding="utf-8")))
        if g is None:
            continue
        seen += 1
        if g[0] != "Eq":
            bad.append(f"  {f.relative_to(ROOT)}:{g[1]} — `__name__` 비교가 "
                       f"`{g[0]}` 다. `==` 가 아니면 직접 실행이 **아무것도 "
                       "안 하고 rc=0** 으로 끝난다")
    assert seen > 100, f"관문을 가진 도구를 {seen}개밖에 못 봤다 — 자가 눈이 멀었다"
    assert not bad, ("진입 관문의 비교가 틀렸다\n" + "\n".join(bad))


def test_no_tool_runs_itself_at_import_time():
    """최상위에서 `main()`·`sys.exit()` 을 부르지 않는가.

    ★ 527 에서 `app = create_app()` 이 모듈 꼬리에 있어 **임포트만으로**
      `RuntimeError` 가 났다. 검사 도구가 그러면 `import` 하는 자가 다 죽는다.
    """
    bad: list[str] = []
    for f in _tools():
        for n in ast.parse(f.read_text(encoding="utf-8")).body:
            if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Call):
                continue
            fn = n.value.func
            name = (fn.id if isinstance(fn, ast.Name)
                    else fn.attr if isinstance(fn, ast.Attribute) else "")
            if name in FORBIDDEN_TOP_CALLS:
                bad.append(f"  {f.relative_to(ROOT)}:{n.lineno} — 최상위에서 "
                           f"`{name}()` 을 부른다. 임포트가 곧 실행이 된다")
    assert not bad, ("도구가 임포트 시점에 자기를 돌린다\n" + "\n".join(bad))


def test_the_probe_bites():
    """★ 자가 **문다**는 것을 보인다 — `!=` 와 최상위 호출을 손으로 만들어 민다."""
    flipped = ast.parse('if __name__ != "__main__":\n    pass\n')
    g = _guard(flipped)
    assert g is not None and g[0] == "NotEq", f"`!=` 를 못 읽었다 — {g}"

    straight = ast.parse('if __name__ == "__main__":\n    pass\n')
    assert _guard(straight) == ("Eq", 1), "`==` 를 못 읽었다"

    assert _guard(ast.parse("x = 1\n")) is None, "없는 관문을 있다고 했다"

    # 최상위 호출 자
    top = ast.parse("main()\n").body[0]
    assert isinstance(top, ast.Expr) and isinstance(top.value, ast.Call)
    assert top.value.func.id in FORBIDDEN_TOP_CALLS, "금지 목록이 비었다"

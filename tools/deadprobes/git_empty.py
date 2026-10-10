"""`deadcheck ③(git)` — git 이 못 답한 것을 **빈 모음**으로 바꾸는가.

★ 2026-10-03 (DECISIONS §372). 저장소에 「git 이 무엇을 추적하나」를 물어
  **검사의 우주**를 정하는 자리가 일곱이었고 **둘만 맞았다** —
  `treecheck.tracked`(`None` 을 돌려준다)와 `deadcheck` 의 프로브 ④·⑤(건을
  낸다. 그중 ⑤ 는 사유까지 적었다 — 「여기서 return 하면 이 프로브가 프로브
  ③ 의 병에 걸린다」). **답이 저장소에 두 번 적혀 있었고 다섯 곳이 안 봤다.**

  나머지 다섯이 `[]` · `frozenset()` 로 뭉갰고, 그러면 —

      `encoding_check` 는 **검사할 파일이 0개**라고 보고 **초록**이 된다
      `docseal` 은 도장 대상 0 · 무효 0 · 미날인 0 으로 **전부 초록**이 된다
      `datalog` 는 산출물 전부를 「추적 밖이라 안 지었다」로 읽는다
                  (§290-7 이 세운 그 구분이 통째로 사라진다)
      `dms.uncommitted` 는 「커밋 안 된 것이 없다」고 답한다 — §180-7 의 거짓 봉인
      `remeasure._diff` 는 **측정 배치를 배선 배치로** 분류한다

  `Dockerfile` 이 git 을 안 깔고 `.git` 도 안 담으므로 **그 기계가 실물**이다.

★ `check=False` 는 **바이너리가 없는 경우를 안 막는다.** 실측 —
  `subprocess.run(["git", ...], check=False)` 는 PATH 에 git 이 없으면
  `FileNotFoundError` 를 던진다. `check` 는 **종료코드**에만 관여한다.

IN    tools/ · src/ 의 파이썬 (관문만. `tests/` 는 터지면 시끄럽다)
OUT   결함 (`hit` 으로 올린다)
밖    **스칼라는 안 센다.** 공백이 눈에 보이고 각자 가드를 가진다 — 실측에서
      이 조건 없이 돌리니 일곱 중 넷이 거짓 양성이었다(`baseline.git_sha` 의
      `or "unknown"` · `deliver._apply` 의 파싱 실패 보고 ·
      `ruleset_check._repo_slug` 의 `if url:` · `layerfsck._cfg` 의
      **rc=1 이 「미설정」이라는 답**).
      **`None` 은 결함이 아니다.** 그것이 옳은 답이다 — 「못 물었다」다.
부류  몸통   진입점이 아니다 — 부르는 쪽이 부류를 든다  (DECISIONS §437)
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: 빈 모음 리터럴. `None` 은 **여기 없다** — `None` 이 정답이다.
EMPTY_LIT = {"[]", "()", "{}", "set()", "frozenset()", "''", '""'}

#: stdout 을 **모음으로** 가르는 꼴. 스칼라와 가르는 기준이다.
SPLITS = (".split()", ".splitlines()", '.split("\0")', ".split('\0')")

#: 모음 꼴. 이 중 하나로 답하는 함수가 「우주를 정하는 자리」다.
COLL = ("list", "set", "frozenset", "dict", "Iterable", "Sequence")

#: 서브프로세스를 띄우는 이름.
_RUNNERS = ("run", "Popen", "check_output", "check_call", "call")


def _is_empty(node) -> bool:
    """`[]` · `set()` 처럼 **빈 모음**인가. `None` 은 아니다."""
    if node is None:
        return False
    try:
        return ast.unparse(node) in EMPTY_LIT
    except Exception:  # noqa: BLE001 — 못 적으면 「빈 것이 아니다」로 본다(과탐보다 미탐이 나쁘지만 여기선 뒤 팔이 받는다)
        return False


def _git_calls(fn: ast.AST) -> list[ast.Call]:
    """이 함수 안에서 `["git", …]` 로 띄우는 호출."""
    out = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if nm not in _RUNNERS:
            continue
        if n.args and isinstance(n.args[0], ast.List) and n.args[0].elts:
            e = n.args[0].elts[0]
            if isinstance(e, ast.Constant) and e.value == "git":
                out.append(n)
    return out


def returns_collection(fn) -> bool:
    """이 함수가 **모음을 답으로 돌려주는가.** 선언이 있으면 선언을 믿는다.

    ★ 이 한 칸이 거짓 양성 하나를 걷었다 — `deliver._apply` 는 `(bool, str)` 을
      돌려주고 단계마다 rc 를 보는데, 안쪽 어딘가의 `.splitlines()` 때문에
      걸렸다. 우주를 정하는 자리는 **모음을 돌려주는 자리**다.
    """
    if fn.returns is not None:
        ann = ast.unparse(fn.returns)
        return any(ann.startswith(c) or f"{c}[" in ann for c in COLL)
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Return) and n.value is not None):
            continue
        v = n.value
        if isinstance(v, (ast.ListComp, ast.SetComp, ast.DictComp,
                          ast.List, ast.Set, ast.Dict)):
            return True
        if isinstance(v, ast.Call) and getattr(v.func, "id", "") in (
                "list", "set", "frozenset", "dict"):
            return True
    return False


def findings(root: Path = ROOT) -> list[tuple[Path, int, str, str]]:
    """(파일, 줄, 함수 이름, 무엇을 했나). **판정은 안 한다.**"""
    out: list[tuple[Path, int, str, str]] = []
    for p in sorted((root / "tools").rglob("*.py")) + sorted((root / "src").rglob("*.py")):
        if "__pycache__" in p.parts or p.name == "gitq.py":
            continue      # ★ `gitq` 는 정본이다. 여기가 `None` 을 만드는 자리다
        try:
            t = ast.parse(p.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for fn in [n for n in ast.walk(t)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            calls = _git_calls(fn)
            if not calls:
                continue
            body = ast.unparse(fn)
            # (a) 예외 자리에서 **빈 모음**을 돌려준다
            for h in [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]:
                for st in h.body:
                    if isinstance(st, ast.Return) and _is_empty(st.value):
                        out.append((p, st.lineno, fn.name,
                                    f"git 실패를 `{ast.unparse(st.value)}` 로 바꾼다"))
            # (b) rc!=0 에서 **빈 모음**을 돌려준다
            for node in [n for n in ast.walk(fn) if isinstance(n, ast.If)]:
                if "returncode" not in ast.unparse(node.test):
                    continue
                for st in node.body:
                    if isinstance(st, ast.Return) and _is_empty(st.value):
                        out.append((p, st.lineno, fn.name,
                                    f"rc!=0 을 `{ast.unparse(st.value)}` 로 바꾼다"))
            # (c) rc 를 안 보고 stdout 을 **모음으로** 갈라 그대로 내보낸다
            for c in calls:
                kw = {k.arg: ast.unparse(k.value) for k in c.keywords}
                if kw.get("check") == "True":
                    continue
                if "returncode" in body or "gitq" in body:
                    continue
                if not any(s in body for s in SPLITS):
                    continue
                if not returns_collection(fn):
                    continue
                out.append((p, c.lineno, fn.name,
                            "rc 를 안 본 채 stdout 을 **모음으로** 갈라 내보낸다"))
    return out

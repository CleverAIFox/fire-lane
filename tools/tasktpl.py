#!/usr/bin/env python3
"""
tasktpl.py — LLM 에게 주는 **작업 지시문 틀**을 저장소에서 읽어 찍어 낸다.  (PLAN #204)

    uv run python tools/tasktpl.py                 틀을 화면에 낸다
    uv run python tools/tasktpl.py --write PATH    그 경로에 쓴다
    uv run python tools/tasktpl.py --check PATH    PATH 가 지금 틀과 다르면 rc 1

── 왜 있나 ─────────────────────────────────────────────────────
틀이 불변량 수 · 관문 이름 · 등재 의무를 **손으로 적으면** MASTER · PLAN · 도구의 사본이 되고 사본은 한쪽만 고쳐지는 날이 온다
(`.claude/TASK_TEMPLATE.md` 가 `test_no_fifth_doc` 에 물려 되돌려졌다). 2026-11-07 에는 지시문에서 금지 블록을 빠뜨렸고 그 판에서
`evalset_2610.key.json` 봉인이 열렸다. 정본은 하나고 틀은 산출이다 — `render_workflow.py` 가 MASTER §12 를 굽는 것과 같은 꼴이다.

── 무엇이 어디서 오나 ───────────────────────────────────────
  먼저 읽을 절         `READ_FIRST` — 문서 · 절 이름표. **그 절이 실재하는지**를 이 도구가 문서 제목에서 확인한다(없으면 rc 1).
  불변량 수            `docnum_check.verdicts()` — MASTER 의 판정 표를 채우는 그 함수. 손으로 안 적는다.
  푸시를 막는 관문      `.githooks/pre-push.gates` 의 이름 열.
  푸시 전 한 명령의 축   `pushready.CHECKS` 의 키와 그 도구 머리말 「무엇을 보나」 줄.
  새 파일의 등재 의무    `obligations.OBLIGATIONS`.
  하지 말 것(금지 칸)   **새로 안 적는다 — 정본이 이미 코드에 있다**(사람이 정했다):
      사람 전용          `fixable.HUMAN_FIRST` — `tools/fix.sh` 가 「손도 안 댄 것」으로 찍는 그 표(이름 · 사유)
      상한 올리기        `ratchet.owners()` — 래칫 수. 느슨해지는 쪽을 `--write` 가 거부하는 것이 집행이다
      판정 폐포          `shardseal.code_closure()` — ingest 가 import 하는 모듈. 이 파일들이 판정을 움직인다
      푸시 · 도장        `pushready` 머리말의 「읽기만 한다」 줄과 그 축
  PLAN 본문 금기        **시험이 PLAN 본문을 무는 규칙** — 새로 안 적는다(2026-11-09 사람이 정했다):
      소속 없는 절 참조 · 빈 행 `#N`   `plan_renumber.unresolved_section_refs` · `unresolved_row_refs` 의 머리 문장
      도구 선언으로 읽히는 `tools/…`    `tests/test_guards.py::test_tools_declared_in_docs_exist` 의 머리 문장과 정규식(AST 로 읽는다)
      벽시계 수                        `tests/test_repo_numbers.py` 의 `_WALL` · `_ABOUT` · `_LIVE`(AST 로 읽는다 — 시험 모듈을 import 하지 않는다)
      평어체                           `tests/test_doc_style.py` 의 `VOICE` · `ALLOW`
      폐기값 수치                      `docnum_check.retired_pattern` 의 머리 문장
      그 밖                            PLAN 을 읽는 시험 · 도구의 **이름만** 센다 — 그것이 본문 규칙을 무는지는 도구가 못 가린다(아래 출력이 그 사실을 적는다)

IN    위 곳들 읽기 전용 · `--check` 의 PATH
OUT   화면(기본) · `--write` 가 준 경로 한 파일. **기본 위치가 없다 — 틀을 저장소에 커밋하지 않는다**(커밋하면 그것이 사본이다 · 사람이 정했다).
      화면으로 받아 쓰고, `--check` 는 「누가 복사해 둔 틀이 낡았나」를 볼 때만 쓴다.
PARAM READ_FIRST
밖    **틀이 지시문으로서 좋은가는 안 본다.** 어느 지시문이 규칙을 지켰는지도 안 본다.
      **이번 일에만 거는 규칙**(이 일은 푸시하지 마라 같은 것)은 안 낸다 — 그것은 일을 시키는 사람의 문장이다.
부류  조사   사람이 손으로 돌려 틀을 낸다. 어느 관문에도 안 올렸다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

import docnum_check
import fixable
import obligations
import plan_renumber
import pushready
import ratchet

from firelane import shardseal

ROOT = Path(__file__).resolve().parent.parent
GATES = ROOT / ".githooks" / "pre-push.gates"

#: (문서, 절 이름표). 지시문이 「먼저 읽어라」 하는 곳. 이름표가 문서 제목에 **실재해야** 한다.
READ_FIRST = (
    ("docs/PLAN.md", "0-1"), ("docs/PLAN.md", "0-2"),
    ("docs/MASTER.md", "0"), ("docs/MASTER.md", "22"), ("docs/MASTER.md", "23"),
)

_HEAD = re.compile(r"^#{2,4} (\d+(?:-\d+)*)\.")


def _sections(rel: str) -> set[str]:
    return {m.group(1) for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines() if (m := _HEAD.match(ln))}


def missing_sections() -> list[str]:
    """`READ_FIRST` 중 문서에 없는 절. 비면 모두 실재한다."""
    cache: dict[str, set[str]] = {}
    out = []
    for rel, sec in READ_FIRST:
        have = cache.setdefault(rel, _sections(rel))
        if sec not in have:
            out.append(f"{rel} §{sec}")
    return out


def gate_names() -> list[str]:
    return [ln.split("\t", 1)[0] for ln in GATES.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def axes() -> list[str]:
    """`pushready` 의 축 — 키와 머리말의 한 줄 설명."""
    said = {m.group(1): m.group(2) for ln in (pushready.__doc__ or "").splitlines() if (m := re.match(r"\s+(㉠|㉡|㉢|㉣|㉤|㉥|㉦|㉧) (.+)", ln))}
    return [f"{k} {said.get(k, '(머리말에 설명이 없다)')}" for k, _ in pushready.CHECKS]


def forbidden() -> list[str]:
    """금지 칸 — **저장소의 정본을 읽어** 채운다. 사본을 안 만든다."""
    L = ["- 사람 전용(손도 안 댄다 · 판단이 먼저다) — `fixable.HUMAN_FIRST`"]
    for tool, why in fixable.HUMAN_FIRST.items():
        t = " ".join(why.split())
        L.append(f"    · {tool} — {t if len(t) <= 90 else t[:90] + '…'}")
    L.append(f"- 상한 올리기 금지 — 래칫을 가진 도구 {len(ratchet.owners())}개. 느슨해지는 쪽은 `ratchet.py --write` 가 안 받는다(손으로 올리고 이유를 적는 일은 사람의 몫이다)")
    names = sorted(p.relative_to(ROOT / "src" / "firelane").as_posix() for p in shardseal.code_closure())
    L.append(f"- 판정 폐포 — ingest 가 import 하는 모듈 {len(names)}개를 고치면 판정이 움직인다: {' · '.join(names)}")
    said = next((ln.strip() for ln in (pushready.__doc__ or "").splitlines() if "읽기만 한다" in ln), "")
    L.append(f"- 푸시 · 도장 — {said.removeprefix('★ ').strip()} 도장(`docseal`)과 푸시는 사람이 한다")
    return L


TESTS = ROOT / "tests"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _assigned(path: Path, name: str):
    """모듈 상수 `name` 의 값 — 문자열 · 튜플 · `re.compile("…")` 의 첫 인자 · `{키: re.compile("…")}` 를 **import 없이** 읽는다. 못 찾으면 죽는다."""
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            v = node.value
            if isinstance(v, ast.Call) and v.args and isinstance(v.args[0], ast.Constant):
                return v.args[0].value
            if isinstance(v, ast.Dict):
                return {ast.literal_eval(k): ast.unparse(x) for k, x in zip(v.keys, v.values, strict=True)}
            return ast.literal_eval(v)
    raise LookupError(f"{path.name} 에 {name} 가 없다 — 이름이 바뀌었으면 틀이 읽을 곳을 잃었다")


def _first(doc: str | None, paras: int = 1, cap: int = 330) -> str:
    t = " ".join(" ".join((doc or "").strip().split("\n\n")[:paras]).split())
    return t if len(t) <= cap else t[:cap] + "…"


def _func_regexes(path: Path, func: str) -> list[str]:
    """함수 몸통 안에서 `re.*` 에 넘긴 **문자열 인자**."""
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            out = []
            for c in ast.walk(node):
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) and c.func.value.id == "re":
                    out += [a.value for a in c.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            return out
    raise LookupError(f"{path.name} 에 {func} 가 없다")


def plan_readers() -> tuple[list[str], list[str]]:
    """PLAN.md 를 읽는 시험 · 도구 이름. **세기만 한다** — 본문 규칙을 무는지는 가리지 못한다."""
    def has(p: Path) -> bool:
        return "PLAN.md" in p.read_text(encoding="utf-8", errors="ignore")
    return ([p.name for p in sorted(TESTS.glob("*.py")) if has(p)], [p.name for p in sorted((ROOT / "tools").glob("*.py")) if has(p)])


def plan_rules() -> list[str]:
    """PLAN 본문 금기 — **시험이 무는 것**을 그 시험 · 도구에서 읽어 채운다."""
    rn, gd, doc = TESTS / "test_repo_numbers.py", TESTS / "test_guards.py", TESTS / "test_doc_style.py"
    L = [f"- 절 참조 — {_first(plan_renumber.unresolved_section_refs.__doc__)}",
         f"- 행 번호 — {_first(plan_renumber.unresolved_row_refs.__doc__)}",
         f"- 도구 선언 — {_first(next(n for n in ast.walk(_tree(gd)) if isinstance(n, ast.FunctionDef) and n.name == 'test_tools_declared_in_docs_exist').body[0].value.value)} "
         f"(정규식 {' · '.join(f'`{r}`' for r in _func_regexes(gd, 'test_tools_declared_in_docs_exist'))})",
         f"- 벽시계 수 — 대상 {' · '.join(_assigned(rn, '_LIVE'))} · 수 꼴 `{_assigned(rn, '_WALL')}` · 줄에 {' · '.join(f'「{w}」' for w in _assigned(rn, '_ABOUT'))} 가 있으면 막는다",
         f"- 평어체 — 검사 {' · '.join(_assigned(doc, 'VOICE'))} · 의도적 인용은 줄 끝 `{_assigned(doc, 'ALLOW')} 사유-->`",
         f"- 폐기값 수치 — {_first(docnum_check.retired_pattern.__doc__, paras=2)}"]
    tests, tools = plan_readers()
    L.append(f"- 그 밖 — PLAN 을 읽는 시험 {len(tests)}개 · 도구 {len(tools)}개가 있다(이름만 센다: {' · '.join(tests)}). "
             "이 가운데 어느 것이 본문 **규칙**을 무는지는 도구가 못 가린다 — 위 여섯 말고 더 있을 수 있다")
    return L


def render(verdicts: dict[str, int] | None = None) -> str:
    v = verdicts if verdicts is not None else docnum_check.verdicts()
    L = ["# 작업 지시문 틀 — 이 파일은 `tools/tasktpl.py` 가 찍는다. 손으로 고치지 않는다.", ""]
    L += ["## 먼저 읽어라 — 세금은 저장소가 안다. 받아쓴 목록을 믿지 마라"]
    L += [f"- {rel} §{sec}" for rel, sec in READ_FIRST]
    L += [f"- {GATES.relative_to(ROOT)} — 무엇이 푸시를 막는가", "- `uv run python tools/obligations.py --new` — 새 파일의 등재 의무를 이름으로 댄다", ""]
    L += ["## 불변량 — 움직이면 판정이 움직인 것이다"]
    L += [f"- {k} {v[k]}" for k in ("clear", "needs_cv", "blocked", "unknown") if k in v]
    if "n" in v:
        L.append(f"- 구간 {v['n']}")
    L += ["", "## 푸시를 막는 관문(`pre-push.gates`)"] + [f"- {n}" for n in gate_names()]
    L += ["", "## 푸시 전 한 명령 — `uv run python tools/pushready.py`"] + [f"- {a}" for a in axes()]
    L += ["", "## 새 파일에 따라붙는 의무(`obligations --new` 가 이름으로 댄다)"]
    L += [f"- {o.name} — {o.applies}: {o.fix}" for o in obligations.OBLIGATIONS]
    L += ["", "## 하지 말 것 — 정본은 저장소에 있다(`tools/tasktpl.py` 가 읽어 채운다)"] + forbidden()
    L += ["", "## PLAN 본문 금기 — 시험이 무는 것(사람이 쓴 PLAN 본문이 이 시험들에 걸렸다)"] + plan_rules() + [""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="작업 지시문 틀을 저장소에서 찍는다")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", metavar="PATH")
    g.add_argument("--check", metavar="PATH")
    a = ap.parse_args(argv)
    miss = missing_sections()
    if miss:
        print(f"✗ 먼저 읽을 절이 문서에 없다: {', '.join(miss)}", file=sys.stderr)
        return 1
    text = render()
    if a.check:
        p = Path(a.check)
        if not p.is_file() or p.read_text(encoding="utf-8") != text:
            print(f"✗ {p} 가 지금 틀과 다르다 — `--write {p}` 로 다시 찍는다(손으로 고친 것은 사라진다)", file=sys.stderr)
            return 1
        print(f"✓ {p} 가 틀과 같다")
        return 0
    if a.write:
        Path(a.write).write_text(text, encoding="utf-8")
        print(f"틀을 {a.write} 에 썼다")
        return 0
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

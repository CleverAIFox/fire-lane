#!/usr/bin/env python3
"""
pushdenom.py — **pushready 칸이 자기 분모를 말하게 한다** — ㉠(래칫)의 「래칫 N개 중 몇 개를 읽었나 · 넘기는 규칙 둘」과 ㉥(시험)의 「읽기 실측 N/M」을 초록일 때도 한 줄로 낸다.  (PLAN #259 · DECISIONS §835)

㉤ 는 변이 지문의 분모다 — `print_denom` 이 「정의 37개 중 지문에 든 것 5개(13.5%)」를 내고 선언표(`OUT_OF_PRINT`)가 안 든 32개의 사유를 든다(`tests/test_mutate_defs_scope.py` 가 같은 표를 쓴다).
`tools/pushready.py` 의 `check_ratchet` · `check_mutate` · `check_tests` 가 부른다 — 칸이 읽은 출력에서 분모를 뽑아 `record` 에 쌓고 `lines` 가 푸시 가능 · 불가 보고 끝에 붙인다.

판별식   `skip_rule(mark, tool, name)` — ㉠ 가 **넘기는** 래칫 항목이 선언표(`RATCHET_SKIPS`)의 어느 규칙인가(없으면 None → 읽는다) · `reads_gap` — ㉥ 의 읽기 장부가 못 덮은 시험이 **새 시험으로 설명되는가**
① 본 몫(분모)      ㉠ = `ratchet.py` 의 「래칫 N개」 중 읽은 수(N − 넘긴 수) · ㉥ = `testpick` 의 「읽기 실측 n/M개 파일」
② 못 세는 값이 갈 칸  넘긴 항목은 규칙마다 따로 센다(`RATCHET_SKIPS` 의 키) · 장부가 못 덮은 시험은 새 시험 수로 설명하고 남는 것은 `설명 안 되는 몫` 이다 · 분모를 못 읽으면 「분모를 못 읽었다」를 낸다(0 이 아니다)
③ 전제와 우는 것   전제 = 넘기는 규칙은 **선언표에 든 둘뿐**이고(사유가 비면 안 된다) 장부가 못 덮은 시험은 새 시험이 전부다. 선언 밖 항목은 읽혀서 막고 · 설명 안 되는 몫이 있으면 ㉥ 가 막는다

IN    `ratchet.py` 의 출력 · `testpick --run` 의 출력(문자열) — 파일을 읽지 않는다
OUT   문자열 · 튜플. `record`/`lines` 가 쓰는 모듈 상태 한 칸(프로세스 안 · 파일은 안 쓴다)
PARAM `RATCHET_SKIPS`(넘기는 규칙 둘 · 사유)
밖    **막을지는 `pushready` 가 정한다**(여기는 분모만 센다) · 래칫 값이 옳은지 · 시험이 초록인지는 안 본다. 분모의 % 는 래칫으로 안 건다(범위 축소는 선언표가 막는다 — `uicheck` 와 같다).
부류  몸통   진입점이 **아니다.** `pushready.py` 가 import 한다  (DECISIONS §398)
"""
from __future__ import annotations

import ast
import re
import threading
from pathlib import Path

#: ㉠ 가 `ratchet.py` 출력에서 **넘기는** 항목 — 키 → (판별식, 사유). 이 밖의 `✗` · `·` 는 전부 읽어 막는다. 사유가 비면 시험이 운다.
RATCHET_SKIPS: dict[str, tuple] = {
    "UNSEALED → ㉢": (lambda mark, tool, name: tool == "docseal.py" and name == "UNSEALED",
                      "도장이 아예 없는 절 수는 ㉢ 가 선언 `docseal.UNSEALED` 와 맞대어 막는다 — 같은 값을 두 칸이 세면 한 병에 막힘이 둘이다"),
    "mutate.py 의 ✗ 아닌 것 → ㉤": (lambda mark, tool, name: tool == "mutate.py" and (mark != "✗" or name == "—"),
                                 "변이 장부가 낡았거나 죽은 것은 ㉤ 가 맡고 · 조이는 쪽의 `--write` 는 변이 지문을 낡게 한다(㉠→㉤) — ✗ 느슨해지는 쪽만 ㉠ 가 읽는다"),
}

ITEM = re.compile(r"^\s+([✗·~]) (\S+) · (\S+)")
SUMMARY = re.compile(r"래칫 (\d+)개 · 낡음 (\d+)(?:.*?건너뜀 (\d+))?")
_READS = re.compile(r"실측 읽기 (\d+)/(\d+)개 파일")
_NEW = re.compile(r"낡은 시험 새: ?(.*)$", re.M)
_LOCK = threading.Lock()
_DENOM: dict[str, list[str]] = {}


def skip_rule(mark: str, tool: str, name: str) -> str | None:
    """넘기는 규칙의 키 — 없으면 None(읽는다)."""
    return next((k for k, (f, _) in RATCHET_SKIPS.items() if f(mark, tool, name)), None)


def ratchet_denom(out: str) -> list[str]:
    """㉠ 의 분모 줄들 — 「래칫 N개 중 읽은 수」와 넘기는 규칙마다 센 수 · 사유. 요약줄을 못 읽으면 그 말을 낸다."""
    m = SUMMARY.search(out)
    if m is None:
        return ["㉠ 분모를 못 읽었다 — `ratchet.py` 의 「래칫 N개」 줄이 없다(출력 꼴이 바뀌었나)"]
    n, ratchet_skip = int(m.group(1)), int(m.group(3) or 0)
    got = [k for ln in out.splitlines() if (it := ITEM.match(ln)) and (k := skip_rule(*it.groups()))]
    return [f"㉠ 래칫 {n}개 중 {n - len(got)}개를 읽었다 · 넘긴 {len(got)}개 · `ratchet.py` 가 못 잰 것 {ratchet_skip}개",
            *(f"    넘기는 규칙 — {k} ({got.count(k)}개): {why}" for k, (_, why) in RATCHET_SKIPS.items())]


def reads_gap(out: str) -> tuple[int, int, int] | None:
    """㉥ — (읽기 실측 n, 시험 파일 M, 새 시험으로 설명 안 되는 몫). 분모 줄이 없으면 None."""
    m = _READS.search(out)
    if m is None:
        return None
    n, total = int(m.group(1)), int(m.group(2))
    new = _NEW.search(out)
    return n, total, max(0, total - n - len(new.group(1).split() if new else []))


def tests_denom(out: str) -> list[str]:
    g = reads_gap(out)
    if g is None:
        return ["㉥ 분모를 못 읽었다 — `testpick` 의 「읽기 실측 n/M개 파일」 줄이 없다(출력 꼴이 바뀌었나)"]
    n, total, unexplained = g
    return [f"㉥ 읽기 실측 {n}/{total}개 파일({n / total:.1%}) · 못 덮은 {total - n}개 중 새 시험으로 설명 안 되는 몫 {unexplained}"
            + (" — 새 시험은 정적 스캔만이라 하한이다(낡음이 막는다)" if total - n else "")]


def gap_block(out: str) -> tuple[str, list[str], list[str]] | None:
    """설명 안 되는 몫이 있으면 막는 것 하나 — (무엇 · 자세히 · 사람이 칠 명령). 없으면 None."""
    g = reads_gap(out)
    if g is None or not g[2]:
        return None
    n, total, un = g
    return (f"읽기 장부가 {un}개 시험을 못 덮는데 새 시험으로 설명이 안 된다(읽기 실측 {n}/{total})", [f"장부에 없는 시험 {total - n}개 중 새 시험은 {total - n - un}개뿐이다"],
            ["uv run python tools/testpick.py --measure-reads --write --only <장부에 없는 시험…>   # 어느 시험인지는 --list 의 「장부에 없음」"])


def record(key: str, lines: list[str]) -> None:
    with _LOCK:
        _DENOM[key] = lines


def lines() -> list[str]:
    """쌓인 분모 줄 — 칸 순서(㉠ · ㉤ · ㉥)."""
    with _LOCK:
        return [x for k in ("㉠", "㉤", "㉥") for x in _DENOM.get(k, [])]


# ── ㉤ 변이 지문의 분모 (PLAN #259 · 정의 37 = 지문 5 + 폐포 안 0 + 선언표 32) ──────────────
#: 지문(`mutatescope.catch_print`)이 후보 · 표본 규칙을 정하는 소스로 읽는 두 파일.
PRINT_FILES = ("mutate.py", "mutatescope.py")
_TOOLS = Path(__file__).resolve().parent

#: 지문에 드는 5개 — `sampler_print` 가 해시하는 소스(`pick` · `_site_keys` · `mutants` · 연산자 표 둘).
IN_PRINT = {
    "mutatescope.py::pick",
    "mutatescope.py::_site_keys",
    "mutate.py::mutants",
    "mutate.py::_CMP",
    "mutate.py::_CMP_SRC",
}

#: 폐포 안인데 지문 밖인 정의의 사유. 지금은 비어 있다 — 지문 5가 서로와 표준 꾸러미만 부른다.
#: 지문 5 중 하나가 새 보조 정의를 부르면 그 정의가 여기 오르거나 지문에 들어야 한다.
CLOSURE_OUT: dict[str, str] = {}

#: 지문 밖 32개와 사유. 모두 코드를 읽고 적었다 — 한 이름에 한 줄이다.
OUT_OF_PRINT: dict[str, str] = {
    # ── mutate.py ──
    "mutate.py::ROOT": "저장소 뿌리 경로라 후보 자리도 표본도 안 정한다 — 붙잡이 명령의 작업 디렉터리와 상대 경로만 가리킨다",
    "mutate.py::LEDGER": "장부 파일의 위치 상수라 읽고 쓸 곳만 가리키고 어느 자리를 흔들지는 안 정한다",
    "mutate.py::MAX_PER_TOOL": "표본 크기를 정하는 상수(4)라 지문 밖이면 값이 조용히 바뀐다 — 지문을 넓히는 대신 `cap_problems` 가 선언값 · 호출 모양 · 장부의 흔든 수를 따로 묻는다",
    "mutate.py::TIMEOUT": "돌연변이 하나에 주는 시간이라 넘기면 「못 쟀다」로 갈릴 뿐 자리 목록과 표본은 그대로다",
    "mutate.py::SURVIVORS": "장부의 생존 수를 맞대는 래칫 선언값이라 결과를 비교할 뿐 자리를 정하지 않는다 — 값을 올리는 일은 래칫 관문이 따로 문다",
    "mutate.py::MUTANTS": "흔든 수(분모)를 잠그는 래칫 선언값이라 표본의 결과를 세어 맞댈 뿐 표본을 고르지 않는다",
    "mutate.py::UNCATCHABLE": "붙잡이가 0 인 과녁 수의 선언값이라 측정 결과를 맞대는 표지 하나이고 자리 규칙과 무관하다",
    "mutate.py::UNSORTED": "아직 안 가른 생존 수의 선언값(`SURVIVORS` 의 종속값)이라 결과 쪽 표지이지 표본 규칙이 아니다",
    "mutate.py::RATCHETS": "어느 상수가 래칫인지 이름만 적은 표라 `sort_survivors` 의 분류에 읽힐 뿐 자리 목록에는 안 읽힌다",
    "mutate.py::_HARMLESS": "무해 돌연변이로 덧붙이는 주석 한 줄이라 붙잡이가 내용 지문에 우는지 가릴 때만 쓰이고 후보가 아니다",
    "mutate.py::catchers": "어떤 명령이 붙잡이인지 도출하므로 생존 판정에 닿지만 흔들 자리는 안 만든다 — 자리는 이미 `mutants` · `pick` 이 정한 뒤다",
    "mutate.py::_run": "붙잡이 명령 하나를 돌려 초록 여부와 침묵 통과를 가르는 실행 도우미라 자리를 정하지 않는다",
    "mutate.py::live_catchers": "밑동에서 초록이고 무해 변이에 안 우는 붙잡이만 거르므로 생존 수에 닿지만 표본의 자리는 안 정한다",
    "mutate.py::shake": "표본을 쓰는 쪽이다 — `pick(mutants(원문), cap, 원문)` 으로 부르고 돌려 생존을 센다. 뽑는 규칙은 지문 5가 들고 부르는 모양은 `cap_problems` 가 ast 로 묻는다",
    "mutate.py::_ratchet_line": "도구 소스에서 모듈 수준 대입의 줄 번호만 읽는 보조라 자기검사와 시험에서 쓰이고 표본에 안 든다",
    "mutate.py::sort_survivors": "끝난 생존을 래칫이 드는 것과 아직 안 가른 것으로 나눠 `UNSORTED` 를 내는 분류라 자리 목록에는 안 읽힌다",
    "mutate.py::ratchet_values": "장부를 읽어 래칫 값을 내고 지문이 낡았으면 운다 — 지문을 비교하는 쪽이지 지문 입력이 아니다",
    "mutate.py::selftest": "옆집 자기검사를 함수 안에서 불러 올 뿐인 한 줄 위임이라 아무 값도 정하지 않는다",
    "mutate.py::main": "인자 해석 · 출력 · 장부 쓰기의 진입점이다 — 상한은 `--max` 기본값으로 흘리는 자리만 `cap_problems` 가 묻는다",
    # ── mutatescope.py ──
    "mutatescope.py::ROOT": "저장소 뿌리 경로라 지문 입력의 파일 위치만 가리키고 값을 안 정한다",
    "mutatescope.py::TOOLS": "도구 폴더 경로라 어느 파일을 읽을지만 가리키고 후보 자리와 표본은 안 정한다",
    "mutatescope.py::TESTS": "시험 폴더 경로라 이름을 적은 시험을 찾을 곳만 가리킬 뿐 값을 안 정한다",
    "mutatescope.py::MUTATE_SRC": "후보 소스 파일의 경로라 값이 아니라 위치다 — 다른 경로로 바꿔 보는 시험이 이미 있고 `operators_source` 가 그 파일의 소스를 읽는다",
    "mutatescope.py::_OPERATOR_NAMES": "지문에 넣을 연산자 표 이름 둘이다 — 바꾸면 `operators_source` 의 「셋을 찾았는가」 검사가 울어 조용히 어긋나지 않는다",
    "mutatescope.py::targets": "어느 도구가 과녁인지 도출한다 — 과녁 집합은 별도 시험이 장부 도구 집합과 같음을 묻고 표본 자체는 안 정한다",
    "mutatescope.py::imported": "소스가 끌어오는 최상위 모듈 이름을 센다 — 지문의 옆집 모듈 몫과 과녁 고르기가 쓰고 표본 규칙은 아니다",
    "mutatescope.py::_imports_ratchet": "선언을 옆집에 둔 관문도 과녁으로 치는 판별이라 어느 도구가 장부에 드는지만 정한다",
    "mutatescope.py::named_tests": "도구 이름을 적은 시험을 모으는 함수라 지문의 시험 몫 입력이고 후보 자리와 표본에는 안 읽힌다",
    "mutatescope.py::local_imports": "도구가 끌어오는 옆집 모듈 이름을 모으는 함수라 지문의 옆집 몫 입력이고 표본 규칙이 아니다",
    "mutatescope.py::catch_print": "지문을 합치는 자리 그 자체다 — 도구 · 옆집 · 시험 · 표본 규칙 지문을 섞을 뿐 자기 소스는 입력이 아니다",
    "mutatescope.py::operators_source": "지문에 넣을 후보 규칙의 소스를 뽑는 함수다 — 못 찾으면 운다는 시험이 있고 뽑은 결과는 지문에 든다",
    "mutatescope.py::sampler_print": "표본 규칙의 지문을 만드는 함수다 — 출력이 모든 도구의 지문에 섞이므로 입력 소스가 바뀔 때만 값이 달라진다",
}


# ── 판별(순수 함수 — 소스 문자열만 받는다) ───────────────────────
def _names(node: ast.AST) -> list[str]:
    """최상위 정의가 내는 이름들. 함수 · 클래스는 이름 하나, 대입은 대상 이름 전부."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def definitions(sources: dict[str, str]) -> dict[str, ast.AST]:
    """`{"파일::이름": 노드}` — 같은 이름이 두 파일에 있으면 둘로 센다."""
    out: dict[str, ast.AST] = {}
    for fname, src in sources.items():
        for node in ast.parse(src).body:
            for nm in _names(node):
                out[f"{fname}::{nm}"] = node
    return out


def _refs(node: ast.AST) -> set[str]:
    """그 정의가 이름으로 · 속성으로 · 이름 문자열로 가리키는 것. 함수 머리말 문자열은 안 센다."""
    skip: set[int] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.FunctionDef | ast.ClassDef) and ast.get_docstring(n, clean=False):
            first = n.body[0]
            if isinstance(first, ast.Expr):
                skip.add(id(first.value))
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip:
            out.add(n.value)
    return out


def closure(defs: dict[str, ast.AST], seeds: set[str]) -> set[str]:
    """씨앗이 직접 · 간접으로 부르거나 읽는 정의(씨앗은 뺀다). 같은 파일을 먼저 보고 없으면 다른 파일."""
    seen = {k for k in seeds if k in defs}
    todo = sorted(seen)
    while todo:
        key = todo.pop()
        home = key.split("::")[0]
        for r in _refs(defs[key]):
            hits = [f"{home}::{r}"] if f"{home}::{r}" in defs else [k for k in defs if k.split("::", 1)[1] == r]
            for h in hits:
                if h not in seen:
                    seen.add(h)
                    todo.append(h)
    return seen - seeds


def problems(sources: dict[str, str], in_print: set[str], out_of_print: dict[str, str],
             closure_out: dict[str, str]) -> list[str]:
    """어긋난 것 목록. 비어 있으면 조용하다 — 이 값이 「선언이 정의와 같다」다."""
    defs = definitions(sources)
    got: list[str] = []
    for k in sorted(in_print - set(defs)):
        got.append(f"지문 5 에 적었는데 실제로 없다(죽은 선언): {k}")
    clo = closure(defs, in_print)
    for k in sorted(clo - set(closure_out)):
        got.append(f"폐포 안인데 지문 밖이고 사유가 없다: {k}")
    for k in sorted(set(closure_out) - clo):
        got.append(f"폐포 선언인데 폐포가 아니다(죽은 선언): {k}")
    rest = set(defs) - in_print - clo
    for k in sorted(rest - set(out_of_print)):
        got.append(f"선언 밖의 새 정의: {k}")
    for k in sorted(set(out_of_print) - set(defs)):
        got.append(f"선언표에 있는데 실제로 없다(죽은 선언): {k}")
    for k in sorted((set(out_of_print) & set(defs)) & (in_print | clo)):
        got.append(f"선언표에 있는데 지문 · 폐포 안이다: {k}")
    for k, why in {**out_of_print, **closure_out}.items():
        if len(why.strip()) < 12:
            got.append(f"사유가 비었거나 짧다: {k}")
    return got


def print_denom() -> list[str]:
    """㉤ 의 분모 줄 — 두 파일의 최상위 정의 중 지문에 드는 몫 · 폐포 · 선언표, 사유 한 줄, 선언이 정의와 어긋난 수. 파일은 `tools/` 의 두 개만 읽는다."""
    sources = {f: (_TOOLS / f).read_text(encoding="utf-8") for f in PRINT_FILES}
    defs = definitions(sources)
    seen = len(IN_PRINT & set(defs))
    if not defs or not seen:
        return ["㉤ 분모를 못 읽었다 — 두 파일에서 정의를 못 셌거나 지문에 드는 정의가 0이다(선언이 낡았나)"]
    clo = closure(defs, IN_PRINT)
    bad = problems(sources, IN_PRINT, OUT_OF_PRINT, CLOSURE_OUT)
    return [f"㉤ 변이 지문 — 후보 · 표본 규칙을 정하는 정의 {len(defs)}개 중 지문에 든 것 {seen}개({seen / len(defs):.1%}) · 폐포 안(지문 밖) {len(clo)}개 · 선언표 {len(OUT_OF_PRINT)}개 · 선언이 어긋난 것 {len(bad)}개",
            f"    못 세는 값이 갈 칸 — 안 든 {len(OUT_OF_PRINT)}개는 `pushdenom.OUT_OF_PRINT` 에 정의마다 사유가 한 줄씩 든다(폐포 안 사유는 `CLOSURE_OUT`)",
            f"    전제 — `{'` · `'.join(PRINT_FILES)}` 의 최상위 정의를 ast 로 센다 · 지문의 해시 입력은 안 넓혔다(넓히면 변이 장부 전량 재측정)"]

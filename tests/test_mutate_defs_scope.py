#!/usr/bin/env python3
"""
test_mutate_defs_scope.py — 변이 장부의 지문 밖 정의를 하나씩 선언했는가.  (PLAN #259 · 도착 ③)

── 무엇을 보는가 ───────────────────────────────────────────────
변이 장부의 후보 목록 · 표본 규칙을 정하는 소스는 두 파일(`mutate.py` ·
`mutatescope.py`)의 최상위 정의 37개 중 5개(`pick` · `_site_keys` · `mutants` ·
`_CMP` · `_CMP_SRC`)만 지문(`catch_print`)에 든다. 나머지 32개는 「왜 지문 밖인가」를
한 줄씩 적은 선언표(`OUT_OF_PRINT`)에 든다. 시험은 ast 로 두 파일의 정의를 다시 세어

  ① 지문 5 · 폐포(지문 5가 부르거나 읽는 정의) · 선언표 어디에도 없는 이름(선언 밖의 새 정의)
  ② 선언표에 있는데 실제로 없는 이름(죽은 선언)
  ③ 폐포 안인데 지문 밖이고 사유가 없는 이름

이 있으면 운다. 판별은 소스 문자열을 받는 순수 함수(`problems`)가 하고, 합성 소스에
새 정의를 더하거나 선언표에서 이름을 지워 우는 것을 따로 보인다(카나리아).
`MAX_PER_TOOL`(표본 상한)은 지문 밖이라 값 시험(`cap_problems`)이 따로 묻는다.

★ 지문의 해시 입력은 넓히지 않았다. 넓히면 모든 행의 지문이 달라져 장부 전량 재측정이
  붙는다(사람 몫). 같은 길로 `test_mutate_scope_set.py` 가 지문 밖 시험을 세웠다.
★ 이 파일은 지문을 가진 도구의 이름을 낱말로 적지 않는다 — 적으면 그 도구의 지문이 이
  파일을 해시해 장부가 낡는다(`named_tests` 가 낱말로 찾는다).

밖    장부 값(생존 수 등)이 옳은지는 안 본다. 정의가 새로 생겼을 때 사람이 가르게 할 뿐이다.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import mutatescope as MS

ROOT = Path(__file__).resolve().parents[1]
FILES = ("mutate.py", "mutatescope.py")
LEDGER = ROOT / "data" / "golden" / "mutation.json"

#: 도구당 흔들 상한의 선언값. 상수를 바꾸면 이 줄도 같이 바뀌어야 하므로 바꾼 사실이 눈에 든다.
DECLARED_CAP = 4

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


def cap_problems(src: str, ledger_rows: list[dict], declared: int) -> list[str]:
    """표본 상한 `MAX_PER_TOOL` 이 선언과 같은가 · 쓰는 자리가 그 상수를 따르는가 · 장부가 그 상한으로 쟀는가."""
    got: list[str] = []
    tree = ast.parse(src)
    val = None
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MAX_PER_TOOL" for t in n.targets):
            val = ast.literal_eval(n.value)
    if val != declared:
        got.append(f"상한 상수가 선언({declared})과 다르다: {val}")
    fn = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    shake = fn.get("shake")
    if shake is None or [type(d).__name__ + ":" + getattr(d, "id", "") for d in shake.args.defaults][:1] != ["Name:MAX_PER_TOOL"]:
        got.append("표본을 쓰는 함수의 상한 기본값이 상수를 안 따른다")
    calls = [c for c in ast.walk(shake) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "pick"] if shake else []
    ok = bool(calls) and all(
        len(c.args) == 3 and isinstance(c.args[0], ast.Call) and getattr(c.args[0].func, "id", "") == "mutants"
        and getattr(c.args[1], "id", "") == "cap" and getattr(c.args[2], "id", "") == "orig"
        for c in calls)
    if not ok:
        got.append("표본을 쓰는 함수가 `pick(mutants(원문), cap, 원문)` 꼴로 안 부른다")
    main = fn.get("main")
    uses = [k for c in ast.walk(main) if isinstance(c, ast.Call) for k in c.keywords
            if k.arg == "default" and getattr(k.value, "id", "") == "MAX_PER_TOOL"] if main else []
    if not uses:
        got.append("진입점의 `--max` 기본값이 상수를 안 따른다")
    for r in ledger_rows:
        want = 0 if r["붙잡이"] == 0 else min(declared, r["전수"])
        if r["돌연변이"] != want:
            got.append(f"장부 {r['도구']} 의 흔든 수 {r['돌연변이']} 가 선언 상한({declared}) · 전수({r['전수']}) 에서 나올 {want} 이 아니다")
    return got


def _sources() -> dict[str, str]:
    return {f: (ROOT / "tools" / f).read_text(encoding="utf-8") for f in FILES}


def _rows() -> list[dict]:
    return json.loads(LEDGER.read_text(encoding="utf-8"))["도구별"]


# ── 실제 저장소 ──────────────────────────────────────────────────
def test_the_counted_definitions_match_the_declaration():
    defs = definitions(_sources())
    clo = closure(defs, IN_PRINT)
    print(f"정의 {len(defs)} · 지문 {len(IN_PRINT)} · 폐포 안(지문 밖) {len(clo)} · 선언표 {len(OUT_OF_PRINT)}")
    assert not problems(_sources(), IN_PRINT, OUT_OF_PRINT, CLOSURE_OUT), "\n".join(
        problems(_sources(), IN_PRINT, OUT_OF_PRINT, CLOSURE_OUT))
    assert (len(defs), len(IN_PRINT), len(OUT_OF_PRINT)) == (37, 5, 32)


def test_the_print_set_is_what_the_sampler_print_hashes():
    """지문 5 의 선언이 실제 해시 입력과 같다 — 연산자 표 이름은 코드에서 읽고 `pick` · `_site_keys` 는 호출을 본다."""
    ops = {f"mutate.py::{n}" for n in MS._OPERATOR_NAMES} | {"mutate.py::mutants"}
    sp = ast.parse((ROOT / "tools" / "mutatescope.py").read_text(encoding="utf-8"))
    body = next(n for n in sp.body if isinstance(n, ast.FunctionDef) and n.name == "sampler_print")
    seen = {n.id for n in ast.walk(body) if isinstance(n, ast.Name)}
    assert {"pick", "_site_keys"} <= seen, "`sampler_print` 가 `pick` · `_site_keys` 를 안 든다 — 지문 5 선언이 낡았다"
    assert IN_PRINT == ops | {"mutatescope.py::pick", "mutatescope.py::_site_keys"}


def test_every_reason_is_its_own_line():
    """일괄 문구 금지 — 사유가 서로 다르다."""
    reasons = list(OUT_OF_PRINT.values()) + list(CLOSURE_OUT.values())
    assert len(set(reasons)) == len(reasons), "같은 사유가 둘 이상이다 — 정의마다 읽고 적는다"


def test_the_sample_cap_is_pinned_outside_the_print():
    src = (ROOT / "tools" / "mutate.py").read_text(encoding="utf-8")
    got = cap_problems(src, _rows(), DECLARED_CAP)
    assert not got, "\n".join(got)


# ── 카나리아(합성 결함) — 판별 함수가 실제로 우는가 ──────────────
_BASE = {
    "a.py": "K = 1\n\n\ndef pick(x):\n    return _keys(x)\n\n\ndef _keys(x):\n    return x\n\n\ndef other():\n    return K\n",
}
_IN = {"a.py::pick"}
_OUT = {"a.py::K": "상수라 값을 정하지 않는다", "a.py::_keys": "이름을 바꾸는 도우미일 뿐이다",
        "a.py::other": "아무도 안 부르는 도우미다"}
_CLO = {"a.py::_keys": "표본 키를 만든다 — 지문에 안 들지만 시험이 따로 묻는다"}


def test_the_synthetic_base_is_quiet_when_declared():
    out = {k: v for k, v in _OUT.items() if k != "a.py::_keys"}
    assert problems(_BASE, _IN, out, _CLO) == []


def test_canary_a_new_definition_outside_the_declaration_cries():
    out = {k: v for k, v in _OUT.items() if k != "a.py::_keys"}
    grown = {"a.py": _BASE["a.py"] + "\n\ndef brand_new():\n    return 2\n"}
    got = problems(grown, _IN, out, _CLO)
    print("카나리아(새 함수):", got)
    assert got == ["선언 밖의 새 정의: a.py::brand_new"]
    grown = {"a.py": _BASE["a.py"] + "\nLIMIT = 5\n"}
    got = problems(grown, _IN, out, _CLO)
    print("카나리아(새 대입):", got)
    assert got == ["선언 밖의 새 정의: a.py::LIMIT"]


def test_canary_deleting_a_name_from_the_table_cries():
    out = {k: v for k, v in _OUT.items() if k not in ("a.py::_keys", "a.py::other")}
    got = problems(_BASE, _IN, out, _CLO)
    print("카나리아(선언표에서 지움):", got)
    assert got == ["선언 밖의 새 정의: a.py::other"]


def test_canary_a_dead_declaration_cries():
    out = {k: v for k, v in _OUT.items() if k != "a.py::_keys"}
    out["a.py::gone"] = "없어진 정의를 아직 적고 있다"
    got = problems(_BASE, _IN, out, _CLO)
    print("카나리아(죽은 선언):", got)
    assert got == ["선언표에 있는데 실제로 없다(죽은 선언): a.py::gone"]
    got = problems(_BASE, _IN | {"a.py::vanished"}, {k: v for k, v in _OUT.items() if k != "a.py::_keys"}, _CLO)
    assert got == ["지문 5 에 적었는데 실제로 없다(죽은 선언): a.py::vanished"]


def test_canary_a_closure_member_without_a_reason_cries():
    """지문이 부르는 새 도우미는 지문에 들거나 폐포 선언에 사유를 적어야 한다."""
    out = {k: v for k, v in _OUT.items() if k != "a.py::_keys"}
    got = problems(_BASE, _IN, out, {})
    print("카나리아(폐포 안 · 사유 없음):", got)
    assert got == ["폐포 안인데 지문 밖이고 사유가 없다: a.py::_keys"]
    wired = {"a.py": _BASE["a.py"].replace("return _keys(x)", "return _keys(x) + K")}
    got = problems(wired, _IN, {"a.py::other": _OUT["a.py::other"]}, _CLO)
    assert got == ["폐포 안인데 지문 밖이고 사유가 없다: a.py::K"]


def test_canary_a_reason_that_is_blank_cries():
    out = {k: v for k, v in _OUT.items() if k != "a.py::_keys"}
    out["a.py::K"] = " "
    assert problems(_BASE, _IN, out, _CLO) == ["사유가 비었거나 짧다: a.py::K"]


def test_canary_the_cap_checks_cry_on_a_broken_source_and_ledger():
    real = (ROOT / "tools" / "mutate.py").read_text(encoding="utf-8")
    rows = [{"도구": "t", "돌연변이": 4, "전수": 9, "붙잡이": 1}]
    assert cap_problems(real, rows, DECLARED_CAP) == []
    bumped = real.replace(f"MAX_PER_TOOL = {DECLARED_CAP}", f"MAX_PER_TOOL = {DECLARED_CAP + 1}", 1)
    got = cap_problems(bumped, rows, DECLARED_CAP)
    print("카나리아(상한 바꿈):", got)
    assert any("선언" in g and "다르다" in g for g in got)
    unwired = real.replace("pick(mutants(orig), cap, orig)", "pick(mutants(orig), cap)", 1)
    assert unwired != real
    assert any("꼴로 안 부른다" in g for g in cap_problems(unwired, rows, DECLARED_CAP))
    detached = real.replace("cap: int = MAX_PER_TOOL", "cap: int = 4", 1)
    assert detached != real
    assert any("기본값이 상수를 안 따른다" in g for g in cap_problems(detached, rows, DECLARED_CAP))
    short = [{"도구": "t", "돌연변이": 3, "전수": 9, "붙잡이": 1}]
    assert any("장부 t" in g for g in cap_problems(real, short, DECLARED_CAP))
    assert cap_problems(real, [{"도구": "t", "돌연변이": 2, "전수": 2, "붙잡이": 1}], DECLARED_CAP) == []


def test_canary_a_new_definition_in_the_real_source_cries():
    """실제 두 파일의 사본에 새 정의를 더하면 같은 판별이 운다 — 파일은 안 건드린다."""
    srcs = _sources()
    srcs["mutate.py"] += "\n\ndef brand_new_helper():\n    return 1\n"
    got = problems(srcs, IN_PRINT, OUT_OF_PRINT, CLOSURE_OUT)
    print("카나리아(실제 사본):", got)
    assert got == ["선언 밖의 새 정의: mutate.py::brand_new_helper"]
    srcs = _sources()
    srcs["mutatescope.py"] = srcs["mutatescope.py"].replace("def targets(", "def targets_renamed(", 1)
    got = problems(srcs, IN_PRINT, OUT_OF_PRINT, CLOSURE_OUT)
    assert got == ["선언 밖의 새 정의: mutatescope.py::targets_renamed",
                   "선언표에 있는데 실제로 없다(죽은 선언): mutatescope.py::targets"]

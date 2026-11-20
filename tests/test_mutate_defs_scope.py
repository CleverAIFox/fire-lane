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
import pushdenom as D
from pushdenom import CLOSURE_OUT, IN_PRINT, OUT_OF_PRINT, closure, definitions, problems

ROOT = Path(__file__).resolve().parents[1]
FILES = D.PRINT_FILES
LEDGER = ROOT / "data" / "golden" / "mutation.json"

#: 도구당 흔들 상한의 선언값. 상수를 바꾸면 이 줄도 같이 바뀌어야 하므로 바꾼 사실이 눈에 든다.
DECLARED_CAP = 4

# 지문 5 · 선언표 · 판별 함수는 `pushdenom` 에 산다 — 도구 출력(`pushready` ㉤ 의 분모 줄)과 이 시험이 같은 것을 센다(복사본이 둘이면 갈린다).


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

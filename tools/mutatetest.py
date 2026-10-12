#!/usr/bin/env python3
"""
mutatetest.py — **`mutate.py` 의 자기검사.** 판별식만 산다.

── 왜 갈라졌나 (2026-10-09 · DECISIONS §445 · PLAN #166 닫힘) ──
`tools/mutate.py` 가 상한(600)을 넘었는데 **쪼개는 길이 막혀 있었다.**
`catch_print()` 가 `tools/<도구>.py` 와 그 이름을 적은 시험만 해시했으므로
자기검사를 옆 파일로 떼면 **문을 고쳐도 장부가 안 낡는다** — `#159` 가 고친
구멍의 재발이고, 그 막힘 때문에 예외 줄이 앉아 있었다.

★ 길을 먼저 넓혔다 — `catch_print` 가 **그 도구가 끌어오는 `tools/` 모듈**도
  해시한다(`local_imports`). 그래서 이 파일이 바뀌면 `mutate` 가 낡는다.
  **갈라 놓고 지문을 안 넓히면 그것이 §431 의 그 구멍이다.**

★ 흔드는 쪽과 재는 쪽이 겹치면 안 된다(§398-6 · §443-6) — 이 파일은
  **아무것도 안 쓴다.** 합성 입력만 민다. `mutate` 의 실물 장부는 안 연다.

IN    tools/mutate.py 의 판별식 (import)
OUT   표준출력 · rc
밖    **흔들지 않는다** — 돌연변이를 만들고 붙잡이를 돌리는 것은 `mutate` 다.
      **장부를 안 쓴다** — 쓰는 자리는 `mutate --write` 하나다.
부류  몸통   진입점이 **아니다.** `mutate.py --selftest` 가 부른다  (DECISIONS §398)
"""
from __future__ import annotations

from mutate import _ratchet_line, catchers, mutants, pick, sort_survivors
from mutatescope import (
    TOOLS,
    _imports_ratchet,
    catch_print,
    imported,
    local_imports,
    named_tests,
    targets,
)


def selftest() -> int:
    fails: list[str] = []
    # ★ 2026-10-06 (DECISIONS §410). 생존 가름 — **양방향**으로 민다.
    #   실물로만 재면 「언제나 래칫」과 「언제나 안 가름」을 못 가른다(§230).
    _ln = _ratchet_line("sealcov", "SEALED_FILES")
    _synth = {"도구별": [{"도구": "sealcov",
                        "생존": [f"{_ln}: 363 → 364", f"{_ln + 900}: 1 → 2"]}]}
    _held, _rest = sort_survivors(_synth)
    if [t for t, _, _ in _held] != ["sealcov"] or len(_held) != 1:
        fails.append(f"래칫 상수 생존을 안 가린다 — 든 것 {_held}")
    if len(_rest) != 1:
        fails.append(f"래칫이 아닌 생존을 래칫으로 센다 — 남은 것 {_rest}")
    if _held and _held[0][2] != "SEALED_FILES":
        fails.append(f"래칫 이름을 틀리게 읽는다 — {_held[0][2] if _held else None}")

    # ★ 2026-10-08 (DECISIONS §431 · PLAN #159). 지문이 **시험에 반응하나.**
    #   안 하면 「시험이 붙든다」를 시험 없이 주장한다.
    #   ★ 과녁 **첫째**를 쓰면 안 된다 — `archcost` 는 그 이름을 적은 시험이
    #     없다(실측 2026-10-08). 시험이 있는 첫 과녁을 고르고, 하나도 없으면
    #     그때 운다. 「없는 것」과 「못 고른 것」은 다른 사실이다(족 6).
    _t, _q = "", []
    for _c in targets():
        if (_q := named_tests(_c)):
            _t = _c
            break
    if not _t:
        fails.append("과녁 중 이름이 적힌 시험을 가진 것이 하나도 없다 — 지문의 전제가 깨졌다")
    else:
        _was = catch_print(_t)
        _f = _q[0]
        _orig = _f.read_bytes()
        try:
            _f.write_bytes(_orig + b"\n# \xec\xa7\x80\xeb\xac\xb8 \xec\xb9\xb4\xeb\x82\x98\xeb\xa6\xac\xec\x95\x84\n")
            if catch_print(_t) == _was:
                fails.append(f"시험 파일을 고쳤는데 {_t} 의 지문이 안 바뀐다 — "
                             "장부가 안 낡는다(#159 ①)")
        finally:
            _f.write_bytes(_orig)
        if catch_print(_t) != _was:
            fails.append("되돌렸는데 지문이 안 돌아온다 — 지문이 결정적이지 않다")

    # ★ 2026-10-09 (§440-10). **선언을 옆집에 둔 관문도 과녁인가** — 양방향.
    if not _imports_ratchet("from sizetable import EXCEPTIONS\n", {"sizetable"}):
        fails.append("옆집 선언을 import 하는데 과녁으로 안 센다")
    if _imports_ratchet("from json import loads\n", {"sizetable"}):
        fails.append("선언 안 든 모듈을 import 해도 과녁으로 센다 — 그물이 샌다")
    if "sizecheck" not in targets():
        fails.append("sizecheck 가 과녁에 없다 — 표를 뗀 관문이 조용히 빠진다")

    # ★ 2026-10-09 (§440-10). 과녁 **밖** 줄이 지워지나. 합성으로 민다.
    _k = {"sealcov": {"도구": "sealcov"}, "없는도구": {"도구": "없는도구"}}
    _g = sorted(set(_k) - set(targets()))
    if _g != ["없는도구"]:
        fails.append(f"과녁 밖 가림이 틀리다 — {_g}")

    # ★ 2026-10-08. `--tool X --write` 가 **남의 행을 지우지 않나.** 합성 장부로 민다.
    _keep = {"a": {"도구": "a", "돌연변이": 3, "생존": ["x"], "붙잡이": 1},
             "b": {"도구": "b", "돌연변이": 5, "생존": [], "붙잡이": 1}}
    _new = [{"도구": "b", "돌연변이": 7, "생존": ["y", "z"], "붙잡이": 2}]
    _m = dict(_keep); _m.update({r["도구"]: r for r in _new})
    _rows = [_m[k] for k in sorted(_m)]
    if [r["도구"] for r in _rows] != ["a", "b"]:
        fails.append(f"한 도구를 적었는데 남의 행이 사라진다 — {[r['도구'] for r in _rows]}")
    if sum(r["돌연변이"] for r in _rows) != 10 or sum(len(r["생존"]) for r in _rows) != 3:
        fails.append("합친 총계가 틀리다 — 분모가 거짓말을 한다")

    src = "def f(a, b):\n    if a >= 3 and not b:\n        return True\n    return False\n"
    got = {w.split(": ", 1)[1] for w, _ in mutants(src)}
    for want in (">= → >", "and → or", "not 제거", "True → False",
                 "False → True", "3 → 4"):
        if want not in got:
            fails.append(f"흔들기가 「{want}」 를 안 낸다")
    if any("import" in w for w, _ in mutants(src)):
        fails.append("이름·import 를 건드린다 — 전부 죽으면 아무것도 안 잰 것이다")

    # ★ 주석이 살아남는가 — `ast.unparse` 로 다시 쓰면 파일 전체가 돌연변이가 된다
    withdoc = '"""머리말."""\nX = 1  # 꼬리 주석\n'
    if not all("꼬리 주석" in b and "머리말" in b for _, b in mutants(withdoc)):
        fails.append("돌연변이가 주석을 날린다 — 변경이 연산자 하나가 아니다")

    # ★ 결정적인가 — 두 번 돌려 같은 순서인가
    if [w for w, _ in mutants(src)] != [w for w, _ in mutants(src)]:
        fails.append("같은 입력에 순서가 다르다")

    # ★ 빈 그물 — 못 읽는 소스에 **조용히 0** 을 내면 「흔들었는데 다 죽었다」가 된다
    if mutants("def (:::") != []:
        fails.append("문법 오류에 돌연변이를 낸다")
    if not mutants("if 1 >= 2:\n    pass\n"):
        fails.append("멀쩡한 소스에 하나도 안 낸다 — 그물이 비었다")

    # ★ 상한이 **고르게** 고르는가 — 앞에서 자르면 머리말만 흔든다
    ten = [(f"{i}", "") for i in range(10)]
    got = [w for w, _ in pick(ten, 3)]
    if got != ["0", "3", "6"]:
        fails.append(f"상한이 고르게 안 고른다 — {got}")
    if pick(ten, 0) != ten or pick(ten, 99) != ten:
        fails.append("상한 0·초과에서 전수를 안 낸다")

    # ★ 붙잡이 도출이 **자기 자신**을 찾는가
    c = catchers("mutate")
    if not any("--selftest" in x for x in c):
        fails.append("제 자기검사를 붙잡이로 안 센다")
    if any("pytest" in x for x in c):
        fails.append("기본에 pytest 가 들어갔다 — 실측 한 시간 넘어 안 끝난다")
    if not any("pytest" in x for x in catchers("mutate", deep=True)):
        fails.append("--deep 이 시험 파일을 안 집는다 — 깃발이 죽었다")

    # ★ 2026-10-09 (DECISIONS §445 · PLAN #166). **지문이 옆집을 보는가.**
    #   이 세 문이 없으면 쪼개는 길을 넓힌 그 변경이 **제 구멍을 다시 팔 수 있다** —
    #   실제로 처음 판은 함수 안의 `import` 를 못 봐서 이 파일이 지문 밖이었다.
    if "mutatetest" not in local_imports((TOOLS / "mutate.py").read_text(encoding="utf-8")):
        fails.append("지문이 **이 파일**을 안 덮는다 — 문을 고쳐도 장부가 안 낡는다")
    if local_imports("def f():\n    from sizetable import EXCEPTIONS\n") != ["sizetable"]:
        fails.append("함수 **안**의 import 를 못 본다 — 맞물림을 끊은 자리가 전부 그 꼴이다")
    if local_imports("import json\nfrom pathlib import Path\n"):
        fails.append("표준 꾸러미를 `tools/` 모듈로 센다")
    if imported("def (:::"):
        fails.append("문법 오류에서 모듈 이름을 낸다")
    if imported("import a.b.c\n") != {"a"}:
        fails.append("점 있는 이름의 최상위를 안 집는다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 26")
    return 1 if fails else 0

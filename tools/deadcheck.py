#!/usr/bin/env python3
"""
deadcheck.py — **검사가 죽었는가**를 검사한다.

★ 이 저장소가 반복해서 당한 형태는 "검사가 있는데 안 운다" 다.
  검사를 늘리는 것으로는 못 잡는다. 늘린 검사도 같은 병에 걸린다.
  그래서 검사를 **대상으로 삼는** 도구가 하나 필요하다.

프로브 다섯. 전부 정적이고 전부 **세는 것**으로 끝난다.

  ① 빈 그물      검사가 만드는 후보 집합이 구조적으로 빌 수 있는가
  ② 손목록       코드에 박힌 목록이 데이터 원본보다 좁은가
  ③ 조용한 통과  실패해야 할 자리에서 return / pass / continue 하는가
  ④ 죽은 게이트  CI 스텝이 없는 파일을 조건으로 걸고 있는가
  ⑤ 좁은 범위    검사 대상 glob 이 실제 파일 집합보다 좁은가

OUT  REDLIST.json  ·  종료코드 = 빨간불 건수(0 이면 초록)

    맨몸        프로브를 돌고 전건을 찍는다. 종료코드 = 건수 (사람이 읽는 판)
    --selftest  **양성 대조만.** 프로브가 **합성 트리에 심은 결함**을 내는가
    --ratchet   ★ **관문.** 프로브별 수가 `CEILING` 과 같은가 (양방향)

★ **생사는 합성 트리에서 묻는다**(2026-09-21 · DECISIONS §208). 종전에는
  「실제 저장소에서 0건이면 죽은 것」으로 읽었는데, 그러면 프로브가 제 일을
  다 해서 0건이 된 날 관문이 빨개진다 — 실제로 `② 손목록` 이 59건 → 0건이 된
  바로 그날 봉인이 막혔다. `CONTROLS` 가 프로브마다 일부러 결함을 심은
  트리를 짓고, 거기서 울어야 살아 있는 것이다. 그러면 **실제 트리의 0건은
  청결**이고, 실제 트리의 수를 보는 것은 `--ratchet` 의 일이다.

★ **2026-09-20 — `--selftest` 를 관문으로 쓰면 안 된다**(DECISIONS §202).
  그것이 묻는 것은 「프로브가 살아 있는가」지 「저장소가 깨끗한가」가 아니다.
  그런데 `verify.sh` 도 CI 도 `--selftest` 만 돌았고, 단계 이름은
  「검사가 죽었는가」였다 — **이름이 약속한 범위가 실제보다 넓고 그것이
  선언돼 있지 않았다.** 그 상태로 148건이 조용히 쌓였다.
  더 나쁜 것은 방향이다 — `--selftest` 는 **결함이 많을수록 더 확실히 통과한다.**
  관문은 `--ratchet` 이다. `--selftest` 는 그 안에서 양성 대조로만 쓴다.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HITS: list[dict] = []


def hit(probe: str, path: Path, line: int, what: str, count: str = "") -> None:
    # ★ 2026-09-21. 프로브는 **합성 트리**에서도 돈다(아래 「양성 대조」).
    #   그 경로는 `ROOT` 밖이라 `relative_to` 가 죽는다 — 여기서 죽으면
    #   양성 대조 자체가 못 돈다.
    try:
        f = str(path.relative_to(ROOT))
    except ValueError:
        f = str(path)
    HITS.append({
        "probe": probe,
        "file": f,
        "line": line,
        "what": what,
        "count": count,
    })


def src(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def tree(p: Path) -> ast.Module | None:
    try:
        return ast.parse(src(p))
    except SyntaxError:
        return None


# ── ① 빈 그물 ───────────────────────────────────────────────────
# 검사가 대장 항목을 `.get("X")` 로 읽는데 그 블록에 X 키가 0건이면
# 그 검사는 구조적으로 빌 수 있다 — 영원히 통과한다.
#
# ★ 2026-09-22 (PLAN §13 W10-1 · 전수 분류). **짝짓기를 수신자 단위로 조였다.**
#   종전에는 「함수가 블록을 적재했는가」와 「함수 본문 어디엔가 `["X"]` 가
#   있는가」를 따로 보고 합쳤다. ②·⑤ 가 앓던 것과 같은 병이다 — 41건 중
#   16건이 **대장 항목이 아닌 dict** 를 읽은 것이었다(`triage()` 의 보고용
#   `r["ext"]`, `ingest.build()` 가 datasets 항목 `e["kind"]` 를 읽는데
#   같은 함수가 outputs 도 적재한다는 이유로 outputs 에 물린 것).
#   지금은 `for k, v in <블록>.items()` · `v = <블록>[k]` 로 **그 블록에
#   묶인 이름**만 수신자로 인정한다. 이름을 다시 묶는 루프 안은 그 루프의 것이다.
# ★ 같은 날 **「드문 키」 판정(0 < n < 절반)을 뺐다.** 그것은 빈 그물이 아니라
#   **선택 필드**다 — 23건 전부가 `files`/`stems`(stem 의 대안) · `on_demand` ·
#   `norm_convert` · `layer` 처럼 **선언한 항목에만 뜻이 있는** 키였다.
#   n ≥ 1 이면 그물은 비어 있지 않다. 「범위가 좁은가」는 ⑤ 의 물음이다.
#   23분의 0 이 신호인 판정은 아무도 안 읽는다(DECISIONS §73).
_BLOCKS = ("datasets", "retired", "outputs")
_WRAP = ("sorted", "list", "dict", "enumerate", "reversed")
_COMP = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


def _str(e: ast.AST | None) -> str | None:
    return e.value if isinstance(e, ast.Constant) and isinstance(e.value, str) else None


def _entry_reads(fn: ast.AST):
    """함수 하나 → (줄, 블록, 키). **그 블록의 항목에 묶인 이름**에 대한 읽기만."""
    cont: dict[str, str] = {}

    def blk_of(e):
        if isinstance(e, ast.BoolOp) and isinstance(e.op, ast.Or):
            return blk_of(e.values[0])
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) \
                and e.func.id in _WRAP and e.args:
            return blk_of(e.args[0])
        if isinstance(e, ast.Name):
            return cont.get(e.id)
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) \
                and e.func.attr == "get" and e.args:
            k = _str(e.args[0])
            return k if k in _BLOCKS else None
        if isinstance(e, ast.Subscript):
            k = _str(e.slice)
            return k if k in _BLOCKS else None
        return None

    def entry_of(e):
        if isinstance(e, ast.BoolOp) and isinstance(e.op, ast.Or):
            return entry_of(e.values[0])
        if isinstance(e, ast.Subscript) and _str(e.slice) not in _BLOCKS:
            return blk_of(e.value)
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) \
                and e.func.attr == "get" and e.args and _str(e.args[0]) not in _BLOCKS:
            return blk_of(e.func.value)
        return None

    def loop_var(it, tgt):
        while isinstance(it, ast.Call) and isinstance(it.func, ast.Name) \
                and it.func.id in _WRAP and it.args:
            it = it.args[0]
        if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute)
                and it.func.attr in ("items", "values")):
            return None
        b = blk_of(it.func.value)
        if not b:
            return None
        if it.func.attr == "items" and isinstance(tgt, ast.Tuple) and len(tgt.elts) == 2 \
                and isinstance(tgt.elts[1], ast.Name):
            return tgt.elts[1].id, b
        if it.func.attr == "values" and isinstance(tgt, ast.Name):
            return tgt.id, b
        return None

    # 컨테이너 — `DS = led["datasets"]` · `ds = y.get("datasets") or {}`
    for _ in range(3):
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                    and isinstance(n.targets[0], ast.Name) and (b := blk_of(n.value)):
                cont[n.targets[0].id] = b
    # 묶음 — (이름, 블록, 범위, 묶은 노드). 루프·내포는 제 몸통이 범위다.
    binds: list[tuple[str, str, list, ast.AST | None]] = []
    assigned: dict[str, set] = {}
    for n in ast.walk(fn):
        if isinstance(n, ast.For):
            if lv := loop_var(n.iter, n.target):
                binds.append((*lv, n.body, n))
        elif isinstance(n, _COMP):
            for g in n.generators:
                if lv := loop_var(g.iter, g.target):
                    binds.append((*lv, [n], g))
        elif isinstance(n, (ast.Assign, ast.NamedExpr)):
            t = (n.targets[0] if len(n.targets) == 1 else None) \
                if isinstance(n, ast.Assign) else n.target
            if isinstance(t, ast.Name):
                assigned.setdefault(t.id, set()).add(entry_of(n.value))
    # 대입 묶음은 **그 이름이 늘 같은 블록일 때만** 함수 전체가 범위다
    for nm, bs in assigned.items():
        if len(bs) == 1 and None not in bs:
            binds.append((nm, next(iter(bs)), list(ast.iter_child_nodes(fn)), None))
    owners: dict[str, list] = {}
    for nm, _b, _sc, own in binds:
        if own is not None:
            owners.setdefault(nm, []).append(own)

    def rebinds(x, nm, own) -> bool:
        others = [o for o in owners.get(nm, []) if o is not own]
        if any(x is o for o in others):
            return True
        return isinstance(x, _COMP) and any(g is o for g in x.generators for o in others)

    for nm, b, scope, own in binds:
        stack = list(scope)
        while stack:
            x = stack.pop()
            if rebinds(x, nm, own):
                continue            # 같은 이름을 다른 블록에 다시 묶은 자리는 그쪽 것이다
            stack.extend(ast.iter_child_nodes(x))
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) \
                    and x.func.attr == "get" and x.args \
                    and isinstance(x.func.value, ast.Name) and x.func.value.id == nm \
                    and (k := _str(x.args[0])):
                yield x.lineno, b, k
            elif isinstance(x, ast.Subscript) and isinstance(x.value, ast.Name) \
                    and x.value.id == nm and (k := _str(x.slice)):
                yield x.lineno, b, k


# ★ 면제 — `"파일::함수::블록.키"` → 사유. 적는 순간 세어지고
#   `tests/test_deadcheck_probes.py` 가 「면제했는데 실은 안 걸리는 것」을 지운다.
EXEMPT_EMPTY_NET = {
    "tools/sweep.py::retired_names::retired.origin_name":
        "세 경로(origin_name · stem · file/files)의 **합집합**이 그물이다 — 오늘은 files 가 "
        "4/4 로 채운다. origin_name 은 datasets 에 실재하고(gjcity_road_facility) 그 항목이 "
        "폐기될 때 취득처 이름으로 landing 을 알아보는 길이다. 한 경로만 보면 intake 가 "
        "retired 를 통째로 놓친 2026-09-10 의 형태로 돌아간다(머리말)",
    "tests/test_guards.py::test_acquire_stage_and_quarantine_do_not_fight::retired.ext":
        "그물이 아니라 **기본값이 있는 값 읽기**다(`v.get(\"ext\") or [\"csv\"]`). 그물 `ret` 는 "
        "바로 아래 `assert ret` 가 비지 않음을 강제한다. ext 는 datasets 72/72 에 있는 키라 "
        "stem 으로 폐기되는 항목이 들고 올 수 있다",
}


def probe_empty_net(root: Path = ROOT) -> None:
    import yaml
    led = yaml.safe_load(src(root / "sources.yaml"))
    blocks = {b: led.get(b) or {} for b in _BLOCKS}
    # 블록별로 실제 존재하는 키의 건수
    have: dict[str, dict[str, int]] = {}
    for b, items in blocks.items():
        c: dict[str, int] = {}
        for v in items.values():
            for k in (v or {}):
                c[k] = c.get(k, 0) + 1
        have[b] = c

    # ★ 대장 스키마에 실재하는 키만 대상이다. 무관한 dict 접근까지 물면
    #   730건이 나오고 그 목록은 아무도 안 읽는다 — 잘못된 경보가
    #   진짜 경보를 죽인다(DECISIONS §73).
    SCHEMA = {k for c in have.values() for k in c}

    seen: set[tuple[str, str, str, str]] = set()
    for p in sorted((root / "tests").rglob("*.py")) + sorted((root / "tools").rglob("*.py")) \
            + sorted((root / "src").rglob("*.py")):
        s = src(p)
        if "sources.yaml" not in s and "ledger" not in s.lower():
            continue
        t = tree(p)
        if t is None:
            continue
        try:
            rel = p.relative_to(root).as_posix()
        except ValueError:
            rel = str(p)
        for fn in ast.walk(t):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for ln, blk, key in _entry_reads(fn):
                tot = len(blocks[blk])
                if key not in SCHEMA or have[blk].get(key, 0) or not tot:
                    continue
                sig = (rel, fn.name, blk, key)
                if sig in seen or f"{rel}::{fn.name}::{blk}.{key}" in EXEMPT_EMPTY_NET:
                    continue
                seen.add(sig)
                hit("① 빈 그물", p, ln,
                    f"{fn.name}() 가 {blk} 항목을 `{key}` 로 읽는데 그 키가 "
                    f"**0/{tot}** 이다 — 이 검사는 구조적으로 빌 수 있다",
                    f"0/{tot}")


# ── ② 손목록 ────────────────────────────────────────────────────
# 대문자 상수에 담긴 리터럴 목록. 그 목록이 유도 가능한 원본보다 좁으면
# 원본이 늘어도 검사가 안 따라간다.
#
# ★ 2026-09-20 (DECISIONS §202). **이 프로브는 옳은 답을 틀린 이유로 냈다.**
#   종전 판별은 「원본 이름이 파일 본문 아무 데나 나오는가」(`key in src(p).lower()`)
#   였다. `tools/` 밑 파일은 거의 전부 머리말에 자기 경로(`tools/x.py`)를 적으므로
#   **`"tools"` 가 항상 참**이고, 분모는 `tools/*.py` 64종이 됐다. 그래서
#   `DOCS 가 4개 리터럴인데 tools 는 64종이다` 같은, **비교 자체가 성립하지 않는**
#   짝짓기가 59건 쌓였다. 그중 하나가 `golden.py:151 WATCH` 였다 — 맞는 결함인데
#   **맞는 이유로 잡힌 것이 아니다.**
#
#   신호가 59건 중 1건이면 사람은 목록을 안 읽는다. 실제로 아무도 안 읽었다
#   (`verify.sh` 도 CI 도 `--selftest` 만 돌았다 — 아래 `main()` 의 ★ 참조).
#   **틀린 이유로 옳은 것은 다음 번에 틀린다.**
#
#   지금 판별은 **부분집합**이다 — 리터럴 *전부* 가 그 원본의 실제 원소일 때만
#   짝짓는다. 그러면 분모가 의미를 갖고, 59건이 실재 3건으로 떨어진다.
# ★ 원본을 못 재면 **건너뛰지 않고 빨간불을 낸다.** 재는 쪽이 죽으면 프로브도
#   죽는데, 조용히 통과하면 그것이 곧 ① 빈 그물이다 — 이 도구가 세는 바로 그 병.
def _members(root: Path = ROOT) -> dict[str, tuple[set[str], int]]:
    """원본 이름 → (원소로 인정하는 표기 집합, 실제 종수).

    좁은 것을 먼저 둔다. `판정코드` ⊂ `src` 라 순서가 뒤집히면 `WATCH` 가
    `src` 58종에 붙어 **분모가 다시 헐거워진다.**

    ★ `root` 가 저장소가 아니면(양성 대조의 합성 트리) `판정코드` 는 안 넣는다 —
      그것은 설치된 `firelane` 패키지의 import 닫힘이라 합성할 수가 없다.
      **조용히 빼는 것이 아니라 여기 적는다.** 합성 트리가 거는 것은 ②의
      **짝짓기 규칙**(부분집합이면 운다)이지 판정코드 분모가 아니다.
    """
    import yaml
    out: dict[str, tuple[set[str], int]] = {}

    def spell(rels: list[str]) -> set[str]:
        return {x for r in rels for x in (r, Path(r).name, Path(r).stem)}

    if root == ROOT:
        # 판정 코드의 닫힘은 여기 하나다 — golden 도 같은 것을 부른다
        from firelane.shardseal import code_closure
        jud = [p.relative_to(ROOT).as_posix() for p in code_closure("firelane.segments")]
        out["판정코드"] = (spell(jud), len(jud))

    y = yaml.safe_load(src(root / "sources.yaml"))
    for k in ("layers", "scopes", "datasets", "outputs"):
        keys = set((y.get(k) or {}).keys())
        out[k] = (keys, len(keys))

    tl = [p.relative_to(root).as_posix() for p in (root / "tools").glob("*.py")]
    out["tools"] = (spell(tl), len(tl))
    sl = [p.relative_to(root).as_posix() for p in (root / "src").rglob("*.py")]
    out["src"] = (spell(sl), len(sl))
    return out


# ★ 면제 — **좁은 것이 의도인 자리.** 사유를 적는다. 적는 순간 세어지고,
#   `tests/test_deadcheck_probes.py::test_exemptions_are_not_dead` 가
#   「면제했는데 실은 안 걸리는 것」을 지운다(`test_tools_are_wired` 와 같은 답 —
#   2026-09-20 에 31개 면제 중 12개가 죽어 있었다).
EXEMPT_HANDLIST = {
    "STAGE_SCRIPTS": "파이프라인 **단계**로 도는 것만. `seg/` 는 부품이지 단계가 아니다 — 머리말이 그 경계를 적는다",
    "SELF": "대장 기계 자신. 자기를 소비자로 세면 모든 대장 항목이 영원히 소비자를 갖는다",
    "_LEGACY_WATCH": "**동결된 옛 범위.** `golden.py rescope` 가 「옛 잠금이 이 범위로 재서 같은가」를 "
                     "증명할 때만 쓴다. 늘어나면 안 되는 목록이라 유도하면 증명이 깨진다",
    # ★ 2026-09-23 (W3-6). ② 를 src 로 넓히며 걸린 유일한 건. 값은 5 → 13종으로 넓혔다.
    "CRITICAL": "판정 관문의 입력 목록. **유도하면 대장의 서술 칸이 관문을 움직인다** — 분모 "
                "`datasets.*.feeds` 는 `shardseal.DOC_KEYS` 가 「산출에 안 닿는 칸」으로 분류한 필드고"
                "(§216-1), 그 한 줄이 관문을 조용히 **좁히면** 거짓 초록이다. 값은 코드에 두고 어긋나면 "
                "우는 강제자를 뒀다 — `test_guards.py::test_critical_covers_every_dataset_feeding_judgment_code`",
}


def probe_handlist(root: Path = ROOT) -> None:
    try:
        mem = _members(root)
    except Exception as e:
        hit("② 손목록", ROOT / "tools" / "deadcheck.py", 0,
            f"원본을 못 쟀다 — {type(e).__name__}: {e}. **분모가 없으면 이 프로브는 빈 그물이다**")
        return
    # ★ 2026-09-23 (W3-6). `src` 를 넣었다 — 검사 코드만 보는 검사는 **제품 코드의 같은 병**을
    #   못 본다. `guards.CRITICAL`(5종)이 대장 13종보다 좁은 채로 대상 밖에 살았다.
    for p in sorted((root / "tests").rglob("*.py")) + sorted((root / "tools").rglob("*.py")) \
            + sorted((root / "src").rglob("*.py")):
        t = tree(p)
        if t is None:
            continue
        for node in ast.walk(t):
            if not isinstance(node, ast.Assign):
                continue
            tgt = node.targets[0]
            if not isinstance(tgt, ast.Name) or not tgt.id.isupper():
                continue
            val = node.value
            if not isinstance(val, (ast.List, ast.Tuple, ast.Set)):
                continue
            items = [e.value for e in val.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(items) < 3 or tgt.id in EXEMPT_HANDLIST:
                continue
            n = len(items)
            for key, (elems, tot) in mem.items():
                if n < tot and all(i in elems for i in items):
                    hit("② 손목록", p, node.lineno,
                        f"{tgt.id} 가 {key} 의 부분집합이다 ({n}/{tot}) "
                        f"— 원본에서 유도하지 않으면 늘어도 안 따라간다", f"{n}/{tot}")
                    break


# ── ③ 조용한 통과 ───────────────────────────────────────────────
# 실패해야 할 자리에서 조용히 빠져나가는 형태 셋.
#
# ★ 2026-09-22 (PLAN §13 W10-1 · 전수 분류). (a) 의 「조용함」을 조였다 — 두 가지.
#   · `pass` 는 빠져나가지 않는다. **다음 문장으로 떨어진다.** 함수의 마지막
#     문장인 `try` 에서만 `pass` 가 곧 통과다. `doc_fsck.check_docx_revised()` 의
#     얕은 저장소 탐지(`except: pass` 뒤에 `git log` 이 이어진다)가 그 오검이었다.
#   · `return [f"...못 쟀다"]` 는 조용하지 않다. **말하는 반환**이다. 빈 값
#     (`None` · `[]` · `()` · `{}` · `""` · `False` · `0`)을 돌려줄 때만 조용하다.
def _quiet_return(b: ast.AST) -> bool:
    if not isinstance(b, ast.Return):
        return False
    v = b.value
    if v is None:
        return True
    if isinstance(v, ast.Constant):
        return not v.value
    return isinstance(v, (ast.List, ast.Tuple, ast.Set, ast.Dict)) and not (
        getattr(v, "elts", None) or getattr(v, "keys", None))


def _asserts(x: ast.AST) -> bool:
    """assert 문 · `pytest.fail` · `assert_*`(np.testing · pandas.testing 류) 호출."""
    if isinstance(x, ast.Assert):
        return True
    if isinstance(x, ast.Call):
        f = x.func
        nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        return nm.startswith("assert") or nm == "fail"
    return False


# ★ 2026-09-22 재검토. 위의 `pass` 조임(끝 `try` 에서만)이 **한쪽을 열었다** —
#   함수 중간의 `for …: try: assert … except Exception: pass` 는 다음 문장으로
#   떨어지지만 **assert 가 낸 실패는 이미 삼켜졌다.** 그래서 (c) 를 더한다 — 넓은
#   예외(Exception · BaseException · 맨 except)를 잡는 handler 가 조용하고 그 try
#   몸통에 assert(또는 assert 류 호출)가 있으면, 끝이든 중간이든 운다.
#   (d) `check_*`/`verify_*`/`is_ok*` 가 예외 자리에서 `return True` 도 같은 병이다.
def probe_silent_pass(root: Path = ROOT) -> None:
    # ★ 2026-09-22 (W10-1). src 도 본다 — `datalog.cmd_check` · `ledger.check_entry` 도
    #   검사다. 종전에는 tests·tools 만 돌았고 ⑤ 가 그것을 이 도구 자신에게서 잡았다.
    for p in sorted((root / "tests").rglob("*.py")) + sorted((root / "tools").rglob("*.py")) \
            + sorted((root / "src").rglob("*.py")):
        t = tree(p)
        if t is None:
            continue
        for fn in [n for n in ast.walk(t) if isinstance(n, ast.FunctionDef)]:
            name = fn.name
            boolish = name.startswith(("check_", "verify_", "is_ok"))
            is_check = name.startswith(("test_", "check_", "cmd_", "verify_", "is_ok")) \
                or "check" in name
            if not is_check:
                continue
            last = fn.body[-1] if fn.body else None
            for node in ast.walk(fn):
                if isinstance(node, ast.Try):
                    tail = node is last
                    asserts = any(_asserts(x) for b in node.body for x in ast.walk(b))
                    for h in node.handlers:
                        ex = h.type
                        nm = getattr(ex, "id", "") or getattr(getattr(ex, "attr", None), "__str__", lambda: "")()
                        broad = ex is None or nm in ("Exception", "BaseException")
                        # (a) except ImportError: return  — 의존성 없으면 통과
                        body_quiet = all(_quiet_return(b) or (isinstance(b, ast.Pass) and tail)
                                         for b in h.body)
                        if body_quiet and ("Import" in str(nm) or broad):
                            hit("③ 조용한 통과", p, h.lineno,
                                f"{name}() 가 예외를 잡고 조용히 빠져나간다 "
                                f"— 의존성·환경이 없으면 늘 통과한다")
                            continue
                        # (c) try: assert … except Exception: pass — 실패를 삼킨다.
                        #     `pass` 가 뒤로 떨어져도 **assert 가 낸 실패는 사라졌다.**
                        if broad and asserts and all(
                                isinstance(b, (ast.Pass, ast.Continue)) or _quiet_return(b)
                                for b in h.body):
                            hit("③ 조용한 통과", p, h.lineno,
                                f"{name}() 가 assert 를 감싼 try 에서 "
                                f"`except {nm or ''}` 로 실패를 삼킨다 — AssertionError 도 잡힌다")
                            continue
                        # (d) check_/verify_/is_ok 가 예외 자리에서 `return True`
                        if boolish and any(isinstance(b, ast.Return) and isinstance(b.value, ast.Constant)
                                           and b.value.value is True for b in h.body):
                            hit("③ 조용한 통과", p, h.lineno,
                                f"{name}() 가 예외를 잡고 `return True` 한다 — 못 잰 것을 "
                                f"맞다고 답한다")
                # (b) if <조건>: return  (assert 없이) — 대상 못 찾으면 통과
                if isinstance(node, ast.If) and len(node.body) == 1 \
                        and isinstance(node.body[0], ast.Return) \
                        and node.body[0].value is None and not node.orelse:
                    cond = ast.unparse(node.test)
                    if any(w in cond for w in ("len(", "not ", "exists", "< 2", "== 0", "is None")):
                        hit("③ 조용한 통과", p, node.lineno,
                            f"{name}() 가 `if {cond[:44]}: return` 으로 빠져나간다 "
                            f"— 대상을 못 찾으면 실패가 아니라 통과다")


# ── ④ 죽은 게이트 ───────────────────────────────────────────────
# CI 스텝이 `[ -f <경로> ]` 를 조건으로 걸었는데 그 경로가 추적 대상이
# 아니면, 그 스텝은 CI 에서 한 번도 안 돈다.
def probe_dead_gate(root: Path = ROOT) -> None:
    try:
        tracked = set(subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.split())
    except Exception as e:
        hit("④ 죽은 게이트", ROOT / "tools" / "deadcheck.py", 0,
            f"git ls-files 가 실패해 추적 여부를 못 가린다 — {e}")
        tracked = set()
    COND = re.compile(r"\[\s*-[fdes]\s+([^\]\s]+)\s*\]")
    for p in sorted((root / ".github").rglob("*.yml")):
        s = src(p)
        for m in COND.finditer(s):
            path = m.group(1).strip('"\'')
            if "$" in path or "*" in path:
                continue
            if path not in tracked:
                ln = s[:m.start()].count("\n") + 1
                blk = s[m.end():m.end() + 300]
                tool = re.search(r"(tools/\w+\.py|python -m [\w.]+)", blk)
                hit("④ 죽은 게이트", p, ln,
                    f"`{path}` 를 조건으로 걸었는데 추적 대상이 아니다 "
                    f"— 이 스텝은 CI 에서 한 번도 안 돈다"
                    + (f" (대상: {tool.group(1)})" if tool else ""))


# ── ⑤ 좁은 범위 ─────────────────────────────────────────────────
# 검사가 훑는 경로가 실제 파일 집합보다 좁은가.
#
# ★ 면제 — `"파일::함수"` → 사유. **제품 코드(src·tools)만 보는 것이 규칙의 뜻인 자리.**
#   여러 폴더를 돌면서 tests 를 뺀 문장 일곱이 전부 이 꼴이었다(2026-09-22 전수 분류).
#   적는 순간 세어지고 `tests/test_deadcheck_probes.py` 가 죽은 면제를 지운다.
_PROD_ONLY = "tests 는 **제품 코드가 아니다**"
EXEMPT_SCOPE = {
    "tests/test_declaration_sync.py::test_unwired_sources_declare_purpose":
        f"{_PROD_ONLY} — 「대장 소스가 배선됐는가」의 소비자는 판정·도구다. "
        "테스트가 소스 이름을 적는 것을 소비로 세면 모든 소스가 영원히 배선된다",
    # ★ 2026-09-24. **반대 방향**의 면제 — 위는 「tests 를 뺐다」, 이것은 「tests 만 본다」.
    "tests/test_skip_policy.py::_skip_literals":
        "`pytest.skip` 은 시험 안에만 산다 — src · tools 에 0건이라 넓히면 빈 폴더를 훑는다",
    "tests/test_guards.py::test_repo_python_compiles":
        f"{_PROD_ONLY} — tests 의 구문 오류는 pytest 수집이 먼저 **오류로** 낸다. "
        "여기서 또 컴파일할 이유가 없다",
    "tests/test_guards.py::test_nothing_writes_into_raw":
        f"{_PROD_ONLY} — 테스트는 RAW 를 `tmp_path` 로 갈아끼우고 거기에 쓴다. "
        "그것을 세면 모든 합성 픽스처가 위반이다",
    "tests/test_guards.py::test_generators_end_json_with_newline":
        f"{_PROD_ONLY} — 규칙의 대상은 **저장소에 남는 생성물**을 쓰는 코드다. "
        "테스트의 JSON 은 `tmp_path` 에서 끝난다",
    "tests/test_layers.py::test_no_tool_writes_outside_declared_layers":
        f"{_PROD_ONLY} — `RAW.parent` 로 루트를 발명하는 것은 **레이크를 만지는 코드**의 "
        "병이다. 테스트는 RAW 를 합성 트리로 갈아끼운다",
    "tests/test_reproducibility.py::test_r4_random_has_seed":
        f"{_PROD_ONLY} — R4 는 **실측 대상을 고르는 코드**의 규약이다(표본 설계). 테스트의 "
        "랜덤은 산출을 안 낸다. 2026-09-22 에 src 만 보던 것을 tools 까지 넓혔다",
    "tools/env_check.py::_py":
        f"{_PROD_ONLY} — 환경 키의 **소비자**를 센다. 테스트는 키를 읽는 쪽이 아니라 "
        "`monkeypatch.setenv` 로 **심는** 쪽이다",
    "tools/refcheck.py::check":
        f"{_PROD_ONLY} — 옛 이름을 `RAW / \"...\"` 로 하드코딩한 **판정·도구**를 찾는다. "
        "테스트의 RAW 경로는 합성이라 개명과 무관하다",
    # ── 폴더 하나만 도는 것 — **범위가 곧 규칙의 이름**인 자리(2026-09-22 재분류).
    #    한때 프로브가 「폴더 하나는 선언」이라고 대신 믿어줬다. 그것은 추측이라
    #    되돌렸고, 의도는 여기 한 줄씩 적는다.
    "tests/test_contract.py::test_web_data_has_no_unintended_orphan":
        "web/data 의 **소비자**는 화면(js)과 파이프라인(src)이다. 도구가 web/data 를 읽는 것을 "
        "소비로 세면 탐색 도구 하나가 고아 레이어를 영원히 살린다",
    "tests/test_guards.py::test_no_dated_scripts_in_tools":
        "이름 그대로 **tools/ 의 파일명** 규칙이다. src 는 패키지 모듈이고 tests 는 pytest 가 "
        "수집 규칙(test_*.py)을 따로 강제한다",
    "tests/test_guards.py::test_no_source_patching_scripts":
        "「소스를 고치는 **스크립트**」의 서식지는 tools/ 다. src 는 패키지이고 tests 의 "
        "문자열 치환은 합성 픽스처를 짓는 것이지 저장소를 고치는 것이 아니다",
    "tests/test_guards.py::test_etl_imports_are_declared":
        "pyproject **필수** 의존성은 파이프라인 패키지(src/firelane)의 계약이다. 도구·검사의 "
        "import 는 dev/extra 의존성이라 여기서 요구하면 필수 목록이 부푼다",
    "tests/test_k2.py::test_no_tool_creates_seal_tags":
        "봉인 태그를 만들 수 있는 것은 **도구와 워크플로**다(.github 과 함께 돈다). "
        "src 는 git 을 안 부르고 tests 는 합성 저장소에서만 태그를 만든다",
    "tests/test_k3.py::test_g16_jq_first_element_has_empty_fallback":
        "셸 스크립트(`*.sh`)와 워크플로의 jq 를 본다 — `.py` 우주와 무관하다. "
        "src·tests 에는 셸 스크립트가 없다",
    "tests/test_layering.py::test_순환_의존이_없다":
        "import **순환**은 패키지 모듈끼리의 성질이다. 도구·검사는 패키지를 import 하되 "
        "패키지가 그것을 import 하지 않으므로 순환의 고리가 될 수 없다",
    "tests/test_tools_are_wired.py::_tools":
        "이 파일의 우주가 tools/ 다 — 「도구가 배선됐는가」",
    "tests/test_tools_are_wired.py::_ambiguous":
        "src 의 모듈 이름은 **도구 이름과 겹치는가**(동명 모호성)를 재는 사전이다. 훑는 대상이 "
        "아니라 대조표다",
    "tests/test_tools_are_wired.py::test_every_tool_is_named_in_readme":
        "tools/README 가 **도구**를 전부 적는가 — 우주가 tools/ 다",
    "tests/test_tools_are_wired.py::test_readme_exempt_entries_are_real_and_reasoned":
        "tools/README 면제 항목이 **tools/ 에 실재**하는가 — 우주가 tools/ 다",
    "tools/deadcheck.py::_members":
        "② 의 **분모**다 — `tools` · `src` 원본은 정의상 그 폴더 하나씩이다",
    "tools/dms.py::_units":
        "강제자 **후보**는 검사 함수(tests)와 도구(tools)다. src 는 강제자가 아니라 강제 대상이다",
    "tools/doc_fsck.py::check_commands":
        "문서가 적은 명령이 **tools/ 에 실재**하는가 — 대조표가 tools/ 다",
    "tools/widen.py::w4":
        "「tools 전량이 어디선가 불리는가」 — 우주가 tools/ 다. 건초더미(`hay`)는 src·tests·tools "
        "전부다(같은 함수 안 `pys(...)`)",
    # ── 2026-09-24 (DECISIONS §226). ⑤ 는 **폴더** 축, `scopedecl` ② 는 **접미사** 축이다.
    #    둘은 같은 족의 다른 축이고 서로를 대신하지 못한다 — 겹치는 것이 아니라 직교한다.
    "tools/env_check.py::_sh":
        "`.sh` 의 우주가 `tools/` 다 — `src/` 와 `tests/` 에는 셸 스크립트가 0개다. "
        "이 함수는 **셸에 사는 환경변수**를 세려고 2026-09-24 에 생겼다",
    "tests/test_refcheck_paths.py::test_example_names_are_only_placeholders":
        "예시 이름 목록이 **도구 이름**을 삼키는지 보는 대조표다. 그 목록의 우주가 "
        "`tools/` 이고(`refcheck` 가 `tools/x.py` 꼴만 예시로 든다), `src`·`tests` 는 "
        "그 목록의 비교 대상이 아니다",
    "tools/scopedecl.py::enforcers":
        "강제자의 우주가 `tools/`(도구) + `tests/test_*.py`(검사) 둘이다. 두 줄로 나눠 "
        "모으므로 줄마다 보면 한쪽만 훑는 것으로 보인다 — 합쳐서 보면 `src/` 만 빠지고 "
        "**`src/` 는 강제자가 아니라 강제 대상**이다(`dms.py::_units` 와 같은 사유)",
    "src/firelane/inventory.py::_code_text":
        "속성이 **쓰이는가**는 판정(src)과 화면(web/*.js)이 읽는가다. 탐색 도구가 컬럼을 "
        "읽는 것을 사용으로 세면 모든 컬럼이 영원히 쓰인다(test_declaration_sync 와 같은 이유)",
}


def probe_narrow_scope(root: Path = ROOT) -> None:
    try:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.split()
    except Exception as e:
        # ★ 여기서 return 하면 이 프로브가 프로브 ③ 의 병에 걸린다 —
        #   git 이 없을 때 0건을 내고, 0건은 깨끗한 것이 아니다.
        hit("⑤ 좁은 범위", ROOT / "tools" / "deadcheck.py", 0,
            f"git ls-files 가 실패해 이 프로브가 아무것도 못 본다 — {e}")
        return
    py = {f for f in tracked if f.endswith(".py")}
    universe = {
        "src": {f for f in py if f.startswith("src/")},
        "tools": {f for f in py if f.startswith("tools/")},
        "tests": {f for f in py if f.startswith("tests/")},
    }
    for p in sorted((root / "tests").rglob("*.py")) + sorted((root / "tools").rglob("*.py")) \
            + sorted((root / "src").rglob("*.py")):
        t = tree(p)
        if t is None:
            continue
        try:
            rel = p.relative_to(root).as_posix()
        except ValueError:
            rel = str(p)
        for ln, fname, roots in _scans(t):
            roots &= set(universe)
            if not roots or roots == set(universe):
                continue
            if f"{rel}::{fname}" in EXEMPT_SCOPE:
                continue
            miss = sorted(set(universe) - roots)
            n = sum(len(universe[k]) for k in miss)
            hit("⑤ 좁은 범위", p, ln,
                f"{fname}() 가 {sorted(roots)} 만 훑는다 — {miss} 의 {n}개 파일이 대상 밖이다",
                f"{sum(len(universe[k]) for k in roots)}/{len(py)}")


# ★ ⑤ 의 짝짓기 — 이력.
#   2026-09-20 (DECISIONS §205). 파일 **전체**에서 폴더 이름과 훑기 호출을 따로 찾아
#   합치던 것을 「같은 줄」로 조이겠다고 적었다. 그러나 코드는 줄마다 찾은 것을
#   `seen |= ...` 로 **파일 전체에 다시 합쳤다** — 주석이 약속한 것을 코드가 안 했다.
#   그래서 검사 마흔 개가 든 `test_guards.py` 가 「src·tools 만 훑는 검사 하나」로 읽혔다.
#   2026-09-22 (PLAN §13 W10-1). **훑기 호출 하나의 수신자**만 본다 —
#     · `(ROOT / "src").rglob(...)` · `PKG.rglob(...)`(PKG = ROOT / "src" / "firelane")
#     · `ROOT.glob("tools/*.py")` 는 패턴의 첫 조각
#   수신자가 저장소 루트에서 시작하는 **폴더**여야 한다. `WEBDIR / "navi" / "src"` 는
#   web 의 src 이고, `ROOT / "tools" / "deadcheck.py"` 는 파일이며, `ast.walk` 는
#   파일 시스템을 안 돈다 — 종전 정규식은 셋 다 폴더 훑기로 읽었다.
#   한 문장(`for` 는 그 머리) 안의 훑기들은 **한 검사**로 합친다.
# ★ 폴더 하나만 도는 문장도 **운다.** 「tests 만 돌고 src·tools 는 밖」이 이 프로브의
#   원래 표적이다. 그 좁음이 의도면 `EXEMPT_SCOPE` 에 **사유와 함께** 적는다 —
#   의도를 선언하는 곳은 코드가 아니라 면제 표다(한때 「폴더 하나는 제 입으로 말한
#   범위」라고 프로브가 대신 믿어준 적이 있다. 그것은 선언이 아니라 추측이다).
_ROOTS = ("src", "tools", "tests")
_ROOTNAMES = {"ROOT", "root", "REPO", "repo", "REPO_ROOT"}
_WALKS = {"rglob", "glob", "iterdir", "walk"}


def _scans(t: ast.Module):
    """모듈 → (줄, 함수, 훑는 폴더 집합) — 문장 하나에 한 번."""
    assigns: dict[str, list[ast.AST]] = {}
    for n in ast.walk(t):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            assigns.setdefault(n.targets[0].id, []).append(n.value)

    def parts(e, depth=0) -> list[str] | None:
        """경로 식 → 루트 뒤 조각들. 루트에서 시작하지 않으면 None."""
        if depth > 5:
            return None
        if isinstance(e, ast.Name):
            if e.id in _ROOTNAMES:
                return []
            vs = assigns.get(e.id) or []
            got = [parts(v, depth + 1) for v in vs]
            got = [g for g in got if g is not None]
            return got[0] if got and all(g == got[0] for g in got) else None
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Div):
            left = parts(e.left, depth)
            k = _str(e.right)
            if left is None or k is None:
                return None
            return left + [x for x in k.split("/") if x]
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) \
                and e.func.id == "Path" and len(e.args) == 1:
            return parts(e.args[0], depth)
        return None

    def folder(ps: list[str]) -> set[str] | None:
        """루트 뒤 조각 → 훑는 최상위 폴더. 파일이면 None. 루트 전체면 전부."""
        if not ps:
            return set(_ROOTS)
        if any("." in x for x in ps):
            return None                 # 파일(확장자)이다. 폴더를 훑는 것이 아니다
        return {ps[0]} if ps[0] in _ROOTS else set()

    def walked(call: ast.Call) -> set[str] | None:
        f = call.func
        if isinstance(f, ast.Attribute) and f.attr in _WALKS:
            if isinstance(f.value, ast.Name) and f.value.id in ("ast", "os"):
                if f.value.id == "ast":
                    return None         # AST 를 도는 것이지 파일을 도는 것이 아니다
                recv = call.args[0] if call.args else None       # os.walk(p)
                ps = parts(recv) if recv is not None else None
                return folder(ps) if ps is not None else None
            ps = parts(f.value)
            if ps is None:
                return None
            if not ps and f.attr in ("glob", "rglob") and call.args:
                pat = _str(call.args[0]) or ""
                head = pat.split("/", 1)[0]
                if head in _ROOTS:
                    return {head}
            return folder(ps)
        if isinstance(f, (ast.Attribute, ast.Name)) and \
                (f.attr if isinstance(f, ast.Attribute) else f.id) == "listdir" and call.args:
            ps = parts(call.args[0])
            return folder(ps) if ps is not None else None
        return None

    owner: dict[int, str] = {}          # id(문장) → 둘러싼 함수. 안쪽이 이긴다
    for fn in ast.walk(t):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for x in ast.walk(fn):
                owner[id(x)] = fn.name
    for st in ast.walk(t):
        if not isinstance(st, ast.stmt):
            continue
        if isinstance(st, (ast.For, ast.AsyncFor)):
            heads = [st.iter]
        elif isinstance(st, (ast.If, ast.While)):
            heads = [st.test]
        elif isinstance(st, (ast.With, ast.AsyncWith)):
            heads = [i.context_expr for i in st.items]
        elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Try, ast.Match)):
            continue
        else:
            heads = [st]
        roots: set[str] = set()
        seen_any = False
        for h in heads:
            for x in ast.walk(h):
                if isinstance(x, ast.Call) and (w := walked(x)) is not None:
                    seen_any = True
                    roots |= w
        if seen_any and roots:
            yield st.lineno, owner.get(id(st), "<module>"), roots


PROBES = [
    ("① 빈 그물", probe_empty_net),
    ("② 손목록", probe_handlist),
    ("③ 조용한 통과", probe_silent_pass),
    ("④ 죽은 게이트", probe_dead_gate),
    ("⑤ 좁은 범위", probe_narrow_scope),
]


# ── 양성 대조 ───────────────────────────────────────────────────
# **프로브가 살아 있는가**를 묻는 자리. 프로브마다 「일부러 결함을 심은
# 합성 트리」를 만들고, 거기서 그 프로브가 우는지 본다.
#
# ★ 2026-09-21 (DECISIONS §208). 종전 `--selftest` 는 **실제 저장소에서
#   0건이면 프로브가 죽었다**고 읽었다. 그래서 `② 손목록` 을 전수 분류해
#   59건 → 0건으로 만든 바로 그날, `dms.py` 의 봉인 강제자가 빨개졌다 ——
#
#       ✗ probe/deadcheck   ★ selftest 실패 — 아무것도 못 낸 프로브: ['② 손목록']
#
#   **프로브가 제 일을 다 했기 때문에 봉인이 안 찍혔다.** 검사가 자기 성공을
#   실패로 읽은 것이고, DECISIONS §73 이 ④ 에 대해 적어둔 바로 그 문장이다 ——
#   「검사가 자기 성공을 실패로 읽으면 사람이 검사를 끈다」.
#
# ★ 그때 고친 방식이 `not k.startswith('④')` 라는 **한 글자 면제**였다.
#   0건이 청결일 수 있다는 것은 **프로브의 성질**인데 그것을 ④ 하나에만
#   적었다 — 범위가 이름보다 좁고 그것이 선언돼 있지 않은 그 족이다.
#   ①③⑤ 도 W10-1 의 전수 분류를 마치면 차례로 0 이 된다. 즉 **분류가
#   진행될수록 관문이 더 막히는** 구조였다.
#
# ★ 답은 면제를 늘리는 것이 아니라 **물음을 옮기는 것**이다. 생사는
#   합성 트리에서 묻고, 실제 트리의 0건은 그 다음에야 **청결**로 읽힌다.
#   실제 트리의 수를 보는 관문은 `--ratchet` 이고 그쪽은 양방향이다.
# ★ ① 의 합성 본문은 **상수로 조립한다.** 그대로 적으면 `deadcheck.py` **자신**이
#   ① 에 걸린다 — 실제로 처음 짰을 때 실제 트리 41 → 42 가 됐다.
#   프로브는 글자를 읽지 뜻을 읽지 않으므로 당연하고, **그 당연함이 좋은 합성
#   결함의 조건**이다(심은 것이 진짜와 구별되지 않는다). 다만 그 한 건이
#   실제 트리의 래칫을 올리면 그것은 결함이 아니라 잡음이다.
_FX_BLK = "outputs"
_FX_KEY = "feeds"


def _fx_empty_net(d: Path) -> None:
    """① — `outputs` 를 적재하면서 거기 0건인 키로 읽는 검사."""
    (d / "tools").mkdir(parents=True)
    (d / "sources.yaml").write_text(
        f"datasets:\n  a: {{{_FX_KEY}: [x]}}\n  b: {{{_FX_KEY}: [y]}}\n"
        f"{_FX_BLK}:\n  o1: {{path: p}}\n  o2: {{path: q}}\n",
        encoding="utf-8")
    (d / "tools" / "t.py").write_text(
        "# sources.yaml 을 읽는다\n"
        "def check_outputs(led):\n"
        f"    for v in led[{_FX_BLK!r}].values():\n"
        f"        assert v.get({_FX_KEY!r})\n", encoding="utf-8")


def _fx_handlist(d: Path) -> None:
    """② — `layers` 5종의 **부분집합**을 상수로 박은 검사."""
    (d / "tools").mkdir(parents=True)
    (d / "sources.yaml").write_text(
        "layers:\n" + "".join(f"  l{i}: {{}}\n" for i in range(5)), encoding="utf-8")
    (d / "tools" / "t.py").write_text(
        'WATCHED = ["l0", "l1", "l2"]\n', encoding="utf-8")


def _fx_silent_pass(d: Path) -> None:
    """③ — 의존성이 없으면 조용히 빠져나가는 검사."""
    (d / "tools").mkdir(parents=True)
    (d / "sources.yaml").write_text("datasets: {}\n", encoding="utf-8")
    (d / "tools" / "t.py").write_text(
        "def check_thing():\n"
        "    try:\n"
        "        import nonexistent_pkg\n"
        "    except ImportError:\n"
        "        return\n"
        "    assert nonexistent_pkg\n", encoding="utf-8")
    # ★ 2026-09-22 재검토. 형태마다 **파일 하나** — `tests/test_deadcheck_probes.py` 가
    #   형태별로 우는지 본다(하나만 울어도 대조는 통과하므로).
    (d / "tools" / "swallow.py").write_text(
        "def test_each():\n"
        "    for x in [1, 2]:\n"
        "        try:\n"
        "            assert x > 5\n"
        "        except Exception:\n"
        "            pass\n"
        "    print('done')\n", encoding="utf-8")
    (d / "tools" / "truthy.py").write_text(
        "def verify_thing(p):\n"
        "    try:\n"
        "        return open(p).read() == 'ok'\n"
        "    except OSError:\n"
        "        return True\n", encoding="utf-8")


def _git_init(d: Path, add: bool = False) -> None:
    subprocess.run(["git", "init", "-q"], cwd=d, check=True,
                   capture_output=True, text=True)
    if add:
        subprocess.run(["git", "add", "-A"], cwd=d, check=True,
                       capture_output=True, text=True)


def _fx_dead_gate(d: Path) -> None:
    """④ — 추적되지 않는 경로를 조건으로 건 CI 스텝."""
    (d / ".github" / "workflows").mkdir(parents=True)
    (d / ".github" / "workflows" / "w.yml").write_text(
        "steps:\n"
        "  - run: if [ -f no/such/file.txt ]; then uv run python tools/x.py; fi\n",
        encoding="utf-8")
    _git_init(d)          # 추적 파일 0개 — 조건 경로는 당연히 대상 밖이다


def _fx_narrow_scope(d: Path) -> None:
    """⑤ — 두 형태. `tests` **하나만** 훑는 검사(`only.py`)와, `src`·`tests` 를 훑고
    `tools` 를 빠뜨린 검사(`two.py`).

    ★ 2026-09-22 재검토. 한때 ⑤ 가 「폴더 하나는 제 입으로 말한 범위」라며 단일
      폴더를 안 울었고 대조도 그쪽으로 옮겨졌다 — **대조가 프로브의 원래 표적을
      놓아버린 것**이다. 단일 폴더 형태를 되살리고 두 형태를 다 심는다.
    """
    for sub in ("src", "tools", "tests"):
        (d / sub).mkdir(parents=True)
        (d / sub / "a.py").write_text("x = 1\n", encoding="utf-8")
    head = 'from pathlib import Path\nROOT = Path(".")\n'
    (d / "tests" / "only.py").write_text(
        head + 'def test_all():\n'
        '    for p in sorted((ROOT / "tests").rglob("*.py")):\n'
        '        assert p\n', encoding="utf-8")
    (d / "tests" / "two.py").write_text(
        head + 'def test_code():\n'
        '    for p in sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "tests").rglob("*.py")):\n'
        '        assert p\n', encoding="utf-8")
    _git_init(d, add=True)


# 프로브 이름 → (합성 트리를 짓는 함수, **무엇을 거는가**)
CONTROLS: dict[str, tuple] = {
    "① 빈 그물": (_fx_empty_net, "적재한 블록에 0건인 키로 읽는 검사"),
    "② 손목록": (_fx_handlist, "원본의 부분집합을 상수로 박은 목록"),
    "③ 조용한 통과": (_fx_silent_pass, "ImportError→return · assert 삼킴 · 예외→return True"),
    "④ 죽은 게이트": (_fx_dead_gate, "추적 안 되는 경로를 건 CI 스텝"),
    "⑤ 좁은 범위": (_fx_narrow_scope, "tests 만 훑는 검사 · tools 를 빠뜨린 검사"),
}


def run_probe(fn, root: Path) -> list[dict]:
    """프로브 하나를 **격리해서** 돌리고 그 건만 돌려준다.

    ★ `HITS` 는 모듈 전역이다. 합성 트리의 건이 실제 집계에 섞이면
      래칫이 그만큼 어긋난다 — 갈아끼웠다가 되돌린다.
    """
    global HITS
    saved, HITS = HITS, []
    try:
        fn(root)
        got = HITS
    finally:
        HITS = saved
    return got


def positive_control() -> list[str]:
    """프로브를 제 합성 트리에서 돌린다. **안 우는 프로브의 이름**을 낸다.

    ★ 대조가 없는 프로브도 「죽은 것」으로 센다. 프로브를 늘리고 대조를
      안 적으면 그것이 곧 이 도구가 세는 무음 통과다.
    """
    import tempfile
    dead: list[str] = []
    for name, fn in PROBES:
        ctl = CONTROLS.get(name)
        if ctl is None:
            dead.append(f"{name} — 양성 대조가 없다")
            continue
        build, _what = ctl
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            try:
                build(d)
                got = run_probe(fn, d)
            except Exception as e:
                dead.append(f"{name} — 대조가 예외로 죽었다: {type(e).__name__}: {e}")
                continue
        if not any(h["probe"] == name for h in got):
            dead.append(f"{name} — 심은 결함을 못 냈다({_what})")
    return dead


# ★ 래칫 — **오늘의 수**다. 목표가 아니라 천장이다(`COV_MIN` · `dupcheck --max` 와 같은 틀).
#   양방향이다 — 늘면 ✗, **줄어도 ✗** 다. 줄었는데 안 조이면 다음에 그만큼 다시 늘어도
#   아무도 안 운다(W4-9 가 이산 래칫 넷에서 닫은 바로 그 구멍).
#
# ★ 2026-09-22 — **전부 0 이다**(PLAN §13 W10-1 닫힘). ①41 · ③15 · ⑤15 를 한 건씩
#   분류했다. 오검은 프로브를 조였고(①: 수신자 단위 짝짓기 · 드문 키 판정 삭제,
#   ③: `pass` 는 떨어진다 · 말하는 반환은 조용하지 않다 — 단 assert 를 삼키는
#   넓은 except 와 예외→`return True` 는 어디서든 운다, ⑤: 훑기 호출의 **수신자**
#   단위 짝짓기 — 단일 폴더도 운다, 의도는 면제 표에), 진짜는 고쳤고,
#   의도된 좁음은 면제 표에 사유를 적었다.
#   이제 이 수는 「미분류」가 아니라 **「새로 들어온 것」**이다 — 하나라도 오르면 운다.
CEILING = {
    "① 빈 그물": 0,
    "② 손목록": 0,
    "③ 조용한 통과": 0,
    "④ 죽은 게이트": 0,
    "⑤ 좁은 범위": 0,
}


def main() -> int:
    selftest = "--selftest" in sys.argv
    ratchet = "--ratchet" in sys.argv

    # ★ 생사는 **합성 트리**에서 먼저 묻는다. 그 답이 있어야 아래의 0건을
    #   「청결」로 읽을 수 있다 — 순서가 뒤바뀌면 이 도구가 세는 병에 걸린다.
    alive = positive_control()

    per: dict[str, int] = {}
    for name, fn in PROBES:
        before = len(HITS)
        try:
            fn()
        except Exception as e:  # 프로브가 죽으면 그것도 빨간불이다
            hit(name, ROOT / "tools" / "deadcheck.py", 0,
                f"프로브가 예외로 죽었다 — {type(e).__name__}: {e}")
        per[name] = len(HITS) - before

    sick = {d.split(" —")[0] for d in alive}
    print(f"deadcheck — 빨간불 {len(HITS)}건\n")
    for name, n in per.items():
        if name in sick:
            flag = "   ★ 양성 대조 실패 — 이 수는 믿을 수 없다"
        elif n == 0:
            flag = "   (대조 통과 — 0건은 청결이다)"
        else:
            flag = ""
        print(f"  {name:14s} {n:4d}건{flag}")

    print("\n── 파일별 상위")
    from collections import Counter
    for f, n in Counter(h["file"] for h in HITS).most_common(15):
        print(f"  {n:3d}  {f}")

    json.dump({"total": len(HITS), "by_probe": per, "hits": HITS},
              open(ROOT / "REDLIST.json", "w"), ensure_ascii=False, indent=1)
    print(f"\nREDLIST.json 기록 — {len(HITS)}건")

    # ★ 양성 대조가 빨가면 **아래의 어떤 수도 못 믿는다.** 관문이든 아니든
    #   여기서 죽는다 — 래칫이 「0건」을 통과시키는 근거가 이 대조뿐이다.
    if (selftest or ratchet) and alive:
        print("\n★ 양성 대조 실패 — 심은 결함을 못 낸 프로브가 있다\n")
        for d in alive:
            print(f"  ✗ {d}")
        print("\n  합성 트리는 `CONTROLS` 가 짓는다. 프로브를 고쳤으면 대조도 같이 고쳐라 —")
        print("  **대조가 통과하지 못하는 프로브의 0건은 청결이 아니다.**")
        return 1

    if selftest:
        # ★ 2026-09-21 (DECISIONS §208). 여기서 **실제 트리의 0건을 보지 않는다.**
        #   종전에는 봤고, 그래서 ② 를 전수 분류해 0건으로 만든 날 이 관문이
        #   빨개졌다 — 프로브가 제 일을 다 했기 때문에 빨개진 것이다.
        #   생사의 근거는 위 `positive_control()` 하나다.
        print("\nselftest 통과 — 프로브 "
              f"{len(PROBES)} 전부 제 합성 트리에서 울었다")
        print("  ★ 실제 트리의 건수는 여기서 안 본다 — 그것은 `--ratchet` 의 물음이다.")
        return 0

    # ★ 2026-09-20 (DECISIONS §202). **여기가 이 도구의 관문이다.**
    #   종전에는 관문이 `--selftest` 뿐이었다. 그것이 묻는 것은 「프로브가
    #   한 건이라도 내는가」이고, 그래서 **결함이 쌓일수록 더 확실히 초록**이었다.
    #   148건이 REDLIST.json 에 앉아 있는 동안 `verify.sh` 도 CI 도 초록이었다.
    #   그중 하나가 `golden.py:151 WATCH` — 대장에 W3-8 로 따로 등재돼
    #   **사람이 다시 발견한 것**이다. 도구는 진작에 찾아놨고 아무도 안 읽었다.
    if ratchet:
        bad = []
        for name, ceil in CEILING.items():
            got = per.get(name, 0)
            if got > ceil:
                bad.append(f"  ✗ {name}  {ceil} → {got}  (+{got - ceil}) — 새 결함이 들어왔다")
            elif got < ceil:
                bad.append(f"  ✗ {name}  {ceil} → {got}  ({got - ceil}) — 닫았으면 "
                           f"`CEILING` 을 {got} 으로 조여라. 안 조이면 다시 늘어도 안 운다")
        unknown = sorted(set(per) - set(CEILING))
        if unknown:
            bad.append(f"  ✗ 래칫에 없는 프로브: {unknown} — 프로브를 늘렸으면 천장도 적는다")
        if bad:
            print("\n★ 래칫 — 프로브별 수가 선언과 다르다\n")
            print("\n".join(bad))
            print("\n  정본: tools/deadcheck.py 의 CEILING. 한 곳이다.")
            print("  무엇이 늘었는지는 REDLIST.json 을 diff 해서 본다.")
            return 1
        print("\n래칫 통과 — " + " · ".join(f"{k} {v}" for k, v in per.items()))
        print("  ★ 천장이 전부 0 이다. 면제는 EXEMPT_* 표에 사유와 함께 있다(PLAN §13 W10-1 닫힘).")
        return 0
    return min(len(HITS), 250)


if __name__ == "__main__":
    sys.exit(main())

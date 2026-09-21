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
    --selftest  **양성 대조만.** 프로브가 한 건이라도 내는가
    --ratchet   ★ **관문.** 프로브별 수가 `CEILING` 과 같은가 (양방향)

★ 이 도구 자신도 ①에 걸린다. `--selftest` 가 그것을 확인한다 —
  프로브가 한 건도 못 내면 프로브가 죽은 것이지 저장소가 깨끗한 것이 아니다.

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
    HITS.append({
        "probe": probe,
        "file": str(path.relative_to(ROOT)),
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
# 검사가 `.get("X")` 로 후보를 모으는데 대장에 X 키가 0건이면
# 그 검사는 구조적으로 빌 수 있다 — 영원히 통과한다.
def probe_empty_net() -> None:
    import yaml
    led = yaml.safe_load(src(ROOT / "sources.yaml"))
    blocks = {"datasets": led.get("datasets") or {},
              "retired": led.get("retired") or {},
              "outputs": led.get("outputs") or {}}
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
    GET = re.compile(r"""\.get\(\s*["'](\w+)["']|\[\s*["'](\w+)["']\s*\]""")

    def scopes_of(p: Path) -> list[tuple[int, int, str, str]]:
        """(시작줄, 끝줄, 이름, 그 범위의 소스) — 함수 단위. 없으면 모듈 전체."""
        t = tree(p)
        if t is None:
            return []
        lines = src(p).splitlines()
        out = []
        for n in ast.walk(t):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a, b = n.lineno, (n.end_lineno or n.lineno)
                out.append((a, b, n.name, "\n".join(lines[a - 1:b])))
        return out

    seen: set[tuple[str, str, str, str]] = set()
    for p in sorted((ROOT / "tests").rglob("*.py")) + sorted((ROOT / "tools").rglob("*.py")) \
            + sorted((ROOT / "src").rglob("*.py")):
        s = src(p)
        if "sources.yaml" not in s and "ledger" not in s.lower():
            continue
        # ★ 블록 판별을 **함수 단위**로 한다. 파일 단위로 하면 한 파일 안에
        #   datasets 검사와 outputs 검사가 같이 있을 때 서로의 키로 오탐이 난다
        #   (첫 실행에서 111건 중 절반이 그것이었다).
        LOAD = re.compile(r"""(?:\.get\(|\[)\s*["'](datasets|retired|outputs)["']""")
        NOCOM = re.compile(r"#[^\n]*")
        for a, b, fname, body in scopes_of(p):
            code = NOCOM.sub("", body)          # 주석은 적재가 아니다
            loaded = {m.group(1) for m in LOAD.finditer(code)}
            if not loaded:
                continue
            for m in GET.finditer(body):
                key = m.group(1) or m.group(2)
                if key not in SCHEMA:
                    continue
                ln = a + body[:m.start()].count("\n")
                # ★ 블록이 **언급**됐는가가 아니라 **적재**됐는가를 본다.
                #   언급으로 판별하면 outputs 를 도는 함수의 주석에 datasets 가
                #   있다는 이유로 걸린다 — 두 번째 조임에서 그것이 남았다.
                # ★ 그 키가 **다른 적재 블록에는 실재**하면, 이 블록에 없는 것은
                #   결손이 아니라 내가 잘못 물린 것이다. 한 함수가 datasets 와
                #   outputs 를 둘 다 적재할 때 서로의 키로 오탐이 난다.
                owner = {b for b in loaded if have[b].get(key, 0) > 0}
                for blk, c in have.items():
                    tot = len(blocks[blk])
                    if blk not in loaded or (owner and blk not in owner):
                        continue
                    n = c.get(key, 0)
                    sig = (str(p), fname, blk, key)
                    if sig in seen:
                        continue
                    if n == 0 and tot:
                        seen.add(sig)
                        hit("① 빈 그물", p, ln,
                            f"{fname}() 가 {blk} 를 `{key}` 로 읽는데 그 키가 "
                            f"**0/{tot}** 이다 — 이 검사는 구조적으로 빌 수 있다",
                            f"0/{tot}")
                    elif 0 < n < tot * 0.5:
                        seen.add(sig)
                        hit("① 빈 그물", p, ln,
                            f"{fname}() 가 {blk}.{key} 를 읽는데 {n}/{tot} 뿐이다 "
                            f"— 나머지 {tot - n}종이 대상 밖이다", f"{n}/{tot}")


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
def _members() -> dict[str, tuple[set[str], int]]:
    """원본 이름 → (원소로 인정하는 표기 집합, 실제 종수).

    좁은 것을 먼저 둔다. `판정코드` ⊂ `src` 라 순서가 뒤집히면 `WATCH` 가
    `src` 58종에 붙어 **분모가 다시 헐거워진다.**
    """
    import yaml
    out: dict[str, tuple[set[str], int]] = {}

    def spell(rels: list[str]) -> set[str]:
        return {x for r in rels for x in (r, Path(r).name, Path(r).stem)}

    # 판정 코드의 닫힘은 여기 하나다 — golden 도 같은 것을 부른다
    from firelane.shardseal import code_closure
    jud = [p.relative_to(ROOT).as_posix() for p in code_closure("firelane.segments")]
    out["판정코드"] = (spell(jud), len(jud))

    y = yaml.safe_load(src(ROOT / "sources.yaml"))
    for k in ("layers", "scopes", "datasets", "outputs"):
        keys = set((y.get(k) or {}).keys())
        out[k] = (keys, len(keys))

    tl = [p.relative_to(ROOT).as_posix() for p in (ROOT / "tools").glob("*.py")]
    out["tools"] = (spell(tl), len(tl))
    sl = [p.relative_to(ROOT).as_posix() for p in (ROOT / "src").rglob("*.py")]
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
}


def probe_handlist() -> None:
    try:
        mem = _members()
    except Exception as e:
        hit("② 손목록", ROOT / "tools" / "deadcheck.py", 0,
            f"원본을 못 쟀다 — {type(e).__name__}: {e}. **분모가 없으면 이 프로브는 빈 그물이다**")
        return
    for p in sorted((ROOT / "tests").rglob("*.py")) + sorted((ROOT / "tools").rglob("*.py")):
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
def probe_silent_pass() -> None:
    for p in sorted((ROOT / "tests").rglob("*.py")) + sorted((ROOT / "tools").rglob("*.py")):
        t = tree(p)
        if t is None:
            continue
        for fn in [n for n in ast.walk(t) if isinstance(n, ast.FunctionDef)]:
            name = fn.name
            is_check = name.startswith(("test_", "check_", "cmd_")) or "check" in name
            if not is_check:
                continue
            for node in ast.walk(fn):
                # (a) except ImportError: return  — 의존성 없으면 통과
                if isinstance(node, ast.ExceptHandler):
                    ex = node.type
                    nm = getattr(ex, "id", "") or getattr(getattr(ex, "attr", None), "__str__", lambda: "")()
                    body_quiet = all(isinstance(b, (ast.Return, ast.Pass)) for b in node.body)
                    if body_quiet and ("Import" in str(nm) or nm == "Exception" or ex is None):
                        hit("③ 조용한 통과", p, node.lineno,
                            f"{name}() 가 예외를 잡고 조용히 빠져나간다 "
                            f"— 의존성·환경이 없으면 늘 통과한다")
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
def probe_dead_gate() -> None:
    try:
        tracked = set(subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split())
    except Exception as e:
        hit("④ 죽은 게이트", ROOT / "tools" / "deadcheck.py", 0,
            f"git ls-files 가 실패해 추적 여부를 못 가린다 — {e}")
        tracked = set()
    COND = re.compile(r"\[\s*-[fdes]\s+([^\]\s]+)\s*\]")
    for p in sorted((ROOT / ".github").rglob("*.yml")):
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
def probe_narrow_scope() -> None:
    try:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
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
    # ★ 훑는 방식이 여럿이다 — rglob · glob · walk · 경로 리터럴.
    #   한 형태만 보면 프로브가 0건을 내고, 0건은 깨끗한 것이 아니라
    #   프로브가 죽은 것이다.
    RG = re.compile(r'["\'](src|tools|tests)(?:/|["\'])'
                    r'|ROOT\s*/\s*["\'](src|tools|tests)["\']')
    WALK = re.compile(r"\.(?:rglob|glob|iterdir|walk)\(|listdir\(")
    # ★ 2026-09-20 (DECISIONS §205). 종전에는 파일 **전체**에서 `RG` 와 `WALK` 를
    #   따로 찾아 합쳤다. 그래서 `ROOT / "src" / "x.py"` 처럼 **파일 하나**를 가리키는
    #   상수와, 전혀 다른 폴더를 도는 `iterdir()` 이 한 파일에 있으면 「src 만 훑는다」로
    #   읽혔다. ②가 앓던 것과 같은 병이다 — 짝짓기가 헐거우면 분모가 의미를 잃는다.
    #   훑는 자리와 폴더 이름은 **같은 줄에 있다**(`sorted((ROOT / "tests").rglob(...))`).
    #   줄 단위로 짝지으면 거짓 경보가 사라지고 진짜만 남는다.
    for p in sorted((ROOT / "tests").rglob("*.py")) + sorted((ROOT / "tools").rglob("*.py")):
        s = src(p)
        if not WALK.search(s):
            continue
        seen = set()
        for line in s.splitlines():
            if not WALK.search(line):
                continue
            seen |= {m.group(1) or m.group(2) for m in RG.finditer(line)}
        seen = {x for x in seen if x} & set(universe)
        if seen and seen != set(universe):
            miss = sorted(set(universe) - seen)
            n = sum(len(universe[k]) for k in miss)
            hit("⑤ 좁은 범위", p, 1,
                f"{sorted(seen)} 만 훑는다 — {miss} 의 {n}개 파일이 대상 밖이다",
                f"{sum(len(universe[k]) for k in seen)}/{len(py)}")


PROBES = [
    ("① 빈 그물", probe_empty_net),
    ("② 손목록", probe_handlist),
    ("③ 조용한 통과", probe_silent_pass),
    ("④ 죽은 게이트", probe_dead_gate),
    ("⑤ 좁은 범위", probe_narrow_scope),
]


# ★ 래칫 — **오늘의 수**다. 목표가 아니라 천장이다(`COV_MIN` · `dupcheck --max` 와 같은 틀).
#   양방향이다 — 늘면 ✗, **줄어도 ✗** 다. 줄었는데 안 조이면 다음에 그만큼 다시 늘어도
#   아무도 안 운다(W4-9 가 이산 래칫 넷에서 닫은 바로 그 구멍).
#
# ★ ②만 0 이다. 나머지 셋(①③⑤)의 수는 **아직 분류되지 않았다** — 진짜 결함인지
#   프로브의 오검인지 한 건씩 본 적이 없다. 그래서 여기 적힌 41·15·33 은
#   「이만큼이 괜찮다」가 아니라 **「이만큼이 미분류로 남아 있다」**는 뜻이다.
#   분류를 마친 프로브만 0 으로 내려온다. PLAN §13 W10-1 이 그 일을 든다.
CEILING = {
    "① 빈 그물": 41,
    "② 손목록": 0,
    "③ 조용한 통과": 15,
    "④ 죽은 게이트": 0,
    # ★ 2026-09-20 33 → 15 (DECISIONS §205). ⑤ 의 짝짓기를 **줄 단위**로 조였다.
    #   종전에는 파일 전체에서 폴더 이름과 훑기 호출을 따로 찾아 합쳤고, 그래서
    #   `ROOT / "src" / "x.py"`(파일 하나)와 전혀 다른 폴더를 도는 `iterdir()` 이
    #   한 파일에 있으면 「src 만 훑는다」로 읽혔다. 거짓 경보 18건이 빠졌다.
    "⑤ 좁은 범위": 15,
}


def main() -> int:
    selftest = "--selftest" in sys.argv
    ratchet = "--ratchet" in sys.argv
    per: dict[str, int] = {}
    for name, fn in PROBES:
        before = len(HITS)
        try:
            fn()
        except Exception as e:  # 프로브가 죽으면 그것도 빨간불이다
            hit(name, ROOT / "tools" / "deadcheck.py", 0,
                f"프로브가 예외로 죽었다 — {type(e).__name__}: {e}")
        per[name] = len(HITS) - before

    print(f"deadcheck — 빨간불 {len(HITS)}건\n")
    for name, n in per.items():
        flag = "   ★ 0건 — 프로브가 죽었는지 확인하라" if n == 0 else ""
        print(f"  {name:14s} {n:4d}건{flag}")

    print("\n── 파일별 상위")
    from collections import Counter
    for f, n in Counter(h["file"] for h in HITS).most_common(15):
        print(f"  {n:3d}  {f}")

    json.dump({"total": len(HITS), "by_probe": per, "hits": HITS},
              open(ROOT / "REDLIST.json", "w"), ensure_ascii=False, indent=1)
    print(f"\nREDLIST.json 기록 — {len(HITS)}건")

    # ★ 양성 대조. 0건이 **청결**인지 **프로브 죽음**인지 가르는 유일한
    #   방법이다. ④ 가 0건을 냈을 때 실제로는 F-211 이 해소된 것이었는데
    #   selftest 는 그것을 프로브 죽음으로 보고했다 — 검사가 자기 성공을
    #   실패로 읽으면 사람이 검사를 끈다(DECISIONS §73).
    def _probe4_alive() -> bool:
        import tempfile
        d = Path(tempfile.mkdtemp())
        (d / "x.yml").write_text(
            'steps:\n  - run: if [ -f no/such/file.txt ]; then :; fi\n',
            encoding="utf-8")
        pat = re.compile(r"\[\s*-[fdes]\s+([^\]\s]+)\s*\]")
        return bool(pat.search((d / "x.yml").read_text(encoding="utf-8")))

    if selftest or ratchet:
        if not _probe4_alive():
            print("\n★ 양성 대조 실패 — ④ 프로브의 정규식이 죽었다")
            return 1

    if selftest:
        # ★ ④ 는 0건이 정상일 수 있다(F-211 해소). 위에서
        #   살아 있음을 확인했으므로 목록에서 뺀다.
        dead = [k for k, v in per.items()
                if v == 0 and not k.startswith('④')]
        if dead:
            print(f"\n★ selftest 실패 — 아무것도 못 낸 프로브: {dead}")
            return 1
        print("\nselftest 통과 — 프로브 다섯 전부 살아 있다")
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
        print("  ★ ①③⑤ 의 수는 **미분류**다. 「괜찮다」가 아니라 「아직 안 봤다」다(PLAN §13 W10-1).")
        return 0
    return min(len(HITS), 250)


if __name__ == "__main__":
    sys.exit(main())

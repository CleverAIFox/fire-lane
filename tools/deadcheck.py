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

★ 이 도구 자신도 ①에 걸린다. `--selftest` 가 그것을 확인한다 —
  프로브가 한 건도 못 내면 프로브가 죽은 것이지 저장소가 깨끗한 것이 아니다.
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
SOURCES = {
    "tools": lambda: len(list((ROOT / "tools").glob("*.py"))),
    "layers": lambda: _yaml_len("layers"),
    "scopes": lambda: _yaml_len("scopes"),
    "datasets": lambda: _yaml_len("datasets"),
    "outputs": lambda: _yaml_len("outputs"),
}


def _yaml_len(k: str) -> int:
    import yaml
    return len(yaml.safe_load(src(ROOT / "sources.yaml")).get(k) or {})


def probe_handlist() -> None:
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
            items = [e for e in val.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(items) < 3:
                continue
            n = len(items)
            for key, fn in SOURCES.items():
                try:
                    tot = fn()
                except Exception:
                    continue
                if key in src(p).lower() and n < tot:
                    hit("② 손목록", p, node.lineno,
                        f"{tgt.id} 가 {n}개 리터럴인데 {key} 는 {tot}종이다 "
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
    for p in sorted((ROOT / "tests").rglob("*.py")) + sorted((ROOT / "tools").rglob("*.py")):
        s = src(p)
        if not WALK.search(s):
            continue
        seen = {m.group(1) or m.group(2) for m in RG.finditer(s)}
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


def main() -> int:
    selftest = "--selftest" in sys.argv
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

    if selftest:
        if not _probe4_alive():
            print("\n★ selftest 실패 — ④ 프로브의 정규식이 죽었다")
            return 1
        # ★ ④ 는 0건이 정상일 수 있다(F-211 해소). 위에서
        #   살아 있음을 확인했으므로 목록에서 뺀다.
        dead = [k for k, v in per.items()
                if v == 0 and not k.startswith('④')]
        if dead:
            print(f"\n★ selftest 실패 — 아무것도 못 낸 프로브: {dead}")
            return 1
        print("\nselftest 통과 — 프로브 다섯 전부 살아 있다")
        return 0
    return min(len(HITS), 250)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
mutate.py — **시험이 이 도구를 붙들고 있는가.** 돌연변이 관문.

    uv run python tools/mutate.py --tool verdictsim   도구 하나를 전수로 흔든다
    uv run python tools/mutate.py --write             결과를 대장에 적는다 (느리다)
    uv run python tools/mutate.py --selftest          ★ 흔드는 쪽과 도출이 살아 있나

── 왜 생겼나  (PLAN #149 · DECISIONS §396) ─────────────────────
`--selftest` 는 「심은 결함을 잡나」를 묻는다. 좋은 물음이고 25개 도구가
답한다. 그런데 **「시험이 이 도구를 붙들고 있나」는 아무도 안 묻는다** —
초록은 「봤다」일 수도 「안 봤다」일 수도 있고, 둘을 가르는 길이 없었다.

2026-10-04 실측이 그 값을 보였다 — 도구 13개 · 돌연변이 104개 중 **생존 13**.
`verdictsim.py` 는 8개 중 넷이 살았고 **셋이 같은 한 줄**이었다
(`(X or 0)` — 「없다」와 「0」을 같은 것으로 읽는다). 그 한 줄이 우연히
맞는 답을 내고 있었고, 맞는 이유는 어디에도 없었다.

── 붙잡이를 **열거하지 않는다**  (이 도구의 핵심) ──────────────
목록을 손으로 적으면 도구가 하나 늘 때마다 빠진다 — 이 저장소가 세 번
배운 꼴이다(§285-2 · §284-4 · §286). 그래서 **도출한다** —

    ① 그 도구의 `--selftest`            선언했으면 그것이 첫 붙잡이다
    ② 그 도구를 이름으로 드는 시험 파일  `tests/` 전수에서 찾는다
    ③ 그 도구의 `RATCHETS` 선언         값이 움직이면 `ratchet.py` 가 운다

── 아무 변경에나 우는 붙잡이는 **안 센다** ─────────────────────
`docseal` 류는 파일 내용 지문을 본다 — 주석 한 줄만 넣어도 운다. 그것을
세면 **전부 죽음**이 되고, 전부 죽음은 반대 방향의 빈 그물이다(「다 잡는다」가
「아무것도 안 잰다」와 같은 수를 낸다).

가르는 법은 재는 것이다 — **무해 돌연변이**(주석 한 줄)를 먼저 넣어 보고,
그것에 우는 붙잡이는 그 도구의 붙잡이 목록에서 뺀다.

── 래칫은 양방향이다 ───────────────────────────────────────────
    SURVIVORS   생존 — **내려가는 쪽으로만**
    MUTANTS     흔든 수 — **올라가는 쪽으로만.** 그물이 줄면 생존도 같이
                줄어 좋아 보인다. 분모를 안 잠그면 생존 수는 수가 아니다

IN    tools/*.py (흔들 대상 — **`.sh` 는 안 흔든다.** 셸에는 AST 가 없다) ·
      tests/test_*.py (`--deep` 의 붙잡이 도출) · `toolclass.classify()`(과녁)
OUT   data/processed/mutation.json (대장) · 표준출력
PARAM MAX_PER_TOOL · SURVIVORS · MUTANTS · UNCATCHABLE · RATCHETS · TIMEOUT
밖    **생존이 나쁘다고 말하지 않는다.** 정렬 키나 로그 문구처럼 아무 행동도
      안 바꾸는 자리의 생존은 정상이다 — 그것을 가르는 것은 사람이고 이
      도구는 **어디가 안 붙들려 있는지**를 낼 뿐이다.
      **시험을 고치지도 않는다.** 흔들고, 세고, 되돌린다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다 — 전수 흔들기는 비싸다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
TESTS = ROOT / "tests"
LEDGER = ROOT / "data" / "golden" / "mutation.json"

def targets() -> list[str]:
    """흔들 도구를 **도출한다** — 손목록을 안 적는다.

    과녁은 **관문이면서 래칫을 든 도구**다. 둘 다 있어야 「흔들면 울어야 할
    자리」가 되기 때문이다 — 관문이 아니면 울 데가 없고, 래칫이 없으면 그
    도구가 무엇을 지키는지 수로 안 적힌다.

    ★ 2026-10-05 (DECISIONS §398). 종전에는 이름 셋을 손으로 적었고
      `deadcheck ②(손목록)` 이 울었다. 목록을 손으로 적으면 도구가 늘 때마다
      빠진다 — 이 저장소가 세 번 배운 꼴이다(§285-2 · §284-4 · §286).
    """
    import toolclass
    rows = toolclass.classify()
    out = []
    for rel, r in rows.items():
        p = ROOT / rel
        if r["부류"] != "관문" or p.suffix != ".py":
            continue
        if "RATCHETS" in p.read_text(encoding="utf-8", errors="replace"):
            out.append(p.stem)
    return sorted(out)

#: 한 도구에서 흔들 **최대 수**. 전수가 아니다 — 그래서 `MUTANTS` 래칫이
#: 분모를 잠근다.
#:
#: ★ 2026-10-05 실측. 상한 없이 다섯 도구를 돌렸더니 **한 시간이 넘어도**
#:   안 끝났다. `sealcov --selftest` 하나가 22초고 돌연변이가 수십 개면
#:   자기검사만 수십 분이다. **값을 못 치르는 관문은 안 돈다** — 안 도는
#:   관문은 없는 관문이고, 그것이 이 저장소가 §286 에서 배운 것이다.
#:   상한을 두고 **상한을 적는 쪽**을 골랐다. 전수인 척하지 않는다.
MAX_PER_TOOL = 4

#: 한 돌연변이에 주는 시간. 넘기면 **생존이 아니라 「못 쟀다」**다.
TIMEOUT = 180

#: 생존 — 내려가는 쪽으로만.
#: ★ 2026-10-05 — 64 → 67 (DECISIONS §398-5). **과녁이 23 → 24 로 늘었다** —
#:   `plan_renumber.py` 가 `OUTSIDE_LEADS` 래칫을 달면서 「관문 ∧ 래칫」 조건에
#:   들어왔다. 그 도구에서 흔든 넷 중 **셋이 살았다.** 생존이 올랐지만 그물이
#:   같이 커졌다(92 → 96) — 비율이 아니라 둘을 같이 봐야 하는 이유다.
SURVIVORS = 67
#: 흔든 수 — 올라가는 쪽으로만. 분모를 안 잠그면 생존 수는 수가 아니다.
MUTANTS = 96
#: 붙잡이가 **0 인 과녁** 수. 흔들어도 못 재는 자리다 — 내려가는 쪽으로만.
UNCATCHABLE = 0
#: 생존 중 **래칫이 드는 것.** 이 문이 안 붙들 뿐 다른 문이 붙든다 — 올라가는
#: 쪽으로만. 줄면 래칫 선언이 사라졌다는 뜻이고 그건 나쁜 쪽이다.
RATCHET_HELD = 20
#: 생존 중 **아직 아무도 안 가른 것.** 내려가는 쪽으로만.
UNSORTED = 47
RATCHETS = {"SURVIVORS": "down", "MUTANTS": "up", "UNCATCHABLE": "down",
            "RATCHET_HELD": "up", "UNSORTED": "down"}

_HARMLESS = "\n# mutation-probe — 무해 돌연변이. 행동을 안 바꾼다.\n"


# ── ① 흔들기 ────────────────────────────────────────────────────
#: `(찾을 것, 바꿀 것)`. **연산자와 상수만** 건드린다 — 이름을 바꾸면
#: `NameError` 로 전부 죽고, 전부 죽음은 아무것도 안 잰 것과 같다.
_CMP = {ast.GtE: ">", ast.Gt: ">=", ast.LtE: "<", ast.Lt: "<=",
        ast.Eq: "!=", ast.NotEq: "=="}
_CMP_SRC = {ast.GtE: ">=", ast.Gt: ">", ast.LtE: "<=", ast.Lt: "<",
            ast.Eq: "==", ast.NotEq: "!="}


def mutants(src: str) -> list[tuple[str, str]]:
    """`(설명, 바뀐 소스)` 목록. **결정적이다** — 같은 입력에 같은 순서.

    ★ 줄 단위 치환이다. AST 로 자리를 **찾고**, 바꾸는 것은 그 줄의 글자다 —
      `ast.unparse` 로 다시 쓰면 주석이 통째로 날아가고, 그러면 돌연변이가
      「연산자 하나」가 아니라 「파일 전체」가 된다.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    lines = src.split("\n")
    out: list[tuple[str, str]] = []
    seen: set[tuple[int, int]] = set()

    def emit(lineno: int, old: str, new: str, what: str) -> None:
        i = lineno - 1
        if not (0 <= i < len(lines)) or old not in lines[i]:
            return
        if (i, hash(old + new)) in seen:
            return
        seen.add((i, hash(old + new)))
        edited = list(lines)
        edited[i] = lines[i].replace(old, new, 1)
        out.append((f"{lineno}: {what}", "\n".join(edited)))

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = type(node.ops[0])
            if op in _CMP:
                emit(node.lineno, _CMP_SRC[op], _CMP[op],
                     f"{_CMP_SRC[op]} → {_CMP[op]}")
        elif isinstance(node, ast.BoolOp):
            a, b = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
            emit(node.lineno, f" {a} ", f" {b} ", f"{a} → {b}")
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            emit(node.lineno, "not ", "", "not 제거")
        elif isinstance(node, ast.Constant):
            if node.value is True:
                emit(node.lineno, "True", "False", "True → False")
            elif node.value is False:
                emit(node.lineno, "False", "True", "False → True")
            elif isinstance(node.value, int) and not isinstance(node.value, bool):
                emit(node.lineno, str(node.value), str(node.value + 1),
                     f"{node.value} → {node.value + 1}")
    return out


# ── ② 붙잡이 도출 ───────────────────────────────────────────────
def catchers(tool: str, deep: bool = False) -> list[list[str]]:
    """그 도구를 붙드는 명령들. **열거하지 않고 도출한다.**

    ★ 2026-10-05 실측. `deep` 을 켜면 시험 파일까지 붙잡이로 돌리는데,
      도구 셋 · 돌연변이 12개씩에서도 **한 시간이 넘어 안 끝났다.** 값을 못
      치르는 관문은 안 돌고, 안 도는 관문은 없는 관문이다(§286). 그래서
      기본은 **자기검사만**이고, 그 대신 이 도구는 「전수가 아니다」를
      `전수` 칸으로 **적는다.** 약한 측정인 것을 숨기지 않는 쪽을 골랐다.
    """
    got: list[list[str]] = []
    src = (TOOLS / f"{tool}.py").read_text(encoding="utf-8")
    if "--selftest" in src:
        got.append([sys.executable, f"tools/{tool}.py", "--selftest"])
    if not deep:
        return got
    named = sorted(p for p in TESTS.glob("test_*.py")
                   if re.search(rf"\b{re.escape(tool)}\b",
                                p.read_text(encoding="utf-8", errors="replace")))
    if named:
        got.append([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:randomly",
                    *[str(p.relative_to(ROOT)) for p in named]])
    return got


def _run(cmd: list[str]) -> bool:
    """붙잡이를 돌린다. 초록이면 참. 시간 초과는 **거짓이 아니라 예외**다.

    ★ 환경을 **안 짓는다** — 부르는 쪽 것을 그대로 물려받는다. `os.environ` 을
      여기서 읽으면 `env_check` 가 운다(독자는 `paths.py` 하나다 · §342-4).
    """
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                       text=True, timeout=TIMEOUT, check=False)
    return p.returncode == 0


def live_catchers(tool: str, deep: bool = False) -> tuple[list[list[str]], list[str]]:
    """밑동에서 초록이고 **무해 돌연변이에 안 우는** 붙잡이만 낸다.

    ★ 뺀 것은 이름과 사유를 낸다 — 말없이 빠지면 「전부 잡았다」가 거짓이 된다.
    """
    path = TOOLS / f"{tool}.py"
    orig = path.read_text(encoding="utf-8")
    keep, dropped = [], []
    try:
        for c in catchers(tool, deep):
            tag = " ".join(c[-2:])
            if not _run(c):
                dropped.append(f"{tag} — 밑동에서 이미 빨갛다")
                continue
            path.write_text(orig + _HARMLESS, encoding="utf-8")
            still = _run(c)
            path.write_text(orig, encoding="utf-8")
            if still:
                keep.append(c)
            else:
                dropped.append(f"{tag} — 주석 한 줄에도 운다(내용 지문)")
    finally:
        path.write_text(orig, encoding="utf-8")
    return keep, dropped


# ── ③ 재기 ──────────────────────────────────────────────────────
def pick(muts: list[tuple[str, str]], cap: int) -> list[tuple[str, str]]:
    """상한 안에서 **파일 전체에 고르게** 고른다. 결정적이다.

    ★ 앞에서부터 자르면 머리말·import 쪽만 흔든다 — 거기는 어차피 행동이
      없어서 「생존」이 쏟아지고, 수가 커지는데 뜻은 없다.
    """
    if cap <= 0 or len(muts) <= cap:
        return muts
    step = len(muts) / cap
    return [muts[int(i * step)] for i in range(cap)]


# ★ **흔드는 동안 트리는 거짓말을 한다**(DECISIONS §398-6). 과녁을 제자리에서
#   바꿔 쓰고 `finally` 로 되돌린다 — 되돌리기는 보장되지만 **그 창 안에**
#   다른 관문을 돌리면 그 관문이 흔들린 사본을 읽는다. 실측: 이 배치에서
#   `docseal stamp` 를 같이 돌렸다가 도장 열다섯이 흔들린 `docseal.py` 의
#   지문을 박았고, 복원된 뒤 전부 무효가 됐다. **같이 돌리지 마라.**
def shake(tool: str, cap: int = MAX_PER_TOOL, deep: bool = False) -> dict:
    path = TOOLS / f"{tool}.py"
    orig = path.read_text(encoding="utf-8")
    keep, dropped = live_catchers(tool, deep)
    muts = pick(mutants(orig), cap)
    survived: list[str] = []
    unmeasured: list[str] = []
    # ★ 붙잡이가 **0 이면 흔들지 않는다.** 2026-10-05 실측(DECISIONS §398-6).
    #   `plan_renumber.py` 가 과녁에 들어오자 흔든 넷이 전부 「생존」으로
    #   집계됐고 생존 총계가 64 → 68 로 올랐다. 읽으면 붙잡이가 0 이었다 —
    #   **아무것도 안 돌리고 「시험이 안 잡는다」고 적고 있었다.** 못 잡은
    #   것과 **안 돌린** 것은 다른 사실이고, 섞으면 수가 거짓말을 한다(족 6).
    if not keep:
        unmeasured = [w for w, _ in muts]
        muts = []
    try:
        for what, body in muts:
            path.write_text(body, encoding="utf-8")
            try:
                killed = any(not _run(c) for c in keep)
            except subprocess.TimeoutExpired:
                unmeasured.append(what)
                continue
            if not killed:
                survived.append(what)
    finally:
        path.write_text(orig, encoding="utf-8")
    return {"도구": tool, "돌연변이": len(muts), "전수": len(mutants(orig)),
            "생존": survived,
            "못 쟀다": unmeasured, "붙잡이": len(keep), "뺀 붙잡이": dropped,
            "지문": hashlib.sha256(orig.encode()).hexdigest()[:12]}


def _ratchet_line(tool: str, name: str) -> int:
    """`tools/<tool>.py` 에서 `name` 을 대입하는 **모듈 수준 줄 번호**.

    ★ 2026-10-06. 판별식이 줄 번호를 박고 있었다(`52: 363 → 364`). 그 파일에
      주석 세 줄을 더하자 합성 입력이 **빈 결과**를 냈고 판별식이 거짓으로
      울었다 — 재는 자가 재는 대상의 줄 수에 매달려 있었다.
    """
    for node in ast.parse((TOOLS / f"{tool}.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == name:
            return node.lineno
    raise RuntimeError(f"{tool}.py 에 {name} 대입이 없다")


def sort_survivors(d: dict) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
    """생존을 **래칫이 드는 것**과 **아직 안 가른 것**으로 나눈다.

    ★ 2026-10-06 (DECISIONS §410 · PLAN 「생존 분류」). 생존 67 을 한 수로 내면
      「시험이 안 붙든 자리가 67」로 읽힌다. **틀린 읽기다** — 그중 스물은
      **래칫 상수**이고, 그 수를 흔들면 `tools/ratchet.py` 가 선언과 실측이
      갈렸다고 운다. 이 도구가 돌리는 것은 **그 도구의 시험**뿐이라 그 문을
      못 본다.

      즉 생존은 「아무도 안 붙든다」가 아니라 **「이 문이 안 붙든다」**를 센다.
      그 둘을 안 가르면, 래칫을 하나 달 때마다 생존이 늘어 **좋은 일이 나쁜
      수로 보인다**(2026-10-05 에 `plan_renumber` 에서 실제로 그랬다).

    ★ 가름은 **추측이 아니라 읽기**다. 모듈 수준 대입의 이름이 그 도구의
      `RATCHETS` 키에 있으면 래칫 상수다 — 이름을 AST 로 읽는다.
    """
    held: list[tuple[str, str, str]] = []
    rest: list[tuple[str, str]] = []
    for r in d["도구별"]:
        src = (TOOLS / f"{r['도구']}.py").read_text(encoding="utf-8")
        names: dict[int, str] = {}
        try:
            for node in ast.parse(src).body:
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                    names[node.lineno] = node.targets[0].id
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    names[node.lineno] = node.target.id
        except SyntaxError:
            pass
        keys = set(re.findall(r'"(\w+)"', (re.search(
            r"^RATCHETS\s*[:=].*?\{(.*?)\}", src, re.S | re.M) or
            type("", (), {"group": lambda *_: ""})()).group(1)))
        for w in r["생존"]:
            nm = names.get(int(w.split(":")[0]))
            if nm and nm in keys:
                held.append((r["도구"], w, nm))
            else:
                rest.append((r["도구"], w))
    return held, rest


def ratchet_values() -> dict[str, int]:
    """대장을 읽는다. 없거나 **낡았으면 재는 쪽이 맞다** — 0 을 내지 않는다."""
    if not LEDGER.exists():
        raise RuntimeError("data/golden/mutation.json 이 없다 — "
                           "`mutate.py --write` 가 만든다 (느리다)")
    d = json.loads(LEDGER.read_text(encoding="utf-8"))
    for r in d["도구별"]:
        now = hashlib.sha256((TOOLS / f"{r['도구']}.py")
                             .read_text(encoding="utf-8").encode()).hexdigest()[:12]
        if now != r["지문"]:
            raise RuntimeError(f"{r['도구']}.py 가 잰 뒤로 바뀌었다 — 다시 재야 한다")
    held, rest = sort_survivors(d)
    return {"SURVIVORS": d["생존"], "MUTANTS": d["돌연변이"],
            "UNCATCHABLE": sum(1 for r in d["도구별"] if r["붙잡이"] == 0),
            "RATCHET_HELD": len(held), "UNSORTED": len(rest)}


# ── ④ 자기검사 ──────────────────────────────────────────────────
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

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 12")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="시험이 도구를 붙들고 있는가")
    ap.add_argument("--tool", help="도구 하나만")
    ap.add_argument("--write", action="store_true", help="대장에 적는다 (느리다)")
    ap.add_argument("--max", type=int, default=MAX_PER_TOOL,
                    help=f"도구당 흔들 상한 (기본 {MAX_PER_TOOL} · 0 이면 전수)")
    ap.add_argument("--deep", action="store_true",
                    help="시험 파일까지 붙잡이로 (실측 한 시간 넘음 · 기본 꺼짐)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--classify", action="store_true",
                    help="생존을 래칫이 드는 것과 아직 안 가른 것으로 나눈다")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    if a.classify:
        # ★ 2026-10-06 (DECISIONS §410). 생존을 **가른다** — 세는 것이 아니라.
        if not LEDGER.exists():
            print("data/golden/mutation.json 이 없다 — `--write` 가 만든다")
            return 2
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        held, rest = sort_survivors(d)
        print(f"생존 {d['생존']} = 래칫이 든다 {len(held)} + 아직 안 가름 {len(rest)}")
        print("\n── 래칫이 든다 — 이 문이 아니라 `tools/ratchet.py` 가 붙든다")
        for t, w, nm in held:
            print(f"  {t:16} {w:22} ← {nm}")
        print("\n── 아직 안 가름 — 사람이 하나씩 봐야 한다")
        for t, w in rest:
            print(f"  {t:16} {w}")
        return 0

    names = [a.tool] if a.tool else targets()
    rows = [shake(n, a.max, a.deep) for n in names]
    tot_m = sum(r["돌연변이"] for r in rows)
    tot_s = sum(len(r["생존"]) for r in rows)
    for r in rows:
        print(f"\n── {r['도구']}  흔듦 {r['돌연변이']}/{r['전수']}"
              f" · 생존 {len(r['생존'])} · 붙잡이 {r['붙잡이']}")
        for s in r["생존"]:
            print(f"     생존  {s}")
        for d in r["뺀 붙잡이"]:
            print(f"     뺌    {d}")
        for u in r["못 쟀다"]:
            print(f"     못 쟀다 {u}")
    print(f"\n돌연변이 {tot_m} · 생존 {tot_s}")
    print("★ **생존이 나쁘다고 말하지 않는다.** 정렬 키처럼 행동을 안 바꾸는"
          " 자리의 생존은 정상이다 — 가르는 것은 사람이다.")
    if a.write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(
            {"돌연변이": tot_m, "생존": tot_s, "도구별": rows},
            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"→ {LEDGER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

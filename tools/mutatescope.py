#!/usr/bin/env python3
"""
mutatescope.py — **무엇을 흔들고, 흔든 것을 무엇이 붙드나.** 과녁과 지문만 산다.

── 왜 갈라졌나 (2026-10-09 · DECISIONS §445 · PLAN #166 닫힘) ──
`tools/mutate.py` 가 상한(600)을 넘었는데 **쪼개는 길이 막혀 있었다.**
`catch_print()` 가 그 도구와 그 이름을 적은 시험만 해시했으므로, 무엇이든
옆 파일로 떼면 **문을 고쳐도 장부가 안 낡는다** — `#159` 가 고친 구멍의
재발이다. 길을 먼저 넓히고(아래 `catch_print` 가 끌어오는 모듈도 해시한다)
그 뒤에 쪼갰다.

★ **금이 어디인가** — 「고를 것 · 지문」과 「흔들 것 · 돌릴 것」이다. 앞은
  정적이다(파일을 읽고 이름을 낸다). 뒤는 돈다(돌연변이를 심고 붙잡이를
  부른다). 같은 물음을 두 번 묻는 자리가 여기 모인다 —
  `_imports_ratchet`(과녁 고르기)과 `local_imports`(지문 넓히기)가 **같은
  `imported()`** 를 쓴다. 갈라 두면 둘이 갈릴 수 있었다.

IN    tools/*.py · tests/test_*.py · `toolclass.classify()`
OUT   도구 이름 목록 · 지문 문자열
밖    **흔들지 않는다** — 돌연변이를 만들고 붙잡이를 돌리는 것은 `mutate` 다.
      **장부를 안 쓴다** — 쓰는 자리는 `mutate --write` 하나다.
      **무엇이 좋은 지문인가는 안 고른다** — 넓히는 결정은 §445 가 든다.
부류  몸통   진입점이 **아니다.** `mutate.py` 가 import 한다  (DECISIONS §398)
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
TESTS = ROOT / "tests"

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
    # ★ **같은 목록에서 낸다.** `glob` 으로 따로 훑으면 `deadcheck ⑤`(좁은 범위)가
    #   울고, 그 말이 맞다 — 목록이 둘이면 둘이 갈린다(족 2). `toolclass` 가
    #   도구의 정본 목록이다.
    body = {rel: (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            for rel in rows if rel.endswith(".py")}
    decl = {Path(rel).stem for rel, src in body.items() if "RATCHETS" in src}
    out = []
    for rel, r in rows.items():
        p = ROOT / rel
        if r["부류"] != "관문" or p.suffix != ".py":
            continue
        src = body[rel]
        if "RATCHETS" in src or _imports_ratchet(src, decl):
            out.append(p.stem)
    return sorted(out)


def imported(src: str) -> set[str]:
    """그 소스가 끌어오는 **최상위 모듈 이름** 전부. 문법으로 센다.

    ★ 2026-10-09 (DECISIONS §445 · PLAN #166). 종전에는 정규식
      「줄머리의 `from … import`」를 찾는 정규식이었다. 그 식은 줄머리만 보므로
      **함수 안에서 끌어오는 것을 못 본다** — 그런데 이 저장소는 맞물림을
      끊으려고 일부러 함수 안에서 끌어온다(`sizetable` 이 `sizecheck.measure`
      를, `mutate` 가 `mutatetest.selftest` 를). 즉 식이 「옆집에 선언이
      있는가」를 묻는다면서 **옆집을 함수 안에서 부르는 꼴을 통째로 놓쳤다.**
    ★ 실측 — 자기검사를 `mutatetest` 로 떼고 함수 안에서 끌어오자
      `local_imports('mutate')` 가 **빈 목록**을 냈다. 지문이 그 파일을 안
      덮으므로 **문을 고쳐도 장부가 안 낡는다** — `#166` 이 든 그 구멍이
      쪼개는 순간 그대로 재현됐다. 낱말이 아니라 **문법**으로 센다(§444-1).
    ★ 문법 오류면 **빈 집합**이다 — 그 파일은 어차피 import 가 안 되고
      `ruff` 와 `test_static` 이 먼저 운다.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module.split(".")[0])
        elif isinstance(n, ast.Import):
            out.update(a.name.split(".")[0] for a in n.names)
    return out


def _imports_ratchet(src: str, decl: set[str]) -> bool:
    """**선언을 옆집에 둔 관문도 과녁이다.**  (2026-10-09 · DECISIONS §440-10)

    ★ 과녁의 뜻은 「관문이면서 무엇을 지키는지 **수로 적힌** 도구」다. 그 수가
      같은 파일에 있어야 한다는 뜻이 아니었는데, 판별식이 `"RATCHETS" in src`
      하나뿐이라 **그렇게 읽혔다.**
    ★ 실측 — `sizecheck` 의 예외 표를 `sizetable` 로 뗐더니(§440-3) 그 도구가
      **과녁에서 조용히 빠졌다.** 여전히 관문이고 여전히 그 수를 지키는데
      아무도 안 흔든다. 쪼개는 일이 돌연변이 덮임을 깎는 쪽으로 돌아간다 —
      쪼개는 것은 이 저장소가 **권하는** 일이므로 그 길에 구멍을 두면 안 된다.
    """
    return bool(imported(src) & decl)


def named_tests(tool: str) -> list[Path]:
    """그 도구 **이름을 적은** 시험 파일. `catchers` 와 지문이 **같은 자**를 본다.

    ★ 2026-10-08 (DECISIONS §431 · PLAN #159). 종전에는 이 도출이 `catchers()`
      안에 **파묻혀** 있었고 `--deep` 일 때만 돌았다. 그래서 장부의 신선도
      지문이 도구 파일 하나였다 — **시험을 지워도 「잡는다」가 그대로 남았다.**
      그쪽이 위험하다. 같은 자를 두 곳이 봐야 둘이 안 갈린다(족 2).
    """
    return sorted(q for q in TESTS.glob("test_*.py")
                  if re.search(rf"\b{re.escape(tool)}\b",
                               q.read_text(encoding="utf-8", errors="replace")))


def local_imports(src: str) -> list[str]:
    """그 도구가 **같은 `tools/` 안에서** 끌어오는 모듈 이름. 정렬해 낸다.

    ★ 2026-10-09 (DECISIONS §445 · PLAN #166). `_imports_ratchet` 과 **같은
      물음**이다 — 「선언이 옆집에 있다」. 거기서는 과녁을 고르고 여기서는
      지문을 넓힌다. 묻는 것이 같으므로 찾는 식도 같아야 한다(`_IMPORT`).
    ★ 표준 꾸러미·외부 꾸러미는 빠진다 — `tools/<이름>.py` 가 있는 것만.
    """
    return sorted(m for m in imported(src) if (TOOLS / f"{m}.py").is_file())


def catch_print(tool: str) -> str:
    """**붙잡이의 지문.** 도구 + 그 도구가 끌어오는 `tools/` 모듈 + 그 이름을 적은 시험.

    ★ 시험 파일이 바뀌면 **그 도구만** 낡는다 — `--write --stale` 이 그것만
      다시 잰다. 도구 파일만 해시하면 시험을 더해도 장부가 안 낡고, 지워도
      안 낡는다. 「시험이 붙든다」는 주장을 **시험 없이** 하는 꼴이다.

    ★ 2026-10-09 (DECISIONS §445 · PLAN #166 닫힘). **옆집 모듈을 더했다.**
      종전에는 `tools/<도구>.py` 와 그 이름을 적은 시험만 해시했다. 그래서
      `selftest()` 를 옆 파일로 떼면 **문을 고쳐도 장부가 안 낡는다** —
      쪼개는 일이 돌연변이 덮임을 깎는 쪽으로 돌아갔고(`#159` 가 고친 구멍의
      재발), 그 막힘 때문에 이 파일이 상한을 넘은 채 예외로 앉아 있었다.
      **쪼개는 것은 이 저장소가 권하는 일이므로 그 길에 구멍을 두지 않는다.**
    ★ 한 겹만 따라간다(`import` 의 `import` 는 안 본다). 더 깊이 가면
      `firelane` 꾸러미까지 끌려 들어와 거의 모든 도구가 서로를 낡게 만들고,
      그러면 `--stale` 이 매번 전량이 된다 — 값을 못 치르는 관문은 안 돈다.
    """
    h = hashlib.sha256((TOOLS / f"{tool}.py").read_bytes())
    src = (TOOLS / f"{tool}.py").read_text(encoding="utf-8")
    for m in local_imports(src):
        h.update(f"import:{m}".encode())
        h.update((TOOLS / f"{m}.py").read_bytes())
    for q in named_tests(tool):
        h.update(q.relative_to(ROOT).as_posix().encode())
        h.update(q.read_bytes())
    return h.hexdigest()[:12]

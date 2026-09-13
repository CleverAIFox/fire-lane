#!/usr/bin/env python3
"""
b3_rules.py — **규칙 조립 3벌을 정본 함수 하나로 만든다.**

    uv run python tools/batches/b3_rules.py            무엇을 할지만
    uv run python tools/batches/b3_rules.py --apply    실제로

★ `tests/test_place_idempotent.py::rules()` 가 스스로 적어놨다 —
  *"이 이중화 자체가 냄새다 — 규칙 조립을 함수로 빼면 이 블록이 사라진다. TODO."*
  이 배치가 그 TODO 다.

★ 셋이 **서로 다르다.** 이것이 이 배치를 여는 근거다.

      main()                 EXT 에 json 있음 · `[a-z0-9_-]` (하이픈 허용)
      test_normalize_rules   EXT 에 json 있음 · `[a-z0-9_-]`
      test_place_idempotent  EXT 에 json **없음** · `[a-z0-9_]`  (하이픈 없음)

  셋째가 두 축 다 낡았다. 09-03(하이픈) · 09-07(json) 정정이 main() 에만
  반영됐고 사본은 안 따라왔다. `providers.all()` 은 이미 정본을 쓰는데
  **정규식 본체가 사본**이라 그 정본이 소용없었다.

  → 그래서 검사가 넓어진다. `eais_..._jngj-dongmyeong_...json` 같은 파일이
    지금까지 멱등 검사를 **안 탔다.** 이제 탄다.
    ★ 이건 위험이 아니라 이 배치의 **목적**이다. 검사가 좁아서 못 보던 것을
      보게 만드는 것이고, 여기서 터지면 그건 배치가 만든 고장이 아니라
      원래 있던 고장이다(원칙 ④ — 0건이면 프로브를 의심한다).

★ **산출물 지문은 안 움직인다.** main() 의 동작은 한 글자도 안 바뀐다 —
  지금 조립하는 것과 똑같은 표를 함수로 뽑아 그대로 부른다.
  움직이는 것은 테스트의 범위뿐이다. 그래서 B3(불변)이고 재잠금이 없다.

정본의 자리 — `normalize_raw.passthrough_rules()`.
  ⒜ `RULES` 를 **복사해서** 돌려준다. 모듈 전역을 부풀리면 같은 프로세스에서
     두 번 부를 때 규칙이 누적된다(`test_main_does_not_mutate_global_rules` 가
     `RULES.append` 를 금지하는 이유가 그것이다).
  ⒝ `EXT` 도 모듈 전역으로 올린다. main() 안에 있으면 테스트가 또 베낀다.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent

# ── ⒜ 정본 함수를 심는다 ────────────────────────────────────────
ANCHOR = "RULES: list[tuple[str, str, str]] = [\n"

CANON = '''# 통과 규칙의 확장자 화이트리스트. **모듈 전역이다.**
# ★ main() 안에 두면 테스트가 베낀다. 실제로 두 벌이 생겼고 한 벌은
#   `json` 이 빠진 채 굳었다(2026-09-11 B3 에서 발견).
#   hwp·pdf·ngi·nda 가 없어 왕복 멱등이 거짓이었던 이력도 같은 병이다.
PASSTHROUGH_EXT = "zip|csv|json|tif|xml|hwpx?|pdf|ngi|nda|geojson"


def passthrough_rules(orgs=None) -> list[tuple[str, str, str]]:
    """`RULES` + 제공기관별 통과 규칙. **규칙 표의 정본 조립기다.**

    ★ 2026-09-11 (B3). main() 안에 있던 조립을 여기로 뺐다. 테스트 두 개가
      같은 표를 손으로 재현하고 있었고 셋이 서로 달랐다 — 하이픈 허용 여부와
      EXT 의 json 포함 여부에서 갈렸다. 소비자를 하나씩 고치지 않고
      **유도를 정본으로** 만든다(HANDOFF 원칙 ⑤ · `ledger.provider_of` 와 같은 수).

    ★ 반드시 `RULES` 의 **사본**을 돌려준다. 모듈 전역에 append 하면 같은
      프로세스에서 두 번 부를 때 규칙이 중복 누적된다.

    ★ 하이픈. 대장 `scopes` 가 `jngj-donggu` 처럼 하이픈을 쓰고 그 블록이
      "별칭 안에 언더스코어를 쓰지 않는다" 고 못 박는다 — 언더스코어가 필드
      구분자라서다. 하이픈은 처음부터 허용이었고 이 정규식만 몰랐다.
      **대장이 정본인데 코드가 더 좁았다.**
    """
    org_list = providers.all() if orgs is None else orgs
    return list(RULES) + [
        (rf"^{o}_[a-z0-9_-]+_\\d{{8}}\\.({PASSTHROUGH_EXT})$", o, None)
        for o in sorted(org_list)
    ]


RULES: list[tuple[str, str, str]] = [
'''

EDITS: list[tuple[str, str, str, str]] = [
    ("src/firelane/normalize_raw.py", ANCHOR, CANON, "def passthrough_rules("),

    # ── main() 이 정본을 쓴다 ────────────────────────────────
    ("src/firelane/normalize_raw.py",
     '    EXT = "zip|csv|json|tif|xml|hwpx?|pdf|ngi|nda|geojson"\n',
     "    # EXT · 조립은 모듈 전역 passthrough_rules() 가 정본이다(위).\n",
     "# EXT · 조립은 모듈 전역 passthrough_rules() 가 정본이다(위)."),
    ("src/firelane/normalize_raw.py",
     '    rules = RULES + [(rf"^{org}_[a-z0-9_-]+_\\d{{8}}\\.({EXT})$", org, None)\n'
     "                     for org in sorted(ORG)]\n",
     "    rules = passthrough_rules(ORG)\n",
     "    rules = passthrough_rules(ORG)\n"),

    # ── 사본 ① test_normalize_rules (모듈 전역) ──────────────
    #   ★ 이 파일 안에 EXT 리터럴이 **두 번** 있다. 43줄(전역)과 265줄
    #     (`test_general_rule_accepts_every_scope_alias` 안의 지역 변수).
    #     즉 규칙 조립은 3벌이 아니라 4벌이었다 — 감사가 하나 덜 셌다.
    ("tests/test_normalize_rules.py",
     'ORG = providers.all()\n'
     'EXT = "zip|csv|json|tif|xml|hwpx?|pdf|ngi|nda|geojson"\n',
     "ORG = providers.all()\n"
     "EXT = N.PASSTHROUGH_EXT          # 정본. 여기 적으면 또 갈린다\n",
     "EXT = N.PASSTHROUGH_EXT"),
    ("tests/test_normalize_rules.py",
     '    EXT = "zip|csv|json|tif|xml|hwpx?|pdf|ngi|nda|geojson"\n'
     '    pat = re.compile(rf"^nfa_[a-z0-9_-]+_\\d{{8}}\\.({EXT})$")\n',
     "    # 정본을 쓴다. 이 지역 사본이 네 번째 벌이었다(2026-09-11 B3).\n"
     '    pat = re.compile(rf"^nfa_[a-z0-9_-]+_\\d{{8}}\\.({N.PASSTHROUGH_EXT})$")\n',
     "({N.PASSTHROUGH_EXT})$"),
    ("tests/test_normalize_rules.py",
     "def _rules(passthrough: bool):\n"
     "    r = list(N.RULES)\n"
     "    if passthrough:\n"
     "        # ★ 하이픈. 스코프 별칭이 `jngj-donggu` 처럼 하이픈을 쓴다.\n"
     "        #   main() 은 09-03 에 고쳤고 이 사본이 남아 있었다.\n"
     '        r += [(rf"^{o}_[a-z0-9_-]+_\\d{{8}}\\.({EXT})$", o, None)\n'
     "              for o in sorted(ORG)]\n"
     "    return r\n",
     "def _rules(passthrough: bool):\n"
     "    # ★ 2026-09-11 (B3). 손으로 재현하던 것을 정본 조립기로 바꿨다.\n"
     "    #   하이픈 사본이 여기 남아 있던 것이 09-03 정정이 안 따라온 흔적이다.\n"
     "    return N.passthrough_rules(ORG) if passthrough else list(N.RULES)\n",
     "return N.passthrough_rules(ORG) if passthrough else list(N.RULES)"),

    # ── 사본 ② test_place_idempotent ─────────────────────────
    ("tests/test_place_idempotent.py",
     'EXT = "zip|csv|tif|xml|hwpx?|pdf|ngi|nda|geojson"\n',
     "EXT = M.PASSTHROUGH_EXT          # 정본. 이 사본에는 json 이 빠져 있었다\n",
     "EXT = M.PASSTHROUGH_EXT"),
    ("tests/test_place_idempotent.py",
     "def rules():\n"
     '    """main() 이 조립하는 것과 같은 규칙 표.\n'
     "\n"
     "    ★ main() 안에서 조립하므로 여기서 재현한다. 이 이중화 자체가 냄새다 —\n"
     "      규칙 조립을 함수로 빼면 이 블록이 사라진다. TODO.\n"
     '    """\n'
     "    return M.RULES + [\n"
     '        (rf"^{org}_[a-z0-9_]+_\\d{{8}}\\.({EXT})$", org, None)\n'
     "        for org in sorted(ORG)\n"
     "    ]\n",
     "def rules():\n"
     '    """main() 이 조립하는 것과 **같은** 규칙 표. 이제 진짜로 같다.\n'
     "\n"
     "    ★ 2026-09-11 (B3). 위 TODO 를 닫았다. 재현하던 사본은 두 축에서\n"
     "      낡아 있었다 — `[a-z0-9_]`(하이픈 없음) · EXT 에 json 없음.\n"
     "      그래서 하이픈 별칭 파일과 json 이 **멱등 검사를 안 탔다.**\n"
     '    """\n'
     "    return M.passthrough_rules(ORG)\n",
     "    return M.passthrough_rules(ORG)\n"),
]


def _names(src: str) -> set[str]:
    out: set[str] = set()
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    by_file: dict[str, list[tuple[str, str, str]]] = {}
    for rel, old, new, done in EDITS:
        by_file.setdefault(rel, []).append((old, new, done))

    changed = skipped = 0
    for rel, pairs in by_file.items():
        p = ROOT / rel
        before = p.read_text(encoding="utf-8")
        text = before
        for old, new, done in pairs:
            if done in text:
                skipped += 1
                continue
            if text.count(old) != 1:
                sys.exit(f"★ {rel} — 대상이 {text.count(old)}곳이다. 멈춘다.\n{old!r}")
            text = text.replace(old, new)
            changed += 1
        if text == before:
            print(f"  = {rel}  이미 적용됨")
            continue
        lost = _names(before) - _names(text)
        if lost:
            sys.exit(f"★ {rel} — 최상위 이름이 사라진다: {sorted(lost)}. 되돌린다.")
        try:
            ast.parse(text)
        except SyntaxError as e:
            sys.exit(f"★ {rel} — 편집 결과가 파싱 안 된다: {e}")
        print(f"  {'✓' if a.apply else '·'} {rel}")
        if a.apply:
            p.write_text(text, encoding="utf-8")

    print(f"\n변경 {changed} · 건너뜀 {skipped}"
          + ("" if a.apply else "   ★ dry-run. --apply 를 붙일 것"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

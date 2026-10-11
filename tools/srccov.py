#!/usr/bin/env python3
"""
srccov.py — **판정 폐포에서 시험이 안 드는 순수 함수가 몇인가.** 래칫.

    uv run python tools/srccov.py
    uv run python tools/srccov.py --list        안 드는 것을 모듈별로 본다
    uv run python tools/srccov.py --selftest

── 왜 생겼나 (DECISIONS §493) ──────────────────────────────────
§481 이 `tools/` 에, §482 가 `web/navi/` 에 **같은 질문**을 했다 — 「시험이
이름으로도 안 부르는 것이 몇인가」. 둘 다 그 수를 세자마자 결함이 나왔다
(§473 의 상수 한 벌 · §483 의 `nextHazard` 꼴). **`src/firelane` 에는 그
질문을 한 적이 없었다.** 거기가 판정이 사는 자리인데, 시험 2700 판이 돌고
있어서 「돈다」와 「든다」가 구별되지 않았다.

재 보니 **순수 함수 중 시험이 이름으로도 안 부르는 것**이 있었고, 첫 하나를
밀자마자 `segkey._road_hash` 의 머리말이 **거짓**이었다 — 「`None` 과 빈
문자열이 같은 키를 받으면 안 된다」고 적어 두고 코드는 같은 토큰을 준다
(그리고 같은 토큰이 옳다). 미는 자가 없으면 **머리말이 코드와 갈려도
조용하다.**

★ **부류로 나눈다.** 나누지 않으면 수가 섞인다 — 「`argparse` 를 들고 argv
  를 읽는 진입점」과 「파일을 여는 것」과 「인자만 받아 값을 내는 것」이
  한 수에 들어가면 그 수는 아무도 안 본다(§481 의 「부류로 나누지 않아 못
  봤다」와 같은 병).

      진입점   `cmd_*` · `main` · `*_cli` · argv/argparse 를 든다
      입출력   몸통이 파일·프로세스·망을 만진다
      순수     인자만 받아 값을 낸다                        ← **여기를 문다**

★ 왜 순수만 무는가. 입출력 함수는 「이름을 안 부른다」가 결함이라고 단정할
  수 없다 — `tests/test_lake.py` 처럼 **산출물로** 드는 시험이 있다. 순수
  함수는 다르다. 이름을 아무 시험도 안 부르면 그 함수의 문턱·경계·되돌림을
  **아무도 지켜 주지 않는다.**

IN    src/firelane/**/*.py · tests/*.py
OUT   표준출력 (판정)
PARAM SRC_UNTESTED · SRC_IO_UNTESTED (래칫 둘)
밖    **시험이 좋은가는 안 본다.** 이름을 부르면 든 것으로 센다 —
      `tools/canary.py` · `tools/navicov.py` 와 같은 한계이고 같은 이유로
      **일부러** 느슨하다.
      **밑줄 이름을 안 센다.** `_road_hash` 는 내보낸 자가 아니고, 그것을
      무는 자리는 그것을 부르는 공개 함수다.
      **몸통만 본다.** 부르는 함수가 파일을 열면 못 본다 — 그래서 순수
      분모가 **넓게** 잡힌다. 넓은 쪽이 옳다(안 무는 쪽으로 새는 것보다
      무는 쪽으로 넘치는 것이 싸다).
      **메서드를 안 센다.** `Name.filename` 은 그 자료형을 드는 시험이
      든다 — 최상위 함수만 분모다.
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "firelane"
TESTS = ROOT / "tests"

#: 안 드는 순수 함수 수. **내려가는 쪽으로만.**
#:
#: ★ 이력 — 2026-10-12 §493 첫 실측 **56**(순수 230 중). 같은 배치에서
#:   `segkey` · `naming` · `skeleton` · `mercator` · `ledger` 에 시험을 달아
#:   내렸다.
SRC_UNTESTED = 2

#: **입출력** 부류에서 시험이 이름을 안 부르는 수. 내려가는 쪽으로만.
#:
#: ★ 2026-10-12 (DECISIONS §497). §493 은 이 부류를 「안 문다」로 뒀다 —
#:   산출물로 드는 시험이 있을 수 있어서 **결함이라고 단정할 수 없다**는
#:   이유였고 그것은 지금도 맞다. 그러나 「물지 않는다」와 「세지 않는다」는
#:   다르다 — §435 · §468 이 다른 축에서 배운 그것이다. 세어 보니 서른이고,
#:   그중 넷은 **합성 입력으로 밀 수 있는 것**이었다(`read_text_table`
#:   (c00 이름 규칙 · 법정동코드 절단) · `read_csv_any`(인코딩 되돌림) ·
#:   `external_targets`(끊긴 마운트) · `lake_connected`(「결함 0」과 「못
#:   쟀음」의 가름)). 넷을 밀어 26 이 됐다.
#: ★ **0 으로 안 간다.** 남은 것 중 여럿은 레이크·도엽·PDF 를 열어야 한다
#:   (`ngii1k.read_sheet` · `terrain.build_terrain_tiles` · `seg/report`).
#:   그래서 이 수의 뜻은 「여기까지 내려왔다」가 아니라 **「새 입출력 함수를
#:   시험 없이 들이지 않는다」**다 — 늘면 그 배치가 늘린 것이다.
SRC_IO_UNTESTED = 26

RATCHETS = {"SRC_UNTESTED": "down", "SRC_IO_UNTESTED": "down"}

#: 몸통에 이 **메서드**가 보이면 입출력이다. 파일·프레임에만 있는 이름들이다.
#:
#: ★ 2026-10-12 (DECISIONS §496). 여기 `get` 이 있었다. **`dict.get` 이다** —
#:   그 한 이름이 함수 **예순**을 입출력으로 보냈고(이 저장소는 대장 항목을
#:   `e.get("scope")` 로 읽는다) 그 예순은 「산출물로 드는 시험이 있을 수
#:   있다」는 이유로 **안 물렸다.** `naming.canonical`(개명 규칙의 정본)이
#:   거기 숨어 있었다. 같이 뺀 것 — `copy`(`dict.copy`) · `replace`
#:   (`str.replace`) · `load`·`dump`(`yaml.safe_load(글자)` 는 파일을 안 연다) ·
#:   `run`(흔한 함수 이름). 그 넷은 **모듈 이름**으로 다시 잡는다.
IO_METHODS = frozenset({
    "read_text", "write_text", "read_bytes", "write_bytes", "mkdir",
    "unlink", "rename", "iterdir", "glob", "rglob", "exists", "is_dir",
    "is_file", "stat", "touch", "read_file", "read_csv", "to_csv",
    "to_file", "check_output", "urlopen", "extractall", "namelist",
})

#: 몸통이 이 **모듈·자료형**을 들면 입출력이다. 메서드 이름보다 확실하다.
IO_MODULES = frozenset({
    "subprocess", "requests", "shutil", "zipfile", "sqlite3", "os",
    "tempfile", "ZipFile", "TemporaryDirectory", "NamedTemporaryFile",
    "urlopen", "environ", "getenv", "fiona", "rasterio",
})

#: 그냥 부르면 파일이 열리는 것.
IO_CALLS = frozenset({"open"})

IO_NAMES = IO_METHODS | IO_MODULES | IO_CALLS

#: 몸통에 이 이름이 보이면 **진입점**이다.
CLI_NAMES = frozenset({"ArgumentParser", "argv", "SystemExit", "add_argument"})


def ratchet_values() -> dict[str, int]:
    """실측. **판정은 `check()` 소관**이다."""
    return {"SRC_UNTESTED": sum(len(v) for v in untested().values()),
            "SRC_IO_UNTESTED": tally().get("입출력", [0, 0])[1]}


def _names(node: ast.AST) -> set[str]:
    """몸통이 부르는/만지는 이름들. 호출·속성·단순이름을 다 모은다."""
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def klass(name: str, node: ast.AST) -> str:
    """한 함수의 부류. **진입점 → 입출력 → 순수** 순으로 가른다."""
    if name == "main" or name.startswith("cmd_") or name.endswith("_cli"):
        return "진입점"
    seen = _names(node)
    if seen & CLI_NAMES:
        return "진입점"
    if seen & IO_NAMES:
        return "입출력"
    return "순수"


def functions(src: Path | None = None) -> dict[str, list[tuple[str, str]]]:
    """모듈 → [(함수 이름, 부류)]. **최상위 · 밑줄 아닌 것**만."""
    s = src if src is not None else SRC
    out: dict[str, list[tuple[str, str]]] = {}
    for p in sorted(s.rglob("*.py")):
        if p.name == "__init__.py":
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rows = [(n.name, klass(n.name, n)) for n in tree.body
                if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                and not n.name.startswith("_")]
        if rows:
            out[p.relative_to(s).as_posix()] = rows
    return out


def test_text(tests: Path | None = None) -> str:
    """시험 묶음을 한 글자로 이어 붙인다. 이름을 찾을 건초더미다."""
    d = tests if tests is not None else TESTS
    if not d.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(d.rglob("*.py")))


def tally(src: Path | None = None, tests: Path | None = None) -> dict[str, list[int]]:
    """부류 → [전체 수, 시험이 이름을 안 부르는 수]."""
    hay = test_text(tests)
    out: dict[str, list[int]] = {}
    for rows in functions(src).values():
        for name, k in rows:
            row = out.setdefault(k, [0, 0])
            row[0] += 1
            if not re.search(rf"\b{re.escape(name)}\b", hay):
                row[1] += 1
    return out


def untested(src: Path | None = None, tests: Path | None = None) -> dict[str, list[str]]:
    """**순수 함수**만. 모듈 → 시험이 이름을 안 부르는 함수 이름들."""
    hay = test_text(tests)
    out: dict[str, list[str]] = {}
    for rel, rows in functions(src).items():
        miss = [n for n, k in rows
                if k == "순수" and not re.search(rf"\b{re.escape(n)}\b", hay)]
        if miss:
            out[rel] = miss
    return out


def check(show: bool = False) -> list[str]:
    bad: list[str] = []
    if not SRC.is_dir():
        return ["`src/firelane` 이 없다 — 작업트리가 얕다"]
    t = tally()
    for kind in ("순수", "입출력", "진입점"):
        n, gap = t.get(kind, [0, 0])
        mark = {"순수": "  ← 문다", "입출력": "  ← 늘면 운다"}.get(kind, "")
        print(f"  {kind:<4} 공개 최상위 {n:>3} · 시험이 이름을 안 부르는 것 {gap:>3}{mark}")
    miss = untested()
    now = sum(len(v) for v in miss.values())
    print(f"안 드는 순수 함수 {now} · 래칫 {SRC_UNTESTED}"
          f"  |  입출력 {t.get('입출력', [0, 0])[1]} · 래칫 {SRC_IO_UNTESTED}")
    if show:
        for rel, names in sorted(miss.items()):
            print(f"    {rel:<24} {len(names):>2}  {' '.join(names)}")

    # ★ 빈 그물 — 분모가 0 이면 이 관문은 아무것도 안 든다
    if t.get("순수", [0, 0])[0] == 0:
        bad.append("순수 함수를 하나도 못 찾았다 — 훑기가 비었다(경로나 부류)")
    if not test_text():
        bad.append("시험 묶음이 비었다 — **모든 함수가 안 드는 것으로 세어진다**")

    io_now = t.get("입출력", [0, 0])[1]
    if io_now > SRC_IO_UNTESTED:
        bad.append(f"시험이 안 드는 입출력 함수가 {io_now} 로 늘었다 "
                   f"(래칫 {SRC_IO_UNTESTED})\n"
                   "       새 입출력 함수에도 **이름으로 부르는** 시험을 달아라 —"
                   " 임시 폴더로 미는 길이 거의 늘 있다")
    elif io_now < SRC_IO_UNTESTED:
        bad.append(f"안 드는 입출력 함수가 {io_now} 로 줄었다 — "
                   "`uv run python tools/ratchet.py --write` 로 조여라")

    if now > SRC_UNTESTED:
        bad.append(f"시험이 안 드는 순수 함수가 {now} 로 늘었다 (래칫 {SRC_UNTESTED})\n"
                   "       새 순수 함수에는 그것을 **이름으로 부르는** 시험을 같이 달아라")
    elif now < SRC_UNTESTED:
        bad.append(f"안 드는 순수 함수가 {now} 로 줄었다 — "
                   "`uv run python tools/ratchet.py --write` 로 조여라")
    return bad


def selftest() -> int:
    """★ **양방향.** 합성 트리로 민다 — 실물 수에 기대면 실물이 바뀔 때 운다."""
    import tempfile
    fails = []

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        src, tst = root / "firelane", root / "tests"
        src.mkdir()
        tst.mkdir()
        (src / "a.py").write_text(
            "def 든다(x):\n    return x\n\n\n"
            "def 안든다(x):\n    return x\n\n\n"
            "def _숨은것(x):\n    return x\n\n\n"
            "def 파일읽는다(p):\n    return p.read_text()\n\n\n"
            "def cmd_무엇(a):\n    return a\n\n\n"
            "def 대장을읽는다(e):\n    return e.get('scope')\n\n\n"
            "def 셸을돈다(cmd):\n    import subprocess\n"
            "    return subprocess.run(cmd)\n\n\n"
            "def 글자를푼다(t):\n    import yaml\n"
            "    return yaml.safe_load(t)\n\n\n"
            "def 진입(a):\n    import argparse\n"
            "    return argparse.ArgumentParser()\n\n\n"
            "class 자료형:\n    def 메서드(self):\n        return 1\n",
            encoding="utf-8")
        (src / "__init__.py").write_text("def 안세는것():\n    return 1\n",
                                         encoding="utf-8")
        (tst / "test_a.py").write_text("from firelane.a import 든다\n"
                                       "def test_x():\n    assert 든다(1) == 1\n",
                                       encoding="utf-8")

        miss = untested(src, tst)
        got = sorted(n for v in miss.values() for n in v)
        if got != ["글자를푼다", "대장을읽는다", "안든다"]:
            fails.append(f"안 드는 순수 함수를 틀리게 센다 — {got}\n"
                         "       기대: 안든다 · 대장을읽는다 · 글자를푼다")
        # ★ 음성 — 이름을 부르는 것은 **안** 세어야 한다
        if "든다" in got:
            fails.append("시험이 이름을 부르는 함수를 안 드는 것으로 센다")

        t = tally(src, tst)
        if t.get("순수", [0, 0]) != [4, 3]:
            fails.append(f"순수 분모를 틀리게 센다 — {t.get('순수')} (기대 [4, 3])\n"
                         "       `든다` · `안든다` · **`대장을읽는다`** ·"
                         " **`글자를푼다`**")
        if t.get("입출력", [0, 0])[0] != 2:
            fails.append(f"입출력을 틀리게 가른다 — {t.get('입출력')} (기대 [2, 2])\n"
                         "       `파일읽는다`(read_text) · `셸을돈다`(subprocess)")
        if t.get("진입점", [0, 0])[0] != 2:
            fails.append(f"진입점을 틀리게 가른다 — {t.get('진입점')} (기대 2건)\n"
                         "       `cmd_무엇`(이름) · `진입`(argparse 를 든다)")
        # ★ §496 — `dict.get` 은 입출력이 아니다. 한 이름이 예순을 숨겼다
        got = sorted(n for v in miss.values() for n in v)
        for n in ("대장을읽는다", "글자를푼다"):
            if n not in got:
                fails.append(f"{n!r} 를 입출력으로 가른다 — `dict.get` ·"
                             " `yaml.safe_load(글자)` 는 파일을 안 연다(§496)")
        if "셸을돈다" in got:
            fails.append("`subprocess` 를 드는 함수를 순수로 센다")
        # ★ 두 래칫이 **다른 수**를 재는가. 한 실측을 둘에 적으면 둘 다 죽는다
        vals = {"SRC_UNTESTED": sum(len(v) for v in untested(src, tst).values()),
                "SRC_IO_UNTESTED": t.get("입출력", [0, 0])[1]}
        if vals != {"SRC_UNTESTED": 3, "SRC_IO_UNTESTED": 2}:
            fails.append(f"두 래칫이 같은 수를 잰다 — {vals}\n"
                         "       기대: 순수 3(안든다·대장을읽는다·글자를푼다) ·"
                         " 입출력 2(파일읽는다·셸을돈다)")
        # ★ 밑줄·메서드·`__init__` 은 분모 밖이다
        allnames = {n for rows in functions(src).values() for n, _ in rows}
        for n in ("_숨은것", "메서드", "안세는것"):
            if n in allnames:
                fails.append(f"분모에 {n!r} 가 들어왔다 — 밑줄·메서드·__init__ 은 밖이다")

        # ★ 빈 그물 — 시험 묶음이 비면 **전부** 안 드는 것이 되어야 한다
        empty = untested(src, root / "없는곳")
        if sorted(n for v in empty.values() for n in v) != [
                "글자를푼다", "대장을읽는다", "든다", "안든다"]:
            fails.append("시험이 없는데도 드는 것이 있다고 센다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 11")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="판정 폐포에서 시험이 안 드는 순수 함수")
    ap.add_argument("--list", action="store_true", help="안 드는 것을 모듈별로 본다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    bad = check(a.list)
    if bad:
        print("\n✗ 판정 시험 분모")
        for b in bad:
            print(f"   {b}")
        return 1
    print("✓ 판정 시험 분모")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

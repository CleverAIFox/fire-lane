#!/usr/bin/env python3
"""
test_cli_surface.py — **모든 CLI 가 모르는 인자를 거절하는가.**

── 왜 생겼나 (2026-09-28 실측 · DECISIONS §283-2) ──────────────
저장소의 CLI 전부에 모르는 깃발을 하나 줘 보았다. **25개가 결함이었다** —

    종료 0, 아무 말 없이 일을 했다      20   ★ 제일 나쁘다
    파이썬 역추적을 토했다                4
    모르는 깃발을 받고도 25초 넘게 돌았다   2   ★ 잘못 불러도 돈다

★ 왜 이것이 「무음 통과」인가. `verify.sh` 가 `--check` 를 `--chek` 으로
  적어도 **초록이었다.** 도구는 기본 동작을 하고 부른 쪽은 「그 검사가
  돌았다」고 믿는다. 이 저장소가 세어 온 1족의 교과서적 형태다.

★ 이 결함을 찾은 첫 판은 `grep -l '__name__ == "__main__"'` 로 도구를
  모았고 **`firelane/cli.py` 의 머리말에 적힌 예시 코드를 도구로 셌다.**
  글이 코드로 세어지면 그물에 구멍이 난다 — 여기서는 AST 로 모은다.

IN    tools/*.py · src/firelane/**/*.py
OUT   없음 (검사)
PARAM WORKERS · TIMEOUT
밖    **인자를 옳게 처리하는가는 안 본다.** `--base dev` 가 실제로 dev 를
      보는지는 그 도구의 시험 소관이다. 여기가 드는 것은 「모르는 것을
      받으면 일을 안 하고 거절하는가」 하나다.
      **도구가 하는 일이 옳은가도 안 본다.**
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 이 깃발을 받는 도구는 없어야 한다. 받으면 그 도구가 틀렸다.
UNKNOWN = "--이런깃발은없다"
TIMEOUT = 20          # 초. 이보다 오래 돌면 **일을 시작한 것**이다.
WORKERS = 8           # 자식 프로세스는 부모 입장에서 I/O 다


def _is_cli(p: Path) -> bool:
    """모듈 맨 위에 `if __name__ == "__main__":` 이 있나. **AST 로 본다.**"""
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in tree.body:                      # 맨 위만 — 함수 안은 아니다
        if not isinstance(node, ast.If):
            continue
        t = node.test
        if (isinstance(t, ast.Compare)
                and isinstance(t.left, ast.Name) and t.left.id == "__name__"
                and any(isinstance(c, ast.Constant) and c.value == "__main__"
                        for c in t.comparators)):
            return True
    return False


def clis() -> list[Path]:
    out = [p for p in sorted([*(ROOT / "tools").glob("*.py"),
                              *(ROOT / "src" / "firelane").rglob("*.py")])
           if "__pycache__" not in p.parts and _is_cli(p)]
    return out


def _probe(p: Path) -> tuple[Path, int, str]:
    """모르는 깃발을 주고 부른다. (도구, 종료코드, 나온 글)"""
    try:
        r = subprocess.run([sys.executable, str(p), UNKNOWN], check=False,
                           capture_output=True, text=True, timeout=TIMEOUT,
                           cwd=ROOT)
    except subprocess.TimeoutExpired:
        return p, 124, "★ 시간 초과 — 모르는 깃발을 받고도 일을 시작했다"
    return p, r.returncode, r.stdout + r.stderr


def _sweep() -> list[tuple[Path, int, str]]:
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        return list(ex.map(_probe, clis()))


def _verdict(rc: int, out: str) -> str:
    """결함이면 이유, 아니면 빈 글."""
    if rc == 124:
        return "모르는 깃발을 받고도 일을 시작했다 (시간 초과)"
    if "Traceback (most recent call last)" in out:
        return "파이썬 역추적을 토했다 — 사용법을 내야 한다"
    if rc == 0:
        return "모르는 깃발을 조용히 무시하고 일을 했다"
    return ""


# ── ① 전수 ─────────────────────────────────────────────────────
def test_every_cli_refuses_an_unknown_flag():
    bad = [(p.relative_to(ROOT).as_posix(), why)
           for p, rc, out in _sweep() if (why := _verdict(rc, out))]
    assert not bad, (
        f"모르는 깃발을 안 거절하는 도구 {len(bad)}개\n  "
        + "\n  ".join(f"{f}  ← {w}" for f, w in bad)
        + "\n\n  인자를 안 받는 도구는 `from firelane.cli import no_args` 뒤"
          "\n  `no_args(__doc__)` 한 줄. 받는 도구는 `argparse` 를 쓴다.")


# ── ② 그물이 비지 않았나 ────────────────────────────────────────
def test_the_collector_finds_the_tools():
    """AST 수집이 죽으면 0개가 전부 통과한다."""
    found = clis()
    assert len(found) > 80, f"CLI 를 {len(found)}개만 찾았다 — 수집이 죽었다"


def test_the_collector_does_not_read_prose_as_code():
    """★ 첫 판은 `firelane/cli.py` 머리말의 **예시 코드**를 도구로 셌다.

    `cli.py` 는 `if __name__ == "__main__":` 이라는 글자를 머리말에 담고 있고
    실제 `__main__` 분기는 없다. 글을 코드로 세면 그물에 구멍이 난다.
    """
    guard = ROOT / "src" / "firelane" / "cli.py"
    assert 'if __name__ == "__main__":' in guard.read_text(encoding="utf-8"), \
        "이 시험의 전제가 사라졌다 — cli.py 머리말의 예시가 없어졌다"
    assert not _is_cli(guard), "머리말의 예시 코드를 도구로 셌다"


def test_the_probe_catches_a_planted_defect(tmp_path):
    """★ 빈 그물 자기검사. 일부러 나쁜 도구를 심고 잡히나 본다."""
    planted = {
        "조용히_일함.py": "import sys\nprint('일을 했다')\n"
                       "if __name__ == '__main__':\n    pass\n",
        "역추적.py": "import sys\n"
                  "if __name__ == '__main__':\n    raise ValueError(sys.argv[1])\n",
    }
    for name, src in planted.items():
        p = tmp_path / name
        p.write_text(src, encoding="utf-8")
        _p, rc, out = _probe(p)
        assert _verdict(rc, out), f"심은 결함 {name} 을 못 잡았다 (종료 {rc})"


# ── ③ 머리말이 약속한 깃발을 실제로 받는가 ──────────────────────
#: 깃발 꼴. `<!--voice-ok-->` 같은 HTML 주석을 깃발로 세면 오탐이 난다 —
#: 첫 판이 그렇게 세어 8개를 헛되게 올렸다.
FLAG = re.compile(r"(?<![\w<!-])--[a-z][a-z0-9-]{0,23}[a-z0-9](?!-)")
#: argparse 가 하위명령을 `{lock,check,rehash}` 꼴로 낸다.
SUBS = re.compile(r"\{([a-z][a-z0-9_,-]+)\}")


def _run(p: Path, *args: str) -> str:
    try:
        r = subprocess.run([sys.executable, str(p), *args], check=False,
                           capture_output=True, text=True, timeout=TIMEOUT,
                           cwd=ROOT)
    except subprocess.TimeoutExpired:
        return ""
    return r.stdout + r.stderr


def _promised(p: Path) -> set[str]:
    """머리말에서 **이 도구를 부르는 줄**에 적힌 깃발.

    남의 도구를 설명하며 언급한 깃발은 약속이 아니다 — `golden.py` 머리말의
    `pipeline --only segments` 가 그렇다.
    """
    doc = ast.get_docstring(ast.parse(p.read_text(encoding="utf-8"))) or ""
    rel = (p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.name)
    keys = (rel, p.name, rel.removeprefix("src/").removesuffix(".py").replace("/", "."))
    want: set[str] = set()
    for line in doc.splitlines():
        # ★ 이름이 같은 줄에 있는 것으로는 부족하다. `golden.py` 머리말의
        #   `pipeline --only segments → golden.py check` 는 `--only` 가
        #   **남의 명령**이다. 깃발은 이 도구 이름 **뒤**에 와야 약속이다.
        at = max((line.rfind(k) for k in keys if k in line), default=-1)
        if at < 0:
            continue
        want |= {m.group() for m in FLAG.finditer(line) if m.start() > at}
    return want - {"--help"}


def _accepted(p: Path) -> set[str]:
    """`--help` 이 내는 깃발. **하위명령의 깃발까지 센다.**

    `deliver.py pack --out` 처럼 하위파서에 달린 깃발은 맨 위 `--help` 에
    안 나온다. 맨 위만 보면 오탐이 난다.
    """
    top = _run(p, "--help")
    have = set(FLAG.findall(top))
    for group in SUBS.findall(top):
        for sub in group.split(","):
            have |= set(FLAG.findall(_run(p, sub, "--help")))
    return have


def test_every_documented_flag_actually_exists():
    """★ 머리말이 약속한 깃발이 실제로 있나.

    2026-09-28. `inventory.py` 를 argparse 로 옮기면서 **머리말에 적혀 있는
    `--dry` 를 빠뜨렸다.** 도구는 `NameError` 로 죽는데 「모르는 깃발을
    거절하나」 시험은 초록이었다 — 그 시험은 거절 경로만 본다. 약속과 실물을
    대조하는 것은 별개의 그물이어야 한다(§283-5).
    """
    bad = []
    for p in clis():
        if not (want := _promised(p)):
            continue
        if miss := sorted(want - _accepted(p)):
            bad.append((p.relative_to(ROOT).as_posix(), miss))
    assert not bad, (
        f"머리말이 약속한 깃발을 안 받는 도구 {len(bad)}개\n  "
        + "\n  ".join(f"{f}  ← {m}" for f, m in bad)
        + "\n\n  머리말을 고치거나 깃발을 만들어라. 둘 중 하나는 낡았다.")


def test_the_promise_check_is_not_an_empty_net(tmp_path):
    """★ 0건은 「없다」와 「못 본다」가 같은 얼굴이다. 둘을 가른다."""
    total = sum(len(_promised(p)) for p in clis())
    assert total > 40, (
        f"머리말에서 약속을 {total}개만 읽었다 — 읽기가 죽었다. "
        "0건 통과는 통과가 아니다")

    # 일부러 「약속만 하는 도구」를 심는다. 못 잡으면 그물이 비었다.
    planted = tmp_path / "promiser.py"
    planted.write_text(
        '"""promiser.py — 시험용.\n\n    python promiser.py --ghost\n"""\n'
        "import argparse\n"
        'if __name__ == "__main__":\n'
        "    argparse.ArgumentParser().parse_args()\n", encoding="utf-8")
    assert _promised(planted) == {"--ghost"}, "심은 약속을 못 읽었다"
    assert "--ghost" not in _accepted(planted), "실물 깃발을 못 읽었다"


def test_help_works_without_a_lake():
    """★ 「이 도구가 무엇이냐」는 레이크 없이 물을 수 있어야 한다.

    `acquire` · `ledger_schema` · `migrate_names` 는 `require_lake()` 를
    `parse_args()` **앞**에 두어, 레이크가 없으면 `--help` 조차 종료 2 였다.
    관문은 일을 막는 것이고 묻는 것을 막는 것이 아니다(§283-4).
    """
    bad = [p.relative_to(ROOT).as_posix() for p in clis()
           if not FLAG.search(_run(p, "--help")) and _promised(p)]
    assert not bad, f"깃발을 약속하는데 `--help` 가 그것을 못 내는 도구 — {bad}"


# ── ④ datalog 명령 표 ──────────────────────────────────────────
def test_datalog_command_table_matches_the_functions():
    """★ 표에 적은 인자 개수와 함수의 인자 개수가 같은가.

    예전 분기부는 `{...}[cmd](*rest)` 였다. 인자 수가 틀리면 `TypeError`
    역추적이 났고, **인자가 뭔지 아무도 모르니 `verify.sh` 가 배선을
    못 했다**(§283-1).
    """
    import inspect

    from firelane import datalog
    for name, (fn, args) in datalog.COMMANDS.items():
        sig = inspect.signature(fn)
        need = [p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty]
        assert len(need) == len(args), (
            f"{name}: 표는 인자 {len(args)}개({', '.join(args) or '없음'}) 라는데 "
            f"{fn.__name__}() 는 {len(need)}개를 요구한다")


def test_datalog_documents_every_command_it_accepts():
    """머리말에 안 적힌 명령은 아무도 못 찾는다."""
    from firelane import datalog
    doc = datalog.__doc__ or ""
    missing = [n for n in datalog.COMMANDS if f"datalog {n}" not in doc]
    assert not missing, f"머리말에 없는 명령 — {missing}"


def test_datalog_rejects_bad_calls_without_a_traceback():
    """인자 없이 · 모르는 명령으로 불러도 사용법과 종료 2 가 나오나."""
    from firelane import datalog
    for argv in ([], ["impact"], ["없는명령"], ["graph", "남는인자"]):
        assert datalog.dispatch(argv) == datalog.USAGE_EXIT, \
            f"{argv} 를 거절하지 않았다"

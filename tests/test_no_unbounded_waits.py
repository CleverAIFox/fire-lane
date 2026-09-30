#!/usr/bin/env python3
"""
test_no_unbounded_waits.py — **영원히 매달릴 수 있는 시험이 몇 개인가.** 래칫.

── 왜 생겼나 (2026-09-28 실측 · DECISIONS §284-5) ──────────────
`tests/test_k2.py` 의 `_ask_in_pty()` 가 마지막에 `os.waitpid(pid, 0)` 을
했다. **시한이 없다.** 가상 터미널 자식 bash 가 안 죽으면 영원히 기다린다.

실제로 났다 —

    merge_batch --release 의 A-0    pytest 1291초(21분31초).  정상 3분33초
    같은 기계에 남아 있던 찌꺼기     ask.sh 3개 · 1시간 11분째
    그 옆의 또 다른 유령            uv run pytest --cov · 1시간 13분째

★ **전에도 났고 아무도 몰랐다.** 한 시간 넘은 고아가 둘이나 살아 있었다.
  한 번 호출이 `bash` 를 셋 남기므로 우두머리만 죽이면 나머지가 쌓인다.

★ 왜 이것이 보통 빨강보다 나쁜가. **빨강을 무한 대기로 바꾼다.** 무한
  대기는 결국 사람이 죽이고, 사람이 죽이면 무엇이 틀렸는지 영영 모른다.
  오늘 릴리즈가 봉인 없이 나간 이유가 그것이다.

── 그물이 둘이다 ──────────────────────────────────────────────
    ① 전역 시한   `pyproject.toml` 의 `timeout = 300`. **어떤 이유로**
                  멈추든 스택 추적이 붙은 빨강으로 떨어진다. 자식뿐 아니라
                  무한 루프 · 잠금 교착까지 같은 그물이 잡는다.
    ② 이 래칫     그래도 **자식은 따로 센다.** 시한에 걸려 시험이 죽어도
                  고아 자식은 남아 다음 실행까지 쌓인다(실측 — 전역 시한이
                  문 뒤에도 `sleep` 자식이 파이프를 잡고 있었다).
                  자식을 기다리는 자리는 제 시한을 갖는 것이 맞다.

IN    tests/**/*.py
OUT   없음 (검사)
PARAM RATCHET
밖    **시한 값이 적절한가는 안 본다.** `timeout=1` 이 그 시험에 충분한지는
      그 시험이 안다. 여기가 드는 것은 「시한이 있는가」 하나다.
      `src/` · `tools/` 는 안 본다 — 도구가 사람을 기다리는 것은 정상이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 자식을 기다리는 호출 → 사람이 읽는 이름
BLOCKING = {
    "run": "subprocess.run", "check_output": "subprocess.check_output",
    "check_call": "subprocess.check_call", "call": "subprocess.call",
    "communicate": "Popen.communicate", "wait": "Popen.wait",
    "waitpid": "os.waitpid", "system": "os.system",
}

#: 2026-09-28 실측 **46**. 줄기만 한다 — 늘면 울고, 줄여도 기록을 안 내리면
#: 운다(느슨해진 래칫은 초록으로 위장한다. `suppress.py` 와 같은 사유).
#:
#: ★ 첫 판은 54 였다. **여덟이 오탐**이었다 — 지역 도우미 `def run(...)` 을
#:   `subprocess.run` 으로 셌다. 판별식을 고쳐 46 이 됐다. 큰 수가 더
#:   그럴듯해 보이지만 **틀린 수는 래칫으로 못 쓴다** — 오탐이 섞인 래칫은
#:   고쳐도 안 줄고, 안 줄면 사람이 그 래칫을 안 믿는다.
RATCHET = 45


def unbounded(path: Path) -> list[tuple[int, str]]:
    """그 파일에서 **시한 없이** 자식을 기다리는 자리. (줄, 이름)"""
    out: list[tuple[int, str]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return out
    # ★ 맨이름 호출은 **그 모듈이 실제로 그 이름을 import 했을 때만** 센다.
    #   `def run(a): ...` 같은 지역 도우미를 `subprocess.run` 으로 세면
    #   오탐이 난다 — 첫 판이 `test_batch_tools` 의 지역 `run()` 둘을
    #   그렇게 세어 래칫을 54 → 56 으로 올렸다(§285-5).
    imported = {a.asname or a.name
                for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                and n.module in ("subprocess", "os") for a in n.names}
    # ★ 두 번째 오탐 물결(2026-09-30). `RT.run(write=False)` 여섯 개를
    #   `subprocess.run` 으로 셌다 — 점 뒤의 이름만 보고 **받는 쪽을 안 봤다.**
    #   첫 물결(맨이름 `def run`)과 **같은 결함이고, 같은 고침을 점 있는 쪽에만
    #   안 한 것**이다. 그래서 이제 `run`·`call`·`check_*`·`system`·`waitpid` 는
    #   **실제로 import 한 모듈 이름을 받는 쪽으로 가진 호출만** 센다.
    #   `communicate`·`wait` 는 그대로 받는 쪽을 안 본다 — `Popen` 을 담은
    #   변수 이름은 아무거나일 수 있고, 그 둘은 다른 데 거의 안 쓰인다.
    mods = {a.asname or a.name for n in ast.walk(tree)
            if isinstance(n, ast.Import) for a in n.names
            if a.name in ("subprocess", "os")}
    ANY_RECEIVER = ("communicate", "wait")
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute):
            name = f.attr
            if name not in ANY_RECEIVER and not (
                    isinstance(f.value, ast.Name) and f.value.id in mods):
                continue        # 남의 `.run()` 이다 — 자식을 안 낳는다
        elif isinstance(f, ast.Name) and f.id in imported:
            name = f.id
        else:
            continue
        if name not in BLOCKING:
            continue
        if name == "system":
            ok = False                      # 시한을 줄 수가 없다
        elif name == "waitpid":
            # `os.waitpid(pid, 0)` 이 무한 대기. `WNOHANG` 이면 안 매달린다.
            ok = (len(n.args) > 1
                  and not (isinstance(n.args[1], ast.Constant)
                           and n.args[1].value == 0))
        else:
            ok = "timeout" in {k.arg for k in n.keywords}
        if not ok:
            out.append((n.lineno, BLOCKING[name]))
    return out


def _files() -> list[Path]:
    return [p for p in sorted((ROOT / "tests").rglob("*.py"))
            if "__pycache__" not in p.parts]


def tally() -> dict[str, list[tuple[int, str]]]:
    return {p.relative_to(ROOT).as_posix(): v
            for p in _files() if (v := unbounded(p))}


def test_unbounded_waits_do_not_grow():
    t = tally()
    n = sum(len(v) for v in t.values())
    assert n <= RATCHET, (
        f"시한 없이 자식을 기다리는 자리가 {n} — 기록 {RATCHET} 보다 늘었다\n  "
        + "\n  ".join(f"{f}: {len(v)}곳 — {v[:3]}" for f, v in sorted(t.items())[:8])
        + "\n\n  `subprocess.run(..., timeout=N)` · `Popen.wait(timeout=N)` ·"
          "\n  `os.waitpid(pid, os.WNOHANG)` 를 써라. 시한 없는 기다림은"
          "\n  빨강을 무한 대기로 바꾼다.")
    assert n >= RATCHET, (
        f"시한 없이 기다리는 자리가 {n} 으로 줄었다 — "
        f"{__file__} 의 RATCHET 을 {n} 으로 조여라")


def test_the_pty_helper_has_a_deadline():
    """★ 오늘 실제로 멈춘 그 자리. 되돌아오면 여기서 운다.

    ★ 첫 판은 글자로 봤다 — `"os.waitpid(pid, 0)" not in src`. 그러면
      **그 사고를 설명하는 주석이 사고로 세어진다.** 같은 날 세 번째였다
      (`suppress` 머리말의 「noqa」 · DECISIONS 의 「voice-ok」 표기 ·
      이것). 글자 검사는 글을 코드로 센다. **AST 로 본다**(§283-3).
    """
    k2 = ROOT / "tests" / "test_k2.py"
    bad = [ln for ln, name in unbounded(k2) if name == "os.waitpid"]
    assert not bad, (
        f"`test_k2` 가 다시 시한 없이 자식을 기다린다 — 줄 {bad}. "
        "2026-09-28 에 21분31초 멈춘 자리다")
    assert "_reap(" in k2.read_text(encoding="utf-8"), \
        "자식을 거두는 `_reap` 이 사라졌다"


def test_the_global_deadline_is_declared():
    """★ ①번 그물이 꺼지면 이 래칫만으로는 무한 루프를 못 잡는다."""
    t = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "pytest-timeout" in t, "전역 시한 도구가 의존성에서 빠졌다"
    assert "\ntimeout = " in t, "`[tool.pytest.ini_options]` 에 전역 시한이 없다"


def test_the_probe_is_not_an_empty_net(tmp_path):
    """★ 0건과 못 봄을 가른다. 일부러 나쁜 꼴을 심는다."""
    p = tmp_path / "test_심은것.py"
    p.write_text(
        "import os, subprocess\n"
        "def run(x):\n"                               # ★ 지역 도우미다
        "    return x\n"
        "def test_a():\n"
        "    subprocess.run(['true'])\n"              # 시한 없음
        "def test_b():\n"
        "    subprocess.run(['true'], timeout=5)\n"   # 시한 있음
        "def test_c():\n"
        "    os.waitpid(1, 0)\n"                      # 무한 대기
        "def test_d():\n"
        "    os.waitpid(1, os.WNOHANG)\n"             # 안 매달림
        "def test_e():\n"
        "    run('지역 함수다')\n",                     # ★ 세면 오탐
        encoding="utf-8")
    got = [name for _ln, name in unbounded(p)]
    assert got == ["subprocess.run", "os.waitpid"], (
        f"판별식이 실물과 갈렸다 — {got}")

    # ★ import 한 맨이름은 센다. 안 세면 이번엔 미탐이다.
    q = tmp_path / "test_맨이름.py"
    q.write_text("from subprocess import run\n"
                 "def test_a():\n    run(['true'])\n", encoding="utf-8")
    assert [n for _l, n in unbounded(q)] == ["subprocess.run"], \
        "`from subprocess import run` 을 놓쳤다"

    # ★ 점 있는 쪽의 오탐(2026-09-30). 남의 `.run()` 은 자식을 안 낳는다.
    #   같이 심는다 — `Popen` 변수의 `.communicate()` 는 **받는 쪽을 몰라도**
    #   세야 한다. 하나만 심으면 고침이 한쪽으로 기운다.
    r = tmp_path / "test_받는쪽.py"
    r.write_text(
        "import subprocess\n"
        "import ratchet as RT\n"
        "def test_a():\n"
        "    RT.run(write=False)\n"                    # ★ 세면 오탐
        "def test_b():\n"
        "    self.client.call('x')\n"                  # ★ 세면 오탐
        "def test_c():\n"
        "    p = subprocess.Popen(['true'])\n"
        "    p.communicate()\n",                       # 받는 쪽을 몰라도 센다
        encoding="utf-8")
    assert [n for _l, n in unbounded(r)] == ["Popen.communicate"], (
        f"받는 쪽을 안 본다 — {[n for _l, n in unbounded(r)]}")

#!/usr/bin/env python3
"""
test_selftests_are_run.py — **선언된 자기검사가 전부 도는가.**

── 왜 생겼나 (2026-09-28 실측 · DECISIONS §286) ────────────────
`--selftest` 를 선언한 도구 26개 중 **16개를 아무도 안 불렀다.**
`docseal` · `gate_parity` · `tonecheck` · `suppress` · `argcheck` 가 그 안에
있었다 — 전부 이 저장소의 주요 강제자다.

★ 이것이 §285 보다 한 겹 깊다. 거기서는 **검사기**가 안 불렸다. 여기서는
  **검사기가 살아 있는지 보는 것**이 안 불린다. `--selftest` 가 존재하는
  이유는 하나다 — 빈 그물이 초록을 내는 것을 잡는 것. 그것을 안 돌리면
  그물이 빈 날 아무도 모른다.

★ 처음 전부 돌린 날 바로 빨강 하나가 나왔다. `gate_parity --selftest` 가
  배치 E 에서(§279-4) `navi:lint` 를 넣은 날부터 죽어 있었다 — 자기검사가
  제 안에 **표본표를 따로** 들고 있었고 그 표를 안 고쳤다.

IN    tools/selftests.py
OUT   없음 (검사)
PARAM 없음
밖    **자기검사를 여기서 돌리지 않는다.** 26개를 pytest 안에서 돌리면
      `pytest` 가 제 안에서 `pytest` 를 부르는 자리가 생긴다. 실행은
      `verify.sh` · CI 의 「자기검사 전수」 단계가 한다. 여기가 드는 것은
      **그 단계가 배선돼 있는가**와 **수집이 비지 않았는가** 둘이다.
"""
from __future__ import annotations

from pathlib import Path

# ★ `sys.path` 를 건드리지 않는다. `pyproject.toml` 의
#   `pythonpath = ["tools", "src"]` 가 정본이고 `test_layering` 이 그것을
#   강제한다 — 시험 파일이 경로를 조작하기 시작하면 다음 시험도 따라 한다.
import gate_parity
import scopedecl
import selftests

ROOT = Path(__file__).resolve().parents[1]


def test_the_single_door_is_wired_locally_and_in_ci():
    """★ 문을 만들고 안 부르면 §286 을 한 번 더 하는 것이다."""
    v = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    assert "tools/selftests.py" in v, "`verify.sh` 가 자기검사 전수를 안 부른다"
    ci = "".join(p.read_text(encoding="utf-8")
                 for p in (ROOT / ".github" / "workflows").glob("*.yml"))
    assert "tools/selftests.py" in ci, "CI 가 자기검사 전수를 안 부른다"


def test_the_collector_finds_the_selftests():
    """0개를 모으면 「전부 초록」이 거짓말이 된다."""
    found = selftests.tools()
    assert len(found) >= 20, f"자기검사를 {len(found)}개만 찾았다 — 수집이 죽었다"


def test_no_skip_entry_is_dead():
    """건너뛴다고 적었는데 그 도구에 자기검사가 없으면 죽은 선언이다."""
    names = {p.stem for p in selftests.tools()}
    dead = [k for k in selftests.SKIP if k not in names]
    assert not dead, f"죽은 건너뜀 선언 — {dead}"


def test_every_skip_carries_a_real_reason():
    """「필요」 두 글자로 빠지는 길을 막는다 — `ci-exempt` 와 같은 설계."""
    thin = [k for k, why in selftests.SKIP.items() if len(why.strip()) < 15]
    assert not thin, f"사유가 너무 짧다 — {thin}"


def test_the_collector_reads_declarations_not_prose():
    """★ 머리말의 사용 예시를 선언으로 세면 그물에 구멍이 난다(§283-3)."""
    assert selftests.selftest() == 0


def test_the_external_samples_live_beside_their_patterns():
    """★ §286-2 가 되돌아오는 자리. 표본이 패턴과 떨어지면 또 갈린다."""
    for name, val in gate_parity.EXTERNAL.items():
        assert isinstance(val, tuple) and len(val) == 2, (
            f"`EXTERNAL[{name}]` 이 (패턴, 표본) 짝이 아니다 — "
            "표본이 다시 딴 곳으로 갔다")
        assert name in gate_parity.tokens(val[1]), (
            f"{name} 의 패턴이 제 표본을 못 잡는다")


# ── 2026-10-12 (DECISIONS §488) ────────────────────────────────────
#   §487 이 분모를 바로잡은 뒤 이 파일이 빚에 남았다. 머리말이 §283-3 을
#   인용해 **「머리말의 사용 예시를 선언으로 세면 그물에 구멍이 난다」**고
#   적는데, 그 주장을 미는 자리는 `selftests.selftest() == 0` 한 줄이었다 —
#   그 안에서 무엇을 보는지는 이 파일 밖이다. 여기서 **합성 파일로** 민다.

#: 삼중 따옴표를 **글자로 만든다** — 합성 파일에 머리말을 넣어야 하는데
#: 이 파일 안에 그 꼴을 직접 적으면 파이썬이 이 파일의 글자를 닫는다.
Q = chr(34) * 3

#: 선언한 꼴 — 호출의 인자로 `--selftest` 가 들어간다.
DECLARED = f"{Q}한 줄.{Q}\nimport argparse\n" \
    'ap = argparse.ArgumentParser()\nap.add_argument("--selftest")\n'

#: 설명만 적은 꼴 — 머리말에 글자가 있을 뿐이다.
PROSE = f"{Q}이 도구는 `--selftest` 로 재는 것이 없다. 설명만 적는다.{Q}\nX = 1\n"

#: 함수로 선 꼴 — 최상위 `def selftest(`.
FUNC = f"{Q}한 줄.{Q}\ndef selftest() -> int:\n    return 0\n"


def _tool(tmp_path: Path, body: str, name: str = "합성도구.py") -> Path:
    """`tools/` 라는 이름의 폴더 아래에 둔다 — `scopedecl` 이 부모 이름을 본다."""
    d = tmp_path / "tools"
    d.mkdir(exist_ok=True)
    q = d / name
    q.write_text(body, encoding="utf-8")
    return q


def test_a_declared_selftest_counts(tmp_path):
    """★ 양성. 선언한 것을 못 세면 「자기검사가 사라졌다」를 못 본다."""
    q = _tool(tmp_path, DECLARED)
    assert scopedecl.has_selftest(q), "깃발로 선언한 자기검사를 안 센다"
    assert selftests._has_selftest(q), "깃발로 선언한 자기검사를 안 센다(수집기)"


def test_a_selftest_function_counts(tmp_path):
    """최상위 `def selftest(` 도 **실행되는 자리**다."""
    assert scopedecl.has_selftest(_tool(tmp_path, FUNC)), \
        "함수로 선 자기검사를 안 센다"


def test_prose_in_the_docstring_does_not_count(tmp_path):
    """★ **음성.** §278-1 이 실측한 그 결함 — 머리말에 설명만 적어도 하나로
    세어졌고, 래칫을 그 수로 올렸으면 **진짜 자기검사가 하나 사라져도 안 운다.**"""
    q = _tool(tmp_path, PROSE)
    assert not scopedecl.has_selftest(q), "머리말의 글자를 선언으로 센다"
    assert not selftests._has_selftest(q), "머리말의 글자를 선언으로 센다(수집기)"


def test_a_file_outside_tools_does_not_count(tmp_path):
    """★ `scopedecl` 쪽 규율 — 시험은 자기가 곧 자기검사라 세면 수가 부푼다."""
    q = tmp_path / "test_합성.py"
    q.write_text(DECLARED, encoding="utf-8")
    assert not scopedecl.has_selftest(q), "`tools/` 밖의 파일을 센다"


def test_the_two_judges_disagree_only_where_it_is_declared():
    """★ 두 판정이 **다른 구현**이다. 어긋나는 자리는 `OUTSIDE` 가 적은
    것뿐이어야 한다 — 어긋남이 선언 밖으로 나가면 §484 의 `outside_faults`
    가 유령 항목을 내고, 그 유령은 「자기검사가 있다」는 거짓 신호다."""
    gap = {q.name for q in sorted((ROOT / "tools").glob("*.py"))
           if scopedecl.has_selftest(q) != selftests._has_selftest(q)}
    assert gap <= set(selftests.OUTSIDE), (
        f"선언에 없는 어긋남 — {sorted(gap - set(selftests.OUTSIDE))}")

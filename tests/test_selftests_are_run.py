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

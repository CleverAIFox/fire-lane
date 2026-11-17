"""tools/pushready.py ㉠ — `ratchet.py` 가 ✗ 를 내는 트리에서 `pushready` 가 초록이면 안 된다. (PLAN #254 · DECISIONS §817)

★ 2026-11-17 — `ratchet.py` 는 rc 1 인데 ㉠ 와 ㉤ 가 둘 다 초록이었다. ㉠ 는 `mutate.py` 항목을 전부 건너뛰고 ㉤ 는 장부의 낡음만 물었다.
밖    실제 `ratchet.py` 를 안 돈다(56초) — 합성 출력으로 「그 출력을 어떻게 읽는가」만 본다. 실물 실증(격리 사본 · 선언을 틀린 트리)은 DECISIONS §817 이 든다.
"""
from __future__ import annotations

from pathlib import Path

import pushready as P  # `pyproject` 의 `pythonpath` 가 tools 를 얹는다
import ratchet as R

ROOT = Path(__file__).resolve().parents[1]


def _check(out: str, rc: int = 1):
    return P.check_ratchet(ROOT, lambda argv, cwd: (rc, out))


def test_a_mutate_declaration_that_ratchet_calls_loose_is_not_green():
    out = ("래칫 92개 · 낡음 2 (조이는 쪽 0 · 느슨해진 쪽 2)\n"
           "\n  ✗ mutate.py · SURVIVORS — **느슨해지는 쪽**이다  선언 82 → 실측 83 (down)\n"
           "\n  ✗ mutate.py · UNSORTED — **느슨해지는 쪽**이다  선언 56 → 실측 57 (down)\n")
    b = _check(out)
    assert b is not None and b.key == "㉠" and "느슨해진 쪽·못 재는 것 2" in b.what
    assert any("mutate.py · SURVIVORS" in d for d in b.detail)


def test_a_loose_line_from_any_ratchet_owner_is_never_swallowed():
    """소유 도구마다 합성 `✗` 한 줄 — ㉢ 이 맡는 `docseal.py · UNSEALED` 만 ㉠ 가 안 센다."""
    names = sorted({p.name for p, _m in R.owners()})
    assert "mutate.py" in names and len(names) > 20
    for tool in names:
        line = f"래칫 1개 · 낡음 1 (조이는 쪽 0 · 느슨해진 쪽 1)\n  ✗ {tool} · FOO — **느슨해지는 쪽**이다  선언 1 → 실측 2 (down)\n"
        assert _check(line) is not None, f"{tool} 의 느슨해진 줄을 ㉠ 가 삼켰다 — CI 의 래칫 정합만 빨개진다"


def test_what_the_other_axes_own_stays_with_them():
    head = "래칫 92개 · 낡음 1 (조이는 쪽 0 · 느슨해진 쪽 1)\n"
    assert _check(head + "  ✗ docseal.py · UNSEALED — **느슨해지는 쪽**이다  선언 0 → 실측 1 (down)\n") is None     # ㉢ 몫
    assert _check(head + "  ✗ mutate.py · — — `ratchet_values()` 가 죽었다 — RuntimeError: 3개가 잰 뒤로 바뀌었다\n") is None   # 장부가 낡았다 — ㉤ 몫
    # 조이는 쪽의 `--write` 는 `mutate.py` 소스를 써서 변이 지문을 낡게 한다(㉠→㉤) — 그 변은 ㉠ 가 만들지 않는다
    assert _check("래칫 92개 · 낡음 1 (조이는 쪽 1 · 느슨해진 쪽 0)\n  · mutate.py · SURVIVORS  83 → 80  (--write 로 고친다)\n") is None

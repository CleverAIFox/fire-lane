"""`tools/pushdenom.py` — pushready ㉠ · ㉥ 가 초록일 때도 자기 분모를 말하고, 선언 밖에서 새로 걸리는 것을 문다.  (PLAN #259 · DECISIONS §835)

IN    tools/pushdenom.py · tools/pushready.py · tools/testpick.py(실물 출력 꼴 한 번) · 합성 출력
OUT   없음 (검사)
PARAM 없음
밖    실제 `ratchet.py` 를 안 돈다(분 단위) — 합성 출력으로 「그 출력에서 분모를 어떻게 읽는가」만 본다. `testpick --list` 는 0.5초라 실물 꼴을 한 번 문다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pushdenom as D
import pushready as P
import pytest
import ratchet as R
from test_pushready import GREEN, _runner

ROOT = Path(__file__).resolve().parents[1]
GREEN_RATCHET = "래칫 91개 · 낡음 0 (조이는 쪽 0 · 느슨해진 쪽 0)\n✓ 래칫이 전부 실측과 같다\n"
READS = "  바뀐 파일 3개(범위 @{{u}}..HEAD) → 닿는 시험 64개 · 예산 밖에서 더함 35개 (정적 스캔 ∪ 실측 읽기 {n}/{m}개 파일 — 장부에 없거나 낡은 시험은 **하한**)\n"
STALE_NEW = "  ⚠ 읽기 장부가 낡았다 — 새 시험 {k} · 바뀐 시험 0 · 없어진 시험 0: {names}\n    낡은 시험 새: {names}\n    낡은 시험 바뀐: \n"


def test_the_ratchet_axis_states_its_denominator_even_when_green_and_names_the_two_skip_rules() -> None:
    d = D.ratchet_denom(GREEN_RATCHET)
    assert d[0] == "㉠ 래칫 91개 중 91개를 읽었다 · 넘긴 0개 · `ratchet.py` 가 못 잰 것 0개" and len(d) == 3
    assert [k for k in D.RATCHET_SKIPS] == ["UNSEALED → ㉢", "mutate.py 의 ✗ 아닌 것 → ㉤"] and all("(0개)" in x for x in d[1:])


def test_skipped_items_are_counted_per_rule_and_subtracted_from_what_was_read() -> None:
    out = ("래칫 92개 · 낡음 3 (조이는 쪽 1 · 느슨해진 쪽 2) · 건너뜀 4\n  ✗ docseal.py · UNSEALED — **느슨해지는 쪽**이다  선언 0 → 실측 1 (down)\n"
           "  ✗ mutate.py · — — `ratchet_values()` 가 죽었다\n  · mutate.py · SURVIVORS  83 → 80  (--write 로 고친다)\n  ✗ suppress.py · SUPPRESS — **느슨해지는 쪽**이다\n")
    d = D.ratchet_denom(out)
    assert d[0] == "㉠ 래칫 92개 중 89개를 읽었다 · 넘긴 3개 · `ratchet.py` 가 못 잰 것 4개", d
    assert "(1개)" in d[1] and "(2개)" in d[2], "UNSEALED 1 · mutate 의 ✗ 아닌 것 2(— 와 ·)"


def test_an_unreadable_ratchet_summary_says_so_instead_of_a_zero() -> None:
    assert "분모를 못 읽었다" in D.ratchet_denom("Traceback\nboom\n")[0]


def test_only_the_two_declared_rules_skip_and_every_rule_has_a_reason() -> None:
    """★ 선언 밖에서 새로 걸리는 것 — 래칫 소유 도구마다 `✗` · `·` 항목이 ㉠ 에 읽힌다. 넘기는 것은 선언표의 둘뿐이다."""
    assert len(D.RATCHET_SKIPS) == 2 and all(why.strip() and len(why) > 20 for _, why in D.RATCHET_SKIPS.values())
    for tool in sorted({p.name for p, _m in R.owners()}):
        for mark in ("✗", "·"):
            for name in ("FOO", "—", "UNSEALED"):
                want = (tool == "docseal.py" and name == "UNSEALED") or (tool == "mutate.py" and (mark != "✗" or name == "—"))
                assert bool(D.skip_rule(mark, tool, name)) is want, f"{tool} {mark} {name}: 선언표 밖인데 넘겼거나 선언표인데 읽었다"


def test_taking_a_rule_off_the_table_makes_its_item_block_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """선언표가 곧 넘김이다 — 규칙을 지우면 그 항목이 ㉠ 를 막는다(조용히 넘기는 길이 표 밖에는 없다)."""
    out = "래칫 92개 · 낡음 1 (조이는 쪽 0 · 느슨해진 쪽 1)\n  ✗ docseal.py · UNSEALED — **느슨해지는 쪽**이다  선언 0 → 실측 1 (down)\n"
    assert P.check_ratchet(ROOT, lambda a, c: (1, out)) is None
    monkeypatch.setattr(D, "RATCHET_SKIPS", {k: v for k, v in D.RATCHET_SKIPS.items() if k != "UNSEALED → ㉢"})
    b = P.check_ratchet(ROOT, lambda a, c: (1, out))
    assert b is not None and b.key == "㉠"


def test_the_tests_axis_states_n_over_m_and_explains_the_gap_with_new_tests() -> None:
    assert D.tests_denom(READS.format(n=279, m=279))[0].startswith("㉥ 읽기 실측 279/279개 파일(100.0%) · 못 덮은 0개")
    out = READS.format(n=279, m=280) + STALE_NEW.format(k=1, names="test_new.py")
    assert D.reads_gap(out) == (279, 280, 0) and "새 시험으로 설명 안 되는 몫 0" in D.tests_denom(out)[0] and D.gap_block(out) is None


def test_a_gap_that_new_tests_do_not_explain_blocks_even_when_the_tests_are_green() -> None:
    """★ 장부가 못 덮은 시험이 새 시험 수보다 많다 — 낡음 경고가 못 잡는 구멍이다. 초록 · 경고 없음이어도 ㉥ 가 막는다."""
    out = READS.format(n=270, m=280) + "✓ 시험 묶음 241개 파일 · 빨강 0 · 25.0초\n"
    assert D.reads_gap(out) == (270, 280, 10)
    b = P.survey(ROOT, _runner(tests=(0, out)))
    assert [x.key for x in b] == ["㉥"] and "10개 시험을 못 덮는데 새 시험으로 설명이 안 된다" in b[0].what and any("--measure-reads" in c for c in b[0].cmds)
    partial = READS.format(n=270, m=280) + STALE_NEW.format(k=4, names="a.py b.py c.py d.py")
    assert D.reads_gap(partial) == (270, 280, 6), "새 시험 4 만 설명된다 — 남는 6 이 몫이다"


def test_an_unreadable_reads_line_says_so_and_does_not_invent_a_zero_or_block() -> None:
    assert "분모를 못 읽었다" in D.tests_denom("✓ 시험 묶음 198개 파일 · 빨강 0 · 25.0초\n")[0] and D.reads_gap("✓ 묶음\n") is None
    assert [x.key for x in P.survey(ROOT, _runner())] == [], "합성 초록(분모 줄이 없는 출력)은 종전처럼 초록이다"


def test_the_green_report_carries_both_denominators(capsys: pytest.CaptureFixture[str]) -> None:
    run = _runner(ratchet=(0, GREEN_RATCHET), tests=(0, READS.format(n=280, m=280) + "✓ 시험 묶음 241개 파일 · 빨강 0 · 25.0초\n"))
    assert P.survey(ROOT, run) == []
    txt = P.render([], D.lines())
    assert "푸시 가능" in txt and "㉠ 래칫 91개 중 91개를 읽었다" in txt and "㉥ 읽기 실측 280/280개 파일(100.0%)" in txt
    assert txt.index("㉠ 래칫") < txt.index("㉥ 읽기") and "넘기는 규칙 — UNSEALED → ㉢" in txt


def test_the_real_testpick_prints_a_reads_line_the_denominator_can_read() -> None:
    """실물 꼴 — `testpick` 가 말을 바꾸면 ㉥ 의 분모가 조용히 「못 읽었다」가 된다. 0.5초라 한 번 읽는다."""
    r = subprocess.run([sys.executable, str(ROOT / "tools/testpick.py"), *D.LIST_ARGS], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
    if r.returncode != 0:
        pytest.skip(f"환경skip(도구) — testpick 가 rc {r.returncode} 로 끝났다")
    g = D.reads_gap(r.stdout + r.stderr)
    assert g is not None and 0 < g[0] <= g[1], "testpick 가 「읽기 실측 n/M개 파일」을 안 낸다 — pushdenom 의 READS 꼴을 같이 고친다"


def test_the_ratchet_format_the_denominator_reads_is_the_one_ratchet_prints() -> None:
    src = (ROOT / "tools/ratchet.py").read_text(encoding="utf-8")
    assert 'f"래칫 {len(live)}개 · 낡음 {len(stale)}"' in src and '건너뜀 {len(skip)}' in src, "ratchet.py 의 요약줄이 바뀌었다 — pushdenom.SUMMARY 도 같이 고친다"
    assert GREEN["ratchet"][1].split("\n")[0].startswith("래칫 ") and D.SUMMARY.search(src.split("print(f")[0] + GREEN_RATCHET)

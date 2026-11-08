"""tools/tasktpl.py — 지시문 틀은 **저장소에서 읽은 것**이어야 한다.  (PLAN #204)

★ 양성 대조 — 정본 하나를 바꾸면 틀이 따라가고, 틀을 손으로 고치면 `--check` 가 운다. 사본이면 둘 다 안 운다.

밖    **틀이 지시문으로서 좋은가는 안 본다.** `docnum_check.verdicts()` · `pushready.CHECKS` · `obligations.OBLIGATIONS` 가
      옳게 세는가는 각자의 시험이 든다 — 여기는 틀이 **그것을 읽는가**만 본다.
"""
from __future__ import annotations

import tasktpl as T

VERDICTS = {"clear": 275, "needs_cv": 283, "blocked": 193, "unknown": 536, "n": 1287}


def test_the_invariants_come_from_the_verdict_source_not_from_the_template():
    a = T.render(VERDICTS)
    b = T.render({**VERDICTS, "clear": 999})
    assert "- clear 275" in a and "- clear 999" in b and "- clear 275" not in b
    assert "- 구간 1287" in a


def test_every_pushready_axis_and_obligation_and_gate_is_named(monkeypatch):
    text = T.render(VERDICTS)
    for key, _ in T.pushready.CHECKS:
        assert f"- {key} " in text
    for o in T.obligations.OBLIGATIONS:
        assert o.name in text
    for name in T.gate_names():
        assert f"- {name}" in text
    # 의무 하나를 빼면 틀에서도 빠진다 — 표를 따로 들고 있으면 남는다
    monkeypatch.setattr(T.obligations, "OBLIGATIONS", T.obligations.OBLIGATIONS[:1])
    rest = T.render(VERDICTS)
    assert T.obligations.OBLIGATIONS[0].name in rest and "머리말 「밖」" not in rest


def test_a_hand_edited_template_is_caught_by_check(tmp_path, monkeypatch):
    monkeypatch.setattr(T.docnum_check, "verdicts", lambda: dict(VERDICTS))
    p = tmp_path / "tpl.txt"
    assert T.main(["--write", str(p)]) == 0 and T.main(["--check", str(p)]) == 0
    p.write_text(p.read_text(encoding="utf-8").replace("clear 275", "clear 276"), encoding="utf-8")
    assert T.main(["--check", str(p)]) == 1                      # 손으로 고쳤다 — 운다
    assert T.main(["--check", str(tmp_path / "none.txt")]) == 1   # 없어도 운다(닫힌 쪽)


def test_a_read_first_section_that_does_not_exist_fails_closed(monkeypatch, capsys):
    monkeypatch.setattr(T, "READ_FIRST", (("docs/PLAN.md", "999-9"),))
    assert T.main([]) == 1
    assert "999-9" in capsys.readouterr().err


def test_the_real_read_first_sections_exist():
    assert T.missing_sections() == []

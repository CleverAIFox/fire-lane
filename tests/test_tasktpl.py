"""tools/tasktpl.py — 지시문 틀은 **저장소에서 읽은 것**이어야 한다.  (PLAN #204)

★ 양성 대조 — 정본 하나를 바꾸면 틀이 따라가고, 틀을 손으로 고치면 `--check` 가 운다. 사본이면 둘 다 안 운다.

밖    **틀이 지시문으로서 좋은가는 안 본다.** 금지 칸은 **정본이 하나**인지만 본다 — 금지 문장을 틀이 따로 들고 있으면 아래 시험이 운다. `docnum_check.verdicts()` · `pushready.CHECKS` · `obligations.OBLIGATIONS` 가
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


def test_the_forbidden_column_is_read_from_the_repository_canon_not_written_in_the_template(monkeypatch):
    """★ 금지 칸의 정본은 이미 코드에 있다(PLAN #204 · 사람이 정했다) — 정본에 하나 더하면 틀에 나오고 빼면 사라진다. 사본이면 그대로 남는다."""
    base = "\n".join(T.forbidden())
    for tool in T.fixable.HUMAN_FIRST:
        assert f"· {tool} " in base                                  # 사람 전용 표 전부
    monkeypatch.setitem(T.fixable.HUMAN_FIRST, "tools/zz_probe.py", "시험이 심은 사유")
    assert "tools/zz_probe.py — 시험이 심은 사유" in "\n".join(T.forbidden())
    monkeypatch.delitem(T.fixable.HUMAN_FIRST, "tools/zz_probe.py")
    monkeypatch.delitem(T.fixable.HUMAN_FIRST, next(iter(T.fixable.HUMAN_FIRST)))
    assert len(T.fixable.HUMAN_FIRST) == 10 and "· tools/golden.py " not in "\n".join(T.forbidden())


def test_the_forbidden_column_counts_ratchets_and_the_verdict_closure_from_their_owners():
    text = "\n".join(T.forbidden())
    assert f"도구 {len(T.ratchet.owners())}개" in text
    names = sorted(p.relative_to(T.ROOT / "src" / "firelane").as_posix() for p in T.shardseal.code_closure())
    assert f"모듈 {len(names)}개" in text and "ingest.py" in text
    assert "읽기만 한다" in text and "사람이 한다" in text


def test_the_template_is_not_committed_anywhere_in_the_repository():
    """★ 커밋하는 순간 그것이 사본이다(사람이 정했다). 틀을 찍은 파일이 저장소에 있으면 운다 — 첫 줄 표지로 찾는다."""
    marker = "# 작업 지시문 틀 — 이 파일은 `tools/tasktpl.py` 가 찍는다."
    hits = [p for p in T.ROOT.rglob("*") if p.is_file() and p.suffix in {".md", ".txt"} and ".venv" not in p.parts and "node_modules" not in p.parts
            and ".git" not in p.parts and marker in p.read_text(encoding="utf-8", errors="ignore")]
    assert not hits, f"틀이 저장소에 커밋돼 있다 — 사본이다: {hits}"


def _synthetic_tests(tmp_path, wall=r"ZZ\d", about="가나"):
    (tmp_path / "test_repo_numbers.py").write_text(
        f'import re\n_LIVE = ("docs/X.md",)\n_WALL = re.compile(r"{wall}")\n_ABOUT = ("{about}",)\n', encoding="utf-8")
    (tmp_path / "test_guards.py").write_text(
        'import re\n\n\ndef test_tools_declared_in_docs_exist():\n    """합성 도구 선언 규칙."""\n    re.finditer(r"foo(\\d)", "x")\n', encoding="utf-8")
    (tmp_path / "test_doc_style.py").write_text(
        'import re\nVOICE = {"가짜체": re.compile("x")}\nALLOW = "<!--v"\n', encoding="utf-8")
    return tmp_path


def test_plan_body_rules_are_read_from_their_sources_not_written_in_the_template(tmp_path, monkeypatch):
    """★ 양성 대조(PLAN #204) — 정본(시험의 상수)을 바꾸면 틀이 따라가고, 실물 값은 사라진다. 사본이면 실물 값이 그대로 남는다."""
    monkeypatch.setattr(T, "TESTS", _synthetic_tests(tmp_path))
    text = "\n".join(T.plan_rules())
    assert "ZZ\\d" in text and "「가나」" in text and "docs/X.md" in text          # 합성 값이 나온다
    assert "foo(\\d)" in text and "합성 도구 선언 규칙" in text and "가짜체" in text and "<!--v" in text
    assert "전량" not in text and "경어체" not in text and "분\\s*\\d+" not in text    # 실물 값은 안 나온다 — 따로 든 사본이 없다


def test_plan_body_rules_fail_closed_when_a_source_constant_is_renamed(tmp_path, monkeypatch):
    d = _synthetic_tests(tmp_path)
    (d / "test_repo_numbers.py").write_text('import re\n_LIVE = ("docs/X.md",)\n_ABOUT = ("가나",)\n', encoding="utf-8")   # _WALL 이 사라졌다
    monkeypatch.setattr(T, "TESTS", d)
    import pytest
    with pytest.raises(LookupError, match="_WALL"):
        T.plan_rules()


def test_plan_readers_census_counts_files_that_read_plan_and_says_it_cannot_tell_which_bite():
    tests, tools = T.plan_readers()
    assert "test_doc_style.py" in tests and "test_repo_numbers.py" in tests and "plan_renumber.py" in tools
    assert len(tests) == sum("PLAN.md" in p.read_text(encoding="utf-8", errors="ignore") for p in T.TESTS.glob("*.py"))
    out = "\n".join(T.plan_rules())
    assert f"시험 {len(tests)}개" in out and "도구가 못 가린다" in out


def test_the_real_plan_rules_name_all_six_known_bites():
    out = "\n".join(T.plan_rules())
    for w in ("절 참조", "행 번호", "도구 선언", "벽시계 수", "평어체", "폐기값 수치"):
        assert w in out

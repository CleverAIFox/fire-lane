"""tools/obligations.py — 새 파일의 **빠진 의무를 이름으로** 댄다. 표의 정본은 기존 검사다. (PLAN #199)

★ 양성 대조가 본체다 — 합성 새 파일 하나를 두고 **의무를 하나씩 빼서** 표가 그 이름을 대는지 본다. 「무언가 빠졌다」가 아니라 **무엇이** 빠졌는지.
  의무 하나를 뺄 때 **다른 의무는 안 대야** 한다(이름이 섞이면 사람이 엉뚱한 곳을 고친다).

★ 표를 따로 세우지 않았으므로(사람이 정했다) 이 시험은 **검사의 판정이 표에 그대로 흘러드는가**를 든다 — 검사가 바뀌면 표가 따라가는 길이 살아 있는가.

밖    세 검사(`sealcov` · `toolclass` · `scopedecl`) **각각이 옳게 우는가**는 그 검사의 시험이 든다. 절 단위 의무(새 절 · 대장)는 안 든다 — 표에 「미도출」로 적혀 있는지만 본다.
"""
from __future__ import annotations

import obligations as O

NEW = "tools/zz_new_tool.py"
ALL_OK = {
    "MASTER §22·§23 등재 분모": {NEW}, "MASTER §22·§23 등재 빠짐": set(),
    "머리말 「부류」 분모": {NEW}, "머리말 「부류」 빠짐": set(),
    "머리말 「밖」 분모": {NEW}, "머리말 「밖」 빠짐": set(),
}


def _names(state, rel=NEW, known=None):
    got = O.unmet([rel], state, known if known is not None else {rel})
    return [o.name for o in got.get(rel, [])]


def test_a_fully_registered_new_file_has_no_missing_obligation():
    assert _names(ALL_OK) == []


def test_removing_each_obligation_makes_the_table_name_exactly_that_one():
    for o in O.OBLIGATIONS:
        st = {k: set(v) for k, v in ALL_OK.items()}
        st[f"{o.name} 빠짐"] = {NEW}
        assert _names(st) == [o.name], f"{o.name} 를 뺐는데 표가 {_names(st)} 를 댄다"


def test_removing_several_names_every_one_of_them_and_nothing_else():
    st = {k: set(v) for k, v in ALL_OK.items()}
    st["머리말 「밖」 빠짐"] = {NEW}
    st["MASTER §22·§23 등재 빠짐"] = {NEW}
    assert sorted(_names(st)) == sorted(["머리말 「밖」", "MASTER §22·§23 등재"])


def test_an_obligation_that_does_not_apply_is_not_counted_as_missing():
    """분모에 없는 파일(예: 시험 파일의 「부류」)은 그 의무가 안 따라붙는다 — 빠진 것이 아니다."""
    st = {k: set(v) for k, v in ALL_OK.items()}
    st["머리말 「부류」 분모"] = set()
    st["머리말 「부류」 빠짐"] = {NEW}
    assert _names(st) == []


def test_an_untracked_file_names_only_the_tracking_step_instead_of_a_false_green():
    """추적 전의 새 파일은 어느 검사에도 안 보인다 — 「없음」이 아니라 「git add 가 먼저」를 댄다."""
    st = {k: set() for k in ALL_OK}          # 검사들은 이 파일을 전혀 모른다(분모에도 없다)
    assert _names(st, known=set()) == [O.UNTRACKED.name]


def test_the_real_tree_counts_equal_what_each_checker_counts_so_there_is_no_second_truth():
    """표는 검사의 판정을 그대로 낸다 — 검사가 **빚으로 안고 있는 수**(래칫)와 표의 수가 같다. 같지 않으면 표가 자기 규칙을 쓰고 있다.

    ★ 「밖」 은 빚이 있다(`scopedecl.NO_DECL` 래칫). 그래서 실물에서 **0 을 기대하지 않는다** — 검사가 말하는 수와 같은가를 본다.
    """
    import scopedecl
    import sealcov
    import toolclass
    trk = O.tracked()
    files = sorted(f for f in trk if f.startswith(("tools/", "tests/")) and f.endswith((".py", ".sh")))
    miss = O.unmet(files, known=trk)
    by: dict[str, int] = {}
    for obs in miss.values():
        for o in obs:
            by[o.name] = by.get(o.name, 0) + 1
    assert by.get("머리말 「밖」", 0) == scopedecl.ratchet_values()["NO_DECL"]
    assert by.get("MASTER §22·§23 등재", 0) == len(sealcov.survey()["빈 곳"])
    assert by.get("머리말 「부류」", 0) >= toolclass.ratchet_values()["UNDECLARED"]   # 표는 어휘 밖 · 어긋남도 센다 — 선언 없음 수보다 작을 수 없다


def test_not_derived_obligations_are_listed_not_pretended():
    kinds = {k for k, _, _ in O.NOT_DERIVED}
    assert {"새 절", "대장을 건드릴 때"} <= kinds
    assert "미도출" in O.table()


def test_the_table_names_one_owner_per_obligation_and_no_rule_text_is_copied():
    owners = {o.owner for o in O.OBLIGATIONS}
    assert owners == {"tools/sealcov.py", "tools/toolclass.py", "tools/scopedecl.py"}

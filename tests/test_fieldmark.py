"""`tools/fieldmark.py` — 현장 표지(PLAN #260)를 판정 뒤에 얹는 후처리. A안: 비도로 표지 구간을 판정 집합에서 빼고 blocked 로 안 보낸다.  (DECISIONS 는 사람이 적는다)

IN    tools/fieldmark.py · 실물 표지 · 판독표 · 발행본(읽기만)
OUT   없음 (검사)
PARAM 없음
밖    판정 폐포는 안 본다. 실물 파일을 안 고친다.
"""
from __future__ import annotations

import fieldmark as F


def test_the_selftest_passes() -> None:
    assert F.selftest() == 0


def test_a_plan_excludes_only_nonroad_marks_and_never_moves_a_verdict_to_blocked() -> None:
    """뺀 구간은 전후 합계의 차이일 뿐이고 `blocked` 는 그대로다 · 막다른마당은 안 뺀다."""
    r = F.run()
    marks = F.read_rows(F.MARKS)
    n_nonroad = sum(m["종류"] in F.NONROAD_KINDS for m in marks)
    assert r["before"]["n"] - r["after"]["n"] == n_nonroad
    assert r["after"]["blocked"] == r["before"]["blocked"] and r["after"]["clear"] == r["before"]["clear"]
    assert {k: r["before"][k] - r["after"][k] for k in ("needs_cv", "unknown")} == {k: sum(m["종류"] in F.NONROAD_KINDS and _verdict(m) == k for m in marks) for k in ("needs_cv", "unknown")}


def _verdict(m: dict) -> str:
    import json
    by = {f["properties"]["seg_uid"]: f["properties"]["verdict"] for f in json.loads(F.SEG.read_text(encoding="utf-8"))["features"]}
    return by[m["seg_uid"]]


def test_the_columns_never_say_not_seen_as_false() -> None:
    """값 표현 — `field_seen` 은 true · null 뿐이고 `nonroad_mark` 는 닫힌 종류 · null 뿐이다. 둘 다 null 이 「안 봤다」다."""
    col = F.run()["col"]
    assert set(col["field_seen"]) <= {True, None} and set(col["nonroad_mark"]) <= {None, *F.NONROAD_KINDS}
    assert all(s is True for s, k in zip(col["field_seen"], col["nonroad_mark"], strict=True) if k), "표지가 있는데 본 구간이 아니다"
    assert col["field_seen"].count(None) > len(col["field_seen"]) // 2, "안 본 구간이 다수다 — 표지 수를 전수의 몫으로 읽지 않는다"


def test_a_mark_whose_key_is_not_in_the_published_set_is_counted_as_stale() -> None:
    marks = [{"seg_uid": "있다", "종류": "계단"}, {"seg_uid": "없다", "종류": "계단"}]
    assert not F.stale_marks(marks, {"있다", "없다"}), "발행본에 다 있는데 낡은 표지로 셌다"
    assert [m["seg_uid"] for m in F.stale_marks(marks, {"있다"})] == ["없다"]
    props = [{"seg_uid": "있다", "verdict": "unknown", "width_min_m": 1.0}]
    col = F.columns(["있다"], marks, F.seen_uids([], marks))
    assert F.region_stat(props, col, 1)["낡은 표지"] == 1 and "낡은 표지 1" in F.region_line(F.region_stat(props, col, 1))


def test_duplicate_keys_and_unknown_kinds_are_faults() -> None:
    assert not F.mark_faults([{"seg_uid": "a", "종류": "계단"}, {"seg_uid": "b", "종류": "계단"}]), "멀쩡한 표지를 결함이라 했다"
    marks = [{"seg_uid": "a", "종류": "계단"}, {"seg_uid": "a", "종류": "공터"}]
    assert len(F.mark_faults(marks)) == 2


def test_the_real_region_line_counts_marks_inside_the_seen_share() -> None:
    s = F.run()["region"]
    assert s["표지"] <= s["본"] <= s["영역"] and s["본"] + s["안 본"] == s["영역"] and s["낡은 표지"] == 0
    assert sum(b for _, b in s["층"].values()) == s["영역"]

"""`tools/fieldmark.py` — 현장 표지(PLAN #260)를 판정 뒤에 얹는 후처리. A안: 비도로 표지 구간을 판정 집합에서 빼고 blocked 로 안 보낸다.  (DECISIONS 는 사람이 적는다)

IN    tools/fieldmark.py · 실물 표지 · 판독표 · 발행본(읽기만)
OUT   없음 (검사)
PARAM 없음
밖    판정 폐포는 안 본다. 실물 파일을 안 고친다.
"""
from __future__ import annotations

import json

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


# ── 도착 ② — 판독표 검정(`evalset.rv_check`)이 표지된 행을 이름 붙여 세고 분모에서 뺀다(보고용 · 판정 불변) ──

def _row(uid: str, ans: str, view: str = "있다") -> dict:
    return {"seg_uid": uid, "거리뷰": view, "답": ans}


def _two_arms(marked: frozenset[str]) -> tuple[int, int, int, int]:
    """합성 판독표 — 가설군 `h1..h4`(둘은 한쪽) · 대조군 `c1..c4`(하나는 한쪽). 분자는 「한쪽」."""
    hyp = [_row("h1", "한쪽"), _row("h2", "한쪽"), _row("h3", "양쪽없다"), _row("h4", "양쪽없다")]
    con = [_row("c1", "한쪽"), _row("c2", "양쪽없다"), _row("c3", "양쪽없다"), _row("c4", "양쪽없다")]
    a, b = F.answers_seen(hyp, True, marked), F.answers_seen(con, True, marked)
    return sum(x == "한쪽" for x in a), len(a), sum(x == "한쪽" for x in b), len(b)


def test_marked_rows_leave_the_denominator_and_are_counted_by_name() -> None:
    assert _two_arms(frozenset()) == (2, 4, 1, 4)
    assert _two_arms(frozenset({"h1", "c2"})) == (1, 3, 1, 3), "표지된 행이 분모에서 안 빠졌다"
    rv = [_row("h1", "한쪽"), _row("c1", "한쪽"), _row("c2", "양쪽없다")]
    marks = [{"seg_uid": "h1", "종류": "계단"}, {"seg_uid": "c1", "종류": F.DEAD_END}, {"seg_uid": "zz", "종류": "계단"}]
    s = F.sheet_marks(rv, marks)
    assert (s["표지된 행"], s["분모에서 뺌(비도로)"], s["안 뺌(막다른마당 · 길이 맞다)"], s["판독표에 없는 표지"]) == (2, 1, 1, 1), s    # (c) 표지에만 있는 열쇠는 따로 센다
    assert F.nonroad_uids(marks) == {"h1", "zz"}, "막다른마당을 비도로로 뺐다"
    assert F.answers_seen([_row("only_in_sheet", "한쪽")], True, F.nonroad_uids(marks)) == ["한쪽"], "표지에 없는 판독표 행은 그대로 센다"


def _synthetic_samples(feats: list[dict]) -> dict[str, list[dict]]:
    """발행본(저장소에 든 구간 파일)에서 표본 행을 **스스로 만든다** — 표본 파일(`data/processed/width_samples.csv`)은 생성물이라 러너에 없다.

    검정이 구간을 가설군 · 대조군으로 가르는 데 쓰는 것은 최소폭 표본 행 하나뿐이다(번호 · 폭이 발행값과 같아야 한다). 그 행만 발행 속성에서 세운다.
    ★ 좌표 검사(최소폭 표본 지점)는 합성 표본으로는 안 맞아 결함 목록에 오르지만 이 시험은 통계만 본다 — 결함 목록은 안 읽는다.
    """
    out: dict[str, list[dict]] = {}
    for f in feats:
        p = f["properties"]
        i, w = p.get("width_min_sample_idx"), p.get("width_min_m")
        if i is None or w is None or p.get("length_m") is None:
            continue
        rows = [{"seg_uid": p["seg_uid"], "w_m": str(w), "s_m": str(float(p["length_m"]) / 2)} for _ in range(int(i) + 1)]
        out[p["seg_uid"]] = rows
    return out


def test_empty_marks_change_nothing_and_say_zero() -> None:
    """(b) 표지가 비면 분모 · 통계가 종전과 같고 요약이 「표지 0건」을 분모와 함께 낸다 — 판정 불변."""
    from pathlib import Path

    import evalset as E
    feats = json.loads(E.SEG.read_text(encoding="utf-8"))["features"]
    samples = _synthetic_samples(feats)
    path = E.OUT_CSV.parent / E.RV_FILE
    _, none = E.rv_check(path, feats, samples, marks=[])
    assert none["현장 표지"]["표지 파일 행"] == 0 and "표지 0건" in none["현장 표지"]["요약"] and "판독표 40행" in none["현장 표지"]["요약"]
    assert F.load_marks(Path("/nonexistent/marks.csv")) == []
    _, real = E.rv_check(path, feats, samples)
    for h in E.RV_HYPO:       # 실물 표지 5구간은 이미 가림 · 거리뷰 없다 · 길 아님으로 못 본 행이라 분자 · 분모 · p 가 안 움직인다
        for k in ("가설군", "대조군", "p", "판정", "못 본 행(거리뷰 없다 · 가림 · 길 아님)"):
            assert real[h][k] == none[h][k], (h, k)
        assert none[h]["그중 현장 표지(분모에서 뺌)"] == 0
    assert sum(real[h]["그중 현장 표지(분모에서 뺌)"] for h in E.RV_HYPO) == real["현장 표지"]["분모에서 뺌(비도로)"] == 5


def test_canary_a_synthetic_defect_that_skips_the_subtraction_is_caught() -> None:
    """(d) 카나리아 — 옛 동작(표지를 안 뺀다)과 새 동작이 합성 입력에서 다른 값을 낸다 · 빼기를 끈 변형이 이 시험에서 운다."""
    import evalset as E
    marked = frozenset({"h3", "h4", "c1"})      # 가설군의 양쪽없다 둘 · 대조군의 한쪽 하나를 표지로 뺀다
    old, new = _two_arms(frozenset()), _two_arms(marked)
    assert old != new and new == (2, 2, 0, 3)
    p_old, p_new = E.rv_fisher(old[0], old[1], old[2], old[3]), E.rv_fisher(new[0], new[1], new[2], new[3])
    assert p_old != p_new and p_new < p_old, (p_old, p_new)

    real = F.answers_seen

    def broken(rows: list[dict], views: bool, marked: frozenset[str] | set[str]) -> list[str]:      # 일부러 빼기를 끈 변형
        return real(rows, views, frozenset())

    try:
        F.answers_seen = broken
        assert _two_arms(marked) == old, "변형이 옛 동작과 같아야 한다"
        assert _two_arms(marked) != new, "빼기를 끈 변형이 새 동작과 같다 — 시험이 못 운다"
    finally:
        F.answers_seen = real
    assert _two_arms(marked) == new

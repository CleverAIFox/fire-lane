"""
test_measurecols.py — 측정 절의 「쓴 칸」 머릿줄 강제자.  (PLAN #193 · DECISIONS §631-5 · §637)

── 이 시험이 무는 것 ──────────────────────────────────────────
① 실물 DECISIONS 의 측정 절이 머릿줄 규약을 지킨다(§635 가 첫 사례) — CI 가 파일 단위 조각으로 이 파일을 돌리므로 **워크플로 변경 없이** 강제된다.
② 규칙 넷이 **합성 입력으로 각자 운다**(양방향 — 실물만 재면 「언제나 초록」과 구별이 안 된다): 칸 실재 · 위치 역할(`not_for` · 좌표 없음 · 지목 없음 · 미확인) ·
   「없음」 선언과 메모 · 빠뜨림 방지(본문 토큰).
③ **과거 사고가 걸린다** — 2026-11-04 `#39` 측정(DECISIONS §625)이 신고자 휴대폰 좌표를 위치로 썼다. §625 의 실제 본문에 그 측정이 쓴 칸을 머릿줄로 달아 보면
   `not_for` 와 「없음」 메모 누락이 **둘 다** 걸리고, 바로잡은 머릿줄은 위치 위반이 사라진다.
④ 소급하지 않는다 — `START` 앞의 절은 머릿줄이 없어도 안 본다.

밖    **측정이 옳은가는 안 본다.** 본문에 칸을 안 적고 머릿줄도 안 적은 측정은 못 본다.
"""
from __future__ import annotations

from firelane import ledger
from firelane import measurecols as M

LED = {"datasets": {
    "t": {"kind": "csv_table", "schema": {"columns": ["LOT", "LAT", "PH_LOT", "PH_LAT", "RES_LOT", "RES_LAT", "T0", "T1", "YR"], "profile": {"n": 9, "cols": {
        "T0": {"empty": 0, "ws": 3}, "T1": {"empty": 1, "ws": 0}}}},
        "coords": {"site": {"x": "LOT", "y": "LAT", "crs": 4326, "means": "재해 위치"},
                   "reporter": {"x": "PH_LOT", "y": "PH_LAT", "crs": 4326, "means": "신고자 휴대폰 위치", "not_for": ["위치 분석", "지도 표출"]},
                   "unconfirmed": {"x": "RES_LOT", "y": "RES_LAT", "crs": 4326, "means": "미확인"}},
        "none": {"T0": {"forms": ["공백"]}}},
    "n": {"kind": "csv_table", "schema": {"columns": ["A", "D"]}, "coords": {"none": "좌표 칸이 없다"}},
}}


def _sec(head: str, body: str = "", n: int = 700) -> list[str]:
    return M.check_section(n, "x 측정", (f"쓴 칸    {head}\n" if head is not None else "") + body, LED)


def test_the_real_decisions_keep_the_header_convention():
    assert M.check_all() == []
    secs = [n for n, t, b in M.sections((M.ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")) if n >= M.START and M.used_line(b)]
    assert 635 in secs, "첫 사례(§635)를 못 읽었다 — 파서가 죽었다"


def test_a_measurement_section_without_the_header_is_refused():
    assert any("머릿줄이 없다" in e for e in _sec(None, "본문"))
    assert _sec("없음 — 사유: 문서만 읽었다") == []
    assert any("사유" in e for e in _sec("없음"))
    assert any("t.LOT" in e for e in _sec("없음 — 사유: x", "`t.LOT` 을 썼다")), "없음이라 하고 칸을 쓰면 모순이다"


def test_columns_must_exist():
    assert any("원천 `zz`" in e for e in _sec("zz.A(거리)"))
    assert any("`NOPE`" in e for e in _sec("t.NOPE(거리)"))
    assert any("항목을 못 읽는다" in e for e in _sec("t.LOT 위치"))
    assert any("역할은" in e for e in _sec("t.LOT(위친)")), "역할 오타가 조용히 건너뛰면 안 된다"


def test_a_location_role_asks_the_ledger_whether_the_column_may_be_a_location():
    assert _sec("t.LOT/LAT(위치)") == []
    assert any("not_for" in e for e in _sec("t.PH_LOT/PH_LAT(위치)")), "신고자 휴대폰 좌표를 위치로 쓰면 운다"
    assert _sec("t.PH_LOT/LAT(위치 비교 대상)") == [], "비교 대상으로 쓰는 것은 막지 않는다"
    assert any("미확인" in e for e in _sec("t.RES_LOT/LAT(위치)"))
    assert _sec("t.RES_LOT/LAT(위치 · 미확인임을 알고 쓴다)") == []
    assert any("좌표가 없다" in e for e in _sec("n.A(위치)"))
    assert any("지목하지 않은" in e for e in _sec("t.T0(위치)"))


def test_a_time_or_split_column_with_a_none_form_must_say_what_none_is():
    assert any("없음=" in e for e in _sec("t.T0(시각)")), "공백 문자열이 있는 칸을 메모 없이 쓰면 운다(`notna()` 사고)"
    assert _sec("t.T0(시각 · 없음=공백)") == []
    assert any("선언이 없다" in e for e in _sec("t.T1(가르기 · 없음=빈 셀)")), "재 보니 빈 셀이 있는데 선언이 없다"
    assert any("T1" in e for e in _sec("t.T0/T1(시각 · 없음=공백)")), "T1 은 선언이 없다"
    assert _sec("t.YR(판 가르기)") == [], "없음이 없는 칸은 메모가 필요 없다"


def test_a_column_the_body_uses_but_the_header_omits_is_caught():
    assert any("t.T1" in e for e in _sec("t.YR(판 가르기)", "본문이 `t.T1` 을 읽었다"))
    assert _sec("t.YR(판 가르기) · T1(거리)", "본문이 `t.T1` 을 읽었다") == []
    assert any("PH_LOT" in e for e in _sec("t.LOT/LAT(위치)", "비교 대상은 `PH_LOT` 이다")), "좌표 칸은 접두 없이 적어도 센다"
    assert _sec("t.LOT/LAT(위치)", "문장 안의 PH_LOT 는 백틱이 없어 안 센다") == []


def test_the_caption_resolves_a_shared_prefix_and_inherits_the_source():
    items, errs = M.parse_used("t.PH_LOT/LAT(위치) · T0(시각 · 없음=공백) · n.A(거리)")
    assert not errs and [(i["src"], i["col"]) for i in items] == [("t", "PH_LOT"), ("t", "LAT"), ("t", "T0"), ("n", "A")]
    assert items[1]["alt"] == "PH_LAT" and items[2]["note"] == "없음=공백"


def test_a_section_before_the_start_is_not_checked():
    assert M.check_all(LED, "## 10. 옛 측정\n\n본문\n\n## 700. 새 측정\n\n본문\n") != []
    assert M.check_all(LED, "## 10. 옛 측정\n\n본문\n") == []


def test_the_incident_of_2026_11_04_is_caught_and_the_correction_is_not():
    """★ 이 시험이 존재하는 이유. §625 의 **실제 본문**을 쓴다."""
    led = ledger.load_sources()
    text = (M.ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    n, t, body = next(s for s in M.sections(text) if s[0] == 625)
    bad = M.check_section(n, t, "쓴 칸    nfa_dispatch_119.DCLR_PSTN_LAT/LOT(위치) · nfa_dispatch_119.GRNDS_ARVL_DT(시각) · "
                          "nfa_dispatch_119.HSPTL_ARVL_DT(가르기)\n" + body, led)
    assert any("not_for" in e and "DCLR_PSTN_LAT" in e for e in bad), bad
    assert any("없음=" in e and "HSPTL_ARVL_DT" in e for e in bad), bad
    good = M.check_section(n, t, "쓴 칸    nfa_dispatch_119.LOT/LAT(위치) · nfa_dispatch_119.DCLR_PSTN_LAT/LOT(위치 비교 대상) · "
                           "nfa_dispatch_119.GRNDS_ARVL_DT/HSPTL_ARVL_DT(시각 · 없음=빈 셀|공백)\n" + body, led)
    assert not any("not_for" in e or "HSPTL_ARVL_DT" in e for e in good), good

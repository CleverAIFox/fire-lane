"""`tools/rvpower.py` — 판독표 검정이 자기 검정력을 판독 전에 말하고 · 실측이 전제를 벗어나면 운다.  (PLAN #263 · DECISIONS §835)

IN    tools/rvpower.py · tools/rvsheet.py · tools/evalset.py · 실물 판독표(읽기만)
OUT   없음 (검사)
PARAM 없음
밖    **대조군 비율이 얼마여야 옳은가**는 안 본다(사전 추정이 없다). 판독 값은 안 고친다 — 읽기만 한다.
"""
from __future__ import annotations

import json

import evalset as E
import pytest
import rvpower as P
import rvsheet as S
from test_evalset import FLAT, SEEN, _hy_real, _hy_sheet, _hy_world, _roles


def test_ceiling_is_the_largest_control_count_a_fully_true_group_can_still_reject() -> None:
    """천장 = 가설군이 전부 참일 때 `fisher ≤ α` 가 되는 대조군 수의 최대 — 설계 넷의 수(PLAN #263 의 표)."""
    assert {k: P.ceiling(*v) for k, v in {"가 설계": (8, 7), "가 본 몫": (4, 6), "나": (7, 5), "다": (6, 5)}.items()} == {"가 설계": 3, "가 본 몫": 1, "나": 2, "다": 1}
    assert P.ceiling(2, 2) == -1 and P.ceiling(0, 5) == -1, "어떤 대조군에서도 기각 못 하는 표본이 -1 이 아니다"
    for n1, n0 in ((8, 7), (4, 6), (7, 5), (6, 5)):
        c = P.ceiling(n1, n0)
        assert P.fisher(n1, n1, c, n0) <= S.RV_ALPHA < P.fisher(n1, n1, c + 1, n0), "천장이 경계가 아니다"
    assert E.rv_fisher is P.fisher


def test_the_old_sample_size_check_assumed_a_zero_control_and_said_nothing() -> None:
    """★ 종전 검사 `rv_fisher(n1, n1, 0, n0) ≤ α` 는 대조군 0 을 가정했다(DECISIONS §782 설계표 「대조군 0 → 가설군 5 이상」). 그 가정은 가 · 다 에서 틀렸다.
    0 을 가정하면 가 · 나 · 다 모두 통과하지만 실측 대조군은 가 5/6 · 다 2/5 였다 — 이제는 가정이 **선언**이고 실측이 넘으면 운다."""
    for k, h in S.RV_HYPO.items():
        assert E.rv_fisher(h[0], h[0], 0, h[1]) <= S.RV_ALPHA, f"가설 {k}: 대조군 0 에서도 기각 못 하는 설계였다"
    assert P.fisher(4, 4, 5, 6) == pytest.approx(0.6) and P.fisher(8, 8, 5, 6) > 0.4 and P.fisher(6, 6, 2, 5) == pytest.approx(0.0606, abs=1e-4), "PLAN #263 의 수"


def test_every_hypothesis_declares_its_control_bound_with_a_reason_and_not_looser_than_the_design() -> None:
    assert set(S.RV_CTRL_MAX) == set(S.RV_HYPO) and P.declaration_flaws() == []
    for k, (hits, n0, why) in S.RV_CTRL_MAX.items():
        assert n0 == S.RV_HYPO[k][1] and hits <= P.ceiling(S.RV_HYPO[k][0], n0) and why.strip()


def test_a_loose_or_missing_declaration_is_a_defect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P, "RV_CTRL_MAX", {**S.RV_CTRL_MAX, "가": (4, 7, "더 느슨하다")})
    assert any("느슨" in x for x in P.declaration_flaws())
    monkeypatch.setattr(P, "RV_CTRL_MAX", {k: v for k, v in S.RV_CTRL_MAX.items() if k != "나"})
    assert any("선언이 없" in x for x in P.declaration_flaws())
    monkeypatch.setattr(P, "RV_CTRL_MAX", {**S.RV_CTRL_MAX, "다": (1, 5, " ")})
    assert any("근거" in x for x in P.declaration_flaws())


def test_the_design_is_told_before_the_reading_and_does_not_leak_the_roles() -> None:
    d = P.design_stat()
    assert d["가"]["검정력(조건부)"].endswith("3/7(43%) 이하여야 기각할 수 있다") and "1/5(20%)" in d["다"]["검정력(조건부)"] and "2/5(40%)" in d["나"]["검정력(조건부)"]
    assert "조건부" in d["조건"] and "사전 추정이 없다" in d["조건"] and "무효로 만들지 않는다" in d["조건"]
    assert all(set(v) == {"설계(가설 쪽 대 대조 쪽)", "검정력(조건부)", "선언한 상한", "근거"} for k, v in d.items() if k in S.RV_HYPO), "어느 행이 대조군인지는 싣지 않는다"


def test_the_real_sheet_cries_for_ga_and_da_and_stays_quiet_for_na() -> None:
    """★ 소급 — 세 판독표의 관측 값만 읽는다. 고치기 전 코드는 가 · 다 에서 한 줄도 안 울었다(판정 칸만 「기각하지 못한다 — 표본이 작아…」)."""
    feats, samples, _ = _hy_real()
    bad, stat = E.rv_check(E.OUT_CSV.parent / E.RV_FILE, feats, samples)
    assert not bad, bad
    cry = {k: stat[k]["검정력"]["울음"] for k in S.RV_HYPO}
    assert cry["나"] == [] and len(cry["가"]) == 2 and len(cry["다"]) == 2, cry
    assert [(stat[k]["가설군"], stat[k]["대조군"]) for k in S.RV_HYPO] == [("2/4", "5/6"), ("5/7", "1/5"), ("5/6", "2/5")]
    assert stat["가"]["검정력"]["본 표본(가설군 대 대조군)"] == "4 대 6" and "1/6(17%)" in stat["가"]["검정력"]["검정력"] and "1/5(20%)" in stat["다"]["검정력"]["검정력"]
    assert all("p" in stat[k] and stat[k]["판정"] for k in S.RV_HYPO), "울어도 결과 칸을 지우지 않는다"
    assert "무효로 만들지 않는다" in stat["가"]["검정력"]["뜻"] and "결론을 못 낸다" in stat["다"]["검정력"]["뜻"]
    assert len(P.cries(stat)) == 4 and all("가설 가" in c or "가설 다" in c for c in P.cries(stat))


def test_a_synthetic_sheet_cries_only_when_the_control_exceeds_the_ceiling(tmp_path) -> None:
    feats, samples = _hy_world()
    picks = E.rv_draw(feats, samples)
    role = dict(zip([u for _, u in picks], [r for _, r in _roles(feats, samples, [{"가설": h, "seg_uid": u} for h, u in picks])], strict=True))
    n1, n0 = S.RV_HYPO["가"][:2]
    for hits, cries in ((0, False), (P.ceiling(n1, n0), False), (P.ceiling(n1, n0) + 1, True)):
        seen_c = [u for h, u in picks if h == "가" and role[u] == "대조군"][:hits]
        ans = {u: {**SEEN, "답": "양쪽" if role[u] == "가설군" else "한쪽" if u in seen_c else "없다", **(FLAT if role[u] != "지명" and ("양쪽" if role[u] == "가설군" else "한쪽" if u in seen_c else "") else {})}
               for h, u in picks if h == "가" and role[u] != "지명"}
        path, f, s_, _ = _hy_sheet(tmp_path, ans)
        bad, stat = E.rv_check(path, f, s_)
        assert not bad, bad
        rep = stat["가"]["검정력"]
        assert bool(rep["울음"]) is cries, (hits, rep)
        assert rep["실측 대조군"].startswith(f"{hits}/{n0}")
        if cries:
            assert "기각 불가능" in rep["울음"][0] and stat["가"]["p"] > S.RV_ALPHA, "천장 위인데 p 가 기각했다"
        else:
            assert stat["가"]["p"] <= S.RV_ALPHA


def test_the_cry_is_printed_in_red_with_its_meaning_and_the_exit_stays_zero(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    """울음은 결과를 무효로 안 만든다 — 실물 판독표는 칸 · 허용값이 온전하므로 종료 코드는 0 이고 붉은 줄과 뜻이 선다."""
    _hy_real()
    assert E.rv_main(True, False) == 0
    out = capsys.readouterr().out
    assert "\033[31m✗ 검정력 — 가설 가: 기각 불가능" in out and "가설 다: 기각 불가능" in out and "가설 나: " not in out.split("↳")[0].split("✗ 검정력")[-1]
    assert "↳ 울음은 결과를 무효로 만들지 않는다" in out and json.loads(out[out.index("{"): out.index("\n}") + 2])["행"] == 40

#!/usr/bin/env python3
"""
test_scopecheck.py — 스코프 래칫이 **넓어지는 쪽을 실제로 막는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §1 #62). 출동 대상지는 동명동 하나(0.429km²)인데 발행된
판정 산출물의 **총연장 68.9% 가 동 밖**이고, 그중 **54.6%p 는 어떤 출동
경로도 안 쓴다**(`route_usage == 0`).

★ **이 사실을 세는 검사가 저장소에 하나도 없었다.** 있던 것은
  `tests/test_station_scope.py` 하나이고 그것은 「스코프가 안전센터를
  덮는가」만 본다 — **넓을수록 통과한다.** 방향이 반대인 검사만 있는 것은
  검사가 없는 것보다 나쁘다. 있다고 적혀 있으면 사람이 안 보기 때문이다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 자체시험 다섯이 실제로 돈다
    2. 상한 키와 측정 키가 같다              (한쪽만 늘면 조용히 안 센다)
    3. 넓어지면 운다                          (본래 목적)
    4. 좁아져도 운다                          (느슨한 래칫 금지 · §199-1)
    5. 상한이 실측보다 **너무 헐겁지 않다**   (세우자마자 낡는 것 금지)
    6. `verify.sh` 와 CI **양쪽**이 부른다    (로컬 전용이 아니다)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import scopecheck as S

ROOT = Path(__file__).resolve().parents[1]


def test_selftest_passes():
    assert S.selftest() == 0


def test_cap_keys_match_measured_keys():
    """상한과 측정이 **같은 것을 가리키는가.**

    ★ 측정이 넷인데 상한이 셋이면 그 하나는 **아무도 안 본다.** 조용히
      안 세는 축이 생기는 것이라, 검사가 있다는 착각만 남는다.
    """
    assert set(S.measure()) == set(S.CAP), (
        f"측정 {sorted(S.measure())} · 상한 {sorted(S.CAP)}\n"
        "  한쪽에만 있는 축은 아무도 안 본다.")


def test_widening_is_rejected():
    """넓어지면 우는가 — 이 검사의 본래 목적."""
    cap = {"x": 50.0}
    assert S.judge({"x": 50.01}, cap), "상한을 넘었는데 안 울었다"
    assert S.judge({"x": 90.0}, cap), "크게 넓어졌는데 안 울었다"


def test_narrowing_also_cries():
    """좁아져도 우는가 — **느슨한 래칫은 초록으로 위장한다**(DECISIONS §199-1).

    ★ 이쪽이 되돌림이다. 스코프를 줄이는 배치가 상한을 안 내리면 다음
      배치가 조용히 원위치해도 아무도 안 운다.
    """
    cap = {"x": 50.0}
    assert S.judge({"x": 50.0 - S.SLACK - 0.01}, cap), (
        "상한보다 눈금 넘게 낮은데 안 울었다 — 래칫이 한 방향만 본다")
    assert not S.judge({"x": 50.0 - S.SLACK + 0.01}, cap), (
        "눈금 안쪽인데 울었다 — 부동소수 잡음으로 빨개진다")


def test_cap_is_not_slack_from_the_start():
    """상한이 실측 바로 위인가 — **세우자마자 낡은 래칫을 금지한다.**

    ★ 2026-09-19 에 커버리지 래칫이 14 인데 실측이 24% 였다. 열 점이
      되돌아갈 자리로 남아 있었고 나흘간 아무도 몰랐다. 같은 일을
      여기서 반복하지 않는다.
    """
    got = S.measure()
    bad = []
    for k, cap in S.CAP.items():
        gap = cap - got[k]
        if gap < 0:
            bad.append(f"  {k}  실측 {got[k]:.2f}% > 상한 {cap}% — 지금 빨갛다")
        elif gap > 1.0:
            bad.append(f"  {k}  실측 {got[k]:.2f}% · 상한 {cap}% — {gap:.2f}%p 헐겁다")
    assert not bad, (
        "상한이 실측과 멀다.\n" + "\n".join(bad)
        + "\n\n  래칫은 **지금 값에서 시작한다.** 여유를 크게 두면 그만큼이\n"
          "  되돌아갈 자리로 남고, 그 자리는 초록으로 위장한다.")


def test_both_verify_and_ci_call_it():
    """로컬과 CI **양쪽**이 부르는가.

    ★ 이 검사는 커밋된 `segments.geojson` 속성만 읽는다 — 레이크도
      지오메트리 연산도 없다. 그러니 CI 에서 못 돌 이유가 없고,
      `ci-exempt` 로 뺄 이유도 없다(PLAN §13 W3-10).
    """
    v = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    c = (ROOT / ".github" / "workflows" / "contract.yml").read_text(encoding="utf-8")
    assert "tools/scopecheck.py" in v, "verify.sh 가 안 부른다"
    assert "tools/scopecheck.py" in c, "CI 가 안 부른다 — 로컬에서만 도는 검사가 된다"
    assert "# ci-exempt: tools/scopecheck.py" not in v, (
        "면제가 선언돼 있다 — 이 검사는 CI 에서 돌 수 있다. 면제는 거짓말이 된다.")


@pytest.mark.parametrize(("feats", "want"), [
    # 전부 안 · 전부 사용 → 0%
    ([{"in_emd": True, "length_m": 10, "route_usage": 3}], (0.0, 0.0, 0.0)),
    # 전부 밖 · 전부 무용 → 100%
    ([{"in_emd": False, "length_m": 10, "route_usage": 0}], (100.0, 100.0, 100.0)),
    # 밖이지만 경로가 쓴다 → 무용은 0
    ([{"in_emd": False, "length_m": 10, "route_usage": 7}], (100.0, 100.0, 0.0)),
    # ★ `in_emd` 가 없으면 **밖으로 센다.** 모름을 안쪽으로 봐주면 속성이
    #   빠진 발행물에서 비율이 조용히 0 이 된다.
    ([{"length_m": 10, "route_usage": 0}], (100.0, 100.0, 100.0)),
])
def test_measure_on_synthetic(tmp_path, feats, want):
    p = tmp_path / "s.geojson"
    p.write_text(json.dumps(
        {"type": "FeatureCollection",
         "features": [{"properties": q} for q in feats]}), encoding="utf-8")
    got = S.measure(p)
    assert (round(got["밖 구간 비율"], 3),
            round(got["밖 연장 비율"], 3),
            round(got["무용 연장 비율"], 3)) == want

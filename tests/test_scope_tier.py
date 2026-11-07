#!/usr/bin/env python3
"""
test_scope_tier.py — 발행 범위 분류 `scope_tier` 가 **정의대로** 붙고, 구간을 하나도 안 떨구는가.
(PLAN #62 · DECISIONS §612-5 · §613)

── 왜 이 가드인가 ─────────────────────────────────────────────
723 → 755 가 낡은 사연이 **수를 문서에 박은 것**이었다(DECISIONS §610). 그래서 이 시험은 수를 한 곳에도 안 적는다 —
정의(`in_emd` · `route_usage` · 소방서 표 주소부)로 다시 계산해 발행 칸과 댄다.

가드 다섯 (발행물 `web/data/segments.geojson` 을 읽는다)
  ① 모든 구간의 `scope_tier` 가 `in_emd` · `route_usage` · 지정으로 **다시 계산한 값과 같다**
  ② 네 묶음의 합이 구간 수와 같다 — 그리고 판정이 낸 구간 수와 같다(**하나도 안 떨궜다**)
  ③ `reference` 가 발행 범위 집계에 안 섞인다
  ④ 매처가 **조용히 안 죽었다** — 지정이 0건이면 운다(`nfa_compare` 가 두 번 겪은 사고의 꼴이다)
  ⑤ 자체시험 — 괄호 안 맥락 이름 `(구, 지호로)` 류가 지정으로 안 잡힌다. 판정기가 양쪽으로 운다.

IN    web/data/segments.geojson · data/processed/segments.geojson(구간 수) · data/processed/fire_access.csv(있으면)
OUT   없음 (검사)
PARAM 없음
밖    **소방서 지정이 옳은가는 안 본다**(`PLAN #187`). 분류가 정의대로인지만 본다.
"""
from __future__ import annotations

import json
from pathlib import Path

import golden
import pytest

from firelane import fireaccess, scopetier

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "data" / "segments.geojson"
PROC = ROOT / "data" / "processed" / "segments.geojson"
FIRE = ROOT / "data" / "processed" / "fire_access.csv"


def _published() -> list[dict]:
    if not WEB.exists():
        pytest.skip("환경skip(산출물) — web/data/segments.geojson 이 없다")
    return [f["properties"] for f in json.loads(WEB.read_text(encoding="utf-8"))["features"]]


def _row(text: str, length: float = 100.0) -> dict:
    return dict(text=text, norm=fireaccess._norm(text), len=length, width="5", hh=1)


# ── 정의 자체 (합성 입력) ─────────────────────────────────────

def test_tier_priority_follows_the_definition():
    t = scopetier.tier
    assert t(True, 0, False) == "target"
    assert t(True, 5, True) == "target", "동명동 안이면 지정이어도 대상지다"
    assert t(False, 3, False) == "corridor"
    assert t(False, 3, True) == "corridor", "경로가 쓰면 지정이어도 회랑이다"
    assert t(False, 0, True) == "listed"
    assert t(False, 0, False) == "reference"
    # 결손(None · NaN)은 0 이다 — 회랑으로 새지 않는다
    assert t(False, None, False) == "reference" and t(False, float("nan"), False) == "reference"
    assert t(None, 0, False) == "reference" and t(float("nan"), 0, True) == "listed"


def test_the_tier_values_and_scope_set_are_closed():
    assert scopetier.TIERS == ("target", "corridor", "listed", "reference")
    assert scopetier.IN_SCOPE == {"target", "corridor", "listed"}
    assert not scopetier.in_scope("reference")
    assert all(scopetier.in_scope(x) for x in ("target", "corridor", "listed"))


def test_selftest_a_parenthetical_context_name_is_not_a_designation():
    """★ 자체시험 — `(구, 지호로)` 처럼 괄호 안에 적힌 옛 이름 · 주변 길은 지정이 아니다(DECISIONS §612-3)."""
    rows = [
        _row("지산복지회관 주변 동구 밤실로4번길 16(지산2동) 일대(구, 지호로)"),
        _row("금남맨션 : 중앙로196번길 14(금남로3가, 금남맨션)일대(구, 중앙초등길, 대의2길)"),
        _row("거성마트옆길 ~ 살레시오여고 후문 동구 지산로 37(지산1동) 일대(구, 섬들1길, 살레시오여고옆길)"),
        _row("남광주 시장 : 제봉로17번길 9-9（학동）일대"),
    ]
    a = scopetier.address_rows(rows)

    def d(n: str) -> bool:
        return scopetier.is_designated(n, a)

    # 주소부에 있는 이름은 지정이다
    assert d("밤실로4번길") and d("중앙로196번길") and d("제봉로17번길")
    assert d("지산로"), "본선 번지 행(지산로 37)은 주소부다 — 지정 구간을 안 세면 지정을 안 세는 것이다"
    # 괄호 안 맥락은 지정이 아니다
    assert not d("지호로") and not d("금남로") and not d("섬들1길") and not d("중앙초등길")
    # 전각 괄호도 주소부 끝이다
    assert scopetier.address_part("제봉로17번길 9-9（학동）일대") == "제봉로17번길 9-9"
    # 지역명 어디서든 걸리는 기존 매처는 지호로를 잡는다 — 그래서 이 정의를 따로 둔다
    assert fireaccess.match("지호로", rows) is not None and fireaccess.match("지호로", a) is None


def test_selftest_the_matcher_stays_exact_and_tolerates_spaces():
    """정확 일치(부분 문자열 아님) · 번길 공백 허용은 `fireaccess.match` 의 것이다 — 여기서 안 깨졌는가."""
    a = scopetier.address_rows([_row("계림동 주변 동구 경양로 247번길 26(계림동) 일대")])
    assert scopetier.is_designated("경양로247번길", a)
    assert not scopetier.is_designated("경양로", a), "본선 경양로가 번길 행에 걸리면 안 된다(DECISIONS §550-2)"
    assert not scopetier.is_designated(None, a) and not scopetier.is_designated("", a)


def test_columns_label_every_segment_and_drop_none():
    rows = [_row("대인시장 : 제봉로184번길 10(대인동) 일대(구, 지호로)")]
    cols = scopetier.columns([True, False, False, False, False], [0, 2, 0, 0, None],
                             ["a", "b", "제봉로184번길", "지호로", "x"], rows)["scope_tier"]
    assert cols == ["target", "corridor", "listed", "reference", "reference"]
    assert len(cols) == 5, "구간을 하나도 안 떨군다"


def test_the_classifier_lives_outside_the_judgment_closure():
    """판정 폐포 안이면 이 모듈을 고칠 때마다 재잠금이 따라온다 — 폐포가 이 모듈을 import 하면 운다."""
    files = golden.judgment_files()
    for rel in ("src/firelane/scopetier.py", "src/firelane/fireaccess.py", "src/firelane/publish_web.py"):
        assert rel not in files, (
            f"{rel} 가 판정 지문 안이다 — 판정 코드(segments 쪽)가 import 했다. "
            "발행 범위는 판정에 안 쓴다(DECISIONS §613).")


# ── 발행물 ───────────────────────────────────────────────────

def test_published_scope_tier_equals_the_definition_recomputed():
    """① 모든 구간의 scope_tier 가 정의로 다시 계산한 값과 같다.

    지정(listed)은 소방서 표가 있으면 **정확 재계산**하고, 표가 없는 기계(CI)에서는 발행 칸이 스스로 들고 있는
    근거로 대조한다 — `listed` 는 반드시 동 밖 · 경로 미사용 · `nfa_access_listed` 이고 그 매칭 원문(`nfa_access_token`)의
    주소부에 `road_name` 이 나온다.
    """
    feats = _published()
    assert all("scope_tier" in p for p in feats), "발행물에 scope_tier 가 없다 — publish 를 다시 돌려야 한다"
    assert {p["scope_tier"] for p in feats} <= set(scopetier.TIERS), "정의 밖의 값이 있다"
    rows = fireaccess.load(FIRE) if FIRE.exists() else None
    arows = scopetier.address_rows(rows) if rows else None
    bad = []
    for p in feats:
        if arows is not None:
            want = scopetier.tier(p["in_emd"], p["route_usage"], scopetier.is_designated(p.get("road_name"), arows))
            if p["scope_tier"] != want:
                bad.append((p["seg_uid"], p["scope_tier"], want))
            continue
        # 표 없는 기계 — 기본 두 갈래는 정확히, 지정은 필요조건으로 댄다
        if p["in_emd"]:
            want = "target"
        elif (p["route_usage"] or 0) > 0:
            want = "corridor"
        else:
            want = None
        if want and p["scope_tier"] != want:
            bad.append((p["seg_uid"], p["scope_tier"], want))
        if not want and p["scope_tier"] == "listed":
            tok = scopetier.address_part(p.get("nfa_access_token") or "")
            if not (p["nfa_access_listed"] and p.get("road_name") and p["road_name"].replace(" ", "") in tok.replace(" ", "")):
                bad.append((p["seg_uid"], "listed 인데 근거가 없다", p.get("road_name")))
        if not want and p["scope_tier"] == "reference" and p["nfa_access_listed"] and p.get("road_name"):
            tok = scopetier.address_part(p.get("nfa_access_token") or "")
            if p["road_name"].replace(" ", "") in tok.replace(" ", ""):
                bad.append((p["seg_uid"], "reference 인데 주소부에 나온다", p.get("road_name")))
    assert not bad, f"scope_tier 가 정의와 다르다 {len(bad)}건 — 예: {bad[:3]}"


def test_published_tiers_partition_the_segments_and_none_is_dropped():
    """② 네 묶음의 합 == 발행 구간 수 == 판정이 낸 구간 수. 구간을 하나도 안 떨궜다. 수를 박지 않는다."""
    feats = _published()
    by = {k: sum(1 for p in feats if p["scope_tier"] == k) for k in scopetier.TIERS}
    assert sum(by.values()) == len(feats)
    assert len({p["seg_uid"] for p in feats}) == len(feats), "seg_uid 가 겹친다"
    if PROC.exists():
        judged = json.loads(PROC.read_text(encoding="utf-8"))["features"]
        assert len(feats) == len(judged), (
            f"발행 {len(feats)} ≠ 판정 {len(judged)} — 발행이 구간을 떨궜다. 발행 범위는 이름만 붙이는 것이다(DECISIONS §612-1)")
        assert {p["seg_uid"] for p in feats} == {f["properties"]["seg_uid"] for f in judged}


def test_reference_is_not_counted_in_scope():
    """③ reference 가 발행 범위 집계에 안 섞인다 — 집계는 `IN_SCOPE` 하나로 센다."""
    feats = _published()
    n_scope = sum(1 for p in feats if scopetier.in_scope(p["scope_tier"]))
    by = {k: sum(1 for p in feats if p["scope_tier"] == k) for k in scopetier.TIERS}
    assert n_scope == by["target"] + by["corridor"] + by["listed"]
    assert n_scope + by["reference"] == len(feats)
    assert all(not scopetier.in_scope(p["scope_tier"]) for p in feats if p["scope_tier"] == "reference")
    # 대상지는 동명동 안과 정확히 같다 · 회랑 · 지정 · 참고는 모두 동 밖이다
    assert all((p["scope_tier"] == "target") == bool(p["in_emd"]) for p in feats)


def test_the_matcher_is_alive_not_silently_dead():
    """④ 매처가 조용히 죽으면 지정이 0건이 되고 그 거짓은 초록이다(`nfa_compare` 가 두 번 겪었다). 0건이면 운다."""
    feats = _published()
    assert sum(1 for p in feats if p["scope_tier"] == "listed") > 0, (
        "지정(listed)이 0건이다 — 소방서 표를 못 읽었거나 매처가 죽었다. 조용한 0 은 거짓이다")
    if FIRE.exists():
        assert len(fireaccess.load(FIRE)) > 0, "소방서 표가 비었다"
    # 지정은 항상 동 밖 · 경로 미사용 안에서만 선다
    assert all((not p["in_emd"]) and not (p["route_usage"] or 0) > 0
               for p in feats if p["scope_tier"] == "listed")

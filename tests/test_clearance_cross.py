#!/usr/bin/env python3
"""
test_clearance_cross.py — **자가 맞는가**를 묻는 도구의 판별식과 음성 대조.

── 왜 생겼나 (2026-10-03 · DECISIONS §379) ─────────────────────
`widthcross` 는 값끼리 대고 `width_fn` 은 같은 표본을 다른 통계량으로 본다.
둘 다 **입력이 같다** — 「폴리곤에 법선을 긋고 잰 표본」. 그 표본이 틀리면
둘이 사이좋게 틀린다. 2026-10-03 에 틀린 것이 드러났다 —

    밤실로4번길 한 구간   wmin 58.19m · 경계까지 2.67m · 네이버 실측 5.4~6.0m
    법선 각도를 0~180도 전수로 돌려도 최솟값이 20.5m

**폴리곤은 멀쩡했고 자가 틀렸다.** 그래서 표본을 안 쓰는 증인을 세웠다 —
중심선에서 경계까지의 거리, 곧 내접원의 반지름이다.

★ 이 파일의 핵심은 아래 **음성 대조**다. 네이버 거리재기 실측이 저장소에
  들어왔고(`data/field/naver_width_2610.csv`), 누가 자를 다시 법선으로
  되돌리면 그 자리에서 운다. 종전에는 이런 대조가 **0 건**이었다.

IN    tools/clearance_cross.py · data/field/naver_width_2610.csv
      web/data/{road_area,segments}.geojson
OUT   없음 (검사)
PARAM 없음
밖    **어느 방법이 옳은지는 안 가른다.** 여기가 드는 것은 ① 판별식이
      양방향으로 무는가 ② 실측과 **자릿수**가 맞는가 둘이다. 0.5m 를
      맞추라고 하지 않는다 — 네이버 자의 오차가 그보다 크다.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import clearance_cross as C
import pytest
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
FIELD = ROOT / "data" / "field" / "naver_width_2610.csv"
WEB = ROOT / "web" / "data"


# ── ① 기하 — 합성 도형으로 문다 ────────────────────────────────
def test_the_inscribed_circle_of_a_straight_strip_is_its_width():
    """폭 10 인 곧은 띠에서는 중심선 어디서나 내접원 지름이 10 이다."""
    strip = C._strip(10.0, 400.0)
    cs = C.clearances(LineString([(-100, 0), (100, 0)]), strip.boundary, step=1.0)
    assert cs
    assert abs(2 * min(cs) - 10.0) < 0.01
    assert abs(2 * max(cs) - 10.0) < 0.01


def test_the_ends_of_a_segment_are_left_out():
    """끝점은 교차로 노드다 — 거기 내접원은 이 구간의 것이 아니다."""
    strip = C._strip(10.0, 400.0)
    line = LineString([(-5, 0), (5, 0)])
    assert len(C.clearances(line, strip.boundary, step=1.0)) == int(line.length) - 1


def test_a_segment_shorter_than_the_step_still_gets_one_sample():
    """★ 0 을 내지 않는다 — 0 은 「폭이 없다」가 되고 회색이 숫자로 굳는다."""
    strip = C._strip(10.0, 400.0)
    assert len(C.clearances(LineString([(0, 0), (0.4, 0)]),
                            strip.boundary, step=1.0)) == 1


def test_the_inscribed_circle_never_exceeds_the_circumscribed_one():
    from shapely.geometry import Polygon
    sq = Polygon([(-5, -5), (5, -5), (5, 5), (-5, 5)])
    cs = C.clearances(LineString([(-4, 0), (4, 0)]), sq.boundary, step=1.0)
    assert 2 * max(cs) <= 10.0 * math.sqrt(2) + 0.01


# ── ② 판별식 — 양방향으로 문다 ────────────────────────────────
def _row(**kw):
    base = {"seg_uid": "A", "seg_label": "A", "verdict": "clear",
            "route_usage": 0, "wmin": None, "c_min": None, "c_max": None}
    return {**base, **kw}


def test_a_span_inside_the_largest_inscribed_circle_is_not_an_overshoot():
    assert not C.overshoot([_row(wmin=5.0, c_max=9.0)])


def test_a_span_beyond_every_inscribed_circle_is_an_overshoot():
    """법선이 길을 **가로지른 것이 아니라 따라 나간** 필요조건이다."""
    out = C.overshoot([_row(wmin=50.0, c_max=5.0)])
    assert out and out[0]["배수"] == pytest.approx(10.0)


def test_a_missing_width_is_not_an_overshoot():
    """회색은 넘침이 아니다. 없는 것을 틀렸다고 세면 안 된다."""
    assert not C.overshoot([_row(wmin=None, c_max=5.0)])


def test_a_width_below_the_smallest_inscribed_circle_is_an_inversion():
    assert C.inversion([_row(wmin=2.0, c_min=5.0)])


def test_a_normal_segment_is_not_an_inversion():
    assert not C.inversion([_row(wmin=9.0, c_min=5.0)])


def test_the_tool_passes_its_own_selftest():
    assert C.selftest() == 0


def test_the_ratchets_are_declared_and_named_the_same_as_the_values():
    """선언과 산출의 이름이 갈리면 래칫이 조용히 아무것도 안 본다."""
    assert set(C.RATCHETS) == {"SPAN_OVERSHOOT", "SPAN_INVERSION"}
    assert all(d == "down" for d in C.RATCHETS.values())


# ── ③ 실측 층 — 정본이 제 모양인가 ────────────────────────────
def test_the_field_table_exists_and_carries_its_provenance():
    assert FIELD.exists(), "네이버 실측 표가 없다 — 음성 대조의 밑동이다"
    rows = list(csv.DictReader(FIELD.open(encoding="utf-8")))
    assert rows
    for r in rows:
        assert r["method"] == "naver_ruler"
        assert r["obs_date"]
        assert float(r["w_m"]) > 0
        assert float(r["acc_m"]) > 0, "오차를 안 적으면 정밀도를 참칭한다"
        assert r["spot"] in {"mid", "off", "none"}


def test_some_measurement_is_pinned_to_a_segment():
    """구간이 안 붙은 표는 음성 대조가 못 된다. 하나라도 붙어 있어야 한다."""
    assert C.field_rows(), "seg_uid 가 붙은 실측이 하나도 없다"


# ── ④ ★ 정량 음성 대조 — **대장 명목폭**이 기준이다 ──────────
@pytest.mark.skipif(not (WEB / "road_area.geojson").exists(),
                    reason="환경skip(산출물) — web/data 발행본이 없으면 기하를 못 잰다")
def test_the_ledger_width_sides_with_the_inscribed_circle_not_the_ray():
    """★ 기준은 **도로명주소 도로대장 명목폭**(`road_bt_m`)이다.

    발행본에 결측 0 으로 들어 있고(1,281/1,281), 우리 기하 계산과 방법이
    독립이며, 스키마가 「참고용. 판정에는 안 쓴다」라고 적은 그대로 판정에
    안 들어가 게이트로 오염되지도 않았다.

    ★ **사람이 화면에서 잰 값은 기준이 아니다.** 네이버 거리재기는 ±1m 이고
      어디를 끌었는지도 기록이 없다 — 그것으로 0.5m 를 다투면 주먹구구다.
      그 표의 쓸모는 「그 자리가 어떤 곳인가」(주차 apron · 로터리 · 보도)이고
      이 시험은 그것을 **안 쓴다.**

    ★ 그리고 **「내접원이 낫다」고 주장하지 않는다.** 전수에서 중앙 편차는
      0.21 로 **같다.** 갈리는 것은 꼬리다 — 대장에서 멀리 간 쪽이 어디까지
      가는가. 그 비대칭만 든다.
    """
    res = C.cross(C.load())
    lg = res["대장 대조"]
    assert lg, "대장 명목폭이 발행본에 없다 — 정량 증인이 사라졌다"
    ray, circ = lg["|wmin ÷ 대장 − 1|"], lg["|내접원 ÷ 대장 − 1|"]
    assert circ["max"] < ray["max"] / 2, (
        f"꼬리가 안 갈린다 — 법선 최대 {ray['max']:.2f} · 내접원 {circ['max']:.2f}. "
        "둘이 같아졌으면 자가 고쳐진 것이고, 그러면 §379 를 다시 읽고 지워라")
    assert circ["q75"] <= ray["q75"], (
        f"75% 에서 내접원이 더 멀다 — {circ['q75']:.2f} > {ray['q75']:.2f}")


@pytest.mark.skipif(not (WEB / "road_area.geojson").exists(),
                    reason="환경skip(산출물) — web/data 발행본이 없으면 기하를 못 잰다")
def test_every_segment_the_field_notes_point_at_is_an_overshoot():
    """★ 현장 인사이트의 **올바른 쓰임**이다.

    사람이 항공뷰로 본 것은 「저기가 주차 apron 이다 · 로터리다 · 보도다」이고,
    그것은 **어디를 볼지**를 알려줄 뿐이다. 그 자리가 실제로 결함인가는
    저장소의 제 자료로 판정한다 — 다섯 구간 전부 `넘침`(법선 span 이 그 구간
    최대 내접원보다 크다)에 든다. 사람 눈이 가리키고, 기하가 확인한다.
    """
    want = {r["seg_uid"] for r in C.field_rows()}
    assert want, "구간이 붙은 현장 기록이 없다"
    rows = C.load(only=want)
    over = {o["seg"] for o in C.overshoot(rows)}
    missing = sorted(want - over)
    assert not missing, (
        f"현장에서 지목한 구간이 넘침에 안 든다 — {missing}. "
        "사람이 본 것과 기하가 보는 것이 갈렸다")

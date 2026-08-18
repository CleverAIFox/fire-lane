"""
test_seg_geom.py — 분리된 순수 함수 단위 테스트

`verdict` 는 이 프로젝트의 **결론 그 자체**다(clear/needs_cv/blocked/unknown).
그런데 2026-08-18 Stage 1 리팩 전까지 테스트가 0개였다. `main()` 안에 중첩
정의돼 있어 import 조차 불가능했기 때문이다. 계약 테스트 19종은 판정 문자열이
4개 어휘 안에 있는지만 봤고, **어떤 폭이 어떤 판정을 받아야 하는지**는
아무도 검사하지 않았다.

주석으로만 존재하던 규칙을 여기서 고정한다. 임계값을 건드리면 여기서 걸린다.
"""
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "etl"))

from seg.geom import _dirv, _join, _seal, verdict  # noqa: E402
from seg.params import NODE_TOL, PARK, TRUCK  # noqa: E402


# ── verdict ────────────────────────────────────────────────────
def test_below_truck_is_blocked():
    """차량 전폭 하한 미달. 장애물이 없어도 못 지나간다."""
    assert verdict(1.0, TRUCK - 0.01) == "blocked"


def test_at_truck_is_not_blocked():
    """경계값은 통과 쪽이다. 3.0 은 blocked 가 아니다."""
    assert verdict(None, TRUCK) != "blocked"


def test_wide_enough_is_clear():
    """양쪽 주차가 있어도 통과 = 영상판정 불필요."""
    assert verdict(TRUCK + 2 * PARK, 20.0, nreg=5) == "clear"


def test_single_sample_never_gets_clear():
    """
    ★ 표본 1개로는 clear 를 주지 않는다.

    DM02825(동계천로95번길)는 표본 하나가 교차로를 대각선으로 가로질러
    42.1m 가 나왔고 그것이 wmin 이 되어 clear 로 판정됐다. 실제로는
    사거리 한복판이다. clear 는 '영상판정조차 필요 없다'는 가장 강한
    주장이라 근거가 필요하다.
    """
    assert verdict(42.1, 45.0, nreg=1) == "needs_cv"
    assert verdict(42.1, 45.0, nreg=2) == "clear"


def test_single_sample_still_gets_blocked():
    """blocked 는 막는 쪽이라 표본 1개여도 유지한다(미탐:오탐 = 100:1)."""
    assert verdict(1.0, 2.0, nreg=1) == "blocked"


def test_wmax_missing_is_not_failure():
    """
    ★ 대로는 건물이 WMAX_CAP 밖이라 담~담을 못 잰다. 실패가 아니다.

    이 규칙이 없어서 필문대로·밤실로 같은 대로 392구간이 회색으로 떨어졌다.
    """
    assert verdict(5.0, None) == "needs_cv"


def test_no_width_is_unknown():
    assert verdict(None, None) == "unknown"


def test_blocked_wins_over_clear():
    """wmax 가 하한 미달이면 wmin 이 아무리 커도 blocked 다. 순서가 중요하다."""
    assert verdict(100.0, 1.0, nreg=9) == "blocked"


@pytest.mark.parametrize("wmin,wmax,nreg,want", [
    (None, None, None, "unknown"),
    (2.0, 2.5, 3, "blocked"),
    (4.0, 5.0, 3, "needs_cv"),
    (7.0, 9.0, 3, "clear"),
    (7.0, 9.0, 1, "needs_cv"),
])
def test_verdict_table(wmin, wmax, nreg, want):
    """판정 4종 대표 케이스. 임계값을 바꾸면 여기가 먼저 깨진다."""
    assert verdict(wmin, wmax, nreg) == want


# ── _seal ──────────────────────────────────────────────────────
def test_seal_closes_hairline_gap():
    """
    ★ mm 단위로 어긋난 인접면을 붙인다.

    붙지 않으면 얇은 틈이 경계선으로 남고 법선이 거기서 끊겨 폭이 0.5m 로
    나온다(중앙로 실측 사례).
    """
    a = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    b = Polygon([(10.05, 0), (20, 0), (20, 10), (10.05, 10)])   # 5cm 틈
    u = _seal([a, b])
    assert u.geom_type == "Polygon", "틈이 안 닫혀 MultiPolygon 으로 남았다"


def test_seal_keeps_disjoint_apart():
    """멀리 떨어진 것까지 붙이면 안 된다. 0.15m 버퍼가 상한이다."""
    a = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    b = Polygon([(50, 0), (60, 0), (60, 10), (50, 10)])
    assert _seal([a, b]).geom_type == "MultiPolygon"


# ── _dirv ──────────────────────────────────────────────────────
def test_dirv_points_inward_from_each_end():
    """어느 끝에서 보든 형상 안쪽을 향한다."""
    g = LineString([(0, 0), (10, 0)])
    assert _dirv(g, (0, 0)) == pytest.approx((1.0, 0.0))
    assert _dirv(g, (10, 0)) == pytest.approx((-1.0, 0.0))


def test_dirv_is_unit_length():
    g = LineString([(0, 0), (30, 40)])
    dx, dy = _dirv(g, (0, 0))
    assert (dx ** 2 + dy ** 2) == pytest.approx(1.0)


# ── _join ──────────────────────────────────────────────────────
def test_join_welds_at_midpoint():
    """
    노드 접합으로 끝점이 최대 NODE_TOL 어긋나 linemerge 가 실패한다.
    중점으로 용접해 틈을 없앤다.
    """
    a = LineString([(0, 0), (10, 0)])
    b = LineString([(10.4, 0), (20, 0)])
    j = _join(a, b)
    assert j is not None
    assert j.coords[0] == (0, 0) and j.coords[-1] == (20, 0)
    assert j.is_valid


def test_join_refuses_when_too_far():
    """NODE_TOL*2 를 넘으면 붙이지 않는다. 없는 연결을 만들면 안 된다."""
    a = LineString([(0, 0), (10, 0)])
    b = LineString([(10 + NODE_TOL * 2 + 0.1, 0), (20, 0)])
    assert _join(a, b) is None


def test_join_handles_reversed_direction():
    """형상 방향이 반대로 저장돼 있어도 가까운 끝끼리 붙인다."""
    a = LineString([(10, 0), (0, 0)])
    b = LineString([(20, 0), (10.2, 0)])
    j = _join(a, b)
    assert j is not None and j.length == pytest.approx(20.0, abs=0.5)


# ── 정본 위치 ──────────────────────────────────────────────────
def test_params_are_not_redefined_in_segments():
    """
    ★ 임계값 정본은 seg/params.py 하나다(R3).

    쪼개는 과정에서 조각들이 각자 숫자를 들고 가면 정본이 깨진다.
    그때는 segments.py 만 고치고 web/config.js 사본은 그대로 두는 식의
    어긋남이 조용히 생긴다.
    """
    src = (ROOT / "src/etl/segments.py").read_text(encoding="utf-8")
    for name in ("TRUCK", "PARK", "NODE_TOL", "COV_MIN", "WMAX_CAP"):
        assert f"\n{name}" not in src.replace(f"\n{name}_", "\n_"), (
            f"{name} 이 segments.py 에서 재정의됐다 — 정본은 seg/params.py")

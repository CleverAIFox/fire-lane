"""
test_seg_width.py — 폭 산출 단위 테스트

`ngii1k 1014 · silpok 84 · ngii 1` 을 만드는 코드다. 소스 우선순위(결정 63),
표본 snap, 커버율 자격(COV_MIN)이 전부 여기서 갈린다. Stage 3 리팩 전까지
`main()` 안에 중첩돼 있어 테스트가 0개였다.

golden 은 "리팩 전후가 같은가"만 본다. 지금 값이 **옳은가**는 안 본다.
그 자리를 여기서 메운다 — 합성 도형으로 정답을 아는 상황을 만들어 검사한다.

★ 실제 데이터가 아니라 사각형 도로면을 쓴다. 실측 검증은 D-25 이고,
  여기서 지키는 것은 "규칙이 코드에 살아 있는가"다.
"""
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "etl"))

from seg.params import COV_MIN, SNAP_MAX, SNAP_TRUST, WMAX_CAP  # noqa: E402
from seg.width import WidthEngine  # noqa: E402


def road(width_m: float, length: float = 100.0, y0: float = 0.0):
    """y0 을 중심으로 폭 width_m 인 직선 도로면."""
    h = width_m / 2.0
    return Polygon([(-10, y0 - h), (length + 10, y0 - h),
                    (length + 10, y0 + h), (-10, y0 + h)])


EMPTY = unary_union([])          # 건물 0건. 운영에서도 None 이 아니라 빈 기하다.


def engine(ngii1k=None, ngii=None, rw=None, bld=None, xn=None, xsec=None):
    return WidthEngine(ngii1k, ngii, rw, EMPTY if bld is None else bld,
                       xn if xn is not None else MultiPoint([(-9999, -9999)]),
                       xsec)


CENTER = LineString([(0, 0), (100, 0)])


# ── 기본 측정 ──────────────────────────────────────────────────
def test_measures_road_width():
    """폭 6m 도로면 위 중심선을 재면 6m 가 나와야 한다."""
    wx = engine(ngii1k=road(6.0))
    wmin, wmax, fb, wsrc, wdis, rsn, cov = wx.widths(CENTER)
    assert wmin == pytest.approx(6.0, abs=0.05)
    assert wsrc == "ngii1k"


def test_narrowest_point_becomes_wmin():
    """구간 폭은 최솟값이다. 병목이 통행 가능 여부를 정한다."""
    wide = road(8.0, length=100)
    pinch = Polygon([(40, -1.0), (60, -1.0), (60, 1.0), (40, 1.0)])
    # 40~60 구간만 2m 로 좁아지는 도로
    body = Polygon([(-10, -4), (40, -4), (40, -1), (60, -1), (60, -4),
                    (110, -4), (110, 4), (60, 4), (60, 1), (40, 1),
                    (40, 4), (-10, 4)])
    assert wide.is_valid and pinch.is_valid
    wx = engine(ngii1k=body)
    wmin, wmax, *_ = wx.widths(CENTER)
    assert wmin == pytest.approx(2.0, abs=0.2), "병목을 못 잡았다"


# ── 소스 우선순위 (결정 63) ────────────────────────────────────
def test_priority_prefers_ngii1k():
    """세 소스가 모두 덮으면 1:1,000 을 쓴다."""
    wx = engine(ngii1k=road(6.0), ngii=road(9.0), rw=road(12.0))
    assert wx.widths(CENTER)[3] == "ngii1k"


def test_falls_through_to_next_source():
    """주 소스가 없으면 다음 순위가 자동으로 올라온다."""
    assert engine(ngii=road(9.0), rw=road(12.0)).widths(CENTER)[3] == "ngii"
    assert engine(rw=road(12.0)).widths(CENTER)[3] == "silpok"


def test_no_source_gives_no_width():
    """소스가 하나도 없으면 폭이 안 나온다. 조용히 0 을 만들지 않는다."""
    wmin, wmax, *_ = engine().widths(CENTER)
    assert wmin is None


# ── 커버율 자격 (COV_MIN) ──────────────────────────────────────
def test_thin_coverage_source_is_disqualified():
    """
    ★ 구간의 절반 미만을 잰 소스는 대표시키지 않는다.

    준법로(DM01608)는 ngii 가 26표본 중 1개(cov 0.038)를 쟀고 그 값 53.2m 가
    구간 폭이 됐다. 나머지 23개는 silpok 1.30m 였다. width_min>30m 47구간이
    전부 clear 로 판정되던 원인이다(미탐 방향).
    """
    # ngii1k 가 구간 끝 10m 만 덮고, 그마저 아주 넓다
    sliver = Polygon([(0, -20), (10, -20), (10, 20), (0, 20)])
    wx = engine(ngii1k=sliver, rw=road(1.3))
    wmin, wmax, fb, wsrc, *_ = wx.widths(CENTER)
    assert wsrc != "ngii1k", f"커버율 미달 소스가 채택됐다 (cov<{COV_MIN})"
    assert wmin == pytest.approx(1.3, abs=0.2)


# ── snap ───────────────────────────────────────────────────────
def test_snaps_center_line_onto_offset_road_surface():
    """
    도로명주소 중심선은 위상용이라 실측 노면과 어긋난다.
    재는 지점만 가장 가까운 노면 안으로 끌어온다.
    """
    wx = engine(ngii1k=road(6.0, y0=2.0))     # 노면이 2m 위로 밀려 있다
    wmin, *_ = wx.widths(CENTER)
    assert wmin is not None, "어긋난 노면을 snap 으로 못 따라갔다"


def test_gives_up_beyond_snap_max():
    """SNAP_MAX 를 넘게 떨어진 노면은 이 구간의 것이 아니다."""
    wx = engine(ngii1k=road(6.0, y0=SNAP_MAX + 10.0))
    assert wx.widths(CENTER)[0] is None


# ── wmax (담~담) ───────────────────────────────────────────────
def test_wmax_uses_buildings():
    """담~담은 건물 사이 거리다. 도로면보다 넓다."""
    walls = unary_union([Polygon([(-10, 5), (110, 5), (110, 9), (-10, 9)]),
                         Polygon([(-10, -9), (110, -9), (110, -5), (-10, -5)])])
    wmin, wmax, *_ = engine(ngii1k=road(6.0), bld=walls).widths(CENTER)
    assert wmax == pytest.approx(10.0, abs=0.5)
    assert wmax > wmin


def test_wmax_is_none_without_buildings():
    """
    ★ 건물이 없으면 wmax 가 없다. 실패가 아니다.

    대로는 건물이 WMAX_CAP 밖이라 벽 사이를 잴 수 없고, 그런 구간은
    도로폭만으로 이미 판정이 끝난다. (법원·검찰청처럼 건물 데이터가
    비어 있는 필지도 같은 경로를 탄다.)
    """
    wmin, wmax, *_ = engine(ngii1k=road(6.0)).widths(CENTER)
    assert wmin is not None and wmax is None


def test_wmax_capped():
    """담~담 상한. 15m 로 잡으면 대로가 전멸한다."""
    far = unary_union([Polygon([(-10, 200), (110, 200), (110, 210), (-10, 210)]),
                       Polygon([(-10, -210), (110, -210), (110, -200), (-10, -200)])])
    wmin, wmax, *_ = engine(ngii1k=road(6.0), bld=far).widths(CENTER)
    assert wmax is None or wmax <= WMAX_CAP


# ── 교차부 제외 ────────────────────────────────────────────────
def test_short_fragment_still_measured():
    """
    ★ 교차로 파편(길이 < MIN_SEG_LEN)은 정의상 전 구간이 교차로 안이다.

    제외를 그대로 적용하면 표본이 0 개가 되어 폭이 안 나오고, 그 구간이
    산출물에서 통째로 사라진다. 짧은 조각은 제외를 풀고 중점 한 점이라도 잰다.
    """
    frag = LineString([(0, 0), (2.0, 0)])
    wx = engine(ngii1k=road(6.0), xn=MultiPoint([(1.0, 0)]))
    assert wx.widths(frag)[0] is not None, "짧은 조각이 통째로 사라진다"


def test_intersection_samples_excluded():
    """교차로 한복판 표본은 뺀다. 안 빼면 대각선 관통으로 폭이 폭발한다."""
    wx = engine(ngii1k=road(6.0), xn=MultiPoint([(50, 0)]))
    long_seg = LineString([(0, 0), (100, 0)])
    assert wx.widths(long_seg)[0] == pytest.approx(6.0, abs=0.3)


# ── 상태 묶음 ──────────────────────────────────────────────────
def test_engine_state_is_explicit():
    """
    ★ 폭 소스 5종은 항상 같이 움직인다.

    Stage 3 전에는 `main()` 로컬로 흩어져 `measure`/`widths` 가 폐포로
    잡고 있었다. 하나를 바꾸면 어디까지 영향이 가는지 읽어낼 수 없었다.
    """
    wx = engine(ngii1k=road(6.0))
    for f in ("ngii1k_u", "ngii_u", "rw_u", "bld_u", "xn", "xsec_poly"):
        assert hasattr(wx, f), f"{f} 가 엔진 상태에 없다"

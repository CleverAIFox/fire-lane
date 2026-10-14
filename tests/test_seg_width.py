"""
test_seg_width.py — 폭 산출 단위 테스트

`ngii1k 1162 · silpok 116 · ngii 1` 을 만드는 코드다. 소스 우선순위(결정 63),
표본 snap, 커버율 자격(COV_MIN)이 전부 여기서 갈린다. Stage 3 리팩 전까지
`main()` 안에 중첩돼 있어 테스트가 0개였다.

golden 은 "리팩 전후가 같은가"만 본다. 지금 값이 **옳은가**는 안 본다.
그 자리를 여기서 메운다 — 합성 도형으로 정답을 아는 상황을 만들어 검사한다.

★ 실제 데이터가 아니라 사각형 도로면을 쓴다. 실측 검증은 D-25 이고,
  여기서 지키는 것은 "규칙이 코드에 살아 있는가"다.
"""
import re
from pathlib import Path

import pytest
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

from firelane.seg.params import COV_MIN, ESCAPE_M, RAY_M, SNAP_MAX, WMAX_CAP
from firelane.seg.width import WidthEngine, carve_walk, walk_spans

ROOT = Path(__file__).resolve().parents[1]
def road(width_m: float, length: float = 100.0, y0: float = 0.0):
    """y0 을 중심으로 폭 width_m 인 직선 도로면."""
    h = width_m / 2.0
    return Polygon([(-10, y0 - h), (length + 10, y0 - h),
                    (length + 10, y0 + h), (-10, y0 + h)])


EMPTY = unary_union([])          # 건물 0건. 운영에서도 None 이 아니라 빈 기하다.


def engine(ngii1k=None, ngii=None, rw=None, bld=None, xn=None, xsec=None,
           walk=None):
    return WidthEngine(ngii1k, ngii, rw, EMPTY if bld is None else bld,
                       xn if xn is not None else MultiPoint([(-9999, -9999)]),
                       xsec, walk_u=walk)


def band(y0: float, y1: float, length: float = 100.0):
    """`y0`~`y1` 에 깔린 띠. 보도면 자리에 쓴다."""
    return Polygon([(-10, y0), (length + 10, y0), (length + 10, y1), (-10, y1)])


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


def test_width_source_priority_has_one_home():
    """폭 소스 우선순위가 **한 곳**에만 사는가.

    ★ 2026-09-24 (PLAN §1 #125 · DECISIONS §245). 이 순서가 `seg/width.py`
      한 파일 안에서 **아홉 번** 재기술되고 있었다. 「결정 63」은 이 저장소에서
      가장 많이 인용되는 규칙인데, 순서를 바꾸려면 아홉 곳을 고쳐야 했다 —
      R3(정본 하나)가 **판정 핵심 안에서** 깨져 있던 자리다.

    ★ 보는 것은 「세 이름이 한 줄에 같이 나오는가」다. 값 하나가 아니라
      **순서**가 사실이므로 SPEC(값 대조)으로는 못 잡는다.
    """

    from firelane.seg.params import WIDTH_SRCS

    assert WIDTH_SRCS == ("ngii1k", "ngii", "silpok"), WIDTH_SRCS
    home = ROOT / "src/firelane/seg/params.py"
    pat = re.compile(r'"ngii1k"[^\n]*"ngii"[^\n]*"silpok"')
    bad = []
    for p in sorted((ROOT / "src/firelane").rglob("*.py")):
        if p == home:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue          # 주석은 사본이 아니다
            if pat.search(line):
                bad.append(f"{p.relative_to(ROOT)}:{i}  {line.strip()[:70]}")
    assert not bad, (
        "폭 소스 우선순위가 `seg/params.py::WIDTH_SRCS` 밖에서 또 쓰였다:\n  "
        + "\n  ".join(bad)
        + "\n  순서가 곧 규칙이다 — 두 벌이면 한쪽만 고치는 날이 온다(결정 63).")


def test_width_diagnosis_selects_by_width_not_by_verdict():
    """「폭 미산출 진단」이 **폭으로** 고른다 (DECISIONS §417).

    종전 선택자는 `g.unknown_reason == "width"` 였다. 이름은 폭인데 **고르는 기준이
    판정**이라, 폭이 안 나왔는데 대장폭으로 `blocked` 가 난 구간은 진단에서 통째로
    빠졌다. 발행본으로 재면 종전 기준은 **0구간**이고 새 기준은 2구간이다 —
    `DM03310` · `DM03311`(동계로15번길). 둘은 전체에서 유일하게 `n_try=0` 으로
    **트랜섹트를 한 발도 안 쐈는데** 어느 자리에도 그 사실이 안 적혔다.

    진단이 0건을 보고 「이상 없음」을 찍는 것이 제일 나쁜 꼴이다.
    """
    src = (ROOT / "src" / "firelane" / "seg" / "report.py").read_text(encoding="utf-8")
    # 주석이 아니라 **선택자 줄** 하나를 본다 — 옛 기준은 주석에 역사로 남아 있다
    pick = [ln.strip() for ln in src.splitlines()
            if ln.strip().startswith("_w = g[")]
    assert len(pick) == 1, f"폭 진단 선택자가 하나가 아니다: {pick}"
    assert "width_min_m.isna()" in pick[0], (
        f"진단이 폭으로 안 고른다 — blocked 가 빠진다(§417): {pick[0]}")
    assert "n_try == 0" in src, "한 발도 안 쏜 구간을 따로 세지 않는다"


# ── 한쪽이 샜을 때 (2026-10-13 · DECISIONS §510 → §516 → §519) ──
def _plaza(lane: float, plaza: float):
    """한쪽은 `lane/2` 에서 벽, 반대쪽은 `plaza` 까지 열린 도로면.

    실물의 꼴이다 — 밤실로4번길 1-11 은 한쪽이 지산복지회관 앞 포장 광장과
    연석 없이 이어져 있고, 네이버 실측은 **5.4m** 다(`data/field`).
    """
    h = lane / 2.0
    return Polygon([(-10, -h), (110, -h), (110, plaza), (-10, plaza)])


def test_one_side_running_off_is_not_half_a_width():
    """**이 판의 머리다.** 한쪽이 광장으로 새면 좌우합은 폭이 아니다.

    §510 이 쟀고 §516 이 한 판 미뤘고 §519 가 **값 규칙만** 고쳐 넣는다.
    """
    wx = engine(ngii1k=_plaza(lane=6.0, plaza=50.0))
    wmin, *_ = wx.widths(CENTER)
    assert wmin == pytest.approx(6.0, abs=0.2), (
        "샌 쪽을 더해 폭으로 냈다 — 가까운 쪽 × 2 여야 한다")


def test_the_escape_rule_is_reachable():
    """**죽은 문을 되살렸다는 증거.** 문턱이 광선보다 짧아야 닫힐 수 있다."""
    assert ESCAPE_M < RAY_M, (
        "문턱이 광선 길이 이상이면 한쪽 거리가 그 값을 넘을 수 없다 — "
        "조건이 영원히 거짓이고 그것이 2026-10-13 까지의 상태였다")
    assert ESCAPE_M < WMAX_CAP, "합의 상한보다도 작아야 한쪽 검사가 먼저 문다"


def test_admission_is_decided_by_the_sum_not_by_the_escape_value():
    """**§519 의 머리.** 입장은 `l+r` 이 정한다 — 값 규칙이 입장을 못 바꾼다.

    §510 의 결함이 이것이었다. `2·min` 을 `range` 검사에 먹이면 `l+r ≥ 60` 인
    표본이 **통과한다** — 종전에는 버려졌다. 그러면 덮임이 올라가고 구간 수가
    움직인다(실측 1,281 → 1,285). 아래가 그 경계를 **양방향**으로 민다.
    """
    # ① l+r 이 상한을 넘는 표본: 한쪽 3m + 반대쪽 58m → 합 61 ≥ WMAX_CAP
    #    종전에도 버려졌고 지금도 버려져야 한다. `2·min`(6.0)이 상한 아래라서
    #    §510 판에서는 **통과했다** — 그것이 구간 수를 움직인 자리다.
    wide = engine(ngii1k=_plaza(lane=6.0, plaza=WMAX_CAP - 2.0))
    got, *_ = wide.widths(CENTER)
    assert got is None, (
        f"`l+r`({3.0 + WMAX_CAP - 2.0:.1f}) 가 상한을 넘는데 통과시켰다 — {got}. "
        "값 규칙이 입장을 바꿨다(DECISIONS §519)")

    # ② 합이 상한 아래면 샌 쪽이어도 통과하고 값은 가까운 쪽 × 2 다
    ok_, *_ = engine(ngii1k=_plaza(lane=6.0, plaza=50.0)).widths(CENTER)
    assert ok_ == pytest.approx(6.0, abs=0.2)


def test_a_zero_escape_span_is_missing_not_narrow():
    """**0 은 「좁다」가 아니라 「못 쟀다」다**(DECISIONS 534).

    ★ 측정 대장 `escape-tiny` 가 **실측으로 났다.** `DM01391`(2순환로 539m)의
      `width_min_m` 이 **0.00** 으로 발행되고 `segcontract` 의
      `WIDTH_OUT_OF_RANGE` 가 0 → 1 로 울었다. 대로가 폭 0 일 수 없다.

    꼴은 **중심선이 도로면 경계에 붙은 것**이다 — 한쪽 거리가 0 이면
    `2·min` 이 0 이고, 입장은 깎지 않은 `l+r`(=50.0)로 이미 통과했다.

    ★ **하한을 세우지 않는다.** 대장이 적은 셋째 규칙(「가까운 쪽의 하한」)은
      그 구간이 실제 비대칭 골목일 때의 길이고, 2순환로는 `cov 0.408` 의
      고가·교차로라 지오메트리 결함 쪽이다. 아래 ②가 **하한이 없다는 것**을
      민다 — 0.2 는 0.3 아래인데 **살아 있어야** 한다.
    """
    # ① 중심선이 경계 위 — 한쪽 거리 0 → 표본을 버린다
    got = engine(ngii1k=_plaza(lane=0.0, plaza=50.0)).widths(CENTER)
    assert got[0] is None, (
        f"`2·min` 이 0 인데 {got[0]} 을 폭으로 냈다 — 0 은 수가 아니라 결측이다")
    assert "escape_zero" in (got[5] or ""), (
        f"사유가 `escape_zero` 가 아니다 — {got[5]!r}. 사유가 틀리면 "
        "`width_fail` 집계가 이 자리를 다른 병으로 센다")

    # ② 0.3 **아래**여도 0 이 아니면 산다 — 하한을 안 세웠다는 증거
    thin, *_ = engine(ngii1k=_plaza(lane=0.2, plaza=50.0)).widths(CENTER)
    assert thin == pytest.approx(0.2, abs=0.01), (
        f"0.2 를 버렸다 — {thin}. 그것은 **하한을 세운 것**이고 측정 대장 "
        "`escape-tiny` 의 ③ 이 그 길을 조건부로만 열어 뒀다(비대칭 골목일 때)")


def test_the_value_never_goes_up():
    """`2·min ≤ l+r` — 구조적으로 보장된다. 틀려도 **안전한 쪽**이다."""
    for lane, plaza in ((1.5, 40.0), (6.0, 25.0), (12.0, 21.0), (3.0, 19.9)):
        wx = engine(ngii1k=_plaza(lane=lane, plaza=plaza))
        got, *_ = wx.widths(CENTER)
        if got is not None:
            assert got <= lane / 2.0 + plaza + 1e-6, (
                f"폭이 좌우합보다 커졌다 — lane {lane} · plaza {plaza} → {got}")


def test_a_tiny_near_side_is_kept_not_dropped():
    """`2·min` 이 0.3 아래로 떨어져도 **버리지 않는다.**

    버리면 입장이 바뀌고 구간 수가 움직인다(§519). 작은 수는 그 구간을
    `blocked` 로 보내므로 **안전한 쪽**이고, 그런 표본이 실물에 몇 개인지는
    측정 대장 `escape-tiny` 가 든다 — 재기 전에 판정 기준을 적어 뒀다.
    """
    wx = engine(ngii1k=_plaza(lane=0.2, plaza=30.0))   # 가까운 쪽 0.1m
    got, *_ = wx.widths(CENTER)
    assert got is None or got < 0.3, (
        f"가까운 쪽 0.1m 인데 {got} 가 나왔다 — 2·min 을 안 쓴다")


def test_a_wide_but_bounded_road_still_uses_the_sum():
    """**대로를 죽이지 않는다.** 양쪽이 다 막혀 있으면 좌우합 그대로다."""
    wx = engine(ngii1k=road(2 * ESCAPE_M - 2.0))      # 한쪽 19m — 안 샌다
    wmin, *_ = wx.widths(CENTER)
    assert wmin == pytest.approx(2 * ESCAPE_M - 2.0, abs=0.1)


def test_both_sides_running_off_still_gets_a_number():
    """양쪽이 다 새면 **0 을 내지 않는다** — 0 은 회색이 숫자로 굳는 자리다."""
    wx = engine(ngii1k=Polygon([(-200, -200), (200, -200), (200, 200), (-200, 200)]))
    wmin, *_ = wx.widths(CENTER)
    assert wmin is None or wmin > 0


# ── 보도 차감 (PLAN #146 · DECISIONS §523) ──────────────────────
def test_sidewalk_is_subtracted_from_the_roadway():
    """차량이 못 가는 면은 폭이 아니다. 8m 노면 양쪽 1m 보도 → 6m."""
    wx = engine(ngii1k=road(8.0), walk=unary_union([band(-4, -3), band(3, 4)]))
    wmin, *_ = wx.widths(CENTER)
    assert wmin == pytest.approx(6.0, abs=0.1), (
        f"보도 2m 를 안 깎았다 — {wmin}")


def test_without_the_sidewalk_layer_the_number_is_the_old_one():
    """**기본 경로가 종전이다.** 자료 없는 기계에서 다른 수가 나오지 않는다."""
    assert engine(ngii1k=road(8.0)).widths(CENTER)[0] == pytest.approx(8.0, abs=0.1)


def test_an_escaped_ray_does_not_eat_someone_elses_sidewalk():
    """**이 판의 머리다.** 샌 광선이 만난 보도는 **남의 도로의** 것이다.

    §512-1 ③ 의 실물 — 필문대로289번길은 2m 안에 보도면이 **하나도 없는데**
    차감으로 6.14 → 0.70 이 됐다. 광선이 escape 100% 로 본선에 새 나가고,
    본선의 보도를 깎으면 **샌 쪽이 짧아져 escape 탐지기가 꺼진다.**
    차감을 escape **뒤에** 두면 그 경로가 막힌다.
    """
    wx = engine(ngii1k=_plaza(lane=6.0, plaza=50.0), walk=band(8, 12))
    wmin, *_ = wx.widths(CENTER)
    assert wmin == pytest.approx(6.0, abs=0.2), (
        f"{wmin} 가 나왔다. 차감을 escape **앞에** 두면 샌 쪽이 50 → 8 로 "
        "짧아져 `max ≥ ESCAPE_M` 이 꺼지고 좌우합 11 이 폭으로 나간다 — "
        "순서가 규칙이다(DECISIONS §523)")


def test_admission_still_uses_the_uncarved_sum():
    """입장은 **깎지 않은** 합이 정한다 — 차감이 구간 수를 못 움직인다.

    §519 가 `2·min` 으로 한 번 지킨 그 경계다. 깎으면 통과할 표본을 만들어
    **양방향**으로 민다 — 한쪽만 밀면 빈 그물이 초록이다.
    """
    shape = _plaza(lane=6.0, plaza=WMAX_CAP - 2.0)     # 생합 61 ≥ 상한
    assert engine(ngii1k=shape).widths(CENTER)[0] is None
    got, *_ = engine(ngii1k=shape, walk=band(50, 55)).widths(CENTER)
    assert got is None, (
        f"깎으면 합이 53 이 되어 통과했다 — {got}. 입장 검사가 깎인 수를 봤다")


def test_a_point_on_the_sidewalk_is_carved_by_nothing_and_dropped_by_nothing():
    """재는 점이 보도 위면 **안 깎고, 버리지도 않는다**(§512-1 · §523-2).

    버림의 효과가 64구간 전부에서 0 임을 쟀다. 효과 없는 가드는 다음 사람이
    무엇을 막는지 모른 채 영영 남는다.
    """
    wx = engine(ngii1k=road(8.0), walk=band(-1, 1))
    wmin, *_ = wx.widths(CENTER)
    assert wmin == pytest.approx(8.0, abs=0.1), (
        f"중심선이 보도 위인 표본을 깎거나 버렸다 — {wmin}")


def test_carving_never_raises_the_width():
    """깎기는 **내리는 쪽으로만** 틀린다(MASTER §3-5a)."""
    for w, (a, b) in ((8.0, (3.0, 4.0)), (12.0, (5.0, 6.0)), (3.0, (1.0, 1.5))):
        bare = engine(ngii1k=road(w)).widths(CENTER)[0]
        cut = engine(ngii1k=road(w),
                     walk=unary_union([band(-b, -a), band(a, b)])).widths(CENTER)[0]
        assert cut is not None and bare is not None
        assert cut <= bare + 1e-6, f"깎았는데 폭이 올라갔다 — {bare} → {cut}"


def test_a_width_carved_below_the_floor_is_kept_not_dropped():
    """깎은 합이 0.3 아래여도 **버리지 않는다** — 버리면 입장이 바뀐다(§519).

    그런 표본이 실물에 몇 개인지는 측정 대장 `walk-tiny` 가 든다.
    """
    wx = engine(ngii1k=road(8.0),
                walk=unary_union([band(-4, -0.05), band(0.05, 4)]))
    wmin, *_ = wx.widths(CENTER)
    assert wmin is not None and 0 < wmin < 0.3, (
        f"0.1m 가 나와야 하고 **0 도 None 도 아니어야** 한다 — {wmin}")


def test_carve_walk_keeps_only_the_piece_holding_zero():
    """순수 함수를 직접 민다. 보도 **섬**이 여러 개여도 가까운 턱이 이긴다."""
    assert carve_walk(10.0, 10.0, []) == (10.0, 10.0)
    assert carve_walk(5.0, 5.0, [(-1.0, 2.0)]) == (5.0, 5.0)   # 0 을 담았다
    got = carve_walk(10.0, 10.0, [(-20.0, -18.0), (-8.0, -6.0),
                                  (3.0, 5.0), (7.0, 9.0)])
    assert got == (6.0, 3.0), f"가장 가까운 턱이 아니다 — {got}"


def test_walk_spans_projects_the_sidewalk_onto_the_ray():
    """광선 × 보도면 → 1차원 구간. `p` 가 원점이고 **정렬돼** 나온다."""
    ray = LineString([(0, -10), (0, 10)])
    p, ux, uy = Point(0, 0), 0.0, 1.0
    got = walk_spans(ray, unary_union([band(3, 4), band(-6, -5)]), p, ux, uy)
    assert [(round(a, 3), round(b, 3)) for a, b in got] == [(-6.0, -5.0), (3.0, 4.0)]
    assert walk_spans(ray, band(40, 41), p, ux, uy) == [], "안 만나는데 구간을 냈다"


def test_walk_spans_ignores_a_grazed_curb():
    """경계를 **스친** 교차는 점이라 폭을 안 깎는다 — `_span` 의 `tangent` 와 같은 자."""
    ray = LineString([(0, -10), (0, 10)])
    graze = Polygon([(0, 2), (5, 2), (5, 6), (0, 6)])      # 광선이 모서리에 접한다
    got = walk_spans(ray, graze, Point(0, 0), 0.0, 1.0)
    assert all(b - a > 0 for a, b in got), f"길이 0 인 구간을 냈다 — {got}"

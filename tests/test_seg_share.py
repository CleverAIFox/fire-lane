"""
test_seg_share.py — `#77` 가름 규칙: 한 폴리곤에 중심선이 둘 이상이면 구간은 **자기 몫** 안에서만 폭을 잰다. (Zm56 · DECISIONS §593 · 설계 §588-2)

IN    src/firelane/seg/share.py (`ShareCarver`) · src/firelane/seg/width.py (`WidthEngine.carver`)
OUT   없음 (검사)
밖    **실제 데이터에서 맞게 가르는가는 안 본다** — 합성 사각형이다. 실측(링크 `도로폭` ±40% 적중률 · 판정 이동)은 DECISIONS §593 이 든다.

★ 합성 기하로 정답을 아는 상황을 만든다 — 폭 50m 띠(y = -25 ~ 25) 한가운데(y = 0)에 「가길」, 한쪽(y = 22)에 이름이 다른 「나길」이 있다. 양쪽이 다 20m(`ESCAPE_M`) 이상 열린
  가운데 길은 한 폴리곤으로 재면 `2·min = 50m` 가 나오고(합쳐진 값 — `DM01876` 의 모양), 몫(y < 11)으로 재면 아래 25m · 위 11m 라 `2·min = 22m` 가 나온다.
"""
import pytest
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.ops import unary_union

from firelane.seg import share
from firelane.seg.share import ShareCarver
from firelane.seg.width import WidthEngine

EMPTY = unary_union([])
A = LineString([(0, 0), (100, 0)])         # 「가길」 — 대장폭 8 · 띠 한가운데
B = LineString([(0, 22), (100, 22)])       # 「나길」 — 대장폭 8 · 띠 가장자리(위 3m 가 벽)


def strip(width: float = 50.0) -> Polygon:
    h = width / 2
    return Polygon([(-10, -h), (110, -h), (110, h), (-10, h)])


def _links(*, same_name: bool = False, nameless: bool = False):
    return [(A, "가길", 8.0), (B, "가길" if same_name else ("" if nameless else "나길"), 8.0)]


def _ref(name="가길", bt=8.0):
    return lambda g: (name, bt)


def engine(carver=None, poly=None):
    return WidthEngine(poly or strip(), None, None, EMPTY, MultiPoint([(-9999, -9999)]), None, carver=carver)


def test_without_a_carver_two_roads_in_one_polygon_measure_the_merged_width():
    """종전 동작(결함의 재현): 한 폴리곤이면 이웃 도로의 몫까지 합쳐 50m 가 나온다."""
    assert engine().widths(A)[0] == pytest.approx(50.0, abs=0.1)


def test_each_road_measures_only_its_own_share():
    """★ 핵심. 보로노이 몫: A 는 y<11 → `2·min(25, 11) = 22m`(종전 50m 의 절반 아래). B 는 후보가 아니라(종전 값이 `CLEAR_M` 미만) 안 건드린다 — 종전과 같다."""
    wx = engine(ShareCarver(_links(), _ref("가길")))
    assert wx.widths(A)[0] == pytest.approx(22.0, abs=0.5)
    assert engine(ShareCarver(_links(), _ref("나길"))).widths(B) == engine().widths(B)


def test_the_width_only_shrinks():
    """몫 ⊂ 폴리곤이라 폭은 **줄기만** 한다 — 틀려도 안전한 쪽으로만 틀린다(MASTER §3-5a)."""
    for width in (44.0, 50.0, 58.0):
        before = engine(poly=strip(width)).widths(A)[0]
        after = engine(ShareCarver(_links(), _ref()), poly=strip(width)).widths(A)[0]
        assert after <= before + 1e-9, (width, before, after)


def test_same_name_links_are_one_road_and_do_not_split():
    """쌍선(같은 도로명)은 한 길이다 — 안 가른다. 값은 종전과 글자까지 같다."""
    wx = engine(ShareCarver(_links(same_name=True), _ref("가길")))
    assert wx.widths(A) == engine().widths(A)


def test_a_road_whose_reference_width_is_close_to_the_measured_one_is_left_alone():
    """기준폭(대장 · 링크 `도로폭` 중 큰 쪽)이 잰 폭과 크게 다르지 않으면(비 < 1.5) 후보가 아니다 — 현행 값을 그대로 둔다. 50 < 1.5×40."""
    c = ShareCarver([(A, "가길", 40.0), (B, "나길", 40.0)], _ref("가길", 40.0))
    assert engine(c).widths(A) == engine().widths(A)
    assert c.stats["not_candidate"] == 1


def test_a_name_mismatch_between_segment_and_nearest_link_falls_back():
    """구간의 도로명과 가장 가까운 링크의 도로명이 다르면 가르지 않는다 — 매칭을 못 믿으면 현행 값이다."""
    c = ShareCarver(_links(), _ref("다른길"))
    assert engine(c).widths(A) == engine().widths(A)
    assert c.stats["name_mismatch"] == 1


def test_a_far_link_falls_back():
    """가장 가까운 링크가 `CARVE_OWN_M` 보다 멀면 가르지 않는다."""
    far = LineString([(0, share.CARVE_OWN_M + 5), (100, share.CARVE_OWN_M + 5)])
    c = ShareCarver([(far, "가길", 8.0), (B, "나길", 8.0)], _ref())
    assert engine(c).widths(A) == engine().widths(A)
    assert c.stats["no_own_link"] == 1


def test_a_floor_keeps_a_too_narrow_share_out():
    """몫이 자기 링크 `도로폭` 의 `CARVE_FLOOR` 배보다 좁게 나오면 잘못 가른 것으로 보고 현행 값을 둔다.
    이웃 「나길」이 y=6 이면 A 의 몫이 위로 3m 뿐이라 `2·min = 6m` — 링크 도로폭 30 의 0.6배(18) 아래다."""
    near = LineString([(0, 6), (100, 6)])
    c = ShareCarver([(A, "가길", 30.0), (near, "나길", 8.0)], _ref("가길", 8.0))
    assert engine(c).widths(A) == engine().widths(A)
    assert c.stats["floor"] == 1


def test_stats_count_every_branch():
    c = ShareCarver(_links(), _ref())
    engine(c).widths(A)
    assert c.stats["carved"] == 1


# ── #180 (DECISIONS §596 · §598) — 가름을 내접원에 붙인다 ─────────────────────────────────
def test_the_inscribed_circle_only_shrinks_inside_the_share():
    """★ 몫 ⊂ 폴리곤이라 표본점의 내접원 지름은 **줄기만 한다.** 폭 쪽 `test_the_width_only_shrinks` 와 같은 성질이다 — 틀려도 안전한 쪽으로만 틀린다."""
    import numpy as np

    from firelane import clearance
    for width in (44.0, 50.0, 58.0):
        area = strip(width)
        clipped = ShareCarver(_links(), _ref()).clip_area(A, width, area)
        assert clipped.area < area.area, width                      # 후보라서 실제로 잘렸다
        full, _ = clearance.inscribed(A, area)
        cut, cov = clearance.inscribed(A, clipped)
        both = ~(np.isnan(full) | np.isnan(cut))
        assert both.any() and (cut[both] <= full[both] + 1e-9).all(), (width, full[both], cut[both])
        assert cov <= 1.0
    # 값으로도 못 박는다: 50m 띠 한가운데 — 종전 내접원 지름 50 · 몫(y<11)으로는 22
    assert np.nanmedian(clearance.inscribed(A, strip(50.0))[0]) == pytest.approx(50.0, abs=0.1)
    assert np.nanmedian(clearance.inscribed(A, ShareCarver(_links(), _ref()).clip_area(A, 50.0, strip(50.0)))[0]) == pytest.approx(22.0, abs=0.5)


def test_clip_area_leaves_a_non_candidate_untouched():
    """후보가 아니면(폭이 `CLEAR_M` 미만 · 이웃 도로 없음) 면을 **그대로** 돌려준다 — 종전 경로와 글자까지 같다."""
    area = strip(50.0)
    c = ShareCarver(_links(), _ref())
    assert c.clip_area(A, 5.0, area) is area                       # 폭이 좁다
    assert c.clip_area(A, None, area) is area                      # 폭이 없다
    one_road = ShareCarver([(A, "가길", 8.0)], _ref())
    assert one_road.clip_area(A, 50.0, area) is area               # 이웃이 없다


def test_clip_area_does_not_count_the_branch_twice():
    """`cell()` 은 갈림을 `stats` 에 센다. 내접원 쪽 호출이 폭 쪽이 이미 센 것을 부풀리면 `report()` 의 가름 수가 거짓이 된다."""
    c = ShareCarver(_links(), _ref())
    c.clip_area(A, 50.0, strip(50.0))
    c.clip_area(A, 5.0, strip(50.0))
    assert dict(c.stats) == {}

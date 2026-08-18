"""
test_seg_roadname.py — 도로명 되붙이기 단위 테스트

`road_name` 은 노딩으로 끊긴 속성을 되찾는 유일한 경로다. 여기가 틀리면
산출물의 `road_name` 이 통째로 옆 도로 이름이 되는데, 판정 숫자는 멀쩡해서
계약 테스트도 golden 도 못 잡는다(둘 다 이름을 안 본다). 사람이 지도를 보고
"어? 이 골목이 왜 중앙로지" 할 때까지 모른다.

주석으로만 있던 규칙 — 중점 최근접이 아니라 겹침 길이, 절반 미만이면 포기 —
을 여기서 고정한다.
"""
import sys
from pathlib import Path

from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "etl"))

from seg.roadname import RoadNameIndex  # noqa: E402


def idx(*rows):
    """(geom, name, dpn, bt) 튜플들로 인덱스를 만든다."""
    return RoadNameIndex([r[0] for r in rows], [r[1] for r in rows],
                         [r[2] for r in rows], [r[3] for r in rows])


def test_matches_the_line_it_lies_on():
    """세그먼트는 원본 선 위에 그대로 놓여 있다. 추정할 필요가 없다."""
    ix = idx((LineString([(0, 0), (100, 0)]), "동명로", "0", 8.0))
    assert ix.match(LineString([(10, 0), (40, 0)])) == ("동명로", "0", 8.0)


def test_overlap_length_beats_proximity():
    """
    ★ 겹침 길이로 고른다. 중점 최근접이 아니다.

    교차로에서 중점 최근접을 쓰면 옆 도로를 집는다. 아래는 그 상황이다 —
    세그먼트 중점은 교차 도로에 더 가깝지만, 실제로 올라타 있는 것은
    본선이다.
    """
    ix = idx((LineString([(0, 0), (100, 0)]), "본선", "0", 8.0),
             (LineString([(50, -0.2), (50, 40)]), "교차로", "0", 3.0))
    seg = LineString([(40, 0), (60, 0)])
    assert ix.match(seg)[0] == "본선"


def test_gives_up_below_half_overlap():
    """겹침이 구간 길이의 절반 미만이면 이름을 붙이지 않는다.

    억지로 붙인 이름은 없는 것보다 나쁘다 — 지도에서 검증할 수 없다.
    """
    ix = idx((LineString([(0, 0), (10, 0)]), "짧은길", "0", 3.0))
    assert ix.match(LineString([(0, 0), (100, 0)])) == (None, None, None)


def test_side_road_flag_travels_with_the_name():
    """
    ★ RDS_DPN_SE 1 = 부속(측도).

    중앙로(본선 25m) 옆에 붙은 폭 1.3m 통로가 같은 도로명을 갖는다.
    이 값이 안 따라오면 "이름은 대로인데 폭이 1m" 를 오산출로 오해한다.
    """
    ix = idx((LineString([(0, 5), (100, 5)]), "중앙로", "0", 25.0),
             (LineString([(0, 0), (100, 0)]), "중앙로", "1", 1.3))
    assert ix.match(LineString([(20, 0), (80, 0)])) == ("중앙로", "1", 1.3)


def test_no_match_outside_everything():
    ix = idx((LineString([(0, 0), (10, 0)]), "동명로", "0", 8.0))
    assert ix.match(LineString([(500, 500), (600, 500)])) == (None, None, None)


def test_empty_index_is_safe():
    """RN 이 전부 비어 있어도 죽지 않는다. 결손은 폐기가 아니다(MASTER 18-3)."""
    ix = idx()
    assert ix.match(LineString([(0, 0), (1, 1)])) == (None, None, None)
    assert ix.nearest(LineString([(0, 0), (1, 1)])) is None


# ── nearest (진단 출력용) ───────────────────────────────────────
def test_nearest_does_not_require_overlap():
    """병렬 엣지 진단은 '대충 어디쯤'만 알면 된다. 겹침을 요구하지 않는다."""
    ix = idx((LineString([(0, 10), (100, 10)]), "밤실로3번길", "0", 5.0))
    assert ix.nearest(LineString([(40, 0), (60, 0)]), 15.0) == "밤실로3번길"


def test_nearest_respects_radius():
    ix = idx((LineString([(0, 100), (100, 100)]), "먼길", "0", 5.0))
    assert ix.nearest(LineString([(40, 0), (60, 0)]), 15.0) is None


def test_nearest_picks_closest():
    ix = idx((LineString([(0, 3), (100, 3)]), "가까운길", "0", 5.0),
             (LineString([(0, 12), (100, 12)]), "먼길", "0", 5.0))
    assert ix.nearest(LineString([(40, 0), (60, 0)]), 15.0) == "가까운길"

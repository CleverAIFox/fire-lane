#!/usr/bin/env python3
"""
test_cover_list.py — **미커버는 비율이 아니라 목록이다.** (§495)

── 왜 생겼나 ───────────────────────────────────────────────────
`guards.uncovered_indices` 의 머리말이 적는다 — 2026-08-18 에 개수만 세던 자를
목록으로 바꿨고, 그 까닭이 「**비율은 게이트고 목록은 작업 지시**다. 둘 다
있어야 한다」였다. 「공간 커버리지 OK · 미커버 3.1%」 가 매 실행 찍히는데
**어느 구간인지 아무도 묻지 않았다** — 같은 날 정사영상 대조로 찾은 결함을
이 검사가 이미 세고 있었다.

그 목록을 내는 쪽을 `tools/srccov.py` 가 「시험이 이름으로도 안 부른다」로
셌다(§493). 가장 많은 소비자를 가진 판정이 미는 자 없이 서 있었다.

★ `tests/test_guards.py` 에 두지 않았다 — 그 파일은 2,911줄 예외이고
  `tools/sizetable.py` 가 「**예외는 늘 자리가 아니다**」라고 적는다. 축이
  다르면 집도 다르다.

IN    없음 (합성 기하)
OUT   없음 (검사)
PARAM 없음
밖    **비율 문턱은 안 본다** — 몇 %까지 허용인가는 관문 선언이고
      `tests/test_guards.py` 가 든다. 여기가 드는 것은 **목록** 하나다.
"""
from __future__ import annotations


# ── 미커버 **목록** — 시험이 이름을 안 부르고 있었다 (§495) ───
# ★ `uncovered_indices` 의 머리말이 이 함수의 존재 이유를 적는다 —
#   「비율은 게이트고, **목록은 작업 지시**다. 둘 다 있어야 한다.」
#   2026-08-18 에 개수만 세던 자를 목록으로 바꾼 자리다. 그런데
#   `tools/srccov.py` 가 「시험이 이름으로도 안 부른다」로 셌다(§493) —
#   **목록을 내는 쪽을 아무도 안 밀었다.**
def test_uncovered_indices_names_the_segment_not_just_the_count():
    """★ 본체. 덮인 것은 빼고 **밖에 있는 것의 번호**를 낸다."""
    from shapely.geometry import LineString, Polygon

    from firelane.guards import uncovered_indices

    inside = LineString([(0, 0), (1, 0)])
    outside = LineString([(100, 100), (101, 100)])
    cover = [Polygon([(-1, -1), (-1, 2), (2, 2), (2, -1)])]
    assert uncovered_indices([inside, outside], cover) == [1]
    assert uncovered_indices([outside, inside], cover) == [0], "번호가 밀렸다"


def test_an_empty_cover_reports_everything_rather_than_nothing():
    """★ **빈 그물을 초록으로 내지 않는다.** 폴리곤이 0개면 전부 미커버다.

    여기서 빈 목록을 내면 「덮을 것이 없다」가 「다 덮였다」로 읽히고,
    그것이 이 저장소가 반복해 겪은 거짓 초록이다(§69).
    """
    from shapely.geometry import LineString

    from firelane.guards import uncovered_indices

    lines = [LineString([(0, 0), (1, 0)]), LineString([(5, 5), (6, 5)])]
    assert uncovered_indices(lines, []) == [0, 1]
    assert uncovered_indices(lines, [None]) == [0, 1], "None 폴리곤을 덮개로 셌다"


def test_the_buffer_decides_how_close_counts_as_covered():
    """★ 버퍼가 판정을 바꾼다 — 기본 1m 는 **닿을 듯한 것**을 덮인 것으로 본다.

    0 으로 주면 교차만 본다. 이 둘이 갈리는 자리를 적어 둔다: 폴리곤
    경계에서 0.5m 밖인 구간은 버퍼 1 에서 덮이고 버퍼 0 에서 안 덮인다.
    """
    from shapely.geometry import LineString, Polygon

    from firelane.guards import uncovered_indices

    cover = [Polygon([(-1, -1), (-1, 2), (2, 2), (2, -1)])]
    near = [LineString([(2.5, 0), (3, 0)])]
    assert uncovered_indices(near, cover, 0) == [0]
    assert uncovered_indices(near, cover, 1) == []


def test_a_missing_geometry_is_not_reported_as_uncovered():
    """★ 기하가 없는 구간은 **미커버가 아니다** — 「덮였나」를 물을 수 없다.

    여기에 번호를 내면 작업 지시에 「이 구간을 보라」가 뜨는데 볼 것이 없다.
    (덮개가 아예 없을 때는 전수를 내므로 그 갈래와 다르다 — 위 시험이 든다.)
    """
    from shapely.geometry import LineString, Polygon

    from firelane.guards import uncovered_indices

    cover = [Polygon([(-1, -1), (-1, 2), (2, 2), (2, -1)])]
    lines = [LineString([(0, 0), (1, 0)]), None, LineString([(9, 9), (9, 8)])]
    assert uncovered_indices(lines, cover) == [2]

"""판정 범위의 공간 규칙. 입력 좌표계는 미터 단위 EPSG:5186.

★ 2026-09-23 (PLAN §13 W3-6). `display_scope` 와 `DISPLAY_*` 를
  `firelane/display_scope.py` 로 옮겼다. 이 파일은 `firelane.segments` 의
  import 닫힘 = **판정 지문** 안이고, 표출 상수가 거기 있으면 지도 여백만
  고쳐도 판정 게이트가 운다. 여기 남는 것은 판정 범위뿐이다.
  표출은 `display_scope` 가 이 함수를 불러 **덮는다** — 정본은 한 곳이다.
"""
from __future__ import annotations

from shapely.ops import unary_union

from firelane.seg.params import CORRIDOR_BUFFER, KEEP_BUFFER, STATION_RADIUS


def judgment_scope(boundary_geometry, corridor_geometries, station_geometries):
    """동명동·접근회랑·안전센터 300m를 포함한다. 도로 형상 자체는 자르지 않는다."""
    stations = tuple(station_geometries)
    if not stations or any(g is None or g.is_empty for g in stations):
        raise ValueError("판정 범위를 만들 안전센터 위치가 없거나 비어 있습니다.")
    parts = [boundary_geometry.buffer(KEEP_BUFFER),
             unary_union(stations).buffer(STATION_RADIUS)]
    corridors = tuple(corridor_geometries)
    if corridors:
        parts.append(unary_union(corridors).buffer(CORRIDOR_BUFFER))
    return unary_union(parts)

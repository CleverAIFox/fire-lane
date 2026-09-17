"""판정·표출 범위의 공통 공간 규칙. 입력 좌표계는 미터 단위 EPSG:5186."""
from __future__ import annotations

from shapely.ops import unary_union

from firelane.seg.params import CORRIDOR_BUFFER, DISPLAY_BUFFER, KEEP_BUFFER, STATION_RADIUS


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


def display_scope(boundary_geometry, corridor_geometries, station_geometries):
    """판정 범위를 모두 덮고, 동 경계 주변의 기존 표출 여백 60m도 유지한다."""
    return judgment_scope(boundary_geometry, corridor_geometries, station_geometries).union(
        boundary_geometry.buffer(DISPLAY_BUFFER)
    )

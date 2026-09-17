"""판정·표출 범위의 공통 공간 규칙. 입력 좌표계는 미터 단위 EPSG:5186."""
from __future__ import annotations

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from firelane.seg.params import (
    CORRIDOR_BUFFER,
    DISPLAY_BUFFER,
    DISPLAY_CLOSE,
    KEEP_BUFFER,
    STATION_RADIUS,
)


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
    """판정 범위를 모두 덮고, 동 경계 주변의 기존 표출 여백 60m도 유지한다.

    ★ 2026-09-17 (DECISIONS §182-7). 회랑 버퍼 · 안전센터 원 · 동 여백을 합치면 레이스 모양이 된다.
      손가락 사이 틈(바깥)과 둘러싸인 구멍(안쪽)이 마스크(불투명도 .9)로 까맣게 덮여 **그 안의 건물 · 정사영상이
      안 보였다**(광주지방법원 앞 블록 · 산수동 쪽 띠). 판정과 무관한 표출 결함이다.
      닫힘(바깥으로 r 만큼 부풀렸다 되돌림)으로 폭 2r 미만 틈을 메우고, 남은 안쪽 구멍은 외곽선만 남겨 없앤다.
      범위(bounds)는 거의 안 바뀐다(실측 0.2m) — view.json · 정사영상 캔버스가 그대로다.
    """
    raw = judgment_scope(boundary_geometry, corridor_geometries, station_geometries).union(
        boundary_geometry.buffer(DISPLAY_BUFFER)
    )
    closed = raw.buffer(DISPLAY_CLOSE).buffer(-DISPLAY_CLOSE).union(raw)
    parts = closed.geoms if hasattr(closed, "geoms") else [closed]
    solid = unary_union([Polygon(p.exterior) for p in parts] + [raw])   # raw 를 다시 합쳐 판정 범위를 정확히 덮는다
    return solid if solid.geom_type == "Polygon" else MultiPolygon(
        [Polygon(p.exterior) for p in solid.geoms])

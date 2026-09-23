#!/usr/bin/env python3
"""
display_scope.py — 표출 범위를 낸다. **판정 지문 밖에서 도는 단계다.**

── 왜 꺼냈나 (2026-09-23 · PLAN §13 W3-6) ──────────────────────
`DISPLAY_BUFFER` · `DISPLAY_CLOSE` 는 지도 표출 전용 상수인데 `seg/params.py`
안에 살았다. 그 파일은 `firelane.segments` 의 import 닫힘이고, 닫힘이 곧 판정
지문이다(`tools/golden.py.judgment_files`). 그래서 **지도 여백 60m 를 손대면
판정이 한 구간도 안 움직이는데 게이트가 울고 재잠금 한 번이 따라왔다.**
정당한 경보가 아니면서 반복되는 빨간불은 `--allow-stale` 을 습관으로 만든다 —
이 저장소가 반복해 겪은 형태다(DECISIONS §69).

계산은 `segments._write_scope()` 가 하고 있었다. 그것을 단계로 꺼낸다.
**옮긴 것은 위치뿐이다.** 같은 재료를 같은 순서로 같은 연산에 넣고 같은
드라이버 · 레이어로 쓴다 — `scope_5186.gpkg` 는 바이트가 같아야 한다.

★ 회랑은 **디스크에서** 읽는다. 직전 단계 `segments` 가 방금 낸
  `corridor_5186.gpkg` 다. STEPS 순서가 segments → scope 라 지난 실행 것을
  읽을 수 없다 — 후진 의존이 아니다(`test_every_read_is_produced_by_an_earlier_step`).
  회랑이 하나도 없으면 `access_corridor` 가 파일을 안 낸다. 종전에 빈 리스트를
  넘기던 것과 같게 빈 리스트로 간다.

★ `firelane.segments` · `firelane.ingest` 가 이 모듈을 import 하면 그 순간
  다시 지문 안이다. 강제자 —
  `tests/test_golden_fp.py::test_display_only_constants_are_outside_the_judgment_closure`

★ 판정 범위(`judgment_scope`)와 그 상수(KEEP_BUFFER · STATION_RADIUS ·
  CORRIDOR_BUFFER)는 `seg/` 에 그대로 둔다. 표출이 판정을 **덮는다**는 관계는
  유지되므로 여기서 `judgment_scope` 를 부른다(정본은 여전히 한 곳이다).

IN    processed/boundary_emd_5186.gpkg · processed/corridor_5186.gpkg
      processed/fire_station.geojson
OUT   processed/scope_5186.gpkg   ★ ortho · publish 가 읽는다
PARAM DISPLAY_BUFFER=60.0 · DISPLAY_CLOSE=150.0 — **표출 상수의 정본은 여기다**
"""
from __future__ import annotations

import geopandas as gpd
import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from firelane.paths import PROCESSED
from firelane.seg.params import EMD_CD
from firelane.seg.scope import judgment_scope

CRS_M = "EPSG:5186"

# ★ 2026-09-23 (W3-6). `seg/params.py` 에서 옮겼다. 값은 하나도 안 바꿨다.
DISPLAY_BUFFER = 60.0        # 동 경계 주변 지도 여백(m). 판정 범위를 덮는다
DISPLAY_CLOSE = 150.0        # 표출 범위 닫힘 반경(m). 폭 300m 미만의 틈 · 안쪽 구멍을 메운다(DECISIONS §182-7)
                             #   판정 범위(judgment_scope)에는 안 쓴다 — 마스크 · 표출 필터만 넓어진다


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


def main() -> None:
    """표출 스코프를 `processed/scope_5186.gpkg` 로 낸다.

    ★ 2026-09-04. 종전에는 `publish_web.main()` 이 계산했고 결과를
      `web/data/scope.geojson` 으로 냈다. 그런데 `ortho` 가 그것을
      읽는다 — STEPS 순서가 … → ortho → publish 라 **뒤 단계 산출을
      앞 단계가 읽고 있었다.** 늘 지난 실행의 스코프로 정사영상을
      구웠고, 스코프가 바뀌면 한 실행 늦게 따라왔다.
      그래서 `segments._write_scope()` 로 올려 순방향으로 만들었다.

    ★ 2026-09-23 (W3-6). 거기서 다시 **자기 단계**로 내렸다. 순방향은
      그대로고(segments → scope → ortho → publish), 표출 상수가 판정
      지문에서 빠진다.

    ★ **기하는 그대로다.** 같은 순서로 같은 연산을 하고 저장 위치 ·
      드라이버 · 레이어 이름이 같다. publish 는 이 파일을 읽어 4326 으로
      돌려 mask · mask_soft 를 만든다 — 변환 단계를 종전과 똑같이
      유지해야 golden 의 L3 기하 동일이 유지된다.
    """
    emd = gpd.read_file(PROCESSED / "boundary_emd_5186.gpkg").to_crs(CRS_M)
    poly = shapely.make_valid(emd.loc[emd.EMD_CD == EMD_CD, "geometry"].iloc[0])

    # ★ 2026-09-16. 판정과 **같은 실행의** 회랑 · 안전센터를 받는다(DECISIONS §170). 규칙은
    #   `seg/scope.py` 의 `judgment_scope` 한 곳이다. 판정 범위를 전부 덮고 동 경계 여백 60m 를 유지한다.
    src = PROCESSED / "corridor_5186.gpkg"
    corridors = list(gpd.read_file(src).geometry) if src.exists() else []
    stations = gpd.read_file(PROCESSED / "fire_station.geojson").to_crs(CRS_M)
    scope = display_scope(poly, corridors, stations.geometry)

    dst = PROCESSED / "scope_5186.gpkg"
    gpd.GeoDataFrame(geometry=[scope], crs=5186).to_file(
        dst, driver="GPKG", layer="scope")
    print(f"스코프 {scope.area / 1e6:.3f}km2 -> {dst.name}")


if __name__ == "__main__":
    from firelane.guards import warn_direct_call

    warn_direct_call(__name__)
    main()

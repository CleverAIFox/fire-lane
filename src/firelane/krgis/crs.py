"""
krgis.crs — 한국 공간데이터 좌표계 판별 및 안전 변환

핵심 문제:
  국내 SHP는 .prj가 없거나, 있어도 틀렸거나, towgs84 파라미터가 누락돼 있다.
  "좌표계를 통일했는데 지도에서 어긋난다"의 원인 90%가 이 셋 중 하나다.

핵심 원칙:
  1. 좌표계를 '추측'하지 말고 '측정'한다 (probe_crs).
  2. 저장은 EPSG:5186(미터, 거리/면적 계산용)과 EPSG:4326(웹 표출용) 두 벌.
  3. Bessel 계열(5174/5175/5176/5177/5178)은 반드시 EPSG 코드로 정의한다.
     proj4 문자열을 손으로 쓰면 towgs84가 빠져 약 390m 어긋난다.
"""

from __future__ import annotations
from dataclasses import dataclass

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError

# ─────────────────────────────────────────────────────────────
# 프로젝트 표준
# ─────────────────────────────────────────────────────────────
CRS_METRIC = "EPSG:5186"   # 중부원점 GRS80, y+600000. 광주 전역이 중부원점 구역.
CRS_WGS84 = "EPSG:4326"   # 웹 표출 / GeoJSON 표준
CRS_WEBMERC = "EPSG:3857"   # 타일 좌표

# 데이터 출처별 실제 좌표계 (2026-08 기준 확인값)
SOURCE_CRS = {
    "도로명주소 전자지도": "EPSG:5179",   # UTM-K(GRS80). 공식 고지: ITRF2000/GRS80/UTM
    "도로명주소 실폭도로": "EPSG:5179",
    "표준노드링크(ITS)": "EPSG:5186",
    "연속지적도": "EPSG:5174",   # 구 지적 계열. towgs84 필수
    "GIS건물통합정보": "EPSG:5179",
    "수치지도 2.0": "EPSG:5186",
    "소상공인 상가정보": "EPSG:4326",   # CSV의 경도/위도 컬럼
    "공공데이터포털 CSV 위경도": "EPSG:4326",
}

# ─────────────────────────────────────────────────────────────
# 좌표계 지문 (광주 동구 동명동 126.9245E, 35.1490N 기준 계산값)
#   → 미상 데이터의 좌표 한 점만 찍어보면 어느 좌표계인지 바로 나온다.
#
#   좌표계                       X(동)        Y(북)
#   EPSG:4326                     126.9         35.1
#   EPSG:5179 UTM-K            947,580    1,683,903
#   EPSG:5186 중부(y+60만)     193,120      283,628
#   EPSG:5187 동부(y+60만)      10,861      285,598
#   EPSG:5181 중부(y+50만)     193,120      183,628
#   EPSG:5174 보정중부 Bessel  193,047      183,321   ← 5181과 x 74m / y 307m 차이
#   EPSG:3857 WebMercator   14,129,171    4,184,148
#
#   판별 요령
#     - 정수부 3자리(126/35)  → 4326
#     - X·Y 모두 7자리        → 5179
#     - Y가 60만대            → 5186(중부) 또는 5187(동부)
#     - Y가 50만대            → 5181 또는 5174 계열 → 둘 다 대보고 300m 어긋나는 쪽을 버린다
#     - X가 8자리             → 3857
# ─────────────────────────────────────────────────────────────

CANDIDATES = [
    "EPSG:4326", "EPSG:5179", "EPSG:5186", "EPSG:5187",
    "EPSG:5185", "EPSG:5188", "EPSG:5181", "EPSG:5174",
    "EPSG:5175", "EPSG:5176", "EPSG:3857",
]

# 광주광역시 대략 경계 (lon_min, lat_min, lon_max, lat_max)
GWANGJU_BBOX = (126.60, 35.00, 127.05, 35.32)
# 전국 대략 경계 — 시군구 단위 미상 데이터 판별용
KOREA_BBOX = (124.5, 33.0, 132.0, 38.7)


@dataclass
class ProbeResult:
    epsg: str
    lon: float
    lat: float
    inside_target: bool

    def __repr__(self) -> str:
        mark = "OK " if self.inside_target else "   "
        return f"{mark}{self.epsg:<12} -> ({self.lon:.5f}, {self.lat:.5f})"


def probe_crs(x: float, y: float, bbox=GWANGJU_BBOX,
              candidates=None) -> list[ProbeResult]:
    """미상 좌표 (x, y) 한 점을 후보 좌표계 전부로 4326 역변환해서
    타깃 bbox 안에 떨어지는 것만 골라낸다.

    >>> hits = [r for r in probe_crs(193120.3, 283627.8) if r.inside_target]
    >>> hits[0].epsg
    'EPSG:5186'
    """
    lo_x, lo_y, hi_x, hi_y = bbox
    out = []
    for code in (candidates or CANDIDATES):
        try:
            tf = Transformer.from_crs(code, CRS_WGS84, always_xy=True)
            lon, lat = tf.transform(x, y)
        except (CRSError, RuntimeError):
            continue
        if not (abs(lon) < 1e5 and abs(lat) < 1e5):   # inf/nan 방어
            continue
        ok = (lo_x <= lon <= hi_x) and (lo_y <= lat <= hi_y)
        out.append(ProbeResult(code, lon, lat, ok))
    out.sort(key=lambda r: not r.inside_target)
    return out


def assert_defined(gdf, name: str, expected: str | None = None):
    """GeoDataFrame의 CRS가 정의돼 있는지, 기대값과 맞는지 검증.
    정의 안 된 채로 파이프라인에 흘러들어가는 것을 여기서 끊는다."""
    if gdf.crs is None:
        raise ValueError(
            f"[{name}] CRS 미정의. .prj가 없다. "
            f"probe_crs()로 판별한 뒤 gdf.set_crs(코드, allow_override=True)로 "
            f"'정의'하라. to_crs()는 정의가 아니라 '변환'이다. 헷갈리면 다 틀어진다."
        )
    if expected and CRS.from_user_input(gdf.crs) != CRS.from_user_input(expected):
        raise ValueError(f"[{name}] CRS 불일치: 실제 {gdf.crs.to_string()} / 기대 {expected}")
    return gdf


def to_metric(gdf, name: str = "?"):
    """거리·면적·버퍼 연산 전 항상 이걸 통과시킨다.
    4326에서 buffer/length 계산하면 단위가 '도'라 결과가 쓰레기가 된다."""
    assert_defined(gdf, name)
    return gdf.to_crs(CRS_METRIC)


def to_wgs84(gdf, name: str = "?"):
    """웹 표출 직전 단 한 번만 호출. GeoJSON 규격상 4326이 표준이다."""
    assert_defined(gdf, name)
    return gdf.to_crs(CRS_WGS84)


def offset_between(x: float, y: float, crs_a: str, crs_b: str) -> float:
    """같은 수치 좌표를 두 좌표계로 각각 해석했을 때 지상에서 몇 m 벌어지는지.
    '5174인데 5181로 정의했다' 같은 사고의 크기를 정량화한다."""
    ta = Transformer.from_crs(crs_a, CRS_WGS84, always_xy=True)
    tb = Transformer.from_crs(crs_b, CRS_WGS84, always_xy=True)
    lon_a, lat_a = ta.transform(x, y)
    lon_b, lat_b = tb.transform(x, y)
    geod = CRS.from_epsg(4326).get_geod()
    _, _, dist = geod.inv(lon_a, lat_a, lon_b, lat_b)
    return dist


if __name__ == "__main__":
    print("=== 좌표계 지문 (동명동 기준) ===")
    for code in CANDIDATES:
        tf = Transformer.from_crs(CRS_WGS84, code, always_xy=True)
        x, y = tf.transform(126.9245, 35.1490)
        print(f"  {code:<12} X={x:>14,.1f}  Y={y:>14,.1f}")

    print("\n=== probe 테스트: (193120.3, 283627.8) ===")
    for r in probe_crs(193120.3, 283627.8)[:4]:
        print(" ", r)

    print("\n=== 흔한 사고의 크기 ===")
    for a, b in [("EPSG:5174", "EPSG:5181"), ("EPSG:5186", "EPSG:5181"),
                 ("EPSG:5186", "EPSG:5187")]:
        print(f"  {a} 데이터를 {b}로 정의 → {offset_between(193120, 183628, a, b):,.0f} m 어긋남")

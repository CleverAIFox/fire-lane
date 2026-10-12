#!/usr/bin/env python3
"""
test_localplane.py — **국소 평면 상수가 실측과 같은가.** (DECISIONS §473)

── 왜 생겼나 ───────────────────────────────────────────────────
§239 → §469 가 같은 상수를 두 번 모았다. **두 번 다 재지 않았다** — 모으는
것과 맞는지 보는 것은 다른 일이고, 모으기만 하면 **틀린 수 하나로** 모인다.
옛 `MY` 는 적도의 자오선 1도였고 위도 35 에서 0.333% 작았다. 3.3km 에서
11m 다. 그 사이 `web/navi/src/domain/geo.ts` 의 머리말은 「오차가 cm 급」
이라고 적고 있었다.

★ **자는 `pyproj` 다** — 이미 선언된 의존이고 파이프라인이 EPSG 변환에
  쓴다. 「어림이라 pyproj 를 안 탄다」(§469-3)는 **지금도 맞다**. 그러나
  그것이 「재지도 않는다」는 뜻은 아니었다. 이 파일이 그 가름이다 —
  **쓰는 것은 상수, 재는 것은 의존성.**

★ 손으로 계산한 기댓값을 **안 적는다.** 적으면 그 수가 셋째 정의가 된다
  (§471 이 분위수에서 든 그 자리다).

IN    없음
OUT   없음 (검사)
PARAM 없음
밖    **고도·측지선은 안 본다** — 평면 근사이고, 이 파일이 드는 것은
      「그 평면이 이 동네에서 얼마나 틀리나」다. 투영의 정확도는
      `pyproj` 의 일이다.
"""
from __future__ import annotations

import math

import pytest

from firelane import localplane as LP

#: 동명동이 든 범위(도). `view.json` 의 상자보다 넉넉하다 — 0.03도 ≈ 3.3km.
SPAN = 0.03

#: 상수가 실측과 어긋나도 되는 폭. 정수로 적은 만큼만 봐준다.
TOL_PCT = 0.01

#: 그 범위에서 평면 근사가 측지선과 어긋나도 되는 거리(m).
TOL_M = 1.0


@pytest.fixture(scope="module")
def geod():
    return pytest.importorskip("pyproj").Geod(ellps="WGS84")


def _deg_metres(geod, lon: float, lat: float) -> tuple[float, float]:
    """그 점에서 경도 1도 · 위도 1도의 미터. **국소 기울기로 잰다.**"""
    _, _, dx = geod.inv(lon - 0.005, lat, lon + 0.005, lat)
    _, _, dy = geod.inv(lon, lat - 0.005, lon, lat + 0.005)
    return dx * 100, dy * 100


def test_the_constants_match_what_pyproj_measures(geod):
    """★ 본체. `MX` · `MY` 가 기준점에서 실측한 수인가."""
    mx, my = _deg_metres(geod, LP.LON0, LP.LAT0)
    bad = []
    for name, mine, real in (("MX", LP.MX, mx), ("MY", LP.MY, my)):
        off = (mine - real) / real * 100
        if abs(off) > TOL_PCT:
            bad.append(f"{name} {mine:,} 인데 실측 {real:,.3f} — {off:+.3f}%")
    assert not bad, "\n  ".join(["국소 평면 상수가 실측과 다르다:", *bad])


def test_the_judge_bites_the_two_numbers_this_section_replaced(geod):
    """★ **카나리아.** 옛 수를 심으면 이 자가 운다 — 안 그러면 「초록」이
    제가 보고 있다는 것을 증명하지 못한다(§445).

    ★ 옛 수를 **글자로 적는다.** 그것이 이 판별식의 과녁이고, 적어 두지
      않으면 누군가 「원래 그랬다」며 되돌린다(§471 이 분위수에서 한 그대로다).
    """
    _, my = _deg_metres(geod, LP.LON0, LP.LAT0)
    for old, why in ((110_574, "적도의 자오선 1도 — §469 가 모은 수"),
                     (111_320, "적도의 경도 1도 — §239 이전의 수"),
                     (110_540, "publish_context 가 들고 있던 수")):
        off = abs(old - my) / my * 100
        assert off > TOL_PCT, f"옛 수 {old:,}({why})가 지금 통과한다 — 자가 죽었다"


def test_the_plane_is_accurate_to_under_a_metre_across_the_neighbourhood(geod):
    """★ **「cm 급」을 말로 적지 않는다.** 범위 전체에서 실제로 잰다.

    옛 상수로는 이 수가 **11m** 였고, 그 동안 머리말은 cm 라고 적고 있었다.
    """
    worst = 0.0
    for i in range(4):
        for j in range(4):
            if i == j == 0:
                continue
            b = (LP.LON0 + SPAN * i / 3, LP.LAT0 + SPAN * j / 3)
            _, _, true = geod.inv(LP.LON0, LP.LAT0, *b)
            worst = max(worst, abs(LP.metres((LP.LON0, LP.LAT0), b) - true))
    assert worst < TOL_M, f"{SPAN * 111:.1f}km 까지 최대 {worst:.2f}m 어긋난다"


def test_the_order_is_lon_lat_and_swapping_is_caught():
    """`(경도, 위도)` 다. 뒤집어 넘기면 **조용히** 엉뚱한 수가 나오므로 묶는다."""
    a, b = (LP.LON0, LP.LAT0), (LP.LON0 + 0.01, LP.LAT0)
    assert LP.metres(a, b) == pytest.approx(0.01 * LP.MX)
    swapped = LP.metres((a[1], a[0]), (b[1], b[0]))
    assert swapped != pytest.approx(LP.metres(a, b)), \
        "경위도를 뒤집어도 같은 수가 나온다 — 그러면 뒤집힌 호출을 못 찾는다"


def test_the_browser_bundle_carries_the_same_two_numbers():
    """★ 번들은 `src` 를 import 할 수 없다 — **수가 두 벌이다.** 같은지 본다.

    ★ `tests/test_sources_of_truth.py` 가 「목록 밖에 또 있나」를 들고,
      이 문은 「선언된 그 자리가 같은 수인가」를 든다. 둘은 다른 물음이다.
    """
    from pathlib import Path
    geo = (Path(__file__).resolve().parent.parent
           / "web/navi/src/domain/geo.ts").read_text(encoding="utf-8")
    bad = []
    for name, v in (("MX", LP.MX), ("MY", LP.MY)):
        # ★ TS 는 정수로 적는다 — `float` 로 적는 사유(§473-5)는 파이썬
        #   `shapely` 쪽 사정이고 번들에는 그 사정이 없다. 수가 같은지만 든다.
        if f"export const {name} = {int(v)};" not in geo:
            bad.append(f"geo.ts 의 `{name}` 가 `{int(v):,}` 가 아니다")
        assert float(int(v)) == v, f"{name} 가 정수가 아니다 — TS 와 못 댄다"
    assert not bad, "\n  ".join(["번들 상수가 파이썬 정본과 다르다:", *bad])


def transform_faults(mx: float, my: float) -> list[str]:
    """그 두 상수로 `shapely.ops.transform` 이 **실제로 변환하는가.** 비면 산다.

    ★ 순수 함수로 뺀 이유 — 아래 카나리아가 **정수를 심어** 이 자가 우는지
      본다. 정수를 심으면 `튜플 * 정수` 가 튜플 반복이 되어 변환이 조용히
      건너뛰어지고, 실물에서는 거기서 메모리가 터졌다(§473-5).
    """
    shapely = pytest.importorskip("shapely")
    from shapely.geometry import LineString
    from shapely.ops import transform
    assert shapely  # 쓰는 이름을 남긴다
    src = [(LP.LON0, LP.LAT0), (LP.LON0 + 0.01, LP.LAT0 + 0.01)]

    def f(x, y, z=None):
        return x * mx, y * my

    out = list(transform(f, LineString(src)).coords)
    want = [(x * float(mx), y * float(my)) for x, y in src]
    if len(out) != len(want):
        # ★ 정수를 넘기면 `튜플 * 정수` 가 **튜플 반복**이라 점이 불어난다.
        #   실물에서는 그 불어남이 메모리를 먹었다.
        return [f"점 수가 {len(out)} — 들어간 것은 {len(want)} 다 (튜플 반복)"]
    bad = []
    for got, w in zip(out, want, strict=True):
        if abs(got[0] - w[0]) > 1e-6 or abs(got[1] - w[1]) > 1e-6:
            bad.append(f"{got} ≠ {w}")
    return bad


def test_shapely_actually_transforms_with_these_constants():
    """★ **조용히 안 변환되는 길을 막는다.** 실물에서 그 길이 열렸었다."""
    assert not transform_faults(LP.MX, LP.MY), \
        f"정본 상수로 변환이 안 된다 — {transform_faults(LP.MX, LP.MY)}"


def test_the_judge_bites_integer_constants():
    """★ 카나리아 — 정수를 심으면 **운다.** 이것이 §473-5 의 과녁이다."""
    assert transform_faults(int(LP.MX), int(LP.MY)), \
        "정수를 심어도 안 운다 — `shapely` 가 고쳐졌으면 사유를 다시 적어라"
    # 한쪽만 정수여도 괜찮다 — 먼저 곱하는 쪽이 float 면 TypeError 로 되돌린다.
    #   옛 판이 그래서 살아 있었다(MX 가 float · MY 가 정수였다).
    assert not transform_faults(LP.MX, int(LP.MY)), \
        "앞쪽이 float 인데도 운다 — 되돌림 경로가 달라졌다. 사유를 다시 재라"


def test_a_degree_of_latitude_is_not_a_degree_of_longitude():
    """★ 이 절의 결함을 **한 줄로** 든다 — 두 수가 같아지면 누가 섞은 것이다."""
    assert LP.MX != LP.MY, "경도 1도와 위도 1도가 같은 수다"
    assert LP.MY > LP.MX, "이 위도에서는 자오선이 더 길다"
    # 적도의 경도 1도(111,320)를 위도에 쓰는 것이 §469 가 걷은 실수다
    assert abs(LP.MY - 111_320) > 100, "위도에 적도 경도 미터가 다시 들어왔다"
    assert math.isclose(LP.metres((LP.LON0, LP.LAT0), (LP.LON0, LP.LAT0)), 0.0)


# ── 웹 메르카토르 역변환 (DECISIONS §493) ─────────────────────
# ★ `firelane.mercator.to_lonlat` 를 **시험이 이름으로도 안 불렀다**
#   (`tools/srccov.py` 가 셌다). §205 가 `ortho` · `terrain` 의 두 벌을
#   여기로 합친 자이고, 합친 뒤로 맞는지 물은 자가 없었다. 타일 경계를
#   `view.json` 에 적는 수가 이 함수에서 나온다 — 틀리면 배경과 지형이
#   **같이** 틀려서 서로 지워진다(§473 이 상수에서 당한 그것이다).
#
# ★ 자는 여기서도 `pyproj` 다. 손으로 계산한 기댓값을 안 적는다.
def test_web_mercator_inverse_matches_pyproj():
    """★ 본체. EPSG:3857 → EPSG:4326 을 의존성과 대조한다."""
    T = pytest.importorskip("pyproj").Transformer.from_crs(
        "EPSG:3857", "EPSG:4326", always_xy=True)
    from firelane.mercator import to_lonlat

    bad = []
    for mx, my in ((0.0, 0.0), (14_126_443.0, 4_184_284.0),
                   (14_000_000.0, 4_200_000.0), (-1_000_000.0, -500_000.0),
                   (20_037_508.0, 20_048_966.0)):
        got, want = to_lonlat(mx, my), T.transform(mx, my)
        if abs(got[0] - want[0]) > 1e-9 or abs(got[1] - want[1]) > 1e-9:
            bad.append(f"({mx:,.0f}, {my:,.0f}) → {got} ≠ {want}")
    assert not bad, "\n".join(bad)


def test_web_mercator_radius_is_the_sphere_not_the_local_plane():
    """★ `R` 은 **구 반지름**이다. 국소 평면 상수와 섞이면 안 된다.

    §473 이 고친 `MX` · `MY` 는 위도 35 의 1도 미터이고, 여기 `R` 은
    적도 반지름이다. 한 수를 다른 자리에 넣는 것이 §469 가 걷은 실수다.
    """
    from firelane import mercator as M

    assert M.R == 6378137.0, "WGS84 적도 반지름이 아니다"
    # 적도 한 바퀴의 절반이 메르카토르 좌표의 끝이다
    assert abs(M.R * math.pi - 20_037_508.34) < 0.01
    assert M.R not in (LP.MX, LP.MY)


def test_web_mercator_round_trips_through_the_project_centre():
    """우리 동네 좌표가 **되돌아오는가**. 타일 경계가 이 왕복에 선다."""
    T = pytest.importorskip("pyproj").Transformer.from_crs(
        "EPSG:4326", "EPSG:3857", always_xy=True)
    from firelane.mercator import to_lonlat

    for dlon, dlat in ((0, 0), (SPAN, SPAN), (-SPAN, -SPAN)):
        lon, lat = LP.LON0 + dlon, LP.LAT0 + dlat
        back = to_lonlat(*T.transform(lon, lat))
        assert abs(back[0] - lon) < 1e-9 and abs(back[1] - lat) < 1e-9, \
            f"({lon}, {lat}) → {back}"


def test_the_inverse_is_odd_about_the_equator_and_the_prime_meridian():
    """★ 부호가 뒤집히면 **반대쪽 반구**가 나온다 — 한 줄로 든다."""
    from firelane.mercator import to_lonlat

    a = to_lonlat(1_000_000.0, 2_000_000.0)
    b = to_lonlat(-1_000_000.0, -2_000_000.0)
    assert abs(a[0] + b[0]) < 1e-12 and abs(a[1] + b[1]) < 1e-12
    assert to_lonlat(0.0, 0.0) == (0.0, 0.0)

#!/usr/bin/env python3
"""
widthlr.py — 중심선에서 **왼쪽·오른쪽을 따로** 잰다. 집이 여기 하나다.

── 왜 생겼나 (2026-10-13 · DECISIONS §509) ─────────────────────
「법선 span 이 맞나 내접원이 맞나」를 두 달 물었고 답이 안 났다. **둘 다 맞고
둘 다 틀렸기 때문**이다 —

    법선 span   왼쪽+오른쪽을 **합쳐서** 낸다 → 한쪽이 광장으로 새면 합이 통째로
                커진다. 실측 5.4m 인 자리를 53.29m 로 냈다
    내접원      **가까운 쪽만** 낸다 → 중심선이 길 한가운데에 없으면 넓은 쪽을
                아예 안 본다. 실측 8~9m 인 자리를 2.0m 로 냈다

**갈라서 재면 그 둘이 한 번에 보인다.** 같은 자리에서 비대칭이 79% 로 같은
구간 둘이 정반대 결과를 낸 것이 증거였고, 가르는 것은 비대칭이 아니라
**광선이 갇혔나 샜나**(`escape`)였다.

    escape = 0   양쪽 다 막힌다  → 폭은 **왼쪽+오른쪽**
    escape > 0   한쪽이 샜다     → 폭은 **2 × 가까운 쪽**

실측 대조(★ 로터리·입구 제외 8점)에서 로그오차 중앙이 **1.605(법선) ·
0.432(내접원) → 0.149** 로 떨어졌고 2배 넘게 틀린 것이 **0** 이 됐다.

IN    없음 (순수 함수 — 중심선과 폴리곤을 인자로 받는다)
OUT   없음
PARAM RAY_CAP_M · OFF_T · ESC_T
밖    **폭을 안 정한다.** 어느 쪽을 쓸지는 부르는 쪽이 정하고, 판정으로
      옮기는 것은 측정 배치의 일이다. 여기가 내는 것은 분해와 그 성질 둘
      (`asym_med` 치우침 · `escape` 샘 · `blind` 양쪽 샘)이다.
      **문헌 대응** — 광선 상한과 포화율은 momepy `street_profile` 의
      `tick_length` · `openness` 와 같은 자리다. 최솟값을 추정량으로 쓰지
      않는 사유는 Brezina·Graser·Leth(2017) 가 적어 둔 그대로다.
부류  몸통   진입점이 아니다 — 부류는 부르는 쪽이 물려받는다  (DECISIONS §398)
"""
from __future__ import annotations

import math
import statistics

#: 광선 상한(m). 문턱이 아니라 「더 가봐야 뜻이 없다」는 선이다 — 동명동 최대
#: 대장폭 35m · 판정 문턱 3~7m. 키워도 결과의 부호가 안 바뀐다.
RAY_CAP_M = 25.0

#: 치우침·샘으로 셀 문턱. **판정 문턱이 아니다** — 세는 자리의 눈금이다.
OFF_T = 0.2
ESC_T = 0.5


def lr_at(line, s: float, poly, cap: float = RAY_CAP_M) -> tuple[float, float, bool]:
    """그 자리의 (왼쪽 거리, 오른쪽 거리, 샜나).

    ★ 광선은 중심선 **위의 점에서 출발**해 제 조각 안에서만 간다 — 건너편
      조각에 닿아도 그것은 다른 도로다.
    """
    # ★ 늦게 든다 — 머리에 두면 모든 호출자가 shapely 를 같이 문다.
    from shapely.geometry import LineString  # noqa: PLC0415  이 함수만 쓴다
    q = line.interpolate(s)
    a = line.interpolate(max(0.0, s - 2.0))
    b = line.interpolate(min(line.length, s + 2.0))
    ang = math.atan2(b.y - a.y, b.x - a.x) + math.pi / 2
    out = []
    for sgn in (1.0, -1.0):
        dx, dy = sgn * cap * math.cos(ang), sgn * cap * math.sin(ang)
        hit = LineString([(q.x, q.y), (q.x + dx, q.y + dy)]).intersection(poly)
        parts = list(hit.geoms) if hasattr(hit, "geoms") else [hit]
        d = 0.0
        for p in parts:
            if p.geom_type == "LineString" and p.distance(q) < 1e-6:
                d = p.length
                break
        out.append(d)
    return out[0], out[1], max(out) >= cap - 1e-6


def lr_profile(line, poly, step: float = 1.0) -> dict:
    """구간 하나의 좌우 분해 요약. 표본이 하나도 없으면 빈 사전.

    ★ 표본은 `clearance_cross.clearances()` 와 **같다** — 끝점을 빼고, 너무
      짧으면 중점 하나. 다르면 두 자가 다른 자리를 재게 되어 대조가 죽는다.
    """
    n = max(int(line.length / step), 1)
    ss = [line.length * i / n for i in range(1, n)] or [line.length / 2]
    L, R, esc = [], [], 0
    for s in ss:
        left, right, out = lr_at(line, s, poly)
        if left + right <= 0:
            continue
        L.append(left)
        R.append(right)
        esc += int(out)
    if not L:
        return {}
    k = len(L)
    # ★ 중앙값의 정본은 `statistics.median` 이다 — 가운데 원소를 손으로 집으면
    #   짝수 길이에서 다른 수가 나온다(`tests/test_handrolled.py`).
    asym = [abs(x - y) / (x + y) for x, y in zip(L, R, strict=True)]
    narrow = [2 * min(x, y) for x, y in zip(L, R, strict=True)]
    wide = [x + y for x, y in zip(L, R, strict=True)]
    # ★ **양쪽이 다 새면 가까운 쪽마저 상한이다.** 그때 `narrow_*` 는 폭이
    #   아니라 2×상한이고, 그것을 폭으로 읽으면 광장이 가장 넓은 길이 된다.
    sat = sum(1 for x, y in zip(L, R, strict=True) if min(x, y) >= RAY_CAP_M - 1e-6)
    return {"asym_med": statistics.median(asym), "escape": esc / k,
            "blind": sat / k, "lr_med": statistics.median(wide),
            "narrow_med": statistics.median(narrow), "narrow_min": min(narrow)}


def off_center(rows: list[dict], t: float = OFF_T) -> list[dict]:
    """**중심선이 길 한가운데에 없는** 구간. 순수하다.

    0 이 아니면 거기서 내접원은 **구조적으로 과소**다 — 자가 아니라 중심선의
    결함이고 고치는 자리도 다르다.
    """
    return sorted(
        ({"seg": r.get("seg_uid"), "label": r.get("seg_label"),
          "asym": r["asym_med"], "lr": r.get("lr_med"),
          "narrow": r.get("narrow_med")}
         for r in rows if (r.get("asym_med") or 0) > t),
        key=lambda d: -d["asym"])


def escaped(rows: list[dict], t: float = ESC_T) -> list[dict]:
    """**광선이 새는** 구간 — 광장 · 교차로 · 로터리.

    거기서 법선 span 은 폭이 아니라 「안 가둬진다」는 라벨이다.
    """
    return sorted(
        ({"seg": r.get("seg_uid"), "label": r.get("seg_label"),
          "escape": r["escape"], "wmin": r.get("wmin"),
          "narrow": r.get("narrow_med")}
         for r in rows if (r.get("escape") or 0) > t),
        key=lambda d: -d["escape"])


def selftest() -> int:
    """★ 합성 도형이 **주장을 그대로 민다.** 빈 그물이면 여기서 운다.

    ★ 진입점이 없다(`부류 몸통`). 이 함수를 부르는 것은
      `tests/test_widthlr.py::test_the_tool_passes_its_own_selftest` 다 —
      `tools/selftests.py` 는 **진입점만** 돈다.
    """
    from shapely.geometry import LineString, Polygon  # noqa: PLC0415  자기검사만 쓴다
    bad: list[str] = []
    strip = Polygon([(0, 0), (40, 0), (40, 4), (0, 4)])

    mid = lr_profile(LineString([(2, 2), (38, 2)]), strip)
    if not (abs(mid["asym_med"]) < 1e-6 and abs(mid["lr_med"] - 4) < 1e-6
            and abs(mid["narrow_med"] - 4) < 1e-6 and mid["escape"] == 0):
        bad.append(f"가운데 중심선을 가운데로 안 읽는다 — {mid}")

    off = lr_profile(LineString([(2, 1), (38, 1)]), strip)
    if abs(off["asym_med"] - 0.5) > 1e-6:
        bad.append(f"치우친 중심선의 비대칭을 못 잰다 — {off}")
    if abs(off["lr_med"] - 4) > 1e-6:
        bad.append("치우쳐도 **좌우합은 폭 그대로**여야 한다 — 그것이 이 분해의 값이다")
    if abs(off["narrow_med"] - 2) > 1e-6:
        bad.append("치우쳤는데 2×가까운쪽이 안 줄었다 — 과소가 안 보이면 빈 그물이다")

    plaza = lr_profile(LineString([(2, 2), (38, 2)]),
                       Polygon([(0, 0), (40, 0), (40, 40), (0, 40)]))
    if plaza["escape"] < 0.99:
        bad.append(f"한쪽이 열린 꼴을 **샘**으로 안 센다 — {plaza}")
    if abs(plaza["narrow_med"] - 4) > 1e-6:
        bad.append("샜는데 2×가까운쪽까지 흔들린다 — 그 자리에서 믿을 수가 없어진다")

    if not off_center([{"asym_med": 0.3}]) or off_center([{"asym_med": 0.1}]):
        bad.append("치우침 판별식이 문턱을 안 가른다")
    if not escaped([{"escape": 0.7}]) or escaped([{"escape": 0.2}]):
        bad.append("샘 판별식이 문턱을 안 가른다")
    if plaza["blind"] != 0:
        bad.append("한쪽만 샌 것을 **양쪽 샘**으로 센다 — 가까운 쪽은 아직 믿을 수 있다")
    big = lr_profile(LineString([(50, 50), (90, 50)]),
                     Polygon([(0, 0), (200, 0), (200, 200), (0, 200)]))
    if big["blind"] < 0.99:
        bad.append(f"**양쪽이 다 샌 것**을 안 센다 — 그 자리엔 폭이 없다. {big}")
    if lr_profile(LineString([(2, 2), (38, 2)]),
                  Polygon([(100, 100), (101, 100), (101, 101)])):
        bad.append("폴리곤 밖의 중심선에서 값을 낸다 — 0 은 폭이 아니다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — 가운데 · 치우침 · 한쪽 샘 · **양쪽 샘** · 두 판별식 · 폴리곤 밖")
    return 0

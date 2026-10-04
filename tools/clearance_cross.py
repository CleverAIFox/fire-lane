#!/usr/bin/env python3
"""
clearance_cross.py — 폭을 **재는 방법**이 기하와 맞는가. 자를 의심한다.

    uv run python tools/clearance_cross.py             대조 (발행본만 쓴다)
    uv run python tools/clearance_cross.py --json OUT  표를 파일로
    uv run python tools/clearance_cross.py --selftest  판별식이 살아 있나

── 왜 생겼나 (DECISIONS §379) ──────────────────────────────────
`widthcross` 는 **값끼리** 댄다 — 우리 폭 · 측량 명목폭 · 대장 명목폭.
`width_fn` 은 같은 표본을 **다른 통계량**으로 본다 — `min` 대신 열림.
둘 다 옳은 방향인데 **입력이 같다.** 셋 다 「폴리곤에 법선을 긋고 잰 표본」
을 먹는다. 표본 자체가 틀리면 셋이 사이좋게 틀린다.

★ 2026-10-03 에 그 표본이 틀렸다는 것이 드러났다. `밤실로4번길` 한 구간이 —

      우리 wmin            58.19 m
      그 점에서 경계까지     2.67 m  (→ 내접원 지름 5.3 m)
      네이버 거리재기        5.4 ~ 6.0 m

  법선 각도를 0~180도 전수로 돌려도 최솟값이 20.5 m 였다. **어느 각도에서도
  진짜 폭이 안 나온다.** 폴리곤은 멀쩡했고 **자가 틀렸다.**

── 이 도구가 드는 양 ───────────────────────────────────────────
표본을 안 쓴다. 중심선 위 각 점에서 **도로구역 경계까지의 거리**를 재고,
그 두 배를 통과폭으로 본다. 거리변환이고 중심축(medial axis)의 반지름이다.

    clearance(s) = dist( centerline(s), ∂RoadArea )
    통과폭(s)     = 2 · clearance(s)

각도를 안 고른다. 표본 간격이 판정을 안 바꾼다. 상한이 필요 없다 —
교차로에서 값이 커지는 것은 **거기가 실제로 넓다**는 뜻이지 거짓이 아니다.

── 세는 것 둘. 둘 다 문턱이 없다 ───────────────────────────────
**보조정리.** 폴리곤 안의 점 p 와 임의 방향 u 에 대해, p 를 지나는 현의
길이는 2·clearance(p) 이상이다. clearance 는 **모든** 방향에 대한 최솟값
이므로 양쪽 거리가 각각 그 이상이고, 합은 두 배 이상이다. ∎

따라서 같은 폴리곤에서 재면 **법선 span ≥ 2·clearance** 가 항상 성립한다.
여기서 둘이 나온다 —

    넘침   wmin > 2·max clearance        법선이 그 구간 어디의 내접원보다
                                          크다. 「길을 따라 나갔다」의 필요조건
    역전   wmin < 2·min clearance        같은 폴리곤이면 **불가능**하다.
                                          나오면 두 값이 다른 폴리곤에서 왔다

★ 「얼마나 넘치면 이상한가」는 안 정한다. 지금 수를 **래칫**으로 박고
  늘지 않게 막는다. 고치면 판정이 움직이고 그것은 측정 배치의 일이다.

IN    web/data/road_area.geojson · sidewalk.geojson · segments.geojson
      data/field/naver_width_2610.csv   (있으면 **현장 인사이트**를 같이 낸다)
OUT   data/processed/clearance_cross.json (--json 이면 지정 경로)
PARAM SPAN_OVERSHOOT · SPAN_INVERSION (래칫. 문턱이 아니라 현재 수다)
밖    **판정을 안 바꾼다.** `widthcross` 와 같은 자리다 — 판정이 끝난 것을
      읽어 기하와 댈 뿐이고 판정 지문 밖이다.
      **어느 쪽이 옳은지도 안 말한다.** 정량 증인은 **도로대장 명목폭**
      (`road_bt_m`)이고, 네이버 기록은 **어디를 볼지**만 알려준다 —
      화면에서 손으로 끌어 잰 값이라 숫자를 기준으로 쓰면 안 된다.
      ★ **레이크가 필요 없다.** 발행본만 읽으므로 CI 에서도 돈다.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

# ★ 좌표 상수의 집은 `tools/localgeo.py` 하나다(§239). 여기 다시 적으면
#   같은 사실이 두 집에 살고 그 둘은 반드시 갈린다.
from localgeo import MX, MY

# ★ 사분위와 결측 읽기의 집은 `tools/statkit.py` 하나다(§379-9).
from statkit import num as _num
from statkit import quartiles

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
PROCESSED = ROOT / "data" / "processed"
FIELD = ROOT / "data" / "field" / "naver_width_2610.csv"

#: 중심선 위 표본 간격(m). **판정을 안 바꾼다** — 더 촘촘하면 더 정확할 뿐이고
#: 이 값이 결과의 부호를 뒤집지 않는다. 그래서 문턱이 아니다.
STEP_M = 1.0

#: 법선 span 이 그 구간 최대 내접원보다 큰 구간 수. **문턱이 아니라 지금 수다.**
#: 줄이려면 폭 산출을 고쳐야 하고 그러면 판정이 움직인다 — 측정 배치의 일이다.
SPAN_OVERSHOOT = 148
#: `wmin` 이 최소 내접원보다 작은 구간 수. **같은 폴리곤이면 0 이다**(보조정리).
#: 0 이 아닌 것은 결함이 아니라 **다른 폴리곤에서 왔다는 증거**이고, 이 수는
#: 그 어긋남의 크기다 — 판정은 `ngii1k`·`ngii`·`실폭도로` 셋을 신뢰도 순으로
#: 쓰고 여기가 읽는 것은 발행된 `road_area` 하나다. 늘면 둘이 더 갈린 것이다.
SPAN_INVERSION = 326

RATCHETS = {"SPAN_OVERSHOOT": "down", "SPAN_INVERSION": "down"}


def _to_m(lon: float, lat: float) -> tuple[float, float]:
    """4326 → 국소 평면(m). `localgeo` 의 상수를 쓴다."""
    return lon * MX, lat * MY


def _geom(path: Path):
    """발행 geojson 을 평면 shapely 도형 목록으로. 없으면 None."""
    from shapely.geometry import shape
    from shapely.ops import transform
    if not path.exists():
        return None

    def f(x, y, z=None):
        return x * MX, y * MY
    g = json.loads(path.read_text(encoding="utf-8"))
    return [transform(f, shape(it["geometry"])) for it in g["features"]]


def clearances(line, boundary, step: float = STEP_M) -> list[float]:
    """중심선을 따라 **경계까지의 거리**. 표본이 아니라 거리변환이다.

    ★ **끝점을 뺀다.** 구간의 양 끝은 교차로 노드이고 거기서 중심선은 이미
      다른 구간과 만난다 — 그 점의 내접원은 이 구간의 것이 아니다. 끝을 넣으면
      교차로의 넓이가 모든 인접 구간으로 번진다.
    ★ 표본이 하나도 안 남을 만큼 짧으면 **중점 하나**를 쓴다. 0 을 내지
      않는다 — 0 은 「폭이 없다」가 되고 회색이 숫자로 굳는다.
    """
    from shapely.geometry import Point
    n = max(int(line.length / step), 1)
    ts = [line.length * i / n for i in range(1, n)] or [line.length / 2]
    out = [d for t in ts
           if (d := boundary.distance(Point(line.interpolate(t)))) > 0]
    return out or [boundary.distance(Point(line.interpolate(line.length / 2)))]


def measure(seg_feats: list, lines: list, road_b, carr_b) -> list[dict]:
    """구간마다 (wmin, 내접원 최소·최대, 차도 기준 최소)."""
    rows = []
    for feat, line in zip(seg_feats, lines, strict=True):
        p = feat["properties"]
        cs = clearances(line, road_b)
        if not cs:
            continue
        row = {
            "seg_uid": p.get("seg_uid"), "seg_label": p.get("seg_label"),
            "road_name": p.get("road_name"), "verdict": p.get("verdict"),
            "wmin": _num(p.get("width_min_m")),
            "ledger": _num(p.get("road_bt_m")),
            "length_m": _num(p.get("length_m")),
            "n_sample": p.get("n_sample"),
            "route_usage": p.get("route_usage") or 0,
            "c_min": 2 * min(cs), "c_max": 2 * max(cs),
            "c_med": 2 * sorted(cs)[len(cs) // 2],
        }
        if carr_b is not None:
            cc = clearances(line, carr_b)
            row["carr_min"] = 2 * min(cc) if cc else None
        rows.append(row)
    return rows


def overshoot(rows: list[dict]) -> list[dict]:
    """`wmin` 이 그 구간 **어디의 내접원보다도** 큰 구간.

    보조정리에 따라 같은 폴리곤에서 재면 span ≥ 2·clearance 다. 넘침 자체는
    모순이 아니다 — 법선이 비스듬하면 현이 길어진다. 그러나 **구간 전체의
    최대 내접원보다도 크다**면 그 법선은 길을 **가로지른 것이 아니라 따라
    나간 것**이다. 그 필요조건을 센다.
    """
    out = []
    for r in rows:
        w, cmax = r.get("wmin"), r.get("c_max")
        if w is None or cmax is None or w <= cmax:
            continue
        out.append({"seg": r["seg_uid"], "label": r["seg_label"],
                    "wmin": w, "c_max": cmax, "배수": w / cmax if cmax else None,
                    "판정": r["verdict"], "사용": r["route_usage"]})
    out.sort(key=lambda d: -(d["배수"] or 0))
    return out


def inversion(rows: list[dict]) -> list[dict]:
    """`wmin` 이 **최소 내접원보다 작은** 구간. 같은 폴리곤이면 불가능하다.

    나오면 둘이 **다른 폴리곤에서 왔다**는 뜻이다 — 판정은 `ngii1k` · `ngii` ·
    `실폭도로` 셋을 신뢰도 순으로 쓰고, 여기가 읽는 것은 발행된 `road_area`
    하나다. 그 어긋남의 크기가 이 수다. **어느 쪽이 옳은지는 안 말한다.**
    """
    return [{"seg": r["seg_uid"], "label": r["seg_label"],
             "wmin": r["wmin"], "c_min": r["c_min"]}
            for r in rows
            if r.get("wmin") is not None and r.get("c_min") is not None
            and r["wmin"] < r["c_min"]]


def field_rows() -> list[dict]:
    """네이버 거리재기 실측. 없으면 빈 목록 — **0 이 아니라 없음이다.**"""
    if not FIELD.exists():
        return []
    with FIELD.open(encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("seg_uid") or "").strip()]


def against_field(rows: list[dict]) -> list[dict]:
    """실측과 두 방법을 나란히. **판정은 안 한다** — 배수만 낸다.

    ★ `spot` 이 측정이 선 자리를 말한다. `mid` 는 구간의 보통 단면이고,
      `off` 는 로터리 진입부나 골목 입구처럼 **구간 중앙과 다른 자리**다.
      둘을 섞으면 「자가 맞는가」를 「측정이 어디였나」가 흔든다.
    """
    by = {r["seg_uid"]: r for r in rows}
    out = []
    for f in field_rows():
        r = by.get(f["seg_uid"])
        w = _num(f.get("w_m"))
        if r is None or w is None or w <= 0:
            continue
        out.append({
            "seg": f["seg_uid"], "label": r["seg_label"], "실측": w,
            "spot": (f.get("spot") or "").strip(),
            "내접원": r["c_med"], "wmin": r["wmin"],
            "내접원/실측": r["c_med"] / w,
            "wmin/실측": (r["wmin"] / w) if r["wmin"] else None,
            "note": f.get("note", ""),
        })
    out.sort(key=lambda d: (d["spot"] != "mid", d["label"]))
    return out


def against_ledger(rows: list[dict]) -> dict:
    """**대장 명목폭과 두 방법을 댄다.** 이것이 정량 증인이다.

    ★ `road_bt_m` 은 도로명주소 도로대장의 명목폭이고 발행본에 **결측 0** 으로
      들어 있다(1,281/1,281). 우리 기하 계산과 **방법이 독립**이다 — 행정이
      적은 수고 폴리곤을 안 쓴다. 스키마가 「참고용. 판정에는 안 쓴다」라고
      적은 그대로 판정에 안 들어가므로, 게이트로 오염되지도 않았다.

    ★ 어느 쪽이 옳은지는 **안 말한다.** 대장이 틀린 사례도 실재한다
      (`필문대로289번길` 은 기하가 틀려 사람이 손으로 보정했다 · §170-2).
      드는 것은 「둘 중 어느 쪽이 대장에서 덜 멀리 있나」 하나다.
    """
    pair = [(r["wmin"], r["c_med"], r["ledger"]) for r in rows
            if r.get("wmin") is not None and r.get("c_med") is not None
            and r.get("ledger")]
    if not pair:
        return {}
    return {
        "짝": len(pair),
        "wmin ÷ 대장": quartiles([w / g for w, _c, g in pair]),
        "내접원 ÷ 대장": quartiles([c / g for _w, c, g in pair]),
        "|wmin ÷ 대장 − 1|": quartiles([abs(w / g - 1) for w, _c, g in pair]),
        "|내접원 ÷ 대장 − 1|": quartiles([abs(c / g - 1) for _w, c, g in pair]),
    }


def cross(rows: list[dict]) -> dict:
    """전수 대조. (분포, 대장 대조, 넘침, 역전, 네이버 인사이트)"""
    ratio = [r["wmin"] / r["c_med"] for r in rows
             if r.get("wmin") and r.get("c_med")]
    diff = [r["wmin"] - r["c_med"] for r in rows
            if r.get("wmin") is not None and r.get("c_med") is not None]
    return {
        "구간": len(rows),
        "표본 간격 m": STEP_M,
        "wmin ÷ 내접원": quartiles(ratio),
        "wmin − 내접원 m": quartiles(diff),
        "대장 대조": against_ledger(rows),
        "넘침": overshoot(rows),
        "역전": inversion(rows),
        "현장 인사이트": against_field(rows),
    }


def ratchet_values() -> dict[str, int]:
    """래칫 이름 → 지금 실측값. **판정은 안 한다**(`show()` 소관).

    발행본이 없으면 `RuntimeError` 를 던진다. **0 을 내지 않는다** — 0 은
    「넘침이 없다」는 뜻이고, 그것을 선언에 적으면 래칫이 조용히 최대로
    조여져 다음 실행이 무조건 빨개진다(§313-1 ① 과 같은 족).
    """
    res = cross(load())
    return {"SPAN_OVERSHOOT": len(res["넘침"]),
            "SPAN_INVERSION": len(res["역전"])}


def load(only: set[str] | None = None) -> list[dict]:
    """발행본에서 구간 · 도로구역 · 보도를 읽는다. 없으면 `RuntimeError`.

    `only` 를 주면 그 `seg_uid` 만 잰다 — 시험이 전수 일 분을 안 쓰게 하는
    자리이고, **값은 전수와 같다**(구간마다 독립으로 재므로).
    """
    from shapely.ops import unary_union
    road = _geom(WEB / "road_area.geojson")
    segs = WEB / "segments.geojson"
    if road is None or not segs.exists():
        raise RuntimeError("web/data 발행본이 없다 — road_area · segments")
    ru = unary_union(road)
    walk = _geom(WEB / "sidewalk.geojson")
    carr_b = None
    if walk:
        carr = ru.difference(unary_union(walk))
        carr_b = carr.boundary if not carr.is_empty else None

    from shapely.geometry import shape
    from shapely.ops import transform

    def f(x, y, z=None):
        return x * MX, y * MY
    g = json.loads(segs.read_text(encoding="utf-8"))
    feats, lines = [], []
    for it in g["features"]:
        if only is not None and it["properties"].get("seg_uid") not in only:
            continue
        geom = transform(f, shape(it["geometry"]))
        line = geom if geom.geom_type == "LineString" else max(
            geom.geoms, key=lambda q: q.length)
        if line.length <= 0:
            continue
        feats.append(it)
        lines.append(line)
    return measure(feats, lines, ru.boundary, carr_b)


def show(res: dict, want: dict[str, int]) -> int:
    n = res["구간"]
    print(f"── 통과폭 교차대조  구간 {n} · 표본 간격 {res['표본 간격 m']}m")
    print("\n  법선 span 과 내접원 지름의 비 — **문턱을 안 건다**")
    for k in ("wmin ÷ 내접원", "wmin − 내접원 m"):
        q = res[k]
        if not q:
            print(f"    {k:16} 겹치는 구간이 없다")
            continue
        print(f"    {k:16} n={q['n']:>5}  25% {q['q25']:+6.2f} · "
              f"중앙 {q['median']:+6.2f} · 75% {q['q75']:+6.2f}   "
              f"[{q['min']:+.2f} ~ {q['max']:+.2f}]")

    lg = res.get("대장 대조") or {}
    if lg:
        print(f"\n  ★ 대장 명목폭과의 대조 — **정량 증인** (짝 {lg['짝']})")
        for k in ("wmin ÷ 대장", "내접원 ÷ 대장",
                  "|wmin ÷ 대장 − 1|", "|내접원 ÷ 대장 − 1|"):
            q = lg[k]
            print(f"    {k:<20} 25% {q['q25']:5.2f} · 중앙 {q['median']:5.2f} · "
                  f"75% {q['q75']:5.2f}   [{q['min']:.2f} ~ {q['max']:.2f}]")
        A, B = lg["|wmin ÷ 대장 − 1|"], lg["|내접원 ÷ 대장 − 1|"]
        print(f"    → 중앙에서는 **같다** ({A['median']:.2f} 대 {B['median']:.2f}). "
              f"갈리는 것은 꼬리다 —")
        print(f"       75%  {A['q75']:.2f} 대 {B['q75']:.2f}   "
              f"최대  {A['max']:.2f} 대 {B['max']:.2f}")
        print("       **법선이 더 낫다고도 더 나쁘다고도 말하지 않는다.** 대부분의")
        print("       구간에서 둘은 같은 값을 내고, 틀리는 자리에서만 법선이 멀리 간다.")

    fld = res["현장 인사이트"]
    print(f"\n  현장 인사이트 {len(fld)}건 — 네이버 항공뷰·거리뷰 (data/field)")
    print("    ★ **숫자는 기준이 아니다.** 화면에서 손으로 끌어 잰 값이라 ±1m 다.")
    print("      이 표가 드는 것은 「그 자리가 어떤 곳인가」다 — 주차 apron ·")
    print("      로터리 · 보도 · 교차로 조각. 정량 대조는 위 대장 칸이 든다.")
    for f in fld:
        wm = f"{f['wmin']:6.2f}" if f["wmin"] is not None else "     —"
        wr = f"{f['wmin/실측']:5.1f}×" if f["wmin/실측"] else "    —"
        mark = "  " if f["spot"] == "mid" else "★ "
        print(f"    {mark}{f['label']:<20} 실측 {f['실측']:5.1f} · "
              f"내접원 {f['내접원']:6.2f} ({f['내접원/실측']:4.1f}×) · "
              f"wmin {wm} ({wr})")
    if any(f["spot"] != "mid" for f in fld):
        print("    ★ 표는 구간 중앙이 아닌 자리에서 잰 것이다 "
              "— 로터리 진입부 · 골목 입구. 배수를 그대로 읽으면 안 된다")
    if not fld:
        print("    없음 — data/field 에 구간이 배정된 실측이 없다")

    over, inv = res["넘침"], res["역전"]
    print(f"\n  넘침 {len(over)}건 · 래칫 {want['SPAN_OVERSHOOT']}"
          "   — wmin 이 그 구간 **최대 내접원**보다 크다")
    for b in over[:10]:
        print(f"    {b['label']:<22} wmin {b['wmin']:6.2f} > "
              f"내접원 최대 {b['c_max']:6.2f}  ({b['배수']:4.1f}×) · "
              f"{b['판정']} · 사용 {b['사용']}")
    if len(over) > 10:
        print(f"    … 그 밖 {len(over) - 10}건")

    print(f"\n  역전 {len(inv)}건 · 래칫 {want['SPAN_INVERSION']}"
          "   — 판정이 쓴 폴리곤과 발행 도로구역이 **다르다**는 증거")
    for b in inv[:10]:
        print(f"    {b['label']:<22} wmin {b['wmin']:6.2f} < "
              f"내접원 최소 {b['c_min']:6.2f}")
    if not inv:
        print("    없음")

    print("\n★ 이 표는 **판정을 안 바꾼다.** 어느 쪽이 옳은가도 안 말한다.")
    print("  분포와 보조정리의 필요조건만 센다. 바꾸려면 판정이 움직이고")
    print("  그것은 측정 배치의 일이다(PLAN §13-5 규칙 2).")

    rc = 0
    for name, got in (("SPAN_OVERSHOOT", len(over)), ("SPAN_INVERSION", len(inv))):
        w = want[name]
        if got > w:
            print(f"\n✗ {name} {got} > 래칫 {w} — **늘었다.** 자가 더 틀렸다.")
            rc = 1
        elif got < w:
            print(f"\n✗ {name} {got} < 래칫 {w} — **래칫을 그 수로 내려라.**")
            rc = 1
    return rc


def _strip(width: float, length: float):
    """자기검사용 곧은 띠. 중심선 위 내접원 지름은 **어디서나 띠의 폭**이다."""
    from shapely.geometry import Polygon
    h, L = width / 2, length / 2
    return Polygon([(-L, -h), (L, -h), (L, h), (-L, h)])


def selftest() -> int:
    """★ 기하가 맞는가. 데이터 없이 합성 도형으로 문다."""
    from shapely.geometry import LineString, Polygon
    bad = []

    # ① 폭 10 인 곧은 띠의 중심선에서 내접원 지름은 어디서나 10 이다.
    strip = _strip(10.0, 400.0)
    mid = LineString([(-100, 0), (100, 0)])
    cs = clearances(mid, strip.boundary, step=1.0)
    if not cs or abs(2 * min(cs) - 10.0) > 0.01 or abs(2 * max(cs) - 10.0) > 0.01:
        bad.append(f"폭 10 띠의 내접원 지름이 10 이 아니다 — {cs[:3]}")

    # ② 끝점을 실제로 빼는가. 길이 10 · 간격 1 이면 **안쪽 아홉 점**이다.
    #    수로 문다 — 값으로 물면 도형이 그 차이를 가려버린다.
    if len(cs) != int(mid.length) - 1:
        bad.append(f"표본 수가 {len(cs)} — 끝을 뺀 안쪽 점이 아니다")
    tiny = clearances(LineString([(0, 0), (0.4, 0)]), strip.boundary, step=1.0)
    if len(tiny) != 1:
        bad.append(f"간격보다 짧은 선에서 표본이 {len(tiny)}개 — 중점 하나여야 한다")

    # ③ 내접원은 외접원을 못 넘는다. 거리 계산이 깨지면 여기서 운다.
    sq = Polygon([(-5, -5), (5, -5), (5, 5), (-5, 5)])
    c2 = clearances(LineString([(-4, 0), (4, 0)]), sq.boundary, step=1.0)
    if 2 * max(c2) > 10.0 * math.sqrt(2) + 0.01:
        bad.append("내접원이 외접원을 넘는다 — 거리 계산이 깨졌다")

    # ③ 넘침 판별식이 양방향으로 무는가.
    if overshoot([{"seg_uid": "A", "seg_label": "A", "wmin": 5.0, "c_max": 9.0,
                   "verdict": "clear", "route_usage": 0}]):
        bad.append("내접원보다 작은 wmin 을 넘침이라 한다")
    if not overshoot([{"seg_uid": "A", "seg_label": "A", "wmin": 50.0,
                       "c_max": 5.0, "verdict": "clear", "route_usage": 0}]):
        bad.append("내접원 최대보다 열 배 큰 wmin 을 못 잡는다")
    if overshoot([{"seg_uid": "A", "seg_label": "A", "wmin": None,
                   "c_max": 5.0, "verdict": "clear", "route_usage": 0}]):
        bad.append("결측을 넘침으로 센다 — 회색은 넘침이 아니다")

    # ④ 역전 판별식.
    if inversion([{"seg_uid": "A", "seg_label": "A", "wmin": 9.0, "c_min": 5.0}]):
        bad.append("정상인 것을 역전이라 한다")
    if not inversion([{"seg_uid": "A", "seg_label": "A", "wmin": 2.0,
                       "c_min": 5.0}]):
        bad.append("wmin 이 최소 내접원보다 작은 것을 못 잡는다")

    # ⑤ 사분위.
    q = quartiles([1.0, 2.0, 3.0, 4.0])
    if not (q["median"] == 2.5 and q["min"] == 1.0 and q["max"] == 4.0):
        bad.append(f"사분위가 틀렸다 — {q}")
    if quartiles([]):
        bad.append("빈 목록에서 값을 낸다")

    # ⑥ 좌표 상수가 `localgeo` 에서 오는가. 여기 다시 적으면 2족이다.
    if not (90_000 < MX < 95_000 and 110_000 < MY < 111_500):
        bad.append(f"좌표 상수가 이상하다 — MX {MX:.0f} · MY {MY}")
    x, y = _to_m(126.92, 35.15)
    if abs(x - 126.92 * MX) > 1e-6 or abs(y - 35.15 * MY) > 1e-6:
        bad.append("평면 변환이 상수와 다르다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — 내접원 · 보조정리 · 넘침/역전 판별식 · 사분위 · 좌표 상수")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="표를 이 경로에 쓴다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    want = {"SPAN_OVERSHOOT": SPAN_OVERSHOOT, "SPAN_INVERSION": SPAN_INVERSION}
    res = cross(load())
    out = a.json or (PROCESSED / "clearance_cross.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    rc = show(res, want)
    print(f"\n→ {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

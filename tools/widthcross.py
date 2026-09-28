#!/usr/bin/env python3
"""
widthcross.py — 폭을 **방법이 다른 원천끼리** 댄다. 오염되지 않은 외부 증인.

    uv run python tools/widthcross.py            대조 (레이크·산출물 필요)
    uv run python tools/widthcross.py --json OUT 표를 파일로
    uv run python tools/widthcross.py --selftest ★ 판별식이 살아 있나

── 왜 생겼나 (DECISIONS §289) ──────────────────────────────────
지금 우리 폭에 대한 외부 대조는 `nfa_compare` **하나**이고 그것은
**오염돼 있다** — 절대편차를 12.6 → 7.24 로 줄이는 데 그 표를 게이트로
썼다(MASTER §4-1). 게이트로 쓴 자료는 그 순간부터 검증 수단이 아니다.

그런데 **방법이 독립인 증인이 이미 셋 있다.** 전부 대장에 있고 전부
파이프라인이 읽고 있으며 **아무도 대조하지 않는다** —

    ngii1k_center.도로폭   1:1,000 수치지형도 **측량 성과**
                           `ngii1k.py` 주석: 「우리 기하 계산과 독립이라
                           대조 검증에 쓴다」 ← 뽑아만 놓고 대조가 없다
    road_bt_m              도로명주소 도로대장 명목폭. **구간마다 이미
                           붙어 있다.** 스키마: 「참고용. 판정에는 안 쓴다」
    node_link.LANES        표준노드링크 차로수

★ 지금 있는 `width_disagree_m` 는 **우리 세 소스끼리만** 잰다 —
  `ngii1k` · `ngii` · `silpok` 셋 다 **같은 방법**(폴리곤에 법선 긋기)이다.
  셋이 맞아도 그 방법이 맞다는 증거가 못 된다. 같은 자로 세 번 잰 것이다.

★ 이 대조는 **한 번 손으로 이미 했다.** `segments.py:413` 주석에 남아 있다 —
  「측량 도로폭과 대조하니 판정이 바뀐 64구간 중 **36구간이 노면·대장폭·
  측량폭이 전부 3m 미만인데 blocked 에서 빠졌다**. 법선이 먼 건물까지 뻗어
  벽 사이를 3.3~25m 로 잡았다. **미탐 쪽으로의 이동이다**」.
  실측이었고 값이 컸는데 **산문으로만 남아 상설 검사가 되지 못했다.**
  이 도구가 그것을 상설로 만든다.

── 무엇을 세나 ────────────────────────────────────────────────
**문턱을 발명하지 않는다.** 1판은 두 가지만 한다 —

    ① 분포     원천 쌍마다 차이의 사분위. 「얼마나 다른가」를 먼저 센다
    ② 모순     문턱 없이 **논리적으로 불가능한 것**만 센다

  모순 둘은 임의 상수가 없다 —
    · `wmin > survey`    우리 **최솟값**이 측량 **명목폭**을 넘는다
    · `wmax < wmin`      담~담이 노면보다 좁다

  「얼마 이상 다르면 이상한가」는 ①의 분포를 보고 **다음 배치에서** 정한다.
  지금 정하면 그 수는 근거가 없다.

IN    processed/segments_5186.gpkg · processed/ngii1k_center_5186.gpkg
OUT   processed/width_cross.json (--json 이면 지정 경로)
PARAM 없음 (문턱이 없다)
밖    **판정을 안 바꾼다.** `nfa_compare` 와 같은 자리다 — 판정이 끝난 것을
      읽어 외부 자료와 댈 뿐이고, 판정 지문 밖이다(§247 과 같은 사유).
      **어느 원천이 옳은가도 안 본다.** 측량폭이 진실이라는 근거가 없다 —
      그것도 사람이 잰 값이다. 여기가 드는 것은 「서로 얼마나 다른가」다.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

#: 이름 → (무엇인가, 우리 기하 계산과 방법이 독립인가)
SOURCES: dict[str, tuple[str, bool]] = {
    "wmin":   ("우리 노면폭 하한 — 폴리곤에 법선을 그어 잰 최솟값", False),
    "wmax":   ("담~담 폭 — 건물 사이", False),
    "survey": ("1:1,000 수치지형도 도로중심선 `도로폭` — 측량 성과", True),
    "ledger": ("도로명주소 도로대장 명목폭 `ROAD_BT`", True),
}

#: 반올림 여유. 측량 도로폭은 0.1m 단위로 기록되고 대장폭은 정수다.
#: **이것은 문턱이 아니라 표기 단위다** — 모순 판정이 표기 오차에 걸리지
#: 않게 하는 값이고, 「얼마나 다르면 이상한가」와는 다른 축이다.
ROUNDING_M = 0.5


def _num(v) -> float | None:
    """수로 읽는다. 결측 · 빈칸 · NaN 은 전부 None 이다. **0 은 수다.**"""
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def contradictions(row: dict) -> list[str]:
    """그 구간에서 **논리적으로 불가능한 것**. 문턱이 없다.

    차이가 큰 것은 여기서 안 센다 — 「크다」의 기준이 아직 없다.
    """
    out: list[str] = []
    wmin, wmax = _num(row.get("wmin")), _num(row.get("wmax"))
    survey = _num(row.get("survey"))

    # ① 우리 **최솟값**이 측량 **명목폭**을 넘는다. 명목폭은 그 길의 대표값이고
    #    최솟값이 그보다 크려면 길이 어디서도 명목폭만큼 좁지 않다는 뜻이다.
    if wmin is not None and survey is not None and wmin > survey + ROUNDING_M:
        out.append(f"wmin {wmin:.2f} > 측량 {survey:.2f} — 최솟값이 명목폭을 넘는다")

    # ② 담~담이 노면보다 좁다. 벽은 노면 밖에 있다.
    if wmin is not None and wmax is not None and wmax + ROUNDING_M < wmin:
        out.append(f"wmax {wmax:.2f} < wmin {wmin:.2f} — 벽 사이가 노면보다 좁다")
    return out


def quartiles(xs: list[float]) -> dict[str, float]:
    """사분위. numpy 를 안 쓴다 — 이 도구는 표를 읽을 뿐이고 의존을 안 늘린다."""
    if not xs:
        return {}
    s = sorted(xs)

    def q(p: float) -> float:
        if len(s) == 1:
            return s[0]
        i = p * (len(s) - 1)
        lo, hi = int(i), min(int(i) + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (i - lo)

    return {"n": len(s), "min": s[0], "q25": q(.25), "median": q(.5),
            "q75": q(.75), "max": s[-1]}


#: 대 볼 쌍. **방법이 독립인 짝을 먼저 둔다** — 그것이 이 도구의 이유다.
PAIRS = (("wmin", "survey"), ("wmin", "ledger"), ("survey", "ledger"),
         ("wmax", "survey"))


def cross(rows: list[dict]) -> dict:
    """전수 대조. (분포, 모순, 덮임)"""
    diffs: dict[str, list[float]] = {}
    for a, b in PAIRS:
        xs = [va - vb for r in rows
              if (va := _num(r.get(a))) is not None
              and (vb := _num(r.get(b))) is not None]
        diffs[f"{a}-{b}"] = xs

    bad = [{"seg": r.get("seg_uid") or r.get("seg_id"), "why": w}
           for r in rows for w in contradictions(r)]

    have = {k: sum(1 for r in rows if _num(r.get(k)) is not None)
            for k in SOURCES}
    return {
        "구간": len(rows),
        "원천별 값 있음": have,
        "차이 분포": {k: quartiles(v) for k, v in diffs.items()},
        "모순": bad,
    }


def show(res: dict) -> int:
    n = res["구간"]
    print(f"── 폭 교차대조  구간 {n}")
    print("\n  원천별 값 있음")
    for k, c in res["원천별 값 있음"].items():
        what, indep = SOURCES[k]
        mark = "★독립" if indep else "  우리"
        pct = f"{c / n:6.1%}" if n else "    —"
        print(f"    {mark} {k:7} {c:>5} {pct}  {what}")

    print("\n  차이 분포 (m) — **문턱을 안 건다. 분포를 먼저 본다**")
    for k, q in res["차이 분포"].items():
        if not q:
            print(f"    {k:16} 겹치는 구간이 없다")
            continue
        print(f"    {k:16} n={q['n']:>5}  "
              f"25% {q['q25']:+6.2f} · 중앙 {q['median']:+6.2f} · "
              f"75% {q['q75']:+6.2f}   [{q['min']:+.2f} ~ {q['max']:+.2f}]")

    bad = res["모순"]
    print(f"\n  모순 {len(bad)}건 — 문턱 없이 **불가능한 것**만")
    for b in bad[:12]:
        print(f"    {b['seg']}  {b['why']}")
    if len(bad) > 12:
        print(f"    … {len(bad) - 12}건 더")
    if not bad:
        print("    없음")
    print("\n★ 이 표는 **판정을 안 바꾼다.** 어느 원천이 옳은가도 안 본다.")
    print("  다음 배치가 이 분포를 보고 「얼마나 다르면 이상한가」를 정한다.")
    return 0


def _load() -> list[dict] | None:
    """산출물에서 구간별 네 값을 모은다. 없으면 None."""
    seg = PROCESSED / "segments_5186.gpkg"
    ctr = PROCESSED / "ngii1k_center_5186.gpkg"
    if not seg.exists():
        return None
    import geopandas as gpd

    from firelane.seg.roadname import RoadNameIndex
    g = gpd.read_file(seg)
    rows = [{"seg_uid": r.get("seg_uid"), "seg_id": r.get("seg_id"),
             "wmin": r.get("width_min_m"), "wmax": r.get("width_max_m"),
             "ledger": r.get("road_bt_m"), "survey": None}
            for _i, r in g.iterrows()]
    if not ctr.exists():
        print(f"  ! {ctr.name} 없음 — 측량 도로폭 없이 낸다")
        return rows

    # ★ 겹침 매칭은 `RoadNameIndex` 가 정본이다. **두 번째 매처를 만들지
    #   않는다**(2족). 그 클래스가 하는 일은 「겹침 길이가 가장 긴 선의 속성을
    #   고른다」이고 컬럼 이름은 부수적이다 — 이름 자리에 도로폭을 넣어 같은
    #   논리를 쓴다. 클래스를 일반화하지 않는 이유는 그것이 **판정 폐포**
    #   안이기 때문이다(§266). 대조 도구 때문에 폐포를 건드리지 않는다.
    #
    # ★ **덮임이 낮을 수 있고 그것도 결과다.** 구간은 `road_link` 위에 놓여
    #   있고 NGII 중심선은 측량 성과라 서로 어긋나 있다 — `centerline_correction`
    #   이 존재하는 이유가 그 어긋남이다(§170-2). 몇 %가 맞는지를 `원천별 값
    #   있음` 이 그대로 낸다. 낮으면 낮다고 보고한다.
    c = gpd.read_file(ctr).to_crs(g.crs)
    if "도로폭" not in c.columns:
        print(f"  ! {ctr.name} 에 `도로폭` 칸이 없다 — 측량 도로폭 없이 낸다")
        return rows
    idx = RoadNameIndex(list(c.geometry), list(c["도로폭"]),
                        [""] * len(c), [None] * len(c))
    for row, geom in zip(rows, g.geometry, strict=True):
        row["survey"] = idx.match(geom)[0]
    return rows


def selftest() -> int:
    """★ 판별식이 실제로 무는가. 데이터 없이 합성으로 문다."""
    bad = []
    if contradictions({"wmin": 2.0, "wmax": 5.0, "survey": 5.0}):
        bad.append("멀쩡한 구간을 모순이라 한다")
    if not contradictions({"wmin": 7.0, "survey": 5.0}):
        bad.append("최솟값이 명목폭을 넘는 것을 못 잡는다")
    if contradictions({"wmin": 5.3, "survey": 5.0}):
        bad.append("표기 반올림을 모순으로 센다")
    if not contradictions({"wmin": 5.0, "wmax": 2.0}):
        bad.append("벽 사이가 노면보다 좁은 것을 못 잡는다")
    if contradictions({"wmin": None, "survey": None}):
        bad.append("결측을 모순으로 센다")
    if contradictions({"wmin": 0.0, "survey": 0.0}):
        bad.append("0 을 결측으로 본다 — 0 은 수다")

    q = quartiles([1.0, 2.0, 3.0, 4.0])
    if not (q["median"] == 2.5 and q["min"] == 1.0 and q["max"] == 4.0):
        bad.append(f"사분위가 틀렸다 — {q}")
    if quartiles([]):
        bad.append("빈 목록에서 값을 낸다")

    r = cross([{"seg_uid": "A", "wmin": 7.0, "survey": 5.0},
               {"seg_uid": "B", "wmin": 3.0, "survey": 5.0}])
    if len(r["모순"]) != 1 or r["모순"][0]["seg"] != "A":
        bad.append(f"전수 집계가 모순을 못 모은다 — {r['모순']}")
    if r["차이 분포"]["wmin-survey"]["n"] != 2:
        bad.append("차이 분포가 짝을 못 센다")

    if not any(indep for _w, indep in SOURCES.values()):
        bad.append("독립 원천이 하나도 선언 안 돼 있다 — 이 도구의 이유가 없다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 모순 판별 · 사분위 · 전수 집계 "
          f"(원천 {len(SOURCES)} · 독립 "
          f"{sum(1 for _w, i in SOURCES.values() if i)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="표를 이 경로에 쓴다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    rows = _load()
    if rows is None:
        print("✗ 산출물이 없다 — data/processed/segments_5186.gpkg")
        print("  파이프라인을 먼저 돌려라. **없는 것은 통과가 아니다.**")
        return 2
    res = cross(rows)
    out = a.json or (PROCESSED / "width_cross.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    rc = show(res)
    print(f"\n→ {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
widthmatch.py — 측량 도로폭이 **왜 구간에 안 붙는가**를 세고, 매칭 규칙을 바꾸면 무엇이 움직이는지 잰다. (Zm17 · DECISIONS §562)

    uv run python tools/widthmatch.py --selftest

IN    processed/segments_5186.gpkg · processed/ngii1k_center_5186.gpkg
OUT   없음 (`widthcross.py --json` 이 "매칭 진단" 칸으로 싣는다)
PARAM SWEEP_GRID · SAME_DIST_P
밖    **판정을 안 바꾼다. 매칭 규칙(`seg/roadname.py` 의 BAND · MATCH_MIN)도 안 바꾼다** — 판정 폐포 안이다. 이 도구는 그 두 상수를 *잠깐*
      바꿔 써 보고 되돌린다(`_match_all`). 어느 규칙이 옳은가는 안 말한다 — 새로 붙은 쌍의 차이 분포가 기존과 구별되는지만 본다.
      `widthcross.py` 에서 갈라 나왔다(파일 길이 — 그 도구는 대조, 이 도구는 매칭 진단이다).
"""
from __future__ import annotations

import sys
from pathlib import Path

from statkit import num as _num

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def reason_of(has_wmin: bool, name_without_width: bool, dist: float | None, same_name: bool | None) -> str:
    """측량 폭이 안 붙은 구간 하나의 **사유**. 순서가 뜻이다(앞이 먼저 걸린다). 순수.

    `dist` 는 구간에서 가장 가까운 측량선까지의 거리(m) — 50m 안에 없으면 None. `same_name` 은 그 선의 도로명이 우리와 같은가.
    0.5m 는 매처의 띠 반폭(`seg/roadname.py` `BAND`)이다 — 이 안이면 **붙어 있는데 겹침이 모자란** 것이고, 밖이면 **어긋난** 것이다.
    """
    if not has_wmin:
        return "우리 wmin 없음"
    if name_without_width:
        return "겹침은 맞으나 측량 도로폭 결측"
    if dist is None:
        return "50m 안에 측량선 없음"
    nm = "이름 같음" if same_name else "이름 다름"
    if dist <= 0.5:
        return f"0.5m 안 — 붙어 있으나 겹침 < 50% · {nm}"
    if dist <= 2:
        return f"0.5~2m 어긋남 · {nm}"
    if dist <= 5:
        return f"2~5m 어긋남 · {nm}"
    if dist <= 10:
        return f"5~10m 어긋남 · {nm}"
    return f"10~50m 어긋남 · {nm}"


#: 매칭 규칙 격자 (띠 반폭 m, 최소 겹침 비율). 첫 칸이 지금 규칙(`seg/roadname.py` 의 값)이다.
SWEEP_GRID = ((0.5, 0.5), (1, 0.5), (2, 0.5), (3, 0.5), (5, 0.5), (10, 0.5), (0.5, 0.3), (1, 0.3), (2, 0.3))

#: 새로 붙은 쌍의 차이 분포가 기존과 **다르지 않다**고 보는 유의수준. 통계 관행(0.05)이다 — 이 데이터에서 도출한 수가 아니다.
SAME_DIST_P = 0.05


def adopt(sweep: list[dict]) -> dict | None:
    """격자에서 **새로 붙은 쌍의 분포가 기존과 구별되지 않는** 규칙 중 가장 많이 붙이는 것. 최소 겹침은 지금 값인 것만. 순수."""
    ok = [r for r in sweep[1:] if r["min"] == sweep[0]["min"] and r["p"] is not None and r["p"] >= SAME_DIST_P]
    return max(ok, key=lambda r: r["n"]) if ok else None


def _geo():
    import geopandas as gpd
    g = gpd.read_file(PROCESSED / "segments_5186.gpkg")
    c = gpd.read_file(PROCESSED / "ngii1k_center_5186.gpkg").to_crs(g.crs)
    return g, c


def _match_all(g, c, band: float, min_overlap: float):
    """주어진 띠·겹침으로 구간마다 (측량폭, 측량 도로명). 매처는 `RoadNameIndex` 하나다 — 모듈 상수를 잠깐 바꿔 쓰고 되돌린다."""
    import firelane.seg.roadname as rn
    old = (rn.BAND, rn.MATCH_MIN)
    rn.BAND, rn.MATCH_MIN = band, min_overlap
    try:
        n = len(c)
        iw = rn.RoadNameIndex(list(c.geometry), list(c["도로폭"]), [""] * n, [None] * n)
        inm = rn.RoadNameIndex(list(c.geometry), list(c["도로명"]), [""] * n, [None] * n)
        return [(iw.match(x)[0], inm.match(x)[0]) for x in g.geometry]
    finally:
        rn.BAND, rn.MATCH_MIN = old


def unmatched_reasons() -> dict:
    """지금 규칙에서 측량 폭이 안 붙은 구간을 사유별로 센다. **고치기 전에 세는 것이다.**"""
    from collections import Counter

    from shapely.strtree import STRtree
    g, c = _geo()
    geoms, names = list(c.geometry), list(c["도로명"])
    tree = STRtree(geoms)
    got = _match_all(g, c, 0.5, 0.5)
    cnt: Counter = Counter()
    fine: Counter = Counter()
    for (w, nm), geom, r in zip(got, g.geometry, g.itertuples(), strict=True):
        if _num(w) is not None and _num(r.width_min_m) is not None:
            continue
        near = tree.query(geom.buffer(50))
        best = min(((geoms[j].distance(geom), j) for j in near), default=None)
        same = None if best is None else (names[best[1]] or "") == (r.road_name or "")
        cnt[reason_of(_num(r.width_min_m) is not None, nm is not None and _num(w) is None,
                      None if best is None else best[0], same)] += 1
        if best is not None and best[0] <= 0.5 and _num(r.width_min_m) is not None:
            # 붙어 있는데 안 붙은 것 — **측량선이 조각나서**인가(같은 이름 조각을 합치면 50% 를 넘나), 아니면 그냥 스칠 뿐인가
            from shapely.ops import unary_union
            band = geom.buffer(0.5)
            near = [k for k in tree.query(band) if geoms[k].distance(geom) <= 0.5]
            same_k = [k for k in near if (names[k] or "") == (r.road_name or "")]
            ov_same = unary_union([geoms[k].intersection(band) for k in same_k]).length / geom.length if same_k else 0.0
            ov_all = unary_union([geoms[k].intersection(band) for k in near]).length / geom.length
            fine["같은 이름 조각을 합치면 ≥ 50% (측량선 조각남)" if ov_same >= 0.5 else
                 ("이름 무시하고 합치면 ≥ 50%" if ov_all >= 0.5 else "합쳐도 < 50% (스칠 뿐)")] += 1
    return {"미매칭": sum(cnt.values()), "사유": dict(cnt.most_common()), "0.5m 안 세분": dict(fine.most_common())}


def sweep() -> list[dict]:
    """매칭 규칙을 바꾸면 매칭 수와 `wmin-survey` 중앙이 어떻게 움직이는가. 새로 붙은 쌍이 기존 쌍과 같은 분포인지 Mann-Whitney 로 본다."""
    import statistics

    from scipy.stats import mannwhitneyu
    g, c = _geo()
    out, base_ids, base_d = [], set(), []
    for band, mn in SWEEP_GRID:
        got = _match_all(g, c, band, mn)
        ids, d = [], []
        for i, ((w, _nm), r) in enumerate(zip(got, g.itertuples(), strict=True)):
            if (a := _num(r.width_min_m)) is not None and (b := _num(w)) is not None:
                ids.append(i)
                d.append(a - b)
        if not base_ids:
            base_ids, base_d = set(ids), d
        new = [x for i, x in zip(ids, d, strict=True) if i not in base_ids]
        out.append({"band": band, "min": mn, "n": len(ids), "median": statistics.median(d),
                    "new": len(new), "new_median": statistics.median(new) if new else None,
                    "p": float(mannwhitneyu(base_d, new).pvalue) if new else None})
    return out


def selftest() -> int:
    bad = []
    if reason_of(False, False, 0.1, True) != "우리 wmin 없음":
        bad.append("wmin 없음을 못 가른다")
    if "결측" not in reason_of(True, True, 0.1, True):
        bad.append("측량 도로폭 결측을 못 가른다")
    if "50m" not in reason_of(True, False, None, None):
        bad.append("측량선이 없는 것을 못 가른다")
    if "0.5m 안" not in reason_of(True, False, 0.3, True) or "0.5~2m" not in reason_of(True, False, 1.0, True):
        bad.append("0.5m 경계를 못 가른다")
    if "이름 다름" not in reason_of(True, False, 3.0, False):
        bad.append("이름 다름을 못 가른다")
    base = {"band": 0.5, "min": 0.5, "n": 10, "p": None}
    pick = adopt([base, {"band": 2, "min": 0.5, "n": 20, "p": 0.5}, {"band": 5, "min": 0.5, "n": 30, "p": 0.01},
                  {"band": 1, "min": 0.3, "n": 99, "p": 0.9}])
    if pick is None or pick["band"] != 2:
        bad.append(f"채택이 p 와 최소 겹침을 안 거른다 — {pick}")
    if adopt([base]) is not None:
        bad.append("후보가 없는데 채택한다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — 사유 분류 · 채택")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else (print(__doc__) or 0))

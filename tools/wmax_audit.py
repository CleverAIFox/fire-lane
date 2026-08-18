#!/usr/bin/env python3
"""
wmax_audit.py — `width_max_m` 결손이 판정을 어느 쪽으로 기울이는지 센다.

    uv run python tools/wmax_audit.py

왜 만들었나
    2026-08-18 UI 팝업에 폭 1.57m 구간의 "벽 사이 폭"이 `-` 로 떴다.
    MASTER §11 은 그것을 이렇게 설명한다 —

        "큰 도로는 건물이 40m 밖이라 벽 사이를 잴 수 없고,
         그런 구간은 도로 폭만으로 이미 판정이 끝납니다."

    1.57m 골목에 건물이 40m 밖일 수는 없다. 설명이 사례를 안 덮는다.
    세어보니 `width_max_m` 결손은 496/1101 (45%) 이고, 그중 160개는
    **도로 폭 자체가 3.0m 미만**이다.

무엇이 문제인가
    `seg/geom.py::verdict()` 는 blocked 를 wmax 로만 판정한다.

        if wmax is not None and wmax < TRUCK:  return "blocked"
        ...
        if wmin is not None:                    return "needs_cv"

    wmax 가 없으면 blocked 로 갈 길이 없다. 그래서 폭 0.38m 짜리 구간이
    needs_cv 로 떨어지고, CCTV 가 멀면 다시 unknown/no_cctv 가 된다.
    화면에는 "카메라가 없어 판단을 못 한다"로 표시되지만, 카메라를 갖다
    대도 소방차는 못 들어간다. **결손이 관대한 쪽으로 해석되고 있다.**

    MASTER §3-3 의 ROAD_BT 예외가 바로 이 경우를 막으려고 만든 것인데,
    `segments.py` 에서 `elif v == "unknown"` 가지에만 걸려 있다. 위 구간들은
    needs_cv 를 거쳐 unknown 이 되므로 그 가지에 도달하지 않는다. 문서에
    "적용 2건"이라고 적힌 이유가 이것이다.

    이 도구는 고치지 않는다. 규모를 재고 대조군을 붙여 출력만 한다.
    수정 여부는 §4-4(오류 비대칭 · 안전마진) 결정이 선행돼야 한다.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "data/processed/segments.geojson"
TRUCK = 3.0

BINS = [(0, 3), (3, 5), (5, 7), (7, 10), (10, 1e9)]


def label(v: float) -> str:
    for lo, hi in BINS:
        if lo <= v < hi:
            return f"{lo}–{hi:g}m" if hi < 1e9 else f"{lo}m+"
    return "?"


def main() -> int:
    if not SEG.exists():
        print(f"! {SEG} 없음 — pipeline 을 먼저 돌려라")
        return 1
    P = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    n = len(P)
    null = [p for p in P if p["width_max_m"] is None]

    print(f"width_max_m 결손 {len(null)} / {n}  ({len(null)/n*100:.0f}%)\n")

    print("도로 폭대별 결손율 — MASTER §11 이 맞다면 넓은 쪽에만 몰려야 한다")
    tot = collections.Counter(label(p["width_min_m"]) for p in P if p["width_min_m"] is not None)
    nul = collections.Counter(label(p["width_min_m"]) for p in null if p["width_min_m"] is not None)
    for k in [f"{lo}–{hi:g}m" if hi < 1e9 else f"{lo}m+" for lo, hi in BINS]:
        if tot[k]:
            print(f"  {k:8s} {nul[k]:4d} / {tot[k]:4d}   {nul[k]/tot[k]*100:5.1f}%")
    print("  → 좁은 쪽에도 고르게 있다. 결손 사유가 '건물이 멀어서'만은 아니다.\n")

    narrow_null = [p for p in null
                   if p["width_min_m"] is not None and p["width_min_m"] < TRUCK]
    narrow_ok = [p for p in P
                 if p["width_max_m"] is not None
                 and p["width_min_m"] is not None and p["width_min_m"] < TRUCK]
    nb = sum(1 for p in narrow_ok if p["verdict"] == "blocked")

    print(f"도로 폭 < {TRUCK}m 인 구간의 판정 — wmax 유무로 갈라 본다")
    print(f"  wmax 있음  {len(narrow_ok):4d}개 → blocked {nb:3d}  ({nb/len(narrow_ok)*100:.0f}%)")
    print(f"  wmax 결손  {len(narrow_null):4d}개 → blocked "
          f"{sum(1 for p in narrow_null if p['verdict']=='blocked'):3d}  (구조적으로 0)")
    print(f"    판정 분포 {dict(collections.Counter(p['verdict'] for p in narrow_null))}")
    print(f"    총연장 {sum(p['length_m'] for p in narrow_null):.0f}m"
          f" · 동명동 밖 {sum(1 for p in narrow_null if not p['in_emd'])}/{len(narrow_null)}")
    bt = sum(1 for p in narrow_null
             if p["road_bt_m"] is not None and p["road_bt_m"] < TRUCK)
    print(f"    그중 road_bt_m < {TRUCK}m 인 것 {bt}개"
          f" ← §3-3 예외가 걸렸어야 하나 가지에 도달하지 않는다")
    if len(narrow_ok):
        print(f"\n  대조군 비율({nb/len(narrow_ok)*100:.0f}%)을 그대로 적용하면"
              f" blocked 가 {round(len(narrow_null)*nb/len(narrow_ok))}개 늘어날 수 있다.")
        print("  ★ 추정이지 산출이 아니다. 실제 값은 wmax 를 채워야 나온다.")

    print("\n답사 후보 — 도로 폭이 좁은데 wmax 가 없고 긴 구간부터")
    cand = sorted(narrow_null, key=lambda p: (p["width_min_m"], -p["length_m"]))[:8]
    print(f"  {'seg_uid':24s} {'도로명':16s} {'폭':>5s} {'길이':>7s} {'대장폭':>6s}  판정")
    for p in cand:
        print(f"  {p['seg_uid']:24s} {str(p['road_name'])[:15]:16s}"
              f" {p['width_min_m']:5.2f} {p['length_m']:6.1f}m"
              f" {str(p['road_bt_m']):>6s}  {p['verdict']}")
    print("\n  대조군도 같이 보라 — 결손만 보면 '원래 그런가보다'로 끝난다.")
    for p in sorted(narrow_ok, key=lambda p: -p["length_m"])[:3]:
        print(f"  {p['seg_uid']:24s} {str(p['road_name'])[:15]:16s}"
              f" {p['width_min_m']:5.2f} {p['length_m']:6.1f}m"
              f" wmax={p['width_max_m']:.2f}  {p['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

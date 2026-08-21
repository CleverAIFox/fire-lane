#!/usr/bin/env python3
"""
tools/basisno_calibrate.py — 도로별 기점 오프셋을 산출한다.

    uv run python tools/basisno_calibrate.py

road_link 는 스코프로 클리핑돼 있어 본선의 진짜 기점이 선 밖에 있다.
`poi_store` 의 건물본번지로 도로마다 밀린 양을 잰다.

    offset_no = median(실제 건물본번지 - 기하로 계산한 기초번호)

★ 표본의 70% 만 쓴다. 나머지 30% 는 `basisno_check.py` 가 정확도를
  보고하는 데만 쓰는 홀드아웃이다. 보정에 쓴 자료로 정확도를 주장하면
  그것은 검증이 아니라 적합(fit)이다 — MASTER §4 의 nfa_compare 와
  같은 함정을 반복하지 않는다.

산출물 `data/basisno_offset.json` 은 커밋한다. 196행이라 가볍고,
git diff 로 도로별 변화를 눈으로 볼 수 있다.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "etl"))
from seg.basisno import BasisNumberIndex, basis_no  # noqa: E402

P = Path("data/processed")
OUT = Path("data/basisno_offset.json")
HOLDOUT_SEED = 20260821          # 고정. 실행마다 갈리면 재현이 안 된다
CALIB_FRAC = 0.70
MIN_SAMPLES = 6                  # 이보다 적으면 중앙값을 못 믿는다


def collect():
    road = gpd.read_file(P / "road_link.geojson")
    poi = gpd.read_file(P / "poi_store.geojson")
    if poi.crs != road.crs:
        poi = poi.to_crs(road.crs)

    bnx = BasisNumberIndex.from_gdf(road)
    rows = collections.defaultdict(list)
    for rn, num, geom in zip(poi["도로명"], poi["건물본번지"], poi.geometry):
        if rn is None or geom is None or geom.is_empty:
            continue
        try:
            actual = int(num)
        except (TypeError, ValueError):
            continue
        if actual <= 0:
            continue
        key = str(rn).split()[-1]
        base = bnx.line.get(key)
        if base is None:
            continue
        iv = bnx.interval.get(key, 20.0)
        rows[key].append((actual, basis_no(base.project(geom), iv)))
    return bnx, rows


def split(n: int, rn: str):
    """도로명으로 시드를 고정해 재현 가능하게 나눈다."""
    rng = np.random.default_rng(HOLDOUT_SEED + (hash(rn) & 0xFFFF))
    idx = rng.permutation(n)
    k = max(1, int(round(n * CALIB_FRAC)))
    return set(idx[:k].tolist())


def main() -> int:
    bnx, rows = collect()
    out, skipped = {}, []

    for rn, pairs in rows.items():
        n = len(pairs)
        if n < MIN_SAMPLES:
            skipped.append((rn, n))
            continue
        calib_idx = split(n, rn)
        devs = [a - c for i, (a, c) in enumerate(pairs) if i in calib_idx]
        med = float(np.median(devs))
        # 기초번호는 홀수 계열이므로 오프셋은 짝수여야 홀짝이 보존된다.
        off = int(round(med / 2.0)) * 2
        spread = float(np.percentile(devs, 75) - np.percentile(devs, 25))
        out[rn] = {
            "offset_no": off,
            "n_calib": len(devs),
            "n_total": n,
            "iqr": round(spread, 1),
            "interval_m": bnx.interval.get(rn, 20.0),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "도로별 기점 오프셋. road_link 가 스코프로 클리핑돼 본선의 "
                "진짜 기점이 선 밖에 있어서 생긴다. tools/basisno_calibrate.py 산출물.",
        "source": "poi_store.geojson 건물본번지",
        "holdout_seed": HOLDOUT_SEED,
        "calib_frac": CALIB_FRAC,
        "roads": dict(sorted(out.items())),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    big = sorted(out.items(), key=lambda x: -abs(x[1]["offset_no"]))[:12]
    print(f"보정 {len(out)}개 도로 · 표본부족 {len(skipped)}개 (<{MIN_SAMPLES}건)")
    print(f"기록: {OUT}\n")
    print("가장 많이 밀린 도로 (클리핑이 심한 본선)")
    for rn, v in big:
        m = v["offset_no"] / 2 * v["interval_m"]
        print(f"  {rn:20s} offset {v['offset_no']:+6d}  ≈ {m:7.0f}m"
              f"  n={v['n_total']:4d}  IQR {v['iqr']:.0f}")
    print("\n오프셋 0 (스코프 안에 통째로 들어 있는 도로)")
    zero = [rn for rn, v in out.items() if v["offset_no"] == 0]
    print(f"  {len(zero)}개  예: {zero[:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

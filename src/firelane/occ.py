"""
occ.py — 점유압력 β: 「이 골목 연석에 차가 얼마나 서는가」의 **상대 순위용** 칸 둘.

IN    구간(`length_m` · `in_emd` · `width_min_m` · `seg_uid` · 기하) · 수요점(`data/processed/occ_demand.csv`)
OUT   `occ_pressure` · `occ_pressure_rank` (web/data/segments.geojson 에 출판이 싣는다)
PARAM `BUFFER_M` · `BAND_EDGES`
밖    **판정을 만들지 않는다.** 이 칸은 순서만 만든다(CCTV 없는 구간 447 중 어디부터 나갈지). 수요에 **거주 세대만**
      잡히고 상업 유입은 안 잡힌다. 건축물대장이 동명동뿐이라 동명동 밖은 **잴 수 없다**(null 이다, 0 이 아니다).

── 정의 ────────────────────────────────────────────────────────────
  occ_pressure       = Σ units / length_m × 100        단위: 거주단위 / 100m · 소수 2자리
  occ_pressure_rank  = `width_min_m` 밴드 (0,3] (3,4] (4,5] (5,6] (6,7] (7,∞) **안에서** occ_pressure 내림차순 순위.
                       동률은 seg_uid 사전순.

★ **길이 기준이다. 면적 기준이 아니다.** β 가 뜻해야 하는 것은 「이 골목 연석에 차가 얼마나 서는가」이고 길이가 물리다.
★ **`cap_style=2`(평평한 끝)는 길이 기준에서만 효력이 있다.** 구간을 12m 로 부풀려(`buffer`) 수요점을 센다.
  둥근 끝(기본값)이면 길이 5m 구간이 반경 12m 원(≈452㎡)을 먹어 **먼 점까지 세고**, 분모는 5m 로 나뉜다 —
  최대가 부풀려진다(2026-10-23 실측: 둥근 끝 529.4 · 평평한 끝 112.7). 평평한 끝은 5m×24m = 120㎡ 만 먹는다.
  면적 기준(`/ bf.area`)에서는 분자·분모가 같이 커져 둘의 차이가 없었다(최대 47.09 대 47.01) — **그래서 면적 기준에서는
  이 인자가 아무 일도 안 한다.** 초안이 「분모가 터진다」고 쓴 사유는 면적 기준에서는 틀렸다.
★ 포함 판정은 `bf.contains(point)` 다. `STRtree.query` 만으로는 느슨하다(상자 겹침까지 센다).
★ **밴드 안에서 순위를 매긴다.** β 는 폭과 상관이 크다(0~3m 중앙 4.3 → 6~7m 중앙 0.0). 전체 순위는 폭 순위를 되풀이할 뿐이다.
★ **null 과 0 은 다르다.** `in_emd == False` 인 구간은 `occ_pressure` 가 **null** 이다 — 건축물대장이 동명동뿐이라 잴 수 없다.
  0 으로 적으면 「압력 없음 = 안전」으로 읽힌다. `occ_pressure == 0`(동명동 안인데 수요점이 없다)은 rank 가 null 이다.
"""
from __future__ import annotations

from pathlib import Path

BUFFER_M = 12.0
BAND_EDGES = (0.0, 3.0, 4.0, 5.0, 6.0, 7.0)      # (0,3] (3,4] (4,5] (5,6] (6,7] (7,∞)
DEMAND_COLS = ("x", "y", "units")


def load_demand(path: Path):
    """수요점 표(`x` `y` EPSG:5179 · `units`). 없으면 None — 호출자가 **결측으로 내야** 한다(0 이 아니다)."""
    import pandas as pd
    if not Path(path).exists():
        return None
    d = pd.read_csv(path)
    missing = [c for c in DEMAND_COLS if c not in d.columns]
    if missing:
        raise ValueError(f"{path} 에 칸이 없다: {missing}")
    return d


def occ_columns(seg, demand):
    """구간 표 → (occ_pressure, occ_pressure_rank) 두 Series. `seg` 는 어느 좌표계든 된다(5179 로 옮겨 잰다).

    `demand` 가 None 이면 **전부 null** 이다.
    """
    import numpy as np
    import pandas as pd
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    idx = seg.index
    occ = pd.Series([None] * len(seg), index=idx, dtype="object")
    rank = pd.Series([None] * len(seg), index=idx, dtype="object")
    if demand is None or len(demand) == 0:
        return occ, rank

    g5179 = seg.to_crs(5179).geometry
    pts = [Point(x, y) for x, y in zip(demand["x"], demand["y"], strict=True)]
    units = demand["units"].to_numpy(dtype=float)
    tree = STRtree(pts)
    inside = seg["in_emd"].astype(bool)
    for i, g, ln in zip(idx, g5179, seg["length_m"], strict=True):
        if not inside.loc[i] or not ln or ln <= 0:
            continue                                   # 동명동 밖 · 길이 없음 → null (0 이 아니다)
        bf = g.buffer(BUFFER_M, cap_style=2)           # ★ 평평한 끝 — 길이 기준에서만 효력이 있다
        hit = [j for j in tree.query(bf) if bf.contains(pts[j])]
        occ.loc[i] = round(float(units[hit].sum()) / float(ln) * 100.0, 2)

    # 밴드 안 순위. occ == 0 · 폭 없음은 rank null.
    rows = [(i, float(v), float(w), u) for i, v, w, u in
            zip(idx, occ, seg["width_min_m"], seg["seg_uid"], strict=True)
            if v is not None and v > 0 and w == w and w is not None and w > 0]
    edges = list(BAND_EDGES) + [np.inf]
    bands: dict[int, list] = {}
    for i, v, w, u in rows:
        b = next(k for k in range(len(edges) - 1) if edges[k] < w <= edges[k + 1])
        bands.setdefault(b, []).append((-v, str(u), i))
    for lst in bands.values():
        for r, (_, _, i) in enumerate(sorted(lst), start=1):
            rank.loc[i] = r
    return occ, rank

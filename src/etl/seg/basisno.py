#!/usr/bin/env python3
"""
seg/basisno.py — 구간 라벨을 도로명주소 기초번호로 만든다.

── 왜 필요한가 ────────────────────────────────────────────────
`road_name` 만으로는 구간을 지목할 수 없다. 실측하면 이렇다.

    동계천로          88 구간
    동명로            68 구간
    필문대로205번길   33 구간

`publish_web.py` 가 지금 붙이는 `seg_no` 는 `(road_name, _oy, _ox)` 정렬
순번이다. 즉 **정렬 결과에 따라 달라지는 임의 번호**다. 노딩이 하나만
바뀌어도 전부 밀린다 — `seg_id` 가 불변 키가 아닌 것과 같은 이유다
(MASTER §5).

'서/중/동' 같은 어휘를 붙이는 것도 같은 문제다. 우리가 만든 말이라
소방관이 못 알아듣는다.

── 대안: 기초번호 ─────────────────────────────────────────────
도로명주소법의 기초번호 체계를 쓴다. 법정 체계이고, **119 가 실제로
무전에서 쓰는 언어**다.

    도로 기점에서 20m 마다 기초번호가 2씩 증가한다.
    왼쪽은 홀수, 오른쪽은 짝수.
    거리 d 지점의 기초번호 = floor(d / 20) * 2 + 1

    "필문대로205번길 11-17"   ← 사람이 지도 없이 찾아갈 수 있다
    "DM00082"                 ← 우리끼리만 통한다

기하에서 유도되므로 노딩이 바뀌어도 **같은 자리는 같은 번호**다.
`seg_no` 와 달리 안정적이다.

── 검증 수단 ──────────────────────────────────────────────────
`data/processed/building_entrance.geojson` 의 실제 건물번호와 대조한다.

    uv run python tools/basisno_check.py

★ 한 가지 가정: 도로선이 기점→종점 방향으로 그려져 있다고 본다.
  `juso_elctrnmap` 의 `TL_SPRD_MANAGE` 는 대체로 그렇지만 전수 확인은
  안 했다. 위 대조에서 계통적으로 뒤집힌 도로가 나오면 해당 RN 만
  `REVERSED` 에 넣어 뒤집는다. 전역 규칙으로 바꾸지 마라.
"""
from __future__ import annotations

from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, unary_union

# 도로명주소법 시행규칙: 20m 마다 기초번호 2 증가.
BASIS_INTERVAL_M = 20.0

# 기점 방향이 뒤집힌 것으로 확인된 도로명. 대조 결과로만 채운다.
REVERSED: set[str] = set()


def basis_no(dist_m: float) -> int:
    """기점에서 dist_m 떨어진 지점의 기초번호(홀수 계열)."""
    if dist_m < 0:
        dist_m = 0.0
    return int(dist_m // BASIS_INTERVAL_M) * 2 + 1


class BasisNumberIndex:
    """도로명별로 선을 이어붙이고, 그 위 임의 지점의 기초번호를 준다.

    한 도로명이 여러 `road_link` 피처로 쪼개져 있으므로 피처별 누적거리를
    쓰면 안 된다. RN 으로 묶어 `linemerge` 한 뒤 전체 기점부터 잰다.
    """

    def __init__(self, geoms, names):
        self.line: dict[str, LineString] = {}
        self.unmerged: set[str] = set()

        bucket: dict[str, list] = {}
        for g, n in zip(geoms, names):
            if n is None or g is None or g.is_empty:
                continue
            bucket.setdefault(str(n), []).append(g)

        for rn, gs in bucket.items():
            merged = linemerge(unary_union(gs)) if len(gs) > 1 else gs[0]
            if isinstance(merged, MultiLineString):
                # 끊긴 도로다. 가장 긴 성분을 기준선으로 쓰고 표시해 둔다.
                merged = max(merged.geoms, key=lambda x: x.length)
                self.unmerged.add(rn)
            if rn in REVERSED:
                merged = LineString(list(merged.coords)[::-1])
            self.line[rn] = merged

    @classmethod
    def from_gdf(cls, road):
        """`road_link` GeoDataFrame 에서 만든다. RN 이 빈 행은 버린다."""
        r = road[road["RN"].notna()]
        return cls(list(r.geometry), list(r["RN"]))

    def range_for(self, rn, geom) -> tuple[int | None, int | None]:
        """구간 `geom` 이 걸치는 기초번호 구간 (시작, 끝)."""
        if rn is None:
            return None, None
        base = self.line.get(str(rn))
        if base is None:
            return None, None
        try:
            cs = base.project(geom.interpolate(0.0))
            ce = base.project(geom.interpolate(geom.length))
        except Exception:
            return None, None
        lo, hi = (cs, ce) if cs <= ce else (ce, cs)
        return basis_no(lo), basis_no(hi)

    def label(self, rn, geom) -> str | None:
        """사람이 읽는 구간 이름. '필문대로205번길 11-17'."""
        if rn is None:
            return None
        s, e = self.range_for(rn, geom)
        if s is None:
            return str(rn)
        return f"{rn} {s}" if s == e else f"{rn} {s}-{e}"

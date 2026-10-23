"""
structures.py — 구간 가까이에 **입체 구조물**(터널 · 고가 · 교량)이 있는가를 진단 칸으로 싣는다. **판정에 안 쓴다.** (Zm18 · DECISIONS §563)

IN    구간(EPSG:5186 선) · `juso_tunnel` · `juso_overpass` · `juso_bridge` 면(`data/processed/juso_*_5186.gpkg` — 도로명주소 기타자료)
OUT   `struct_kind`(`터널` · `고가` · `교량` — 반경 안에서 가장 가까운 것) · `struct_dist_m`(그 거리, m)
PARAM `RADIUS_M`
밖    **판정을 안 한다.** `seg/classify.py` 가 이 칸을 읽으면 시험이 운다(`tests/test_structures.py`). 판정 폐포(`segments.py`) 밖이다 — 출판(`publish_web`)이 부른다.
      **이 칸이 2D 가정을 깬다는 것도 안 말한다.** 입체 구조물 50m 안 구간의 괴리가 바깥보다 크지 않았다(DECISIONS §563-2: 안 0.197 · 밖 0.243, 비 0.81). 칸은 *어디가 입체인가*를 알려 줄 뿐이다.

★ `RADIUS_M = 50` 은 지시문이 정한 수다 — 이 데이터에서 도출한 값이 아니다.
★ **하천 면(`juso_river`)은 안 싣는다.** 입체가 아니다(복개천이 거기 들어 있는지도 이 판은 확인하지 못했다 — DM00562 에서 가장 가까운 하천 면이 900m 밖이다).
★ 면은 **입력 범위(`bbox_4326`) 안만** 적재된다 — 터널 10 중 4 · 교량 36 중 7 · 고가 4 중 0. 범위 밖 구조물은 이 칸에 없다. null 은 「없다」가 아니라 「적재된 것 중에는 없다」다.
"""
from __future__ import annotations

NAMES = ("struct_kind", "struct_dist_m")
RADIUS_M = 50.0
#: (적재 키, 표시 이름). 순서는 동거리일 때의 우선순위다.
KINDS = (("tunnel", "터널"), ("overpass", "고가"), ("bridge", "교량"))


def nearest(line, layers: dict) -> tuple[str | None, float | None]:
    """반경 안에서 가장 가까운 입체 구조물의 `(이름, 거리)`. 없으면 `(None, None)`. `layers`: 키 → 도형 목록."""
    best = (None, None)
    for key, label in KINDS:
        for g in layers.get(key, ()):
            d = float(line.distance(g))
            if d <= RADIUS_M and (best[1] is None or d < best[1]):
                best = (label, d)
    return best[0], (None if best[1] is None else round(best[1], 1))


def columns(lines, layers: dict) -> dict[str, list]:
    """구간 선 목록 → 두 칸의 목록(같은 순서). 판정에 안 쓴다."""
    out: dict[str, list] = {k: [] for k in NAMES}
    for ln in lines:
        kind, dist = nearest(ln, layers)
        out["struct_kind"].append(kind)
        out["struct_dist_m"].append(dist)
    return out

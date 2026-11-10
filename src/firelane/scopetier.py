"""
scopetier.py — 구간마다 **발행 범위 분류** `scope_tier` 를 붙인다. (PLAN #62 · DECISIONS §612 · §613)

IN    구간 표(`in_emd` · `route_usage` · `road_name`) · `firelane.fireaccess.load` 가 읽은 소방서 표 행
OUT   `scope_tier` — `target` · `corridor` · `listed` · `reference` 넷 중 하나(구간마다)
PARAM 없음
밖    **구간을 하나도 안 떨군다** — 이름만 붙인다. 1,281구간을 전부 판정하고 전부 발행하며, 어디를 보여줄지는
      표출(내비)이 이 칸으로 고른다. **판정에 안 쓴다**: 판정 폐포(`segments.py`)가 이 모듈을 import 하는 순간
      골든 코드 지문 안이 된다(`tests/test_scope_tier.py` 가 그 한 줄을 문다).
      **수를 안 적는다** — 몇 구간인지는 이 칸을 세는 쪽이 계산한다.

── 정의 (DECISIONS §613) ──────────────────────────────────────────
발행 범위 = 대상지 ∪ 회랑 ∪ 지정. 위에서 아래로 처음 맞는 것 하나다.

    target     동명동 안(`in_emd`)
    corridor   동 밖 · `route_usage > 0`
    listed     동 밖 · `route_usage == 0` · 소방서 표 지역명의 **주소부**에 `road_name` 이 통째로 나온다
    reference  나머지(참고)

★ **주소부 = 지역명의 첫 `(` 앞.** 소방서 지역명은 「<주소> <번지>(<동>) 일대(구, <옛 이름 · 주변 길>)」 꼴이다.
  괄호 안은 지정이 아니라 **설명**이다 — 「(구, 지호로)」가 지호로를 지정으로 만들면 안 된다(DECISIONS §612-3).
  지역명 어디서든 걸리는 `nfa_access_listed` 는 303구간이고 그 286 이 스스로 느슨이라 이 정의를 쓰지 않는다.
★ **매처를 새로 안 만든다.** 이름의 정확 일치(공백 허용 · 부분 문자열 아님)는 `fireaccess.match` 의 것이고, 여기는
  **찾는 범위를 주소부로 좁힌 행**을 넘길 뿐이다. 매칭 규칙을 고치는 날 한 곳만 고치면 되게 하려는 것이다.
★ **본선 번지 행**(`지산로 37` · `중앙로 283-1외` · `경양로 333외` · `무등로 314외`)은 번지 하나를 가리킨다. 본선 전체가 걸리던
  과대를 **번지 위치로 좁혔다**(PLAN #186 · DECISIONS §629-6 의 답):
    · 번지 → `(RN_CD, 본번, 부번)`. `RN_CD` 는 `road_link` 의 `RN` ↔ `RN_CD`. 부번이 건물에 있으면 그 동, 없으면 본번의 동 전부.
    · 그 건물 폴리곤에서 **반경 = 그 행 `구간거리(m)` ÷ 2** 안의 같은 도로명 구간만 `listed` 다(`외` 는 번지 목록으로 풀지 않는다 — 구간거리가 범위다).
    · 건물이 **0 이면 폴백 A — 본선 전체를 유지한다.** 지정을 없는 것으로 만들지 않는다(미탐이 비싸다). 대신 근거를 가른다:
      `scope_basis` = `address`(번지 위치로 좁혀서 걸렸다) · `road`(도로명뿐 — 번길 행 · 폴백).
    · 번호 없는 행(번길 · `충장로 5가`)은 종전 그대로 본선 전체 · `road` 다.
  **판정에 안 쓴다 · 구간을 하나도 안 떨군다** — `reference` 로 가는 구간이 줄 뿐이다.
"""
from __future__ import annotations

import re

from firelane import fireaccess

#: 본선 번지 — `경양로 333외` · `중앙로 283-1외` · `지산로 37` · `무등로 314 외`. 번길(`제봉로 184번길 10`)과 `충장로 5가` 는 아니다.
_STREET_ADDR = re.compile(r"(?<![가-힣\d])([가-힣]+로)\s+(\d+)(?:-(\d+))?(?![\d-])(?!\s*번길)(?!가)")

#: 값 넷. 순서가 우선순위다.
TARGET, CORRIDOR, LISTED, REFERENCE = "target", "corridor", "listed", "reference"
TIERS = (TARGET, CORRIDOR, LISTED, REFERENCE)

#: 발행 범위에 드는 값. **`reference` 는 안 든다** — 집계가 이 집합 하나로 센다.
IN_SCOPE = frozenset((TARGET, CORRIDOR, LISTED))

_PAREN = re.compile(r"[(（]")


def address_part(text: str | None) -> str:
    """지역명의 주소부 — 첫 괄호(`(` 또는 `（`) 앞."""
    return _PAREN.split(text or "", maxsplit=1)[0]


def address_rows(rows: list[dict]) -> list[dict]:
    """`fireaccess.load` 행에서 `text` · `norm` 만 주소부로 좁힌 사본. 나머지 칸은 그대로다."""
    out = []
    for r in rows:
        head = address_part(r["text"])
        out.append({**r, "text": head, "norm": fireaccess._norm(head)})
    return out


def is_designated(road_name: str | None, arows: list[dict]) -> bool:
    """이 `road_name` 이 주소부 행에 통째로 한 도로명으로 나타나는가. 매칭은 `fireaccess.match` 의 것이다."""
    return fireaccess.match(road_name, arows) is not None


def _positive(x) -> bool:
    """`route_usage > 0`. 결손(None · NaN)은 0 이다."""
    try:
        return x is not None and x == x and float(x) > 0
    except (TypeError, ValueError):
        return False


def _truthy(x) -> bool:
    return x is not None and x == x and bool(x)


def tier(in_emd, route_usage, designated: bool) -> str:
    """분류 하나. **정의의 정본은 이 함수다** — 발행 칸도 시험도 이것을 부른다."""
    if _truthy(in_emd):
        return TARGET
    if _positive(route_usage):
        return CORRIDOR
    if designated:
        return LISTED
    return REFERENCE


def in_scope(t: str) -> bool:
    """발행 범위에 드는가. `reference` 는 안 든다."""
    return t in IN_SCOPE


ADDRESS, ROAD = "address", "road"


def street_address(text: str | None) -> tuple[str, int, int | None] | None:
    """주소부의 본선 번지 `(도로명, 본번, 부번)`. 번지가 없거나 번길 · `5가` 면 None."""
    m = _STREET_ADDR.search(address_part(text))
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3)) if m.group(3) else None


def _buildings_of(buildings, rn_cd: dict, road: str, main: int, sub: int | None):
    """번지의 건물 폴리곤. 부번이 있으면 그 동, 없으면 본번의 동 전부. 없으면 빈 목록."""
    codes = rn_cd.get(road) or ()
    if not codes:
        return []
    hit = buildings[buildings["RN_CD"].astype(str).isin([str(c) for c in codes])
                    & (buildings["BULD_MNNM"].astype(int) == main)]
    if sub is not None:
        exact = hit[hit["BULD_SLNO"].astype(int) == sub]
        if len(exact):
            hit = exact
    return list(hit.geometry)


def designations(road_names, geoms, rows: list[dict], buildings, rn_cd: dict) -> tuple[list[bool], list[str | None]]:
    """구간마다 (지정인가, 근거). `geoms` 는 구간 형상 · **EPSG:5186(미터)** · `buildings` 도 같은 좌표계.

    매처는 새로 안 만든다 — 행이 도로명에 걸리는가는 `fireaccess.match` 의 것이다.
    """
    from shapely.ops import unary_union

    arows = address_rows(rows)
    names = list(road_names)
    out_d = [False] * len(names)
    out_b: list[str | None] = [None] * len(names)
    for rn in {n for n in names if n}:
        hits = [r for r in arows if fireaccess.match(rn, [r]) is not None]
        if not hits:
            continue
        zones = []           # 번지로 좁힌 행들의 (건물 합 · 반경)
        whole = False        # 도로 전체를 거는 행이 하나라도 있나
        for r in hits:
            addr = street_address(r["text"])
            blds = (_buildings_of(buildings, rn_cd, addr[0], addr[1], addr[2])
                    if addr and addr[0] == rn else [])
            if not blds:
                whole = True          # 번호 없는 행 · **0건 폴백 A** — 본선 전체를 유지한다
            else:
                zones.append((unary_union(blds), r["len"] / 2.0))
        for i, n in enumerate(names):
            if n != rn:
                continue
            if whole:
                out_d[i], out_b[i] = True, ROAD
            elif any(geoms[i].distance(z) <= rad for z, rad in zones):
                out_d[i], out_b[i] = True, ADDRESS
    return out_d, out_b


def columns(in_emd, route_usage, road_names, rows: list[dict], geoms=None, buildings=None,
            rn_cd: dict | None = None) -> dict[str, list]:
    """구간마다의 `scope_tier` · `scope_basis`(같은 순서의 목록). 판정에 안 쓴다.

    `geoms` · `buildings` · `rn_cd` 가 없으면 종전대로 **도로명 전체**(근거는 `road`)다.
    `scope_basis` 는 `listed` 인 구간에만 값이 있다.
    """
    names = list(road_names)
    if geoms is not None and buildings is not None:
        des, basis = designations(names, list(geoms), rows, buildings, rn_cd or {})
    else:
        arows = address_rows(rows)
        memo: dict[str | None, bool] = {}
        for rn in names:
            if rn not in memo:
                memo[rn] = is_designated(rn, arows)
        des = [memo[rn] for rn in names]
        basis = [ROAD if d else None for d in des]
    tiers = [tier(e, u, d) for e, u, d in zip(in_emd, route_usage, des, strict=True)]
    return {"scope_tier": tiers,
            "scope_basis": [b if t == LISTED else None for t, b in zip(tiers, basis, strict=True)]}

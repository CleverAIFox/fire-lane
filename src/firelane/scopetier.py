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
★ 본선 번지 행(`지산로 37` · `중앙로 283-1외`)은 번지 하나를 가리키는데 본선 전체가 걸린다. 그 과대는 안다
  (`PLAN #186` — 번지 위치의 구간만 매칭하려면 `building` 의 도로명코드 + 건물번호로 좁혀야 한다).
"""
from __future__ import annotations

import re

from firelane import fireaccess

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


def columns(in_emd, route_usage, road_names, rows: list[dict]) -> dict[str, list[str]]:
    """구간마다의 `scope_tier`(같은 순서의 목록). 판정에 안 쓴다."""
    arows = address_rows(rows)
    memo: dict[str | None, bool] = {}
    out = []
    for e, u, rn in zip(in_emd, route_usage, road_names, strict=True):
        if rn not in memo:
            memo[rn] = is_designated(rn, arows)
        out.append(tier(e, u, memo[rn]))
    return {"scope_tier": out}

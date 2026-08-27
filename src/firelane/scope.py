#!/usr/bin/env python3
"""
scope.py — 공간 범위의 통제 어휘. **선언이 정본이고 파일명은 그 별칭이다.**

── 왜 생겼나 ───────────────────────────────────────────────────
raw 36건의 스코프 토큰이 여섯 갈래였고, 그 여섯이 **서로 다른 세 축**을
한 자리에 뭉개고 있었다.

    전국          kr · (없음)          ← kfs 8종은 토큰 자체가 없다
    시도          jngj
    시군구        gjdonggu · dongu     ← 같은 것을 두 이름으로 적었다
    관할서        gj_dong              ← ★ 행정구역이 아니다. 동부소방서다
    도엽          gj9708 · gj35616 · gj037

`gj_dong` 이 제일 나쁘다. `dongu`(행정구역 동구) 와 눈으로 안 갈린다.
`safety_fire_access_gj_dong_20250731.csv` 는 **동부소방서 관할** 자료이고
`gjcity_bin_trash_dongu_20241130.csv` 는 **동구 행정구역** 자료다.
둘을 같은 필드에 적는 한, 언젠가 관할서 자료를 행정구역으로 클립한다.

축을 셋으로 가른다. 파일명은 `scope` 하나만 갖고, 나머지 둘은 대장 필드다.

    scope      행정구역. 포함관계가 성립한다 (kr ⊃ jngj ⊃ jngj-dong ⊃ …)
    authority  관할기관. 행정구역과 경계가 다르다. 파일명에 넣지 않는다
    part       도엽·분할본. 파일명의 선택 필드이며 스코프가 아니다

── 왜 별칭인가 ─────────────────────────────────────────────────
법정동코드를 파일명에 그대로 박으면(`emd12210108`) 기계는 편하지만 사람이
못 읽고, 2026-07-01 개편처럼 **코드가 바뀌면 파일명이 거짓이 된다**
(구 광주 동구 29110 → 12210). 별칭을 쓰고 코드는 선언에 둔다. 개편이 오면
선언 한 줄을 고치고 파일명은 그대로 둔다.

IN    sources.yaml(scopes)
OUT   없음 (조회 전용)
PARAM 없음
"""
from __future__ import annotations

import functools

import yaml

from firelane import paths

# 좁은 쪽이 큰 수. 포함관계 판정에 쓴다.
LEVELS = {"nation": 0, "sido": 1, "sigungu": 2, "emd": 3}

# 별칭 문법. 언더스코어는 파일명의 필드 구분자이므로 **토큰 안에서 금지**한다.
# `gj_dong` 이 `gj` + `dong` 인지 `gj_dong` 한 덩어리인지 파서가 못 가른 것이
# 애초의 사고 원인이다. 계층은 하이픈으로 잇는다 — `jngj-dong-dm`.
ALIAS_RE = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"


class ScopeError(RuntimeError):
    """스코프 선언이 깨졌거나 통제 어휘 밖이다."""


# ── 선언 ──────────────────────────────────────────────────────
# ★ 이 기본값은 `sources.yaml` 에 `scopes:` 블록이 아직 없을 때만 쓴다.
#   블록이 생기면 그쪽이 이긴다. 코드에 사실을 박아두지 않는다.
DEFAULT = {
    "kr": {"level": "nation", "code": None, "label": "전국", "parent": None},
    "jngj": {"level": "sido", "code": "12", "label": "전남광주통합특별시",
             "parent": "kr"},
    "jngj-dong": {"level": "sigungu", "code": "12210",
                  "label": "전남광주통합특별시 동구", "parent": "jngj",
                  "former_code": "29110",
                  "note": "2026-07-01 개편. 구 광주 동구 29110 → 12210"},
    "jngj-dong-dm": {"level": "emd", "code": "12210108",
                     "label": "전남광주통합특별시 동구 동명동",
                     "parent": "jngj-dong"},
}

# 옛 파일명이 쓰던 토큰 → 정규 별칭. **마이그레이션 전용이다.**
# 새 파일이 이 표에 걸리면 통과가 아니라 경고다 — 표는 과거를 읽기 위한
# 것이지 미래를 허용하기 위한 것이 아니다.
LEGACY = {
    "gjdonggu": "jngj-dong",
    "dongu": "jngj-dong",
    "gj": "jngj",
    # ★ gj_dong 은 스코프가 아니다. 동부소방서 관할이며 행정구역과 경계가
    #   다르다. 별칭을 주지 않는다 — 주는 순간 그 사실이 지워진다.
    #   대장에서 scope: jngj-dong + authority: 동부소방서 로 쪼갠다.
}

# 스코프인 척했지만 실은 도엽인 것들. 접두만 보고 판정한다.
LEGACY_PART_PREFIXES = ("gj9", "gj35616", "gj0")


@functools.lru_cache(maxsize=1)
def spec() -> dict:
    f = paths.ROOT / "sources.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    S = d.get("scopes") or DEFAULT
    _validate(S)
    return S


def _validate(S: dict) -> None:
    import re
    for alias, v in S.items():
        if not re.match(ALIAS_RE, alias):
            raise ScopeError(
                f"스코프 별칭 {alias!r} 이 문법 밖이다: {ALIAS_RE}\n"
                "  ★ 언더스코어는 파일명 필드 구분자다. 토큰 안에 쓰면\n"
                "    `gj_dong` 처럼 파서가 경계를 못 찾는다.")
        if v.get("level") not in LEVELS:
            raise ScopeError(
                f"scopes.{alias}.level 이 {sorted(LEVELS)} 밖이다: {v.get('level')!r}")
        p = v.get("parent")
        if p is not None and p not in S:
            raise ScopeError(f"scopes.{alias}.parent 가 선언에 없다: {p!r}")
        if p is not None and LEVELS[S[p]["level"]] >= LEVELS[v["level"]]:
            raise ScopeError(
                f"scopes.{alias} 의 부모 {p!r} 가 더 좁거나 같다. "
                "포함관계가 뒤집혀 있다.")


def known(alias: str) -> bool:
    return alias in spec()


def resolve(token: str) -> tuple[str, str]:
    """파일명 토큰 → (정규 별칭, 상태).

    상태는 셋이다 — `ok` · `legacy` · `part`.
    `part` 는 스코프가 아니라 도엽이라는 뜻이며, 호출자가 필드를 옮겨야 한다.
    """
    if known(token):
        return token, "ok"
    if token in LEGACY:
        return LEGACY[token], "legacy"
    if token.startswith(LEGACY_PART_PREFIXES):
        return token, "part"
    raise ScopeError(
        f"통제 어휘 밖의 스코프 토큰: {token!r}\n"
        f"  선언된 것 — {', '.join(sorted(spec()))}\n"
        "  ★ 새 스코프가 필요하면 sources.yaml 의 scopes 에 먼저 적는다.\n"
        "    파일명이 선언을 앞서면 대장이 정본이라는 원칙이 깨진다.")


def chain(alias: str) -> list[str]:
    """자기부터 최상위까지. `jngj-dong-dm` → [dm, dong, jngj, kr]"""
    S, out, cur = spec(), [], alias
    seen = set()
    while cur is not None:
        if cur in seen:
            raise ScopeError(f"scopes 에 순환이 있다: {cur!r}")
        seen.add(cur)
        out.append(cur)
        cur = S[cur].get("parent")
    return out


def contains(outer: str, inner: str) -> bool:
    """`outer` 가 `inner` 를 포함하나. 같으면 참이다."""
    return outer in chain(inner)


def covers_project(alias: str, target: str = "jngj-dong-dm") -> bool:
    """이 데이터의 범위가 분석 대상을 덮나.

    ★ 덮지 못하는 소스는 결손이 조용히 난다. 2026-08-18 에 V-WORLD
      74도엽이 동명동 북부 12도엽을 흘려 1,091구간 중 755개(69%)의 중점이
      폴리곤 밖이었다. 그때 배운 것이 이것이다 —
      **행정구역 단위 취득은 스코프를 보장하지 않는다.**
      선언 단계에서 걸러낼 수 있는 것은 여기서 걸러낸다.
    """
    return contains(alias, target)


def label(alias: str) -> str:
    return spec()[alias]["label"]


def code(alias: str) -> str | None:
    return spec()[alias]["code"]

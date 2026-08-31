#!/usr/bin/env python3
"""
providers.py — raw 의 1단 폴더(제공기관) 정본. **목록은 여기 하나뿐이다.**

── 왜 ─────────────────────────────────────────────────────────
2026-08-24 에 `normalize_raw` 머리말이 7종, `MASTER §18-2a` 가 8종,
`ORG` 상수가 9종이었다. 정정하면서 아홉으로 통일했는데 **통일한 값이 또
네 곳에 복사됐다** — `layers.raw.naming` 정규식 · `normalize_raw.ORG` ·
`test_normalize_rules.ORG` · `test_place_idempotent.ORG`.

★ 값을 맞추는 것으로는 안 끝난다. **사본이 남아 있으면 다시 갈린다.**
  `stem` 이관이 역산을 조회로 바꾼 것과 같은 수술이다 — 정본을 하나
  두고 나머지는 읽기만 한다.

── state ──────────────────────────────────────────────────────
    active    대장 datasets 가 읽는다. 폴더가 있어야 하고 비면 결손이다
    reserved  등재만. 파일 0건이 정상이고 **폴더도 없어야 한다**

★ reserved 를 둔 이유는 빈 폴더에 근거를 붙이기 위해서다. 2026-08-19 에
  `nsdi/AL_D002_12_20260808.zip` 970MB 를 격리하고 껍데기가 남았는데,
  `doctor` 의 무결성 검사가 `p.is_file()` 로 걸러서 두 달 동안 아무도
  몰랐다. 폴더는 파일이 아니라서 대장과 대조되지 않았다.

IN    sources.yaml (layers.raw.providers)
OUT   없음 (순수 조회)
PARAM 없음
"""
from __future__ import annotations

import re
from functools import lru_cache

from firelane import layers as L

ACTIVE, RESERVED = "active", "reserved"
STATES = (ACTIVE, RESERVED)


class ProviderError(RuntimeError):
    """provider 선언이 문법 밖이거나 조회가 실패했다."""


@lru_cache(maxsize=1)
def spec() -> dict[str, dict]:
    """{provider: {org, state, ...}}. 선언 자체를 검증하고 돌려준다."""
    raw = L.policy("raw")
    P = raw.get("providers")
    if not P:
        raise ProviderError(
            "layers.raw.providers 가 없다.\n"
            "  ★ 이 목록이 정본이다. 정규식에서 역산하지 마라 — 역산이"
            " 사고 네 건의 뿌리였다(DECISIONS §73).")
    for name, e in P.items():
        if not re.fullmatch(r"[a-z][a-z0-9]{1,15}", name):
            raise ProviderError(f"provider 가 문법 밖이다: {name!r}")
        if e.get("state") not in STATES:
            raise ProviderError(
                f"{name}: state 는 {STATES} 중 하나여야 한다: {e.get('state')!r}\n"
                "  ★ state 는 폴더가 존재해도 되는 근거다. 비워두면 빈 폴더가"
                " 다시 근거 없이 남는다.")
        if not (e.get("org") or "").strip():
            raise ProviderError(f"{name}: org(기관명) 이 비었다")
    return dict(P)


def all() -> set[str]:                                      # noqa: A001
    """선언된 전부. `normalize_raw` 통과 규칙이 쓰는 집합이다."""
    return set(spec())


def active() -> set[str]:
    """실제로 파일이 있어야 하는 것."""
    return {k for k, v in spec().items() if v["state"] == ACTIVE}


def reserved() -> set[str]:
    """등재만 된 것. 폴더가 있으면 그것이 결함이다."""
    return {k for k, v in spec().items() if v["state"] == RESERVED}


def known(name: str) -> bool:
    return name in spec()


def org(name: str) -> str:
    if not known(name):
        raise ProviderError(f"등재되지 않은 provider: {name!r}\n"
                            f"  등재된 것 — {', '.join(sorted(spec()))}")
    return spec()[name]["org"]


def pattern() -> str:
    """`layers.raw.naming` 이 가져야 할 값. 선언에서 만든다.

    ★ 정규식을 손으로 고치지 마라. 이 함수가 만든 것과 다르면
      `test_provider_registry` 가 실패한다.
    """
    return "^(" + "|".join(sorted(all())) + ")/"


def naming_matches_registry() -> tuple[bool, str]:
    """선언된 정규식이 등재 목록과 같은가. (같음, 설명)"""
    declared = L.policy("raw").get("naming") or ""
    got = set(re.findall(r"[a-z][a-z0-9]*", declared[declared.find("(") + 1:
                                                     declared.find(")")]))
    want = all()
    if got == want:
        return True, ""
    return False, (f"naming 정규식이 providers 와 다르다\n"
                   f"  정규식에만  {sorted(got - want)}\n"
                   f"  등재에만    {sorted(want - got)}\n"
                   f"  기대값      {pattern()}")


def depth() -> int:
    """raw 아래 허용 깊이. `{provider}/{file}` 이므로 2다."""
    return int(L.policy("raw").get("depth") or 2)

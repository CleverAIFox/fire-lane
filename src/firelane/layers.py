#!/usr/bin/env python3
"""
layers.py — 계층 선언과 경로 해석을 이름으로 묶는다.

── 역할 분리 ───────────────────────────────────────────────────
    paths.py       경로 해석의 정본. 환경변수를 탄다(기계마다 다르다)
    sources.yaml   정책의 정본. 기계와 무관하다
    여기           둘을 이름으로 묶는다. `layers` 블록은 여기서만 읽는다

중복이 아니라 분리다. `params.py`(임계값 정본) ↔ `config.js`(표시용 사본)
와 같은 구조다.

★ `paths.py` 가 yaml 을 읽게 만들지 않는다. 그것은 모든 모듈이 import 하는
  최하층이고, 거기에 파싱을 넣으면 실패 모드가 하나 는다. 경로는 상수로
  두고 정책만 여기서 얹는다.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-24. MASTER §18-1 이 계층을 산문으로 선언하고 `paths.py` 가 경로를
따로 잡고 있었다. 둘이 어긋나도 아무도 몰랐다.

`interim` 은 **양쪽 다 없었다.** 그래서 탐색 도구가 갈 곳이 없어 자기
자리를 발명했다 — `jijeok_probe._side()` 가 `RAW.parent.parent`(프로젝트
루트)를 쓰며 주석으로 그것을 자백하고 있었고, SSD 루트에 11.7MB 가 떨어졌다.

**계층이 없으면 파일은 아무 데나 떨어진다.** 규율이 아니라 구조의 문제다.

IN    sources.yaml(layers) · firelane.paths
OUT   없음 (조회 전용)
PARAM 없음
"""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

from firelane import paths

# 선언 이름 → paths 의 상수 이름. 여기가 두 정본을 잇는 유일한 자리다.
BIND = {
    "landing": "LANDING",
    "raw": "RAW",
    "norm": "NORM",
    "interim": "INTERIM",
    "processed": "PROCESSED",
    "field": "FIELD",
    "quarantine": "QUARANTINE",
    "web": "WEB",
    "golden": "GOLDEN",
    "baseline": "BASELINE",
}

REQUIRED_FIELDS = ("base", "sub", "required", "mutable",
                   "committed", "backup", "regenerable")


class LayerError(RuntimeError):
    """계층 선언이 깨졌다."""


@functools.lru_cache(maxsize=1)
def spec() -> dict:
    """`sources.yaml` 의 `layers` 블록. 없으면 죽는다."""
    f = paths.ROOT / "sources.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    L = d.get("layers")
    if not L:
        raise LayerError(
            f"{f} 에 layers 블록이 없다.\n"
            "  계층은 선언이 정본이다. 코드가 자기 자리를 발명하면\n"
            "  2026-08-24 의 SSD 루트 오염이 되풀이된다.")
    for name, v in L.items():
        miss = [k for k in REQUIRED_FIELDS if k not in v]
        if miss:
            raise LayerError(f"layers.{name} 에 {', '.join(miss)} 가 없다")
        if v["base"] not in ("data", "repo"):
            raise LayerError(
                f"layers.{name}.base 는 data|repo 여야 한다: {v['base']!r}")
    return L


def names() -> list[str]:
    return list(spec())


def policy(name: str) -> dict:
    try:
        return spec()[name]
    except KeyError:
        raise LayerError(f"선언에 없는 계층: {name!r}") from None


def path(name: str) -> Path:
    """이 계층의 실제 경로. `paths.py` 가 정본이다."""
    const = BIND.get(name)
    if const is None:
        raise LayerError(f"BIND 에 {name!r} 가 없다 — 선언과 코드가 어긋난다")
    p = getattr(paths, const, None)
    if p is None:
        raise LayerError(
            f"paths.{const} 가 없다. 선언은 {name} 을 요구한다.\n"
            "  선언만 있고 코드가 모르면 그 계층을 쓰려던 도구는\n"
            "  매번 자기 자리를 발명한다.")
    return Path(p)


def declared_base(name: str) -> str:
    """이 계층이 왜 거기 있나 — data(SSD) 인가 repo(저장소) 인가."""
    return policy(name)["base"]


def expected_base(name: str) -> Path:
    d = paths.DATA or (paths.ROOT / "data")
    return Path(d) if declared_base(name) == "data" else paths.ROOT


def of(kind: str) -> list[str]:
    """불리언 정책으로 계층을 고른다. `of("backup")` 처럼 쓴다."""
    return [n for n, v in spec().items() if v.get(kind) is True]


def implemented(name: str) -> bool:
    """`status: 미구현` 이 아니면 구현된 것으로 본다."""
    return policy(name).get("status") != "미구현"

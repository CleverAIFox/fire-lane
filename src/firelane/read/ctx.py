"""
ctx.py — 갈래 함수가 받는 **하나의 인자**.  (PLAN §1 #132 · DECISIONS §274)

★ 인자를 일곱 개 늘어놓지 않는 이유는 취향이 아니다. 갈래가 열둘이고 저마다
  쓰는 칸이 다르다 — 늘어놓으면 새 갈래가 칸 하나를 더 필요로 할 때마다
  **열두 곳의 서명**이 바뀐다. 한 덩이로 받으면 한 곳만 바뀐다.

★ `save` 를 **주입으로 받는다.** 갈래가 `ingest.save` 를 직접 부르면 임포트가
  `read` → `ingest` → `read` 로 돈다. 그리고 시험이 가짜 `save` 를 꽂아
  갈래 하나만 떼어 돌릴 수 있다 — 지금은 `ngii1k` 하나만 쓴다.

IN    없음 (자료 구조)
OUT   없음
밖    **칸이 참인지는 안 본다.** `src` 가 실재하는가 · `crs` 가 유효한가는
      `ingest.build` 가 이미 보고 넘긴다. 여기서 다시 세면 두 벌이 된다.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Ctx:
    """갈래 하나가 한 데이터셋을 읽는 데 필요한 전부."""

    key: str                    #: 대장 키
    e: dict[str, Any]           #: 대장 항목
    src: Path                   #: 고른 실물 (hits[0])
    hits: list[Path]            #: 글롭이 잡은 전부 — 도엽 묶음이 쓴다
    crs: str                    #: 대장이 선언한 원본 좌표계
    tmp: Path                   #: 이 실행의 작업 폴더
    out: Path                   #: 산출 폴더 — `ingest.OUT` 을 부를 때 넘긴다
    rec: dict[str, Any]         #: 여기까지 쌓인 계보 조각
    save: Callable[..., dict]   #: `ingest.save` — 주입으로 받는다

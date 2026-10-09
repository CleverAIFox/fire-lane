"""
hashing.py — 파일 sha256. **한 곳에서만 잰다.**

★ 2026-09-13. 같은 구현이 10곳이었다. `dupcheck` 가 ×7(44노드) ·
  ×3(51노드) 두 군으로 셌다. 이름만 달랐다 — `sha256` · `sha` · `_sha`,
  게다가 `doctor` 는 `_sha256 = _sha` 별칭까지 달고 있었다.

★ 같은 것을 두 이름으로 부르면 사람도 도구도 한 번 더 속는다. 이 저장소가
  232번 당한 형태다.

★ 청크 크기를 바꿔도 결과가 같아야 한다 — 그래서 인자로 두되 기본값을
  한 곳에 둔다. 사본이던 시절에는 한 곳만 고치면 나머지 아홉이 안 따라왔다.

★ 2026-10-09. **같은 물음이 하나 더 있었다** — 「무엇을 내용으로 세지 **않나**」.
  `as_of` · `git_sha` 는 매 실행 바뀌고 `git_sha` 는 **직전 커밋**을 적는다.
  추적되는 파일에 그것을 쓰면 커밋할 때마다 값이 또 바뀌어 **도달할 수 없는
  고정점**이 된다 — 열차가 「전수 초록인데 추적 파일이 더럽다」로 영원히 선다.
  `tests/test_evalgen.py` 가 그 목록을 이미 들고 있었고 **git 으로 가는 길이
  그것을 몰랐다**(족 2 · 정본이 둘). 그래서 목록을 이 파일로 올린다.

IN    파일 경로 · 쓸 사전
OUT   64자 소문자 16진수 · 썼는가
PARAM CHUNK · VOLATILE
밖    **무엇이 내용인가는 안 정한다** — 휘발 칸만 센다. 수가 옳은가는
      산출한 도구가 든다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CHUNK = 1 << 20

#: 시계와 커밋만 적는 **맨 위** 칸. 내용이 아니다.
#: ★ 맨 위에서만 뗀다 — 아래쪽의 같은 이름은 내용일 수 있다(행마다 적는 지문).
VOLATILE = ("as_of", "frozen_at", "git_sha", "generated_at")


def without(obj: object, volatile: tuple[str, ...] = VOLATILE) -> object:
    """휘발 칸을 **맨 위에서만** 뗀 사본."""
    if not isinstance(obj, dict):
        return obj
    return {k: v for k, v in obj.items() if k not in volatile}


def write_stable(p: Path, obj: object, *, indent: int = 2,
                 volatile: tuple[str, ...] = VOLATILE) -> bool:
    """**휘발 칸 말고** 달라졌을 때만 쓴다. 썼으면 True.

    ★ 안 쓰면 옛 `as_of` 가 남는다. 그것이 **더 참이다** — 수가 그때 것이다.
    ★ 읽다 깨지면 **쓴다.** 조용히 두면 깨진 파일이 영원히 남는다.
    """
    p = Path(p)
    txt = json.dumps(obj, ensure_ascii=False, indent=indent) + "\n"
    if p.is_file():
        try:
            old = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = None
        if old is not None and without(old, volatile) == without(obj, volatile):
            return False
    p.write_text(txt, encoding="utf-8")
    return True


def sha256(p: Path, chunk: int = CHUNK) -> str:
    """파일 전체의 sha256. 큰 파일을 통째로 안 읽는다."""
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()

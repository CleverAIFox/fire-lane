"""
hashing.py — 파일 sha256. **한 곳에서만 잰다.**

★ 2026-09-13. 같은 구현이 10곳이었다. `dupcheck` 가 ×7(44노드) ·
  ×3(51노드) 두 군으로 셌다. 이름만 달랐다 — `sha256` · `sha` · `_sha`,
  게다가 `doctor` 는 `_sha256 = _sha` 별칭까지 달고 있었다.

★ 같은 것을 두 이름으로 부르면 사람도 도구도 한 번 더 속는다. 이 저장소가
  232번 당한 형태다.

★ 청크 크기를 바꿔도 결과가 같아야 한다 — 그래서 인자로 두되 기본값을
  한 곳에 둔다. 사본이던 시절에는 한 곳만 고치면 나머지 아홉이 안 따라왔다.

★ 2026-10-14 (DECISIONS 536). **ENOMEM 에 한 번 물러선다.** WSL 에서
  `/mnt/f`(drvfs) 의 3.97 GB 를 훑다가 `f.read(1 MiB)` 가
  `OSError: [Errno 12] Cannot allocate memory` 로 터졌고, 반입 사슬
  4단계가 역추적을 토하고 죽었다. 위의 「청크를 바꿔도 결과가 같다」가
  **이미 선언돼 있으므로** 작은 청크로 다시 읽는 것은 같은 답이다 —
  규약이 고치는 길을 미리 열어둔 자리다.

IN    파일 경로
OUT   64자 소문자 16진수
"""
from __future__ import annotations

import errno
import hashlib
from pathlib import Path

CHUNK = 1 << 20
SMALL = 1 << 16   # ENOMEM 때 물러서는 자리. 같은 답이 나온다(위 ★)


class NoMemory(OSError):
    """작은 청크로도 못 읽었다. 기계가 모자란 것이고 파일 탓이 아니다."""


def _digest(p: Path, chunk: int) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def sha256(p: Path, chunk: int = CHUNK) -> str:
    """파일 전체의 sha256. 큰 파일을 통째로 안 읽는다.

    ENOMEM 이면 `SMALL` 로 한 번 물러선다. 그래도 안 되면 `NoMemory` —
    **어느 쪽이 모자란지 말하고** 멈춘다. 다른 OSError 는 그대로 올린다.
    """
    sizes = (chunk, SMALL) if chunk > SMALL else (chunk,)
    for i, c in enumerate(sizes):
        try:
            return _digest(p, c)
        except OSError as e:
            if e.errno != errno.ENOMEM:
                raise
            if i == len(sizes) - 1:
                raise NoMemory(
                    errno.ENOMEM,
                    f"{p} 를 {c}B 청크로도 못 읽었다 — 기계의 메모리다",
                ) from e
    raise AssertionError("닿지 않는다")   # pragma: no cover
